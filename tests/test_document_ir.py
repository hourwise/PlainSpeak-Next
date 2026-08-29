"""Tests for the document intermediate representation.

The gate for this phase is that parsing and serialising an unedited document
returns the input unchanged. That is necessary but nowhere near sufficient: a
parser that produced no nodes at all would pass it. So these tests also check
the property that makes the representation *useful* — that every node's span
really does point at the source it claims, and that the spans offered up as
editable exclude everything that must not be edited.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plainspeak.document import load, parse_markdown, parse_text
from plainspeak.document.model import (
    CodeBlock,
    Document,
    Quote,
    REASON_UNLOCATABLE,
    Span,
    Text,
    content_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = sorted((REPO_ROOT / "tests" / "characterisation" / "corpus").glob("*.txt"))
MARKDOWN_FILES = sorted(REPO_ROOT.glob("*.md")) + [
    REPO_ROOT / "tests" / "characterisation" / "formats" / "sample.md",
    REPO_ROOT / "tests" / "characterisation" / "README.md",
]

PARSERS = {"text": parse_text.parse, "markdown": parse_markdown.parse}


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


# ── The phase gate ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
@pytest.mark.parametrize("parser", sorted(PARSERS), ids=lambda name: name)
def test_round_trip_preserves_corpus_exactly(parser: str, path: Path) -> None:
    """Parse then serialise returns the input byte for byte."""
    source = read(path)
    assert PARSERS[parser](source).serialise() == source


@pytest.mark.parametrize("path", MARKDOWN_FILES, ids=lambda p: p.name)
def test_round_trip_preserves_real_markdown(path: Path) -> None:
    """Real documents, not just fixtures — including this repo's own docs."""
    source = read(path)
    assert parse_markdown.parse(source).serialise() == source


@pytest.mark.parametrize(
    "source",
    [
        "",
        "   \n\n\t \n",
        "one paragraph",
        "no trailing newline",
        "trailing newline\n",
        "\n\n\nleading blank lines",
        "windows\r\nline\r\nendings\r\n\r\nsecond paragraph\r\n",
        "unicode — em dash, “quotes”, café, 21 °C\n",
        "* not a list\\* really\n",
        "| a | b |\n|---|---|\n| 1 | 2 |\n",
        "```\nunterminated fence\n",
        "> quote\n> continued\n\nafter\n",
        "# heading\n\n- a\n- b\n\n1. one\n2. two\n",
        "<div>\n  <p>raw html block</p>\n</div>\n",
        "text with a <https://example.org/auto> link\n",
        "text with an ![image](https://example.org/i.png) in it\n",
        "reference [link][ref]\n\n[ref]: https://example.org/r\n",
    ],
    ids=[
        "empty", "whitespace", "one-paragraph", "no-trailing-newline",
        "trailing-newline", "leading-blanks", "crlf", "unicode", "escape",
        "table", "unterminated-fence", "blockquote", "lists", "html-block",
        "autolink", "image", "reference-link",
    ],
)
@pytest.mark.parametrize("parser", sorted(PARSERS), ids=lambda name: name)
def test_round_trip_preserves_edge_cases(parser: str, source: str) -> None:
    assert PARSERS[parser](source).serialise() == source


# ── Span integrity ─────────────────────────────────────────────────────────


def all_documents():
    """Every (label, source, document) pair the span checks apply to."""
    for path in CORPUS:
        source = read(path)
        for name, parse in PARSERS.items():
            yield f"{path.stem}:{name}", source, parse(source)
    for path in MARKDOWN_FILES:
        source = read(path)
        yield f"{path.name}:markdown", source, parse_markdown.parse(source)


DOCUMENTS = list(all_documents())


@pytest.mark.parametrize("label,source,document", DOCUMENTS, ids=[d[0] for d in DOCUMENTS])
def test_every_span_lies_within_the_source(label, source: str, document: Document) -> None:
    for node in document.walk():
        assert 0 <= node.span.start <= node.span.end <= len(source), (
            f"{type(node).__name__} at {node.location} has span "
            f"[{node.span.start}, {node.span.end}) outside a {len(source)}-character source"
        )


@pytest.mark.parametrize("label,source,document", DOCUMENTS, ids=[d[0] for d in DOCUMENTS])
def test_every_located_node_still_hashes_to_its_source(label, source: str, document: Document) -> None:
    """A node's recorded hash must match the source it points at.

    This is the check that would catch an off-by-one in span arithmetic, which
    is otherwise invisible: the document still round-trips, and the wrong text
    just quietly gets edited.
    """
    for node in document.walk():
        if node.original_hash:
            assert node.verify(source), (
                f"{type(node).__name__} at {node.location} points at "
                f"{node.span.text(source)[:60]!r}, which is not what it recorded"
            )


@pytest.mark.parametrize("label,source,document", DOCUMENTS, ids=[d[0] for d in DOCUMENTS])
def test_text_nodes_hold_the_text_they_point_at(label, source: str, document: Document) -> None:
    for node in document.walk():
        if isinstance(node, Text) and node.transformable:
            assert node.span.text(source) == node.text, (
                f"text node at {node.location} claims {node.text[:40]!r} "
                f"but its span covers {node.span.text(source)[:40]!r}"
            )


@pytest.mark.parametrize("label,source,document", DOCUMENTS, ids=[d[0] for d in DOCUMENTS])
def test_prose_spans_are_ordered_and_disjoint(label, source: str, document: Document) -> None:
    """Overlapping editable spans would make a transformation plan ambiguous."""
    spans = document.prose_spans()
    for earlier, later in zip(spans, spans[1:]):
        assert earlier.end <= later.start, (
            f"prose spans overlap or are out of order: "
            f"[{earlier.start}, {earlier.end}) then [{later.start}, {later.end})"
        )


@pytest.mark.parametrize("label,source,document", DOCUMENTS, ids=[d[0] for d in DOCUMENTS])
def test_children_are_contained_by_their_parents(label, source: str, document: Document) -> None:
    def check(node) -> None:
        for child in node.children():
            if child.original_hash and node.original_hash:
                assert node.span.contains(child.span), (
                    f"{type(child).__name__} at {child.location} "
                    f"[{child.span.start}, {child.span.end}) escapes its parent "
                    f"{type(node).__name__} [{node.span.start}, {node.span.end})"
                )
            check(child)

    for block in document.blocks:
        check(block)


# ── What must not be edited ────────────────────────────────────────────────


def test_code_quotes_and_tables_are_not_prose() -> None:
    source = read(REPO_ROOT / "tests" / "characterisation" / "formats" / "sample.md")
    document = parse_markdown.parse(source)
    prose = "\n".join(document.text_of(span) for span in document.prose_spans())

    assert "compute(0.5)" not in prose, "a fenced code block was offered as prose"
    assert "should not be rewritten" not in prose, "quoted material was offered as prose"
    assert "|---|" not in prose, "table structure was offered as prose"
    assert "https://example.org/guidance" not in prose, "a link destination was offered as prose"

    # And the structure is actually recognised, rather than merely absent.
    kinds = {type(block).__name__ for block in document.blocks}
    assert {"CodeBlock", "Quote", "Table", "Heading", "Paragraph", "ListBlock"} <= kinds


@pytest.mark.parametrize(
    "source,forbidden",
    [
        ("Set `rm -rf /` carefully.", "rm -rf /"),
        ("See [docs](https://example.org/secret-path) now.", "secret-path"),
        ("Visit <https://example.org/auto-path> today.", "auto-path"),
        ("An ![image](https://example.org/pic.png) here.", "pic.png"),
        ("    indented code block\n\nprose after\n", "indented code block"),
        ("~~~\nfenced with tildes\n~~~\n", "fenced with tildes"),
    ],
    ids=["code-span", "link-target", "autolink", "image", "indented-code", "tilde-fence"],
)
def test_non_prose_never_reaches_the_editable_spans(source: str, forbidden: str) -> None:
    document = parse_markdown.parse(source)
    prose = "\n".join(document.text_of(span) for span in document.prose_spans())
    assert forbidden not in prose


def test_quote_contents_are_parsed_but_not_editable() -> None:
    """Analysis should still see inside a quote; only editing is refused."""
    document = parse_markdown.parse("> The committee was convened.\n\nOrdinary prose.\n")
    quote = next(b for b in document.blocks if isinstance(b, Quote))

    assert not quote.transformable
    assert quote.untransformable_reason
    # The prose inside is still represented, so an analyser can report on it.
    inner = [n for n in quote.walk() if isinstance(n, Text)]
    assert inner and "committee" in inner[0].text
    # But it is not offered up for rewriting.
    assert "committee" not in "".join(
        document.text_of(span) for span in document.prose_spans()
    )


# ── Failing safe ───────────────────────────────────────────────────────────


def test_a_failed_lookup_stops_the_scanner_permanently() -> None:
    """Once the scan has lost its place, every later offset is suspect.

    Resuming after a miss would be worse than stopping: the tokens that follow
    would be located at plausible-looking but wrong offsets, and an edit at a
    wrong offset corrupts the document silently.
    """
    from plainspeak.document.parse_markdown import _Scanner

    source = "some prose here"
    scanner = _Scanner(source, Span(0, len(source)))
    assert scanner.locate("some") is not None
    assert scanner.locate("nowhere in this string") is None
    assert scanner.lost, "a failed lookup must put the scanner into the lost state"
    assert scanner.locate("prose") is None, "a lost scanner must not resume locating"


def test_an_unlocatable_block_is_refused_rather_than_guessed_at(monkeypatch) -> None:
    """A block containing an unlocatable node offers no prose at all.

    No real Markdown construct currently defeats the scanner — escapes,
    entities, autolinks and reference links are all handled — so the failure
    has to be forced to test that the refusal path works. It is the path that
    matters most: it is what stands between a parser bug and a corrupted
    document, and it would otherwise only ever run in production.
    """
    from plainspeak.document import parse_markdown as pm

    original = pm._Scanner.locate

    def failing(self, needle: str):
        if needle and "convened" in needle:
            self.lost = True
            return None
        return original(self, needle)

    monkeypatch.setattr(pm._Scanner, "locate", failing)

    source = """The committee was convened.

A second paragraph survives.
"""
    document = pm.parse(source)

    first, second = document.blocks
    assert not first.transformable
    assert first.untransformable_reason == REASON_UNLOCATABLE

    prose = "".join(document.text_of(span) for span in document.prose_spans())
    assert "convened" not in prose, "an unlocatable block was still offered for editing"
    assert "second paragraph survives" in prose, "one bad block took out the whole document"
    assert document.serialise() == source


def test_scanner_never_moves_backwards() -> None:
    """Out-of-order tokens mean the scan has desynchronised from the source."""
    from plainspeak.document.parse_markdown import _Scanner

    source = "alpha beta alpha"
    scanner = _Scanner(source, Span(0, len(source)))
    first = scanner.locate("alpha")
    second = scanner.locate("beta")
    third = scanner.locate("alpha")
    assert first.start == 0
    assert second.start > first.end
    assert third.start > second.end, "the second 'alpha' must be found, not the first"


def test_empty_and_whitespace_documents_parse_without_raising() -> None:
    """Contrast with the inherited analyser, which raises on empty input."""
    for source in ("", "   ", "\n\n\n", "\t \r\n"):
        for parse in PARSERS.values():
            document = parse(source)
            assert document.blocks == []
            assert document.prose_spans() == []
            assert document.serialise() == source


# ── Editing through the representation ─────────────────────────────────────


def test_replacing_every_prose_span_with_itself_is_the_identity() -> None:
    """The strongest available check that the spans are exactly right.

    If any span were off by a character, or overlapped its neighbour, splicing
    each one back over itself would not reproduce the source.
    """
    for path in CORPUS + MARKDOWN_FILES:
        source = read(path)
        document = parse_markdown.parse(source)
        replacements = [(span, document.text_of(span)) for span in document.prose_spans()]
        assert document.serialise(replacements) == source, f"identity splice failed for {path.name}"


def test_replacement_edits_only_the_span_it_names() -> None:
    source = "The committee was convened.\n\nSee `code` here.\n"
    document = parse_markdown.parse(source)
    target = next(
        span for span in document.prose_spans() if "committee" in document.text_of(span)
    )
    result = document.serialise([(target, "The panel met.")])
    assert result == "The panel met.\n\nSee `code` here.\n"


def test_overlapping_replacements_are_rejected() -> None:
    """Two edits to the same characters have no defined result."""
    document = parse_text.parse("The committee was convened.")
    with pytest.raises(ValueError, match="overlapping"):
        document.serialise([(Span(4, 13), "panel"), (Span(8, 20), "group")])


def test_replacements_are_applied_independently_of_their_order() -> None:
    """Later edits must not be shifted by earlier ones."""
    document = parse_text.parse("alpha beta gamma")
    forwards = document.serialise([(Span(0, 5), "A"), (Span(11, 16), "G")])
    backwards = document.serialise([(Span(11, 16), "G"), (Span(0, 5), "A")])
    assert forwards == backwards == "A beta G"


# ── Loading ────────────────────────────────────────────────────────────────


def test_markdown_files_get_the_markdown_parser() -> None:
    formats = REPO_ROOT / "tests" / "characterisation" / "formats"
    assert load.format_for(formats / "sample.md") == "markdown"
    assert load.format_for(formats / "sample.txt") == "text"
    # A format with no structured parser degrades to text rather than pretending.
    assert load.format_for(formats / "sample.docx") == "text"


def test_load_reads_and_parses_a_file() -> None:
    formats = REPO_ROOT / "tests" / "characterisation" / "formats"
    document = load.load(formats / "sample.md")
    assert document.source_format == "markdown"
    assert document.serialise() == read(formats / "sample.md")
    assert any(isinstance(block, CodeBlock) for block in document.blocks)


def test_document_records_its_own_provenance() -> None:
    document = parse_markdown.parse("Some prose.\n")
    assert "markdown-it-py" in document.provenance
    assert document.source_hash == content_hash("Some prose.\n")
    for node in document.walk():
        if node.original_hash:
            assert node.provenance, f"{type(node).__name__} has no provenance recorded"
