"""The document intermediate representation.

A document is not a string. Treating it as one is why the inherited engine
cannot tell a heading from a quotation, or a code fence from a paragraph, and
why it will happily rewrite the inside of a URL.

The representation here is built on one commitment: **every node knows exactly
which characters of the original source it came from**. That single property
gives us the rest for free —

- serialising an unedited document returns the original bytes, because the
  original bytes are what it holds;
- an edit is a span replacement, so a transformation plan is just a list of
  span replacements that can be validated and ordered before anything is
  applied;
- a node whose source location cannot be established exactly is marked
  untransformable rather than guessed at.

That last point is the whole safety argument. A parser that is unsure where a
piece of prose lives in the source must say so, because an edit applied at the
wrong offset is a corrupted document, and a corrupted document is worse than an
unimproved one.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterator, Optional, Sequence


def content_hash(text: str) -> str:
    """The provenance hash for a piece of original source."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class Span:
    """A half-open character range `[start, end)` into the document source."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span: [{self.start}, {self.end})")

    def __len__(self) -> int:
        return self.end - self.start

    def text(self, source: str) -> str:
        return source[self.start : self.end]

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "Span") -> bool:
        return self.start <= other.start and other.end <= self.end


# Two different authorities, deliberately kept apart.
#
#   analyzable    — this text is prose, and the analyser may read and report on
#                   it.
#   transformable — the engine may additionally *rewrite* it.
#
# They are not the same question, and collapsing them loses real cases. A block
# quote is ordinary prose: it can be measured, and a report should say if it is
# hard to read. It still must not be reworded, because rewording somebody
# else's words while leaving them inside quotation marks misattributes them.
#
# A code fence is the other shape: not prose at all, so neither authority
# applies. Recording *which* authority is missing, and why, is what lets a
# report answer "why was nothing done here?" with something better than
# silence.
#
# Invariant: anything not analyzable is not transformable either. There is no
# meaningful "rewrite text we are not willing to read".

#: Not prose. Neither analysable nor transformable.
REASON_CODE = "code is not prose"
REASON_TABLE = "table structure is significant"
REASON_RAW = "raw markup is not prose"
REASON_LINK_TARGET = "a link destination is an address, not prose"
REASON_UNLOCATABLE = "the parser could not establish this node's source offsets"

#: Prose, but not ours to change.
REASON_QUOTE = "quoted material must not be reworded"

#: Applied to descendants of a node that carries one of the reasons above.
REASON_INHERITED = "an enclosing node is not transformable"


@dataclass
class Node:
    """Common state every node carries, whether block or inline."""

    span: Span
    #: Index path from the document root, e.g. `(3, 1, 0)`. Identifies a node's
    #: place in the tree independently of its source offsets, so a change
    #: record can name a location that survives re-parsing.
    path: tuple[int, ...] = ()
    #: Which parser produced this node, e.g. `"markdown-it-py/commonmark"`.
    provenance: str = ""
    #: SHA-256 of the original source slice, captured at parse time. If a node's
    #: current source no longer hashes to this, something has rewritten the
    #: document underneath us.
    original_hash: str = ""
    #: Whether this node's text is prose the analyser may read.
    analyzable: bool = True
    #: Whether the engine may rewrite it. Never true when `analyzable` is false.
    transformable: bool = True
    #: Empty when `transformable`; otherwise one of the REASON_* constants.
    untransformable_reason: str = ""
    #: Empty when `analyzable`; otherwise one of the REASON_* constants.
    unanalyzable_reason: str = ""

    @property
    def location(self) -> str:
        """The node's path as a readable string, for reports and audit records."""
        return ".".join(str(index) for index in self.path) or "root"

    def mark_untransformable(self, reason: str) -> None:
        """Withhold edit authority while leaving the text analysable."""
        self.transformable = False
        self.untransformable_reason = reason

    def mark_unanalyzable(self, reason: str) -> None:
        """Withhold both authorities: this node's text is not prose.

        Edit authority goes with it necessarily. Rewriting text the analyser is
        not willing to read would mean editing on no evidence at all.
        """
        self.analyzable = False
        self.unanalyzable_reason = reason
        self.mark_untransformable(reason)

    def children(self) -> Sequence["Node"]:
        return ()

    def walk(self) -> Iterator["Node"]:
        """Yield this node and every descendant, in document order."""
        yield self
        for child in self.children():
            yield from child.walk()

    def verify(self, source: str) -> bool:
        """Check the source still matches what was hashed at parse time."""
        return content_hash(self.span.text(source)) == self.original_hash


# ── Inline nodes ───────────────────────────────────────────────────────────


@dataclass
class Inline(Node):
    """Marker base for nodes that live inside a block."""


@dataclass
class Text(Inline):
    """A run of prose. This is the only thing the engine may rewrite."""

    text: str = ""


@dataclass
class CodeSpan(Inline):
    """An inline code span. Never prose, however much it looks like a word."""

    code: str = ""

    def __post_init__(self) -> None:
        self.mark_unanalyzable(REASON_CODE)


@dataclass
class Literal(Inline):
    r"""A prose character the source spells with markup: an escape or an entity.

    `\*` is one asterisk. `&amp;` is one ampersand. Both are ordinary prose to
    a reader, and both occupy more source characters than they contribute to
    the text, so `text` and `span` here deliberately have different lengths.
    Everything downstream must therefore treat this node as non-linear: a range
    covering part of it has no exact source equivalent, though a range covering
    all of it maps cleanly onto the whole markup.

    Dropping these instead — the obvious shortcut — would delete characters
    from the middle of a sentence and hand the analyser prose the author never
    wrote.
    """

    text: str = ""


@dataclass
class RawInline(Inline):
    """Inline HTML or any other markup passed through untouched."""

    def __post_init__(self) -> None:
        self.mark_unanalyzable(REASON_RAW)


@dataclass
class LineBreak(Inline):
    """A soft or hard break inside a block."""

    hard: bool = False


@dataclass
class Emphasis(Inline):
    """Emphasised or strongly emphasised text.

    The emphasis markers themselves are not prose, but the text between them
    is, so this node holds children rather than a string.
    """

    kind: str = "em"  # "em" | "strong" | "s"
    content: list[Inline] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class Link(Inline):
    """A link. Its text is prose; its destination emphatically is not."""

    href: str = ""
    title: str = ""
    content: list[Inline] = field(default_factory=list)
    #: The span covering the destination, so a validator can prove no edit
    #: ever lands inside it.
    href_span: Optional[Span] = None

    def children(self) -> Sequence[Node]:
        return self.content


# ── Block nodes ────────────────────────────────────────────────────────────


@dataclass
class Block(Node):
    """Marker base for top-level and nested structural nodes."""


@dataclass
class Paragraph(Block):
    content: list[Inline] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class Heading(Block):
    level: int = 1
    content: list[Inline] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class Quote(Block):
    """Quoted material.

    Marked untransformable but *not* unanalysable: rewording somebody else's
    words and leaving them inside quotation marks misattributes them, but a
    quotation is still prose and a report should be able to say that it is hard
    to read. This is the case that makes the two authorities worth separating.
    """

    content: list[Block] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.mark_untransformable(REASON_QUOTE)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class ListItem(Block):
    content: list[Block] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.content


@dataclass
class ListBlock(Block):
    ordered: bool = False
    items: list[ListItem] = field(default_factory=list)

    def children(self) -> Sequence[Node]:
        return self.items


@dataclass
class CodeBlock(Block):
    language: str = ""
    code: str = ""

    def __post_init__(self) -> None:
        self.mark_unanalyzable(REASON_CODE)


@dataclass
class Table(Block):
    """A table, held as opaque source.

    Cell contents are prose, but the alignment row and the pipe structure are
    not, and getting that wrong silently destroys the table. Until the cell
    spans are parsed properly, the whole block is off limits.
    """

    def __post_init__(self) -> None:
        self.mark_unanalyzable(REASON_TABLE)


@dataclass
class ThematicBreak(Block):
    def __post_init__(self) -> None:
        self.mark_unanalyzable(REASON_RAW)


@dataclass
class HtmlBlock(Block):
    def __post_init__(self) -> None:
        self.mark_unanalyzable(REASON_RAW)


# ── The structural contract ────────────────────────────────────────────────


def _segment_kind(node: Node) -> str:
    if isinstance(node, Text):
        return "text"
    if isinstance(node, Literal):
        return "literal"
    return "break"


@dataclass(frozen=True)
class ProseSegment:
    """One run of document text, with both authorities already resolved.

    This is the contract between the document representation and everything
    downstream. It is produced by exactly one traversal
    (`Document.prose_segments`) so that no two callers can form different
    opinions about what may be read or written.

    A segment is a run of prose (`kind="text"`), a character the source spells
    as markup (`kind="literal"` — an escape or an entity), or a line break
    inside a block (`kind="break"`). The latter two are included because they
    occupy source characters between runs of prose: a consumer that skipped
    them would either lose the gap or silently join two lines together.

    Only `text` segments are guaranteed to have `len(text) == len(span)`.
    """

    span: Span
    kind: str
    text: str
    path: tuple[int, ...]
    #: Path of the enclosing block. A consumer that has to know where one unit
    #: of prose ends and the next begins cannot recover this from `path` alone,
    #: because an inline node may be nested to any depth inside its block.
    block_path: tuple[int, ...]
    provenance: str
    original_hash: str
    #: The analyser may read this text.
    analyzable: bool
    #: The engine may rewrite it. Never true when `analyzable` is false.
    transformable: bool
    #: Why an authority is missing. Empty when the segment carries both.
    #: When the segment is not analysable this explains that; otherwise, if it
    #: is merely not transformable, it explains *that*. One field, because two
    #: could disagree.
    reason: str = ""

    def __post_init__(self) -> None:
        if self.transformable and not self.analyzable:
            raise ValueError(
                "a segment cannot be transformable without being analyzable: "
                "rewriting text the analyser will not read is editing on no evidence"
            )


# ── The document ───────────────────────────────────────────────────────────


@dataclass
class Document:
    """A parsed document, and the source it was parsed from.

    The source is kept in full and is the authority. Nodes index into it; they
    do not replace it. Serialising a document that has not been edited is
    therefore not a reconstruction — it is the original string.
    """

    source: str
    source_format: str
    blocks: list[Block] = field(default_factory=list)
    provenance: str = ""
    source_hash: str = ""

    def __post_init__(self) -> None:
        if not self.source_hash:
            self.source_hash = content_hash(self.source)

    def walk(self) -> Iterator[Node]:
        for block in self.blocks:
            yield from block.walk()

    def prose_segments(self) -> list["ProseSegment"]:
        """The single structural traversal, in document order.

        Everything that needs to know what may be read or written derives from
        this one walk. Two traversals that answered "is this prose?" and "may we
        edit this?" separately would agree today and drift apart on the first
        node type somebody adds to only one of them, and the failure would be
        silent — the engine would simply start editing something it should not.

        Authority is resolved by inheritance down the tree, because that is
        where the interesting cases live. The paragraph inside a block quote is
        transformable in itself; it is its enclosing quote that says no.
        """
        segments: list[ProseSegment] = []

        def visit(
            node: Node,
            analysis_refusal: str,
            edit_refusal: str,
            block_path: tuple[int, ...],
        ) -> None:
            if not node.analyzable:
                analysis_refusal = analysis_refusal or node.unanalyzable_reason
            if not node.transformable:
                edit_refusal = edit_refusal or node.untransformable_reason
            if isinstance(node, Block):
                block_path = node.path

            if isinstance(node, (Text, Literal, LineBreak)) and len(node.span):
                segments.append(
                    ProseSegment(
                        span=node.span,
                        kind=_segment_kind(node),
                        text=getattr(node, "text", ""),
                        path=node.path,
                        block_path=block_path,
                        provenance=node.provenance,
                        original_hash=node.original_hash,
                        analyzable=not analysis_refusal,
                        transformable=not (analysis_refusal or edit_refusal),
                        reason=analysis_refusal or edit_refusal,
                    )
                )

            for child in node.children():
                visit(child, analysis_refusal, edit_refusal, block_path)

        for block in self.blocks:
            visit(block, "", "", block.path)
        return segments

    def prose_spans(self) -> list[Span]:
        """Every span the engine is allowed to rewrite, in document order.

        Derived from `prose_segments` rather than walking the tree again, so
        the edit authority reported here can never disagree with the one the
        analysis pipeline sees.
        """
        return [
            segment.span
            for segment in self.prose_segments()
            if segment.transformable and segment.kind in ("text", "literal")
        ]

    def analyzable_segments(self) -> list["ProseSegment"]:
        """The segments whose text the analyser may read.

        A superset of the transformable ones: it includes block quotes, which
        are prose but not ours to reword.
        """
        return [segment for segment in self.prose_segments() if segment.analyzable]

    def text_of(self, span: Span) -> str:
        return span.text(self.source)

    def serialise(self, replacements: Sequence[tuple[Span, str]] = ()) -> str:
        """Render the document, optionally replacing some spans.

        With no replacements this returns `self.source` unchanged — the
        round-trip guarantee is structural rather than something the serialiser
        has to be careful about.

        Replacements are applied right to left so that earlier offsets stay
        valid, and are rejected if they overlap, because two edits to the same
        characters have no defined meaning and silently letting one win is how
        a deterministic engine stops being deterministic.
        """
        if not replacements:
            return self.source

        ordered = sorted(replacements, key=lambda pair: (pair[0].start, pair[0].end))
        for (left, _), (right, _) in zip(ordered, ordered[1:]):
            if left.overlaps(right):
                raise ValueError(
                    f"overlapping replacements: [{left.start}, {left.end}) "
                    f"and [{right.start}, {right.end})"
                )

        result = self.source
        for span, text in reversed(ordered):
            if span.end > len(result):
                raise ValueError(f"span [{span.start}, {span.end}) is outside the source")
            result = result[: span.start] + text + result[span.end :]
        return result
