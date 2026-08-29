"""Every bundled rule, tested against its own stated examples.

A rule that ships without saying when it should fire and when it should stay
quiet is a rule nobody can review. The schema requires both, and this suite
enforces that the claims are true: each positive example must match, each
negative example must not, and each safe-fix must produce the transformation it
advertises.

The negative cases carry as much weight as the positive ones. Detecting a
phrase is easy; the cost of a prose tool is false positives, and a rule with no
stated false-positive case is a rule whose author has not yet thought about
when it should hold its tongue.
"""
from __future__ import annotations

import pytest

from plainspeak.document import parse_markdown
from plainspeak.pipeline.apply import apply_plan
from plainspeak.pipeline.planner import build_plan
from plainspeak.rules import (
    MODE_DIAGNOSTIC,
    MODE_PROTECTED,
    MODE_SAFE_FIX,
    Rule,
    explain_rule,
    find_matches,
    load_ruleset,
)
from plainspeak.rules.explain import list_rules

RULESET = load_ruleset()
RULES = list(RULESET.rules)
SAFE_FIXES = [rule for rule in RULES if rule.mode == MODE_SAFE_FIX]

#: The build plan asks for a bounded but production-quality starter set.
MINIMUM_RULES = 20


def ids(rules) -> list:
    return [rule.id for rule in rules]


# ── The ruleset as shipped ─────────────────────────────────────────────────


def test_the_ruleset_is_large_enough_to_be_representative() -> None:
    assert len(RULES) >= MINIMUM_RULES


def test_the_ruleset_covers_several_families() -> None:
    families = {rule.family for rule in RULES}
    assert families >= {"clarity", "framing", "lexical", "protected", "voice"}


def test_every_mode_is_represented() -> None:
    """A ruleset of nothing but safe fixes would not be a conservative one."""
    modes = {rule.mode for rule in RULES}
    assert modes == {MODE_SAFE_FIX, MODE_DIAGNOSTIC, MODE_PROTECTED}


def test_rule_ids_are_unique_and_well_formed() -> None:
    assert len(set(ids(RULES))) == len(RULES)
    for rule in RULES:
        assert rule.id.startswith("PS.")
        assert rule.version >= 1


def test_every_rule_records_its_provenance() -> None:
    for rule in RULES:
        assert rule.provenance.source.strip(), f"{rule.id} has no provenance source"
        assert rule.provenance.licence.strip(), f"{rule.id} has no provenance licence"


def test_no_bundled_rule_claims_third_party_data() -> None:
    """If one ever does, THIRD_PARTY_NOTICES.md has to say so.

    Studying another project does not require copying its data, and nothing
    here has copied any. This test is the tripwire for that changing quietly.
    """
    from pathlib import Path

    third_party = [
        rule.id for rule in RULES if rule.provenance.licence != "project-authored"
    ]
    if third_party:
        notices = Path(__file__).resolve().parent.parent / "THIRD_PARTY_NOTICES.md"
        assert notices.exists(), "third-party rule data needs a notices file"
        content = notices.read_text(encoding="utf-8")
        for rule_id in third_party:
            assert rule_id in content, f"{rule_id} uses third-party data but is not in the notices"


# ── Positive examples ──────────────────────────────────────────────────────


@pytest.mark.parametrize("rule", RULES, ids=ids(RULES))
def test_positive_examples_match(rule: Rule) -> None:
    """Every example the rule says it catches must actually be caught."""
    for example in rule.examples.positive:
        matches = [m for m in find_matches(example, [rule])]
        assert matches, f"{rule.id} did not match its own positive example: {example!r}"


@pytest.mark.parametrize("rule", RULES, ids=ids(RULES))
def test_negative_examples_do_not_match(rule: Rule) -> None:
    """Every example the rule says it leaves alone must be left alone."""
    for example in rule.examples.negative:
        matches = [m for m in find_matches(example, [rule])]
        assert not matches, (
            f"{rule.id} fired on its own negative example {example!r}, "
            f"matching {[m.matched_text for m in matches]}"
        )


# ── Safe fixes do what they say ────────────────────────────────────────────


@pytest.mark.parametrize("rule", SAFE_FIXES, ids=ids(SAFE_FIXES))
def test_stated_transformations_are_produced(rule: Rule) -> None:
    """Run the rule's own worked example through the whole pipeline."""
    for example in rule.examples.transform:
        document = parse_markdown.parse(example.before + "\n")
        result = apply_plan(document, build_plan(document, RULESET))
        assert result.output.rstrip("\n") == example.after, (
            f"{rule.id} advertises {example.after!r} but produced "
            f"{result.output.rstrip(chr(10))!r}"
        )


@pytest.mark.parametrize("rule", SAFE_FIXES, ids=ids(SAFE_FIXES))
def test_a_safe_fix_output_is_stable(rule: Rule) -> None:
    """The engine must not want to change its own output again."""
    for example in rule.examples.transform:
        document = parse_markdown.parse(example.after + "\n")
        plan = build_plan(document, RULESET)
        assert plan.accepted == (), (
            f"{rule.id} would keep editing its own output: "
            f"{[c.original_text for c in plan.accepted]}"
        )


@pytest.mark.parametrize("rule", SAFE_FIXES, ids=ids(SAFE_FIXES))
def test_a_safe_fix_replacement_is_not_matched_by_any_rule(rule: Rule) -> None:
    """The direct cause of a non-idempotent ruleset, checked at the source."""
    replacement = rule.action.replacement
    if not replacement:
        return
    matches = find_matches(replacement, RULES)
    assert not matches, (
        f"{rule.id} replaces text with {replacement!r}, which "
        f"{matches[0].rule_id} then matches"
    )


# ── Conservatism ───────────────────────────────────────────────────────────


def test_words_with_shifting_meaning_are_diagnostics_not_fixes() -> None:
    """Detecting a word is not the same as being able to replace it.

    "Aforementioned" has no single substitution — "the aforementioned document"
    does not become "the this document" — so it reports rather than edits. This
    test pins that judgement so nobody promotes it to a safe fix without
    thinking about the grammar.
    """
    rule = RULESET.by_id("PS.LEXICAL.012")
    assert rule is not None
    assert rule.mode == MODE_DIAGNOSTIC


def test_passive_detection_never_proposes_an_edit() -> None:
    """Turning a passive active needs an actor the sentence may not contain."""
    rule = RULESET.by_id("PS.VOICE.001")
    assert rule.mode == MODE_DIAGNOSTIC
    assert rule.action.type == "none"


def test_deletions_declare_how_they_handle_capitalisation() -> None:
    """A deletion that leaves a lower-case sentence start must say what it does."""
    deletions = [rule for rule in SAFE_FIXES if rule.action.type == "delete"]
    assert deletions, "the ruleset should exercise deletion"
    for rule in deletions:
        assert rule.action.recapitalize, f"{rule.id} deletes without stating a casing policy"
        assert rule.match.text.endswith(" "), (
            f"{rule.id} must own its trailing space, or deleting it leaves a double space"
        )


# ── Explanation ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rule", RULES, ids=ids(RULES))
def test_every_rule_can_explain_itself(rule: Rule) -> None:
    explanation = explain_rule(rule.id, RULESET)

    assert explanation.id == rule.id
    assert explanation.reason
    assert explanation.matches, "an explanation must say what the rule looks for"
    assert explanation.proposes, "an explanation must say what the rule would do"
    assert explanation.provenance_source


def test_explaining_an_unknown_rule_raises() -> None:
    with pytest.raises(KeyError, match="no such rule"):
        explain_rule("PS.NOSUCH.999", RULESET)


def test_an_explanation_is_plain_data() -> None:
    import json

    rendered = explain_rule("PS.CLARITY.001", RULESET).as_dict()
    assert json.loads(json.dumps(rendered)) == rendered
    assert rendered["mode"] == MODE_SAFE_FIX
    assert rendered["examples"]["transform"]


def test_listing_rules_returns_them_in_identity_order() -> None:
    listed = list_rules(RULESET)
    assert [item.id for item in listed] == sorted(item.id for item in listed)
    assert len(listed) == len(RULES)


def test_a_diagnostic_explains_that_it_proposes_nothing() -> None:
    explanation = explain_rule("PS.VOICE.001", RULESET)
    assert "reports only" in explanation.proposes


def test_a_protected_rule_explains_that_it_protects() -> None:
    explanation = explain_rule("PS.PROTECT.001", RULESET)
    assert explanation.mode == MODE_PROTECTED
    assert "reports only" in explanation.proposes or "nothing" in explanation.proposes
