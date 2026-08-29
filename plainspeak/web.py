"""The web adapter.

This module moved when the engine was split into layers. It is kept as a
compatibility shim so that existing callers — and the characterisation
seal, which must keep testing the same entry points across the refactor —
go on working unchanged.

New code should import from the layer directly.
"""

from .adapters.web import (
    create_app,
    main,
)

__all__ = [
    "create_app",
    "main",
]
