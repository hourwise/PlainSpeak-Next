"""Reading documents into text.

This module moved when the engine was split into layers. It is kept as a
compatibility shim so that existing callers — and the characterisation
seal, which must keep testing the same entry points across the refactor —
go on working unchanged.

New code should import from the layer directly.
"""

from .document.text import read_text
from .document.html import (
    _TextExtractingHTMLParser,
    read_html,
)
from .document.docx import read_docx
from .document.pdf import read_pdf
from .document.detect import (
    SUPPORTED_EXTENSIONS,
    get_supported_extensions,
    read_auto,
)

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "get_supported_extensions",
    "read_auto",
    "read_docx",
    "read_html",
    "read_pdf",
    "read_text",
]
