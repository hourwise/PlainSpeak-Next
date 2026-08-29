"""The contract a proposed change has to satisfy.

Phase 4 will add a rule engine that produces proposed edits. This module is
deliberately not that engine: it defines only the shape a proposal must take
and the single function that fills it in, so that when rules arrive they have
somewhere correct to put their output and no reason to reach around the
projection to compute source offsets themselves.

A proposal records everything needed to decide whether it may be applied, to
show a reviewer what would change, and to detect later that the document moved
underneath it:

    analysis range      where the finding was made
    source range(s)     which original characters it covers
    document location   which node, by path
    original text/hash  what was there when the proposal was made
    applicability       whether it may be applied automatically
    reason              why not, when it may not

Nothing here decides *what* to change. That is a rule's job, and rules do not
exist yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..document.model import Document, Span, content_hash
from .projection import Projection, SourceMapping


@dataclass(frozen=True)
class ProposedChange:
    """One candidate edit, with its authority already resolved.

    Immutable on purpose. A proposal that could be edited after it was
    validated would let the thing that was checked and the thing that was
    applied drift apart, which is the whole failure this design exists to
    prevent.
    """

    #: Which rule proposed it. Empty until the rule engine exists.
    rule_id: str
    #: Where the finding was made, in projection coordinates.
    analysis_span: Span
    #: The source characters it covers. Empty when nothing could be located.
    source_spans: tuple[Span, ...]
    #: Path of the enclosing block, and a readable form of it.
    document_path: tuple[int, ...]
    location: str
    #: What is there now, and its hash at the time of proposing.
    original_text: str
    original_hash: str
    #: What the rule suggests instead. Empty for a deletion; empty also for a
    #: diagnostic that proposes no text at all.
    replacement: str
    #: Whether this may be applied automatically. False does not mean the
    #: finding is wrong — only that no exact, safe edit is defined for it.
    applicable: bool
    #: Why not, when `applicable` is false.
    reason: str

    @property
    def source_span(self) -> Optional[Span]:
        """The contiguous source range, when the proposal has one."""
        if not self.applicable or not self.source_spans:
            return None
        return Span(self.source_spans[0].start, self.source_spans[-1].end)

    def still_matches(self, document: Document) -> bool:
        """Whether the document still holds what this proposal was made against.

        A proposal is made against a snapshot. Applying one to a document that
        has changed since would edit the wrong characters, so anything that
        applies proposals must check this first.
        """
        span = self.source_span
        if span is None:
            return False
        return content_hash(span.text(document.source)) == self.original_hash


def propose_change(
    projection: Projection,
    document: Document,
    analysis_span: Span,
    replacement: str = "",
    rule_id: str = "",
) -> ProposedChange:
    """Turn a finding in analysis coordinates into a proposal against the source.

    The mapping decides applicability; this function never second-guesses it.
    An inapplicable proposal is still returned, complete with whatever source
    positions could be established, because a diagnostic a reader can be shown
    is worth more than a finding that quietly disappeared.
    """
    mapping: SourceMapping = projection.map_to_source(analysis_span)
    span = mapping.source_span
    original = span.text(document.source) if span is not None else ""

    return ProposedChange(
        rule_id=rule_id,
        analysis_span=analysis_span,
        source_spans=mapping.source_spans,
        document_path=_block_path(mapping),
        location=_location(mapping),
        original_text=original,
        original_hash=content_hash(original) if span is not None else "",
        replacement=replacement,
        applicable=mapping.applicable,
        reason=mapping.reason,
    )


def _block_path(mapping: SourceMapping) -> tuple[int, ...]:
    return mapping.segments[0].block_path if mapping.segments else ()


def _location(mapping: SourceMapping) -> str:
    path = _block_path(mapping)
    return ".".join(str(index) for index in path) or "root"
