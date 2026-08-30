"""Deterministic JSON for a style analysis.

Same discipline as the transformation audit: sorted keys, a total order over
findings and evidence, rounded floats, and no clock anywhere in the content. Two
runs over the same document produce byte-identical output, which is what makes
the report worth comparing against a previous one.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .model import StyleAnalysis
from .policy import canonical_json


def analysis_to_dict(analysis: StyleAnalysis) -> dict[str, Any]:
    return analysis.as_dict()


def analysis_to_json(analysis: StyleAnalysis) -> str:
    return canonical_json(analysis.as_dict())


def analysis_digest(analysis: StyleAnalysis) -> str:
    """SHA-256 of the report — an identity for the whole observation."""
    return hashlib.sha256(analysis_to_json(analysis).encode("utf-8")).hexdigest()
