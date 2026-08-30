"""Style-fix rules, and the profile gate that decides when one may speak.

The claim Phase 9 makes is narrow: a style transformation is a preference
relative to a chosen profile, it exists only when the style layer has already
said the pattern is undesirable *for that profile*, and it never becomes an edit
without a person. Each of those is checked here from both sides — the case where
a proposal should appear and the case where it must not.

The gate is the interesting half. A rule that could decide for itself that a
document is repetitive would be a second style detector hiding inside the
transformation engine, free to disagree with the first, and several tests below
exist only to make that impossible to reintroduce quietly.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plainspeak.document import parse_markdown
from plainspeak.pipeline.audit import style_plan_digest, style_plan_to_json
from plainspeak.pipeline.planner import build_plan
from plainspeak.pipeline.apply import apply_plan
from plainspeak.pipeline.style_plan import (
    MAX_PROPOSALS_PER_DIAGNOSTIC,
    STATUS_REFUSED,
    STATUS_REVIEW_REQUIRED,
    StylePlan,
    StylePlanError,
    plan_style_changes,
)
from plainspeak.pipeline.styling import compare_style_profiles, observe_style
from plainspeak.rules import load_ruleset
from plainspeak.rules.schema import AUTOMATIC_MODES, MODE_STYLE_FIX
from plainspeak.style import policy, profile_ids
from plainspeak.style.profiles import ProfileError

FIXTURES = Path(__file__).resolve().parent / "style" / "stylefix"
CORPUS = Path(__file__).resolve().parent / "style" / "corpus"
PROFILES = Path(__file__).resolve().parent / "style" / "profiles"

ALL = tuple(profile_ids())


def document(path: Path):
    return parse_markdown.parse(path.read_text(encoding="utf-8"))


def fixture(name: str):
    return document(FIXTURES / f"{name}.md")


# ── The shipped rules ──────────────────────────────────────────────────────


def test_style_fixes_exist_and_are_bounded() -> None:
    """A small defensible set. The brief suggests 5–15; eight are shipped."""
    style_fixes = load_ruleset().style_fixes
    assert 5 <= len(style_fixes) <= 15


def test_every_style_fix_declares_its_whole_contract() -> None:
    for rule in load_ruleset().style_fixes:
        assert rule.id.startswith("PS.STYLEFIX."), rule.id
        assert rule.version >= 1
        assert rule.match.type == "phrase" and rule.match.text
        assert rule.action.type == "replace" and rule.action.replacement
        assert rule.reason
        assert rule.provenance.source
        assert rule.priority >= 0
        assert rule.trigger is not None
        assert rule.trigger.diagnostic in policy.DIAGNOSTIC_IDS
        assert rule.trigger.evidence_label
        assert rule.review is not None and rule.review.required is True
        assert rule.examples.positive and rule.examples.negative
        assert rule.examples.transform, "a change with no written expected output"


def test_style_fix_ids_are_a_separate_namespace_from_diagnostics() -> None:
    """One observes, the other proposes. Never the same identity."""
    for rule in load_ruleset().style_fixes:
        assert rule.id not in policy.DIAGNOSTIC_IDS
        assert not rule.id.startswith("PS.STYLE."), rule.id
        assert rule.trigger.diagnostic.startswith("PS.STYLE.")


def test_no_style_fix_duplicates_an_existing_safe_fix() -> None:
    """The finding that removed half the first draft of this family.

    "furthermore", "moreover", "additionally" and "consequently" all already
    have Phase 6 safe-fix rules — PS.LEXICAL.161, .183, .103 and .122 — that
    replace them automatically. Style rules for the same surfaces were written,
    were superseded by mode precedence on every document, and could never have
    produced a single review item. They were deleted rather than shipped.

    This test is what stops them coming back.
    """
    ruleset = load_ruleset()
    automatic = {
        literal.strip().lower()
        for rule in ruleset.safe_fixes
        for literal in rule.match.literals
        if literal
    }
    clashes = [
        (rule.id, rule.match.text)
        for rule in ruleset.style_fixes
        if rule.match.text.strip().strip(",").lower() in automatic
    ]
    assert not clashes, (
        f"these style fixes duplicate an existing safe fix and would be superseded "
        f"on every document: {clashes}"
    )


def test_replacements_stay_in_the_same_discourse_class() -> None:
    """No register changes, checked against the words that would signal one."""
    banned = {"but", "so", "and", "yet", "though"}
    for rule in load_ruleset().style_fixes:
        first = rule.action.replacement.strip().strip(",").split()[0].lower()
        assert first not in banned, (
            f"{rule.id} replaces with {rule.action.replacement!r}, which shifts register"
        )


def test_no_style_fix_is_automatic() -> None:
    assert MODE_STYLE_FIX not in AUTOMATIC_MODES
    for rule in load_ruleset().style_fixes:
        assert not rule.is_automatic


# ── The profile gate ───────────────────────────────────────────────────────


def test_a_profile_is_mandatory() -> None:
    """No default, and no silent fall back to the Phase 7 baseline.

    The baseline measures. It represents nobody's intent, and it carries three
    known sealed false positives, so authorising an edit from it would mean
    changing a document because of a threshold this project already knows to be
    wrong.
    """
    with pytest.raises(StylePlanError, match="requires an explicit profile"):
        plan_style_changes(fixture("concessive-heavy"), None)


def test_an_unknown_profile_fails_explicitly() -> None:
    with pytest.raises(ProfileError, match="natrual"):
        plan_style_changes(fixture("concessive-heavy"), "natrual")


def test_a_quiet_diagnostic_produces_no_proposals() -> None:
    """`signposted.md` is below the natural profile's density line."""
    plan = plan_style_changes(fixture("signposted"), "natural")
    assert plan.review_required == ()
    assert plan.proposals == ()


def test_a_firing_diagnostic_produces_proposals() -> None:
    plan = plan_style_changes(fixture("signposted"), "plain")
    assert plan.review_required
    assert all(p.trigger_diagnostic == policy.TRANSITION_DENSITY for p in plan.review_required)


def test_a_rule_only_acts_on_a_finding_that_names_its_label() -> None:
    """A rule for "nevertheless" says nothing about a finding about "in addition".

    Without this the rule would be forming its own opinion about whether the
    document is repetitive, which is the style layer's job and not a rule's.
    """
    plan = plan_style_changes(fixture("concessive-heavy"), "natural")
    finding = next(f for f in plan.findings if f["id"] == policy.REPEATED_TRANSITION)
    assert finding["severity"]
    for proposal in plan.proposals:
        assert proposal.evidence_label == "nevertheless"


def test_style_rules_do_not_recompute_the_document_condition() -> None:
    """Structural, not behavioural: the planner reads the finding.

    A style rule declares a phrase and a replacement and nothing else. It has no
    threshold, no minimum sample and no measurement of its own, so there is
    nothing in it that could disagree with the style layer.
    """
    for rule in load_ruleset().style_fixes:
        rendered = json.dumps(
            {
                "match": rule.match.text,
                "action": rule.action.replacement,
                "trigger": rule.trigger.diagnostic,
            }
        )
        for word in ("threshold", "notice", "strong", "minimum", "count", "ratio"):
            assert word not in rendered.lower()


def test_the_planner_uses_the_style_layers_own_tokeniser() -> None:
    """One connective tokeniser, shared, so there is no second detector."""
    import inspect

    from plainspeak.pipeline import style_plan

    source = inspect.getsource(style_plan)
    assert "from ..style.patterns import transition_hits" in source
    assert "TRANSITIONS" in source and "from ..style.policy import" in source


# ── The cross-profile contrast ─────────────────────────────────────────────


def test_the_same_document_gets_different_proposals_by_profile() -> None:
    """The proof that Phase 8 is actually governing Phase 9.

    `signposted.md` measures 0.2027 transition density. The plain, technical and
    government profiles draw their line at 0.20 and the document crosses it; the
    natural profile draws it at 0.24 and academic at 0.30, and it does not. Same
    prose, same metrics, different reading — and therefore three profiles with a
    review item and two with nothing to review.
    """
    doc = fixture("signposted")
    counts = {name: len(plan_style_changes(doc, name).review_required) for name in ALL}

    assert counts["plain"] >= 1
    assert counts["technical"] >= 1
    assert counts["government"] >= 1
    assert counts["natural"] == 0
    assert counts["academic"] == 0


def test_the_metrics_are_identical_across_that_contrast() -> None:
    """Only the interpretation moved. The measurement did not."""
    doc = fixture("signposted")
    rendered = {
        name: json.dumps(analysis.metrics.as_dict(), sort_keys=True)
        for name, analysis in compare_style_profiles(doc).items()
    }
    assert len(set(rendered.values())) == 1


def test_the_contrast_is_visible_in_the_audit() -> None:
    doc = fixture("signposted")
    quiet = json.loads(style_plan_to_json(plan_style_changes(doc, "natural")))
    loud = json.loads(style_plan_to_json(plan_style_changes(doc, "plain")))

    assert quiet["proposals"] == []
    assert loud["proposals"]
    assert loud["proposals"][0]["profile"] == "plain"
    assert loud["identity"]["profile_id"] == "plain"
    assert quiet["identity"]["profile_id"] == "natural"
    # Same document, same style policy, different profile identity.
    assert quiet["identity"]["input_sha256"] == loud["identity"]["input_sha256"]
    assert quiet["identity"]["style_policy_sha256"] == loud["identity"]["style_policy_sha256"]
    assert quiet["identity"]["profile_sha256"] != loud["identity"]["profile_sha256"]


# ── Surplus selection ──────────────────────────────────────────────────────


def test_the_earliest_occurrences_survive() -> None:
    """Six "Nevertheless"es, four proposals, and the first two are kept.

    The earliest uses established the connective; the later ones are the
    repetition. Source order is a total order over a fixed document, so this is
    deterministic without reference to hashing or iteration order.
    """
    doc = fixture("concessive-heavy")
    plan = plan_style_changes(doc, "natural")
    positions = sorted(p.source_span.start for p in plan.review_required)

    all_positions = []
    start = 0
    while (found := doc.source.find("Nevertheless,", start)) != -1:
        all_positions.append(found)
        start = found + 1

    assert len(all_positions) == 6
    assert positions == all_positions[2:], "the first two occurrences must be left alone"


def test_the_number_proposed_is_the_smallest_that_resolves_the_finding() -> None:
    """Not every occurrence: only enough to bring the document under the line."""
    plan = plan_style_changes(fixture("concessive-heavy"), "natural")
    assert len(plan.review_required) == 4


def test_one_budget_is_shared_across_rules_for_one_finding() -> None:
    """Two rules that could each act do not each propose a full fix.

    `signposted.md` contains both "In addition," and "That said,", and either
    substitution alone brings the density under the plain profile's line. One
    proposal is correct; two would ask a reviewer to approve an edit that was
    not needed.
    """
    plan = plan_style_changes(fixture("signposted"), "plain")
    assert len(plan.review_required) == 1


def test_proposals_are_capped_and_the_cap_is_disclosed() -> None:
    """A long document must not become a queue, and nothing is hidden."""
    source = (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8")
    plan = plan_style_changes(parse_markdown.parse("\n\n".join([source] * 12)), "natural")

    for diagnostic in {p.trigger_diagnostic for p in plan.proposals}:
        produced = sum(1 for p in plan.proposals if p.trigger_diagnostic == diagnostic)
        assert produced <= MAX_PROPOSALS_PER_DIAGNOSTIC

    if plan.truncated:
        assert all(count > 0 for count in plan.truncated.values())
        assert "truncated" in json.loads(style_plan_to_json(plan))


# ── Nothing enters the accepted set ────────────────────────────────────────


def test_a_style_plan_has_no_accepted_set() -> None:
    """The guarantee expressed as a missing attribute.

    There is nowhere in a `StylePlan` to put an automatically applicable style
    change, so no amount of planner logic can produce one.
    """
    assert "accepted" not in StylePlan.__dataclass_fields__
    assert not hasattr(plan_style_changes(fixture("concessive-heavy"), "natural"), "accepted")


def test_every_live_proposal_is_review_required() -> None:
    for name in ALL:
        for fixture_name in ("concessive-heavy", "signposted"):
            plan = plan_style_changes(fixture(fixture_name), name)
            for proposal in plan.proposals:
                assert proposal.status in (STATUS_REVIEW_REQUIRED, STATUS_REFUSED)


def test_the_transformation_planner_ignores_style_fixes_entirely() -> None:
    """`build_plan` and `apply_plan` cannot reach a style rule.

    A style-fix match is not proposed, not accepted, not refused and not recorded
    as a diagnostic by the transformation planner. It simply is not that
    planner's business, and `apply_plan` therefore has nothing to apply.
    """
    doc = fixture("concessive-heavy")
    plan = build_plan(doc)

    everything = plan.proposals + plan.accepted + plan.refused + plan.diagnostics
    assert not [c for c in everything if c.rule_id.startswith("PS.STYLEFIX.")]

    result = apply_plan(doc, plan)
    assert not [c for c in result.applied if c.rule_id.startswith("PS.STYLEFIX.")]


def test_review_required_is_not_a_refusal() -> None:
    """A valid suggestion awaiting judgement is a distinct state.

    Representing it as a refusal — or as `applicable = false` — would tell a
    review interface that the engine had rejected something it had not, and the
    difference is the whole point of the mode.
    """
    plan = plan_style_changes(fixture("concessive-heavy"), "natural")
    for proposal in plan.review_required:
        assert proposal.status == STATUS_REVIEW_REQUIRED
        assert proposal.refusal == ""
        assert proposal.integrity_checked
        assert proposal.before and proposal.after


# ── Effectiveness ──────────────────────────────────────────────────────────


def measure(doc, profile: str, diagnostic: str):
    analysis = compare_style_profiles(doc)[profile]
    return next((f.value for f in analysis.findings if f.id == diagnostic), None)


@pytest.mark.parametrize(
    "name,profile,diagnostic",
    [
        ("concessive-heavy", "natural", policy.REPEATED_TRANSITION),
        ("signposted", "plain", policy.TRANSITION_DENSITY),
    ],
)
def test_applying_the_proposals_does_not_worsen_the_targeted_metric(
    name: str, profile: str, diagnostic: str
) -> None:
    """The condition that justified the change must not get worse because of it.

    Measured against the triggering diagnostic only. There is no aggregate style
    score to optimise, and inventing one to report an improvement against would
    be the exact failure Phase 7 refused.
    """
    from plainspeak.pipeline.style_review import (
        accept_all,
        apply_style_changes,
        approve_style_changes,
    )

    doc = fixture(name)
    plan = plan_style_changes(doc, profile)
    assert plan.review_required

    observed = observe_style(doc).by_id()[diagnostic].value
    result = apply_style_changes(doc, approve_style_changes(plan, accept_all(plan)))
    after_doc = parse_markdown.parse(result.output)
    after = observe_style(after_doc).by_id().get(diagnostic)
    after_value = after.value if after is not None else 0.0

    assert after_value <= observed, (
        f"{name}: {diagnostic} went from {observed} to {after_value}"
    )
    assert measure(after_doc, profile, diagnostic) is None, (
        "the finding that justified the change should be resolved by it"
    )


def test_the_no_worse_guard_holds_when_it_can_bite() -> None:
    """The guard against a substitution that moves the problem rather than fixing it.

    Worth being precise about: this guard cannot fire on a real document today.
    A budget is only computed for a finding that fired, so the profile's line is
    at or below the current value; both measures fall monotonically as more
    occurrences change; so anything below the line is already an improvement.

    It is exercised here directly, with a line above the starting value — the
    shape a non-monotonic measure would produce — rather than by a fixture
    pretending to be a document that cannot exist.
    """
    from collections import Counter

    from plainspeak.pipeline.style_plan import _concentration, _smallest_k

    # Replacing "nevertheless" with a connective that is already level with it:
    # every substitution hands the lead to "however", so every k leaves the
    # concentration higher than it started and none is accepted — even with the
    # line set generously enough that the value would otherwise qualify.
    level = Counter({"nevertheless": 6, "however": 6})
    assert _smallest_k(level, "nevertheless", "however", 0.99, _concentration) == 0

    # The ordinary case, where the replacement is not itself counted, resolves:
    # 8 of 10 is 0.8, and changing four leaves 4 of 6, which is 0.667.
    ordinary = Counter({"nevertheless": 8, "however": 2})
    assert _smallest_k(ordinary, "nevertheless", "", 0.70, _concentration) == 4


def test_a_counted_replacement_cannot_reduce_density() -> None:
    """Swapping one discourse marker for another leaves the density identical.

    A density rule whose replacement is itself counted would propose changes
    that could not possibly resolve the finding, so such a rule takes no budget
    at all.
    """
    from plainspeak.pipeline.style_plan import _counted

    for rule in load_ruleset().style_fixes:
        if rule.trigger.diagnostic == policy.TRANSITION_DENSITY:
            assert not _counted(rule.action.replacement), (
                f"{rule.id} replaces a connective with another connective, which "
                f"cannot move the density it is triggered by"
            )


def test_an_unresolvable_finding_produces_a_diagnostic_and_no_proposals() -> None:
    """Where the arithmetic cannot be settled, the brief calls for silence."""
    source = "However, one. However, two. However, three. However, four.\n"
    plan = plan_style_changes(parse_markdown.parse(source), "natural")
    assert plan.review_required == ()


# ── The calibration corpora ────────────────────────────────────────────────


def corpus_documents() -> list[Path]:
    return sorted(
        [p for p in CORPUS.glob("*.md") if p.stem != "README"] + list(PROFILES.rglob("*.md"))
    )


@pytest.mark.parametrize(
    "path", corpus_documents(), ids=lambda p: f"{p.parent.name}/{p.stem}"
)
def test_documents_quiet_under_their_own_profile_get_no_style_proposals(path: Path) -> None:
    """Phase 8 established these are quiet. Phase 9 must not make them noisy.

    Every profile-corpus document is checked under the profile it was written
    for. A style proposal on a document the style layer considers well-suited to
    its target register would mean the gate had failed open.
    """
    own = path.parent.name if path.parent.name in ALL else None
    if own is None:
        return
    plan = plan_style_changes(document(path), own)
    assert plan.review_required == (), (
        f"{path.name} is quiet under {own} but produced "
        f"{[(p.rule_id, p.before) for p in plan.review_required]}"
    )


def test_proposal_density_across_the_whole_corpus_is_recorded() -> None:
    """A census, so a change in how noisy the engine is cannot pass unnoticed.

    The projection and the observation are built once per document and reused
    across the five profiles — the same measure-once discipline the engine
    follows, applied to the test so it stays affordable to run. The safe plan is
    deliberately *not* pre-built: the planner only needs one when a style
    proposal exists to be outranked, and passing one eagerly here would cost a
    full 222-rule pass per document for documents that produce nothing.
    """
    from plainspeak.pipeline.projection import project_document

    total = {}
    for path in corpus_documents():
        doc = document(path)
        view = project_document(doc)
        observed = observe_style(doc, view)
        for name in ALL:
            plan = plan_style_changes(doc, name, projection=view, observed=observed)
            if plan.review_required:
                total[f"{path.parent.name}/{path.stem}:{name}"] = len(plan.review_required)

    # transition_heavy.md is the only calibration document any profile produces a
    # style proposal for, and every one of those is superseded by the existing
    # safe fix for "furthermore" — so the live count across both corpora is zero.
    assert total == {}, f"unexpected style proposals across the calibration corpora: {total}"
