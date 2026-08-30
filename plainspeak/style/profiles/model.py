"""What a style profile is, as an immutable validated object.

Phase 7 measures. Phase 8 interprets. The split matters because the two things
fail differently: a measurement is either right or wrong about the text, and an
interpretation is a judgement about what kind of prose the writer is aiming at.
Keeping them in separate objects means an argument about the second cannot
quietly change the first.

A profile therefore holds no algorithms. It holds numbers a diagnostic is
compared against, sample sizes it must clear, ranges a metric is expected to sit
in, and prose explaining why. It cannot say how lexical overlap is computed, and
it cannot say what to do about the answer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

#: Where a threshold came from. Recorded per override so a reader can tell a
#: number drawn from this project's corpus from one taken on convention.
#:
#: `weakly-calibrated` is the important one. It is not a source; it is an
#: admission, applied wherever the corpus has no document on one side of a line.
#: A threshold nobody has evidence for is more dangerous when it looks the same
#: as one that has been measured.
PROVENANCE = (
    "project-calibration",
    "baseline-derived",
    "plain-language-convention",
    "technical-writing-convention",
    "public-service-convention",
    "academic-convention",
    "weakly-calibrated",
)

#: How a measured value sits against a target range. Deliberately not a verdict:
#: a sentence mean above the range is a fact about the document, and whether it
#: is a problem depends on things this layer cannot see.
TARGET_STATES = ("within", "above", "below")


def finite_number(value: Any, where: str) -> float:
    """Reject NaN and infinity at the door.

    A NaN threshold compares false against everything, so a diagnostic carrying
    one goes silent and looks like it simply found nothing. That is the worst
    available failure: silence that is indistinguishable from a clean document.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{where}: expected a number, got {value!r}") from None
    if math.isnan(number) or math.isinf(number):
        raise ValueError(f"{where}: {value!r} is not a finite number")
    return number


@dataclass(frozen=True)
class DiagnosticRule:
    """How one profile interprets one diagnostic.

    `notice` and `strong` replace the baseline thresholds; `minimum_sample`
    replaces the baseline minimum but may only ever raise it. `enabled` can
    silence a diagnostic entirely, which is a heavier decision than it looks and
    is why every disabled rule must carry a reason.
    """

    diagnostic: str
    enabled: bool
    notice: float
    strong: float
    minimum_sample: int
    inverted: bool
    provenance: str
    reason: str = ""

    def severity_for(self, value: float) -> str:
        """Which band a measurement falls in under this profile, or ``""``.

        The same explicit comparison the baseline makes, against this profile's
        numbers. No weighting, no blending: a reader who disagrees can see which
        comparison produced the answer.
        """
        if not self.enabled:
            return ""
        if self.inverted:
            if value <= self.strong:
                return "strong"
            if value <= self.notice:
                return "notice"
            return ""
        if value >= self.strong:
            return "strong"
        if value >= self.notice:
            return "notice"
        return ""

    def threshold_for(self, severity: str) -> float:
        return self.strong if severity == "strong" else self.notice

    def as_dict(self) -> dict[str, Any]:
        """Behaviour-affecting fields only; `reason` is prose and excluded.

        See `canonical.py` for why the line is drawn there.
        """
        return {
            "enabled": self.enabled,
            "minimum_sample": self.minimum_sample,
            "notice": round(self.notice, 6),
            "provenance": self.provenance,
            "strong": round(self.strong, 6),
        }


@dataclass(frozen=True)
class TargetRange:
    """A range a metric is expected to sit in for this kind of prose.

    Descriptive, not a diagnostic. Deliberately a separate type from
    `DiagnosticRule` rather than a variant of it, because the two answer
    different questions and merging them would let one be mistaken for the
    other: a diagnostic threshold decides whether something is reported, and a
    target range describes what this sort of writing usually looks like.

    A value outside the range is reported as *outside the range*. It is not a
    defect, and nothing in this package will call it one.
    """

    metric: str
    minimum: float
    maximum: float
    provenance: str
    reason: str = ""

    def state_for(self, value: float) -> str:
        if value < self.minimum:
            return "below"
        if value > self.maximum:
            return "above"
        return "within"

    def as_dict(self) -> dict[str, Any]:
        return {
            "max": round(self.maximum, 6),
            "min": round(self.minimum, 6),
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class StyleProfile:
    """One resolved, validated interpretation of the base style policy.

    Every diagnostic is present, always. A profile that listed only its
    differences would need inheritance to be readable, and inheritance is
    exactly what makes a profile hard to audit — you cannot see what a number is
    without knowing what it came from. Five files repeating thirteen diagnostics
    is more text and less mystery.
    """

    id: str
    version: int
    name: str
    description: str
    target_use: str
    provenance: str
    diagnostics: dict[str, DiagnosticRule]
    targets: dict[str, TargetRange]
    #: Filled in by the loader once the profile is canonicalised.
    hash: str = ""

    def rule(self, diagnostic: str) -> Optional[DiagnosticRule]:
        return self.diagnostics.get(diagnostic)

    @property
    def disabled(self) -> tuple[str, ...]:
        return tuple(
            sorted(key for key, rule in self.diagnostics.items() if not rule.enabled)
        )

    @property
    def weakly_calibrated(self) -> tuple[str, ...]:
        """Diagnostics whose threshold has no calibration document behind it.

        Surfaced as a property rather than buried in documentation because a
        caller building a report should be able to mark these without reading
        STYLE_PROFILES.md first.
        """
        return tuple(
            sorted(
                key
                for key, rule in self.diagnostics.items()
                if rule.provenance == "weakly-calibrated"
            )
        )

    def as_dict(self) -> dict[str, Any]:
        """The identity-bearing view. Display prose is deliberately absent."""
        return {
            "diagnostics": {key: self.diagnostics[key].as_dict() for key in sorted(self.diagnostics)},
            "id": self.id,
            "provenance": self.provenance,
            "targets": {key: self.targets[key].as_dict() for key in sorted(self.targets)},
            "version": self.version,
        }

    def reference(self) -> dict[str, Any]:
        """How a profile names itself in a report."""
        return {"id": self.id, "version": self.version, "sha256": self.hash}
