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


def check_wheel(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if REQUIRED not in names:
            return [f"{path.name} does not contain {REQUIRED}"]
        size = archive.getinfo(REQUIRED).file_size
    if size < MINIMUM_BYTES:
        return [f"{path.name} contains {REQUIRED} but it is only {size} bytes"]
    return []


def check_sdist(path: Path) -> list[str]:
    with tarfile.open(path) as archive:
        # An sdist nests everything under a "<name>-<version>/" directory.
        entries = {
            "/".join(member.name.split("/")[1:]): member.size
            for member in archive.getmembers()
        }
    if REQUIRED not in entries:
        return [f"{path.name} does not contain {REQUIRED}"]
    if entries[REQUIRED] < MINIMUM_BYTES:
        return [f"{path.name} contains {REQUIRED} but it is only {entries[REQUIRED]} bytes"]
    return []


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
    print(f"{REQUIRED} present in {checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
