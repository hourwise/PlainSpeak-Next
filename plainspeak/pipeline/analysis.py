"""Running the inherited analyser over a structured document.

The inherited engine takes a string and returns findings located by sentence
index and by offset within that sentence. Those coordinates are useless on
their own once the input is a projection: to show a reader where a finding is,
or to propose an edit for it, every finding has to be traced back to exact
characters of the original source.

That tracing is what this module does, and it fails closed at every step. A
finding whose sentence cannot be located, whose matched text appears more than
once, or whose range crosses markup, is kept as a diagnostic and marked
unusable for automatic editing. It is never given a plausible-looking position.

The inherited flat-text API is untouched. `core.metrics.analyze(text)` still
means exactly what it meant, and the characterisation seal still holds it to
that. This is a second path alongside it, not a redefinition of it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.barriers import Barrier, SimplificationResult, analyze_simplification
from ..core.metrics import ReadabilityScores, analyze
from ..document.model import Document, Span
from .plan import ProposedChange, propose_change
from .projection import Projection, SourceMapping, project_document

#: Why a barrier could not be placed in the analysis text.
REFUSAL_SENTENCE_LOST = "the sentence this finding refers to could not be located in the analysis text"
REFUSAL_AMBIGUOUS = "the matched text occurs more than once in its sentence, so its position is ambiguous"
REFUSAL_NOT_FOUND = "the matched text does not appear in its sentence"


@dataclass(frozen=True)
class Finding:
    """One barrier, placed in the source as exactly as it can honestly be.

    `editable` is the question a caller should ask before offering to change
    anything. A finding with `editable=False` is still a real finding worth
    reporting; it simply has no safe automatic edit, either because the engine
    may not rewrite that text or because no exact source range corresponds to
    it.
    """

    barrier: Barrier
    #: Where it sits in the projection, when that could be established.
    analysis_span: Optional[Span]
    #: Where it sits in the source, and whether an edit there would be safe.
    mapping: Optional[SourceMapping]
    #: Readable document path of the enclosing block.
    location: str
    editable: bool
    reason: str

    @property
    def source_span(self) -> Optional[Span]:
        return self.mapping.source_span if self.mapping else None


@dataclass(frozen=True)
class DocumentAnalysis:
    """Everything the pipeline produces for one structured document."""

    document: Document
    projection: Projection
    scores: ReadabilityScores
    simplification: SimplificationResult
    findings: tuple[Finding, ...]

    @property
    def editable_findings(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.editable)

    @property
    def diagnostic_findings(self) -> tuple[Finding, ...]:
        """Findings worth reporting that carry no automatic edit authority."""
        return tuple(finding for finding in self.findings if not finding.editable)

    def propose(self, finding: Finding, replacement: str, rule_id: str = "") -> ProposedChange:
        """Build a proposal for a finding, subject to the same mapping rules."""
        if finding.analysis_span is None:
            return ProposedChange(
                rule_id=rule_id,
                rule_version=0,
                mode="",
                analysis_span=Span(0, 0),
                source_spans=(),
                document_path=(),
                location=finding.location,
                original_text="",
                original_hash="",
                replacement=replacement,
                applicable=False,
                reason=finding.reason,
            )
        return propose_change(
            self.projection, self.document, finding.analysis_span, replacement, rule_id
        )


def analyze_document(document: Document) -> DocumentAnalysis:
    """Analyse a structured document.

    The single orchestration entry point. The CLI, and later the desktop
    application and the MCP server, all call this, so that the same document
    cannot produce different findings depending on which interface asked.

    An empty projection — a document of nothing but code fences, say — is
    returned as an empty analysis rather than being passed to the inherited
    analyser, which raises on empty input. That is not a behaviour change to
    `analyze`; it is this layer declining to ask it a question it does not
    answer.
    """
    projection = project_document(document)

    if not projection.text.strip():
        return DocumentAnalysis(
            document=document,
            projection=projection,
            scores=ReadabilityScores(),
            simplification=SimplificationResult(original_text=projection.text),
            findings=(),
        )

    scores = analyze(projection.text)
    simplification = analyze_simplification(projection.text)
    findings = tuple(
        _place(projection, simplification, barrier) for barrier in simplification.barriers
    )

    return DocumentAnalysis(
        document=document,
        projection=projection,
        scores=scores,
        simplification=simplification,
        findings=findings,
    )


# ── Placing a barrier in the source ────────────────────────────────────────


def _sentence_offsets(projection: Projection, sentences: list[str]) -> list[Optional[int]]:
    """Where each sentence starts in the analysis text, by forward scan.

    The inherited splitter returns sentences that are exact substrings of its
    input, in order, so a single forward pass places all of them. The scan
    never moves backwards: a sentence found before an earlier one would mean
    the scan had desynchronised, and every offset after it would be wrong.
    """
    offsets: list[Optional[int]] = []
    cursor = 0
    for sentence in sentences:
        if not sentence:
            offsets.append(None)
            continue
        found = projection.text.find(sentence, cursor)
        if found < 0:
            offsets.append(None)
            continue
        offsets.append(found)
        cursor = found + len(sentence)
    return offsets


def _place(
    projection: Projection, simplification: SimplificationResult, barrier: Barrier
) -> Finding:
    offsets = _sentence_offsets_cached(projection, simplification)
    index = barrier.sentence_index

    if not (0 <= index < len(offsets)) or offsets[index] is None:
        return Finding(barrier, None, None, "root", False, REFUSAL_SENTENCE_LOST)

    base = offsets[index]
    sentence = simplification.sentences[index]
    span, reason = _range_within_sentence(sentence, barrier)
    if span is None:
        return Finding(barrier, None, None, "root", False, reason)

    analysis_span = Span(base + span.start, base + span.end)
    mapping = projection.map_to_source(analysis_span)
    segment = projection.segment_at(analysis_span.start)
    location = ".".join(str(part) for part in segment.block_path) if segment else "root"

    return Finding(
        barrier=barrier,
        analysis_span=analysis_span,
        mapping=mapping,
        location=location or "root",
        editable=mapping.applicable,
        reason=mapping.reason,
    )


def _range_within_sentence(sentence: str, barrier: Barrier) -> tuple[Optional[Span], str]:
    """Locate a barrier inside its own sentence.

    The inherited detectors are inconsistent about this: some set `start_char`
    and `end_char`, and some leave both at zero and record only `matched_text`.
    Both are handled, and a disagreement between the two is treated as a reason
    to refuse rather than a reason to pick one.
    """
    matched = barrier.matched_text

    if barrier.end_char > barrier.start_char:
        span = Span(barrier.start_char, min(barrier.end_char, len(sentence)))
        if matched and sentence[span.start : span.end] != matched:
            # The offsets and the matched text disagree. Trusting either would
            # be a guess.
            return None, REFUSAL_NOT_FOUND
        return span, ""

    if not matched:
        # No offsets and nothing matched: the finding is about the sentence as
        # a whole, which is how long-sentence detection reports.
        return Span(0, len(sentence)), ""

    first = sentence.find(matched)
    if first < 0:
        return None, REFUSAL_NOT_FOUND
    if sentence.find(matched, first + 1) >= 0:
        # Two candidates and no way to choose. Reporting it is fine; editing
        # one of them at random is not.
        return None, REFUSAL_AMBIGUOUS
    return Span(first, first + len(matched)), ""


def _sentence_offsets_cached(
    projection: Projection, simplification: SimplificationResult
) -> list[Optional[int]]:
    """Compute the sentence offsets once per analysis, not once per barrier."""
    cache = getattr(simplification, "_projection_offsets", None)
    if cache is not None and cache[0] is projection:
        return cache[1]
    offsets = _sentence_offsets(projection, simplification.sentences)
    try:
        object.__setattr__(simplification, "_projection_offsets", (projection, offsets))
    except Exception:  # noqa: BLE001 - caching is an optimisation, never a requirement
        pass
    return offsets
