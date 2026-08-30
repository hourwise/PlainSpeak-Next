"""Human review of profile-relative style proposals, and applying what survives.

A style fix is a preference. Preferences need a person, and this module is the
only path by which one becomes an edit. The shape is deliberate:

    style proposal
         │
         ▼  integrity preflight (in the planner — a reviewer is never shown a
         │  change the firewall would refuse)
    review_required
         │
         ▼  a person accepts or rejects, in a decision naming the exact plan
    approved
         │
         ▼  freshness: is every authority still what it was?
         │
         ▼  whole-plan integrity revalidation on the finished document
    applied

Two properties are worth stating because they are easy to erode.

**Approval does not outrank integrity.** A person saying yes changes whether a
proposal is wanted, not whether it is safe. The firewall runs again over the
whole finished document before anything is written, and there is no flag,
parameter or configuration by which that can be skipped.

**A decision is bound to one reading of one document.** Not just to the
document: to the ruleset, the integrity policy, the style policy, the profile
pack and the selected profile that produced the plan. Approving "replace this
'Nevertheless'" under the natural profile does not authorise the same edit after
somebody adjusts a threshold, because the thing that was approved no longer
exists.

**Batch decisions are atomic.** One unknown proposal, one contradictory pair,
one stale identity, and the whole submission is refused. Partially applying a
review is how a document ends up in a state nobody approved and no record
describes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any, Iterable, Optional, Sequence

from ..document.model import Document, Span, content_hash
from ..integrity import check as integrity_check
from ..integrity.policy import POLICY_VERSION as INTEGRITY_POLICY_VERSION
from ..integrity.policy import policy_hash as integrity_policy_hash
from ..rules import load_ruleset
from ..rules.canonical import canonical_json, sha256_text
from ..style import STYLE_POLICY_VERSION
from ..style import policy_hash as style_policy_hash
from ..style.profiles import PROFILE_PACK_VERSION, load_pack, load_profile, pack_hash
from .style_plan import (
    STATUS_APPLIED,
    STATUS_APPROVED,
    STATUS_REVIEW_REQUIRED,
    StylePlan,
    StyleProposal,
)

ACCEPT = "accept"
REJECT = "reject"
#: The whole vocabulary. There is deliberately no "edit": a reviewer may take a
#: proposal or leave it, and free-form replacement text would be a new proposal
#: nobody validated, integrity-checked or bound to a plan.
DECISIONS = (ACCEPT, REJECT)

REFUSAL_UNKNOWN_PROPOSAL = "the submission names a proposal this plan does not contain"
REFUSAL_DUPLICATE = "the submission contains two decisions for the same proposal"
REFUSAL_NOT_REVIEWABLE = "the proposal is not awaiting review"
REFUSAL_UNKNOWN_DECISION = "the decision must be 'accept' or 'reject'"
REFUSAL_WRONG_PLAN = "the submission was made against a different plan"
REFUSAL_STALE = "an authority has changed since the plan was built"

ABORT_WRONG_DOCUMENT = "the approval was made against a different document"
ABORT_STALE = "the document has changed since the plan was built"
ABORT_OVERLAP = "two approved changes cover the same characters"
ABORT_INTEGRITY = "the finished document would not preserve protected information"


class ReviewError(ValueError):
    """A review submission was refused. Atomically: nothing was approved."""


class StyleApplicationError(RuntimeError):
    """Approved style changes could not be applied. Nothing was changed."""


@dataclass(frozen=True)
class ReviewDecision:
    """One person's answer about one proposal. Immutable."""

    proposal_id: str
    decision: str

    def as_dict(self) -> dict[str, str]:
        return {"decision": self.decision, "proposal_id": self.proposal_id}


@dataclass(frozen=True)
class ReviewSubmission:
    """A batch of decisions, bound to the exact plan they were made against.

    `plan_hash` is the binding, and it covers every authority the plan was built
    under — the document, the ruleset, the integrity policy, the style policy,
    the profile pack and the selected profile. A submission that still matches
    is a submission about a document nobody has reinterpreted since.
    """

    plan_hash: str
    decisions: tuple[ReviewDecision, ...]

    @property
    def submission_hash(self) -> str:
        return hashlib.sha256(
            canonical_json(
                {
                    "decisions": [item.as_dict() for item in self.decisions],
                    "plan_sha256": self.plan_hash,
                }
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class ApprovedStylePlan:
    """What a person authorised, ready to apply and impossible to widen.

    Holds the proposals themselves rather than their identifiers, so nothing
    between approval and application has to look anything up again — and so a
    change to the plan after approval cannot quietly alter what gets written.
    """

    plan: StylePlan
    approved: tuple[StyleProposal, ...]
    rejected: tuple[str, ...]
    submission_hash: str

    @property
    def plan_hash(self) -> str:
        return self.plan.plan_hash

    def as_dict(self) -> dict[str, Any]:
        return {
            "approved": [item.as_dict() for item in self.approved],
            "identity": self.plan.identity(),
            "plan_sha256": self.plan.plan_hash,
            "rejected": list(self.rejected),
            "submission_sha256": self.submission_hash,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.as_dict()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StyleApplicationResult:
    """The outcome of applying approved style changes."""

    input_source: str
    output: str
    input_hash: str
    output_hash: str
    plan_hash: str
    submission_hash: str
    profile_id: str
    profile_hash: str
    applied: tuple[StyleProposal, ...]

    @property
    def changed(self) -> bool:
        return self.output != self.input_source

    def as_dict(self) -> dict[str, Any]:
        return {
            "applied": [item.as_dict() for item in self.applied],
            "input_sha256": self.input_hash,
            "output_sha256": self.output_hash,
            "plan_sha256": self.plan_hash,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_hash,
            "submission_sha256": self.submission_hash,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.as_dict()).encode("utf-8")).hexdigest()


# ── Approval ───────────────────────────────────────────────────────────────


def current_identity(plan: StylePlan) -> dict[str, Any]:
    """The authorities as they stand *now*, in the plan's own shape.

    Compared against `plan.identity()` to decide freshness. Deriving it from
    live state rather than trusting the plan is the point: a plan is a record of
    what was true, and the question at approval time is whether it still is.
    """
    ruleset = load_ruleset()
    profile = load_profile(plan.profile_id)
    return {
        **plan.identity(),
        "integrity_policy_sha256": integrity_policy_hash(),
        "integrity_policy_version": INTEGRITY_POLICY_VERSION,
        "morphology_sha256": ruleset.morphology_hash,
        "morphology_version": ruleset.morphology_version,
        "profile_pack_sha256": pack_hash(load_pack()),
        "profile_pack_version": PROFILE_PACK_VERSION,
        "profile_sha256": profile.hash,
        "profile_version": profile.version,
        "ruleset_sha256": ruleset.hash,
        "ruleset_version": ruleset.version,
        "style_policy_sha256": style_policy_hash(),
        "style_policy_version": STYLE_POLICY_VERSION,
    }


def approve_style_changes(
    plan: StylePlan, submission: ReviewSubmission
) -> ApprovedStylePlan:
    """Turn a batch of decisions into an authorisation, or refuse the lot.

    Every check below fails the whole submission. There is no partial approval:
    a reviewer who sent five decisions and got three applied would have no way
    to know which two, and the document would be in a state their review does
    not describe.
    """
    if submission.plan_hash != plan.plan_hash:
        raise ReviewError(
            f"{REFUSAL_WRONG_PLAN}: submission names {submission.plan_hash[:12]}…, "
            f"plan is {plan.plan_hash[:12]}…"
        )

    live = current_identity(plan)
    stale = sorted(key for key, value in plan.identity().items() if live.get(key) != value)
    if stale:
        raise ReviewError(
            f"{REFUSAL_STALE}: {stale}. A decision made about one reading of a document "
            f"does not authorise an edit to a different one; rebuild the plan and review "
            f"it again."
        )

    seen: dict[str, str] = {}
    for decision in submission.decisions:
        if decision.decision not in DECISIONS:
            raise ReviewError(f"{REFUSAL_UNKNOWN_DECISION}: {decision.decision!r}")
        if decision.proposal_id in seen:
            raise ReviewError(
                f"{REFUSAL_DUPLICATE}: {decision.proposal_id} appears as "
                f"{seen[decision.proposal_id]!r} and {decision.decision!r}"
            )
        seen[decision.proposal_id] = decision.decision

        found = plan.proposal(decision.proposal_id)
        if found is None:
            raise ReviewError(f"{REFUSAL_UNKNOWN_PROPOSAL}: {decision.proposal_id}")
        if found.status != STATUS_REVIEW_REQUIRED:
            raise ReviewError(
                f"{REFUSAL_NOT_REVIEWABLE}: {decision.proposal_id} is {found.status!r}"
            )

    approved = tuple(
        replace(plan.proposal(identifier), status=STATUS_APPROVED)
        for identifier, verdict in sorted(seen.items())
        if verdict == ACCEPT
    )
    rejected = tuple(sorted(key for key, verdict in seen.items() if verdict == REJECT))

    return ApprovedStylePlan(
        plan=plan,
        approved=tuple(sorted(approved, key=lambda item: item.source_span.start)),
        rejected=rejected,
        submission_hash=submission.submission_hash,
    )


# ── Application ────────────────────────────────────────────────────────────


def apply_style_changes(
    document: Document, approval: ApprovedStylePlan
) -> StyleApplicationResult:
    """Write the approved changes, or none of them.

    The same all-or-nothing discipline as the transformation applier, for the
    same reason: a half-applied review is a document in a state no person
    approved and no record describes.

    The firewall runs last, over the whole finished document rather than over
    each change in isolation. Two edits that are individually harmless can
    combine, and the per-proposal preflight in the planner cannot see that.
    """
    _check_preconditions(document, approval)

    changes = sorted(approval.approved, key=lambda item: item.source_span.start)
    pieces, cursor = [], 0
    for change in changes:
        span = change.source_span
        pieces.append(document.source[cursor:span.start])
        pieces.append(change.after)
        cursor = span.end
    pieces.append(document.source[cursor:])
    output = "".join(pieces)

    verdict = integrity_check(document.source, output)
    if not verdict.passed:
        raise StyleApplicationError(
            f"{ABORT_INTEGRITY}: {verdict.summary}. Nothing was applied. A person "
            f"approving a style change does not overrule the integrity firewall, and "
            f"there is no way to ask it to stand aside."
        )

    return StyleApplicationResult(
        input_source=document.source,
        output=output,
        input_hash=document.source_hash,
        output_hash=sha256_text(output),
        plan_hash=approval.plan_hash,
        submission_hash=approval.submission_hash,
        profile_id=approval.plan.profile_id,
        profile_hash=approval.plan.profile_hash,
        applied=tuple(replace(item, status=STATUS_APPLIED) for item in changes),
    )


def _check_preconditions(document: Document, approval: ApprovedStylePlan) -> None:
    if not approval.plan.is_for(document):
        raise StyleApplicationError(ABORT_WRONG_DOCUMENT)

    stale = [item.proposal_id for item in approval.approved if not item.still_matches(document)]
    if stale:
        raise StyleApplicationError(f"{ABORT_STALE}: {stale}")

    spans = sorted(
        (item.source_span for item in approval.approved), key=lambda span: (span.start, span.end)
    )
    for earlier, later in zip(spans, spans[1:]):
        if earlier.end > later.start:
            raise StyleApplicationError(
                f"{ABORT_OVERLAP}: {earlier.start}-{earlier.end} and {later.start}-{later.end}"
            )


# ── Convenience ────────────────────────────────────────────────────────────


def accept_all(plan: StylePlan) -> ReviewSubmission:
    """A submission accepting every reviewable proposal.

    A test and demonstration helper, not a shortcut for a caller. It still goes
    through `approve_style_changes` and every check there, so nothing about it
    weakens the guarantee — it just saves writing the same eight decisions out
    by hand.
    """
    return ReviewSubmission(
        plan_hash=plan.plan_hash,
        decisions=tuple(
            ReviewDecision(proposal_id=item.proposal_id, decision=ACCEPT)
            for item in plan.review_required
        ),
    )


def decide(plan: StylePlan, **verdicts: str) -> ReviewSubmission:
    """Build a submission from `proposal_id=decision` pairs."""
    return ReviewSubmission(
        plan_hash=plan.plan_hash,
        decisions=tuple(
            ReviewDecision(proposal_id=key, decision=value)
            for key, value in sorted(verdicts.items())
        ),
    )
