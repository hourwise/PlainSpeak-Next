"""The release tooling produces artifacts that can actually be verified."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def package_release(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("package_release", ROOT / "tools" / "package_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "RELEASE", tmp_path / "release")
    (tmp_path / "release").mkdir()
    return module


def test_checksums_are_written_in_the_format_sha256sum_reads(package_release, tmp_path):
    """LF only, two spaces, a 64-character digest — on Windows too.

    The first Windows release candidate wrote CRLF, and `sha256sum --check`
    looked for files whose names ended in a carriage return.
    """
    from plainspeak import __version__

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / f"plainspeak-{__version__}-py3-none-any.whl").write_bytes(b"wheel")
    (dist / f"plainspeak-{__version__}.tar.gz").write_bytes(b"sdist")
    produced = package_release.package_python(dist)
    sums = package_release.write_sums(produced)

    raw = sums.read_bytes()
    assert b"\r" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        assert re.fullmatch(r"[0-9a-f]{64}  plainspeak-[^ ]+", line), line


def test_checksums_accumulate_without_duplicates(package_release, tmp_path):
    from plainspeak import __version__

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / f"plainspeak-{__version__}-py3-none-any.whl").write_bytes(b"wheel")
    produced = package_release.package_python(dist)
    package_release.write_sums(produced)
    sums = package_release.write_sums(produced)
    assert len(sums.read_text(encoding="utf-8").splitlines()) == 1
