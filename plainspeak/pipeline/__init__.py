"""Orchestration between the document representation and the analysis engine.

This layer exists because of a constraint worth keeping: **`core` does not
import `document`.** The analysis engine works on strings and knows nothing
about headings, quotes or code fences; the document representation knows all of
that and nothing about readability. Making either depend on the other would
collapse a clean separation for the sake of convenience, and the thing that
would rot first is the one that matters — `core` would gradually acquire
opinions about markup.

So the dependency runs one way, from here outwards:

    adapters
        │
        ▼
    pipeline ──────┬──────────┬───────────┐
                   ▼          ▼           ▼
                document     core     integrity

Everything in this package is orchestration. It contains no readability
algorithm, no tokenisation, no glossary, no morphology, no barrier detection,
no protected-term policy and no document parsing. If something here starts to
look like analysis, it belongs in `core`; if it starts to look like parsing, it
belongs in `document`.

The entry point is `analyze_document`. Adapters — the CLI today, a desktop
application and an MCP server later — call that one function, so that a
structured document cannot get different answers depending on which interface
asked.
"""

from .analysis import DocumentAnalysis, Finding, analyze_document
from .plan import ProposedChange, propose_change
from .projection import (
    Projection,
    ProjectedSegment,
    SourceMapping,
    project_block,
    project_document,
)
from .styling import (
    analyze_style,
    analyze_style_with_profile,
    compare_style_profiles,
    explain_profile,
    interpret_style,
    list_profiles,
    observe_style,
    structure_of,
)

__all__ = [
    "DocumentAnalysis",
    "Finding",
    "ProjectedSegment",
    "Projection",
    "ProposedChange",
    "SourceMapping",
    "analyze_document",
    "analyze_style",
    "analyze_style_with_profile",
    "compare_style_profiles",
    "explain_profile",
    "interpret_style",
    "list_profiles",
    "observe_style",
    "project_block",
    "project_document",
    "propose_change",
    "structure_of",
]
