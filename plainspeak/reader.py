"""
Multi-format document reader for PlainSpeak.

Supports reading text from:
- Plain text (.txt, .md, .rst, and other text formats)
- Microsoft Word (.docx) — requires python-docx (optional)
- PDF (.pdf) — requires pypdf (optional)
- HTML (.html, .htm) — uses stdlib html.parser

All readers extract plain text only. Formatting, images, and structure
are discarded. The goal is to feed clean text into the readability analyzer.
"""

import re
from pathlib import Path
from html.parser import HTMLParser
from typing import Optional


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


def read_text(filepath: str | Path) -> str:
    """
    Read a plain text file with automatic encoding detection.

    Tries UTF-8 first, then common fallback encodings.
    """
    path = Path(filepath)
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: read as bytes and decode with replacement
    raw = path.read_bytes()
    return raw.decode("utf-8", errors="replace")


def read_docx(filepath: str | Path) -> str:
    """
    Extract text from a .docx file.

    Requires python-docx: pip install python-docx
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError(
            "Reading .docx files requires python-docx. "
            "Install it with: pip install python-docx"
        )

    doc = Document(str(filepath))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def read_pdf(filepath: str | Path) -> str:
    """
    Extract text from a .pdf file.

    Requires pypdf: pip install pypdf
    Note: Only extracts text content. Scanned/image-based PDFs
    (without embedded text) will return empty or garbled text.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "Reading .pdf files requires pypdf. "
            "Install it with: pip install pypdf"
        )

    reader = PdfReader(str(filepath))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


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


def read_auto(filepath: str | Path) -> tuple[str, str]:
    """
    Auto-detect file type and extract text.

    Args:
        filepath: Path to the file.

    Returns:
        Tuple of (extracted_text, file_format_name).

    Raises:
        ValueError: If the file format is not supported.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    suffix = path.suffix.lower()

    if suffix in (".txt", ".md", ".rst", ".text", ".log", ".csv", ".json", ".xml", ".yaml", ".yml", ".cfg", ".ini", ".toml"):
        return read_text(path), "plain text"

    if suffix in (".docx", ".doc"):
        return read_docx(path), "Word document"

    if suffix == ".pdf":
        return read_pdf(path), "PDF"

    if suffix in (".html", ".htm"):
        return read_html(path), "HTML"

    # Unknown extension — try as plain text
    try:
        return read_text(path), "plain text (unknown extension)"
    except Exception:
        raise ValueError(
            f"Unsupported file format: {suffix}. "
            f"Supported formats: .txt, .md, .docx, .pdf, .html"
        )


# ── Format detection ───────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".txt": "Plain text",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".docx": "Word document",
    ".doc": "Word document (legacy)",
    ".pdf": "PDF document",
    ".html": "HTML document",
    ".htm": "HTML document",
    ".text": "Plain text",
    ".log": "Log file",
}


def get_supported_extensions() -> dict[str, str]:
    """Return a dict of supported file extensions and their descriptions."""
    return dict(SUPPORTED_EXTENSIONS)
