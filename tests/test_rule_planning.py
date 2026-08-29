"""Planning: projection integration, authority, protection and conflicts.

The planner is where a rule's opinion about a string becomes a decision about a
document, and every safeguard in the system meets here. Three properties carry
the weight:

**Rules never see a modified document.** All matching happens against one
projection of the original. If a rule saw text an earlier rule had changed, the
result would depend on which order the rules ran in, and every claim to
determinism would be gone.

**Protection cannot be bypassed.** Declarative `protected` rules and the
inherited register in `plainspeak.integrity.protected` are checked
independently, and a proposal has to survive both.

**Conflicts are settled by rule, not by accident.** Where two rules want the
same characters and neither has been given precedence, both are refused. That
is not a limitation to be fixed later — picking one would make the output depend
on something nobody chose.
"""
from __future__ import annotations

import random

import pytest

from plainspeak.document import parse_markdown, parse_text
from plainspeak.document.model import REASON_QUOTE
from plainspeak.pipeline.planner import (
    REFUSAL_CONFLICT,
    REFUSAL_DECLARED_PROTECTED,
    REFUSAL_DIAGNOSTIC,
    REFUSAL_DUPLICATE,
    REFUSAL_INHERITED_PROTECTED,
    REFUSAL_SUPERSEDED_LONGER,
    REFUSAL_SUPERSEDED_PRIORITY,
    build_plan,
)

from .conftest import VALID_RULE


def md(source: str):
    return parse_markdown.parse(source)


def plan_for(source: str, ruleset=None):
    document = md(source)
    return document, build_plan(document, ruleset)


def rule_yaml(
    rule_id: str,
    text: str,
    replacement: str = "REPLACED",
    mode: str = "safe-fix",
    priority: int = 100,
    match_type: str = "phrase",
    scope_include: str = "[prose]",
) -> str:
    """A minimal valid rule, for tests that care about one property."""
    action = {
        "safe-fix": f'action:\n  type: replace\n  replacement: "{replacement}"\n',
        "protected": "action:\n  type: protect\n",
        "diagnostic": "",
    }[mode]
    transform = (
        f'  transform:\n    - before: "{text} here"\n      after: "{replacement} here"\n'
        if mode == "safe-fix"
        else ""
    )
    return (
        f"id: {rule_id}\n"
        f"version: 1\n"
        f"name: rule-{rule_id.lower().replace('.', '-')}\n"
        f"mode: {mode}\n"
        f"description: >\n  A rule for planner tests.\n"
        f"match:\n  type: {match_type}\n  text: \"{text}\"\n"
        f"{action}"
        f"scope:\n  include: {scope_include}\n"
        f"priority: {priority}\n"
        f'reason:\n  short: "Test rule {rule_id}"\n'
        f'provenance:\n  source: "PlainSpeak test suite"\n  reference: ""\n'
        f'  licence: "project-authored"\n'
        f"examples:\n"
        f'  positive:\n    - "{text} here"\n'
        f'  negative:\n    - "nothing to see"\n'
        f"{transform}"
    )


# ── Rules see the original, always ─────────────────────────────────────────


def test_no_edit_is_applied_while_matching(ruleset_from) -> None:
    """Two rules whose outputs would feed each other must not chain.

    `alpha` becomes `beta`, and a second rule turns `beta` into `gamma`. If
    matching ran against a progressively modified document, the first rule's
    output would trigger the second and the result would be `gamma`. It must be
    `beta`: every rule saw the original.
    """
    ruleset = ruleset_from(
        {
            "a.yaml": rule_yaml("PS.TEST.001", "alpha", "beta"),
            "b.yaml": rule_yaml("PS.TEST.002", "beta", "gamma"),
        }
    )
    document, plan = plan_for("The alpha value is recorded.\n", ruleset)

    fired = {change.rule_id for change in plan.accepted}
    assert fired == {"PS.TEST.001"}, "the second rule matched output the first produced"

    from plainspeak.pipeline.apply import apply_plan

    assert apply_plan(document, plan).output == "The beta value is recorded.\n"


def test_rule_order_does_not_change_the_plan(bundled) -> None:
    source = (
        "It is important to note that staff utilise the register in order to "
        "ascertain approximately how many additional forms are needed.\n"
    )
    document = md(source)
    baseline = build_plan(document, bundled)

    for seed in range(8):
        shuffled = list(bundled.rules)
        random.Random(seed).shuffle(shuffled)
        from plainspeak.rules import Ruleset

        reordered = Ruleset(version=bundled.version, hash=bundled.hash, rules=tuple(shuffled))
        plan = build_plan(document, reordered)

        assert [c.rule_id for c in plan.accepted] == [c.rule_id for c in baseline.accepted]
        assert [c.source_span for c in plan.accepted] == [c.source_span for c in baseline.accepted]
        assert [c.reason for c in plan.refused] == [c.reason for c in baseline.refused]


# ── Projection integration ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "source,expect_accepted",
    [
        ("Staff utilise the register.\n", True),
        ("Staff **utilise** the register.\n", True),
        ("Staff *utilise* the register.\n", True),
        ("# Staff utilise the register\n", True),
        ("- Staff utilise the register\n", True),
        ("See [staff utilise this](https://e.org/x).\n", True),
        ("Set `utilise` as the name.\n", False),
        ("```\nutilise\n```\n", False),
        ("> Staff utilise the register.\n", False),
        ("See [x](https://utilise.example/y).\n", False),
    ],
    ids=["plain", "bold", "emphasis", "heading", "list", "link-text",
         "code-span", "fence", "quote", "link-target"],
)
def test_the_projection_decides_where_a_rule_may_act(source: str, expect_accepted: bool) -> None:
    _, plan = plan_for(source)
    accepted = [c for c in plan.accepted if c.rule_id.startswith("PS.LEXICAL")]
    assert bool(accepted) is expect_accepted


def test_a_match_in_a_quote_is_refused_with_the_quote_reason(bundled) -> None:
    """Analysed, reported, and not rewritten — with the right explanation."""
    _, plan = plan_for("> Staff utilise the register.\n", bundled)
    refused = [c for c in plan.refused if c.rule_id == "PS.LEXICAL.001"]

    assert refused, "the match should still be recorded"
    assert refused[0].reason == REASON_QUOTE
    assert refused[0].original_text == "utilise"


def test_a_proposal_maps_to_exactly_the_original_characters() -> None:
    source = "Staff **utilise** the register.\n"
    document, plan = plan_for(source)
    change = next(c for c in plan.accepted if c.rule_id == "PS.LEXICAL.001")

    span = change.source_span
    assert source[span.start : span.end] == "utilise", "the edit must not touch the markers"


def test_a_match_crossing_a_block_boundary_is_dropped(ruleset_from) -> None:
    """The separator between blocks is not in the document."""
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "one two"))
    _, plan = plan_for("Ends with one\n\ntwo starts here.\n", ruleset)
    assert plan.proposals == ()


@pytest.mark.parametrize(
    "source", ["Staff utilise it.\r\nSecond line.\r\n", "Staff utilise it.\nSecond line.\n"],
    ids=["crlf", "lf"],
)
def test_line_endings_do_not_change_what_is_accepted(source: str) -> None:
    document, plan = plan_for(source)
    change = next(c for c in plan.accepted if c.rule_id == "PS.LEXICAL.001")
    span = change.source_span
    assert source[span.start : span.end] == "utilise"


def test_an_escaped_character_does_not_displace_a_later_match() -> None:
    r"""A `\*` is one character of prose spelled with two of source."""
    source = "A literal \\* then staff utilise the register.\n"
    document, plan = plan_for(source)
    change = next(c for c in plan.accepted if c.rule_id == "PS.LEXICAL.001")
    assert source[change.source_span.start : change.source_span.end] == "utilise"


def test_an_entity_does_not_displace_a_later_match() -> None:
    source = "Terms &amp; conditions: staff utilise the register.\n"
    document, plan = plan_for(source)
    change = next(c for c in plan.accepted if c.rule_id == "PS.LEXICAL.001")
    assert source[change.source_span.start : change.source_span.end] == "utilise"


# ── Scope ──────────────────────────────────────────────────────────────────


def test_a_rule_can_exclude_a_scope(ruleset_from) -> None:
    ruleset = ruleset_from(
        rule_yaml("PS.TEST.001", "alpha").replace(
            "  include: [prose]\n", "  include: [prose]\n  exclude: [heading]\n"
        )
    )
    _, in_heading = plan_for("# The alpha value\n", ruleset)
    _, in_prose = plan_for("The alpha value.\n", ruleset)

    assert in_heading.proposals == ()
    assert len(in_prose.accepted) == 1


def test_a_rule_can_target_a_scope_it_names(ruleset_from) -> None:
    ruleset = ruleset_from(
        rule_yaml("PS.TEST.001", "alpha", scope_include="[heading]")
    )
    _, in_heading = plan_for("# The alpha value\n", ruleset)
    _, in_prose = plan_for("The alpha value.\n", ruleset)

    assert len(in_heading.accepted) == 1
    assert in_prose.proposals == ()


def test_the_bundled_framing_rules_leave_headings_alone(bundled) -> None:
    _, plan = plan_for("# It is important to note that this is a heading\n", bundled)
    assert not [c for c in plan.accepted if c.rule_id.startswith("PS.FRAMING")]


# ── Diagnostics ────────────────────────────────────────────────────────────


def test_a_diagnostic_never_becomes_an_accepted_edit(bundled) -> None:
    _, plan = plan_for("The application was refused by the panel.\n", bundled)

    assert plan.diagnostics, "the passive construction should be reported"
    for finding in plan.diagnostics:
        assert not finding.applicable
        assert finding.replacement == ""
    assert not any(c.mode == "diagnostic" for c in plan.accepted)


def test_a_diagnostic_records_where_it_found_something(bundled) -> None:
    source = "Applicants shall provide evidence.\n"
    _, plan = plan_for(source, bundled)
    finding = next(c for c in plan.diagnostics if c.rule_id == "PS.VOICE.004")

    assert finding.original_text == "shall"
    assert finding.reason == REFUSAL_DIAGNOSTIC
    assert finding.source_spans


# ── Protection ─────────────────────────────────────────────────────────────


def test_a_protected_rule_beats_a_competing_safe_fix(ruleset_from) -> None:
    """The case the build plan names: A wants to replace, B protects."""
    ruleset = ruleset_from(
        {
            "fix.yaml": rule_yaml("PS.TEST.001", "provisional", "temporary"),
            "protect.yaml": rule_yaml("PS.TEST.002", "provisional measures", mode="protected"),
        }
    )
    _, protected = plan_for("The provisional measures were granted.\n", ruleset)
    _, unprotected = plan_for("The provisional figure was welcome.\n", ruleset)

    assert protected.accepted == ()
    assert protected.refused[0].reason == REFUSAL_DECLARED_PROTECTED
    assert len(unprotected.accepted) == 1, "protection must not spill beyond its phrase"


def test_protection_holds_whatever_order_the_rules_load_in(ruleset_from) -> None:
    """Protection computed before judging proposals, not as they are seen."""
    files = {
        "z_fix.yaml": rule_yaml("PS.TEST.001", "provisional", "temporary"),
        "a_protect.yaml": rule_yaml("PS.TEST.002", "provisional measures", mode="protected"),
    }
    reversed_files = {
        "a_fix.yaml": rule_yaml("PS.TEST.001", "provisional", "temporary"),
        "z_protect.yaml": rule_yaml("PS.TEST.002", "provisional measures", mode="protected"),
    }
    for layout in (files, reversed_files):
        _, plan = plan_for("The provisional measures were granted.\n", ruleset_from(layout))
        assert plan.accepted == ()


def test_the_bundled_protection_stops_the_bundled_safe_fix(bundled) -> None:
    _, plan = plan_for(
        "Name the contractor as an additional insured and send additional documents.\n", bundled
    )
    accepted = [c for c in plan.accepted if c.rule_id == "PS.LEXICAL.009"]
    refused = [c for c in plan.refused if c.rule_id == "PS.LEXICAL.009"]

    assert len(accepted) == 1, "the ordinary use should still be fixed"
    assert len(refused) == 1
    assert refused[0].reason == REFUSAL_DECLARED_PROTECTED


def test_the_inherited_register_still_overrides_a_rule(ruleset_from) -> None:
    """A declarative rule cannot reach a term the project already protects."""
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "consideration", "thought"))
    _, plan = plan_for("The consideration was adequate.\n", ruleset)

    assert plan.accepted == ()
    assert REFUSAL_INHERITED_PROTECTED in plan.refused[0].reason
    assert "consideration" in plan.refused[0].reason


def test_the_inherited_register_covers_any_word_inside_a_phrase(ruleset_from) -> None:
    """Replacing a phrase changes every word in it, protected ones included."""
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "the material fact", "the key point"))
    _, plan = plan_for("Disclose the material fact promptly.\n", ruleset)

    assert plan.accepted == ()
    assert REFUSAL_INHERITED_PROTECTED in plan.refused[0].reason


def test_no_bundled_safe_fix_targets_an_inherited_protected_term(bundled) -> None:
    """A rule that could never fire would be dead weight in the ruleset."""
    from plainspeak.integrity.protected import is_protected_term

    offenders = [
        rule.id
        for rule in bundled.safe_fixes
        for literal in (rule.match.literals or (rule.match.text,))
        for word in literal.split()
        if is_protected_term(word)
    ]
    assert not offenders, f"these rules can never apply: {sorted(set(offenders))}"


# ── Conflicts ──────────────────────────────────────────────────────────────


def test_identical_proposals_are_deduplicated(ruleset_from) -> None:
    ruleset = ruleset_from(
        {
            "a.yaml": rule_yaml("PS.TEST.001", "alpha", "beta"),
            "b.yaml": rule_yaml("PS.TEST.002", "alpha", "beta"),
        }
    )
    _, plan = plan_for("The alpha value.\n", ruleset)

    assert len(plan.accepted) == 1
    assert plan.accepted[0].rule_id == "PS.TEST.001", "the lowest rule ID wins, deterministically"
    assert plan.refused[0].reason == REFUSAL_DUPLICATE
    assert plan.conflicts[0].kind == "duplicate"


def test_the_same_span_with_different_replacements_refuses_both(ruleset_from) -> None:
    """No principled winner, so neither is applied."""
    ruleset = ruleset_from(
        {
            "a.yaml": rule_yaml("PS.TEST.001", "alpha", "beta"),
            "b.yaml": rule_yaml("PS.TEST.002", "alpha", "gamma"),
        }
    )
    document, plan = plan_for("The alpha value.\n", ruleset)

    assert plan.accepted == ()
    assert {c.reason for c in plan.refused} == {REFUSAL_CONFLICT}
    assert plan.conflicts[0].kind == "unresolved"

    from plainspeak.pipeline.apply import apply_plan

    assert apply_plan(document, plan).output == document.source, "nothing should change"


def test_an_explicit_priority_settles_a_conflict(ruleset_from) -> None:
    ruleset = ruleset_from(
        {
            "a.yaml": rule_yaml("PS.TEST.001", "alpha", "beta", priority=100),
            "b.yaml": rule_yaml("PS.TEST.002", "alpha", "gamma", priority=500),
        }
    )
    _, plan = plan_for("The alpha value.\n", ruleset)

    assert len(plan.accepted) == 1
    assert plan.accepted[0].rule_id == "PS.TEST.002"
    assert plan.accepted[0].replacement == "gamma"
    assert plan.conflicts[0].kind == "superseded-by-priority"


def test_a_longer_match_supersedes_one_it_contains(ruleset_from) -> None:
    ruleset = ruleset_from(
        {
            "short.yaml": rule_yaml("PS.TEST.001", "alpha", "X"),
            "long.yaml": rule_yaml("PS.TEST.002", "the alpha value", "Y"),
        }
    )
    document, plan = plan_for("Record the alpha value now.\n", ruleset)

    assert len(plan.accepted) == 1
    assert plan.accepted[0].rule_id == "PS.TEST.002"
    assert plan.conflicts[0].kind == "superseded-by-longer-match"
    assert plan.refused[0].reason == REFUSAL_SUPERSEDED_LONGER


def test_a_partial_overlap_refuses_both(ruleset_from) -> None:
    """Neither contains the other, so applying either would corrupt the other."""
    ruleset = ruleset_from(
        {
            "a.yaml": rule_yaml("PS.TEST.001", "alpha beta", "X"),
            "b.yaml": rule_yaml("PS.TEST.002", "beta gamma", "Y"),
        }
    )
    _, plan = plan_for("Record alpha beta gamma now.\n", ruleset)

    assert plan.accepted == ()
    assert plan.conflicts[0].kind == "unresolved"


def test_non_overlapping_proposals_all_survive(ruleset_from) -> None:
    ruleset = ruleset_from(
        {
            "a.yaml": rule_yaml("PS.TEST.001", "alpha", "X"),
            "b.yaml": rule_yaml("PS.TEST.002", "gamma", "Y"),
        }
    )
    _, plan = plan_for("Record alpha and gamma now.\n", ruleset)

    assert len(plan.accepted) == 2
    assert plan.conflicts == ()


def test_conflict_resolution_is_independent_of_file_order(ruleset_from) -> None:
    layouts = [
        {"a.yaml": rule_yaml("PS.TEST.001", "alpha", "X", priority=500),
         "b.yaml": rule_yaml("PS.TEST.002", "alpha", "Y", priority=100)},
        {"z.yaml": rule_yaml("PS.TEST.002", "alpha", "Y", priority=100),
         "y.yaml": rule_yaml("PS.TEST.001", "alpha", "X", priority=500)},
    ]
    outcomes = set()
    for layout in layouts:
        _, plan = plan_for("The alpha value.\n", ruleset_from(layout))
        outcomes.add(tuple((c.rule_id, c.replacement) for c in plan.accepted))
    assert len(outcomes) == 1, f"file order changed the decision: {outcomes}"


# ── Plan shape ─────────────────────────────────────────────────────────────


def test_accepted_and_refused_partition_the_proposals(bundled) -> None:
    source = (
        "It is important to note that staff utilise the register in order to apply.\n\n"
        "> Staff utilise the register.\n"
    )
    _, plan = plan_for(source, bundled)
    assert len(plan.accepted) + len(plan.refused) == len(plan.proposals)


def test_a_plan_is_bound_to_its_document_and_ruleset(bundled) -> None:
    document, plan = plan_for("Staff utilise the register.\n", bundled)

    assert plan.is_for(document)
    assert not plan.is_for(md("Something else entirely.\n"))
    assert plan.ruleset_hash == bundled.hash
    assert plan.ruleset_version == bundled.version


def test_a_plan_is_immutable(bundled) -> None:
    _, plan = plan_for("Staff utilise the register.\n", bundled)
    with pytest.raises(Exception):
        plan.accepted = ()  # type: ignore[misc]


def test_planning_the_same_document_twice_gives_the_same_plan(bundled) -> None:
    source = "It is important to note that staff utilise the register in order to apply.\n"
    _, first = plan_for(source, bundled)
    _, second = plan_for(source, bundled)

    assert [c.rule_id for c in first.accepted] == [c.rule_id for c in second.accepted]
    assert [c.source_span for c in first.accepted] == [c.source_span for c in second.accepted]
    assert first.projection_hash == second.projection_hash


def test_plain_text_documents_plan_too() -> None:
    document = parse_text.parse("Staff utilise the register in order to apply.\n")
    plan = build_plan(document)
    assert {c.rule_id for c in plan.accepted} == {"PS.LEXICAL.001", "PS.CLARITY.001"}


def test_an_empty_document_plans_to_nothing() -> None:
    document = md("")
    plan = build_plan(document)
    assert plan.proposals == ()
    assert plan.accepted == ()
    assert plan.diagnostics == ()
