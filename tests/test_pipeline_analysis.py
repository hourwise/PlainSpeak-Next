"""Tests for the structured analysis pipeline.

The point of this phase is that the structured path changes *what reaches the
analyser*. These tests are written to fail if it stops doing that — if code
content leaks in as prose, if a URL gets analysed, if markup characters survive
into the analysis text, or if a sentence arrives in pieces.

The other half is edit authority, which is not the same thing as analysis. The
clearest way to see the distinction is the same word in four settings:

    Use **approximately** 5 mg.                     editable
    Use `approximately` as the variable name.       never seen at all
    See [approximately](https://approximately.example).  editable (the link text)
    > Use approximately 5 mg.                       analysed, not editable

Four occurrences, three different answers. A system that gave them all the same
answer would be wrong in at least two of them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plainspeak.core.metrics import analyze
from plainspeak.document import parse_markdown, parse_text
from plainspeak.document.model import REASON_QUOTE, Span, content_hash
from plainspeak.pipeline import analyze_document, propose_change
from plainspeak.pipeline.analysis import REFUSAL_AMBIGUOUS
from plainspeak.pipeline.projection import REFUSAL_DISCONTIGUOUS, project_document

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = sorted((REPO_ROOT / "tests" / "characterisation" / "corpus").glob("*.txt"))

ADVERSARIAL = """Use **approximately** 5 mg.

Use `approximately` as the variable name.

See [approximately](https://approximately.example).

> Use approximately 5 mg.
"""


def md(source: str):
    return parse_markdown.parse(source)


def findings_for(source: str, word: str):
    result = analyze_document(md(source))
    return [f for f in result.findings if word in f.barrier.matched_text]


# ── The structured path changes what the analyser sees ─────────────────────


def test_code_content_never_becomes_prose_input() -> None:
    result = analyze_document(md("Set `utilise(0.5)` first.\n\n```\ncommence work\n```\n"))
    assert "utilise" not in result.projection.text
    assert "commence" not in result.projection.text
    assert not any("utilise" in f.barrier.matched_text for f in result.findings)


def test_link_destinations_are_not_analysed_as_prose() -> None:
    result = analyze_document(md("See [the guidance](https://utilise.example/commence) now.\n"))
    assert "utilise.example" not in result.projection.text
    assert "commence" not in result.projection.text
    assert "the guidance" in result.projection.text


def test_inline_formatting_markers_are_absent_from_analysis_text() -> None:
    result = analyze_document(md("A **bold** and *italic* and ~~struck~~ sentence.\n"))
    for marker in ("**", "*", "~~", "_"):
        assert marker not in result.projection.text
    assert result.projection.text == "A bold and italic and struck sentence."


def test_human_readable_link_text_remains_prose() -> None:
    result = analyze_document(md("See [the utilise guidance](https://example.org/g) now.\n"))
    assert "the utilise guidance" in result.projection.text
    assert any("utilise" in f.barrier.matched_text for f in result.findings)


def test_sentence_context_survives_inline_emphasis() -> None:
    """The words either side of emphasis belong to the same sentence."""
    result = analyze_document(md("The system provides a **robust** solution to the problem.\n"))
    assert result.simplification.sentences == [
        "The system provides a robust solution to the problem."
    ]


def test_the_structured_path_differs_from_the_flat_one() -> None:
    """Proof the phase did something: flat and structured disagree, correctly."""
    source = "Set `utilise` first. See [docs](https://commence.example) now.\n"

    flat = analyze(source)
    structured = analyze_document(md(source))

    assert flat.total_words > structured.scores.total_words, (
        "the flat analyser should be counting markup and URLs as words"
    )
    assert "commence.example" not in structured.projection.text


# ── The four adversarial occurrences ───────────────────────────────────────


def test_the_four_occurrences_do_not_all_carry_the_same_authority() -> None:
    result = analyze_document(md(ADVERSARIAL))
    text = result.projection.text

    # The code-span occurrence never reaches the analyser at all.
    assert text.count("approximately") == 3, (
        f"expected three analysable occurrences, projection was {text!r}"
    )

    matches = [f for f in result.findings if f.barrier.matched_text == "approximately"]
    assert matches, "the word should be flagged where it is analysable"

    authorities = {f.editable for f in matches}
    assert authorities == {True, False}, (
        "all occurrences were given the same edit authority, which cannot be right"
    )


def test_the_bold_occurrence_is_editable_and_maps_to_the_bare_word() -> None:
    source = "Use **approximately** 5 mg.\n"
    result = analyze_document(md(source))
    finding = next(f for f in result.findings if f.barrier.matched_text == "approximately")

    assert finding.editable
    span = finding.source_span
    assert source[span.start : span.end] == "approximately", (
        "the mapping must land on the word, not on the emphasis markers"
    )


def test_the_code_occurrence_is_never_seen() -> None:
    result = analyze_document(md("Use `approximately` as the variable name.\n"))
    assert "approximately" not in result.projection.text
    assert not [f for f in result.findings if f.barrier.matched_text == "approximately"]


def test_the_link_text_occurrence_is_editable() -> None:
    source = "See [approximately](https://approximately.example) for details.\n"
    result = analyze_document(md(source))
    finding = next(f for f in result.findings if f.barrier.matched_text == "approximately")

    assert finding.editable
    span = finding.source_span
    assert span.start == source.index("[") + 1, "the mapping must land on the link text"
    assert source[span.start : span.end] == "approximately"


def test_the_quoted_occurrence_is_analysed_but_not_editable() -> None:
    result = analyze_document(md("> Use approximately 5 mg.\n"))
    finding = next(f for f in result.findings if f.barrier.matched_text == "approximately")

    assert "approximately" in result.projection.text, "quoted prose must still be analysed"
    assert not finding.editable
    assert finding.reason == REASON_QUOTE
    assert finding.mapping.source_spans, "a diagnostic should still say where the text is"


# ── Mapping exactness for findings ─────────────────────────────────────────


@pytest.mark.parametrize(
    "source,word",
    [
        ("The department will utilise the facility.\n", "utilise"),
        ("The department will **utilise** the facility.\n", "utilise"),
        ("The department will *utilise* the facility.\n", "utilise"),
        ("# The department will utilise it\n", "utilise"),
        ("- The department will utilise it\n", "utilise"),
        ("See [the utilise page](https://example.org/x) now.\n", "utilise"),
        ("First line here.\nThe department will utilise it.\n", "utilise"),
    ],
    ids=["plain", "bold", "emphasis", "heading", "list", "link-text", "second-line"],
)
def test_a_finding_maps_back_to_exactly_the_original_characters(source: str, word: str) -> None:
    result = analyze_document(md(source))
    finding = next(f for f in result.findings if f.barrier.matched_text == word)

    assert finding.editable, f"expected an editable finding, got: {finding.reason}"
    span = finding.source_span
    assert source[span.start : span.end] == word


def test_applying_a_mapped_finding_edits_only_that_word() -> None:
    source = "The department will **utilise** the facility.\n"
    document = md(source)
    result = analyze_document(document)
    finding = next(f for f in result.findings if f.barrier.matched_text == "utilise")

    edited = document.serialise([(finding.source_span, "use")])
    assert edited == "The department will **use** the facility.\n"


def test_a_finding_spanning_markup_is_refused() -> None:
    """A phrase detector that crosses an emphasis marker has no safe edit."""
    result = analyze_document(md("The system provides a **robust** solution.\n"))
    crossing = [
        f for f in result.findings if f.reason == REFUSAL_DISCONTIGUOUS
    ]
    assert crossing, "expected at least one finding to cross the emphasis markers"
    for finding in crossing:
        assert not finding.editable
        assert finding.mapping.source_spans, "still reportable"


def test_an_ambiguous_match_is_refused_rather_than_guessed() -> None:
    """Two candidates and no way to choose is a refusal, not a coin toss."""
    result = analyze_document(md("The utilise and utilise approach was chosen.\n"))
    finding = next(f for f in result.findings if f.barrier.matched_text == "utilise")

    assert not finding.editable
    assert finding.reason == REFUSAL_AMBIGUOUS


# ── Line endings ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_line_endings_do_not_change_the_analysis(path: Path) -> None:
    """The same canonical document must analyse identically either way."""
    lf = path.read_bytes().decode("utf-8")
    crlf = lf.replace("\n", "\r\n")

    a = analyze_document(md(lf))
    b = analyze_document(md(crlf))

    assert a.projection.text == b.projection.text
    assert a.scores == b.scores
    assert [f.editable for f in a.findings] == [f.editable for f in b.findings]

    def mapped(source: str, result) -> list:
        return [
            source[f.source_span.start : f.source_span.end] if f.source_span else None
            for f in result.findings
        ]

    assert mapped(lf, a) == mapped(crlf, b), (
        "findings must land on the same original characters whatever the line ending"
    )


# ── Legacy compatibility ───────────────────────────────────────────────────


def test_the_flat_text_api_is_untouched() -> None:
    """The inherited entry point still means exactly what it meant."""
    source = "The department will utilise the facility. It was reviewed by staff."
    before = analyze(source)
    analyze_document(md(source))
    after = analyze(source)

    assert before == after
    assert before.total_words == len(source.split())


def test_an_all_code_document_returns_an_empty_analysis_without_raising() -> None:
    """The flat analyser raises on empty input; this layer declines to ask it."""
    result = analyze_document(md("```\nonly code here\n```\n"))

    assert result.projection.text == ""
    assert result.findings == ()
    assert result.scores.total_words == 0
    with pytest.raises(ValueError):
        analyze("")  # the inherited behaviour it is protecting against


@pytest.mark.parametrize("source", ["", "   \n\n", "\n\n\n"], ids=["empty", "spaces", "newlines"])
def test_degenerate_documents_do_not_raise(source: str) -> None:
    assert analyze_document(md(source)).findings == ()
    assert analyze_document(parse_text.parse(source)).findings == ()


# ── The proposed-change contract ───────────────────────────────────────────


def test_a_proposal_records_everything_needed_to_review_it() -> None:
    source = "The department will **utilise** the facility.\n"
    document = md(source)
    result = analyze_document(document)
    finding = next(f for f in result.findings if f.barrier.matched_text == "utilise")

    change = result.propose(finding, "use", rule_id="PS.TEST.001")

    assert change.rule_id == "PS.TEST.001"
    assert change.applicable
    assert change.replacement == "use"
    assert change.original_text == "utilise"
    assert change.original_hash == content_hash("utilise")
    assert change.source_span is not None
    assert change.document_path == (0,)
    assert change.location == "0"
    assert change.reason == ""


def test_a_refused_proposal_carries_its_reason_and_no_authority() -> None:
    document = md("> Use approximately 5 mg.\n")
    result = analyze_document(document)
    finding = next(f for f in result.findings if f.barrier.matched_text == "approximately")

    change = result.propose(finding, "about")
    assert not change.applicable
    assert change.reason == REASON_QUOTE


def test_a_proposal_detects_that_the_document_moved_underneath_it() -> None:
    """A proposal is made against a snapshot, and says so."""
    source = "The department will utilise the facility.\n"
    document = md(source)
    projection = project_document(document)
    start = projection.text.index("utilise")

    change = propose_change(projection, document, Span(start, start + 7), "use")
    assert change.applicable
    assert change.still_matches(document)

    moved = md("Some entirely different prose lives here now.\n")
    assert not change.still_matches(moved), (
        "a proposal must not claim to still apply to a document that changed"
    )


def test_a_proposal_over_synthetic_material_is_refused() -> None:
    document = md("First paragraph.\n\nSecond paragraph.\n")
    projection = project_document(document)
    start = projection.text.index("First")
    end = projection.text.index("Second") + len("Second")

    change = propose_change(projection, document, Span(start, end), "replacement")
    assert not change.applicable
    assert change.source_span is None


# ── Determinism ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_analysis_is_deterministic(path: Path) -> None:
    source = path.read_bytes().decode("utf-8")
    first = analyze_document(md(source))
    second = analyze_document(md(source))

    assert first.projection.text == second.projection.text
    assert first.scores == second.scores
    assert [f.editable for f in first.findings] == [f.editable for f in second.findings]
    assert [f.analysis_span for f in first.findings] == [f.analysis_span for f in second.findings]


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_no_editable_finding_ever_points_outside_the_source(path: Path) -> None:
    """The invariant that makes an automatic edit safe at all."""
    source = path.read_bytes().decode("utf-8")
    document = md(source)
    result = analyze_document(document)

    for finding in result.editable_findings:
        span = finding.source_span
        assert span is not None
        assert 0 <= span.start <= span.end <= len(source)
        # And the characters really are what the finding claims to be about.
        if finding.barrier.matched_text and finding.barrier.end_char > finding.barrier.start_char:
            assert source[span.start : span.end] == finding.barrier.matched_text
