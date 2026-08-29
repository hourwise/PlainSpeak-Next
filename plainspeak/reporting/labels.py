"""Shared presentation helpers.

Kept in one place so the HTML report and the console report cannot drift
into describing the same finding differently.
"""

import html


def _escape(text: str) -> str:
    """HTML-escape user-provided text to prevent injection."""
    return html.escape(text, quote=True)


def _severity_icon(severity: str) -> str:
    """Return an accessible icon indicator for severity."""
    icons = {
        "critical": "&#9888;&#65039;",  # Warning sign
        "warning": "&#9888;",  # Warning sign
        "info": "&#8505;&#65039;",  # Information
    }
    return icons.get(severity, "")


def _barrier_type_label(barrier_type: str) -> str:
    """Human-readable label for barrier types."""
    labels = {
        "passive_voice": "Passive Voice",
        "long_sentence": "Long Sentence",
        "complex_word": "Complex Word",
        "nominalization": "Nominalization",
        "jargon": "Jargon / Formal Language",
        "redundant_pair": "Redundant Pair",
        "hidden_verb": "Hidden Verb",
    }
    return labels.get(barrier_type, barrier_type.replace("_", " ").title())


def _pct(part: int, whole: int) -> str:
    """Format a percentage safely."""
    if whole == 0:
        return "0.0"
    return f"{(part / whole) * 100:.1f}"
