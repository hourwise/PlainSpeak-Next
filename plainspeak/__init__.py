"""
PlainSpeak — deterministic, integrity-protected presentation of prose.

Makes only the changes it can show preserve the facts a text states, and
reports what it changed, what needs a person and what it refused. All
processing is offline and local. See HOW_IT_WORKS.md.
"""

__version__ = "1.1.0"
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
