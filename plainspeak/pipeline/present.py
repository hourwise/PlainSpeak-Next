"""Presenting a document: every SAFE change applied, nothing else.

`present` is the non-interactive form of the review the desktop application
performs, and the operation a machine caller — a script, a CI job, and later an
MCP server — should use. It builds the same `ReviewBundle` the desktop builds
and takes the same preview with **no review decisions**, so:

    SAFE      applied, because the engine already accepted them
    REVIEW    reported and left unapplied, because only a person may accept one
    REFUSED   reported, with the reason, and never applied

There is deliberately no parameter that accepts a review-required change. A
caller who wants one applied must go through a review, where the decision is
bound to the plan hash, rather than through a flag here.

### The contract

`PresentResult.as_dict()` is a public, versioned contract. Its `schema` field
names the version, and within one schema id a field is never removed, renamed,
or given a different type or meaning. Adding a field is allowed. Everything in
it is deterministic: no timestamps, no paths, no host information, so the same
input under the same engine and profile serialises to identical bytes on every
platform.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .. import __version__
from ..document.model import Document
from ..integrity import snapshot
from ..integrity import check as integrity_check
from ..rules import Ruleset
from ..rules.canonical import canonical_json
from ..style.profiles import ProfileError, StyleProfile, load_profile, profile_ids
from .review import (
    KIND_REFUSED,
    KIND_SAFE,
    KIND_STYLE,
    PreviewResult,
    ReviewBundle,
    ReviewError,
    build_review_bundle,
    parse_source,
)

#: The contract identifier. Bump the trailing version for any change that is
#: not purely additive; see V1_SCOPE.md.
PRESENT_SCHEMA = "plainspeak.present.v1"

STATUS_OK = "ok"
STATUS_ERROR = "error"

#: Machine-readable error codes. Part of the contract.
ERROR_EMPTY_INPUT = "empty_input"
ERROR_UNSUPPORTED_INPUT = "unsupported_input"
ERROR_UNREADABLE_INPUT = "unreadable_input"
ERROR_UNKNOWN_PROFILE = "unknown_profile"
ERROR_NOT_PRESENTABLE = "not_presentable"

#: How an input was parsed. Markdown protects code, quotes, tables and link
#: destinations; plain text treats every paragraph as prose.
FORMAT_MARKDOWN = "markdown"
FORMAT_TEXT = "text"


class PresentError(ValueError):
    """An input could not be presented. Carries a contract error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": PRESENT_SCHEMA,
            "status": STATUS_ERROR,
            "error": {"code": self.code, "message": self.message},
        }

    def to_json(self) -> str:
        return canonical_json(self.as_dict())


@dataclass(frozen=True)
class PresentResult:
    """One document presented under one profile."""

    bundle: ReviewBundle
    preview: PreviewResult
    input_format: str

    @property
    def source_text(self) -> str:
        return self.bundle.source_text

    @property
    def text(self) -> str:
        """The presented document. The only text a caller should publish."""
        return self.preview.revised_text

    @property
    def changed(self) -> bool:
        return self.preview.changed

    @property
    def applied(self) -> tuple:
        return self.preview.of_kind(KIND_SAFE)

    @property
    def review(self) -> tuple:
        return self.preview.of_kind(KIND_STYLE)

    @property
    def refused(self) -> tuple:
        return self.preview.of_kind(KIND_REFUSED)

    def marked_text(self, open_mark: str = "**", close_mark: str = "**") -> str:
        """The presented text with every applied change wrapped in markers.

        For a person reading a terminal or a web page. Built from the engine's
        own revised offsets, so no adapter has to recompute where a change went.
        A deletion has no text to wrap and is left unmarked.
        """
        text = self.preview.revised_text
        pieces: list[str] = []
        cursor = 0
        for change in sorted(self.applied, key=lambda item: item.revised_start):
            if change.revised_end <= change.revised_start:
                continue
            pieces.append(text[cursor:change.revised_start])
            pieces.append(open_mark + text[change.revised_start:change.revised_end] + close_mark)
            cursor = change.revised_end
        pieces.append(text[cursor:])
        return "".join(pieces)

    def as_dict(self) -> dict[str, Any]:
        """The `plainspeak.present.v1` contract."""
        protected = snapshot(self.source_text)
        verdict = integrity_check(self.source_text, self.text)
        profile = self.bundle.profile
        return {
            "schema": PRESENT_SCHEMA,
            "status": STATUS_OK,
            "plainspeak_version": __version__,
            "profile": {"id": profile.id, "version": profile.version, "sha256": profile.hash},
            "input": {
                "format": self.input_format,
                "sha256": self.bundle.input_hash,
                "characters": len(self.source_text),
            },
            "output": {
                "sha256": self.preview.output_hash,
                "characters": len(self.text),
                "changed": self.changed,
                "text": self.text,
            },
            "engine": self.bundle.identities(),
            "counts": {
                "applied": len(self.applied),
                "review": len(self.review),
                "refused": len(self.refused),
                "protected": len(protected),
                "diagnostics": len(self.bundle.diagnostics()),
            },
            "applied": [item.as_dict() for item in self.applied],
            "review": [item.as_dict() for item in self.review],
            "refused": [item.as_dict() for item in self.refused],
            "protected": {
                "policy_version": protected.policy_version,
                "policy_sha256": protected.policy_hash,
                "preserved": verdict.passed,
                "facts": [
                    {
                        "kind": fact.kind,
                        "surface": fact.surface,
                        "normalized": fact.normalized,
                        "source_start": fact.start,
                        "source_end": fact.end,
                    }
                    for fact in protected.facts
                ],
            },
            "diagnostics": [item.as_dict() for item in self.bundle.diagnostics()],
        }

    def to_json(self) -> str:
        """Canonical JSON: sorted keys, no insignificant whitespace, one newline."""
        return canonical_json(self.as_dict())


def present(
    document: Document,
    profile: Any,
    ruleset: Optional[Ruleset] = None,
    input_format: str = FORMAT_MARKDOWN,
) -> PresentResult:
    """Present one document under one explicitly named profile.

    Refuses rather than degrades: an empty document, an unknown profile, or a
    set of safe changes that together fail the document-wide integrity check
    each raise `PresentError` instead of returning something partial.
    """
    if not document.source.strip():
        raise PresentError(ERROR_EMPTY_INPUT, "the input is empty")
    resolved = _resolve_profile(profile)
    try:
        bundle = build_review_bundle(document, resolved, ruleset=ruleset)
    except ReviewError as error:
        raise PresentError(ERROR_NOT_PRESENTABLE, str(error)) from None
    try:
        preview = bundle.preview()
    except ReviewError as error:
        raise PresentError(ERROR_NOT_PRESENTABLE, str(error)) from None
    return PresentResult(bundle=bundle, preview=preview, input_format=input_format)


def present_text(
    text: str,
    profile: Any,
    markdown: bool = True,
    ruleset: Optional[Ruleset] = None,
) -> PresentResult:
    """Present text an adapter already holds — standard input, a paste, a request body."""
    document = parse_source(text, markdown=markdown)
    return present(
        document, profile, ruleset=ruleset,
        input_format=FORMAT_MARKDOWN if markdown else FORMAT_TEXT,
    )


def _resolve_profile(profile: Any) -> StyleProfile:
    """An explicit, known profile, or a contract error. Never a default."""
    if isinstance(profile, StyleProfile):
        return profile
    if profile is None or not str(profile).strip():
        raise PresentError(
            ERROR_UNKNOWN_PROFILE,
            f"a profile is required; available: {', '.join(profile_ids())}",
        )
    try:
        return load_profile(str(profile))
    except ProfileError:
        raise PresentError(
            ERROR_UNKNOWN_PROFILE,
            f"unknown profile {str(profile)!r}; available: {', '.join(profile_ids())}",
        ) from None


__all__ = [
    "ERROR_EMPTY_INPUT",
    "ERROR_NOT_PRESENTABLE",
    "ERROR_UNKNOWN_PROFILE",
    "ERROR_UNREADABLE_INPUT",
    "ERROR_UNSUPPORTED_INPUT",
    "FORMAT_MARKDOWN",
    "FORMAT_TEXT",
    "PRESENT_SCHEMA",
    "PresentError",
    "PresentResult",
    "present",
    "present_text",
]
