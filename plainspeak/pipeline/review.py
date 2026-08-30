"""One coherent snapshot of everything an interface needs to review a document.

Four independent authorities have something to say about a document: the rule
engine proposes safe changes, the integrity firewall refuses some of them, the
style layer measures the prose, and a profile decides what those measurements
mean. An interface that had to join those four itself would be re-implementing
this module — badly, in a widget, where nobody would test it.

So the join lives here. A `ReviewBundle` is built once against one immutable
document under one explicitly named profile, and answers every question an
adapter can ask without going back to the engine:

    what would change automatically          bundle.preview(...).changes, kind "safe"
    what a person must decide                kind "style", status "review_required"
    what the firewall refused                kind "refused"
    what the style layer observed            bundle.diagnostics
    which authorities produced all of it     bundle.identities

The important property is that a bundle is a *snapshot*. Accepting a proposal
does not re-plan anything; it selects from decisions the engine already made and
already bound to a plan hash. Nothing an interface does can move the ground
under a review that is in progress.

### Mapping

`PreviewResult` carries, for every change, where it is in the source *and* where
the corresponding text sits in the revised output — including for changes that
were not applied, whose original text is still present and has still moved.
Computing that in a widget from "source offset plus accumulated lengths" is the
obvious approach and is wrong the first time two edits are adjacent, so it is
computed once, here, from the same ordered replacement list the serialiser uses.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from ..document.model import Document, Span, content_hash
from ..integrity import check as integrity_check
from ..rules import Ruleset, load_ruleset
from ..rules.canonical import canonical_json
from ..style.model import ProfiledAnalysis, StyleObservations
from ..style.profiles import StyleProfile, load_profile, profile_ids
from .apply import ApplicationError
from .planner import TransformationPlan, build_plan
from .projection import Projection, project_document
from .sources import load_document, read_text_source
from .style_plan import STATUS_REVIEW_REQUIRED, StylePlan, plan_style_changes
from .style_review import (
    ACCEPT,
    REJECT,
    ReviewDecision,
    ReviewSubmission,
    approve_style_changes,
)
from .styling import interpret_style, observe_style

#: Document types an interface may review and save.
#:
#: Deliberately not everything the reader can open. DOCX, PDF and HTML currently
#: load through the plain-text degradation path, which is an honest fallback for
#: *analysis* and a poor foundation for *editing*: a caller shown a revised
#: document would reasonably assume its structure had been preserved, and
#: nothing in the engine can promise that yet.
REVIEWABLE_SUFFIXES: tuple[str, ...] = (".txt", ".md", ".markdown")

UNSUPPORTED_MESSAGE = (
    "This version can review and save plain text and Markdown (.txt, .md, "
    ".markdown). Structured DOCX, PDF and HTML support is not available yet."
)

#: What kind of thing a row in a review list is.
KIND_SAFE = "safe"
KIND_STYLE = "style"
KIND_REFUSED = "refused"

#: What has happened to it. `review_required` is a first-class state: a valid
#: suggestion awaiting judgement is not a refusal, and an interface that could
#: not tell them apart would be useless.
STATUS_APPLIED = "applied"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
STATUS_REFUSED = "refused"


class ReviewError(ValueError):
    """A document could not be reviewed. Never downgraded to an empty bundle."""


@dataclass(frozen=True)
class ChangeView:
    """One row in a review list, with everything needed to render and locate it.

    Carries both coordinate systems. `revised_start`/`revised_end` are where the
    text sits *after* every applied change, which for an unapplied change is
    where its unchanged original now is — a rejected proposal has still moved if
    something before it grew.
    """

    change_id: str
    kind: str
    status: str
    rule_id: str
    rule_version: int
    mode: str
    source_start: int
    source_end: int
    revised_start: int
    revised_end: int
    before: str
    after: str
    reason: str
    refusal: str = ""
    profile_id: str = ""
    trigger_diagnostic: str = ""
    trigger_severity: str = ""
    integrity_checked: bool = False

    @property
    def is_reviewable(self) -> bool:
        return self.kind == KIND_STYLE and self.status in (
            STATUS_REVIEW_REQUIRED,
            STATUS_ACCEPTED,
            STATUS_REJECTED,
        )

    @property
    def badge(self) -> str:
        """A short label that carries the state without relying on colour."""
        if self.kind == KIND_SAFE:
            return "SAFE"
        if self.kind == KIND_REFUSED:
            return "REFUSED"
        return {
            STATUS_REVIEW_REQUIRED: "REVIEW",
            STATUS_ACCEPTED: "ACCEPTED",
            STATUS_REJECTED: "REJECTED",
        }.get(self.status, "REVIEW")

    def as_dict(self) -> dict[str, Any]:
        return {
            "after": self.after,
            "badge": self.badge,
            "before": self.before,
            "change_id": self.change_id,
            "integrity_checked": self.integrity_checked,
            "kind": self.kind,
            "mode": self.mode,
            "profile_id": self.profile_id,
            "reason": self.reason,
            "refusal": self.refusal,
            "revised_end": self.revised_end,
            "revised_start": self.revised_start,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "source_end": self.source_end,
            "source_start": self.source_start,
            "status": self.status,
            "trigger_diagnostic": self.trigger_diagnostic,
            "trigger_severity": self.trigger_severity,
        }


@dataclass(frozen=True)
class PreviewResult:
    """The revised document, and where everything went.

    `revised_text` is the artifact. An interface displays it and may save it, but
    must save *this* string rather than whatever a text widget currently holds —
    a rendering bug in the widget must not be able to reach a file.
    """

    source_text: str
    revised_text: str
    output_hash: str
    changes: tuple[ChangeView, ...] = ()

    @property
    def changed(self) -> bool:
        return self.revised_text != self.source_text

    def change(self, change_id: str) -> Optional[ChangeView]:
        for item in self.changes:
            if item.change_id == change_id:
                return item
        return None

    def of_kind(self, kind: str) -> tuple[ChangeView, ...]:
        return tuple(item for item in self.changes if item.kind == kind)

    def as_dict(self) -> dict[str, Any]:
        return {
            "changes": [item.as_dict() for item in self.changes],
            "output_sha256": self.output_hash,
        }


@dataclass(frozen=True)
class DiagnosticView:
    """One style observation, with the evidence a reader can go and check."""

    id: str
    severity: str
    message: str
    value: float
    threshold: float
    sample_size: int
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence": list(self.evidence),
            "id": self.id,
            "message": self.message,
            "sample_size": self.sample_size,
            "severity": self.severity,
            "threshold": round(self.threshold, 6),
            "value": round(self.value, 6),
        }


@dataclass(frozen=True)
class ReviewBundle:
    """One document, one profile, one immutable reading of both.

    Everything below was decided when this was built. Accepting or rejecting a
    proposal selects among those decisions; it never re-plans, so proposal
    identifiers and review authority cannot move under an interface mid-session.
    """

    document: Document
    profile: StyleProfile
    safe_plan: TransformationPlan
    style_plan: StylePlan
    analysis: ProfiledAnalysis
    observations: StyleObservations
    projection: Projection

    @property
    def source_text(self) -> str:
        return self.document.source

    @property
    def input_hash(self) -> str:
        return self.document.source_hash

    @property
    def profile_id(self) -> str:
        return self.profile.id

    @property
    def reviewable(self) -> tuple:
        """Style proposals awaiting a person, in source order."""
        return self.style_plan.review_required

    def identities(self) -> dict[str, Any]:
        """Every authority that produced this bundle.

        The same shape the style plan binds, so a details view and an audit
        record cannot disagree about what was in force.
        """
        return {
            **self.style_plan.identity(),
            "plan_sha256": self.style_plan.plan_hash,
            "safe_plan_ruleset_sha256": self.safe_plan.ruleset_hash,
        }

    def diagnostics(self) -> tuple[DiagnosticView, ...]:
        """What the style layer observed, under this profile."""
        return tuple(
            DiagnosticView(
                id=finding.id,
                severity=finding.severity,
                message=finding.message,
                value=finding.value,
                threshold=finding.threshold,
                sample_size=finding.sample_size,
                evidence=tuple(
                    f"{item.label} — {item.count} of {item.total}"
                    for item in finding.evidence
                ),
            )
            for finding in self.analysis.findings
        )

    def preview(
        self,
        accepted: Iterable[str] = (),
        rejected: Iterable[str] = (),
    ) -> PreviewResult:
        """Materialise the revised document for a set of review decisions.

        `accepted` and `rejected` name style proposals by identifier. Acceptance
        goes through the Phase 9 review contract — a real `ReviewSubmission`
        bound to this plan's hash, checked for freshness and atomicity — rather
        than being a boolean an interface keeps to itself. An identifier that is
        not awaiting review, or a plan whose authorities have moved, refuses
        here exactly as it would refuse anywhere else.
        """
        accepted_ids = tuple(sorted(set(accepted)))
        rejected_ids = tuple(sorted(set(rejected) - set(accepted_ids)))

        approved = ()
        if accepted_ids or rejected_ids:
            submission = ReviewSubmission(
                plan_hash=self.style_plan.plan_hash,
                decisions=tuple(
                    ReviewDecision(identifier, ACCEPT) for identifier in accepted_ids
                )
                + tuple(ReviewDecision(identifier, REJECT) for identifier in rejected_ids),
            )
            approved = approve_style_changes(self.style_plan, submission).approved

        replacements: list[tuple[Span, str]] = [
            (change.source_span, change.replacement)
            for change in self.safe_plan.accepted
            if change.source_span is not None
        ]
        replacements += [
            (item.source_span, item.after) for item in approved if item.source_span is not None
        ]

        try:
            revised = self.document.serialise(replacements)
        except ValueError as error:
            raise ReviewError(f"the selected changes cannot be combined: {error}") from None

        # The document-global check. Every change here already passed the
        # firewall alone; only the finished text shows what several did together,
        # and a person accepting a style change does not overrule it.
        verdict = integrity_check(self.document.source, revised)
        if not verdict.passed:
            raise ReviewError(
                f"the revised document would not preserve protected information: "
                f"{verdict.summary}"
            )

        accepted_set = set(accepted_ids)
        rejected_set = set(rejected_ids)
        return PreviewResult(
            source_text=self.document.source,
            revised_text=revised,
            output_hash=content_hash(revised),
            changes=self._changes(replacements, accepted_set, rejected_set),
        )

    # ── Building the rows ──────────────────────────────────────────────────

    def _changes(
        self,
        replacements: Sequence[tuple[Span, str]],
        accepted: set[str],
        rejected: set[str],
    ) -> tuple[ChangeView, ...]:
        shift = _ShiftMap(replacements)
        rows: list[ChangeView] = []

        for change in self.safe_plan.accepted:
            span = change.source_span
            if span is None:
                continue
            start = shift.revised_offset(span.start)
            rows.append(
                ChangeView(
                    change_id=_change_id("safe", change.rule_id, change.rule_version, span,
                                         change.original_text, change.replacement),
                    kind=KIND_SAFE,
                    status=STATUS_APPLIED,
                    rule_id=change.rule_id,
                    rule_version=change.rule_version,
                    mode=change.mode,
                    source_start=span.start,
                    source_end=span.end,
                    revised_start=start,
                    revised_end=start + len(change.replacement),
                    before=change.original_text,
                    after=change.replacement,
                    reason=_reason_of(change.rule_id, self.safe_plan),
                    integrity_checked=True,
                )
            )

        for proposal in self.style_plan.proposals:
            span = proposal.source_span
            if span is None:
                continue
            if proposal.status != STATUS_REVIEW_REQUIRED:
                status, applied = STATUS_REFUSED, False
            elif proposal.proposal_id in accepted:
                status, applied = STATUS_ACCEPTED, True
            elif proposal.proposal_id in rejected:
                status, applied = STATUS_REJECTED, False
            else:
                status, applied = STATUS_REVIEW_REQUIRED, False

            start = shift.revised_offset(span.start)
            rows.append(
                ChangeView(
                    change_id=proposal.proposal_id,
                    kind=KIND_STYLE if proposal.status == STATUS_REVIEW_REQUIRED else KIND_REFUSED,
                    status=status,
                    rule_id=proposal.rule_id,
                    rule_version=proposal.rule_version,
                    mode=proposal.mode,
                    source_start=span.start,
                    source_end=span.end,
                    revised_start=start,
                    revised_end=start + len(proposal.after if applied else proposal.before),
                    before=proposal.before,
                    after=proposal.after,
                    reason=proposal.reason,
                    refusal=proposal.refusal,
                    profile_id=proposal.profile_id,
                    trigger_diagnostic=proposal.trigger_diagnostic,
                    trigger_severity=proposal.trigger_severity,
                    integrity_checked=proposal.integrity_checked,
                )
            )

        # Refused safe fixes come from the plan's own refusal list, which carries
        # the text and the span. The firewall's separate record is matched in by
        # analysis position to supply the detail: "refused for integrity" is not
        # something a reader can act on, and "modal: must became may" is.
        detail = {
            (item.analysis_start, item.analysis_end): item
            for item in self.safe_plan.integrity_refusals
        }
        for change in self.safe_plan.refused:
            if not change.source_spans:
                continue
            span = Span(change.source_spans[0].start, change.source_spans[-1].end)
            found = detail.get((change.analysis_span.start, change.analysis_span.end))
            start = shift.revised_offset(span.start)
            rows.append(
                ChangeView(
                    change_id=_change_id(
                        "refused", change.rule_id, change.rule_version, span,
                        change.original_text, change.replacement,
                    ),
                    kind=KIND_REFUSED,
                    status=STATUS_REFUSED,
                    rule_id=change.rule_id,
                    rule_version=change.rule_version,
                    mode=change.mode,
                    source_start=span.start,
                    source_end=span.end,
                    revised_start=start,
                    revised_end=start + len(change.original_text),
                    before=change.original_text,
                    after=change.replacement,
                    reason="",
                    refusal=(
                        f"{change.reason} — {found.summary}" if found is not None
                        else change.reason
                    ),
                    integrity_checked=found is not None,
                )
            )

        return tuple(sorted(rows, key=lambda item: (item.source_start, item.change_id)))


class _ShiftMap:
    """Where a source offset ends up once every applied replacement is in place.

    The obvious implementation — "source offset plus accumulated lengths" done
    inside a widget — is wrong the first time two edits are adjacent, and wrong
    in a way nobody notices until a highlight lands two characters off. Built
    once here from the same ordered replacement list the serialiser uses, so the
    mapping and the text cannot disagree.
    """

    def __init__(self, replacements: Sequence[tuple[Span, str]]) -> None:
        self._edits = sorted(
            ((span.start, span.end, len(text)) for span, text in replacements),
            key=lambda item: (item[0], item[1]),
        )

    def revised_offset(self, source_offset: int) -> int:
        delta = 0
        for start, end, length in self._edits:
            if end <= source_offset:
                delta += length - (end - start)
            elif start < source_offset:
                # The offset falls inside a replaced span. The replacement is a
                # unit, so the whole of it begins where the span began.
                return start + delta
            else:
                break
        return source_offset + delta


def _change_id(kind: str, rule_id: str, version: int, span: Span, before: str, after: str) -> str:
    """A stable identifier for a row that is not a style proposal.

    Style proposals already have Phase 9 identifiers and keep them. Safe changes
    and integrity refusals need one so an interface can address a row without
    using its visible text, which would break the moment two rows read alike.
    """
    digest = hashlib.sha256(
        canonical_json(
            {
                "after": after,
                "before": before,
                "kind": kind,
                "rule_id": rule_id,
                "rule_version": version,
                "source_end": span.end,
                "source_start": span.start,
            }
        ).encode("utf-8")
    ).hexdigest()
    return f"{'SF' if kind == 'safe' else 'IR'}-{digest[:16]}"


def _reason_of(rule_id: str, plan: TransformationPlan) -> str:
    for change in plan.proposals:
        if change.rule_id == rule_id and change.reason:
            return change.reason
    return ""


# ── Building a bundle ──────────────────────────────────────────────────────


def is_reviewable_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in REVIEWABLE_SUFFIXES


def load_reviewable(path: str | Path) -> Document:
    """Read a document an interface may review, or refuse it by name.

    Reading is `sources.load_document`'s job and is not repeated here. What this
    adds is the narrower question of whether the result can be *edited* safely,
    which is a different question from whether it can be read.
    """
    target = Path(path)
    if not is_reviewable_path(target):
        raise ReviewError(f"{UNSUPPORTED_MESSAGE} ({target.suffix or 'no extension'})")
    if not target.is_file():
        raise ReviewError(f"file not found: {target}")
    return load_document(target)


def build_review_bundle(
    document: Document,
    profile: Any,
    ruleset: Optional[Ruleset] = None,
) -> ReviewBundle:
    """Read one document under one explicitly named profile.

    There is no default profile. An interface may show one selected, and that is
    a product decision; every call still names it, so nothing here can analyse a
    specification against conversational expectations because a default went
    unnoticed.
    """
    if profile is None:
        raise ReviewError(
            f"a review needs an explicit profile; available: {list(profile_ids())}"
        )
    resolved = profile if isinstance(profile, StyleProfile) else load_profile(str(profile))

    rules = ruleset if ruleset is not None else load_ruleset()
    view = project_document(document)
    observed = observe_style(document, view)
    analysis = interpret_style(observed, resolved)
    safe_plan = build_plan(document, rules, view)
    style = plan_style_changes(
        document, resolved, ruleset=rules, projection=view,
        observed=observed, safe_plan=safe_plan,
    )

    return ReviewBundle(
        document=document,
        profile=resolved,
        safe_plan=safe_plan,
        style_plan=style,
        analysis=analysis,
        observations=observed,
        projection=view,
    )


def engine_identities() -> dict[str, Any]:
    """Every version and hash the engine publishes, in one call.

    Exists because the desktop needs them and may not reach into `rules`,
    `integrity`, `style` or `morphology` to collect them itself. An adapter
    gathering five identities from five packages would be four opportunities to
    read a different one than the pipeline actually used.
    """
    from ..core.syllables import get_syllable_count
    from ..integrity import POLICY_VERSION as INTEGRITY_VERSION
    from ..integrity import policy_hash as integrity_hash
    from ..style import STYLE_POLICY_VERSION
    from ..style import policy_hash as style_hash
    from ..style.profiles import PROFILE_PACK_VERSION, load_pack, pack_hash, profile_ids

    ruleset = load_ruleset()
    pack = load_pack()
    return {
        "ruleset_version": ruleset.version,
        "ruleset_count": len(ruleset),
        "ruleset_sha256": ruleset.hash,
        "style_fix_count": len(ruleset.style_fixes),
        "style_fixes_all_review_required": all(
            not rule.is_automatic for rule in ruleset.style_fixes
        ),
        "integrity_version": INTEGRITY_VERSION,
        "integrity_sha256": integrity_hash(),
        "morphology_version": ruleset.morphology_version,
        "morphology_sha256": ruleset.morphology_hash,
        "style_policy_version": STYLE_POLICY_VERSION,
        "style_policy_sha256": style_hash(),
        "profile_pack_version": PROFILE_PACK_VERSION,
        "profile_pack_sha256": pack_hash(pack),
        "profiles": tuple(profile_ids()),
        "profile_hashes": {profile.id: profile.hash for profile in pack},
        "syllable_entries": len(get_syllable_count()),
        "syllable_uses_dictionary": get_syllable_count().get("business") == 2,
    }


def text_hash(text: str) -> str:
    """The engine's content hash, so an adapter need not import `document`."""
    return content_hash(text)


def parse_source(text: str, markdown: bool = True) -> Document:
    """Turn text into a `Document` without an adapter importing `document`.

    Reading a file is `load_reviewable`'s job; this is for text an adapter
    already holds — a fixture inside the package, a clipboard paste, a string in
    a test.
    """
    from ..document import parse_markdown, parse_text

    return parse_markdown.parse(text) if markdown else parse_text.parse(text)
