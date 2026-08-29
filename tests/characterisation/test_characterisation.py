"""The characterisation seal.

These tests do not check that PlainSpeak is *right*. They check that it still
behaves exactly as it did at the fork point, so that the architectural work in
later phases cannot change established behaviour by accident.

A failure here means one of two things:

  1. A refactor changed behaviour unintentionally — fix the code, not the
     golden file; or
  2. behaviour was changed deliberately — regenerate the goldens with
     `python -m tests.characterisation.capture --write` and commit the diff
     alongside the change, so the review shows exactly what moved.

Never regenerate the goldens to make a red test go green without reading the
diff first. That is the one thing that would make this whole suite worthless.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from . import capture

# Golden payloads that are not derived from a corpus document.
SYNTHETIC_GOLDENS = ["_globals", "_readers"]

CORPUS_NAMES = [path.stem for path in capture.corpus_files()]
ALL_GOLDEN_NAMES = SYNTHETIC_GOLDENS + CORPUS_NAMES


def _first_difference(actual: Any, expected: Any, path: str = "") -> str | None:
    """Locate the first divergence, as a readable path into the payload.

    Comparing two multi-thousand-line dicts with a bare assert produces output
    nobody can read. This walks both sides and reports one precise location,
    which is nearly always enough to see what a refactor moved.
    """
    if type(actual) is not type(expected):
        return f"{path or '<root>'}: type {type(actual).__name__} != {type(expected).__name__}"

    if isinstance(actual, dict):
        for key in sorted(set(actual) | set(expected)):
            if key not in actual:
                return f"{path}.{key}: missing from captured output"
            if key not in expected:
                return f"{path}.{key}: present in captured output but not in the golden"
            found = _first_difference(actual[key], expected[key], f"{path}.{key}")
            if found:
                return found
        return None

    if isinstance(actual, list):
        if len(actual) != len(expected):
            return f"{path}: length {len(actual)} != {len(expected)}"
        for index, (a, e) in enumerate(zip(actual, expected)):
            found = _first_difference(a, e, f"{path}[{index}]")
            if found:
                return found
        return None

    if actual != expected:
        return f"{path or '<root>'}: {actual!r} != {expected!r}"
    return None


def _built() -> dict[str, dict]:
    # Built once per session: capturing the whole corpus is cheap, but not so
    # cheap that it should happen once per parametrised case.
    if not hasattr(_built, "cache"):
        _built.cache = capture.build_all()  # type: ignore[attr-defined]
    return _built.cache  # type: ignore[attr-defined]


@pytest.mark.parametrize("name", ALL_GOLDEN_NAMES)
def test_behaviour_matches_golden(name: str) -> None:
    """Current behaviour is identical to the sealed behaviour."""
    golden_file = capture.golden_path(name)
    assert golden_file.exists(), (
        f"no golden file for {name!r}. If you added a corpus document, run:\n"
        f"    python -m tests.characterisation.capture --write"
    )

    actual = json.loads(capture.serialise(_built()[name]))
    expected = capture.load_golden(name)

    difference = _first_difference(actual, expected, "")
    assert difference is None, (
        f"behaviour changed for {name!r}\n"
        f"  first difference at {difference}\n"
        f"  if this change is intended, regenerate with:\n"
        f"    python -m tests.characterisation.capture --write"
    )


def test_every_corpus_document_is_sealed() -> None:
    """A corpus document with no golden file would be silently unprotected."""
    missing = [name for name in CORPUS_NAMES if not capture.golden_path(name).exists()]
    assert not missing, f"corpus documents with no golden file: {missing}"


def test_no_orphaned_golden_files() -> None:
    """A golden with no corpus document is dead weight that will drift."""
    expected = set(ALL_GOLDEN_NAMES)
    found = {path.stem for path in capture.GOLDEN_DIR.glob("*.json")}
    assert not (found - expected), f"golden files with no source: {sorted(found - expected)}"


def test_capture_is_deterministic_within_a_process() -> None:
    """Two captures of the same input must be byte-identical.

    Anything that varies run to run — a timestamp, a set iteration order, an
    unsorted dict — would make every golden file a slow-burning flake.
    """
    text = capture.read_corpus(capture.CORPUS_DIR / "legal-petition.txt")
    first = capture.serialise(capture.capture_document(text))
    second = capture.serialise(capture.capture_document(text))
    assert first == second


def test_report_timestamps_are_redacted() -> None:
    """The HTML report stamps the wall clock; the seal must not see it."""
    from plainspeak import analyzer, reporter

    scores = analyzer.analyze("A short sentence. Another one.")
    html = reporter.generate_report(scores, None, "A short sentence. Another one.")

    assert "<TIMESTAMP>" in capture.redact_timestamps(html), (
        "the report no longer contains a recognisable timestamp, or the "
        "redaction pattern has stopped matching it — check redact_timestamps"
    )
    assert capture.redact_timestamps(html) == capture.redact_timestamps(html)


def test_golden_files_are_canonically_serialised() -> None:
    """Goldens must be sorted, indented and LF-terminated, or diffs go noisy."""
    for name in ALL_GOLDEN_NAMES:
        path = capture.golden_path(name)
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"{path.name} contains CRLF line endings"
        text = raw.decode("utf-8")
        assert text == capture.serialise(json.loads(text)), (
            f"{path.name} is not canonically serialised; regenerate it with "
            f"python -m tests.characterisation.capture --write"
        )


def test_text_fixtures_are_lf_normalised() -> None:
    """CRLF in a fixture would seal behaviour that only holds on Windows.

    Sentence segmentation keys off blank lines, so a fixture carrying CRLF
    produces different offsets — and therefore different goldens — depending on
    which platform last touched it. `.gitattributes` marks these trees
    byte-significant; this test is the belt to that braces.
    """
    binary_suffixes = {".docx", ".pdf"}
    for directory in (capture.CORPUS_DIR, capture.FORMATS_DIR):
        for path in sorted(directory.iterdir()):
            if path.suffix in binary_suffixes or not path.is_file():
                continue
            assert b"\r\n" not in path.read_bytes(), (
                f"{path.name} contains CRLF line endings; convert it to LF before sealing"
            )
