"""Deterministic, bounded English morphology.

One job: given a lemma somebody declared and a form class, produce the
corresponding surface form. Nothing here parses documents, loads rules,
orchestrates a pipeline or knows what Markdown is.

It runs in one direction only — from a declared lemma outwards to its forms.
It never takes a surface form and tries to work out what it came from. The
inherited simplifier did exactly that, stripping suffixes and hoping, and
suggested the verb "clare" for the noun "clarity". Going forwards from a
reviewed lemma, the worst outcome is a form nobody uses; it cannot be a word
that does not exist.

Like the ruleset and the integrity policy, morphology is versioned product
behaviour with a pinned SHA-256 identity covering its irregular tables,
inflection rules, casing policy and supported form classes.

This package is an architectural leaf: it imports nothing else from PlainSpeak.
"""

from .casing import apply_shape, match_casing, shape_of
from .forms import MorphologyError, forms_for, inflected_pairs
from .policy import (
    CASE_SHAPES,
    FORM_CLASSES,
    MORPHOLOGY_VERSION,
    PARTS_OF_SPEECH,
    canonical_json,
    policy_document,
    policy_hash,
)

__all__ = [
    "CASE_SHAPES",
    "FORM_CLASSES",
    "MORPHOLOGY_VERSION",
    "PARTS_OF_SPEECH",
    "MorphologyError",
    "apply_shape",
    "canonical_json",
    "forms_for",
    "inflected_pairs",
    "match_casing",
    "policy_document",
    "policy_hash",
    "shape_of",
]
