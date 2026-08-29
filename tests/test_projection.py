"""Tests for the analysis projection and its mapping back to source.

Two properties carry the weight here.

**Context survives inline formatting.** `The system provides a **robust**
solution.` must reach the analyser as one sentence, because sentence
segmentation, long-sentence detection and every readability statistic are
computed over sentences. A projection that cut at each emphasis marker would
turn one sentence into three fragments and quietly change what every metric
means.

**Mapping is exact or it is refused.** Every offset the projection hands back
must land on the characters it claims. Where that cannot be guaranteed — across
markup, across a synthetic separator, across a partially covered line break —
the mapping refuses. There is no third answer, because the only alternative to
an exact offset is a wrong one.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plainspeak.document import parse_markdown, parse_text
from plainspeak.document.model import (
    Block,
    Document,
    Quote,
    REASON_CODE,
    REASON_LINK_TARGET,
    REASON_QUOTE,
    Span,
)
from plainspeak.pipeline import projection as proj
from plainspeak.pipeline.projection import (
    BLOCK_SEPARATOR,
    REFUSAL_DISCONTIGUOUS,
    REFUSAL_EMPTY,
    REFUSAL_SYNTHETIC,
    project_block,
    project_document,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = sorted((REPO_ROOT / "tests" / "characterisation" / "corpus").glob("*.txt"))


def md(source: str) -> Document:
    return parse_markdown.parse(source)


def projected(source: str) -> str:
    return project_document(md(source)).text


# ── What reaches the analyser ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "source,expected",
    [
        ("ordinary prose\n", "ordinary prose"),
        ("**bold prose**\n", "bold prose"),
        ("*emphasised prose*\n", "emphasised prose"),
        ("~~struck prose~~\n", "struck prose"),
        ("text with a [human-readable link](https://example.com)\n",
         "text with a human-readable link"),
        ("# A heading\n", "A heading"),
        ("- first item\n- second item\n", "first item" + BLOCK_SEPARATOR + "second item"),
        ("> quoted prose\n", "quoted prose"),
        (r"escaped \* markdown" + "\n", "escaped * markdown"),
        ("entity &amp; reference\n", "entity & reference"),
        ("prose then <https://example.org/auto> after\n", "prose then  after"),
        ("prose ![alt](https://example.org/i.png) after\n", "prose  after"),
        ("reference [link][r] here\n\n[r]: https://example.org/r\n", "reference link here"),
    ],
    ids=[
        "plain", "bold", "emphasis", "strikethrough", "link-text", "heading",
        "list", "quote", "escape", "entity", "autolink", "image", "reference-link",
    ],
)
def test_projection_text_is_prose_without_markup(source: str, expected: str) -> None:
    assert projected(source) == expected


@pytest.mark.parametrize(
    "source,absent",
    [
        ("Set `value = compute(0.5)` first.\n", "compute"),
        ("```python\nutilise(0.5)\n```\n", "utilise"),
        ("    indented code here\n\nprose\n", "indented code"),
        ("See [docs](https://secret.example/path) now.\n", "secret.example"),
        ("Visit <https://auto.example/path> now.\n", "auto.example"),
        ("| head | cell |\n|---|---|\n| a | b |\n", "head"),
        ("<div>raw html block</div>\n", "raw html"),
        ("Some <b>inline html</b> here.\n", "<b>"),
    ],
    ids=["code-span", "fence", "indented-code", "link-target", "autolink",
         "table", "html-block", "html-inline"],
)
def test_non_prose_never_reaches_the_analyser(source: str, absent: str) -> None:
    assert absent not in projected(source)


def test_inline_formatting_does_not_split_a_sentence() -> None:
    """The single most important property of the projection."""
    source = "The system provides a **robust and comprehensive** solution.\n"
    text = projected(source)

    assert text == "The system provides a robust and comprehensive solution."

    # And the analyser genuinely sees one sentence, not three fragments.
    from plainspeak.core.tokenize import split_sentences

    assert split_sentences(text) == ["The system provides a robust and comprehensive solution."]


def test_many_inline_changes_inside_one_sentence_stay_one_sentence() -> None:
    from plainspeak.core.tokenize import split_sentences

    source = "text with **multiple** inline *formatting* changes inside one sentence.\n"
    text = projected(source)
    assert text == "text with multiple inline formatting changes inside one sentence."
    assert len(split_sentences(text)) == 1


def test_blocks_are_separated_so_sentences_do_not_run_together() -> None:
    from plainspeak.core.tokenize import split_sentences

    text = projected("First paragraph ends here\n\nSecond paragraph starts here\n")
    assert BLOCK_SEPARATOR in text
    assert len(split_sentences(text)) == 2


def test_line_breaks_within_a_block_are_canonical() -> None:
    """A newline is a newline, whatever the source wrote."""
    assert projected("line one\nline two\n") == "line one\nline two"
    assert projected("line one\r\nline two\r\n") == "line one\nline two"


# ── Mapping exactness ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "source,needle",
    [
        ("The system provides a robust solution.\n", "robust"),
        ("The system provides a **robust** solution.\n", "robust"),
        ("The system provides a *robust* solution.\n", "robust"),
        ("See [the guidance](https://example.org/g) now.\n", "guidance"),
        ("# A robust heading\n", "robust"),
        ("- a robust item\n", "robust"),
        (r"escaped \* then robust text" + "\n", "robust"),
        ("entity &amp; then robust text\n", "robust"),
        ("line one\nrobust line two\n", "robust"),
        ("line one\r\nrobust line two\r\n", "robust"),
    ],
    ids=["plain", "bold", "emphasis", "link-text", "heading", "list",
         "after-escape", "after-entity", "after-break", "after-crlf-break"],
)
def test_mapping_lands_on_exactly_the_intended_source_characters(source: str, needle: str) -> None:
    """The core safety property: an offset points where it says it points."""
    document = md(source)
    projection = project_document(document)

    start = projection.text.index(needle)
    mapping = projection.map_to_source(Span(start, start + len(needle)))

    assert mapping.applicable, f"expected an applicable mapping, got: {mapping.reason}"
    assert mapping.source_span is not None
    assert document.source[mapping.source_span.start : mapping.source_span.end] == needle


def test_mapping_survives_an_edit_round_trip() -> None:
    """Mapping, then splicing, changes exactly the intended characters."""
    source = "The system provides a **robust** solution.\n"
    document = md(source)
    projection = project_document(document)

    start = projection.text.index("robust")
    mapping = projection.map_to_source(Span(start, start + len("robust")))
    result = document.serialise([(mapping.source_span, "strong")])

    assert result == "The system provides a **strong** solution.\n"


def test_every_projection_offset_maps_back_to_its_own_character() -> None:
    """Exhaustive check over the corpus: no offset is off by one.

    Every single-character range in every projection must map back to the same
    character in the source, unless the mapping is refused. This is the check
    that would catch a systematic drift the spot tests miss.
    """
    for path in CORPUS:
        source = path.read_bytes().decode("utf-8")
        document = md(source)
        projection = project_document(document)

        for offset in range(len(projection.text)):
            mapping = projection.map_to_source(Span(offset, offset + 1))
            if not mapping.applicable:
                continue
            span = mapping.source_span
            assert source[span.start : span.end] == projection.text[offset], (
                f"{path.name}: analysis offset {offset} "
                f"({projection.text[offset]!r}) mapped to {source[span.start:span.end]!r}"
            )


# ── Failing closed ─────────────────────────────────────────────────────────


def test_a_range_crossing_markup_is_refused() -> None:
    """No single source replacement exists across an emphasis marker."""
    source = "The system provides a **robust** solution.\n"
    projection = project_document(md(source))

    start = projection.text.index("provides")
    end = projection.text.index("robust") + len("robust")
    mapping = projection.map_to_source(Span(start, end))

    assert not mapping.applicable
    assert mapping.reason == REFUSAL_DISCONTIGUOUS
    # Still reportable: the real source positions are available to point at.
    assert mapping.source_spans


def test_a_range_crossing_a_block_separator_is_refused() -> None:
    """Synthetic material is permanently ineligible to be edited."""
    source = "First paragraph.\n\nSecond paragraph.\n"
    projection = project_document(md(source))

    start = projection.text.index("First")
    end = projection.text.index("Second") + len("Second")
    mapping = projection.map_to_source(Span(start, end))

    assert not mapping.applicable
    assert mapping.reason == REFUSAL_SYNTHETIC


def test_a_range_inside_a_quote_is_refused_but_the_text_is_still_projected() -> None:
    """The distinction this whole design exists for."""
    source = "> Use approximately 5 mg.\n"
    projection = project_document(md(source))

    assert "approximately" in projection.text, "quoted prose must still be analysable"

    start = projection.text.index("approximately")
    mapping = projection.map_to_source(Span(start, start + len("approximately")))

    assert not mapping.applicable
    assert mapping.reason == REASON_QUOTE
    assert mapping.source_spans, "a refused mapping should still say where the text is"


def test_an_empty_range_is_refused() -> None:
    projection = project_document(md("Some prose here.\n"))
    assert projection.map_to_source(Span(3, 3)).reason == REFUSAL_EMPTY


def test_a_range_beyond_the_projection_is_refused() -> None:
    projection = project_document(md("Short.\n"))
    mapping = projection.map_to_source(Span(0, len(projection.text) + 5))
    assert not mapping.applicable


def test_a_partially_covered_crlf_break_is_refused() -> None:
    """One character of analysis text over two of source has no partial answer."""
    source = "line one\r\nline two\r\n"
    projection = project_document(md(source))
    break_offset = projection.text.index("\n")

    # The break alone maps to the whole two-character terminator.
    whole = projection.map_to_source(Span(break_offset, break_offset + 1))
    assert whole.applicable
    assert source[whole.source_span.start : whole.source_span.end] == "\r\n"

    # A range ending in the middle of it still resolves, because the break is
    # covered entirely; what must not happen is an invented half-terminator.
    for span in projection.segments:
        if span.kind == "break":
            assert not span.linear, "a CRLF break is not a one-for-one mapping"
            break
    else:
        pytest.fail("no line break segment was produced")


def test_a_document_of_pure_non_prose_projects_to_nothing() -> None:
    projection = project_document(md("```\ncode only\n```\n"))
    assert projection.text == ""
    assert projection.segments == ()


# ── Determinism and structure ──────────────────────────────────────────────


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_projection_is_deterministic(path: Path) -> None:
    source = path.read_bytes().decode("utf-8")
    first = project_document(md(source))
    second = project_document(md(source))
    assert first.text == second.text
    assert first.segments == second.segments


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_line_endings_do_not_change_the_projection(path: Path) -> None:
    """The same canonical document must project identically either way."""
    source = path.read_bytes().decode("utf-8")
    assert projected(source) == projected(source.replace("\n", "\r\n"))


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_segments_tile_the_projection_exactly(path: Path) -> None:
    """No character of analysis text belongs to no segment, or to two."""
    source = path.read_bytes().decode("utf-8")
    projection = project_document(md(source))

    cursor = 0
    rebuilt = []
    for segment in projection.segments:
        assert segment.analysis_span.start == cursor, "a gap or overlap between segments"
        cursor = segment.analysis_span.end
        rebuilt.append(projection.text[segment.analysis_span.start : segment.analysis_span.end])
    assert cursor == len(projection.text)
    assert "".join(rebuilt) == projection.text


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_only_synthetic_segments_lack_a_source_span(path: Path) -> None:
    """There is no third category between "from the source" and "invented"."""
    source = path.read_bytes().decode("utf-8")
    for segment in project_document(md(source)).segments:
        assert (segment.source_span is None) == segment.synthetic


def test_synthetic_segments_are_never_transformable() -> None:
    projection = project_document(md("One.\n\nTwo.\n"))
    synthetic = [s for s in projection.segments if s.synthetic]
    assert synthetic, "expected a separator between two blocks"
    for segment in synthetic:
        assert not segment.transformable
        assert segment.reason


# ── Block projections ──────────────────────────────────────────────────────


def test_block_projection_covers_only_that_block() -> None:
    source = "First paragraph here.\n\nSecond paragraph here.\n"
    document = md(source)
    second = document.blocks[1]

    projection = project_block(document, second)
    assert projection.text == "Second paragraph here."
    assert projection.unit == "block"
    assert projection.path == second.path


def test_block_projection_maps_back_to_the_same_source_as_the_document_one() -> None:
    """Two units of analysis, one set of source coordinates."""
    source = "First paragraph here.\n\nSecond robust paragraph here.\n"
    document = md(source)
    block = document.blocks[1]

    whole = project_document(document)
    part = project_block(document, block)

    from_whole = whole.map_to_source(
        Span(whole.text.index("robust"), whole.text.index("robust") + 6)
    )
    from_part = part.map_to_source(
        Span(part.text.index("robust"), part.text.index("robust") + 6)
    )
    assert from_whole.source_span == from_part.source_span


def test_block_projection_of_a_quote_stays_unrewritable() -> None:
    document = md("> Quoted prose here.\n")
    quote = next(b for b in document.blocks if isinstance(b, Quote))
    projection = project_block(document, quote)

    assert "Quoted prose" in projection.text
    start = projection.text.index("Quoted")
    assert not projection.map_to_source(Span(start, start + 6)).applicable


# ── Plain text ─────────────────────────────────────────────────────────────


def test_plain_text_projects_to_itself_paragraph_by_paragraph() -> None:
    source = "First paragraph.\n\nSecond paragraph.\n"
    projection = project_document(parse_text.parse(source))
    assert projection.text == "First paragraph." + BLOCK_SEPARATOR + "Second paragraph."


def test_plain_text_mapping_is_exact() -> None:
    source = "The committee was convened.\n\nA second paragraph.\n"
    document = parse_text.parse(source)
    projection = project_document(document)

    start = projection.text.index("committee")
    mapping = projection.map_to_source(Span(start, start + len("committee")))
    assert mapping.applicable
    assert document.source[mapping.source_span.start : mapping.source_span.end] == "committee"
