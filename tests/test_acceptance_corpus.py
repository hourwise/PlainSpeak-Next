"""The V1 acceptance corpus and what reading it found.

`tests/acceptance/corpus/` holds 27 short, realistic documents — AI-style
prose, technical writing, government and legal text, short agent replies and
prose that is already good. They were run through `analyze`, `present` and the
desktop review before 1.0, and the output was read. This file keeps the
invariants that reading established, and pins every sentence that was broken
by an automatic change so it stays unbroken. It is not a style assessment: what
reads better is judged by a person, and recorded in V1_ACCEPTANCE_REVIEW.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plainspeak.integrity import snapshot
from plainspeak.pipeline import load_reviewable, present, present_text

CORPUS = Path(__file__).resolve().parent / "acceptance" / "corpus"
DOCUMENTS = sorted(CORPUS.glob("*.md"))


def test_the_corpus_is_what_the_review_read():
    assert len(DOCUMENTS) == 27
    kinds = {path.stem.split("-")[0] for path in DOCUMENTS}
    assert kinds == {"ai", "tech", "gov", "legal", "finance", "short", "good"}


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: path.stem)
def test_every_document_keeps_its_protected_facts(path):
    result = present(load_reviewable(path), "natural")
    assert snapshot(result.source_text).signature == snapshot(result.text).signature


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: path.stem)
def test_every_document_presents_identically_twice(path):
    document = load_reviewable(path)
    assert present(document, "plain").to_json() == present(document, "plain").to_json()


@pytest.mark.parametrize("path", [p for p in DOCUMENTS if p.stem.startswith("good-")],
                         ids=lambda path: path.stem)
def test_good_prose_is_left_alone(path):
    """Four documents that need nothing get nothing."""
    result = present(load_reviewable(path), "natural")
    assert result.applied == ()
    assert not result.changed


@pytest.mark.parametrize("path", [p for p in DOCUMENTS if p.stem.startswith("short-")],
                         ids=lambda path: path.stem)
def test_short_replies_say_they_are_too_short_to_judge(path):
    result = present(load_reviewable(path), "natural")
    assert result.bundle.diagnostics() == ()
    assert len(result.bundle.insufficient_sample()) == 13


# ── Sentences an automatic change used to break ────────────────────────────

BROKEN_BEFORE_2026_5 = [
    # The review's own finds in the corpus.
    "Requests are rate-limited to 100 per minute.",
    "Between 09:12 and 10:47 checkout requests took up to 14 seconds.",
    "Requests for leave must be submitted via the portal.",
    "A fundamental paradigm shift is under way.",
    "Confirm that the signature verifies.",
    # And the probe of every safe fix that followed.
    "This is a worthwhile endeavour for the team.",
    "Race is a social construct.",
    "The manufacture of drugs is regulated.",
    "We need an objective assessment.",
    "The tenant undertakes to pay the rent.",
    "They will furnish the flat.",
    "Exercise can compensate for a poor diet.",
    "The drug may inhibit growth.",
    "The company is incorporated in England.",
    "The film contains gratuitous violence.",
    "This API is deprecated.",
    "Read the API specification.",
    "The chair will convene a meeting.",
    "Phones are ubiquitous devices.",
    "The copy is identical to the original.",
    "We collaborate with partners.",
    "Staff liaise with the council.",
    "She took an empirical approach.",
    "It took considerable time.",
    "Resilient systems recover quickly.",
    "There was a sufficient reason.",
    "This is an optimal choice.",
]


@pytest.mark.parametrize("sentence", BROKEN_BEFORE_2026_5)
def test_a_sentence_an_automatic_change_used_to_break_is_left_alone(sentence):
    assert present_text(sentence + "\n", "natural").text == sentence + "\n"


@pytest.mark.parametrize(
    "before, after",
    [
        ("It offers an advantageous position.", "It offers a helpful position."),
        ("An advantageous position helps.", "A helpful position helps."),
        ("We found an erroneous result.", "We found a wrong result."),
        # "a" before a vowel letter with a consonant sound stays "a". This was
        # "a unilateral decision" until "unilateral" was demoted in ruleset
        # 2026.6 (field testing of 1.0.0: "one-sided" is not "made by one party").
        ("They formed a homogeneous group.", "They formed a uniform group."),
        ("It is an obsolete tool.", "It is an outdated tool."),
        ("We have sufficient funds.", "We have enough funds."),
    ],
)
def test_the_article_agrees_with_the_replacement(before, after):
    assert present_text(before + "\n", "natural").text == after + "\n"


def test_an_article_outside_the_words_markup_refuses_the_change():
    """The article cannot join a change it is not contiguous with; nothing is applied."""
    result = present_text("It was an *advantageous* position.\n", "natural")
    assert not result.changed
    assert result.refused
