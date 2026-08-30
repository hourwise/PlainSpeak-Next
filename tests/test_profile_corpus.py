"""The profile calibration corpus, checked against expectations written first.

`expectations.yaml` states what each document must and must not produce before
the engine is asked. That ordering is the point: a snapshot proves behaviour has
not changed, and a suite built only from snapshots will freeze a defect as
happily as it freezes a fix. Stating the answer in advance is how a test can
disagree with the code.

The corpus also closes the calibration gaps Phase 7 recorded, and closing them
found two thresholds that were wrong. Both corrections are in the profiles rather
than in the base policy, because the Phase 7 identity is accepted and its
baseline output is pinned — see STYLE_PROFILES.md for the full account.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from plainspeak.document import parse_markdown
from plainspeak.pipeline.styling import analyze_style, compare_style_profiles, observe_style
from plainspeak.style import policy, profile_ids
from plainspeak.style.profiles import load_profile

ROOT = Path(__file__).resolve().parent / "style" / "profiles"
EXPECTATIONS = ROOT / "expectations.yaml"
SNAPSHOT = ROOT / "profile-findings.json"

REGISTERS = ("academic", "controls", "government", "natural", "plain", "technical")


def expectations() -> list[dict]:
    return yaml.safe_load(EXPECTATIONS.read_text(encoding="utf-8"))["documents"]


def document(relative: str):
    return parse_markdown.parse((ROOT / relative).read_text(encoding="utf-8"))


CASES = expectations()
IDS = [case["document"] for case in CASES]


# ── The corpus itself ──────────────────────────────────────────────────────


def test_every_document_is_declared() -> None:
    """A document nobody wrote an expectation for is a document nobody checked."""
    on_disk = {
        str(path.relative_to(ROOT)).replace("\\", "/") for path in ROOT.rglob("*.md")
    }
    declared = {case["document"] for case in CASES}
    assert on_disk == declared, (
        f"undeclared: {sorted(on_disk - declared)}; missing: {sorted(declared - on_disk)}"
    )


def test_every_profile_has_calibration_evidence() -> None:
    for identifier in profile_ids():
        owned = [case for case in CASES if case["profile"] == identifier]
        assert len(owned) >= 2, f"{identifier} has {len(owned)} calibration documents"


def test_every_profile_has_long_documents() -> None:
    """Phase 7's longest calibration source was 352 words, too short to trust."""
    for identifier in profile_ids():
        long_enough = [
            case for case in CASES
            if case["profile"] == identifier and case["words"] >= 1000
        ]
        assert len(long_enough) >= 2, (
            f"{identifier} has {len(long_enough)} documents of 1,000+ words"
        )


def test_declared_word_counts_are_accurate() -> None:
    """The declarations are evidence, so they have to be true."""
    for case in CASES:
        actual = len((ROOT / case["document"]).read_text(encoding="utf-8").split())
        assert abs(actual - case["words"]) <= 5, (
            f"{case['document']} declares {case['words']} words and has {actual}"
        )


def test_every_document_states_why_it_exists() -> None:
    for case in CASES:
        assert case.get("reason", "").strip(), f"{case['document']} has no reason"


def test_the_corpus_is_lf_normalised() -> None:
    for path in sorted(ROOT.rglob("*")):
        if path.is_file():
            assert b"\r\n" not in path.read_bytes(), f"{path.name} contains CRLF"


# ── Expectations ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_a_document_is_quiet_under_its_own_profile(case: dict) -> None:
    """Zero false positives in-register is the headline claim."""
    results = compare_style_profiles(document(case["document"]))
    found = results[case["profile"]].findings
    unexpected = [f.id for f in found if f.id not in set(case.get("must_find") or [])]
    assert not unexpected, (
        f"{case['document']} under {case['profile']} produced {unexpected}\n"
        f"  {case['reason'].strip()}"
    )


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_declared_non_findings_hold(case: dict) -> None:
    results = compare_style_profiles(document(case["document"]))
    ids = {f.id for f in results[case["profile"]].findings}
    for forbidden in case.get("must_not_find") or []:
        assert forbidden in policy.DIAGNOSTIC_IDS, f"{forbidden} is not a diagnostic"
        assert forbidden not in ids, f"{case['document']}: unexpected {forbidden}"


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_declared_findings_hold(case: dict) -> None:
    results = compare_style_profiles(document(case["document"]))
    ids = {f.id for f in results[case["profile"]].findings}
    for required in case.get("must_find") or []:
        assert required in ids, f"{case['document']}: expected {required}"


CONTRASTS = [
    (case, contrast)
    for case in CASES
    for contrast in (case.get("contrasts") or [])
]


@pytest.mark.parametrize(
    "case,contrast", CONTRASTS,
    ids=[f"{case['document']}->{c['profile']}" for case, c in CONTRASTS],
)
def test_cross_profile_contrasts_hold(case: dict, contrast: dict) -> None:
    """The same document, read against a profile it was not written for.

    This is where profiles justify themselves. If a contrast stops holding,
    either a threshold moved or two profiles have converged, and both are worth a
    reviewer's attention.
    """
    results = compare_style_profiles(document(case["document"]))
    other = results[contrast["profile"]]

    ids = {f.id for f in other.findings}
    for required in contrast.get("must_find") or []:
        assert required in ids, (
            f"{case['document']} under {contrast['profile']}: expected {required}\n"
            f"  {contrast['reason'].strip()}"
        )

    states = {t.metric: t.state for t in other.targets}
    for metric, expected in (contrast.get("target_outside") or {}).items():
        assert states.get(metric) == expected, (
            f"{case['document']} under {contrast['profile']}: {metric} is "
            f"{states.get(metric)}, expected {expected}"
        )

    assert contrast.get("reason", "").strip()


def test_every_contrast_actually_contrasts() -> None:
    """A declared contrast that matches the home profile proves nothing."""
    for case, contrast in CONTRASTS:
        results = compare_style_profiles(document(case["document"]))
        home = results[case["profile"]]
        other = results[contrast["profile"]]
        assert (
            {f.id for f in home.findings} != {f.id for f in other.findings}
            or {(t.metric, t.state) for t in home.targets}
            != {(t.metric, t.state) for t in other.targets}
        ), f"{case['document']}: {contrast['profile']} agrees with {case['profile']}"


# ── The gaps Phase 7 recorded ──────────────────────────────────────────────


def quiet_side(diagnostic: str) -> list[tuple[str, float, int]]:
    """Documents that measure this diagnostic without crossing any profile line."""
    found = []
    for path in sorted(ROOT.rglob("*.md")):
        observed = observe_style(parse_markdown.parse(path.read_text(encoding="utf-8")))
        item = observed.by_id().get(diagnostic)
        if item is not None and item.sample_size >= policy.MINIMUM_SAMPLES[diagnostic]:
            found.append((path.stem, item.value, item.sample_size))
    return found


@pytest.mark.parametrize(
    "diagnostic",
    [
        policy.REPEATED_TRANSITION,
        policy.LIST_DOMINANCE,
        policy.PARAGRAPH_UNIFORMITY,
        policy.RHETORICAL_REPETITION,
        policy.TRIADIC_REPETITION,
    ],
)
def test_the_phase_seven_gaps_are_closed(diagnostic: str) -> None:
    """Five diagnostics had no natural document testing them from the quiet side.

    Phase 7's calibration document said so explicitly. Each now has calibration
    material that reaches its minimum sample, which is what makes the threshold
    testable rather than merely plausible.
    """
    measured = quiet_side(diagnostic)
    assert measured, f"still no document reaches the minimum sample for {diagnostic}"


def test_list_dominance_now_has_documents_with_real_lists() -> None:
    """Phase 7 separated 0.789 from 0.0 because nothing natural had a list."""
    measured = [(name, value) for name, value, _ in quiet_side(policy.LIST_DOMINANCE) if value > 0]
    assert len(measured) >= 5, f"only {len(measured)} documents contain lists: {measured}"
    assert max(value for _, value in measured) >= 0.35, (
        "no document exercises list dominance near a threshold"
    )


def test_paragraph_uniformity_has_many_controls_now() -> None:
    """Phase 7 had exactly one natural document clearing the eight-paragraph floor."""
    measured = quiet_side(policy.PARAGRAPH_UNIFORMITY)
    assert len(measured) >= 10, f"only {len(measured)} documents clear the minimum"


def test_the_baseline_still_disagrees_where_the_corpus_says_it_should() -> None:
    """The two corrections this phase found, pinned as findings of this phase.

    These are baseline false positives on documents written to be ordinary. They
    are not fixed in the base policy, because the Phase 7 identity is accepted and
    its output is pinned byte-for-byte; they are fixed in every profile, and
    recorded here so the disagreement cannot quietly disappear.
    """
    rhetoric = analyze_style(document("controls/ordinary-rhetoric.md"))
    baseline_ids = {f.id for f in rhetoric.findings}
    assert policy.RHETORICAL_REPETITION in baseline_ids, (
        "the baseline no longer fires on ordinary rhetorical usage; if the base "
        "policy was corrected, update STYLE_PROFILES.md and the profile reasons"
    )
    assert policy.TRIADIC_REPETITION in baseline_ids

    for identifier in profile_ids():
        profiled = compare_style_profiles(
            document("controls/ordinary-rhetoric.md")
        )[identifier]
        ids = {f.id for f in profiled.findings}
        assert policy.RHETORICAL_REPETITION not in ids, identifier
        assert policy.TRIADIC_REPETITION not in ids, identifier


def test_repeated_transition_was_a_baseline_false_positive() -> None:
    for name in ("natural/allotment-year.md", "natural/packing-for-the-hills.md",
                 "natural/learning-to-cook-late.md"):
        baseline = {f.id for f in analyze_style(document(name)).findings}
        assert policy.REPEATED_TRANSITION in baseline, name

        under_natural = compare_style_profiles(document(name))["natural"]
        assert policy.REPEATED_TRANSITION not in {f.id for f in under_natural.findings}, name


# ── Snapshot ───────────────────────────────────────────────────────────────


def snapshot_of() -> str:
    produced = {}
    for case in CASES:
        results = compare_style_profiles(document(case["document"]))
        produced[case["document"]] = {
            identifier: {
                "findings": [
                    {"id": f.id, "severity": f.severity, "value": round(f.value, 4)}
                    for f in analysis.findings
                ],
                "outside_target": {
                    t.metric: t.state for t in analysis.outside_target()
                },
            }
            for identifier, analysis in results.items()
        }
    return json.dumps(produced, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_the_corpus_matches_its_reviewed_snapshot() -> None:
    """Every document under every profile, pinned as readable JSON.

    The expectations above say what must be true. This says what is currently
    true, in full, so that a threshold change names the documents and profiles it
    moved instead of merely reporting that something did.
    """
    assert SNAPSHOT.exists(), "no profile snapshot; write one and read it"
    assert snapshot_of() == SNAPSHOT.read_bytes().decode("utf-8"), (
        "the profile corpus produces different results.\n"
        "  Read the diff: it names the document, the profile and what moved."
    )
