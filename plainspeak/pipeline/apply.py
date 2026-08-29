"""Applying a transformation plan to a document.

A plan is a decision made at a moment, against a specific document and a
specific ruleset. Applying it later is only safe if nothing has moved in
between, so every precondition is checked before a single character is
replaced:

1. the plan was built against *this* document (`input_hash`);
2. every accepted proposal still finds the text it was made against
   (its `original_hash`);
3. no two accepted proposals overlap.

If any of those fails, nothing is applied. Not "as much as possible", not "the
ones that still check out" — nothing. A half-applied plan is a document in a
state no rule intended and no audit record describes, and there is no way to
tell from the result which half ran.

The original `Document` is never mutated. Application produces a new string;
what the caller does with it is their business.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ..document.model import Document, Span, content_hash
from .plan import ProposedChange
from .planner import TransformationPlan

#: Why an application was refused. Each names a precondition, because "it did
#: not work" is not something a caller can act on.
ABORT_WRONG_DOCUMENT = "the plan was built against a different document"
ABORT_STALE = "the document has changed since the plan was built"
ABORT_OVERLAP = "two accepted changes cover the same characters"


class ApplicationError(RuntimeError):
    """A plan could not be applied. Nothing was changed."""


@dataclass(frozen=True)
class AppliedChange:
    """One change that was actually made, for the audit trail."""

    rule_id: str
    rule_version: int
    source_start: int
    source_end: int
    before: str
    after: str


@dataclass(frozen=True)
class ApplicationResult:
    """The outcome of applying a plan.

    `output` is a new string. The document that was passed in is unchanged and
    still describes the input, which is what makes it safe to hold both and
    show a reader the difference.
    """

    input_source: str
    output: str
    input_hash: str
    output_hash: str
    ruleset_hash: str
    ruleset_version: str
    engine_version: str
    applied: tuple[AppliedChange, ...]
    refused_count: int
    diagnostic_count: int

    @property
    def changed(self) -> bool:
        return self.output != self.input_source

    @property
    def change_count(self) -> int:
        return len(self.applied)


def apply_plan(document: Document, plan: TransformationPlan) -> ApplicationResult:
    """Apply every accepted change in a plan, or raise and change nothing."""
    _check_preconditions(document, plan)

    replacements = [
        (change.source_span, change.replacement)
        for change in plan.accepted
        if change.source_span is not None
    ]

    # `Document.serialise` applies right to left and rejects overlaps itself, so
    # the ordering guarantee lives in one place rather than being re-implemented
    # here where it could drift.
    output = document.serialise(replacements)

    applied = tuple(
        AppliedChange(
            rule_id=change.rule_id,
            rule_version=change.rule_version,
            source_start=change.source_span.start,
            source_end=change.source_span.end,
            before=change.original_text,
            after=change.replacement,
        )
        for change in sorted(
            plan.accepted, key=lambda item: (item.source_span.start, item.rule_id)
        )
        if change.source_span is not None
    )

    return ApplicationResult(
        input_source=document.source,
        output=output,
        input_hash=document.source_hash,
        output_hash=content_hash(output),
        ruleset_hash=plan.ruleset_hash,
        ruleset_version=plan.ruleset_version,
        engine_version=plan.engine_version,
        applied=applied,
        refused_count=len(plan.refused),
        diagnostic_count=len(plan.diagnostics),
    )


def _check_preconditions(document: Document, plan: TransformationPlan) -> None:
    if not plan.is_for(document):
        raise ApplicationError(
            f"{ABORT_WRONG_DOCUMENT}: plan expects {plan.input_hash[:12]}, "
            f"document is {document.source_hash[:12]}"
        )

    stale = []
    for change in plan.accepted:
        span = change.source_span
        if span is None:
            raise ApplicationError(
                f"{ABORT_STALE}: {change.rule_id} was accepted without a source range"
            )
        if span.end > len(document.source):
            stale.append(f"{change.rule_id} points past the end of the document")
            continue
        if not change.still_matches(document):
            found = span.text(document.source)
            stale.append(
                f"{change.rule_id} expected {change.original_text!r} at "
                f"[{span.start}, {span.end}) but found {found!r}"
            )
    if stale:
        raise ApplicationError(f"{ABORT_STALE}: " + "; ".join(stale))

    ordered = sorted(
        (change.source_span for change in plan.accepted if change.source_span is not None),
        key=lambda span: (span.start, span.end),
    )
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier.overlaps(later):
            raise ApplicationError(
                f"{ABORT_OVERLAP}: [{earlier.start}, {earlier.end}) and "
                f"[{later.start}, {later.end})"
            )
