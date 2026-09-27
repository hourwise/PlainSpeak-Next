"""Diagnosing a document: everything PlainSpeak observes, nothing changed.

`present` applies the SAFE changes and reports the rest. `diagnose` reports all
of it and applies nothing: the SAFE changes `present` *would* make, the
suggestions awaiting a person, the refusals and their reasons, the style
observations under a profile with their coverage, the protected facts, and the
inherited readability measurements.

It is built from exactly the same `ReviewBundle` and preview as `present`, and
every item in it is serialised by the same code, so the two can never disagree
about a document. The only difference is what is returned: no presented text,
because diagnosing is not transforming.

`DiagnoseResult.as_dict()` is the public `plainspeak.diagnose.v1` contract,
under the same rules as the other contracts: deterministic, no timestamps,
paths or host details, and within one schema id a field is never removed,
renamed or given a different type or meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..document.model import Document
from ..rules import Ruleset, canonical_json
from .analysis import analyze_document
from .present import FORMAT_MARKDOWN, FORMAT_TEXT, PresentResult, present

DIAGNOSE_SCHEMA = "plainspeak.diagnose.v1"

#: Readability measurements reported, rounded to two decimal places — as the
#: inherited JSON report rounds them — so that the last digit of a float cannot
#: differ between platforms.
READABILITY_FIELDS = (
    "total_words", "total_sentences", "avg_sentence_length", "avg_syllables_per_word",
    "flesch_reading_ease", "flesch_kincaid_grade", "gunning_fog_index", "smog_index",
    "automated_readability_index", "coleman_liau_index", "consensus_grade_level",
    "difficulty_band", "short_text_warning",
)


@dataclass(frozen=True)
class DiagnoseResult:
    presented: PresentResult
    readability: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """The `plainspeak.diagnose.v1` contract."""
        shared = self.presented.as_dict()
        return {
            "schema": DIAGNOSE_SCHEMA,
            "status": shared["status"],
            "plainspeak_version": shared["plainspeak_version"],
            "profile": shared["profile"],
            "input": shared["input"],
            "engine": shared["engine"],
            "counts": {
                "safe": shared["counts"]["applied"],
                "review": shared["counts"]["review"],
                "refused": shared["counts"]["refused"],
                "protected": shared["counts"]["protected"],
                "diagnostics": shared["counts"]["diagnostics"],
                "insufficient_sample": shared["counts"]["insufficient_sample"],
            },
            # What `present` would apply. Nothing here has been applied.
            "safe": shared["applied"],
            "review": shared["review"],
            "refused": shared["refused"],
            "protected": {key: value for key, value in shared["protected"].items()
                          if key != "preserved"},
            "diagnostics": shared["diagnostics"],
            "style_coverage": shared["style_coverage"],
            "readability": self.readability,
        }

    def to_json(self) -> str:
        return canonical_json(self.as_dict())


def diagnose(
    document: Document,
    profile: Any,
    ruleset: Optional[Ruleset] = None,
    input_format: str = FORMAT_MARKDOWN,
) -> DiagnoseResult:
    """Diagnose one document under one explicitly named profile.

    Refuses exactly what `present` refuses, with the same `PresentError` codes.
    """
    presented = present(document, profile, ruleset=ruleset, input_format=input_format)
    return DiagnoseResult(presented=presented, readability=_readability(document))


def diagnose_text(
    text: str, profile: Any, markdown: bool = True, ruleset: Optional[Ruleset] = None
) -> DiagnoseResult:
    from .review import parse_source

    return diagnose(parse_source(text, markdown=markdown), profile, ruleset=ruleset,
                    input_format=FORMAT_MARKDOWN if markdown else FORMAT_TEXT)


def _readability(document: Document) -> dict[str, Any]:
    scores = analyze_document(document).scores
    values: dict[str, Any] = {}
    for name in READABILITY_FIELDS:
        value = getattr(scores, name)
        values[name] = round(value, 2) if isinstance(value, float) else value
    return values


__all__ = ["DIAGNOSE_SCHEMA", "DiagnoseResult", "diagnose", "diagnose_text"]
