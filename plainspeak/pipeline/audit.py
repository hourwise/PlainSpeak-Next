"""The audit record for a transformation plan.

Every change PlainSpeak makes should be inspectable afterwards, by a person or
by a machine, without re-running anything. That is what this produces: a
canonical JSON document naming the engine, the ruleset, the input, and every
proposal with its outcome and — where it was refused — its reason.

Two properties make it an audit record rather than a log.

**It is deterministic.** The same document and ruleset produce byte-identical
JSON on every platform: sorted keys, fixed field order by virtue of that
sorting, UTF-8 rather than escapes, and entries in a total order that does not
depend on how anything was iterated.

**It carries no clock.** There is no timestamp anywhere in the deterministic
content, so the record's own hash identifies the *decision*, not the moment it
was taken. Running the engine twice over the same input produces the same
audit; if it did not, the hash would be worthless for comparing two runs, which
is most of what an audit is for. A human-facing timestamp can be attached
alongside later, outside the hashed content.
"""
from __future__ import annotations

from typing import Any, Optional

from ..rules import canonical_json, sha256_text
from .apply import ApplicationResult
from .plan import ProposedChange
from .planner import Conflict, TransformationPlan

STATUS_ACCEPTED = "accepted"
STATUS_REFUSED = "refused"
STATUS_DIAGNOSTIC = "diagnostic"


def plan_to_dict(plan: TransformationPlan) -> dict[str, Any]:
    """The plan as plain, ordered data."""
    # Built from the settled lists rather than from `proposals`, which holds the
    # candidates as they were *before* conflict resolution. A refused candidate
    # still looks applicable in that list; only its counterpart in `refused`
    # carries the reason it was turned down.
    entries = [_change_entry(change, STATUS_ACCEPTED) for change in plan.accepted]
    entries += [_change_entry(change, STATUS_REFUSED) for change in plan.refused]
    entries += [_change_entry(change, STATUS_DIAGNOSTIC) for change in plan.diagnostics]
    entries.sort(key=_entry_order)

    return {
        "engine_version": plan.engine_version,
        "ruleset_version": plan.ruleset_version,
        "ruleset_sha256": plan.ruleset_hash,
        "input_sha256": plan.input_hash,
        "projection_sha256": plan.projection_hash,
        "counts": {
            "proposed": len(plan.proposals),
            "accepted": len(plan.accepted),
            "refused": len(plan.refused),
            "diagnostics": len(plan.diagnostics),
            "conflicts": len(plan.conflicts),
        },
        "rules_fired": list(plan.rule_ids),
        "changes": entries,
        "conflicts": [_conflict_entry(item) for item in plan.conflicts],
    }


def plan_to_json(plan: TransformationPlan) -> str:
    """The canonical JSON audit record for a plan."""
    return canonical_json(plan_to_dict(plan))


def plan_digest(plan: TransformationPlan) -> str:
    """SHA-256 of the audit record — an identity for the whole decision."""
    return sha256_text(plan_to_json(plan))


def result_to_dict(result: ApplicationResult) -> dict[str, Any]:
    """The record of what was actually applied."""
    return {
        "engine_version": result.engine_version,
        "ruleset_version": result.ruleset_version,
        "ruleset_sha256": result.ruleset_hash,
        "input_sha256": result.input_hash,
        "output_sha256": result.output_hash,
        "changed": result.changed,
        "counts": {
            "applied": len(result.applied),
            "refused": result.refused_count,
            "diagnostics": result.diagnostic_count,
        },
        "applied": [
            {
                "rule_id": change.rule_id,
                "rule_version": change.rule_version,
                "source_start": change.source_start,
                "source_end": change.source_end,
                "before": change.before,
                "after": change.after,
            }
            for change in result.applied
        ],
    }


def result_to_json(result: ApplicationResult) -> str:
    return canonical_json(result_to_dict(result))


# ── Entries ────────────────────────────────────────────────────────────────


def _change_entry(change: ProposedChange, status: str) -> dict[str, Any]:
    span = change.source_span
    spans = [{"start": item.start, "end": item.end} for item in change.source_spans]
    return {
        "rule_id": change.rule_id,
        "rule_version": change.rule_version,
        "mode": change.mode,
        "status": status,
        "analysis_start": change.analysis_span.start,
        "analysis_end": change.analysis_span.end,
        # The single contiguous range, when there is one. Null rather than a
        # guess when the match spans markup: `source_spans` below still records
        # exactly which pieces were found.
        "source_start": span.start if span is not None else None,
        "source_end": span.end if span is not None else None,
        "source_spans": spans,
        "document_path": list(change.document_path),
        "location": change.location,
        "before": change.original_text,
        "before_sha256": change.original_hash,
        "after": change.replacement,
        "reason": change.reason,
    }


def _entry_order(entry: dict[str, Any]) -> tuple:
    """A total order over audit entries.

    Position first, so the record reads in document order; then rule identity,
    so two rules firing at the same offset always appear the same way round.
    Nothing here depends on iteration or insertion order.
    """
    return (
        entry["analysis_start"],
        entry["analysis_end"],
        entry["rule_id"],
        entry["rule_version"],
        entry["status"],
    )


def _conflict_entry(conflict: Conflict) -> dict[str, Any]:
    return {
        "kind": conflict.kind,
        "reason": conflict.reason,
        "source_start": conflict.source_start,
        "source_end": conflict.source_end,
        "rule_ids": list(conflict.rule_ids),
        "winner": conflict.winner,
    }
