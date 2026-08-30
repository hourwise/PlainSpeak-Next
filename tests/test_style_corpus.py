"""Calibration: the thresholds must separate natural prose from repetitive prose.

This is where the numbers in `plainspeak/style/policy.py` came from. Every
threshold was set by measuring these documents and drawing a line the natural
samples sit clear of and the repetitive ones cross.

The natural half matters more. Anyone can build a detector that fires; the work
is in not firing on ordinary writing, and six of the fourteen documents here
exist solely to hold the thresholds honest about that. A false positive on the
government sample is what forced the paragraph-uniformity minimum from five
paragraphs to eight.

Nothing is trained. The corpus is regression data.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plainspeak.document import parse_markdown
from plainspeak.pipeline.styling import analyze_style
from plainspeak.style import analysis_digest, analysis_to_json, policy

CORPUS = Path(__file__).resolve().parent / "style" / "corpus"
SNAPSHOT = Path(__file__).resolve().parent / "style" / "corpus-findings.json"

#: Documents that must produce no findings. Ordinary prose in several registers.
NATURAL = ("academic", "conversational", "government", "long_natural", "short", "technical")

#: Documents written to exhibit one pattern each, with the diagnostic each must
#: produce. Pinning the expected diagnostic — not merely "something fired" —
#: means a document cannot start passing for the wrong reason.
REPETITIVE = {
    "framing_heavy": policy.CANNED_FRAMING,
    "list_heavy": policy.LIST_DOMINANCE,
    "overlapping": policy.LEXICAL_OVERLAP,
    "repeated_openers": policy.REPEATED_SENTENCE_OPENER,
    "transition_heavy": policy.REPEATED_TRANSITION,
    "uniform_cadence": policy.SENTENCE_UNIFORMITY,
    "uniform_paragraphs": policy.PARAGRAPH_UNIFORMITY,
    "vocabulary_heavy": policy.VOCABULARY_OVERUSE,
}


def analyse(name: str):
    source = (CORPUS / f"{name}.md").read_bytes().decode("utf-8")
    return analyze_style(parse_markdown.parse(source))


@pytest.mark.parametrize("name", NATURAL)
def test_natural_prose_produces_no_findings(name: str) -> None:
    """The half of the corpus that keeps the thresholds honest."""
    findings = analyse(name).findings
    assert findings == (), (
        f"{name}.md is ordinary prose and produced "
        f"{[f'{item.id}:{item.severity}' for item in findings]}"
    )


@pytest.mark.parametrize("name,expected", sorted(REPETITIVE.items()))
def test_repetitive_prose_produces_its_diagnostic(name: str, expected: str) -> None:
    ids = {finding.id for finding in analyse(name).findings}
    assert expected in ids, f"{name}.md should have produced {expected}, got {sorted(ids)}"


def test_the_corpus_covers_both_directions() -> None:
    """A corpus of only positives would prove nothing about false positives."""
    present = {path.stem for path in CORPUS.glob("*.md")} - {"README"}
    assert present == set(NATURAL) | set(REPETITIVE)
    assert len(NATURAL) >= 5
    assert len(REPETITIVE) >= 6


def test_every_threshold_has_a_document_that_exercises_it() -> None:
    """A threshold no document crosses is a number nobody has checked.

    Measured against what the corpus actually produces, not against the
    `REPETITIVE` mapping — three diagnostics (paragraph openers, transition
    density, repeated phrases) are never a document's headline pattern but do
    fire alongside one, and that counts as exercised.
    """
    exercised = {
        finding.id
        for name in REPETITIVE
        for finding in analyse(name).findings
    }
    untested = set(policy.DIAGNOSTIC_IDS) - exercised
    # Exercised by `test_style_diagnostics.py` instead. Each needs prose shaped
    # so particularly that a whole document of it would not resemble anything
    # anyone writes, which would make it useless as calibration evidence.
    allowed = {policy.RHETORICAL_REPETITION, policy.TRIADIC_REPETITION}
    assert untested <= allowed, f"no calibration document exercises: {sorted(untested)}"


# ── Determinism ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(set(NATURAL) | set(REPETITIVE)))
def test_analysis_is_deterministic(name: str) -> None:
    assert analysis_to_json(analyse(name)) == analysis_to_json(analyse(name))


def test_the_corpus_is_lf_normalised() -> None:
    """CRLF here would calibrate the thresholds against Windows-only bytes.

    Paragraph boundaries key off blank lines, so a corpus document carrying
    CRLF would be split differently depending on which platform last touched
    it — and the thresholds were drawn against these exact splits.
    """
    for path in sorted(CORPUS.iterdir()):
        assert b"\r\n" not in path.read_bytes(), f"{path.name} contains CRLF line endings"
    assert b"\r\n" not in SNAPSHOT.read_bytes()


@pytest.mark.parametrize("name", sorted(set(NATURAL) | set(REPETITIVE)))
def test_line_endings_do_not_change_the_analysis(name: str) -> None:
    source = (CORPUS / f"{name}.md").read_bytes().decode("utf-8")
    lf = analyze_style(parse_markdown.parse(source))
    crlf = analyze_style(parse_markdown.parse(source.replace("\n", "\r\n")))

    assert [item.id for item in lf.findings] == [item.id for item in crlf.findings]
    assert [item.severity for item in lf.findings] == [item.severity for item in crlf.findings]


def snapshot_of() -> str:
    produced = {
        name: [
            {"id": item.id, "severity": item.severity, "value": round(item.value, 4)}
            for item in analyse(name).findings
        ]
        for name in sorted(set(NATURAL) | set(REPETITIVE))
    }
    return json.dumps(produced, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_the_corpus_matches_its_reviewed_snapshot() -> None:
    """Findings across the whole corpus, pinned as readable JSON.

    The same role as the generated-forms snapshot in Phase 6: a hash says
    something changed, and this says what. A reviewer sees which document
    started or stopped producing which finding, in plain terms.
    """
    assert SNAPSHOT.exists(), "no corpus snapshot; write one and read it"
    assert snapshot_of() == SNAPSHOT.read_bytes().decode("utf-8"), (
        "the calibration corpus produces different findings.\n"
        "  Read the diff: it names the document and the diagnostic that moved."
    )


# ── Report ─────────────────────────────────────────────────────────────────


def test_the_report_is_canonical_json() -> None:
    rendered = analysis_to_json(analyse("repeated_openers"))

    assert rendered.endswith("\n")
    assert json.dumps(json.loads(rendered), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")) + "\n" == rendered


def test_the_report_carries_no_timestamp() -> None:
    import re

    rendered = analysis_to_json(analyse("repeated_openers"))
    assert not re.search(r"\d{4}-\d{2}-\d{2}", rendered)
    for key in ("timestamp", "generated", "date", "time"):
        assert key not in rendered.lower()


def test_the_report_names_the_policy_and_the_document() -> None:
    record = json.loads(analysis_to_json(analyse("repeated_openers")))

    assert record["style_policy_sha256"] == policy.policy_hash()
    assert record["style_policy_version"] == policy.STYLE_POLICY_VERSION
    assert len(record["document_sha256"]) == 64


def test_every_finding_carries_checkable_evidence() -> None:
    """A reader must be able to go and look."""
    for name in REPETITIVE:
        for found in analyse(name).findings:
            assert found.message, f"{name}: {found.id} has no message"
            assert found.evidence, f"{name}: {found.id} has no evidence"
            assert found.sample_size >= policy.MINIMUM_SAMPLES[found.id]
            assert found.evidence[0].label


def test_the_digest_identifies_the_observation() -> None:
    first, second = analyse("uniform_cadence"), analyse("uniform_cadence")
    assert analysis_digest(first) == analysis_digest(second)
    assert analysis_digest(first) != analysis_digest(analyse("technical"))
