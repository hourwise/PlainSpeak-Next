"""Measuring a document once, and interpreting the result.

The split here is the whole of Phase 8's architecture.

`observe` measures. It runs every diagnostic, collects the metrics, and returns
raw observations with no thresholds applied to any of them. It is the expensive
half — sentence segmentation, n-gram counting, paragraph comparison — and it
knows nothing about profiles.

`interpret_baseline`, and the profile interpreter next door, decide what a set of
observations means. That half is arithmetic over numbers that already exist:
compare, band, sort. It knows nothing about text.

Because the two are separate, comparing five profiles costs one measurement and
five comparisons rather than five measurements. That matters for a profile
selector in a desktop pane, and it is asserted by counting measurement calls
rather than assumed.

It also turns the invariant that keeps the layering honest into something a test
can check: a profile cannot alter raw metrics, because interpretation never
touches the text.

`analyze` is the Phase 7 entry point and is unchanged in behaviour. It observes,
interprets against the base policy, and returns exactly the bytes it returned
before — pinned by a digest that predates this refactor.
"""
from __future__ import annotations

from typing import Optional

from . import patterns
from .metrics import measure
from .model import (
    DocumentStructure,
    StyleAnalysis,
    StyleFinding,
    StyleMetrics,
    StyleObservation,
    StyleObservations,
    text_hash,
)
from .policy import MINIMUM_SAMPLES, STYLE_POLICY_VERSION, THRESHOLDS, policy_hash, severity_for

#: Severity order for sorting. Strongest first, so a reader sees the thing most
#: worth looking at without scrolling.
_ORDER = {"strong": 0, "notice": 1, "info": 2}


def observe(text: str, structure: Optional[DocumentStructure] = None) -> StyleObservations:
    """Measure a document. No thresholds, no profile, no opinions.

    `text` is clean prose — the projection, with markup already removed by the
    document layer. `structure` describes the document's shape. Neither is
    parsed here: there is one parser in this project and it is not this one.
    """
    shape = structure if structure is not None else DocumentStructure()
    metrics = measure(text, shape)

    found = [
        patterns.sentence_uniformity(text, metrics),
        patterns.paragraph_uniformity(shape, metrics),
        patterns.repeated_sentence_opener(text),
        patterns.repeated_paragraph_opener(shape),
        patterns.transition_density(text),
        patterns.repeated_transition(text, shape),
        patterns.canned_framing(text, shape),
        patterns.vocabulary_overuse(text),
        patterns.rhetorical_repetition(text),
        patterns.triadic_repetition(text),
        patterns.repeated_phrase(text),
        patterns.lexical_overlap(shape),
        patterns.list_dominance(shape),
    ]

    # Surface-template counts are metrics rather than findings: repeating "This
    # demonstrates" is already caught by the opener diagnostic, and a second
    # finding for the same text would be noise.
    enriched = dict(metrics.values)
    for name, count in patterns.surface_template_counts(text).items():
        enriched[f"template_{name.replace('-', '_')}"] = count

    return StyleObservations(
        document_hash=text_hash(text),
        metrics=StyleMetrics(values=enriched),
        observations=tuple(
            sorted((item for item in found if item is not None), key=lambda item: item.id)
        ),
    )


def finding_from(observation: StyleObservation, severity: str, threshold: float) -> StyleFinding:
    """Turn a measurement plus a judgement into a reportable finding.

    Shared by the baseline and the profile interpreter so that the two cannot
    drift into producing differently shaped findings from the same observation.
    """
    return StyleFinding(
        id=observation.id,
        category=observation.category,
        severity=severity,
        message=observation.message,
        value=observation.value,
        threshold=threshold,
        sample_size=observation.sample_size,
        evidence=observation.evidence,
    )


def interpret_baseline(observed: StyleObservations) -> StyleAnalysis:
    """Read observations against the base style policy.

    Byte-for-byte the Phase 7 answer. This is the same comparison the diagnostic
    functions used to make inline, moved here when measurement and judgement were
    separated, and not otherwise changed.
    """
    findings = []
    for observation in observed.observations:
        if observation.sample_size < MINIMUM_SAMPLES[observation.id]:
            continue
        severity = severity_for(observation.id, observation.value)
        if not severity:
            continue
        notice, strong = THRESHOLDS[observation.id]
        findings.append(
            finding_from(observation, severity, strong if severity == "strong" else notice)
        )

    return StyleAnalysis(
        document_hash=observed.document_hash,
        policy_version=STYLE_POLICY_VERSION,
        policy_hash=policy_hash(),
        metrics=observed.metrics,
        findings=tuple(sorted(findings, key=lambda item: (_ORDER[item.severity], item.id))),
    )


def analyze(text: str, structure: Optional[DocumentStructure] = None) -> StyleAnalysis:
    """Measure a document and report what is unusual about how it is written.

    The unprofiled, baseline analysis: exactly the Phase 7 behaviour, and pinned
    as such. A caller who wants a document read against expectations for a
    particular kind of prose passes observations and a profile to
    `plainspeak.style.interpret` instead.
    """
    return interpret_baseline(observe(text, structure))
