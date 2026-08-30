"""Profile-governed style transformation planning.

Phase 4 answers *what can be safely rewritten*. Phase 7 answers *what patterns
does this document contain*. Phase 8 answers *how should those patterns be read
for a chosen kind of prose*. This module is where those three meet, and the
whole of its job is to make sure the meeting is one-directional.

A style fix may propose something only when **all** of the following hold:

1. A profile was named explicitly. There is no default and no fallback to the
   Phase 7 baseline — that baseline exists for measurement compatibility, has
   three known sealed false positives, and represents nobody's intent.
2. The style layer, reading the document under that profile, actually produced
   the rule's declared trigger diagnostic.
3. That finding names the rule's declared evidence label.
4. The arithmetic of how many occurrences must change can be settled exactly.
   Where it cannot, the correct answer is a diagnostic and no proposals.

Everything that survives all four is `review_required`. Nothing here can produce
an accepted change, because `StylePlan` has no accepted set to put one in.

### How many, and which

The document says the top transition accounts for six of ten. The profile says
anything at or above 0.70 is a finding. So: how many of the six must become
something else before the document is quiet?

The answer is computed by simulation over the *same* connective tokeniser the
diagnostic used — `style.patterns.transition_hits` — because a planner that
counted transitions its own way would be a second detector, free to disagree
with the first about what a transition is. For each k from 1 upwards, the
distribution that would result from changing k occurrences is built and
measured. The first k that falls under the profile's notice line is the answer.
If no k does, there are no proposals: the relationship could not be settled, and
the brief's instruction for that case is a diagnostic.

Which k occurrences? The **last** k in source order. The earliest uses of a
connective are the ones that established it; the later ones are the repetition.
Source order is a total order over a fixed document, so this is deterministic
without reference to hashing, iteration order or anything a platform could vary.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from ..document.model import Document, Span, content_hash
from ..integrity import check as integrity_check
from ..integrity.policy import POLICY_VERSION as INTEGRITY_POLICY_VERSION
from ..integrity.policy import policy_hash as integrity_policy_hash
from ..rules import Ruleset, load_ruleset
from ..rules.canonical import canonical_json, sha256_text
from ..rules.matcher import find_matches
from ..rules.schema import MODE_STYLE_FIX, Rule
from ..style import STYLE_POLICY_VERSION
from ..style import policy_hash as style_policy_hash
from ..style.model import ProfiledAnalysis, StyleObservations
from ..style.patterns import transition_hits
from ..style.policy import (
    REPEATED_TRANSITION,
    TRANSITION_DENSITY,
    TRANSITIONS,
    TRANSITION_PHRASES,
)
from ..style.profiles import PROFILE_PACK_VERSION, StyleProfile, load_pack, load_profile, pack_hash
from .plan import propose_change
from .planner import (
    ENGINE_VERSION,
    TransformationPlan,
    _in_scope,
    _inherited_protection,
    _protected_regions,
    _SegmentIndex,
    build_plan,
)
from .projection import Projection, project_document
from .styling import observe_style, structure_of
from ..style import interpret as interpret_prose

#: Bumped when the shape of a style plan changes. Separate from the engine
#: version because a review decision is bound to this schema: a decision made
#: against one plan layout must not be replayable against another.
STYLE_PLAN_SCHEMA_VERSION = "1"

#: What a proposal's life can look like. `review_required` is a first-class
#: state and emphatically not a refusal — a valid style suggestion awaiting a
#: person's judgement is a different thing from one the engine rejected, and a
#: review UI that could not tell them apart would be useless.
STATUS_REVIEW_REQUIRED = "review_required"
STATUS_REFUSED = "refused"
STATUS_APPROVED = "approved"
STATUS_APPLIED = "applied"
STATUSES = (STATUS_REVIEW_REQUIRED, STATUS_REFUSED, STATUS_APPROVED, STATUS_APPLIED)

REFUSAL_INTEGRITY = "the change would alter protected information"
REFUSAL_PROTECTED = "the text is covered by a protected term or rule"
REFUSAL_SUPERSEDED_SAFE_FIX = (
    "a safe-fix rule already proposes a change to these characters; a stylistic "
    "preference does not displace a mechanically safe transformation"
)
REFUSAL_SUPERSEDED_STYLE = "another style proposal covers these characters"
REFUSAL_TRUNCATED = "the per-diagnostic proposal cap was reached"

#: An upper bound on how many proposals one diagnostic may produce for one
#: document. Versioned behaviour: it changes what a reviewer is shown, so it is
#: bound into the plan and disclosed whenever it bites. Twenty-five review items
#: from a single diagnostic is already more than anybody will work through
#: carefully, and a ten-thousand-word document should not become a queue.
MAX_PROPOSALS_PER_DIAGNOSTIC = 25

#: Everything the connective tokeniser counts, for deciding whether a
#: replacement is itself a counted transition. Read from the style policy rather
#: than restated, so the two cannot drift.
_COUNTED = frozenset(TRANSITIONS) | frozenset(TRANSITION_PHRASES)


class StylePlanError(ValueError):
    """A style plan could not be built. Never downgraded to an empty plan."""


@dataclass(frozen=True)
class StyleProposal:
    """One profile-relative change, awaiting a person.

    Carries everything a review interface needs without going back to the
    engine: what is there now, what would replace it, which rule proposed it,
    which profile authorised it, which finding justified it, and whether the
    integrity firewall was content. A UI that had to re-derive any of that from
    raw rule matches would be re-implementing this module.
    """

    proposal_id: str
    rule_id: str
    rule_version: int
    mode: str
    status: str
    #: The finding that justified this proposal, and how strongly.
    trigger_diagnostic: str
    trigger_severity: str
    trigger_value: float
    evidence_label: str
    #: The profile that authorised this proposal. Carried on the proposal itself,
    #: not only on the plan, because a review interface renders proposals and a
    #: reader must be able to see which expectations produced each one.
    profile_id: str
    profile_hash: str
    #: Where, in both coordinate systems.
    analysis_span: Span
    source_spans: tuple[Span, ...]
    document_path: tuple[int, ...]
    location: str
    before: str
    after: str
    original_hash: str
    reason: str
    #: Set when `status` is `refused`. Empty otherwise.
    refusal: str = ""
    #: True when the firewall inspected this proposal and was content.
    integrity_checked: bool = True

    @property
    def source_span(self) -> Optional[Span]:
        if not self.source_spans:
            return None
        return Span(self.source_spans[0].start, self.source_spans[-1].end)

    def still_matches(self, document: Document) -> bool:
        span = self.source_span
        if span is None:
            return False
        return content_hash(span.text(document.source)) == self.original_hash

    def identity_payload(self) -> dict[str, Any]:
        """The behaviour-bearing content the proposal ID is derived from."""
        span = self.source_span
        return {
            "after": self.after,
            "before": self.before,
            "evidence_label": self.evidence_label,
            "original_hash": self.original_hash,
            # The profile is part of the identity: the same edit authorised by
            # two different profiles is two different proposals, and a stored
            # decision must not be able to cross between them.
            "profile_hash": self.profile_hash,
            "profile_id": self.profile_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "source_end": span.end if span else -1,
            "source_start": span.start if span else -1,
            "trigger_diagnostic": self.trigger_diagnostic,
        }

    def as_dict(self) -> dict[str, Any]:
        span = self.source_span
        return {
            "after": self.after,
            "before": self.before,
            "evidence_label": self.evidence_label,
            "integrity_checked": self.integrity_checked,
            "location": self.location,
            "mode": self.mode,
            "profile": self.profile_id,
            "proposal_id": self.proposal_id,
            "reason": self.reason,
            "refusal": self.refusal,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "source_end": span.end if span else -1,
            "source_start": span.start if span else -1,
            "status": self.status,
            "trigger": self.trigger_diagnostic,
            "trigger_severity": self.trigger_severity,
            "trigger_value": round(self.trigger_value, 6),
        }


@dataclass(frozen=True)
class StylePlan:
    """Everything one profile-governed style pass decided, frozen.

    Binds every authority that contributed. A review decision references
    `plan_hash`, and `plan_hash` covers all of them, so an approval made when the
    ruleset said one thing cannot be replayed after it says another.

    There is no `accepted` field. That is the guarantee, expressed as a missing
    attribute rather than a rule somebody has to remember: there is nowhere in
    this object to put an automatically applicable style change.
    """

    engine_version: str
    plan_schema_version: str
    ruleset_version: str
    ruleset_hash: str
    integrity_policy_version: str
    integrity_policy_hash: str
    morphology_version: str
    morphology_hash: str
    style_policy_version: str
    style_policy_hash: str
    profile_pack_version: str
    profile_pack_hash: str
    profile_id: str
    profile_version: int
    profile_hash: str
    input_hash: str
    projection_hash: str
    #: Every proposal considered, in deterministic order.
    proposals: tuple[StyleProposal, ...] = ()
    #: Diagnostics that fired under this profile, whether or not any rule could
    #: act on them. A reviewer should be able to see that a document is
    #: repetitive even where nothing in the ruleset knows how to help.
    findings: tuple[dict[str, Any], ...] = ()
    #: Diagnostic ID -> how many proposals the cap dropped. Never hidden.
    truncated: dict[str, int] = field(default_factory=dict)

    @property
    def review_required(self) -> tuple[StyleProposal, ...]:
        return tuple(p for p in self.proposals if p.status == STATUS_REVIEW_REQUIRED)

    @property
    def refused(self) -> tuple[StyleProposal, ...]:
        return tuple(p for p in self.proposals if p.status == STATUS_REFUSED)

    def proposal(self, proposal_id: str) -> Optional[StyleProposal]:
        for item in self.proposals:
            if item.proposal_id == proposal_id:
                return item
        return None

    def is_for(self, document: Document) -> bool:
        return self.input_hash == document.source_hash

    def identity(self) -> dict[str, Any]:
        """Every authority this plan was built under."""
        return {
            "engine_version": self.engine_version,
            "input_sha256": self.input_hash,
            "integrity_policy_sha256": self.integrity_policy_hash,
            "integrity_policy_version": self.integrity_policy_version,
            "morphology_sha256": self.morphology_hash,
            "morphology_version": self.morphology_version,
            "profile_id": self.profile_id,
            "profile_pack_sha256": self.profile_pack_hash,
            "profile_pack_version": self.profile_pack_version,
            "profile_sha256": self.profile_hash,
            "profile_version": self.profile_version,
            "projection_sha256": self.projection_hash,
            "ruleset_sha256": self.ruleset_hash,
            "ruleset_version": self.ruleset_version,
            "style_plan_schema_version": self.plan_schema_version,
            "style_policy_sha256": self.style_policy_hash,
            "style_policy_version": self.style_policy_version,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": list(self.findings),
            "identity": self.identity(),
            "plan_sha256": self.plan_hash,
            "proposals": [item.as_dict() for item in self.proposals],
            "proposal_cap": MAX_PROPOSALS_PER_DIAGNOSTIC,
            "truncated": {key: self.truncated[key] for key in sorted(self.truncated)},
        }

    @property
    def plan_hash(self) -> str:
        """SHA-256 over the identity and every proposal, in order.

        A review decision names this. Change the profile, the ruleset, the
        document or the order of proposals and the hash moves, so a decision made
        against one reading of a document cannot be applied to another.
        """
        return hashlib.sha256(
            canonical_json(
                {
                    "identity": self.identity(),
                    "proposals": [
                        {
                            "proposal_id": item.proposal_id,
                            "status": item.status,
                            **item.identity_payload(),
                        }
                        for item in self.proposals
                    ],
                    "truncated": {key: self.truncated[key] for key in sorted(self.truncated)},
                }
            ).encode("utf-8")
        ).hexdigest()


# ── Planning ───────────────────────────────────────────────────────────────


def plan_style_changes(
    document: Document,
    profile: Any,
    ruleset: Optional[Ruleset] = None,
    projection: Optional[Projection] = None,
    observed: Optional[StyleObservations] = None,
    safe_plan: Optional[TransformationPlan] = None,
) -> StylePlan:
    """Plan profile-relative style changes for one document.

    `profile` is mandatory and has no default. Passing `None` is an error rather
    than a fallback to the baseline: a configuration typo that silently analysed
    a specification against conversational expectations would produce a review
    queue that looked entirely normal and was answering the wrong question.

    `observed`, `projection` and `safe_plan` may be supplied by a caller that
    already has them, so a session comparing profiles measures once.
    """
    if profile is None:
        raise StylePlanError(
            "a style plan requires an explicit profile. The Phase 7 baseline measures "
            "and does not represent anybody's intent, and it carries three known "
            f"sealed false positives; choose one of {list(_profile_ids())}"
        )
    resolved = profile if isinstance(profile, StyleProfile) else load_profile(str(profile))

    rules = ruleset if ruleset is not None else load_ruleset()
    view = projection if projection is not None else project_document(document)
    seen = observed if observed is not None else observe_style(document, view)
    analysis = interpret_prose(seen, resolved)

    style_rules = [rule for rule in rules.rules if rule.mode == MODE_STYLE_FIX]
    by_trigger: dict[str, list[Rule]] = {}
    for rule in style_rules:
        by_trigger.setdefault(rule.trigger.diagnostic, []).append(rule)

    index = _SegmentIndex(view)
    matches = find_matches(view.text, style_rules) if style_rules else []
    in_scope = {rule.id: [] for rule in style_rules}
    lookup = {rule.id: rule for rule in style_rules}
    for match in matches:
        if _in_scope(index, match, lookup[match.rule_id]):
            in_scope[match.rule_id].append(match)

    # Protected regions come from the whole ruleset, not from the style rules:
    # a `protected` rule claims text regardless of who wants to change it.
    # Computed lazily for the same reason the safe plan is — a document with no
    # style matches at all has nothing to protect from.
    _protected_cache: list = []

    def protected_regions():
        if not _protected_cache:
            by_rule_id = {rule.id: rule for rule in rules.rules}
            scoped = [
                m
                for m in find_matches(view.text, rules.rules)
                if _in_scope(index, m, by_rule_id[m.rule_id])
            ]
            _protected_cache.append(_protected_regions(view, document, scoped, by_rule_id))
        return _protected_cache[0]

    hits = transition_hits(view.text)
    proposals: list[StyleProposal] = []
    truncated: dict[str, int] = {}

    for finding in analysis.findings:
        candidates = [
            rule
            for rule in sorted(by_trigger.get(finding.id, []), key=lambda item: item.id)
            # A rule for "furthermore" has nothing to say about a finding naming
            # "however". Without this the rule would be deciding for itself that
            # the document is repetitive, which is the style layer's job.
            if rule.trigger.evidence_label in {item.label for item in finding.evidence}
            and in_scope.get(rule.id)
        ]
        if not candidates:
            continue

        budget = _budget(finding, candidates, hits, resolved)
        if budget <= 0:
            continue

        produced = 0
        for rule in candidates:
            if budget <= 0:
                break
            available = in_scope[rule.id]
            # The last k in source order: the earliest uses established the
            # connective, the later ones are the repetition.
            take = min(budget, len(available))
            chosen = available[-take:]
            room = MAX_PROPOSALS_PER_DIAGNOSTIC - produced
            if len(chosen) > room:
                truncated[finding.id] = truncated.get(finding.id, 0) + (len(chosen) - max(room, 0))
                chosen = chosen[: max(room, 0)]
            for match in chosen:
                built = _build(
                    view, document, match, rule, finding, protected_regions(), resolved
                )
                if built is not None:
                    proposals.append(built)
                    produced += 1
            budget -= take

    proposals = _preflight_integrity(view, index, proposals)
    if proposals:
        # The transformation plan is only needed to learn which characters a
        # safe fix has already claimed, and it costs a full pass over 200-odd
        # rules. Most documents produce no style proposals at all, and there is
        # nothing to settle for a document with none — so it is built only when
        # there is something for it to outrank.
        proposals = _settle_against_safe_fixes(
            document, view, proposals,
            safe_plan if safe_plan is not None else build_plan(document, rules, view),
        )
        proposals = _settle_among_styles(proposals)

    ordered = tuple(sorted(proposals, key=_order))
    pack = load_pack()

    return StylePlan(
        engine_version=ENGINE_VERSION,
        plan_schema_version=STYLE_PLAN_SCHEMA_VERSION,
        ruleset_version=rules.version,
        ruleset_hash=rules.hash,
        integrity_policy_version=INTEGRITY_POLICY_VERSION,
        integrity_policy_hash=integrity_policy_hash(),
        # Read from the ruleset rather than from `morphology` directly. The
        # pipeline reaches morphology through the rule engine and nowhere else,
        # and the ruleset already binds the identity that expanded its lemmas.
        morphology_version=rules.morphology_version,
        morphology_hash=rules.morphology_hash,
        style_policy_version=STYLE_POLICY_VERSION,
        style_policy_hash=style_policy_hash(),
        profile_pack_version=PROFILE_PACK_VERSION,
        profile_pack_hash=pack_hash(pack),
        profile_id=resolved.id,
        profile_version=resolved.version,
        profile_hash=resolved.hash,
        input_hash=document.source_hash,
        projection_hash=sha256_text(view.text),
        proposals=ordered,
        findings=tuple(
            {
                "id": item.id,
                "severity": item.severity,
                "value": round(item.value, 6),
                "threshold": round(item.threshold, 6),
                "sample_size": item.sample_size,
            }
            for item in analysis.findings
        ),
        truncated=dict(sorted(truncated.items())),
    )


def _profile_ids() -> tuple[str, ...]:
    return tuple(item.id for item in load_pack())


# ── How many occurrences must change ───────────────────────────────────────


def _counted(text: str) -> str:
    """The connective key a replacement would be counted as, or ``""``."""
    key = " ".join(text.strip().strip(",.;:").split()).lower()
    return key if key in _COUNTED else ""


def _budget(finding, rules: Sequence[Rule], hits: Sequence[str], profile: StyleProfile) -> int:
    """How many occurrences must change before this document is quiet.

    One budget per *finding*, shared by every rule that can act on it — not one
    per rule. Two rules each independently deciding they need one change would
    propose two where one resolves the measurement, and a reviewer would be
    asked to approve an edit that was not needed.

    Simulated, never estimated. For each k the resulting connective distribution
    is built and measured against the profile's own notice line, and the first k
    that falls below it is the answer.

    Returns 0 when no k works. That is the case the brief calls out: where the
    relationship between the threshold and the number of edits cannot be settled
    cleanly, a diagnostic is the correct result. Proposing a handful of changes
    that would not resolve anything is worse than proposing none.
    """
    band = profile.rule(finding.id)
    if band is None or not band.enabled:
        return 0
    counts = Counter(hits)

    if finding.id == REPEATED_TRANSITION:
        # Concentration is about one connective, so only the rule whose evidence
        # label matches participates and the budget is that rule's alone.
        rule = rules[0]
        target = rule.trigger.evidence_label
        if not counts.get(target):
            return 0
        return _smallest_k(
            counts, target, _counted(rule.action.replacement), band.notice, _concentration
        )

    if finding.id == TRANSITION_DENSITY:
        sentences = finding.sample_size
        if sentences <= 0:
            return 0
        # Density falls only when a counted connective becomes an uncounted one.
        # A rule whose replacement is itself a discourse marker moves the
        # measurement not at all, and must not consume budget.
        effective = [rule for rule in rules if not _counted(rule.action.replacement)]
        if not effective:
            return 0
        total = sum(counts.values())
        for k in range(1, total + 1):
            if (total - k) / sentences < band.notice:
                return k
        return 0

    # A trigger with no arithmetic behind it. The schema restricts triggers to
    # the two above, so reaching here means one was added without its algorithm,
    # and refusing is the safe reading.
    return 0


def _concentration(sim: Counter) -> float:
    total = sum(sim.values())
    if total <= 0:
        return 0.0
    return max(sim.values()) / total


def _smallest_k(
    counts: Counter, target: str, replacement_key: str, notice: float, measure
) -> int:
    """First k whose simulated outcome is below `notice` and no worse than now.

    The second condition is a guard against a substitution that moves the problem
    rather than reducing it — replacing four of six "nevertheless"es can promote a
    different connective to the top of the distribution.

    It is, as things stand, unreachable, and saying so is more useful than
    implying otherwise. A budget is only computed for a finding that fired, so
    `notice <= start`; both measures used here fall monotonically as k rises; and
    `value < notice` therefore already implies `value < start`. It is kept
    because it costs one comparison and because the next measure added here may
    not be monotonic, and a guard that has to be remembered is a guard that will
    not be. `test_the_no_worse_guard_holds_when_it_can_bite` exercises it
    directly rather than pretending a document could.
    """
    start = measure(counts)
    for k in range(1, counts[target] + 1):
        sim = Counter(counts)
        sim[target] -= k
        if sim[target] <= 0:
            del sim[target]
        if replacement_key:
            sim[replacement_key] += k
        value = measure(sim)
        if value < notice and value <= start:
            return k
    return 0


# ── Building and checking one proposal ─────────────────────────────────────


def _build(
    view,
    document,
    match,
    rule: Rule,
    finding,
    protected_regions,
    profile: StyleProfile,
) -> Optional[StyleProposal]:
    """Turn one in-scope match into a proposal, or nothing if it cannot be placed.

    Deliberately built on `propose_change` and the transformation planner's own
    protection helpers rather than on a private copy of either. Protected-term
    authority is a safety property, and the way to be sure a style fix respects
    exactly the same protection a safe fix does is to run exactly the same code —
    not to write a second implementation that agrees today.
    """
    change = propose_change(
        view,
        document,
        Span(match.start, match.end),
        replacement=match.replacement or rule.action.replacement,
        rule_id=rule.id,
        rule_version=rule.version,
        mode=MODE_STYLE_FIX,
    )

    status, refusal = STATUS_REVIEW_REQUIRED, ""
    if match.refusal:
        status, refusal = STATUS_REFUSED, match.refusal
    elif not change.applicable:
        status, refusal = STATUS_REFUSED, change.reason
    else:
        span = change.source_span
        if span is not None and any(span.overlaps(region) for region in protected_regions):
            status, refusal = STATUS_REFUSED, REFUSAL_PROTECTED
        else:
            inherited = _inherited_protection(change.original_text)
            if inherited:
                # A profile disliking repetition does not outrank a protected
                # term of art. For technical and public-service prose especially,
                # the repeated official word is very often the correct one.
                status, refusal = STATUS_REFUSED, inherited

    proposal = StyleProposal(
        proposal_id="",
        rule_id=rule.id,
        rule_version=rule.version,
        mode=MODE_STYLE_FIX,
        status=status,
        trigger_diagnostic=finding.id,
        trigger_severity=finding.severity,
        trigger_value=finding.value,
        evidence_label=rule.trigger.evidence_label,
        profile_id=profile.id,
        profile_hash=profile.hash,
        analysis_span=change.analysis_span,
        source_spans=change.source_spans,
        document_path=change.document_path,
        location=change.location,
        before=change.original_text,
        after=change.replacement,
        original_hash=change.original_hash,
        reason=rule.reason,
        refusal=refusal,
        integrity_checked=False,
    )
    return _with_id(proposal)



def _with_id(proposal: StyleProposal) -> StyleProposal:
    """Attach the deterministic proposal identifier.

    Derived from behaviour-bearing content only: the rule and its version, the
    exact source span, what is there now, what would replace it, and the finding
    that justified it. No clock, no counter, no iteration order — the same
    document under the same profile produces the same identifiers on every
    platform, which is what makes a stored review decision meaningful.
    """
    digest = hashlib.sha256(
        canonical_json(proposal.identity_payload()).encode("utf-8")
    ).hexdigest()
    return _replace(proposal, proposal_id=f"SP-{digest[:16]}")


def _replace(proposal: StyleProposal, **changes) -> StyleProposal:
    from dataclasses import replace as _dc_replace

    return _dc_replace(proposal, **changes)


def _preflight_integrity(view, index, proposals: list[StyleProposal]) -> list[StyleProposal]:
    """Run the firewall over every style proposal before anybody sees it.

    A reviewer should never be shown a change the firewall would refuse. This is
    the same check the transformation planner runs, applied here for the same
    reason, and approving a proposal later does not repeat or replace it — the
    whole-plan check still runs at application.
    """
    checked = []
    for proposal in proposals:
        if proposal.status != STATUS_REVIEW_REQUIRED:
            checked.append(proposal)
            continue
        verdict = integrity_check(proposal.before, proposal.after)
        if verdict.passed:
            checked.append(_replace(proposal, integrity_checked=True))
            continue
        checked.append(
            _replace(
                proposal,
                status=STATUS_REFUSED,
                refusal=REFUSAL_INTEGRITY,
                integrity_checked=True,
            )
        )
    return checked


def _settle_against_safe_fixes(
    document, view, proposals: list[StyleProposal], plan: TransformationPlan
) -> list[StyleProposal]:
    """Mode precedence: protection, then safe fixes, then style preferences.

    A style rule cannot displace a safe fix by declaring a bigger priority
    number, because priority is never consulted across modes. Where the two
    cover the same characters the safe fix wins and the style proposal is
    recorded as superseded with the reason — not silently dropped, because a
    reviewer wondering why a suggestion vanished deserves an answer.
    """
    occupied: list[tuple[int, int, str]] = []
    for change in plan.accepted:
        span = change.source_span
        if span is not None:
            occupied.append((span.start, span.end, change.rule_id))
    for change in plan.diagnostics:
        if change.mode == "protected":
            for span in change.source_spans:
                occupied.append((span.start, span.end, change.rule_id))

    settled = []
    for proposal in proposals:
        if proposal.status != STATUS_REVIEW_REQUIRED:
            settled.append(proposal)
            continue
        span = proposal.source_span
        clash = next(
            (item for item in occupied if span is not None and span.start < item[1] and item[0] < span.end),
            None,
        )
        if clash is None:
            settled.append(proposal)
            continue
        settled.append(
            _replace(proposal, status=STATUS_REFUSED, refusal=REFUSAL_SUPERSEDED_SAFE_FIX)
        )
    return settled


def _settle_among_styles(proposals: list[StyleProposal]) -> list[StyleProposal]:
    """Two style proposals over the same characters: the earlier rule wins.

    Deterministic and total: rule ID, then source position. A loser is refused
    here and stays refused — the Phase 5 rule that a losing candidate never
    returns if the winner later fails holds for style proposals too, because
    one planner pass means one conflict resolution.
    """
    settled: list[StyleProposal] = []
    taken: list[tuple[int, int]] = []
    for proposal in sorted(proposals, key=_order):
        if proposal.status != STATUS_REVIEW_REQUIRED:
            settled.append(proposal)
            continue
        span = proposal.source_span
        if span is None:
            settled.append(_replace(proposal, status=STATUS_REFUSED, refusal=REFUSAL_SUPERSEDED_STYLE))
            continue
        if any(span.start < end and start < span.end for start, end in taken):
            settled.append(_replace(proposal, status=STATUS_REFUSED, refusal=REFUSAL_SUPERSEDED_STYLE))
            continue
        taken.append((span.start, span.end))
        settled.append(proposal)
    return settled


def _order(proposal: StyleProposal) -> tuple:
    span = proposal.source_span
    return (
        span.start if span else -1,
        span.end if span else -1,
        proposal.rule_id,
        proposal.proposal_id,
    )
