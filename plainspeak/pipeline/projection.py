"""Projecting a structured document into prose the analyser can read.

The analyser takes a string. The document is a tree with markup in it. A
projection is the string the analyser should see, plus enough bookkeeping to
turn any offset in that string back into an exact offset in the original
source.

    source:    The system provides a **robust** solution.
    analysis:  The system provides a robust solution.
    mapping:   analysis[22:28] -> source[24:30]

Two things this is not, and both matter.

**It is not a concatenation of `Text` nodes.** Analysing each node separately
would cut every sentence at each emphasis marker, and sentence segmentation,
long-sentence detection and readability statistics would all be measuring
fragments. The projection deliberately reads across inline boundaries so that
`The system provides a **robust** solution.` is one sentence, as it plainly is.

**It is not lossy.** Every character of the projection belongs to exactly one
segment, and every segment either names the source characters it came from or
declares itself synthetic. There is no third category, and no offset that
"probably" corresponds to something. When a range cannot be mapped exactly, the
mapping is refused rather than approximated — an edit at a wrong offset
silently corrupts a document, and no improvement is worth that.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ..document.model import Block, Document, ProseSegment, Span

#: Inserted between blocks in a whole-document projection so that two
#: paragraphs do not run into one sentence. It corresponds to no source
#: characters, and segments carrying it are marked synthetic precisely so that
#: nothing can ever propose editing it.
BLOCK_SEPARATOR = "\n\n"

#: What a line break inside a block contributes to the analysis text. Always a
#: single newline, whatever the source used, so that the same document with
#: CRLF and with LF produces identical analysis text and therefore identical
#: findings. The source span still records both characters when the source had
#: two, which is what `linear` below is for.
LINE_BREAK = "\n"

#: Why a mapping was refused. Phrased for a person reading a report.
REFUSAL_EMPTY = "the range is empty"
REFUSAL_OUT_OF_RANGE = "the range lies outside the projected text"
REFUSAL_SYNTHETIC = "the range crosses material inserted between blocks, which is not in the source"
REFUSAL_DISCONTIGUOUS = "the range crosses markup, so no single source replacement is defined"
REFUSAL_PARTIAL_BREAK = "the range covers part of a line break, which cannot be partially replaced"
REFUSAL_UNCOVERED = "part of the range is not backed by any segment"


@dataclass(frozen=True)
class ProjectedSegment:
    """One run of analysis text and the source it came from.

    `source_span` is `None` exactly when `synthetic` is true. Nothing else may
    be missing: a segment that neither names its source nor admits to being
    synthetic would be a hole in the mapping, and holes are what let wrong
    offsets through.
    """

    #: Range within the projection's text.
    analysis_span: Span
    #: Range within the document source, or `None` for synthetic material.
    source_span: Optional[Span]
    #: "text", "literal" (an escape or entity), "break", or "separator".
    kind: str
    synthetic: bool
    #: Path of the IR node this came from, and of its enclosing block.
    path: tuple[int, ...]
    block_path: tuple[int, ...]
    #: Structural scopes that apply here, for rules that target or avoid them.
    scopes: tuple[str, ...]
    provenance: str
    original_hash: str
    analyzable: bool
    transformable: bool
    reason: str
    #: Whether analysis offsets within this segment correspond one-for-one to
    #: source offsets. False for a CRLF line break (one character of analysis
    #: text over two of source) and for an escape or entity (`&amp;` is five
    #: source characters spelling one). A range that only partly covers such a
    #: segment has no exact source equivalent and is refused.
    linear: bool

    def source_subspan(self, start: int, end: int) -> Optional[Span]:
        """Map an absolute analysis range, clipped to this segment, to source.

        Returns `None` when this segment cannot answer exactly — because it is
        synthetic, or because the range covers only part of a non-linear
        segment.
        """
        if self.source_span is None:
            return None
        low = max(start, self.analysis_span.start)
        high = min(end, self.analysis_span.end)
        if low >= high:
            return None
        if not self.linear:
            covers_whole = low == self.analysis_span.start and high == self.analysis_span.end
            if not covers_whole:
                return None
            return self.source_span
        offset = self.source_span.start - self.analysis_span.start
        return Span(low + offset, high + offset)


@dataclass(frozen=True)
class SourceMapping:
    """The result of mapping an analysis range back to the source.

    `applicable` is the only thing a caller should consult before proposing an
    automatic edit. A mapping may carry perfectly good `source_spans` and still
    be inapplicable — the spans say where the text *is*, which is enough to
    report a diagnostic and point at it, and not enough to replace it.
    """

    analysis_span: Span
    source_spans: tuple[Span, ...]
    segments: tuple[ProjectedSegment, ...]
    applicable: bool
    reason: str

    @property
    def source_span(self) -> Optional[Span]:
        """The single contiguous source range, when there is one."""
        if not self.applicable or not self.source_spans:
            return None
        return Span(self.source_spans[0].start, self.source_spans[-1].end)


@dataclass(frozen=True)
class Projection:
    """Analysis text plus the mapping back to the document that produced it."""

    text: str
    segments: tuple[ProjectedSegment, ...]
    #: "document" or "block" — see `project_document` and `project_block`.
    unit: str
    #: Which block this projects, for a block projection; empty for a document.
    path: tuple[int, ...]
    document_hash: str
    provenance: str

    def map_to_source(self, analysis_span: Span) -> SourceMapping:
        """Map a range of the analysis text back to the document source.

        Refuses — rather than approximating — when the range crosses synthetic
        material, crosses markup so that no single replacement is defined,
        partly covers a line break, or touches anything the engine may not
        rewrite.
        """
        return _map(self, analysis_span)

    def segment_at(self, offset: int) -> Optional[ProjectedSegment]:
        for segment in self.segments:
            if segment.analysis_span.start <= offset < segment.analysis_span.end:
                return segment
        return None


def project_document(document: Document) -> Projection:
    """Project a whole document.

    This is the unit the analyser sees. Readability statistics, sentence
    segmentation and long-sentence detection are all document-level questions,
    and answering them per block would change what the inherited engine means
    by every one of them.

    Blocks are joined by a synthetic separator so that the last sentence of one
    paragraph and the first of the next are not read as one. The separator is
    marked synthetic and is therefore permanently ineligible to be edited.
    """
    return _build(document, document.analyzable_segments(), unit="document", path=())


def project_block(document: Document, block: Block) -> Projection:
    """Project one block, for callers that want a bounded unit of prose.

    Useful for reviewing or re-analysing a single paragraph without paying for
    the whole document. It is *not* the unit document-level statistics should be
    computed over; see `project_document`.
    """
    prefix = block.path
    selected = [
        segment
        for segment in document.analyzable_segments()
        if segment.block_path[: len(prefix)] == prefix
    ]
    return _build(document, selected, unit="block", path=prefix)


def _build(
    document: Document,
    segments: Sequence[ProseSegment],
    unit: str,
    path: tuple[int, ...],
) -> Projection:
    pieces: list[str] = []
    projected: list[ProjectedSegment] = []
    cursor = 0
    previous_block: Optional[tuple[int, ...]] = None

    for segment in segments:
        if previous_block is not None and segment.block_path != previous_block:
            span = Span(cursor, cursor + len(BLOCK_SEPARATOR))
            pieces.append(BLOCK_SEPARATOR)
            projected.append(
                ProjectedSegment(
                    analysis_span=span,
                    source_span=None,
                    kind="separator",
                    synthetic=True,
                    path=segment.block_path,
                    block_path=segment.block_path,
                    scopes=(),
                    provenance="pipeline.projection",
                    original_hash="",
                    analyzable=True,
                    transformable=False,
                    reason=REFUSAL_SYNTHETIC,
                    linear=False,
                )
            )
            cursor = span.end
        previous_block = segment.block_path

        # A literal contributes the character it stands for, not the markup
        # that spells it; only a break contributes a canonical newline.
        text = LINE_BREAK if segment.kind == "break" else segment.text
        if not text:
            continue
        span = Span(cursor, cursor + len(text))
        pieces.append(text)
        projected.append(
            ProjectedSegment(
                analysis_span=span,
                source_span=segment.span,
                kind=segment.kind,
                synthetic=False,
                path=segment.path,
                block_path=segment.block_path,
                scopes=segment.scopes,
                provenance=segment.provenance,
                original_hash=segment.original_hash,
                analyzable=segment.analyzable,
                transformable=segment.transformable,
                reason=segment.reason,
                linear=len(text) == len(segment.span),
            )
        )
        cursor = span.end

    return Projection(
        text="".join(pieces),
        segments=tuple(projected),
        unit=unit,
        path=path,
        document_hash=document.source_hash,
        provenance=document.provenance,
    )


def _map(projection: Projection, analysis_span: Span) -> SourceMapping:
    def refuse(reason: str, spans: tuple[Span, ...] = (), touched=()) -> SourceMapping:
        return SourceMapping(
            analysis_span=analysis_span,
            source_spans=spans,
            segments=tuple(touched),
            applicable=False,
            reason=reason,
        )

    if len(analysis_span) == 0:
        return refuse(REFUSAL_EMPTY)
    if analysis_span.end > len(projection.text):
        return refuse(REFUSAL_OUT_OF_RANGE)

    touched = [
        segment
        for segment in projection.segments
        if segment.analysis_span.overlaps(analysis_span)
    ]
    if not touched:
        return refuse(REFUSAL_UNCOVERED)

    # The touched segments must tile the range with no gap. A gap would mean
    # the projection text contains characters no segment claims, which is a
    # bug in the builder rather than a property of the input — but checking is
    # cheap and the failure mode is silent corruption.
    covered = touched[0].analysis_span.start
    for segment in touched:
        if segment.analysis_span.start > covered:
            return refuse(REFUSAL_UNCOVERED, touched=touched)
        covered = max(covered, segment.analysis_span.end)
    if covered < analysis_span.end or touched[0].analysis_span.start > analysis_span.start:
        return refuse(REFUSAL_UNCOVERED, touched=touched)

    # Real source positions, gathered first so that a refused mapping can still
    # point a reader at the text it is talking about.
    spans: list[Span] = []
    exact = True
    for segment in touched:
        piece = segment.source_subspan(analysis_span.start, analysis_span.end)
        if piece is None:
            exact = False
            continue
        spans.append(piece)
    located = tuple(spans)

    if any(segment.synthetic for segment in touched):
        return refuse(REFUSAL_SYNTHETIC, located, touched)

    for segment in touched:
        if not segment.transformable:
            return refuse(segment.reason, located, touched)

    if not exact:
        return refuse(REFUSAL_PARTIAL_BREAK, located, touched)

    for earlier, later in zip(located, located[1:]):
        if earlier.end != later.start:
            # The gap is markup — an emphasis marker, a bracket, a fence. There
            # is no single stretch of source that corresponds to this range, so
            # there is no replacement that could be applied to it.
            return refuse(REFUSAL_DISCONTIGUOUS, located, touched)

    return SourceMapping(
        analysis_span=analysis_span,
        source_spans=located,
        segments=tuple(touched),
        applicable=True,
        reason="",
    )
