"""Getting input into the pipeline.

Adapters do not read documents for themselves. They ask for one here, and the
reason is not tidiness: an adapter that reached into `document` directly and
then called `core` would be joining parsing to analysis on its own terms, and
two adapters doing that independently is precisely how the CLI and the MCP
server end up giving different answers for the same file.

There are two ways in, and they are different questions:

    read_text_source(path)   the inherited flat path — "what does this say?"
    load_document(path)      the structured path      — "what is this made of?"

Both are pure delegation. Nothing here parses, detects or decides anything; if
it ever needs to, it belongs in `document` or `core` instead.
"""
from __future__ import annotations

from pathlib import Path

from ..document import load as _load
from ..document.detect import get_supported_extensions, read_auto
from ..document.model import Document


def read_text_source(filepath: str | Path) -> tuple[str, str]:
    """Read a file as flat text, the way the inherited analyser expects.

    Returns `(text, format_name)`. This is the sealed path: it behaves exactly
    as `document.detect.read_auto` does, because it is that function.
    """
    return read_auto(filepath)


def load_document(filepath: str | Path) -> Document:
    """Read and parse a file into the structured representation."""
    return _load.load(filepath)


def supported_extensions() -> dict[str, str]:
    """The file extensions an adapter may offer to open."""
    return get_supported_extensions()
