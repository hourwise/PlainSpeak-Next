"""Loading a file into the structured document representation.

This sits alongside `detect.read_auto`, which returns a flat string, rather than
replacing it. The two answer different questions:

    read_auto(path)  -> "what does this file say?"
    load(path)       -> "what is this file made of, and which parts are prose?"

Only the second can support editing. The first is what the inherited analyser
consumes, and it keeps working unchanged.

Formats that have no structured parser yet are loaded as plain text. That is an
honest degradation rather than a silent one: the resulting document records
which parser was actually used, so a caller can tell the difference between "the
structure says this is prose" and "we could not see any structure".
"""
from __future__ import annotations

from pathlib import Path

from . import parse_markdown, parse_text
from .detect import read_auto
from .model import Document

#: Extensions parsed with the Markdown parser. Everything else readable falls
#: back to the plain-text parser.
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}


def parse(text: str, source_format: str = "text") -> Document:
    """Parse a string that is already in memory.

    `source_format` is `"markdown"` or `"text"`; anything else is treated as
    text, because inventing structure for a format we cannot parse is exactly
    the failure mode the representation exists to prevent.
    """
    if source_format == "markdown":
        return parse_markdown.parse(text)
    return parse_text.parse(text)


def load(filepath: str | Path) -> Document:
    """Read a file and parse it into a `Document`."""
    path = Path(filepath)
    text, _ = read_auto(path)
    return parse(text, format_for(path))


def format_for(filepath: str | Path) -> str:
    """The parser to use for a path, by extension."""
    return "markdown" if Path(filepath).suffix.lower() in MARKDOWN_EXTENSIONS else "text"
