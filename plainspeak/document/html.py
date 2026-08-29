"""Extracting text from HTML, discarding script, style and markup."""

import re
from html.parser import HTMLParser
from pathlib import Path


class _TextExtractingHTMLParser(HTMLParser):
    """Extract visible text from HTML, ignoring scripts and styles."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self.skip = False
        self.skip_tags = {"script", "style", "noscript", "iframe", "svg", "head"}

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in self.skip_tags:
            self.skip = True

    def handle_endtag(self, tag: str):
        if tag.lower() in self.skip_tags:
            self.skip = False
        # Add newlines after block-level elements for readability
        if tag.lower() in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str):
        if not self.skip:
            self.text_parts.append(data)


def read_html(filepath: str | Path) -> str:
    """
    Extract visible text from an HTML file.

    Uses stdlib html.parser — no external dependencies.
    Strips all tags, scripts, and styles. Preserves paragraph breaks.
    """
    path = Path(filepath)
    html_content = path.read_text(encoding="utf-8", errors="replace")

    parser = _TextExtractingHTMLParser()
    parser.feed(html_content)
    parser.close()

    # Join text parts and clean up whitespace
    text = "".join(parser.text_parts)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Trim leading/trailing whitespace
    return text.strip()
