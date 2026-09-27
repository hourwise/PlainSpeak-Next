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

from pathlib import Path

import pytest

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
    # The project supports 3.10, which has no TOML parser in the standard
    # library, and this guard is not worth a dependency. The fallback reads the
    # one table it cares about; see `_package_data`.
    tomllib = None

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


def _package_data() -> dict[str, list[str]]:
    """The `[tool.setuptools.package-data]` table from pyproject.toml.

    Uses the standard-library TOML parser where there is one. On 3.10 there is
    not, and rather than take a dependency for a single table this reads the
    section directly. The fallback is narrow on purpose: it knows about one
    table and gives up loudly rather than half-understanding the file.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    if tomllib is not None:
        return tomllib.loads(text)["tool"]["setuptools"]["package-data"]

    table: dict[str, list[str]] = {}
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped == "[tool.setuptools.package-data]"
            continue
        if not inside or not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        table[key.strip().strip('"')] = [
            item.strip().strip('"').strip("'")
            for item in value.strip().strip("[]").split(",")
            if item.strip()
        ]
    assert table, "could not find [tool.setuptools.package-data] in pyproject.toml"
    return table


def test_packaging_declares_the_data_file() -> None:
    """The configuration that stops it being dropped from a built wheel.

    A refactor that moved the package layout and forgot this line would
    reintroduce the original defect exactly, and nothing else in the suite
    would notice.
    """
    package_data = _package_data()
    patterns = package_data.get("plainspeak.core", [])

    assert any(pattern.endswith(".bin") or pattern == "*" for pattern in patterns), (
        "pyproject.toml no longer ships plainspeak.core data files; the syllable "
        f"dictionary would be dropped from built wheels. Found: {package_data}"
    )


def test_packaging_declares_the_bundled_profiles() -> None:
    """The same defect shape, one layer up.

    `plainspeak/style/profiles/bundled/*.yaml` is packaged data. Omit it from
    `package-data` and every wheel installs a style layer that cannot load a
    single profile, while editable installs keep working perfectly — which is
    exactly how the syllable dictionary shipped broken before Phase 2.
    """
    package_data = _package_data()
    patterns = package_data.get("plainspeak.style.profiles", [])

    assert any("yaml" in pattern or pattern == "*" for pattern in patterns), (
        "pyproject.toml no longer ships plainspeak.style.profiles data files; the "
        f"bundled profiles would be dropped from built wheels. Found: {package_data}"
    )


def test_the_bundled_profiles_are_present() -> None:
    from plainspeak.style.profiles import BUNDLED, profile_ids

    for identifier in profile_ids():
        assert (BUNDLED / f"{identifier}.yaml").exists()


def test_the_version_is_stated_consistently_everywhere() -> None:
    """`pyproject.toml`, `plainspeak.__version__`, the Windows build spec and the
    release certification script agree.

    The version is part of every plan's identity, so a wheel reporting one
    version while the engine reports another would produce plans nobody could
    match to a release. Windows file versions are four numbers, so the spec
    carries the release without its pre-release suffix.
    """
    import re

    from plainspeak import __version__

    if tomllib is None:
        pytest.skip("needs tomllib (Python 3.11+); the 3.13 jobs run this on every platform")

    root = Path(__file__).resolve().parent.parent
    declared = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert declared == __version__

    spec = (root / "deploy" / "pysidedeploy.spec").read_text(encoding="utf-8")
    release = re.match(r"\d+\.\d+\.\d+", __version__).group(0)
    assert f"--product-version={release}.0" in spec
    assert f"--file-version={release}.0" in spec

    # The certification script pins the version independently of the package it
    # certifies — that independence is its point — so it is checked here too.
    certify = (root / "tools" / "certify_release.py").read_text(encoding="utf-8")
    assert f'EXPECTED_VERSION = "{__version__}"' in certify



def test_the_distribution_is_plainspeak_next_and_everything_else_stays_plainspeak() -> None:
    """PyPI name `plainspeak-next`; import package and command `plainspeak`.

    `plainspeak` on PyPI is an unrelated project, so the distribution needed a
    free name. Only the distribution name changed: renaming the import or the
    command would break every user of 1.0 for no benefit.
    """
    if tomllib is None:
        pytest.skip("needs tomllib (Python 3.11+); the 3.13 jobs run this on every platform")

    root = Path(__file__).resolve().parent.parent
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    assert project["name"] == "plainspeak-next"
    assert project["scripts"]["plainspeak"] == "plainspeak.adapters.cli:main"
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == ["plainspeak*"]
    assert (root / "plainspeak" / "__init__.py").is_file()


def test_the_runtime_dependencies_are_declared_where_installers_read_them() -> None:
    """A table placed in the middle of `[project]` captures the keys after it.

    Found while preparing the release candidate: `[project.urls]` inserted above
    `dependencies` made TOML read the dependency list as a URL, and the build
    refused the metadata. An installer given such a wheel would install
    PlainSpeak without click, markdown-it or PyYAML.
    """
    if tomllib is None:
        pytest.skip("needs tomllib (Python 3.11+); the 3.13 jobs run this on every platform")

    root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = {entry.split(">")[0].split("=")[0].strip().lower() for entry in project["dependencies"]}
    assert names == {"click", "markdown-it-py", "pyyaml"}
    assert all(isinstance(value, str) for value in project["urls"].values())
