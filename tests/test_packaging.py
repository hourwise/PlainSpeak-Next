"""Guards against the syllable dictionary silently disappearing.

`plainspeak/core/syllable_data.bin` is a 1.8 MB marshal blob holding CMU
pronunciation-derived syllable counts for 125,000 words. When it is present,
syllable counting is a dictionary lookup. When it is absent, `count_syllables`
falls back to a vowel-group heuristic — and says nothing about it. Every
readability metric shifts, quietly, and the tests that check "a grade level was
produced" all still pass.

That is exactly what happened before Phase 2: `pyproject.toml` declared no
package data, so the file was omitted from built wheels while editable installs
kept working perfectly. The defect was invisible to everyone developing on the
project and would have shipped to everyone using it.

These tests are cheap and they run everywhere. The wheel and sdist are checked
separately by the `package` job in CI, which builds them for real.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = REPO_ROOT / "plainspeak" / "core" / "syllable_data.bin"

#: The CMU dictionary has roughly 125,000 entries. A file that loaded but held
#: only a handful of words would pass a mere existence check while behaving
#: like no dictionary at all.
MINIMUM_ENTRIES = 100_000


def test_the_syllable_dictionary_is_present() -> None:
    assert DATA_FILE.exists(), (
        f"{DATA_FILE.name} is missing; syllable counting has silently fallen back "
        f"to the heuristic and every readability metric has shifted"
    )


def test_the_syllable_dictionary_actually_loads() -> None:
    from plainspeak.core.syllables import get_syllable_count

    counts = get_syllable_count()
    assert len(counts) >= MINIMUM_ENTRIES, (
        f"the syllable dictionary holds {len(counts)} entries, expected at least "
        f"{MINIMUM_ENTRIES}"
    )
    # Spot-check words whose heuristic answer differs from the dictionary's.
    assert counts["business"] == 2, "expected the dictionary, not the heuristic"


def test_the_dictionary_path_is_used_rather_than_the_heuristic() -> None:
    """Prove the lookup is live, not merely that a file exists somewhere."""
    from plainspeak.core.tokenize import _count_syllables_heuristic, count_syllables

    # "business" is two syllables; a naive vowel-group count says three.
    assert count_syllables("business") == 2
    assert _count_syllables_heuristic("business") != 2, (
        "this test no longer distinguishes the dictionary from the heuristic; "
        "pick a different word"
    )


def test_packaging_declares_the_data_file() -> None:
    """The configuration that stops it being dropped from a built wheel.

    A refactor that moved the package layout and forgot this line would
    reintroduce the original defect exactly, and nothing else in the suite
    would notice.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]

    patterns = package_data.get("plainspeak.core", [])
    assert any(pattern.endswith(".bin") or pattern == "*" for pattern in patterns), (
        "pyproject.toml no longer ships plainspeak.core data files; the syllable "
        f"dictionary would be dropped from built wheels. Found: {package_data}"
    )
