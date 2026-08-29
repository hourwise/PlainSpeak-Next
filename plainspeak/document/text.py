"""Reading plain text and Markdown as undifferentiated characters."""

from pathlib import Path


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
