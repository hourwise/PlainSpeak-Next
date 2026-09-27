"""Every classifier PlainSpeak declares is one PyPI accepts.

The first 1.0.0 publication attempt was certified, tagged and approved, and
PyPI then refused the wheel: `Intended Audience :: Government` is not a
classifier. tools/check_classifiers.py now checks the declaration and the
built metadata against PyPI's own list; these tests keep it honest.
"""
from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytest.importorskip("trove_classifiers", reason="installed with the dev extra")
tomllib = pytest.importorskip("tomllib", reason="Python 3.11+; the 3.13 jobs run this on every platform")


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location("check_classifiers", ROOT / "tools" / "check_classifiers.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata(classifiers: list[str]) -> bytes:
    lines = ["Metadata-Version: 2.4", "Name: plainspeak-next", "Version: 1.0.0"]
    return ("\n".join(lines + [f"Classifier: {item}" for item in classifiers]) + "\n\n").encode("utf-8")


def _wheel(path: Path, classifiers: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr("plainspeak_next-1.0.0.dist-info/METADATA", _metadata(classifiers))
    return path


def _sdist(path: Path, classifiers: list[str]) -> Path:
    data = _metadata(classifiers)
    with tarfile.open(path, "w:gz") as sdist:
        info = tarfile.TarInfo("plainspeak_next-1.0.0/PKG-INFO")
        info.size = len(data)
        sdist.addfile(info, io.BytesIO(data))
    return path


def test_every_declared_classifier_is_accepted_by_pypi(checker):
    known, deprecated = checker.accepted()
    declared = checker.declared(ROOT / "pyproject.toml")
    assert declared
    assert not checker.problems("pyproject.toml", declared, known, deprecated)


def test_the_classifier_pypi_refused_is_caught(checker):
    known, deprecated = checker.accepted()
    found = checker.problems("x", ["Intended Audience :: Government"], known, deprecated)
    assert found and "not a valid classifier" in found[0]


def test_built_metadata_is_checked_too(checker, tmp_path):
    """A bad classifier in a wheel or sdist fails, and so does a set that differs from the source."""
    declared = checker.declared(ROOT / "pyproject.toml")
    dist = tmp_path / "dist"
    dist.mkdir()
    _wheel(dist / "plainspeak_next-1.0.0-py3-none-any.whl", declared)
    _sdist(dist / "plainspeak_next-1.0.0.tar.gz", declared)
    assert checker.main([str(ROOT / "pyproject.toml"), str(dist)]) == 0

    _wheel(dist / "plainspeak_next-1.0.0-py3-none-any.whl", declared + ["Intended Audience :: Government"])
    assert checker.main([str(ROOT / "pyproject.toml"), str(dist)]) == 1


def test_an_empty_distribution_directory_fails(checker, tmp_path):
    assert checker.main([str(ROOT / "pyproject.toml"), str(tmp_path)]) == 1


def test_trove_classifiers_is_not_a_runtime_dependency():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not any("trove" in entry for entry in project["dependencies"])
    assert any(entry.startswith("trove-classifiers") for entry in project["optional-dependencies"]["dev"])
