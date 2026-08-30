"""Deterministic document-level style diagnostics.

A glossary sees one word at a time. It cannot see that eight of twelve
paragraphs open the same way, that one transition is doing all the work, or that
every sentence is seventeen words long — and those are what make prose read as
machinery.

This layer measures those things and reports them. It changes nothing.

**It is not an authorship detector.** PlainSpeak does not know who wrote a
document and will not guess. There is no "83% likely AI-generated" here and a
test asserts there never will be. Findings take the form "8 of 12 paragraphs
begin with 'The system'" — an observation a reader can check and disagree with.

**There is no score.** One number would compress a dozen independent
observations into something that looks authoritative while hiding its own
evidence, and it would be used as an AI detector within a week. The output is a
profile of bands, each traceable to a measurement and a threshold.

**It does not parse.** Clean prose and a small description of the document's
shape come in; the document layer does the parsing, and there is exactly one
parser in this project. Style borrows the project's sentence segmentation for
the same reason.

Style profiles — deciding that a particular band is *wrong* for a particular
kind of writing — are Phase 8. This phase establishes what can be observed.
"""

from .analyze import analyze
from .model import (
    BLOCK_KINDS,
    DocumentStructure,
    Evidence,
    Occurrence,
    ProseBlock,
    StyleAnalysis,
    StyleFinding,
    StyleMetrics,
    text_hash,
)
from .policy import (
    DIAGNOSTIC_IDS,
    MINIMUM_SAMPLES,
    SEVERITIES,
    STYLE_POLICY_VERSION,
    THRESHOLDS,
    canonical_json,
    policy_document,
    policy_hash,
    severity_for,
)
from .report import analysis_digest, analysis_to_dict, analysis_to_json

__all__ = [
    "BLOCK_KINDS",
    "DIAGNOSTIC_IDS",
    "MINIMUM_SAMPLES",
    "SEVERITIES",
    "STYLE_POLICY_VERSION",
    "THRESHOLDS",
    "DocumentStructure",
    "Evidence",
    "Occurrence",
    "ProseBlock",
    "StyleAnalysis",
    "StyleFinding",
    "StyleMetrics",
    "analysis_digest",
    "analysis_to_dict",
    "analysis_to_json",
    "analyze",
    "canonical_json",
    "policy_document",
    "policy_hash",
    "severity_for",
    "text_hash",
]
