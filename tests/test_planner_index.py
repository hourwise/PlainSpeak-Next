"""The segment index, and the scaling it exists to fix.

Migration took the ruleset from 38 rules to 214. Planning had been answering
"which segments does this range touch?" by scanning every segment, which is fine
when both counts are small and quadratic when they are not: a 34,000-word
document took a hundred seconds.

An index fixes the scaling. It must not fix anything else — an optimisation that
changed a single decision would be a behaviour change wearing a performance
costume — so the first test here compares it against the scan it replaced, over
every corpus document and every match the real ruleset makes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plainspeak.document import parse_markdown
from plainspeak.document.model import Span
from plainspeak.pipeline.planner import _SegmentIndex, build_plan
from plainspeak.pipeline.projection import project_document
from plainspeak.rules import find_matches, load_ruleset

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = sorted((REPO_ROOT / "tests" / "characterisation" / "corpus").glob("*.txt"))


def reference_touching(view, start: int, end: int) -> list:
    """The scan the index replaced, kept as the definition of correctness."""
    if end <= start:
        return []
    return [
        segment
        for segment in view.segments
        if segment.analysis_span.overlaps(Span(start, end))
    ]


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_the_index_agrees_with_the_scan_it_replaced(path: Path, bundled) -> None:
    """Same answer for every range the real ruleset actually asks about."""
    source = path.read_bytes().decode("utf-8")
    view = project_document(parse_markdown.parse(source))
    index = _SegmentIndex(view)

    for match in find_matches(view.text, bundled.rules):
        assert index.touching(match.start, match.end) == reference_touching(
            view, match.start, match.end
        ), f"index disagreed at [{match.start}, {match.end}) in {path.name}"


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_the_index_agrees_on_every_single_character_range(path: Path) -> None:
    """Exhaustive, not just where the rules happen to look."""
    source = path.read_bytes().decode("utf-8")
    view = project_document(parse_markdown.parse(source))
    index = _SegmentIndex(view)

    for offset in range(len(view.text)):
        assert index.touching(offset, offset + 1) == reference_touching(
            view, offset, offset + 1
        )


def test_the_index_handles_ranges_outside_the_text() -> None:
    view = project_document(parse_markdown.parse("Some prose here.\n"))
    index = _SegmentIndex(view)

    assert index.touching(0, 0) == []
    assert index.touching(5, 3) == []
    assert index.touching(len(view.text) + 10, len(view.text) + 20) == []


def test_the_index_knows_each_block_range() -> None:
    source = "First paragraph here.\n\nSecond paragraph here.\n"
    view = project_document(parse_markdown.parse(source))
    index = _SegmentIndex(view)

    for segment in view.segments:
        if segment.synthetic:
            continue
        bounds = index.block_range(segment.block_path)
        assert bounds is not None
        assert bounds[0] <= segment.analysis_span.start
        assert bounds[1] >= segment.analysis_span.end


def test_an_empty_projection_indexes_cleanly() -> None:
    view = project_document(parse_markdown.parse(""))
    index = _SegmentIndex(view)
    assert index.touching(0, 5) == []
    assert index.block_range((0,)) is None


def test_planning_work_grows_with_the_document_not_its_square(bundled) -> None:
    """A structural check, so it cannot go flaky on a loaded machine.

    Counts the segment lookups rather than the seconds. Quadratic planning shows
    up as lookups growing with the product of matches and segments; linear
    planning keeps the lookups per match roughly constant however long the
    document is.
    """
    base = (REPO_ROOT / "tests" / "characterisation" / "corpus" / "legal-petition.txt")
    source = base.read_bytes().decode("utf-8")

    ratios = []
    for factor in (1, 8):
        document = parse_markdown.parse((source + "\n\n") * factor)
        view = project_document(document)
        index = _SegmentIndex(view)

        # `_SegmentIndex` uses __slots__, so the method is counted by calling it
        # rather than by replacing it.
        matches = find_matches(view.text, bundled.rules)
        assert matches, "the fixture should produce matches"

        visited = sum(len(index.touching(match.start, match.end)) for match in matches)
        ratios.append(visited / len(matches))

    assert ratios[1] < ratios[0] * 2, (
        f"segments visited per match grew from {ratios[0]:.1f} to {ratios[1]:.1f} "
        f"as the document got eight times longer; the lookup is not bounded"
    )
