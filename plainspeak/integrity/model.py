"""The immutable contracts the integrity firewall reasons about.

A fact is one piece of information the policy has declared invariant, found at
one place in a piece of text. A snapshot is every fact in that text, plus the
identity of the policy that found them — because a snapshot taken under one
policy says nothing about what a different policy would have protected.

Comparison between snapshots is deliberately **position-independent**. Any edit
shifts the offsets of everything after it, so comparing positions would flag
every successful transformation as a violation. What matters is the multiset of
facts: which protected values are present, and how many times. A dosage that
appears twice must still appear twice.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class IntegrityFact:
    """One invariant, as found in one piece of text.

    Ordered by position first so a snapshot reads in document order, and by
    kind and identity after, so that two facts starting at the same offset
    always sort the same way whatever order they were found in.
    """

    start: int
    end: int
    kind: str
    #: Exactly the characters that were matched.
    surface: str
    #: The identity used for comparison. Two facts are the same fact when their
    #: kind and normalized form agree, whatever the surface said — "£2,500" and
    #: "£2500" are one amount, and "0.5 mg" is not "5 mg".
    normalized: str

    @property
    def identity(self) -> tuple[str, str]:
        return (self.kind, self.normalized)


@dataclass(frozen=True)
class IntegritySnapshot:
    """Every protected fact in a piece of text, under a named policy."""

    text_hash: str
    policy_version: str
    policy_hash: str
    facts: tuple[IntegrityFact, ...]

    def __iter__(self) -> Iterator[IntegrityFact]:
        return iter(self.facts)

    def __len__(self) -> int:
        return len(self.facts)

    @property
    def signature(self) -> Counter:
        """The multiset of fact identities.

        This is what comparison actually uses. Counts matter: an edit that
        removed one of two identical dosages would leave the *set* unchanged.
        """
        return Counter(fact.identity for fact in self.facts)

    def of_kind(self, kind: str) -> tuple[IntegrityFact, ...]:
        return tuple(fact for fact in self.facts if fact.kind == kind)

    def surfaces(self, kind: str) -> tuple[str, ...]:
        return tuple(fact.surface for fact in self.of_kind(kind))

    def as_dict(self) -> dict:
        """Plain data, for audit records."""
        return {
            "text_sha256": self.text_hash,
            "policy_version": self.policy_version,
            "policy_sha256": self.policy_hash,
            "facts": [
                {
                    "kind": fact.kind,
                    "start": fact.start,
                    "end": fact.end,
                    "surface": fact.surface,
                    "normalized": fact.normalized,
                }
                for fact in self.facts
            ],
        }


@dataclass(frozen=True)
class Violation:
    """One protected category that did not survive a transformation.

    `before` and `after` are the surfaces, so a report can show a reader what
    changed rather than an internal normalisation they never wrote.
    """

    kind: str
    before: tuple[str, ...]
    after: tuple[str, ...]
    detail: str

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "before": list(self.before),
            "after": list(self.after),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class IntegrityVerdict:
    """The firewall's answer about one transformation.

    `passed` is the only field a caller may act on. A verdict is never advisory
    and has no severity: either the protected information survived, or the
    transformation does not happen.
    """

    passed: bool
    policy_version: str
    policy_hash: str
    violations: tuple[Violation, ...] = ()

    @property
    def summary(self) -> str:
        if self.passed:
            return "integrity preserved"
        parts = []
        for violation in self.violations:
            before = ", ".join(violation.before) or "nothing"
            after = ", ".join(violation.after) or "nothing"
            parts.append(f"{violation.kind}: {before} -> {after}")
        return "integrity violation — " + "; ".join(parts)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "policy_version": self.policy_version,
            "policy_sha256": self.policy_hash,
            "violations": [violation.as_dict() for violation in self.violations],
        }
