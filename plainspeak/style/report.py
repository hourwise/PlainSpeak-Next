"""Deterministic JSON for a style analysis.

Same discipline as the transformation audit: sorted keys, a total order over
findings and evidence, rounded floats, and no clock anywhere in the content. Two
runs over the same document produce byte-identical output, which is what makes
the report worth comparing against a previous one.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .model import ProfiledAnalysis, StyleAnalysis
from .policy import canonical_json


def analysis_to_dict(analysis: StyleAnalysis) -> dict[str, Any]:
    return analysis.as_dict()


def analysis_to_json(analysis: StyleAnalysis) -> str:
    return canonical_json(analysis.as_dict())


def analysis_digest(analysis: StyleAnalysis) -> str:
    """SHA-256 of the report — an identity for the whole observation."""
    return hashlib.sha256(analysis_to_json(analysis).encode("utf-8")).hexdigest()


def profiled_to_dict(analysis: ProfiledAnalysis) -> dict[str, Any]:
    return analysis.as_dict()


def profiled_to_json(analysis: ProfiledAnalysis) -> str:
    """Canonical JSON for a profile-aware analysis.

    The profile is part of the record rather than an annotation on it. A style
    report that did not say which expectations produced it could not be checked,
    compared against a previous run, or argued with.
    """
    return canonical_json(analysis.as_dict())


def profiled_digest(analysis: ProfiledAnalysis) -> str:
    return hashlib.sha256(profiled_to_json(analysis).encode("utf-8")).hexdigest()
