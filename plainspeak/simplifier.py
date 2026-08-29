"""Barrier detection and vocabulary substitution.

This module moved when the engine was split into layers. It is kept as a
compatibility shim so that existing callers — and the characterisation
seal, which must keep testing the same entry points across the refactor —
go on working unchanged.

New code should import from the layer directly.
"""

from .integrity.protected import (
    PROTECTED_TERMS,
    get_protected_domain,
    is_protected_term,
)
from .core.lexicon import (
    STEM_EXCEPTIONS,
    SUFFIXES_TO_STRIP,
    find_glossary_match,
    stem_word,
)
from .core.barriers import (
    ADJECTIVAL_PARTICIPLES,
    BARRIER_CONFIDENCE,
    BARRIER_LABELS,
    BARRIER_PRIORITY,
    Barrier,
    HIDDEN_VERB_PATTERNS,
    NOMINALIZATION_EXCEPTIONS,
    NOMINALIZATION_PATTERN,
    PASSIVE_PATTERNS,
    REDUNDANT_PAIRS,
    SimplificationResult,
    _build_recommendation,
    _deduplicate_barriers,
    _is_real_word,
    _nominalization_to_verb,
    _noun_to_verb,
    analyze_simplification,
    build_top_improvements,
    find_complex_words,
    find_hidden_verbs,
    find_jargon,
    find_long_sentences,
    find_nominalizations,
    find_passive_voice,
    find_redundant_pairs,
    get_barrier_confidence,
    get_barrier_label,
    get_barrier_priority,
    group_barriers_by_sentence,
)
from .core.transform import generate_simplified_text
from .core.tokenize import (
    count_syllables,
    split_sentences,
    split_words,
)
from .core.glossary import (
    GLOSSARY,
    SIMPLE_WORD_MAP,
)

__all__ = [
    "ADJECTIVAL_PARTICIPLES",
    "BARRIER_CONFIDENCE",
    "BARRIER_LABELS",
    "BARRIER_PRIORITY",
    "Barrier",
    "GLOSSARY",
    "HIDDEN_VERB_PATTERNS",
    "NOMINALIZATION_EXCEPTIONS",
    "NOMINALIZATION_PATTERN",
    "PASSIVE_PATTERNS",
    "PROTECTED_TERMS",
    "REDUNDANT_PAIRS",
    "SIMPLE_WORD_MAP",
    "STEM_EXCEPTIONS",
    "SUFFIXES_TO_STRIP",
    "SimplificationResult",
    "analyze_simplification",
    "build_top_improvements",
    "count_syllables",
    "find_complex_words",
    "find_glossary_match",
    "find_hidden_verbs",
    "find_jargon",
    "find_long_sentences",
    "find_nominalizations",
    "find_passive_voice",
    "find_redundant_pairs",
    "generate_simplified_text",
    "get_barrier_confidence",
    "get_barrier_label",
    "get_barrier_priority",
    "get_protected_domain",
    "group_barriers_by_sentence",
    "is_protected_term",
    "split_sentences",
    "split_words",
    "stem_word",
]
