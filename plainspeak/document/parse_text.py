"""Parsing plain text into the document representation.

Plain text has no markup to respect, so this is deliberately the simplest
parser in the system: blank lines separate paragraphs, and everything else is
prose. It exists as much to establish the contract the Markdown parser has to
meet as to handle `.txt` files.

Note what this parser does *not* do. It does not detect headings from
capitalisation, list items from leading hyphens, or code from indentation. The
inherited sentence splitter guesses at some of that, and its guesses are sealed
in the characterisation suite; but a guess about structure is not a safe basis
for editing text, so the structural claims made here are only the ones the
format actually supports.
"""
from __future__ import annotations

import re

from .model import (
    Document,
    Paragraph,
    Span,
    Text,
    content_hash,
)

PROVENANCE = "plainspeak.document.parse_text"

# A paragraph break is a newline followed by a line containing nothing but
# whitespace. Anything less — a single newline — is a wrapped line within one
# paragraph, which is how most plain-text documents are actually written.
#
# `\r` is in the character class rather than being normalised away first,
# because normalising would shift every offset after it and the offsets are the
# whole point. A Windows-authored document must parse into the same structure
# as the same document with Unix line endings.
_PARAGRAPH_BREAK = re.compile(r"\n[ \t\r]*(?:\n[ \t\r]*)+")


def parse(source: str) -> Document:
    """Parse plain text into a `Document`."""
    document = Document(
        source=source,
        source_format="text",
        provenance=PROVENANCE,
    )

    for index, (start, end) in enumerate(_paragraph_ranges(source)):
        span = Span(start, end)
        raw = span.text(source)
        text_node = Text(
            span=span,
            path=(index, 0),
            provenance=PROVENANCE,
            original_hash=content_hash(raw),
            text=raw,
        )
        document.blocks.append(
            Paragraph(
                span=span,
                path=(index,),
                provenance=PROVENANCE,
                original_hash=content_hash(raw),
                content=[text_node],
            )
        )

    return document


def _paragraph_ranges(source: str) -> list[tuple[int, int]]:
    """Character ranges of each paragraph, with surrounding whitespace excluded.

    Leading and trailing whitespace is left outside every node on purpose. A
    node's span is what an edit may replace, and an edit that swallowed the
    blank line after a paragraph would silently join it to the next one.
    """
    ranges: list[tuple[int, int]] = []
    cursor = 0

    for match in _PARAGRAPH_BREAK.finditer(source):
        _append_trimmed(ranges, source, cursor, match.start())
        cursor = match.end()
    _append_trimmed(ranges, source, cursor, len(source))

    return ranges


def _append_trimmed(
    ranges: list[tuple[int, int]], source: str, start: int, end: int
) -> None:
    chunk = source[start:end]
    if not chunk.strip():
        return
    leading = len(chunk) - len(chunk.lstrip())
    trailing = len(chunk) - len(chunk.rstrip())
    ranges.append((start + leading, end - trailing))
