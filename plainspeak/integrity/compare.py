"""Deciding whether a transformation preserved what must be preserved.

The comparison is a multiset difference between two snapshots. A fact that
appears twice must still appear twice; a fact that appears in one snapshot and
not the other — in either direction — is a violation.

Both directions matter, and the second is less obvious than the first. Removing
a negation turns a prohibition into a permission. *Introducing* one does the
same in reverse, and introducing a comparator where there was none can invent an
ordering the author never wrote. The firewall does not care which way the
information moved; it cares that it moved.

There is no severity and no threshold. A verdict either passed or it did not.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from .extract import snapshot
from .model import IntegritySnapshot, IntegrityVerdict, Violation
from .policy import POLICY_VERSION, policy_hash

_POLICY_HASH = policy_hash()


def compare(before: IntegritySnapshot, after: IntegritySnapshot) -> IntegrityVerdict:
    """Compare two snapshots taken under the same policy.

    Comparing snapshots from different policies is refused rather than
    attempted: the two would have been looking for different things, so an
    apparent agreement between them would mean nothing.
    """
    if before.policy_hash != after.policy_hash:
        raise ValueError(
            "cannot compare snapshots taken under different integrity policies: "
            f"{before.policy_hash[:12]} and {after.policy_hash[:12]}"
        )

    lost = before.signature - after.signature
    gained = after.signature - before.signature
    if not lost and not gained:
        return IntegrityVerdict(
            passed=True, policy_version=before.policy_version, policy_hash=before.policy_hash
        )

    return IntegrityVerdict(
        passed=False,
        policy_version=before.policy_version,
        policy_hash=before.policy_hash,
        violations=_violations(before, after, lost, gained),
    )


def check(before_text: str, after_text: str) -> IntegrityVerdict:
    """Snapshot two pieces of text and compare them."""
    return compare(snapshot(before_text), snapshot(after_text))


def _violations(
    before: IntegritySnapshot,
    after: IntegritySnapshot,
    lost: Counter,
    gained: Counter,
) -> tuple[Violation, ...]:
    """One violation per affected category, reported in surfaces.

    Grouped by kind rather than by individual fact, because "the modal changed"
    is what a reader needs to see, with both sides shown so they can judge it
    for themselves.
    """
    kinds = sorted({kind for kind, _ in lost} | {kind for kind, _ in gained})
    violations = []

    for kind in kinds:
        removed = sorted(value for (k, value), count in lost.items() for _ in range(count) if k == kind)
        added = sorted(value for (k, value), count in gained.items() for _ in range(count) if k == kind)
        violations.append(
            Violation(
                kind=kind,
                before=before.surfaces(kind),
                after=after.surfaces(kind),
                detail=_detail(kind, removed, added),
            )
        )

    return tuple(violations)


def _detail(kind: str, removed: list[str], added: list[str]) -> str:
    if removed and added:
        return f"{kind} changed: {', '.join(removed)} became {', '.join(added)}"
    if removed:
        return f"{kind} removed: {', '.join(removed)}"
    return f"{kind} introduced: {', '.join(added)}"


def passes(before_text: str, after_text: str) -> bool:
    """Convenience for tests and callers that only need the yes or no."""
    return check(before_text, after_text).passed
