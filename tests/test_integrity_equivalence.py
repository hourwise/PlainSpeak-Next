"""The integrity equivalence table, tested in both directions and at its edges.

An equivalence is a decision about meaning, so each one is admitted only with
tests that it passes where it should, that everything around it still fails,
and that admitting it made the firewall stricter rather than weaker.
"""
from __future__ import annotations

import pytest

from plainspeak.integrity import POLICY_VERSION, check, snapshot
from plainspeak.integrity.policy import EQUIVALENCES, policy_document


def passes(before: str, after: str) -> bool:
    return check(before, after).passed


def test_the_table_is_small_and_versioned():
    assert POLICY_VERSION == "2026.2"
    assert EQUIVALENCES == {"comparator": {"prior to": "before"}}
    assert policy_document()["equivalences"] == {"comparator": {"prior to": "before"}}


def test_every_key_is_itself_a_protected_surface():
    """An equivalence for a form the extractor never produces would do nothing."""
    for kind, table in EQUIVALENCES.items():
        for surface, canonical in table.items():
            assert [fact.kind for fact in snapshot(f"x {surface} y").facts] == [kind], surface
            assert [fact.kind for fact in snapshot(f"x {canonical} y").facts] == [kind], canonical


# ── Admitted ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "before, after",
    [
        ("File it prior to the hearing.", "File it before the hearing."),
        ("File it before the hearing.", "File it prior to the hearing."),
        ("Prior to the hearing, file it.", "Before the hearing, file it."),
        ("PRIOR TO the hearing, file it.", "Before the hearing, file it."),
        ("You must not file it prior to 3 June 2027.", "You must not file it before 3 June 2027."),
        ("Pay £1,200 prior to delivery.", "Pay £1,200 before delivery."),
    ],
)
def test_the_equivalent_spellings_are_one_fact(before, after):
    assert passes(before, after)


def test_the_bundled_rule_now_applies():
    from plainspeak.pipeline import present_text

    result = present_text("Staff must file the form prior to the hearing.\n", "plain")
    assert "before the hearing" in result.text
    assert not [item for item in result.refused if item.rule_id == "PS.CLARITY.009"]


# ── Refused ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "before, after, why",
    [
        ("File it prior to the hearing.", "File it after the hearing.", "ordering reversed"),
        ("File it prior to the hearing.", "File it the hearing.", "comparator deleted"),
        ("File it prior to the hearing.", "File it no later than the hearing.", "different comparator"),
        ("File it prior to the hearing.", "File it until the hearing.", "different comparator"),
        ("File it prior to the hearing.", "File it only before the hearing.", "qualifier added"),
        ("File it prior to the hearing.", "File it before and after the hearing.", "scope widened"),
        ("File it prior to 3 June 2027.", "File it before 4 June 2027.", "date changed"),
        ("File it prior to 5 days.", "File it before 6 days.", "number changed"),
        ("You must file it prior to the hearing.", "You may file it before the hearing.", "modal weakened"),
        ("You must not file it prior to the hearing.", "You must file it before the hearing.", "negation lost"),
        ("You must file it prior to the hearing.", "You must not file it before the hearing.", "negation added"),
        ("File it prior to the hearing and prior to the trial.",
         "File it before the hearing.", "one of two occurrences lost"),
    ],
)
def test_everything_around_the_equivalence_still_fails(before, after, why):
    assert not passes(before, after), why


@pytest.mark.parametrize(
    "before, after",
    [
        # The adjective is not the preposition, and is not matched.
        ("A prior agreement applies.", "A before agreement applies."),
        ("The prior version is kept.", "The before version is kept."),
        # "Prior" alone is not in the table; only the phrase with "to" is.
        ("Get prior approval.", "Get before approval."),
    ],
)
def test_near_misses_are_not_equivalent(before, after):
    assert not passes(before, after)


def test_prior_without_to_is_not_protected_or_mapped():
    facts = snapshot("A prior agreement applies.").facts
    assert not [fact for fact in facts if fact.kind == "comparator"]


# ── Stricter, not looser ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "before, after",
    [
        ("File it prior to the hearing.", "File it the hearing."),
        ("File it prior to the hearing.", "File it after the hearing."),
    ],
)
def test_admitting_a_spelling_also_protects_it(before, after):
    """Under 2026.1 "prior to" was not a comparator, so both of these passed."""
    assert not passes(before, after)


@pytest.mark.parametrize(
    "before, after",
    [
        ("File it before the hearing.", "File it after the hearing."),
        ("File it before the hearing.", "File it the hearing."),
        ("Pay at least 5.", "Pay at most 5."),
    ],
)
def test_existing_protections_are_unchanged(before, after):
    assert not passes(before, after)
