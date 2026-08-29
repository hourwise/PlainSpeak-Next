"""Report rendering.

This module moved when the engine was split into layers. It is kept as a
compatibility shim so that existing callers — and the characterisation
seal, which must keep testing the same entry points across the refactor —
go on working unchanged.

New code should import from the layer directly.
"""

from .reporting.labels import (
    _barrier_type_label,
    _escape,
    _pct,
    _severity_icon,
)
from .reporting.html import (
    _build_html_template,
    generate_report,
)
from .reporting.json import generate_json
from .reporting.console import format_console_report
from .core.barriers import (
    Barrier,
    SimplificationResult,
)
from .core.metrics import (
    ReadabilityScores,
    describe_flesch_score,
)

__all__ = [
    "Barrier",
    "ReadabilityScores",
    "SimplificationResult",
    "describe_flesch_score",
    "format_console_report",
    "generate_json",
    "generate_report",
]
