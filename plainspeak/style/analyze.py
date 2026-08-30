"""Running every style diagnostic over one document.

Orchestration only: measure, run each diagnostic, sort, freeze. The order in
which diagnostics run has no effect on the result — findings are sorted by
identity before they are returned — so nothing here can become load-bearing by
accident.
"""
from __future__ import annotations

from typing import Optional

from . import patterns
from .metrics import measure
from .model import DocumentStructure, StyleAnalysis, StyleFinding, StyleMetrics, text_hash
from .policy import STYLE_POLICY_VERSION, policy_hash

#: Severity order for sorting. Strongest first, so a reader sees the thing most
#: worth looking at without scrolling.
_ORDER = {"strong": 0, "notice": 1, "info": 2}


def analyze(text: str, structure: Optional[DocumentStructure] = None) -> StyleAnalysis:
    """Measure a document and report what is unusual about how it is written.

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

    findings = tuple(
        sorted(
            (finding for finding in found if finding is not None),
            key=lambda item: (_ORDER[item.severity], item.id),
        )
    )

    # Surface-template counts are metrics rather than findings: repeating "This
    # demonstrates" is already caught by the opener diagnostic, and a second
    # finding for the same text would be noise.
    enriched = dict(metrics.values)
    for name, count in patterns.surface_template_counts(text).items():
        enriched[f"template_{name.replace('-', '_')}"] = count

    return StyleAnalysis(
        document_hash=text_hash(text),
        policy_version=STYLE_POLICY_VERSION,
        policy_hash=policy_hash(),
        metrics=StyleMetrics(values=enriched),
        findings=findings,
    )
