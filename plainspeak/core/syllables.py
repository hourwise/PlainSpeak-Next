"""
Pre-computed syllable counts from the CMU Pronouncing Dictionary.

Source: http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b
Words: 125068
Uses Python marshal format for fast loading (~50ms vs ~1200ms for .py).
Generated automatically — do not edit by hand.
"""

import marshal
from pathlib import Path

_SYLLABLE_COUNT: dict[str, int] | None = None


def get_syllable_count() -> dict[str, int]:
    """Return the syllable count dictionary, loading from binary on first call."""
    global _SYLLABLE_COUNT
    if _SYLLABLE_COUNT is None:
        _data_path = Path(__file__).parent / "syllable_data.bin"
        with open(_data_path, "rb") as _f:
            _SYLLABLE_COUNT = marshal.load(_f)
    return _SYLLABLE_COUNT
