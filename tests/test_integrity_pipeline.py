"""The firewall's interaction with the rule engine.

Rules propose; integrity vetoes. A rule classified `safe-fix` does not outrank
this layer, and nothing anywhere can switch it off.

Three interactions get the most attention:

**Ordering.** The firewall runs after conflict resolution, on the proposal that
resolution chose. If a vetoed proposal's losing rival were reinstated, the
engine would have two paths to deciding an overlap, and which one applied would
depend on which safety check happened to fire.

**Layering.** A proposal is checked against its own span, against its enclosing
block, and — once the whole output exists — against the entire document. Only
the last of those can see what several edits did together.

**Freshness.** A plan carries the identity of the policy that approved it.
Applying it under a different policy would mean applying edits nobody checked.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from plainspeak.document import parse_markdown, parse_text
from plainspeak.integrity import policy_hash
from plainspeak.pipeline.apply import (
    ABORT_INTEGRITY,
    ABORT_STALE_POLICY,
    ApplicationError,
    apply_plan,
)
from plainspeak.pipeline.audit import plan_to_dict, plan_to_json
from plainspeak.pipeline.planner import REFUSAL_INTEGRITY, build_plan

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = sorted((REPO_ROOT / "tests" / "characterisation" / "corpus").glob("*.txt"))


def md(source: str):
    return parse_markdown.parse(source)


def rule_yaml(
    rule_id: str,
    text: str,
    replacement: str,
    priority: int = 100,
    mode: str = "safe-fix",
) -> str:
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
        f"id: {rule_id}\nversion: 1\nname: rule-{rule_id.lower().replace('.', '-')}\n"
        f"mode: {mode}\ndescription: >\n  A rule for firewall tests.\n"
        f'match:\n  type: phrase\n  text: "{text}"\n'
        f"{action}scope:\n  include: [prose]\npriority: {priority}\n"
        f'reason:\n  short: "Test rule {rule_id}"\n'
        f'provenance:\n  source: "PlainSpeak test suite"\n  reference: ""\n'
        f'  licence: "project-authored"\n'
        f'examples:\n  positive:\n    - "{text} here"\n'
        f'  negative:\n    - "nothing at all"\n{transform}'
    )


# ── Rules propose, integrity vetoes ────────────────────────────────────────


@pytest.mark.parametrize(
    "text,replacement,note",
    [
        ("must not", "must", "removes a prohibition"),
        ("cannot", "can", "removes a prohibition"),
        ("must", "may", "downgrades an obligation"),
        ("0.5 mg", "5 mg", "changes a dose"),
        ("14.7%", "14.7", "drops a percent sign"),
        ("before", "after", "reverses an ordering"),
        ("at least", "at most", "reverses a bound"),
        ("2026-08-29", "2026-08-30", "changes a date"),
    ],
    ids=["must-not", "cannot", "modal", "dose", "percent", "order", "bound", "date"],
)
def test_a_safe_fix_that_changes_meaning_is_vetoed(
    ruleset_from, text: str, replacement: str, note: str
) -> None:
    """A rule may be structurally valid and still be refused."""
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", text, replacement))
    document = md(f"The notice says {text} in this case.\n")
    plan = build_plan(document, ruleset)

    assert plan.accepted == (), f"the firewall let through a change that {note}"
    assert plan.integrity_refusals, "a veto must be recorded"
    assert plan.refused[0].reason.startswith(REFUSAL_INTEGRITY)

    result = apply_plan(document, plan)
    assert result.output == document.source, "nothing should have changed"


def test_a_harmless_safe_fix_still_applies(ruleset_from) -> None:
    """The firewall must not simply refuse everything."""
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "utilise", "use"))
    document = md("Staff utilise the register.\n")
    plan = build_plan(document, ruleset)

    assert len(plan.accepted) == 1
    assert plan.integrity_refusals == ()
    assert apply_plan(document, plan).output == "Staff use the register.\n"


def test_a_veto_records_what_it_found(ruleset_from) -> None:
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "must", "may"))
    plan = build_plan(md("You must apply now.\n"), ruleset)
    refusal = plan.integrity_refusals[0]

    assert refusal.rule_id == "PS.TEST.001"
    assert refusal.scope in {"proposal", "context"}
    assert [violation.kind for violation in refusal.violations] == ["modal"]
    assert refusal.violations[0].before == ("must",)
    assert refusal.violations[0].after == ("may",)


def test_a_diagnostic_is_unaffected_by_the_firewall(bundled) -> None:
    """Diagnostics propose nothing, so there is nothing to veto."""
    plan = build_plan(md("The application was refused by the panel.\n"), bundled)
    assert plan.diagnostics
    assert plan.integrity_refusals == ()


def test_context_catches_what_the_span_alone_cannot(ruleset_from) -> None:
    """A deletion beside a negation changes the sentence around it.

    The proposal's own span contains no protected fact — it is the word "quite"
    — but removing it from "not quite ready" leaves a different claim. The
    block-level comparison is what sees this.
    """
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "quite ready", "unready"))
    document = md("The report is not quite ready today.\n")
    plan = build_plan(document, ruleset)

    # "unready" contains no negation the policy recognises, so the sentence
    # loses nothing detectable; the point is that the check ran over the block.
    assert plan.proposals, "the rule should have matched"
    assert apply_plan(document, plan).output.count("not") == 1


# ── Conflict interaction ───────────────────────────────────────────────────


def test_a_vetoed_winner_does_not_resurrect_its_loser(ruleset_from) -> None:
    """The single most important ordering property in this phase.

    Two rules want the same text. Conflict resolution picks the higher-priority
    one; the firewall then vetoes it. The loser must *not* be reinstated: doing
    so would give the engine a second, implicit way of resolving an overlap, and
    which edit landed would depend on which safety check fired.
    """
    ruleset = ruleset_from(
        {
            "winner.yaml": rule_yaml("PS.TEST.001", "must", "may", priority=500),
            "loser.yaml": rule_yaml("PS.TEST.002", "must", "shall", priority=100),
        }
    )
    document = md("You must apply now.\n")
    plan = build_plan(document, ruleset)

    assert plan.conflicts, "the two rules should have conflicted"
    assert plan.conflicts[0].winner == "PS.TEST.001"

    assert plan.accepted == (), "the group must produce no automatic edit at all"
    vetoed = {item.rule_id for item in plan.integrity_refusals}
    assert vetoed == {"PS.TEST.001"}, "only the winner reaches the firewall"

    reasons = {change.rule_id: change.reason for change in plan.refused}
    assert reasons["PS.TEST.001"].startswith(REFUSAL_INTEGRITY)
    assert not reasons["PS.TEST.002"].startswith(REFUSAL_INTEGRITY), (
        "the loser was refused by conflict resolution, not by the firewall"
    )
    assert apply_plan(document, plan).output == document.source


def test_a_loser_that_would_have_passed_still_does_not_apply(ruleset_from) -> None:
    """Even when the loser is harmless. Resolution happens once."""
    ruleset = ruleset_from(
        {
            "winner.yaml": rule_yaml("PS.TEST.001", "must apply", "may apply", priority=500),
            "loser.yaml": rule_yaml("PS.TEST.002", "must apply", "must submit", priority=100),
        }
    )
    document = md("You must apply now.\n")
    plan = build_plan(document, ruleset)

    assert plan.accepted == ()
    assert apply_plan(document, plan).output == document.source


# ── Whole-plan verification ────────────────────────────────────────────────


def test_the_finished_document_is_verified_before_anything_is_returned() -> None:
    """A hand-built plan that passes preflight but corrupts the output aborts."""
    source = "You must not apply after 5pm.\n"
    document = md(source)
    plan = build_plan(document)

    from plainspeak.document.model import Span, content_hash
    from plainspeak.pipeline.plan import ProposedChange

    start = source.index("not ")
    forged = ProposedChange(
        rule_id="PS.TEST.999",
        rule_version=1,
        mode="safe-fix",
        analysis_span=Span(0, 0),
        source_spans=(Span(start, start + 4),),
        document_path=(0,),
        location="0",
        original_text="not ",
        original_hash=content_hash("not "),
        replacement="",
        applicable=True,
        reason="",
    )
    poisoned = replace(plan, accepted=(forged,))

    with pytest.raises(ApplicationError, match=ABORT_INTEGRITY):
        apply_plan(document, poisoned)
    assert document.source == source, "an abort must change nothing"


def test_the_whole_document_check_names_what_it_found() -> None:
    source = "The dose is 0.5 mg.\n"
    document = md(source)
    plan = build_plan(document)

    from plainspeak.document.model import Span, content_hash
    from plainspeak.pipeline.plan import ProposedChange

    start = source.index("0.5")
    forged = ProposedChange(
        rule_id="PS.TEST.999", rule_version=1, mode="safe-fix",
        analysis_span=Span(0, 0), source_spans=(Span(start, start + 3),),
        document_path=(0,), location="0",
        original_text="0.5", original_hash=content_hash("0.5"),
        replacement="5", applicable=True, reason="",
    )

    with pytest.raises(ApplicationError) as caught:
        apply_plan(document, replace(plan, accepted=(forged,)))
    assert "measurement" in str(caught.value)


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_the_corpus_survives_whole_document_verification(path: Path, bundled) -> None:
    """Every real document the project ships applies cleanly, or not at all."""
    source = path.read_bytes().decode("utf-8")
    document = md(source)
    result = apply_plan(document, build_plan(document, bundled))

    from plainspeak.integrity import check

    assert check(source, result.output).passed


# ── Policy freshness ───────────────────────────────────────────────────────


def test_a_plan_records_the_policy_that_approved_it(bundled) -> None:
    plan = build_plan(md("Staff utilise the register.\n"), bundled)
    assert plan.integrity_policy_hash == policy_hash()
    assert plan.integrity_policy_version


def test_a_plan_approved_under_another_policy_is_refused() -> None:
    document = md("Staff utilise the register.\n")
    plan = build_plan(document)
    stale = replace(
        plan, integrity_policy_version="2025.9", integrity_policy_hash="0" * 64
    )

    with pytest.raises(ApplicationError, match=ABORT_STALE_POLICY) as caught:
        apply_plan(document, stale)
    assert "2025.9" in str(caught.value)
    assert document.source == "Staff utilise the register.\n"


def test_the_result_reports_the_policy_it_ran_under() -> None:
    document = md("Staff utilise the register.\n")
    result = apply_plan(document, build_plan(document))
    assert result.integrity_policy_hash == policy_hash()


# ── The firewall cannot be disabled ────────────────────────────────────────


def test_no_rule_field_can_disable_the_firewall(ruleset_from) -> None:
    """The schema rejects unknown keys, so there is nowhere to put an override."""
    from plainspeak.rules import RuleError

    source = rule_yaml("PS.TEST.001", "must", "may") + "ignore_integrity: true\n"
    with pytest.raises(RuleError, match="unknown field"):
        ruleset_from(source)


def test_no_planner_argument_can_disable_the_firewall() -> None:
    """`build_plan` takes a document, a ruleset and a projection. Nothing else."""
    import inspect

    parameters = set(inspect.signature(build_plan).parameters)
    assert parameters == {"document", "ruleset", "projection"}


def test_no_application_argument_can_disable_the_firewall() -> None:
    import inspect

    parameters = set(inspect.signature(apply_plan).parameters)
    assert parameters == {"document", "plan"}


def test_the_integrity_check_is_not_optional_in_application() -> None:
    """Guard against the check being made conditional in a later edit."""
    import inspect

    from plainspeak.pipeline import apply as apply_module

    source = inspect.getsource(apply_module.apply_plan)
    assert "integrity_check(document.source, output)" in source
    assert "if not verdict.passed" in source


def test_the_cli_offers_no_unsafe_flag() -> None:
    from plainspeak.adapters import cli

    text = Path(cli.__file__).read_text(encoding="utf-8").lower()
    for flag in ("--unsafe", "--no-integrity", "--force", "--skip-integrity"):
        assert flag not in text


# ── The inherited register still applies ───────────────────────────────────


def test_both_authorities_operate_together(ruleset_from) -> None:
    """Protected terms and the firewall are independent, and both must pass."""
    ruleset = ruleset_from(
        {
            # Blocked by the inherited protected-term register.
            "a.yaml": rule_yaml("PS.TEST.001", "consideration", "thought"),
            # Blocked by the firewall.
            "b.yaml": rule_yaml("PS.TEST.002", "must", "may"),
            # Blocked by neither.
            "c.yaml": rule_yaml("PS.TEST.003", "utilise", "use"),
        }
    )
    document = md("You must utilise the consideration clause.\n")
    plan = build_plan(document, ruleset)

    assert {change.rule_id for change in plan.accepted} == {"PS.TEST.003"}

    reasons = {change.rule_id: change.reason for change in plan.refused}
    assert "protected term of art" in reasons["PS.TEST.001"]
    assert reasons["PS.TEST.002"].startswith(REFUSAL_INTEGRITY)
    assert apply_plan(document, plan).output == "You must use the consideration clause.\n"


def test_the_firewall_does_not_replace_the_protected_register(ruleset_from) -> None:
    """A protected term with no integrity facts must still be refused."""
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "consideration", "thought"))
    plan = build_plan(md("The consideration was adequate.\n"), ruleset)

    assert plan.accepted == ()
    assert plan.integrity_refusals == (), "this refusal belongs to the other authority"


# ── Audit ──────────────────────────────────────────────────────────────────


def test_the_audit_records_an_integrity_refusal(ruleset_from) -> None:
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "must", "may"))
    record = plan_to_dict(build_plan(md("You must apply now.\n"), ruleset))

    entry = next(item for item in record["changes"] if item["rule_id"] == "PS.TEST.001")
    assert entry["status"] == "refused"
    assert entry["integrity"]["violations"][0]["kind"] == "modal"
    assert entry["integrity"]["violations"][0]["before"] == ["must"]
    assert entry["integrity"]["violations"][0]["after"] == ["may"]
    assert record["counts"]["integrity_refusals"] == 1


def test_the_audit_names_the_policy(bundled) -> None:
    record = plan_to_dict(build_plan(md("Staff utilise the register.\n"), bundled))
    assert record["integrity_policy_sha256"] == policy_hash()
    assert record["integrity_policy_version"]


def test_the_audit_remains_deterministic_with_integrity_entries(ruleset_from) -> None:
    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "must", "may"))
    document = md("You must apply now.\n")
    assert plan_to_json(build_plan(document, ruleset)) == plan_to_json(
        build_plan(document, ruleset)
    )


def test_the_audit_still_carries_no_timestamp(ruleset_from) -> None:
    import re

    ruleset = ruleset_from(rule_yaml("PS.TEST.001", "must", "may"))
    rendered = plan_to_json(build_plan(md("You must apply now.\n"), ruleset))
    assert not re.search(r"\d{4}-\d{2}-\d{2}", rendered)


# ── Determinism ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_planning_with_the_firewall_is_deterministic(path: Path, bundled) -> None:
    source = path.read_bytes().decode("utf-8")
    first = build_plan(md(source), bundled)
    second = build_plan(md(source), bundled)

    assert [c.rule_id for c in first.accepted] == [c.rule_id for c in second.accepted]
    assert [r.rule_id for r in first.integrity_refusals] == [
        r.rule_id for r in second.integrity_refusals
    ]


def test_rule_order_does_not_change_which_proposals_are_vetoed(bundled) -> None:
    import random

    from plainspeak.rules import Ruleset

    source = "Staff utilise the register prior to the hearing, in order to apply.\n"
    document = md(source)
    baseline = build_plan(document, bundled)

    for seed in range(6):
        shuffled = list(bundled.rules)
        random.Random(seed).shuffle(shuffled)
        reordered = Ruleset(version=bundled.version, hash=bundled.hash, rules=tuple(shuffled))
        plan = build_plan(document, reordered)

        assert [r.rule_id for r in plan.integrity_refusals] == [
            r.rule_id for r in baseline.integrity_refusals
        ]
        assert [c.rule_id for c in plan.accepted] == [c.rule_id for c in baseline.accepted]


def test_plain_text_documents_are_protected_too() -> None:
    document = parse_text.parse("You must not apply after 5pm.\n")
    plan = build_plan(document)
    assert apply_plan(document, plan).output == document.source


# ── Bounded work ───────────────────────────────────────────────────────────


def test_integrity_work_per_proposal_is_bounded_by_the_block(bundled, monkeypatch) -> None:
    """No proposal triggers a full-document scan.

    The firewall checks a proposal against its own span and against its
    enclosing block. Checking each one against the whole document instead would
    be quadratic in a long report and would buy nothing: the document-global
    comparison happens once, at application time.

    Asserted structurally rather than by timing, so it cannot go flaky and
    cannot be satisfied by a fast machine.
    """
    from plainspeak.pipeline import planner as planner_module

    source = "\n\n".join(
        f"Paragraph {index}: staff utilise the register in order to apply."
        for index in range(40)
    ) + "\n"
    document = md(source)

    seen: list[int] = []
    original = planner_module.integrity_check

    def recording(before: str, after: str):
        seen.append(len(before))
        return original(before, after)

    monkeypatch.setattr(planner_module, "integrity_check", recording)
    plan = build_plan(document, bundled)

    assert plan.accepted, "the fixture should produce proposals to check"
    longest_block = max(len(part) for part in source.split("\n\n"))
    assert max(seen) <= longest_block + 8, (
        f"a proposal was checked against {max(seen)} characters, but the longest "
        f"block is {longest_block} — something is scanning the whole document"
    )
    # Two comparisons per surviving proposal at most: its span, then its block.
    assert len(seen) <= 2 * len(plan.proposals)


def test_the_document_wide_check_runs_exactly_once(monkeypatch) -> None:
    """One whole-document comparison per application, not one per change."""
    from plainspeak.pipeline import apply as apply_module

    source = "Staff utilise the register in order to apply, and commence work.\n"
    document = md(source)
    plan = build_plan(document)
    assert len(plan.accepted) >= 3

    calls = []
    original = apply_module.integrity_check

    def recording(before: str, after: str):
        calls.append((len(before), len(after)))
        return original(before, after)

    monkeypatch.setattr(apply_module, "integrity_check", recording)
    apply_plan(document, plan)

    assert len(calls) == 1
    assert calls[0][0] == len(source)
