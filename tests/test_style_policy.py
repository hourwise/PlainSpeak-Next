"""The style policy's identity, and the things it promises never to do.

Two groups of tests here. The first is the familiar identity discipline: a
threshold is product behaviour, so moving one from 5% to 8% must move the hash.

The second group is unusual and more important. This is the layer that could
most easily turn into an AI detector — the temptation is obvious, the demand is
real, and the method cannot support it. So the prohibitions are tested rather
than merely written down: no authorship claim, no probability, no aggregate
score. A promise nobody checks is a promise until somebody is in a hurry.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from plainspeak import style
from plainspeak.style import (
    DIAGNOSTIC_IDS,
    MINIMUM_SAMPLES,
    SEVERITIES,
    STYLE_POLICY_VERSION,
    THRESHOLDS,
    canonical_json,
    policy_document,
    policy_hash,
    severity_for,
)
from plainspeak.style import policy as policy_module

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The style policy as it currently ships. Pinned so the Windows, Linux and
#: macOS jobs all assert the same number rather than each comparing itself to
#: itself, and so that a threshold cannot move without a reviewer seeing it.
STYLE_POLICY_HASH = "ecb8b5d8f0dfde3cc4a7f7332052d449eba0616616058465ceb9e49be1007aa0"


# ── Identity ───────────────────────────────────────────────────────────────


def test_the_policy_has_its_expected_identity() -> None:
    assert STYLE_POLICY_VERSION == "2026.1"
    assert policy_hash() == STYLE_POLICY_HASH, (
        "The style policy hash changed.\n"
        "  If you moved a threshold or edited a vocabulary deliberately, update\n"
        "  STYLE_POLICY_HASH here and say so in the commit message — thresholds\n"
        "  decide what users are told.\n"
        "  If you did not, something platform-dependent has reached the canonical\n"
        "  form, which is a bug in the hashing rather than in this test."
    )


def test_hashing_is_stable_within_a_process() -> None:
    assert policy_hash() == policy_hash()


@pytest.mark.parametrize("diagnostic", DIAGNOSTIC_IDS)
def test_moving_a_threshold_changes_the_identity(monkeypatch, diagnostic: str) -> None:
    """The example from the brief: 5% becoming 8% is a change of behaviour."""
    altered = dict(THRESHOLDS)
    notice, strong = altered[diagnostic]
    altered[diagnostic] = (notice + 0.05, strong + 0.05)

    before = policy_hash()
    monkeypatch.setattr(policy_module, "THRESHOLDS", altered)
    assert policy_hash() != before, f"changing {diagnostic}'s threshold did not move the hash"


@pytest.mark.parametrize("diagnostic", DIAGNOSTIC_IDS)
def test_moving_a_minimum_sample_changes_the_identity(monkeypatch, diagnostic: str) -> None:
    altered = dict(MINIMUM_SAMPLES)
    altered[diagnostic] += 1

    before = policy_hash()
    monkeypatch.setattr(policy_module, "MINIMUM_SAMPLES", altered)
    assert policy_hash() != before


@pytest.mark.parametrize(
    "attribute,mutate",
    [
        ("TRANSITIONS", lambda v: v + ("henceforth",)),
        ("FRAMING_PHRASES", lambda v: v + ("it bears repeating",)),
        ("FLAGGED_VOCABULARY", lambda v: v + ("bespoke",)),
        ("STOP_WORDS", lambda v: frozenset(v | {"nonetheless"})),
        ("CONTRACTIONS", lambda v: v + ("ain't",)),
        ("NGRAM_SIZES", lambda v: v + (6,)),
        ("OVERLAP_MINIMUM_TOKENS", lambda v: v + 5),
        ("STYLE_POLICY_VERSION", lambda v: "9999.1"),
        ("INVERTED", lambda v: frozenset(v | {"PS.STYLE.LIST_DOMINANCE"})),
    ],
)
def test_changing_a_vocabulary_or_bound_changes_the_identity(
    monkeypatch, attribute: str, mutate
) -> None:
    """Anything that alters what a reader is told must alter the identity."""
    before = policy_hash()
    monkeypatch.setattr(policy_module, attribute, mutate(getattr(policy_module, attribute)))
    assert policy_hash() != before, f"changing {attribute} did not move the style policy hash"


def test_changing_a_rhetorical_pattern_changes_the_identity(monkeypatch) -> None:
    altered = policy_module.RHETORICAL_PATTERNS + (("test", r"\bnothing at all\b"),)
    before = policy_hash()
    monkeypatch.setattr(policy_module, "RHETORICAL_PATTERNS", altered)
    assert policy_hash() != before


def test_the_policy_document_is_plain_data() -> None:
    document = policy_document()
    assert json.loads(json.dumps(document)) == document


def test_canonicalisation_agrees_with_the_other_layers() -> None:
    """Four leaves each carry a copy; none may drift from the others."""
    from plainspeak.integrity import canonical_json as integrity_canonical
    from plainspeak.morphology import canonical_json as morphology_canonical
    from plainspeak.rules import canonical_json as rules_canonical

    for value in ({"b": 1, "a": 2}, {"x": ["z", "y"]}, {"u": "café — 21 °C"}):
        rendered = canonical_json(value)
        assert rendered == rules_canonical(value)
        assert rendered == integrity_canonical(value)
        assert rendered == morphology_canonical(value)


# ── Coherence ──────────────────────────────────────────────────────────────


def test_every_diagnostic_declares_a_threshold_and_a_minimum_sample() -> None:
    for diagnostic in DIAGNOSTIC_IDS:
        assert diagnostic in THRESHOLDS, f"{diagnostic} has no threshold"
        assert diagnostic in MINIMUM_SAMPLES, f"{diagnostic} has no minimum sample size"


def test_no_threshold_exists_for_a_diagnostic_that_cannot_fire() -> None:
    assert set(THRESHOLDS) == set(DIAGNOSTIC_IDS)
    assert set(MINIMUM_SAMPLES) == set(DIAGNOSTIC_IDS)


def test_diagnostic_ids_are_in_their_own_namespace() -> None:
    """A style diagnostic is not a transformation rule and must not look like one."""
    from plainspeak.rules import load_ruleset

    rule_ids = set(load_ruleset().ids)
    for diagnostic in DIAGNOSTIC_IDS:
        assert diagnostic.startswith("PS.STYLE."), diagnostic
        assert diagnostic not in rule_ids


def test_severity_bands_come_from_explicit_comparisons() -> None:
    """No weighting, no blending — a reader can reproduce any band by hand."""
    for diagnostic in DIAGNOSTIC_IDS:
        notice, strong = THRESHOLDS[diagnostic]
        if diagnostic in policy_module.INVERTED:
            assert strong < notice, f"{diagnostic} is inverted but its bands are not"
            assert severity_for(diagnostic, strong) == "strong"
            assert severity_for(diagnostic, notice) == "notice"
            assert severity_for(diagnostic, notice + 0.01) == ""
        else:
            assert strong > notice, f"{diagnostic} bands are out of order"
            assert severity_for(diagnostic, strong) == "strong"
            assert severity_for(diagnostic, notice) == "notice"
            assert severity_for(diagnostic, notice - 0.01) == ""


def test_every_band_is_a_declared_severity() -> None:
    for diagnostic in DIAGNOSTIC_IDS:
        notice, strong = THRESHOLDS[diagnostic]
        for value in (notice, strong):
            band = severity_for(diagnostic, value)
            assert band in SEVERITIES


# ── What this layer will not do ────────────────────────────────────────────


FORBIDDEN_LANGUAGE = (
    "ai-generated", "ai generated", "written by ai", "machine-generated",
    "machine generated", "authorship", "likely ai", "probability", "human score",
    "ai score", "chatgpt", "gpt", "llm-written", "detector",
)


def test_the_package_makes_no_authorship_claim() -> None:
    """PlainSpeak does not know who wrote a document and will not guess.

    Checked against the source rather than against outputs, because the failure
    this guards against is somebody adding a helpful-sounding message under
    deadline. The phrasing that is allowed — "this document contains repetitive
    structural patterns" — is an observation. "83% likely AI-generated" is a
    claim the method cannot support at any confidence.
    """
    import ast

    offences = []
    for path in sorted((REPO_ROOT / "plainspeak" / "style").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # Docstrings are excluded, because the prohibition is stated in them.
        # What is checked is every other string literal: the messages, labels
        # and identifiers that could actually reach a reader.
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstrings:
                continue
            lowered = node.value.lower()
            for phrase in FORBIDDEN_LANGUAGE:
                if phrase in lowered:
                    offences.append(f"{path.name}:{node.lineno} says {phrase!r}")
    assert not offences, "authorship language in style output: " + "; ".join(offences)


def test_there_is_no_aggregate_score() -> None:
    """A single number would hide its own evidence and be used as a detector."""
    from plainspeak.style import StyleAnalysis

    fields = set(StyleAnalysis.__dataclass_fields__)
    for forbidden in ("score", "rating", "probability", "confidence", "likelihood"):
        assert not any(forbidden in name for name in fields), (
            f"StyleAnalysis has a {forbidden!r} field; the output is a profile of "
            f"bands, each traceable to a measurement and a threshold"
        )


def test_the_profile_reports_bands_not_numbers() -> None:
    """What comes out instead of a score."""
    analysis = style.analyze("A short sentence. Another one here.")
    profile = analysis.profile

    assert set(profile) == set(DIAGNOSTIC_IDS)
    assert set(profile.values()) <= {"none", *SEVERITIES}


def test_no_diagnostic_claims_certainty_about_grammar() -> None:
    """Surface templates are lexical. The naming says so, deliberately."""
    source = (REPO_ROOT / "plainspeak" / "style" / "policy.py").read_text(encoding="utf-8")
    assert "SURFACE_TEMPLATES" in source
    assert "surface" in source.lower()


def test_the_style_layer_proposes_no_edits() -> None:
    """Phase 7 is diagnostic-first: nothing here may rewrite anything."""
    import ast

    forbidden = {"replacement", "replace", "apply", "fix", "rewrite"}
    offences = []
    for path in sorted((REPO_ROOT / "plainspeak" / "style").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(word == node.name.lower().strip("_") for word in forbidden):
                    offences.append(f"{path.name}:{node.lineno} defines `{node.name}`")
    assert not offences, "the style layer must not transform text: " + "; ".join(offences)


def test_no_style_fix_mode_was_introduced() -> None:
    """`style-fix` stays reserved until profiles exist to make it meaningful."""
    from plainspeak.rules.schema import MODES

    assert "style-fix" not in MODES
