"""Same input, same bytes, on every platform — and bounded work getting there.

Two things are pinned here that the policy hash does not cover. The policy hash
says the thresholds have not moved; it says nothing about whether the *metrics*
still compute the same numbers, or whether a finding still renders the same
bytes. A refactor of `metrics.py` could leave the policy untouched and change
every answer, and only a pinned output would notice.

The bounded-work tests count operations rather than seconds. A test that
measures elapsed time goes flaky on a loaded CI machine and then gets deleted;
a test that counts pair updates fails for exactly one reason.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plainspeak.document import parse_markdown
from plainspeak.pipeline.styling import analyze_style, structure_of
from plainspeak.pipeline.projection import project_document
from plainspeak.style import analysis_digest, analysis_to_json, canonical_json, policy
from plainspeak.style import patterns

CORPUS = Path(__file__).resolve().parent / "style" / "corpus"

#: A document with several findings across several categories, so the pin has
#: something to be sensitive to. Asserted on Windows, Linux and macOS, so each
#: platform compares against the same number rather than against itself.
REPRESENTATIVE = "transition_heavy"
METRIC_DIGEST = "41b82bc3c56c1e39bb584bd94d0dd55719b66833994f6aaa2a833a5eb12a7ed5"
ANALYSIS_DIGEST = "903209e323beff7326aa496a025fcc1d33e17bf49542d7f7b867e0a7dc37cd4a"

#: A document that produces nothing, pinned for the same reason: silence is an
#: answer, and a refactor that made a quiet document speak would be the single
#: worst regression this layer could have.
QUIET = "long_natural"
QUIET_METRIC_DIGEST = "ef029b9ca1018a0039ae0d5cf0e3b1e43ec371410f42992be63c93df1ea099bf"
QUIET_ANALYSIS_DIGEST = "4d0a1510e029d798cf094142c0224fcd76c9e264652550d29974f719051722ca"


def analyse(name: str):
    return analyze_style(parse_markdown.parse((CORPUS / f"{name}.md").read_text(encoding="utf-8")))


def metric_digest(analysis) -> str:
    # Rounded before hashing. Floating-point arithmetic can differ in the last
    # place between platforms, and pinning a bit that has no bearing on any
    # decision would produce a test that fails for reasons nobody can act on.
    rendered = canonical_json({key: round(value, 6) for key, value in analysis.metrics.values.items()})
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


# ── Pinned identities ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name,expected",
    [(REPRESENTATIVE, METRIC_DIGEST), (QUIET, QUIET_METRIC_DIGEST)],
)
def test_the_metrics_have_their_expected_identity(name: str, expected: str) -> None:
    assert metric_digest(analyse(name)) == expected, (
        f"the metrics computed for {name}.md changed.\n"
        f"  The policy hash cannot catch this: thresholds can sit still while the\n"
        f"  numbers they are compared against move. If the change was deliberate,\n"
        f"  update the pin and say which metric moved and why."
    )


@pytest.mark.parametrize(
    "name,expected",
    [(REPRESENTATIVE, ANALYSIS_DIGEST), (QUIET, QUIET_ANALYSIS_DIGEST)],
)
def test_the_analysis_has_its_expected_identity(name: str, expected: str) -> None:
    assert analysis_digest(analyse(name)) == expected


def test_the_quiet_document_is_still_quiet() -> None:
    """Stated separately from its digest, so the failure names itself."""
    assert analyse(QUIET).findings == ()


# ── Stable ordering ────────────────────────────────────────────────────────


def test_findings_are_ordered_by_severity_then_id() -> None:
    order = {"strong": 0, "notice": 1, "info": 2}
    findings = analyse(REPRESENTATIVE).findings
    assert len(findings) > 1, "this document should produce several findings"

    keys = [(order[item.severity], item.id) for item in findings]
    assert keys == sorted(keys)


def test_ordering_does_not_depend_on_the_run() -> None:
    for name in (REPRESENTATIVE, "vocabulary_heavy", "framing_heavy", "overlapping"):
        first, second = analyse(name), analyse(name)
        assert [item.id for item in first.findings] == [item.id for item in second.findings]
        for left, right in zip(first.findings, second.findings):
            assert [item.label for item in left.evidence] == [
                item.label for item in right.evidence
            ]
            for one, two in zip(left.evidence, right.evidence):
                assert [place.location for place in one.occurrences] == [
                    place.location for place in two.occurrences
                ]


def test_the_json_is_byte_identical_across_runs() -> None:
    for name in sorted(path.stem for path in CORPUS.glob("*.md")):
        if name == "README":
            continue
        assert analysis_to_json(analyse(name)) == analysis_to_json(analyse(name))


# ── Bounded work ───────────────────────────────────────────────────────────


def paragraphs_of(source: str):
    document = parse_markdown.parse(source)
    structure = structure_of(document, project_document(document))
    return [
        frozenset(patterns.content_words(block.text))
        for block in structure.paragraphs
        if len(patterns.content_words(block.text)) >= policy.OVERLAP_MINIMUM_TOKENS
    ]


def test_pair_counting_never_exceeds_its_budget() -> None:
    """The bound that the first implementation only appeared to have.

    `OVERLAP_MAX_COMPARISONS` caps the Jaccard scoring, which is the cheap half.
    The candidate set was built first by counting every co-occurring pair, and
    that was genuinely quadratic: measured pair counts grew as 3n² in
    paragraphs, so 160 paragraphs cost 76,240 pairs and 5,000 would have cost
    75 million. The cap could not see any of it.
    """
    base = (CORPUS / "long_natural.md").read_text(encoding="utf-8")

    for factor in (1, 8, 32, 128):
        _, updates = patterns.shared_token_counts(paragraphs_of("\n\n".join([base] * factor)))
        assert updates <= policy.OVERLAP_MAX_PAIR_UPDATES, (
            f"{factor}x the corpus document used {updates} pair updates, over the "
            f"budget of {policy.OVERLAP_MAX_PAIR_UPDATES}"
        )


def test_work_stops_growing_once_the_budget_binds() -> None:
    """What a budget actually buys, stated honestly.

    It does not make the growth sub-quadratic. Below the budget, doubling the
    paragraphs still roughly quadruples the pair count — measured at 4.2x and
    4.1x going from 40 to 80 to 160 paragraphs, which is the quadratic the old
    implementation had all the way up. What the budget buys is a ceiling: from
    320 paragraphs onwards the work stops rising and sits at the bound, so the
    whole analysis stays linear in document length because this part of it has
    stopped scaling at all.

    Asserting the plateau is the honest test. Asserting sub-quadratic growth
    would have been a nicer-sounding claim and a false one.
    """
    base = (CORPUS / "long_natural.md").read_text(encoding="utf-8")
    measured = {}
    for factor in (64, 128, 256, 512):
        paragraphs = paragraphs_of("\n\n".join([base] * factor))
        _, updates = patterns.shared_token_counts(paragraphs)
        measured[len(paragraphs)] = updates

    sizes = sorted(measured)
    assert min(sizes) >= 320, "these sizes must be past the point where the budget binds"

    for smaller, larger in zip(sizes, sizes[1:]):
        assert measured[larger] <= measured[smaller] * 1.05, (
            f"work grew from {measured[smaller]} to {measured[larger]} when "
            f"paragraphs went from {smaller} to {larger}; past the budget it "
            f"should have plateaued"
        )


def test_a_smaller_budget_still_produces_a_deterministic_answer() -> None:
    """Stopping early must not make the result depend on iteration order."""
    base = (CORPUS / "overlapping.md").read_text(encoding="utf-8")
    paragraphs = paragraphs_of("\n\n".join([base] * 8))

    for budget in (50, 500, 5000):
        first, first_updates = patterns.shared_token_counts(paragraphs, budget=budget)
        second, second_updates = patterns.shared_token_counts(paragraphs, budget=budget)
        assert first == second
        assert first_updates == second_updates
        assert first_updates <= budget


def test_a_larger_budget_never_loses_a_pair_a_smaller_one_found() -> None:
    """Rarest-first is what makes truncation monotonic rather than arbitrary."""
    base = (CORPUS / "overlapping.md").read_text(encoding="utf-8")
    paragraphs = paragraphs_of("\n\n".join([base] * 8))

    small, _ = patterns.shared_token_counts(paragraphs, budget=500)
    large, _ = patterns.shared_token_counts(paragraphs, budget=50000)
    for pair, count in small.items():
        assert large[pair] >= count, f"{pair} lost evidence when the budget grew"


def test_repeated_phrase_retention_is_bounded() -> None:
    """N-gram counting is the other place memory could run away."""
    sentence = "The framework enables the team to deliver the outcome reliably. "
    varied = "".join(
        sentence.replace("outcome", f"outcome{index}") for index in range(400)
    )
    finding = patterns.repeated_phrase(varied)
    if finding is not None:
        assert len(finding.evidence) <= policy.NGRAM_MAX_RETAINED
