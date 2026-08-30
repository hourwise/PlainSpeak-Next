"""Running style analysis over a structured document.

The style layer measures clean prose. It does not parse, does not know what
Markdown is, and does not compute source offsets — so something has to translate
between the document representation and what it needs, and this is that
something. Same arrangement as `projection`: exactly one parser in the project,
and every layer that needs structure is told about it rather than working it out.

What style receives is the *projected* text of each block — markup already
removed by the document layer — labelled with what kind of block it was and
where it sits. Block kinds come from the representation rather than from
guessing at the text, which is the whole reason the representation exists.
"""
from __future__ import annotations

from typing import Optional

from ..document.model import (
    CodeBlock,
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    Quote,
    Table,
)
from ..style import DocumentStructure, ProfiledAnalysis, ProseBlock, StyleAnalysis
from ..style import StyleObservations
from ..style import analyze as analyze_prose
from ..style import compare_profiles as compare_prose_profiles
from ..style import interpret as interpret_prose
from ..style import observe as observe_prose
from ..style import explain_all as explain_prose_profiles
from ..style import explain_profile as explain_prose_profile
from .projection import Projection, project_document

#: Which document node maps to which style block kind. Anything absent from this
#: mapping contributes no prose block — code fences and tables are not prose, and
#: the document layer has already kept them out of the projection.
BLOCK_KINDS: dict[type, str] = {
    Paragraph: "paragraph",
    Heading: "heading",
    ListItem: "list_item",
}

#: Node types the walk descends into. Anything else is a leaf as far as
#: document shape is concerned.
BLOCK_TYPES = (Paragraph, Heading, ListBlock, ListItem, Quote, CodeBlock, Table)


def analyze_style(
    document: Document, projection: Optional[Projection] = None
) -> StyleAnalysis:
    """Measure how a structured document is written."""
    view = projection if projection is not None else project_document(document)
    return analyze_prose(view.text, structure_of(document, view))


def observe_style(
    document: Document, projection: Optional[Projection] = None
) -> StyleObservations:
    """Measure a document once, for as many profiles as a caller wants.

    The expensive half. Callers comparing profiles should call this and then
    `interpret_style` per profile, rather than `analyze_style_with_profile` per
    profile, which would re-measure each time.
    """
    view = projection if projection is not None else project_document(document)
    return observe_prose(view.text, structure_of(document, view))


def interpret_style(observed: StyleObservations, profile) -> ProfiledAnalysis:
    """Read an existing measurement against one profile. Cheap."""
    return interpret_prose(observed, profile)


def analyze_style_with_profile(
    document: Document, profile, projection: Optional[Projection] = None
) -> ProfiledAnalysis:
    """Measure a document and read it against one named profile.

    There is no default. An unknown or absent profile is an error rather than a
    quiet fall back to `natural`, because a configuration typo that analysed a
    specification against conversational expectations would produce a report that
    looked entirely normal and was answering the wrong question.
    """
    return interpret_style(observe_style(document, projection), profile)


def compare_style_profiles(
    document: Document, profiles=None, projection: Optional[Projection] = None
) -> dict:
    """One measurement, read against several profiles."""
    return compare_prose_profiles(observe_style(document, projection), profiles)


def structure_of(document: Document, view: Projection) -> DocumentStructure:
    """Describe a document's shape in the terms the style layer understands."""
    # The projected text of each block, read from the projection rather than
    # from the source: markup is already gone, and a line break inside a block
    # becomes a space so a sentence wrapped across two lines stays one sentence.
    by_block: dict[tuple[int, ...], list[str]] = {}
    for segment in view.segments:
        if segment.synthetic or segment.source_span is None:
            continue
        piece = " " if segment.kind == "break" else view.text[
            segment.analysis_span.start : segment.analysis_span.end
        ]
        by_block.setdefault(segment.block_path, []).append(piece)

    blocks: list[ProseBlock] = []
    counts = {"list_blocks": 0, "code_blocks": 0, "tables": 0}

    for node, quoted, listed in _walk(document):
        if isinstance(node, ListBlock):
            counts["list_blocks"] += 1
            continue
        if isinstance(node, CodeBlock):
            counts["code_blocks"] += 1
            continue
        if isinstance(node, Table):
            counts["tables"] += 1
            continue

        kind = BLOCK_KINDS.get(type(node))
        if kind is None:
            continue
        # The representation nests a paragraph inside every list item, so the
        # node that owns the text is a Paragraph either way. What kind of prose
        # it is depends on where it sits, which is what the walk reports.
        if listed:
            kind = "list_item"
        # Quoted prose is still measurable — style makes no edits, so nothing is
        # at stake — but it is labelled as a quote so a reader can tell that the
        # repetition they are looking at belongs to somebody the author quoted.
        if quoted:
            kind = "quote"

        pieces = by_block.get(node.path)
        if not pieces:
            continue
        text = "".join(pieces).strip()
        if not text:
            continue

        blocks.append(
            ProseBlock(
                kind=kind,
                text=text,
                index=len(blocks),
                path=node.path,
                level=getattr(node, "level", 0),
            )
        )

    return DocumentStructure(
        blocks=tuple(blocks),
        list_blocks=counts["list_blocks"],
        code_blocks=counts["code_blocks"],
        tables=counts["tables"],
    )


def _walk(document: Document):
    """Every block, with whether it sits inside a quote and inside a list item.

    Reported alongside the node rather than recorded on it: the document
    representation is immutable and belongs to another layer, and reaching in to
    tag it would make this function's convenience somebody else's surprise.
    """

    def visit(node, quoted: bool, listed: bool):
        in_quote = quoted or isinstance(node, Quote)
        in_list = listed or isinstance(node, ListItem)
        yield node, in_quote, in_list
        for child in node.children():
            if isinstance(child, BLOCK_TYPES):
                yield from visit(child, in_quote, in_list)

    for block in document.blocks:
        yield from visit(block, False, False)


# ── Adapter-facing view ────────────────────────────────────────────────────
#
# `adapters` may reach `pipeline` and not `style`, so a CLI or a desktop pane
# asks here. Read-only, deliberately: Phase 8 establishes the reference frame a
# style fix would need and grants no authority to make one.


def list_profiles() -> list:
    """Every bundled profile, in canonical display order, as plain data."""
    return explain_prose_profiles()


def explain_profile(identifier: str) -> dict:
    """One profile, in enough detail to choose it or argue with it."""
    return explain_prose_profile(identifier)
