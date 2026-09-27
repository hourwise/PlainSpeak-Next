"""The V1 quality blockers, and how they behave together.

Three changes that interact, tested here on their own and in combination:

- **The style guard.** SAFE changes that together would make a baseline style
  diagnostic more severe are withheld, rule by rule, and refused with the
  diagnostic named.
- **Honest connective counting.** The connectives PlainSpeak's own rules write
  are counted when they open a sentence, so a swap cannot make a transition
  measure look better than it is.
- **Short-text honesty.** A diagnostic without enough text says so, rather
  than falling silent in a way a reader could take for a clean result.

The integrity equivalence is tested in `test_integrity_equivalence.py`; its
interactions with the rest are tested here.
"""
from __future__ import annotations

from collections import Counter

import pytest
from click.testing import CliRunner

from plainspeak.adapters.cli import main
from plainspeak.integrity import snapshot
from plainspeak.pipeline import (
    COVERAGE_ASSESSED,
    COVERAGE_INSUFFICIENT,
    build_review_bundle,
    parse_source,
    present_text,
)
from plainspeak.pipeline.audit import plan_to_dict
from plainspeak.pipeline.planner import build_plan
from plainspeak.pipeline.style_guard import REFUSAL_STYLE_REGRESSION
from plainspeak.style import policy
from plainspeak.style.analyze import interpret_baseline
from plainspeak.style.patterns import transition_hits
from plainspeak.style.profiles import load_profile

PROFILES = ("natural", "plain", "technical", "government", "academic")

#: Four paragraphs that lean on "Furthermore", "Moreover" and "Additionally".
#: Three safe fixes turn all three into "Also,", which on its own would make
#: twelve of twenty sentences begin with the same word.
SIGNPOSTED = """The migration plan covers three services. Furthermore, the billing service must move first because it owns the ledger. Moreover, the ledger schema changes in version 4.2. Additionally, the reporting jobs read from the same tables. The team will freeze writes for 30 minutes.

Furthermore, the search index must be rebuilt after the move. Moreover, the rebuild takes about two hours on current hardware. Additionally, the cache must be cleared before traffic returns. Nevertheless, the plan keeps the old cluster online for a week. The rollback window closes on 14 March.

Furthermore, support staff need a short briefing. Moreover, customers on the enterprise tier get an email notice. Additionally, the status page will show a banner. Nevertheless, some users will see stale data for a few minutes. Nevertheless, no payments will be lost.

Furthermore, monitoring alerts are tuned for the new cluster. Moreover, on-call staff will have a written runbook. Additionally, the database team will review the indexes. Nevertheless, the first week will need close watching. The owner of this plan is the platform team.
"""

SHORT = "In order to reset it, staff must utilize the portal prior to 3 June 2027.\n"


def severities(text: str) -> dict[str, str]:
    from plainspeak.pipeline.styling import observe_style

    analysis = interpret_baseline(observe_style(parse_source(text)))
    return {finding.id: finding.severity for finding in analysis.findings}


_RANK = {"": 0, "info": 1, "notice": 2, "strong": 3}


# ── The style guard ────────────────────────────────────────────────────────


def test_safe_changes_never_make_a_baseline_diagnostic_more_severe():
    before = severities(SIGNPOSTED)
    after = severities(present_text(SIGNPOSTED, "natural").text)
    worse = {key: (before.get(key, ""), value) for key, value in after.items()
             if _RANK[value] > _RANK[before.get(key, "")]}
    assert worse == {}


def test_without_the_guard_the_same_changes_would_have():
    """The case the guard exists for, shown to be real rather than assumed."""
    from plainspeak.pipeline import Span

    plan = build_plan(parse_source(SIGNPOSTED))
    withheld = [item for item in plan.refused if item.reason.startswith(REFUSAL_STYLE_REGRESSION)]
    assert withheld
    replacements = [(item.source_span, item.replacement) for item in plan.accepted]
    # A withheld change is inapplicable, so its span is rebuilt from the record.
    replacements += [
        (Span(item.source_spans[0].start, item.source_spans[-1].end), item.replacement)
        for item in withheld
    ]
    unguarded = parse_source(SIGNPOSTED).serialise(replacements)
    assert severities(unguarded).get(policy.REPEATED_SENTENCE_OPENER)
    assert not severities(SIGNPOSTED).get(policy.REPEATED_SENTENCE_OPENER)


def test_a_withheld_change_is_refused_with_the_diagnostic_named():
    result = present_text(SIGNPOSTED, "natural")
    withheld = [item for item in result.refused if REFUSAL_STYLE_REGRESSION in item.refusal]
    assert withheld
    for item in withheld:
        assert item.badge == "REFUSED"
        assert policy.REPEATED_SENTENCE_OPENER in item.refusal
        assert result.text[item.revised_start:item.revised_end] == item.before


def test_a_rule_is_admitted_or_withheld_as_a_whole():
    """Never some of one rule's replacements and not others."""
    result = present_text(SIGNPOSTED, "natural")
    applied = {item.rule_id for item in result.applied}
    withheld = {item.rule_id for item in result.refused if REFUSAL_STYLE_REGRESSION in item.refusal}
    assert applied and withheld
    assert not applied & withheld


def test_the_guard_admits_rules_in_identifier_order():
    result = present_text(SIGNPOSTED, "natural")
    applied = sorted({item.rule_id for item in result.applied})
    withheld = sorted({item.rule_id for item in result.refused
                       if REFUSAL_STYLE_REGRESSION in item.refusal})
    # PS.LEXICAL.103 ("Additionally") is admitted first; the two after it would
    # each add four more "Also" openers and are declined.
    assert applied == ["PS.LEXICAL.103"]
    assert withheld == ["PS.LEXICAL.161", "PS.LEXICAL.183"]


def test_the_guard_does_nothing_when_nothing_gets_worse():
    text = "Staff utilise the register.\n\nThe team will commence the audit in order to check it.\n"
    plan = build_plan(parse_source(text))
    assert plan.accepted
    assert not [item for item in plan.refused if item.reason.startswith(REFUSAL_STYLE_REGRESSION)]


def test_safe_output_does_not_depend_on_the_profile():
    """The guard judges against the baseline, so SAFE means the same for everyone."""
    outputs = {present_text(SIGNPOSTED, name).text for name in PROFILES}
    assert len(outputs) == 1


def test_the_plan_names_the_style_policy_it_was_guarded_under():
    plan = build_plan(parse_source(SIGNPOSTED))
    record = plan_to_dict(plan)
    assert plan.style_policy_version == policy.STYLE_POLICY_VERSION == "2026.2"
    assert plan.style_policy_hash == policy.policy_hash()
    assert record["style_policy_version"] == "2026.2"
    assert record["style_policy_sha256"] == policy.policy_hash()


def test_the_guard_is_deterministic():
    first = build_plan(parse_source(SIGNPOSTED))
    second = build_plan(parse_source(SIGNPOSTED))
    assert plan_to_dict(first) == plan_to_dict(second)


# ── Honest counting ────────────────────────────────────────────────────────


@pytest.mark.parametrize("opener", ["Also,", "So,", "Even so,", "By contrast,", "After that,"])
def test_the_connectives_plainspeak_writes_are_counted(opener):
    assert transition_hits(f"{opener} the plan changed.") != []


@pytest.mark.parametrize(
    "text",
    [
        "We also tested it.",           # mid-sentence "also" is ordinary prose
        "It is so much better.",        # an intensifier, not a connective
        "Also-rans rarely win.",        # a compound, not a connective
        "Soon the team left.",          # a different word
    ],
)
def test_ordinary_uses_are_not_counted(text):
    assert transition_hits(text) == []


def test_a_swap_does_not_lower_the_transition_count():
    """The failure that honest counting closes: a swap used to look like a cut."""
    before = transition_hits("Furthermore, the fee is waived. Moreover, the form is shorter.")
    after = transition_hits("Also, the fee is waived. Also, the form is shorter.")
    assert len(after) == len(before)


# ── Short-text honesty ─────────────────────────────────────────────────────


def test_a_short_text_reports_insufficient_sample_for_every_diagnostic():
    bundle = build_review_bundle(parse_source(SHORT), "natural")
    assert bundle.diagnostics() == ()
    assert len(bundle.insufficient_sample()) == len(policy.DIAGNOSTIC_IDS)


def test_a_long_text_is_assessed():
    coverage = build_review_bundle(parse_source(SIGNPOSTED), "natural").coverage()
    statuses = Counter(item.status for item in coverage)
    assert statuses[COVERAGE_ASSESSED] >= 6


@pytest.mark.parametrize("name", PROFILES)
def test_the_minimum_is_the_profiles_own(name):
    """Technical asks for more blocks and academic for more paragraphs than the baseline."""
    profile = load_profile(name)
    for item in build_review_bundle(parse_source(SIGNPOSTED), name).coverage():
        assert item.minimum == profile.rule(item.id).minimum_sample


def test_every_diagnostic_declares_its_sample_unit():
    assert set(policy.SAMPLE_UNITS) == set(policy.DIAGNOSTIC_IDS)
    assert set(policy.SAMPLE_UNITS.values()) <= {"sentences", "paragraphs", "words", "blocks",
                                                 "transitions"}


def test_coverage_agrees_with_the_observation_where_there_is_one():
    bundle = build_review_bundle(parse_source(SIGNPOSTED), "natural")
    observed = bundle.observations.by_id()
    for item in bundle.coverage():
        if item.id in observed:
            assert item.sample_size == observed[item.id].sample_size
            assert bundle.observations.samples[item.id] == observed[item.id].sample_size


def test_present_json_carries_the_coverage():
    data = present_text(SHORT, "natural").as_dict()
    assert data["counts"]["insufficient_sample"] == len(policy.DIAGNOSTIC_IDS)
    assert {item["status"] for item in data["style_coverage"]} == {COVERAGE_INSUFFICIENT}
    for item in data["style_coverage"]:
        assert item["sample_size"] < item["minimum"]
        assert item["unit"] == policy.SAMPLE_UNITS[item["id"]]


def test_the_cli_summary_says_too_short_rather_than_nothing():
    result = CliRunner().invoke(main, ["present", "--stdin", "--profile", "natural",
                                       "--format", "summary"], input=SHORT)
    assert result.exit_code == 0
    assert "INSUFFICIENT_SAMPLE" in result.stdout
    assert "not judged clean" in result.stdout


def _session_for(tmp_path, text: str):
    from plainspeak.desktop.session import ReviewSession

    path = tmp_path / "doc.md"
    path.write_text(text, encoding="utf-8")
    session = ReviewSession()
    session.load(path, text)
    return session


def test_the_desktop_session_carries_the_coverage(tmp_path):
    session = _session_for(tmp_path, SHORT)
    document = parse_source(SHORT)
    generation = session.begin_analysis()
    session.accept_analysis(build_review_bundle(document, session.snapshot().profile_id), generation)
    assert len(session.snapshot().insufficient) == len(policy.DIAGNOSTIC_IDS)


# ── Together ───────────────────────────────────────────────────────────────


def test_a_short_text_still_gets_its_safe_fixes():
    """Too short for style is not too short for safe changes, and the guard stays out of it."""
    result = present_text(SHORT, "natural")
    assert {item.rule_id for item in result.applied} >= {"PS.CLARITY.001", "PS.CLARITY.009"}
    assert "before 3 June 2027" in result.text


def test_equivalence_and_protected_facts_survive_together():
    result = present_text(SHORT, "natural")
    data = result.as_dict()
    assert data["protected"]["preserved"] is True
    assert snapshot(result.source_text).signature == snapshot(result.text).signature
    assert "must" in result.text


def test_equivalence_does_not_unlock_a_different_refusal():
    text = "It should be noted that staff must file it prior to the hearing.\n"
    result = present_text(text, "natural")
    assert "before the hearing" in result.text
    assert "It should be noted that" in result.text
    assert "PS.FRAMING.003" in {item.rule_id for item in result.refused}


def test_the_desktop_and_present_agree_on_what_changed(tmp_path):
    result = present_text(SIGNPOSTED, "natural")
    session = _session_for(tmp_path, SIGNPOSTED)
    document = parse_source(SIGNPOSTED)
    generation = session.begin_analysis()
    session.accept_analysis(build_review_bundle(document, "natural"), generation)
    snap = session.snapshot()
    assert snap.revised_text == result.text
    assert [c.change_id for c in snap.changes] == [c.change_id for c in result.preview.changes]


def test_the_whole_contract_is_deterministic_with_every_feature_in_play():
    text = SIGNPOSTED + "\nIt should be noted that staff must file it prior to 3 June 2027.\n"
    assert present_text(text, "plain").to_json() == present_text(text, "plain").to_json()


# ── What a profile changes ─────────────────────────────────────────────────


def test_style_suggestions_really_are_the_same_under_every_profile():
    """HOW_IT_WORKS.md, the CLI and the desktop all say so; this keeps it true.

    Every bundled style fix is triggered by a diagnostic whose line — both
    bands and the minimum sample — is identical in all five profiles. If a
    profile ever draws that line differently, the documentation is wrong and
    this fails.
    """
    from plainspeak.rules import load_ruleset

    triggers = {rule.trigger.diagnostic for rule in load_ruleset().style_fixes}
    assert triggers
    for diagnostic in triggers:
        lines = {
            (rule.threshold_for("notice"), rule.threshold_for("strong"), rule.minimum_sample, rule.enabled)
            for rule in (load_profile(name).rule(diagnostic) for name in PROFILES)
        }
        assert len(lines) == 1, (diagnostic, lines)


def test_every_interface_says_what_a_profile_changes():
    from pathlib import Path

    from plainspeak.adapters import cli

    assert "does not change the automatic SAFE" in " ".join(cli.PROFILE_SCOPE.split())
    listed = CliRunner().invoke(main, ["profiles", "list"]).output
    assert "does not change the automatic SAFE" in " ".join(listed.split())
    window = (Path(cli.__file__).resolve().parents[1] / "desktop" / "main_window.py").read_text(encoding="utf-8")
    assert "does not change the automatic SAFE" in window
