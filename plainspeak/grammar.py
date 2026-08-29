"""Grammar repair after substitution.

This module moved when the engine was split into layers. It is kept as a
compatibility shim so that existing callers — and the characterisation
seal, which must keep testing the same entry points across the refactor —
go on working unchanged.

New code should import from the layer directly.
"""

from .core.morphology import (
    VOWEL_SOUND_WORDS,
    _starts_with_vowel_sound,
    fix_articles,
    fix_capitalization,
    post_process_simplified,
)

__all__ = [
    "VOWEL_SOUND_WORDS",
    "fix_articles",
    "fix_capitalization",
    "post_process_simplified",
]
