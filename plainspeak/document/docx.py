"""Extracting text from Word documents.

Requires the optional `python-docx` dependency; the import is deferred so
that an installation without it still works for every other format.
"""

from pathlib import Path


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
