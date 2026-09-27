"""
PlainSpeak — A readability analysis and text simplification toolkit.

Helps writers and advocates understand how readable text is and what
can be done to make it clearer. All processing is offline and local.
"""

__version__ = "1.0.0rc1"
__all__ = [
    # Layers
    "core",
    "document",
    "integrity",
    "reporting",
    "adapters",
    # Deprecated flat modules, kept as compatibility shims
    "analyzer",
    "simplifier",
    "glossary",
    "grammar",
    "reader",
    "reporter",
    "cli",
    "web",
]
