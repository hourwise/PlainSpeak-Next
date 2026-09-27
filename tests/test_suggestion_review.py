"""The reviewed suggestion glossary behind the readability report.

The report used to offer every inherited suggestion, including ones that are
wrong in ordinary prose. These tests pin the review: what was withdrawn, what
was corrected, that the inherited data itself was not touched, and that the
report and the inherited substitution engine both honour it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plainspeak.core import suggestions
from plainspeak.core.barriers import analyze_simplification
from plainspeak.core.glossary import GLOSSARY, SIMPLE_WORD_MAP
from plainspeak.core.lexicon import find_glossary_match
from plainspeak.core.transform import generate_simplified_text

REPO = Path(__file__).resolve().parent.parent

#: Pinned so every platform asserts the same values. Moving any of them is a
#: change to what users are told, and needs a version bump and a reason.
REVIEW_VERSION = "2026.1"
REVIEW_HASH = "ee2612759484992dc676dc41254465e8c39a251c98aeb1e835d3209b367f1f19"
#: The inherited vocabulary. This must never move: the review overlays it.
INHERITED_HASH = "60a20496271c57124cce73d6825dfdd222ed2a6d1777056c58db73c8c36e21f1"
EFFECTIVE_HASH = "44b2fb1ccec737ea02c73fdcb447e10665baedd2f834aa8b29f1a15ff8d9aae2"


def _inherited_suggestion(term: str) -> str:
    from plainspeak.core.lexicon import stem_word

    for key in (term, stem_word(term)):
        if key in GLOSSARY:
            return GLOSSARY[key][0]
        if key in SIMPLE_WORD_MAP:
            return SIMPLE_WORD_MAP[key]
    raise KeyError(term)


def test_the_review_has_its_expected_identity():
    assert suggestions.SUGGESTION_REVIEW_VERSION == REVIEW_VERSION
    assert suggestions.review_hash() == REVIEW_HASH


def test_the_inherited_vocabulary_is_untouched():
    assert suggestions.inherited_glossary_hash() == INHERITED_HASH


def test_the_effective_vocabulary_has_its_expected_identity():
    assert suggestions.effective_glossary_hash() == EFFECTIVE_HASH


def test_every_decision_names_a_real_inherited_entry():
    """Each decision is about an inherited entry, or a form the stemmer sends to one."""
    from plainspeak.core.lexicon import stem_word

    inherited = set(GLOSSARY) | set(SIMPLE_WORD_MAP)
    for term in list(suggestions.WITHDRAWN) + list(suggestions.CORRECTED):
        assert term in inherited or stem_word(term) in inherited, term


def test_every_entry_the_migration_rejected_is_withdrawn():
    """Phase 6 judged these wrong; the report must not keep offering them."""
    inventory = json.loads((REPO / "migration" / "glossary-inventory.json").read_text(encoding="utf-8"))
    rejected = {entry["term"] for entry in inventory["entries"] if entry["classification"] == "rejected"}
    assert rejected
    assert rejected <= set(suggestions.WITHDRAWN)


@pytest.mark.parametrize("term", sorted(suggestions.WITHDRAWN))
def test_a_withdrawn_suggestion_is_never_offered(term):
    old = _inherited_suggestion(term)
    sentence = f"The {term} was noted in the documentation for the committee."
    offered = [b.suggestion for b in analyze_simplification(sentence).barriers]
    assert not [s for s in offered if f'"{old}"' in s], (term, offered)
    assert find_glossary_match(term) is None


@pytest.mark.parametrize("term", sorted(suggestions.CORRECTED))
def test_a_corrected_suggestion_replaces_the_inherited_one(term):
    new, _ = suggestions.CORRECTED[term]
    old = _inherited_suggestion(term)
    offered = " ".join(b.suggestion for b in analyze_simplification(
        f"The team will {term} the data in the documentation." if " " not in term
        else f"The fee is set {term} the documentation."
    ).barriers)
    assert f'"{new}"' in offered
    assert f'"{old}"' not in offered


def test_leverage_is_no_longer_borrowed_money():
    """The example that prompted the review."""
    offered = " ".join(b.suggestion for b in analyze_simplification(
        "The system leverages a robust framework."
    ).barriers)
    assert "borrowed money" not in offered
    assert '"use"' in offered


def test_a_withdrawn_term_does_not_fall_through_to_its_stem():
    """"implementation" is withdrawn; its stem "implement" is not, and must not answer for it."""
    assert find_glossary_match("implementation") is None
    assert find_glossary_match("implement") is not None
    simplified, _ = generate_simplified_text("The implementation of the policy.")
    assert "carry out" not in simplified


def test_the_inherited_engine_leaves_withdrawn_words_alone():
    simplified, _ = generate_simplified_text(
        "The court's venue, the terms of the lease and the premises are said to be in dispute."
    )
    for word in ("venue", "terms", "premises", "said"):
        assert word in simplified
    for gloss in ("location of court", "length of cover", "the the"):
        assert gloss not in simplified


def test_the_governed_ruleset_is_not_affected():
    """The review changes advice, not rules: the ruleset identity does not move."""
    from plainspeak.rules import load_ruleset

    assert load_ruleset().version == "2026.5"


# ── Nouns and verbs ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "sentence, verb",
    [
        ("We will make a decision tomorrow.", "decide"),
        ("They gave a presentation to the board.", "present"),
        ("He provided a solution to the problem.", "solve"),
        ("She made a payment last week.", "pay"),
        ("Staff conduct a review of the files.", "review"),
    ],
)
def test_hidden_verbs_are_offered_the_reviewed_verb(sentence, verb):
    offered = [b.suggestion for b in analyze_simplification(sentence).barriers
               if b.barrier_type == "hidden_verb"]
    assert offered and f'"{verb}"' in offered[0]


@pytest.mark.parametrize(
    "sentence, nonsense",
    [
        ("We will make a decision tomorrow.", "deci"),
        ("He provided a solution to the problem.", "solu"),
        ("They gave a presentation to the board.", "presente"),
        ("We make a difference every day.", "differ"),
        ("They made a mistake in the form.", "mistake"),
        ("The service provides a true picture.", "true"),
    ],
)
def test_hidden_verbs_never_offer_a_guess(sentence, nonsense):
    offered = " ".join(b.suggestion for b in analyze_simplification(sentence).barriers
                       if b.barrier_type == "hidden_verb")
    assert f'"{nonsense}"' not in offered


@pytest.mark.parametrize(
    "noun",
    ["action", "lesion", "ration", "motion", "version", "commission", "confidence",
     "organization", "competence", "deduction", "residence", "settlement",
     "darkness", "purity", "clarity", "kindness"],
)
def test_no_verb_is_invented_for_a_noun_nobody_reviewed(noun):
    from plainspeak.core.barriers import _nominalization_to_verb

    assert _nominalization_to_verb(noun) is None
    offered = [b for b in analyze_simplification(f"The {noun} was noted.").barriers
               if b.barrier_type == "nominalization"]
    assert offered == []


def test_every_reviewed_verb_is_a_single_word_distinct_from_its_noun():
    for noun, verb in suggestions.NOUN_VERBS.items():
        assert verb.isalpha() and verb != noun, (noun, verb)

