"""The immutable contracts the style layer produces and consumes.

The input is deliberately narrow. `style` receives clean prose and a small
description of the document's shape; it never sees Markdown, never computes a
source offset and never opens a file. Everything structural it knows arrives as
`DocumentStructure`, which the pipeline builds from the document
representation — so there is exactly one parser in this project and it is not
here.

The output is evidence. Every finding carries the measurement that produced it,
the threshold it crossed, the sample it was drawn from, and concrete occurrences
a reader can go and look at. A finding a reader cannot check is a finding they
have to take on trust, and this layer is not in a position to be trusted about
prose.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

#: Block kinds the style layer understands. Anything the document
#: representation refuses to treat as prose never reaches here at all.
BLOCK_KINDS: tuple[str, ...] = ("paragraph", "heading", "list_item", "quote")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProseBlock:
    """One block of prose, as the style layer sees it."""

    kind: str
    text: str
    #: Position among all blocks, for evidence a reader can locate.
    index: int
    #: The document path this came from, so a report can point at it.
    path: tuple[int, ...] = ()
    #: Heading level, where the block is a heading.
    level: int = 0

    @property
    def location(self) -> str:
        readable = ".".join(str(part) for part in self.path)
        return f"{self.kind} {self.index + 1}" + (f" ({readable})" if readable else "")


@dataclass(frozen=True)
class DocumentStructure:
    """What the style layer is told about a document's shape.

    Counts that need the document representation to establish — how many list
    blocks, how many code fences — are passed in rather than inferred, because
    inferring them would mean parsing, and parsing here would mean a second
    parser that could disagree with the first.
    """

    blocks: tuple[ProseBlock, ...] = ()
    list_blocks: int = 0
    code_blocks: int = 0
    tables: int = 0

    def of_kind(self, kind: str) -> tuple[ProseBlock, ...]:
        return tuple(block for block in self.blocks if block.kind == kind)

    @property
    def paragraphs(self) -> tuple[ProseBlock, ...]:
        return self.of_kind("paragraph")

    @property
    def headings(self) -> tuple[ProseBlock, ...]:
        return self.of_kind("heading")

    @property
    def list_items(self) -> tuple[ProseBlock, ...]:
        return self.of_kind("list_item")


@dataclass(frozen=True)
class Occurrence:
    """One place a pattern was observed."""

    location: str
    excerpt: str

    def as_dict(self) -> dict[str, str]:
        return {"location": self.location, "excerpt": self.excerpt}


@dataclass(frozen=True)
class Evidence:
    """What was observed, how often, and where.

    `label` is the thing itself — the repeated opener, the overused word — so a
    report can say "The system" rather than "a repeated pattern".
    """

    label: str
    count: int
    total: int
    occurrences: tuple[Occurrence, ...] = ()

    @property
    def share(self) -> float:
        return self.count / self.total if self.total else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "count": self.count,
            "total": self.total,
            "occurrences": [item.as_dict() for item in self.occurrences],
        }


@dataclass(frozen=True)
class StyleFinding:
    """One observation about the document, with its arithmetic attached."""

    id: str
    category: str
    severity: str
    message: str
    #: What was measured, and the line it crossed.
    value: float
    threshold: float
    #: How much text the measurement was drawn from. A finding is never issued
    #: below the minimum sample its diagnostic declares.
    sample_size: int
    evidence: tuple[Evidence, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "value": round(self.value, 6),
            "threshold": round(self.threshold, 6),
            "sample_size": self.sample_size,
            "evidence": [item.as_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class StyleMetrics:
    """Everything measured, whether or not it produced a finding.

    Kept separate from findings on purpose. Metrics are neutral: a document with
    no findings still has a sentence-length distribution, and a future style
    profile will want it.
    """

    values: dict[str, float] = field(default_factory=dict)

    def get(self, name: str, default: float = 0.0) -> float:
        return self.values.get(name, default)

    def as_dict(self) -> dict[str, float]:
        return {key: _round(self.values[key]) for key in sorted(self.values)}


def _round(value: float) -> float:
    """Six places, so platform floating-point noise cannot reach the output."""
    rounded = round(float(value), 6)
    return 0.0 if rounded == 0 else rounded


@dataclass(frozen=True)
class StyleAnalysis:
    """The style layer's whole answer about one document.

    There is no score. A single number would compress a dozen independent
    observations into something that looks authoritative while hiding all of its
    own evidence, and it would be used as an AI detector within a week. What
    comes out instead is a profile of bands, each traceable to a measurement, a
    threshold and a list of places to look.
    """

    document_hash: str
    policy_version: str
    policy_hash: str
    metrics: StyleMetrics
    findings: tuple[StyleFinding, ...]

    @property
    def profile(self) -> dict[str, str]:
        """A band per diagnostic family, for a report or a review pane.

        Diagnostics that produced no finding read as "none" rather than being
        absent, so a reader can see what was looked for as well as what was
        found.
        """
        from .policy import DIAGNOSTIC_IDS

        bands = {identifier: "none" for identifier in DIAGNOSTIC_IDS}
        order = {"none": 0, "info": 1, "notice": 2, "strong": 3}
        for finding in self.findings:
            if order[finding.severity] > order[bands.get(finding.id, "none")]:
                bands[finding.id] = finding.severity
        return dict(sorted(bands.items()))

    def of_severity(self, severity: str) -> tuple[StyleFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == severity)

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_sha256": self.document_hash,
            "style_policy_version": self.policy_version,
            "style_policy_sha256": self.policy_hash,
            "metrics": self.metrics.as_dict(),
            "profile": self.profile,
            "findings": [finding.as_dict() for finding in self.findings],
        }
