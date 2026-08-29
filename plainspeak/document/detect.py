"""Choosing a reader from a file extension."""

from pathlib import Path

from .docx import read_docx
from .html import read_html
from .pdf import read_pdf
from .text import read_text


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
