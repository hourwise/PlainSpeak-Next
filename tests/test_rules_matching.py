"""Deterministic matching over analysis text.

The matcher sees a string and produces analysis coordinates. It never sees a
document and never computes a source offset, which is the property that makes
it impossible for a rule to put an edit in the wrong place.

Two areas get disproportionate attention here, because both are where a naive
implementation quietly does the wrong thing:

**Word boundaries.** A rule for `utilise` must not rewrite the middle of
`utiliser`. Which inflected forms a rule matches is written down in the rule,
not derived — the inherited engine derived forms by stripping suffixes and
produced non-words.

**Casing.** A replacement has to fit the capitalisation of what it replaces, and
where it cannot be made to fit, the honest answer is to refuse. Lower-casing
whatever was found would turn a sentence-initial phrase into a lower-case one.
"""
from __future__ import annotations

import random

import pytest

from plainspeak.rules import find_matches, load_ruleset
from plainspeak.rules.matcher import (
    REFUSAL_CASE_UNMAPPABLE,
    REFUSAL_RECAPITALIZE,
    REFUSAL_SPACING,
    deletion_span,
)

from .conftest import VALID_RULE

WORD_RULE = """\
id: PS.TEST.010
version: 1
name: utilise-rule
mode: safe-fix
description: >
  A word rule for boundary tests.
match:
  type: word
  text: "utilise"
  forms: ["utilize"]
action:
  type: replace
  replacement: "use"
scope:
  include: [prose]
case:
  policy: preserve
priority: 100
reason:
  short: "Everyday word"
provenance:
  source: "PlainSpeak test suite"
  reference: ""
  licence: "project-authored"
examples:
  positive:
    - "Staff utilise it."
  negative:
    - "The utiliser."
  transform:
    - before: "Staff utilise it."
      after: "Staff use it."
"""

DELETE_RULE = """\
id: PS.TEST.011
version: 1
name: framing-delete
mode: safe-fix
description: >
  A deletion rule for punctuation and spacing tests.
match:
  type: phrase
  text: "it is important to note that "
action:
  type: delete
  recapitalize: true
scope:
  include: [prose]
priority: 100
reason:
  short: "Framing"
provenance:
  source: "PlainSpeak test suite"
  reference: ""
  licence: "project-authored"
examples:
  positive:
    - "It is important to note that x happened."
  negative:
    - "The phrase it is important to note that appears."
  transform:
    - before: "It is important to note that x happened."
      after: "X happened."
"""


def rules_of(ruleset):
    return ruleset.rules


# ── Phrase matching ────────────────────────────────────────────────────────


def test_an_exact_phrase_is_found(ruleset_from) -> None:
    ruleset = ruleset_from(VALID_RULE)
    matches = find_matches("You must register in order to vote.", rules_of(ruleset))

    assert len(matches) == 1
    assert matches[0].matched_text == "in order to"
    assert matches[0].replacement == "to"
    assert matches[0].rule_id == "PS.TEST.001"


def test_every_occurrence_is_found(ruleset_from) -> None:
    ruleset = ruleset_from(VALID_RULE)
    matches = find_matches("in order to a, and in order to b.", rules_of(ruleset))
    assert [match.start for match in matches] == [0, 19]


def test_a_phrase_inside_a_longer_word_is_not_matched(ruleset_from) -> None:
    """Word boundaries apply at any edge where they are defined."""
    ruleset = ruleset_from(VALID_RULE)
    assert find_matches("joining order tokens", rules_of(ruleset)) == ()


# ── Word boundaries ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Staff utilise it.", ["utilise"]),
        ("Staff utilize it.", ["utilize"]),
        ("Staff utilised it.", []),
        ("Staff utilises it.", []),
        ("The utiliser signed.", []),
        ("Reutilise the form.", []),
        ("utilise", ["utilise"]),
        ("(utilise)", ["utilise"]),
        ("'utilise',", ["utilise"]),
        ("utilise-adjacent", ["utilise"]),
    ],
    ids=["base", "us-spelling", "past", "third-person", "agent-noun", "prefixed",
         "alone", "bracketed", "quoted", "hyphenated"],
)
def test_word_matching_respects_boundaries(ruleset_from, text: str, expected: list) -> None:
    """Exactly the forms the rule names, and no others.

    `utilised` and `utilises` are absent on purpose: this rule does not declare
    them, and there is no stemmer to infer them. The bundled ruleset writes each
    inflection out as its own rule.
    """
    ruleset = ruleset_from(WORD_RULE)
    matches = find_matches(text, rules_of(ruleset))
    assert [match.matched_text for match in matches] == expected


def test_the_bundled_ruleset_covers_the_declared_inflections(bundled) -> None:
    text = "utilise utilises utilised utilising utiliser"
    matches = find_matches(text, bundled.rules)
    found = {match.matched_text for match in matches}

    assert found == {"utilise", "utilises", "utilised", "utilising"}
    assert "utiliser" not in found, "the agent noun is a different word"


# ── Casing ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected_replacement",
    [
        ("register in order to vote", "to"),
        ("In order to vote", "To"),
        ("IN ORDER TO VOTE", "TO"),
        ("In Order To Vote", "To"),
    ],
    ids=["lower", "sentence", "upper", "title"],
)
def test_replacement_casing_follows_the_matched_text(
    ruleset_from, text: str, expected_replacement: str
) -> None:
    ruleset = ruleset_from(VALID_RULE)
    match = find_matches(text, rules_of(ruleset))[0]
    assert match.replacement == expected_replacement
    assert match.refusal == ""


def test_unreproducible_casing_is_refused_rather_than_guessed(ruleset_from) -> None:
    """`iN OrDeR tO` has no mechanical equivalent, so no edit is offered."""
    ruleset = ruleset_from(VALID_RULE)
    match = find_matches("register iN OrDeR tO vote", rules_of(ruleset))[0]

    assert match.refusal == REFUSAL_CASE_UNMAPPABLE
    assert match.replacement == ""


def test_a_multi_word_replacement_keeps_a_single_capital(bundled) -> None:
    """One capitalised word is sentence-shaped, not title-shaped.

    "Ascertain" at the start of a sentence should become "Find out", not "Find
    Out": the capital marks the sentence, and reproducing it on every word would
    invent emphasis the author did not write.
    """
    match = next(
        m for m in find_matches("Ascertain the facts before deciding.", bundled.rules)
        if m.rule_id == "PS.LEXICAL.010"
    )
    assert match.replacement == "Find out"


def test_a_title_cased_phrase_keeps_title_case(bundled) -> None:
    """A genuinely multi-word capitalised match does get title case back."""
    match = next(
        m for m in find_matches("Register In Order To Vote", bundled.rules)
        if m.rule_id == "PS.CLARITY.001"
    )
    assert match.matched_text == "In Order To"
    assert match.replacement == "To"


# ── Deletion, spacing and punctuation ──────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected_output_start,expected_refusal",
    [
        ("It is important to note that registration closes.", "R", ""),
        ("Note: it is important to note that registration closes.", None, REFUSAL_SPACING),
        ("It is important to note that  double spaced.", None, REFUSAL_SPACING),
        ("It is important to note that .", None, REFUSAL_SPACING),
    ],
    ids=["sentence-start", "mid-sentence", "double-space", "punctuation-follows"],
)
def test_deletion_only_happens_where_it_is_mechanically_safe(
    ruleset_from, text: str, expected_output_start, expected_refusal: str
) -> None:
    """A deletion that would leave broken spacing is refused, not attempted."""
    ruleset = ruleset_from(DELETE_RULE)
    matches = find_matches(text, rules_of(ruleset))
    assert matches, "the phrase should still be found even when the edit is refused"
    match = matches[0]

    assert match.refusal == expected_refusal
    if expected_refusal:
        assert match.replacement == ""
    else:
        assert match.replacement == expected_output_start


def test_a_deletion_that_recapitalises_extends_its_own_span(ruleset_from) -> None:
    """The edit covers one character more than the phrase it matched."""
    ruleset = ruleset_from(DELETE_RULE)
    rule = ruleset.by_id("PS.TEST.011")
    text = "It is important to note that registration closes."
    match = find_matches(text, rules_of(ruleset))[0]

    start, end = deletion_span(text, rule, match)
    assert (start, end) == (match.start, match.end + 1)
    assert text[start:end].endswith("r")
    assert match.replacement == "R"


def test_a_refused_deletion_does_not_extend_its_span(ruleset_from) -> None:
    ruleset = ruleset_from(DELETE_RULE)
    rule = ruleset.by_id("PS.TEST.011")
    text = "Note: it is important to note that registration closes."
    match = find_matches(text, rules_of(ruleset))[0]

    assert deletion_span(text, rule, match) == (match.start, match.end)


# ── Punctuation boundaries ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,should_match",
    [
        ("Prior to the hearing, evidence is filed.", True),
        ("Prior to, the hearing was adjourned.", True),
        ('"Prior to" is a stock phrase.', True),
        ("There was no prior agreement.", False),
        ("Prior art was cited.", False),
    ],
    ids=["plain", "comma-after", "quoted", "adjective", "prior-art"],
)
def test_punctuation_around_a_phrase_does_not_hide_it(bundled, text: str, should_match: bool) -> None:
    matches = [m for m in find_matches(text, bundled.rules) if m.rule_id == "PS.CLARITY.009"]
    assert bool(matches) is should_match


# ── Regex ──────────────────────────────────────────────────────────────────


def test_a_regex_rule_matches(bundled) -> None:
    matches = [
        m for m in find_matches("The application was refused by the panel.", bundled.rules)
        if m.rule_id == "PS.VOICE.001"
    ]
    assert len(matches) == 1
    assert matches[0].matched_text == "was refused"


def test_a_regex_rule_proposes_nothing(bundled) -> None:
    """Diagnostics never carry a replacement, whatever they match."""
    for match in find_matches("It was decided and it is agreed.", bundled.rules):
        if match.mode == "diagnostic":
            assert match.replacement == ""


# ── Determinism ────────────────────────────────────────────────────────────


def test_match_order_does_not_depend_on_rule_order(bundled) -> None:
    text = (
        "It is important to note that staff utilise the register in order to "
        "ascertain approximately how many additional forms are needed."
    )
    baseline = find_matches(text, bundled.rules)

    for seed in range(10):
        shuffled = list(bundled.rules)
        random.Random(seed).shuffle(shuffled)
        assert find_matches(text, shuffled) == baseline


def test_matching_the_same_text_twice_gives_the_same_answer(bundled) -> None:
    text = "In order to ascertain the facts, staff utilise the register."
    assert find_matches(text, bundled.rules) == find_matches(text, bundled.rules)


def test_matches_are_ordered_by_position_then_identity(bundled) -> None:
    text = "In order to apply, utilise the form in order to register."
    matches = find_matches(text, bundled.rules)
    keys = [match.sort_key for match in matches]
    assert keys == sorted(keys)


def test_a_rule_never_conflicts_with_itself(ruleset_from) -> None:
    """Overlapping forms of one rule must not produce two matches at one place."""
    ruleset = ruleset_from(WORD_RULE)
    matches = find_matches("utilise", rules_of(ruleset))
    assert len(matches) == 1
