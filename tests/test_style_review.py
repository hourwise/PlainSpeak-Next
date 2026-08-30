"""Review, approval and application of style proposals.

The path from a suggestion to an edit is the part of Phase 9 with the most ways
to go quietly wrong, so most of this file is about the paths that must *not*
work: a decision about a plan that no longer exists, a decision about a proposal
that was never offered, a batch where one entry is bad, an approval that expects
to outrank the integrity firewall.

Everything here is atomic. There is no half-approved review and no
partially-applied document, because a document in a state nobody authorised and
no record describes is worse than one that was left alone.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from plainspeak.document import parse_markdown
from plainspeak.pipeline.audit import approval_to_json, style_plan_digest, style_result_to_json
from plainspeak.pipeline.style_plan import (
    STATUS_APPLIED,
    STATUS_APPROVED,
    STATUS_REVIEW_REQUIRED,
    plan_style_changes,
)
from plainspeak.pipeline.style_review import (
    ACCEPT,
    REJECT,
    ApprovedStylePlan,
    ReviewDecision,
    ReviewError,
    ReviewSubmission,
    StyleApplicationError,
    accept_all,
    apply_style_changes,
    approve_style_changes,
    current_identity,
    decide,
)
from plainspeak.pipeline.styling import observe_style
from plainspeak.style import policy, profile_ids

FIXTURES = Path(__file__).resolve().parent / "style" / "stylefix"

#: Pinned so Windows, Linux and macOS all assert the same values rather than
#: each comparing itself to itself. Everything downstream of a proposal — its
#: identifier, the plan it belongs to, the approval, the finished document — is
#: derived from content and must be identical everywhere.
PINNED = {
    "concessive-heavy": {
        "profile": "natural",
        "proposal_ids": [
            "SP-b4e361bc7d682ebb",
            "SP-9b5cb53f11ce23e2",
            "SP-5de1cbe21aedf1ea",
            "SP-0cf6c1273b06490c",
        ],
        "plan_hash": "700d00d88f1234863aeea33811846890d61ff124e95aacafac2722eb1d0991bd",
        "plan_digest": "7cf722ccbfdcd3ac6cc6214506136d50e924a7f27f2827e57600ab2f2843b649",
        "approved_digest": "5e0be9f0fc91e9882c97475dab9a279ea9e2eddf9f3e5dc74f6d941cdf12af50",
        "result_digest": "0091e3a988de24fba78d6b1d51810d0f16c4e9f9e789217589cf4f268c8cb74a",
        "output_hash": "2c941db92783c38f2113bd7311fe32b64c3812b732aad578f969e3d5c762f191",
    },
    "signposted": {
        "profile": "plain",
        "proposal_ids": ["SP-d7e2921c0024cf0b"],
        "plan_hash": "480b408107659d5b4af8298567ab341a5935fd9ba89ff3f8230c75efeb32335f",
        "plan_digest": "609ad61e04bcc2d719cf9718165b00ce498ce56ddb7e67092927b47de338f86f",
        "approved_digest": "490febe9e6d1bf7f8f28bb6a4d0c2ace051e6a4f0c49ded84499606e406e16df",
        "result_digest": "950dd7a743ef7e007aaecfde5cad451f8a7c379e55f456bb4bf1edddd12a611c",
        "output_hash": "bcddb6d030aba7d37452f8591b0b585e1989da2a82a87b52ba15c9e43b16e807",
    },
}


def fixture(name: str):
    return parse_markdown.parse((FIXTURES / f"{name}.md").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plan():
    return plan_style_changes(fixture("concessive-heavy"), "natural")


@pytest.fixture(scope="module")
def doc():
    return fixture("concessive-heavy")


# ── Nothing applies without a decision ─────────────────────────────────────


def test_a_plan_alone_changes_nothing(plan, doc) -> None:
    """The default is inaction, and it is the only default."""
    assert plan.review_required
    assert doc.source == fixture("concessive-heavy").source


def test_applying_an_empty_approval_changes_nothing(plan, doc) -> None:
    approval = approve_style_changes(plan, ReviewSubmission(plan.plan_hash, ()))
    result = apply_style_changes(doc, approval)

    assert approval.approved == ()
    assert not result.changed
    assert result.output == doc.source


def test_rejecting_everything_changes_nothing(plan, doc) -> None:
    submission = ReviewSubmission(
        plan.plan_hash,
        tuple(ReviewDecision(item.proposal_id, REJECT) for item in plan.review_required),
    )
    result = apply_style_changes(doc, approve_style_changes(plan, submission))

    assert not result.changed
    assert len(approve_style_changes(plan, submission).rejected) == len(plan.review_required)


# ── Approval ───────────────────────────────────────────────────────────────


def test_accepting_one_proposal_approves_exactly_that_one(plan, doc) -> None:
    chosen = plan.review_required[0]
    approval = approve_style_changes(plan, decide(plan, **{chosen.proposal_id: ACCEPT}))

    assert [item.proposal_id for item in approval.approved] == [chosen.proposal_id]
    assert approval.approved[0].status == STATUS_APPROVED

    result = apply_style_changes(doc, approval)
    assert result.changed
    assert result.output.count("Even so,") == 1
    assert result.output.count("Nevertheless,") == 5


def test_a_mixed_batch_is_honoured_exactly(plan, doc) -> None:
    first, second = plan.review_required[0], plan.review_required[1]
    approval = approve_style_changes(
        plan, decide(plan, **{first.proposal_id: ACCEPT, second.proposal_id: REJECT})
    )

    assert [item.proposal_id for item in approval.approved] == [first.proposal_id]
    assert approval.rejected == (second.proposal_id,)


def test_an_approved_proposal_reports_its_state(plan) -> None:
    approval = approve_style_changes(plan, accept_all(plan))
    assert all(item.status == STATUS_APPROVED for item in approval.approved)

    result = apply_style_changes(fixture("concessive-heavy"), approval)
    assert all(item.status == STATUS_APPLIED for item in result.applied)


# ── Refusals ───────────────────────────────────────────────────────────────


def test_a_decision_naming_the_wrong_plan_is_refused(plan) -> None:
    with pytest.raises(ReviewError, match="different plan"):
        approve_style_changes(plan, ReviewSubmission("0" * 64, ()))


def test_an_unknown_proposal_is_refused(plan) -> None:
    with pytest.raises(ReviewError, match="does not contain"):
        approve_style_changes(plan, decide(plan, **{"SP-doesnotexist": ACCEPT}))


def test_an_unknown_decision_verb_is_refused(plan) -> None:
    chosen = plan.review_required[0].proposal_id
    with pytest.raises(ReviewError, match="accept"):
        approve_style_changes(plan, decide(plan, **{chosen: "maybe"}))


def test_contradictory_decisions_are_refused(plan) -> None:
    """Two answers for one proposal is not a preference to be resolved."""
    chosen = plan.review_required[0].proposal_id
    submission = ReviewSubmission(
        plan.plan_hash,
        (ReviewDecision(chosen, ACCEPT), ReviewDecision(chosen, REJECT)),
    )
    with pytest.raises(ReviewError, match="two decisions for the same proposal"):
        approve_style_changes(plan, submission)


def test_a_decision_about_a_refused_proposal_is_refused(plan) -> None:
    """Only what was actually offered for review may be decided."""
    doc = fixture("signposted")
    heavy = plan_style_changes(doc, "natural")
    assert heavy.proposals == ()

    faked = replace(plan.review_required[0], status="refused", refusal="integrity")
    altered = replace(plan, proposals=(faked,) + plan.proposals[1:])
    with pytest.raises(ReviewError, match="not awaiting review"):
        approve_style_changes(
            altered,
            ReviewSubmission(
                altered.plan_hash, (ReviewDecision(faked.proposal_id, ACCEPT),)
            ),
        )


def test_a_batch_fails_atomically(plan) -> None:
    """One bad entry refuses the lot, and nothing partial survives.

    A reviewer who sent five decisions and got three applied would have no way
    to know which two, and the document would be in a state their review does
    not describe.
    """
    good = plan.review_required[0].proposal_id
    submission = ReviewSubmission(
        plan.plan_hash,
        (
            ReviewDecision(good, ACCEPT),
            ReviewDecision("SP-notreal", ACCEPT),
            ReviewDecision(plan.review_required[1].proposal_id, REJECT),
        ),
    )
    with pytest.raises(ReviewError):
        approve_style_changes(plan, submission)

    # And the good decision was not quietly kept.
    approval = approve_style_changes(plan, decide(plan, **{good: ACCEPT}))
    assert len(approval.approved) == 1


# ── Freshness ──────────────────────────────────────────────────────────────


def test_a_decision_is_bound_to_every_authority(plan) -> None:
    """Not merely to the document.

    Approving "replace this Nevertheless" under the natural profile does not
    authorise the same edit after somebody adjusts a threshold, because the thing
    that was approved no longer exists.
    """
    identity = plan.identity()
    for key in (
        "input_sha256",
        "integrity_policy_sha256",
        "morphology_sha256",
        "profile_pack_sha256",
        "profile_sha256",
        "ruleset_sha256",
        "style_policy_sha256",
    ):
        assert key in identity and identity[key]


@pytest.mark.parametrize(
    "key",
    [
        "ruleset_sha256",
        "integrity_policy_sha256",
        "style_policy_sha256",
        "profile_pack_sha256",
        "profile_sha256",
        "morphology_sha256",
    ],
)
def test_a_stale_authority_refuses_the_decision(plan, monkeypatch, key: str) -> None:
    """Every bound authority, checked one at a time."""
    from plainspeak.pipeline import style_review

    real = style_review.current_identity

    def drifted(target):
        return {**real(target), key: "0" * 64}

    monkeypatch.setattr(style_review, "current_identity", drifted)
    with pytest.raises(ReviewError, match="an authority has changed"):
        approve_style_changes(plan, accept_all(plan))


def test_the_plan_hash_moves_when_the_profile_does() -> None:
    """A decision cannot be replayed against a different reading."""
    doc = fixture("concessive-heavy")
    hashes = {name: plan_style_changes(doc, name).plan_hash for name in profile_ids()}
    assert len(set(hashes.values())) == len(hashes)


def test_proposal_ids_are_scoped_to_the_profile() -> None:
    doc = fixture("concessive-heavy")
    natural = {p.proposal_id for p in plan_style_changes(doc, "natural").review_required}
    plain = {p.proposal_id for p in plan_style_changes(doc, "plain").review_required}
    assert natural and plain
    assert not natural & plain


# ── Application ────────────────────────────────────────────────────────────


def test_applying_to_a_different_document_is_refused(plan) -> None:
    approval = approve_style_changes(plan, accept_all(plan))
    with pytest.raises(StyleApplicationError, match="different document"):
        apply_style_changes(fixture("signposted"), approval)


def test_applying_to_a_changed_document_is_refused(plan) -> None:
    """The plan names the document by hash; a changed one is a different one."""
    approval = approve_style_changes(plan, accept_all(plan))
    original = fixture("concessive-heavy")
    edited = parse_markdown.parse(original.source.replace("Nevertheless,", "However,", 1))
    with pytest.raises(StyleApplicationError, match="different document"):
        apply_style_changes(edited, approval)


def test_overlapping_approvals_are_refused(plan, doc) -> None:
    approval = approve_style_changes(plan, accept_all(plan))
    duplicated = replace(
        approval, approved=approval.approved + (approval.approved[0],)
    )
    with pytest.raises(StyleApplicationError, match="same characters"):
        apply_style_changes(doc, duplicated)


def test_the_original_document_is_never_mutated(plan, doc) -> None:
    before = doc.source
    apply_style_changes(doc, approve_style_changes(plan, accept_all(plan)))
    assert doc.source == before


# ── Integrity is not negotiable ────────────────────────────────────────────


def test_approval_does_not_bypass_the_firewall(plan, doc, monkeypatch) -> None:
    """A person saying yes changes whether a change is wanted, not whether it is safe.

    The whole-document check runs after approval, and there is no flag,
    parameter or configuration by which it can be skipped.
    """
    from plainspeak.pipeline import style_review

    class Verdict:
        passed = False
        summary = "a measurement was altered"

    monkeypatch.setattr(style_review, "integrity_check", lambda before, after: Verdict())
    approval = approve_style_changes(plan, accept_all(plan))
    with pytest.raises(StyleApplicationError, match="protected information"):
        apply_style_changes(doc, approval)


def test_there_is_no_integrity_override_anywhere() -> None:
    """Checked over the source, because the failure would be a helpful flag."""
    import ast

    root = Path(__file__).resolve().parent.parent / "plainspeak"
    forbidden = ("ignore_integrity", "skip_integrity", "bypass_integrity", "unsafe")
    offences = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [arg.arg for arg in node.args.args + node.args.kwonlyargs]
                for name in names:
                    if any(word in name.lower() for word in forbidden):
                        offences.append(f"{path.name}:{node.lineno} takes `{name}`")
    assert not offences, "; ".join(offences)


def test_the_firewall_runs_on_the_whole_document_not_each_change(plan, doc) -> None:
    """Two individually harmless edits can combine; the preflight cannot see that."""
    import inspect

    from plainspeak.pipeline import style_review

    source = inspect.getsource(style_review.apply_style_changes)
    assert "integrity_check(document.source, output)" in source


# ── Determinism ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(PINNED))
def test_the_whole_pipeline_has_its_expected_identity(name: str) -> None:
    """Proposal IDs, plan hash, approval and output, pinned cross-platform.

    Everything here is derived from content: the rule, the span, the text, the
    profile. No clock, no counter, no iteration order — so a review decision
    stored on one machine means the same thing on another.
    """
    expected = PINNED[name]
    doc = fixture(name)
    plan = plan_style_changes(doc, expected["profile"])

    assert [item.proposal_id for item in plan.review_required] == expected["proposal_ids"]
    assert plan.plan_hash == expected["plan_hash"]
    assert style_plan_digest(plan) == expected["plan_digest"]

    approval = approve_style_changes(plan, accept_all(plan))
    assert approval.digest == expected["approved_digest"]

    result = apply_style_changes(doc, approval)
    assert result.digest == expected["result_digest"]
    assert result.output_hash == expected["output_hash"]


@pytest.mark.parametrize("name", sorted(PINNED))
def test_repeated_runs_agree(name: str) -> None:
    doc = fixture(name)
    profile = PINNED[name]["profile"]
    first, second = plan_style_changes(doc, profile), plan_style_changes(doc, profile)
    assert first.plan_hash == second.plan_hash
    assert [p.proposal_id for p in first.proposals] == [p.proposal_id for p in second.proposals]


def test_proposals_are_in_source_order(plan) -> None:
    starts = [item.source_span.start for item in plan.proposals]
    assert starts == sorted(starts)


def test_line_endings_do_not_change_which_proposals_appear() -> None:
    source = (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8")
    lf = plan_style_changes(parse_markdown.parse(source), "natural")
    crlf = plan_style_changes(parse_markdown.parse(source.replace("\n", "\r\n")), "natural")

    assert [p.rule_id for p in lf.proposals] == [p.rule_id for p in crlf.proposals]
    assert [p.before for p in lf.proposals] == [p.before for p in crlf.proposals]


# ── Idempotence ────────────────────────────────────────────────────────────


def test_the_same_proposal_is_not_offered_twice(plan, doc) -> None:
    """Applied changes do not come back.

    Where a document is still above the line, new proposals for *other*
    occurrences are legitimate. The same proposal — same rule, same span, same
    text — is not.
    """
    before = {item.proposal_id for item in plan.review_required}
    result = apply_style_changes(doc, approve_style_changes(plan, accept_all(plan)))

    again = plan_style_changes(parse_markdown.parse(result.output), "natural")
    assert not before & {item.proposal_id for item in again.review_required}


def test_a_partly_reviewed_document_may_still_have_work() -> None:
    """Accepting one of four leaves the finding standing, and more to offer."""
    doc = fixture("concessive-heavy")
    plan = plan_style_changes(doc, "natural")
    one = plan.review_required[0]

    result = apply_style_changes(
        doc, approve_style_changes(plan, decide(plan, **{one.proposal_id: ACCEPT}))
    )
    again = plan_style_changes(parse_markdown.parse(result.output), "natural")

    assert again.review_required, "the document is still above the line"
    assert one.proposal_id not in {item.proposal_id for item in again.review_required}


# ── Audit ──────────────────────────────────────────────────────────────────


def test_the_audit_distinguishes_every_state(plan, doc) -> None:
    """`review_required`, `approved` and `applied` are separate and stay separate."""
    record = json.loads(json.dumps(json.loads(
        __import__("plainspeak.pipeline.audit", fromlist=["x"]).style_plan_to_json(plan)
    )))
    assert {item["status"] for item in record["proposals"]} == {STATUS_REVIEW_REQUIRED}

    approval = approve_style_changes(plan, accept_all(plan))
    approved = json.loads(approval_to_json(approval))
    assert {item["status"] for item in approved["approved"]} == {STATUS_APPROVED}

    result = apply_style_changes(doc, approval)
    applied = json.loads(style_result_to_json(result))
    assert {item["status"] for item in applied["applied"]} == {STATUS_APPLIED}


def test_the_audit_carries_no_timestamp(plan) -> None:
    import re

    from plainspeak.pipeline.audit import style_plan_to_json

    rendered = style_plan_to_json(plan)
    assert not re.search(r"\d{4}-\d{2}-\d{2}", rendered)
    for key in ("timestamp", "generated", "date", "time"):
        assert key not in rendered.lower()


def test_the_audit_shows_what_a_review_interface_needs(plan) -> None:
    """The Phase 10 contract, asserted so it does not have to be reverse-engineered."""
    from plainspeak.pipeline.audit import style_plan_to_json

    entry = json.loads(style_plan_to_json(plan))["proposals"][0]
    for key in (
        "before", "after", "rule_id", "profile", "reason", "trigger",
        "trigger_severity", "integrity_checked", "status", "proposal_id",
    ):
        assert key in entry, key


# ── Performance ────────────────────────────────────────────────────────────


def test_planning_measures_and_interprets_once(monkeypatch) -> None:
    """Not once per style rule, and not once per proposal.

    Asserted by counting calls rather than by timing, so it fails for exactly one
    reason and cannot go flaky on a loaded runner.
    """
    import sys

    analyze_module = sys.modules["plainspeak.style.analyze"]
    counts = {"measure": 0, "interpret": 0}

    original_measure = analyze_module.measure

    def counted_measure(text, structure):
        counts["measure"] += 1
        return original_measure(text, structure)

    monkeypatch.setattr(analyze_module, "measure", counted_measure)

    from plainspeak.pipeline import style_plan as module

    original_interpret = module.interpret_prose

    def counted_interpret(observed, profile):
        counts["interpret"] += 1
        return original_interpret(observed, profile)

    monkeypatch.setattr(module, "interpret_prose", counted_interpret)

    plan_style_changes(fixture("concessive-heavy"), "natural")

    assert counts["measure"] == 1, f"measured {counts['measure']} times"
    assert counts["interpret"] == 1, f"interpreted {counts['interpret']} times"


def test_an_existing_observation_is_reused(monkeypatch) -> None:
    """A caller comparing profiles measures once for all of them."""
    import sys

    from plainspeak.pipeline.planner import build_plan
    from plainspeak.pipeline.projection import project_document

    doc = fixture("concessive-heavy")
    view = project_document(doc)
    observed = observe_style(doc, view)
    safe = build_plan(doc, None, view)

    analyze_module = sys.modules["plainspeak.style.analyze"]
    calls = {"n": 0}
    original = analyze_module.measure

    def counted(text, structure):
        calls["n"] += 1
        return original(text, structure)

    monkeypatch.setattr(analyze_module, "measure", counted)

    for name in profile_ids():
        plan_style_changes(doc, name, projection=view, observed=observed, safe_plan=safe)

    assert calls["n"] == 0, f"re-measured {calls['n']} times despite being given the observation"
