"""Reading a set of observations against a profile.

Everything here is arithmetic over numbers that already exist. Nothing in this
module touches the document, the text, or any tokeniser, which is what makes the
central Phase 8 invariant hold by construction rather than by discipline: a
profile cannot change a metric, because interpretation never has the text to
measure.

The consequence worth stating is the one the gate cares about. Comparing five
profiles measures once and compares five times. A caller that wanted five
measurements would have to ask for them explicitly, and no code path here does.
"""
from __future__ import annotations

from typing import Iterable, Sequence, Union

from .analyze import _ORDER, finding_from, observe
from .model import (
    DocumentStructure,
    ProfiledAnalysis,
    StyleObservations,
    TargetResult,
)
from .policy import STYLE_POLICY_VERSION, policy_hash
from .profiles import StyleProfile, load_pack, load_profile, pack_hash

#: What a caller may pass wherever a profile is wanted: the object, or its ID.
ProfileLike = Union[StyleProfile, str]


def _resolved(profile: ProfileLike) -> StyleProfile:
    return profile if isinstance(profile, StyleProfile) else load_profile(profile)


def interpret(observed: StyleObservations, profile: ProfileLike) -> ProfiledAnalysis:
    """Read one set of observations against one profile.

    The profile decides three things and nothing else: whether a diagnostic is
    considered at all, how much evidence it needs before it will speak, and where
    its bands sit. Everything it reports — the value, the sample, the quoted
    occurrences — came from the measurement unchanged.
    """
    resolved = _resolved(profile)
    findings = []

    for observation in observed.observations:
        rule = resolved.rule(observation.id)
        if rule is None or not rule.enabled:
            continue
        # A profile may demand more evidence than the baseline. The loader has
        # already refused any profile that tried to demand less.
        if observation.sample_size < rule.minimum_sample:
            continue
        severity = rule.severity_for(observation.value)
        if not severity:
            continue
        findings.append(finding_from(observation, severity, rule.threshold_for(severity)))

    targets = []
    for metric, target in sorted(resolved.targets.items()):
        if metric not in observed.metrics.values:
            # The document gave nothing to compare — no headings, no paragraphs.
            # Silence is the honest answer; a range cannot be met or missed by a
            # measurement that does not exist.
            continue
        value = observed.metrics.values[metric]
        targets.append(
            TargetResult(
                metric=metric,
                value=value,
                minimum=target.minimum,
                maximum=target.maximum,
                state=target.state_for(value),
                provenance=target.provenance,
            )
        )

    return ProfiledAnalysis(
        document_hash=observed.document_hash,
        policy_version=STYLE_POLICY_VERSION,
        policy_hash=policy_hash(),
        profile_id=resolved.id,
        profile_version=resolved.version,
        profile_hash=resolved.hash,
        pack_hash=pack_hash(load_pack()),
        metrics=observed.metrics,
        findings=tuple(sorted(findings, key=lambda item: (_ORDER[item.severity], item.id))),
        targets=tuple(targets),
        disabled=resolved.disabled,
    )


def analyze_with_profile(
    text: str, profile: ProfileLike, structure: DocumentStructure | None = None
) -> ProfiledAnalysis:
    """Measure a document and read it against one profile."""
    return interpret(observe(text, structure), profile)


def compare_profiles(
    observed: StyleObservations, profiles: Sequence[ProfileLike] | None = None
) -> dict[str, ProfiledAnalysis]:
    """Read one measurement against several profiles.

    Takes observations rather than text, deliberately. A signature that accepted
    a document would make it possible — and eventually likely — for a caller to
    measure once per profile without noticing, and the whole point of the split
    is that comparing profiles is cheap.

    Returns a mapping in canonical profile order.
    """
    wanted: Iterable[ProfileLike]
    wanted = profiles if profiles is not None else load_pack()
    return {analysis.profile_id: analysis
            for analysis in (interpret(observed, item) for item in wanted)}
