"""Verify that built distributions actually contain the syllable dictionary.

Run after `python -m build`:

    python tools/check_packaged_data.py dist

Before Phase 2, `pyproject.toml` declared no package data, so
`plainspeak/core/syllable_data.bin` was omitted from built wheels. Editable
installs hid it completely: syllable counting fell back to a vowel-group
heuristic, every readability metric shifted, and nothing failed. Only the built
artefacts show this, which is why it is checked here rather than in the test
suite.
"""
from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

REQUIRED = "plainspeak/core/syllable_data.bin"
#: Rough size of the CMU-derived dictionary. A truncated or placeholder file
#: would satisfy a mere presence check while behaving like no dictionary.
MINIMUM_BYTES = 1_000_000

#: The ruleset manifest, and how many rule files must accompany it. An engine
#: installed without its rules proposes nothing and says nothing about why.
RULESET_MANIFEST = "plainspeak/rules/bundled/RULESET.yaml"
MINIMUM_RULE_FILES = 4


def _check_contents(label: str, sizes: dict[str, int]) -> list[str]:
    """Both artefact kinds are checked the same way, once unpacked to a mapping."""
    problems = []
    if REQUIRED not in sizes:
        problems.append(f"{label} does not contain {REQUIRED}")
    elif sizes[REQUIRED] < MINIMUM_BYTES:
        problems.append(f"{label} contains {REQUIRED} but it is only {sizes[REQUIRED]} bytes")

    if RULESET_MANIFEST not in sizes:
        problems.append(f"{label} does not contain {RULESET_MANIFEST}")
    rule_files = [
        name
        for name in sizes
        if name.startswith("plainspeak/rules/bundled/")
        and name.endswith(".yaml")
        and not name.endswith("RULESET.yaml")
    ]
    if len(rule_files) < MINIMUM_RULE_FILES:
        problems.append(
            f"{label} contains only {len(rule_files)} rule file(s), expected at least "
            f"{MINIMUM_RULE_FILES}"
        )
    return problems


def check_wheel(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        sizes = {item.filename: item.file_size for item in archive.infolist()}
    return _check_contents(path.name, sizes)


def check_sdist(path: Path) -> list[str]:
    with tarfile.open(path) as archive:
        # An sdist nests everything under a "<name>-<version>/" directory.
        sizes = {
            "/".join(member.name.split("/")[1:]): member.size
            for member in archive.getmembers()
        }
    return _check_contents(path.name, sizes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", nargs="?", default="dist", help="directory holding the artefacts")
    args = parser.parse_args(argv)

    dist = Path(args.dist)
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))

    if not wheels or not sdists:
        print(f"no artefacts found in {dist}/ — run `python -m build` first", file=sys.stderr)
        return 2

    failures: list[str] = []
    for wheel in wheels:
        failures += check_wheel(wheel)
    for sdist in sdists:
        failures += check_sdist(sdist)

    if failures:
        print("packaging regression:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    checked = ", ".join(path.name for path in wheels + sdists)
    print(f"syllable dictionary and bundled ruleset present in {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
