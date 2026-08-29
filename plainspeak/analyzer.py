"""Readability analysis.

This module moved when the engine was split into layers. It is kept as a
compatibility shim so that existing callers — and the characterisation
seal, which must keep testing the same entry points across the refactor —
go on working unchanged.

New code should import from the layer directly.
"""

from .core.tokenize import (
    ABBREVIATIONS,
    _count_syllables_heuristic,
    count_complex_words,
    count_syllables,
    split_sentences,
    split_words,
)
from .core.metrics import (
    MAX_CREDIBLE_GRADE,
    MIN_CREDIBLE_GRADE,
    ReadabilityScores,
    _classify_difficulty_band,
    _describe_grade_level,
    analyze,
    describe_flesch_score,
)

__all__ = [
    "ABBREVIATIONS",
    "MAX_CREDIBLE_GRADE",
    "MIN_CREDIBLE_GRADE",
    "ReadabilityScores",
    "analyze",
    "count_complex_words",
    "count_syllables",
    "describe_flesch_score",
    "split_sentences",
    "split_words",
]
