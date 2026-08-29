"""What the integrity firewall recognises, and what it deliberately does not.

Two failure modes matter here and they pull in opposite directions.

**Missing a fact** means a transformation can change it silently. That is the
serious one: a dose, a deadline, a modal verb.

**Inventing a fact** means ordinary prose gets frozen for no reason. That is
merely annoying, but enough of it would make the firewall useless in practice
and tempt somebody to loosen it.

So every category is tested from both sides: the shapes it must catch, and the
lookalikes it must leave alone. `notable` is not a negation, `decade` is not a
hash, and a slash in a sentence is not a file path.
"""
from __future__ import annotations

import pytest

from plainspeak.integrity import KINDS, extract, snapshot


def kinds_in(text: str) -> set[str]:
    return {fact.kind for fact in extract(text)}


def surfaces(text: str, kind: str) -> list[str]:
    return [fact.surface for fact in extract(text) if fact.kind == kind]


def normalized(text: str, kind: str) -> list[str]:
    return [fact.normalized for fact in extract(text) if fact.kind == kind]


# ── Numbers ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Take 5 tablets.", ["5"]),
        ("Take 0.5 tablets.", ["0.5"]),
        ("Around 1,000 people.", ["1,000"]),
        ("Around 1,000.25 exactly.", ["1,000.25"]),
        ("A change of -12 points.", ["-12"]),
        ("A change of +3 points.", ["+3"]),
        ("Between 5 and 10.", ["5", "10"]),
    ],
    ids=["integer", "decimal", "thousands", "thousands-decimal", "negative",
         "positive", "two-numbers"],
)
def test_numbers_are_found(text: str, expected: list) -> None:
    assert surfaces(text, "number") == expected


def test_thousands_separators_do_not_change_a_value() -> None:
    """Reformatting is not a change of meaning; the digits are."""
    assert normalized("1,000.25", "number") == normalized("1000.25", "number")
    assert normalized("+3", "number") == normalized("3", "number")
    assert normalized("-3", "number") != normalized("3", "number")


# ── Percentages ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Growth of 14%.", "14%"),
        ("Growth of 14.7%.", "14.7%"),
        ("Growth of 14.7 %.", "14.7%"),
        ("Growth of 0.5 percent.", "0.5%"),
        ("Growth of 12 per cent.", "12%"),
    ],
    ids=["integer", "decimal", "spaced", "word", "two-words"],
)
def test_percentages_normalise_to_one_form(text: str, expected: str) -> None:
    assert normalized(text, "percentage") == [expected]


def test_a_percentage_is_not_also_a_bare_number() -> None:
    """The more specific category claims the digits."""
    assert surfaces("Growth of 14.7%.", "number") == []


# ── Currency ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("It costs £2,500.", "GBP 2500"),
        ("It costs $25.99.", "USD 25.99"),
        ("It costs €10.", "EUR 10"),
        ("It costs GBP 100.", "GBP 100"),
        ("It costs USD 50.", "USD 50"),
        ("It costs 12.50 EUR.", "EUR 12.50"),
    ],
    ids=["gbp-symbol", "usd-symbol", "eur-symbol", "gbp-code", "usd-code", "trailing-code"],
)
def test_currency_carries_its_identity(text: str, expected: str) -> None:
    assert normalized(text, "currency") == [expected]


def test_the_same_amount_in_two_currencies_is_two_different_facts() -> None:
    """Swapping the symbol leaves the digits alone and changes the amount."""
    assert normalized("£2,500", "currency") != normalized("$2,500", "currency")


# ── Units ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Take 0.5 mg.", "0.5 mg"),
        ("Take 5mg.", "5 mg"),
        ("Add 500 mL.", "500 mL"),
        ("Drive at 30 mph.", "30 mph"),
        ("Store at 25 °C.", "25 °C"),
        ("Wait 250 ms.", "250 ms"),
        ("Allow 2 GB.", "2 GB"),
    ],
    ids=["mg", "no-space", "millilitres", "speed", "temperature", "milliseconds", "data"],
)
def test_measurements_pair_a_value_with_its_unit(text: str, expected: str) -> None:
    assert normalized(text, "measurement") == [expected]


def test_the_same_number_with_a_different_unit_is_a_different_fact() -> None:
    """A thousandfold dosing error reads as a one-character edit."""
    assert normalized("5 mg", "measurement") != normalized("5 g", "measurement")


def test_an_unrecognised_unit_leaves_an_ordinary_number() -> None:
    """No guessing at unit syntax: the number is still protected."""
    assert surfaces("Take 5 widgets.", "measurement") == []
    assert surfaces("Take 5 widgets.", "number") == ["5"]


# ── Dates and times ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    ["Due 2026-08-29.", "Due 29 August 2026.", "Due August 29, 2026.",
     "Due 29/08/2026.", "Due 08/29/2026."],
    ids=["iso", "day-month-year", "month-day-year", "slash-dmy", "slash-mdy"],
)
def test_dates_are_found(text: str) -> None:
    assert len(surfaces(text, "date")) == 1


def test_slash_dates_are_protected_by_surface_not_interpretation() -> None:
    """No locale resolution: 08/29 and 29/08 are simply different surfaces."""
    assert normalized("29/08/2026", "date") != normalized("08/29/2026", "date")


@pytest.mark.parametrize(
    "text,count",
    [("At 14:30.", 1), ("At 14:30:00.", 1), ("At 4pm.", 1), ("At 4:30 PM.", 1)],
    ids=["hh-mm", "hh-mm-ss", "bare-pm", "twelve-hour"],
)
def test_times_are_found(text: str, count: int) -> None:
    assert len(surfaces(text, "time")) == count


def test_transposed_digits_in_a_time_are_a_different_fact() -> None:
    assert normalized("14:30", "time") != normalized("14:03", "time")


# ── Addresses and identifiers ──────────────────────────────────────────────


def test_a_url_is_protected_whole() -> None:
    text = "See https://example.com/file?id=17#section for details."
    assert surfaces(text, "url") == ["https://example.com/file?id=17#section"]
    assert surfaces(text, "number") == [], "a URL's digits are part of the URL"


def test_a_trailing_full_stop_is_not_part_of_the_url() -> None:
    assert surfaces("Visit https://example.com/page.", "url") == ["https://example.com/page"]


def test_emails_are_protected_exactly() -> None:
    assert surfaces("Write to case.work+ref@example.gov.uk today.", "email") == [
        "case.work+ref@example.gov.uk"
    ]


@pytest.mark.parametrize(
    "text,expected",
    [
        (r"Open C:\Projects\file.txt now.", r"C:\Projects\file.txt"),
        ("Open D:/work/report.md now.", "D:/work/report.md"),
        ("Open /home/user/file.txt now.", "/home/user/file.txt"),
        ("Open ./docs/readme.md now.", "./docs/readme.md"),
        ("Open ../config/settings.yaml now.", "../config/settings.yaml"),
    ],
    ids=["windows-backslash", "windows-forward", "posix", "relative", "parent"],
)
def test_file_paths_are_found(text: str, expected: str) -> None:
    assert surfaces(text, "path") == [expected]


@pytest.mark.parametrize(
    "text",
    [
        "Choose yes/no on the form.",
        "The and/or clause applies.",
        "It costs 5 per person/day.",
        "Read the terms and conditions carefully.",
    ],
    ids=["yes-no", "and-or", "per-unit", "plain-prose"],
)
def test_ordinary_prose_with_slashes_is_not_a_path(text: str) -> None:
    """Over-detection here would freeze half the sentences in a document."""
    assert surfaces(text, "path") == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Affects v1.5.0.", "v1.5.0"),
        ("Affects 1.5.0.", "1.5.0"),
        ("Affects 2.0.0-beta.1.", "2.0.0-beta.1"),
        ("Affects v2.0.", "v2.0"),
    ],
    ids=["v-prefix", "three-part", "pre-release", "v-two-part"],
)
def test_versions_are_found(text: str, expected: str) -> None:
    assert surfaces(text, "version") == [expected]


def test_a_bare_two_part_decimal_is_a_number_not_a_version() -> None:
    """"Version 1.5" and "1.5 metres" look identical; the number is protected either way."""
    assert surfaces("The value is 1.5 exactly.", "version") == []
    assert surfaces("The value is 1.5 exactly.", "number") == ["1.5"]


def test_cve_identifiers_are_found() -> None:
    assert surfaces("See CVE-2026-12345 for details.", "cve") == ["CVE-2026-12345"]


def test_uuids_are_found() -> None:
    text = "Reference 550e8400-e29b-41d4-a716-446655440000 applies."
    assert surfaces(text, "uuid") == ["550e8400-e29b-41d4-a716-446655440000"]


def test_long_hex_runs_are_treated_as_digests() -> None:
    digest = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    assert surfaces(f"The checksum is {digest}.", "hash") == [digest]


@pytest.mark.parametrize("word", ["decade", "faced", "added", "beaded", "defaced"])
def test_short_hex_looking_words_are_not_digests(word: str) -> None:
    """"decade" is valid hexadecimal and is also an ordinary English word."""
    assert surfaces(f"Over a {word} of work.", "hash") == []


# ── Logic ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    ["You must not apply.", "You cannot apply.", "You can't apply.", "You won't apply.",
     "There is no fee.", "It never applies.", "Apply without delay.",
     "Neither option works.", "Nor does the other."],
    ids=["not", "cannot", "cant", "wont", "no", "never", "without", "neither", "nor"],
)
def test_negation_markers_are_found(text: str) -> None:
    assert surfaces(text, "negation"), f"no negation found in {text!r}"


@pytest.mark.parametrize(
    "word",
    ["notable", "notably", "notice", "notation", "nothing", "november", "cannonball", "nowhere"],
)
def test_words_containing_negation_letters_are_not_negations(word: str) -> None:
    """The classic substring bug: "not" inside "notable"."""
    assert surfaces(f"A {word} example.", "negation") == []


def test_a_contraction_is_one_negation_not_a_modal_plus_punctuation() -> None:
    """`can't` must not also yield the modal `can`."""
    facts = extract("You can't apply.")
    assert [fact.kind for fact in facts] == ["negation"]


@pytest.mark.parametrize(
    "word", ["must", "shall", "may", "can", "should", "will", "would", "could", "might"]
)
def test_modal_verbs_are_found(word: str) -> None:
    assert surfaces(f"You {word} apply.", "modal") == [word]


@pytest.mark.parametrize(
    "phrase",
    ["at least", "at most", "more than", "less than", "greater than", "fewer than",
     "before", "after", "within", "until", "unless", "only"],
)
def test_comparators_are_found(phrase: str) -> None:
    assert surfaces(f"Provide {phrase} the stated amount.", "comparator") == [phrase]


def test_a_multi_word_comparator_claims_its_whole_phrase() -> None:
    """"at least" must not be recorded as something plus a stray word."""
    assert surfaces("Provide at least 5.", "comparator") == ["at least"]


# ── Interaction and boundaries ─────────────────────────────────────────────


def test_a_month_name_in_a_date_is_not_the_modal_may() -> None:
    """Dates claim their text before modals get a chance at it."""
    assert surfaces("Due 29 May 2026.", "modal") == []
    assert len(surfaces("Due 29 May 2026.", "date")) == 1


def test_repeated_facts_are_recorded_separately() -> None:
    """Counts matter: losing one of two identical doses is a change."""
    assert surfaces("Take 5 mg, then 5 mg again.", "measurement") == ["5 mg", "5 mg"]


def test_adjacent_facts_do_not_swallow_each_other() -> None:
    facts = extract("Pay £250 by 2026-08-29 at 14:30.")
    assert [fact.kind for fact in facts] == ["currency", "date", "time"]


def test_facts_are_returned_in_document_order() -> None:
    facts = extract("You must pay £250 before 2026-08-29.")
    assert [fact.start for fact in facts] == sorted(fact.start for fact in facts)


def test_offsets_point_at_the_surface_they_claim() -> None:
    text = "Take 0.5 mg before 14:30 on 2026-08-29."
    for fact in extract(text):
        assert text[fact.start : fact.end] == fact.surface


@pytest.mark.parametrize(
    "text",
    ['The dose is "0.5 mg" exactly.', "The dose is (0.5 mg) exactly.",
     "The dose is —0.5 mg— exactly.", "The dose is ‘0.5 mg’ exactly."],
    ids=["quotes", "brackets", "em-dashes", "smart-quotes"],
)
def test_punctuation_around_a_fact_does_not_hide_it(text: str) -> None:
    assert "0.5 mg" in surfaces(text, "measurement")


def test_line_endings_do_not_change_which_facts_are_found() -> None:
    lf = "Take 0.5 mg.\nPay £250 by 2026-08-29.\n"
    crlf = lf.replace("\n", "\r\n")
    assert [f.identity for f in extract(lf)] == [f.identity for f in extract(crlf)]


def test_extraction_is_deterministic() -> None:
    text = "Take 0.5 mg before 14:30 on 2026-08-29, costing £250 (14.7% more)."
    assert extract(text) == extract(text)


def test_an_empty_document_has_no_facts() -> None:
    assert extract("") == ()
    assert len(snapshot("")) == 0


def test_every_declared_kind_is_reachable() -> None:
    """A category nobody can trigger is a category nobody has tested."""
    text = (
        "You must not pay more than £2,500 or 14.7% of 1,000 before 2026-08-29 "
        "at 14:30, taking 0.5 mg. See https://example.com/x, email a@b.com, "
        "read /etc/app.conf, install v1.5.0, note CVE-2026-12345 and "
        "550e8400-e29b-41d4-a716-446655440000 with digest "
        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08."
    )
    assert kinds_in(text) == set(KINDS)
