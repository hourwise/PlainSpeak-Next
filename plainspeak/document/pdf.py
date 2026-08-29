"""Extracting text from PDFs.

Requires the optional `pypdf` dependency. PDF is a layout format, so what
comes back is whatever text the producer happened to embed — not a faithful
reading order.
"""

from pathlib import Path


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
