"""Confirm an *installed* PlainSpeak counts syllables from the dictionary.

Run against a fresh virtual environment that has the wheel installed, from a
directory that is not the source tree, so that the dictionary being found
proves it shipped rather than that the repository happens to be nearby.
"""
from __future__ import annotations

import sys

MINIMUM_ENTRIES = 100_000


def main() -> int:
    from plainspeak.core.syllables import get_syllable_count
    from plainspeak.core.tokenize import _count_syllables_heuristic, count_syllables

    counts = get_syllable_count()
    if len(counts) < MINIMUM_ENTRIES:
        print(f"only {len(counts)} syllable entries loaded", file=sys.stderr)
        return 1

    # "business" is two syllables; the vowel-group heuristic says otherwise, so
    # the right answer proves the dictionary is the one being consulted.
    if count_syllables("business") != 2:
        print("syllable counting fell back to the heuristic", file=sys.stderr)
        return 1
    if _count_syllables_heuristic("business") == 2:
        print("this check no longer distinguishes dictionary from heuristic", file=sys.stderr)
        return 1

    print(f"installed package loads {len(counts)} syllable entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
