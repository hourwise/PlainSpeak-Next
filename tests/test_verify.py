"""`plainspeak verify`: judging a transformation somebody else made.

Most of these are adversarial. Verify's value is in what it refuses and what it
declines to vouch for; a verifier that accepted everything would pass every
test that only checked the happy path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plainspeak.pipeline import present_text
from plainspeak.pipeline.verify import (
    ACCEPTED,
    EQUIVALENCE_FACT,
    EQUIVALENCE_FORMATTING,
    EQUIVALENCE_MOVE,
    EQUIVALENCE_RULE,
    ERROR_EMPTY_INPUT,
    ERROR_FORMAT_MISMATCH,
    ERROR_UNREADABLE_INPUT,
    ERROR_UNSUPPORTED_INPUT,
    INCONCLUSIVE,
    RECEIPT_SCHEMA,
    REFUSAL_FACT,
    REFUSAL_REGION,
    REFUSAL_TERM,
    REFUSED,
    UNRESOLVED_MOVED,
    UNRESOLVED_WORDING,
    VERIFY_SCHEMA,
    VerifyError,
    verify,
    verify_files,
    verify_policy_hash,
    verify_text,
)
from plainspeak.pipeline.review import parse_source

CORPUS = Path(__file__).resolve().parent / "acceptance" / "corpus"

BEFORE = (
    "# Account migration\n\n"
    "In order to finish, you must utilize the new portal prior to 30 June 2027. "
    "It should be noted that the old portal will not accept payments of £42.50 or more.\n\n"
    "Your reference, ACC-20931, does not change. Statements arrive within 5 working days.\n"
)


def result_of(after: str, before: str = BEFORE, markdown: bool = True):
    return verify_text(before, after, markdown=markdown)


def codes(items) -> list[str]:
    return [item["code"] for item in items]


# ── Accepted ───────────────────────────────────────────────────────────────


def test_identical_text_is_accepted():
    result = result_of(BEFORE)
    assert result.result == ACCEPTED
    assert result.identical
    assert not result.refusals and not result.unresolved


def test_line_endings_and_reflowed_lines_are_formatting():
    result = result_of(BEFORE.replace("\n", "\r\n"))
    assert result.result == ACCEPTED
    assert codes(result.equivalences) == [EQUIVALENCE_FORMATTING]

    reflowed = BEFORE.replace("It should be noted", "It should be\nnoted")
    assert result_of(reflowed).result == ACCEPTED


def test_plainspeak_present_output_is_accepted_and_explained():
    presented = present_text(BEFORE, "natural").text
    result = result_of(presented)
    assert result.result == ACCEPTED
    explained = {(item["before"], item["after"]) for item in result.equivalences
                 if item["code"] == EQUIVALENCE_RULE}
    assert ("utilize", "use") in explained
    assert ("in order to", "to") in explained


def test_a_subset_of_safe_changes_is_accepted():
    result = result_of(BEFORE.replace("utilize", "use"))
    assert result.result == ACCEPTED
    assert [item["kind"] for item in result.equivalences] == ["PS.LEXICAL.001"]


def test_a_safe_change_in_reverse_is_accepted():
    """A reviewed equivalence holds in both directions."""
    result = verify_text("Please use the new portal.\n", "Please utilize the new portal.\n")
    assert result.result == ACCEPTED
    assert result.equivalences[0]["detail"].endswith("in reverse")


def test_a_fact_equivalence_is_accepted_and_reported():
    result = verify_text("The fee is £2,500 this year.\n", "The fee is £2500 this year.\n")
    assert result.result == ACCEPTED
    assert codes(result.equivalences) == [EQUIVALENCE_FACT]


def test_a_time_phrase_may_move_within_its_sentence():
    before = "You must submit the form before 5pm.\n"
    after = "Before 5pm, you must submit the form.\n"
    result = verify_text(before, after)
    assert result.result == ACCEPTED
    assert codes(result.equivalences) == [EQUIVALENCE_MOVE]


def test_a_paragraph_break_between_sentences_is_formatting():
    result = result_of(BEFORE.replace("It should be noted", "\nIt should be noted"))
    assert result.result == ACCEPTED


def test_capitalisation_is_formatting_only_when_a_word_changes_position():
    """A word that became, or stopped being, a sentence's first word may change case.

    A word that is first in both texts and changed case is not accounted for:
    without a lexicon, "you" to "You" cannot be told from "Polish" to "polish"
    (validation study case X04, a false acceptance under policy 2026.1).
    """
    moved = verify_text("You must submit the form before 5pm.\n", "Before 5pm, you must submit the form.\n")
    assert moved.result == ACCEPTED
    assert verify_text("Polish workers must register.\n", "polish workers must register.\n").result \
        == INCONCLUSIVE
    assert verify_text("The deadline is 5pm. you must attend.\n",
                       "The deadline is 5pm. You must attend.\n").result == INCONCLUSIVE


@pytest.mark.parametrize(
    "before,after",
    [
        # Study case X02: the fronted deadline now reads as governing both actions.
        ("You must submit the form before 5pm and pay the fee.\n",
         "Before 5pm, you must submit the form and pay the fee.\n"),
        # Study case X01: the deadline moved onto a different action.
        ("Submit the form within 5 days and pay the fee.\n",
         "Submit the form and pay the fee within 5 days.\n"),
        ("If you can, submit the form before 5pm.\n", "Before 5pm, if you can, submit the form.\n"),
        ("Submit the form before 5pm unless told otherwise.\n",
         "Before 5pm, submit the form unless told otherwise.\n"),
        # The phrase moved, and the rest of the sentence was reworded too.
        ("You must submit the form before 5pm.\n", "Before 5pm, you must send the form.\n"),
    ],
)
def test_a_time_phrase_moves_only_in_a_single_clause_sentence(before, after):
    assert verify_text(before, after).result == INCONCLUSIVE


# ── Refused: protected facts ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "old,new,kind",
    [
        ("£42.50", "£45.50", "currency"),
        ("30 June 2027", "30 July 2027", "date"),
        ("30 June 2027", "30 June 2028", "date"),
        ("5 working days", "15 working days", "number"),
        ("ACC-20931", "ACC-20932", "number"),
        ("will not accept", "will accept", "negation"),
        ("does not change", "does change", "negation"),
        ("you must", "you should", "modal"),
        ("It should be", "It must be", "modal"),
        ("within 5", "in 5", "comparator"),
        ("prior to", "after", "comparator"),
    ],
)
def test_changing_a_protected_fact_is_refused(old, new, kind):
    assert old in BEFORE
    result = result_of(BEFORE.replace(old, new, 1))
    assert result.result == REFUSED
    assert REFUSAL_FACT in codes(result.refusals)
    assert kind in {item["kind"] for item in result.refusals}


def test_must_to_should_and_back_are_both_refused():
    assert verify_text("You must pay.\n", "You should pay.\n").result == REFUSED
    assert verify_text("You should pay.\n", "You must pay.\n").result == REFUSED


def test_deleting_a_sentence_that_carries_facts_is_refused():
    result = result_of(BEFORE.replace("Statements arrive within 5 working days.", ""))
    assert result.result == REFUSED
    assert {item["kind"] for item in result.refusals} == {"comparator", "number"}


def test_adding_protected_meaning_is_refused():
    assert result_of(BEFORE + "\nYou may also pay 10% extra.\n").result == REFUSED
    assert verify_text("Submit the form.\n", "Do not submit the form.\n").result == REFUSED
    assert verify_text("Submit the form.\n", "Submit the form before Friday.\n").result == REFUSED


@pytest.mark.parametrize(
    "before,after",
    [
        ("Reply within 5 days.\n", "Reply in 5 days.\n"),
        ("Pay at least £40.\n", "Pay £40 or more.\n"),
        ("Finish no later than 5pm.\n", "Finish by 5pm.\n"),
        ("Take 5 mg daily.\n", "Take 5 g daily.\n"),
        ("Take 0.5 mg daily.\n", "Take 5 mg daily.\n"),
        ("You cannot leave.\n", "You can leave.\n"),
        ("Only members may vote.\n", "Members may vote.\n"),
    ],
)
def test_near_equivalences_do_not_pass(before, after):
    """Plausible paraphrases the model cannot establish are never accepted."""
    assert verify_text(before, after).result == REFUSED


def test_a_refusal_points_at_the_occurrence_that_changed():
    """A lost "will" is the one that went, not every "will" in the text."""
    before = "It will rain.\n\nThe bus will stop.\n\nWe will see.\n"
    after = "It will rain.\n\nThe bus stops.\n\nWe will see.\n"
    refusal = verify_text(before, after).refusals[0]
    assert refusal["kind"] == "modal"
    assert refusal["before_lines"] == [3]


def test_the_refusal_says_where():
    result = result_of(BEFORE.replace("£42.50", "£45.50"))
    refusal = result.refusals[0]
    assert refusal["before"] == ["£42.50"] and refusal["after"] == ["£45.50"]
    assert refusal["before_lines"] == [3] and refusal["after_lines"] == [3]


# ── Refused: terms of art and untouchable regions ──────────────────────────


def test_substituting_a_term_of_art_is_refused():
    result = verify_text("The party must indemnify the landlord.\n",
                         "The party must protect the landlord.\n")
    assert result.result == REFUSED
    assert codes(result.refusals) == [REFUSAL_TERM]


def test_substituting_a_declared_protected_phrase_is_refused():
    result = verify_text("Informed consent was obtained.\n", "Told consent was obtained.\n")
    assert result.result == REFUSED
    assert codes(result.refusals) == [REFUSAL_TERM]


DOCUMENT = (
    "Run the installer.\n\n```bash\npip install example==2.4.1\n```\n\n"
    "> The tenant shall give notice within 30 days.\n\n"
    "See [the guide](https://example.com/guide) for details.\n\n"
    "| a | b |\n|---|---|\n| 1 | 2 |\n"
)


@pytest.mark.parametrize(
    "old,new,kind",
    [
        ("example==2.4.1", "example==2.4.2", "code"),
        ("Run the installer.\n\n```bash\n", "Run the installer.\n\n```sh\n", "code"),
        ("give notice", "tell us", "quote"),
        ("example.com/guide", "example.org/guide", "link destination"),
        ("| 1 | 2 |", "| 1 | 3 |", "table"),
    ],
)
def test_changing_a_region_plainspeak_never_rewrites_is_refused(old, new, kind):
    result = verify_text(DOCUMENT, DOCUMENT.replace(old, new))
    assert result.result == REFUSED
    assert any(item["code"] == REFUSAL_REGION and kind in item["kind"] for item in result.refusals)


def test_relayout_of_a_quotation_or_table_is_not_a_change():
    rewrapped = DOCUMENT.replace("> The tenant shall give notice within 30 days.",
                                 "> The tenant shall give notice\n> within 30 days.")
    assert verify_text(DOCUMENT, rewrapped).result == ACCEPTED
    realigned = DOCUMENT.replace("|---|---|", "|------|-----|")
    assert verify_text(DOCUMENT, realigned).result == ACCEPTED


# ── Inconclusive ───────────────────────────────────────────────────────────


def test_rewording_is_not_accepted_even_when_facts_survive():
    """The facts surviving is not the same claim as nothing that matters changing."""
    result = result_of(BEFORE.replace("Statements arrive", "Statements leave"))
    assert result.result == INCONCLUSIVE
    assert codes(result.unresolved) == [UNRESOLVED_WORDING]
    assert result.unresolved[0]["before"] == "arrive"
    assert result.unresolved[0]["after"] == "leave"


def test_deleting_or_adding_a_fact_free_sentence_is_inconclusive():
    assert result_of(BEFORE.replace("# Account migration\n\n", "")).result == INCONCLUSIVE
    assert result_of(BEFORE + "\nThank you for reading.\n").result == INCONCLUSIVE


def test_swapped_values_are_never_accepted():
    """The V1 multiset check alone would pass this: both amounts are still there."""
    result = verify_text("Pay £5 before Monday and £10 after Friday.\n",
                         "Pay £10 before Monday and £5 after Friday.\n")
    assert result.result == INCONCLUSIVE
    assert UNRESOLVED_MOVED in codes(result.unresolved)


def test_swapped_obligations_are_never_accepted():
    result = verify_text("You must pay. You may leave.\n", "You may pay. You must leave.\n")
    assert result.result == INCONCLUSIVE
    assert UNRESOLVED_MOVED in codes(result.unresolved)


def test_a_time_phrase_may_not_move_to_another_sentence():
    result = verify_text("Submit the form. Pay the fee before 5pm.\n",
                         "Submit the form before 5pm. Pay the fee.\n")
    assert result.result == INCONCLUSIVE
    assert set(codes(result.unresolved)) == {UNRESOLVED_MOVED}


def test_a_negated_comparator_does_not_move():
    result = verify_text("You may apply, but not before 5pm.\n",
                         "Before 5pm, you may apply, but not.\n")
    assert result.result != ACCEPTED


def test_capitalisation_mid_sentence_is_not_formatting():
    result = verify_text("We ship to the polish office.\n", "We ship to the Polish office.\n")
    assert result.result == INCONCLUSIVE


def test_an_unlocatable_document_is_inconclusive(monkeypatch):
    from plainspeak.document.model import REASON_UNLOCATABLE

    before = parse_source("Pay £5 today.\n")
    after = parse_source("Pay £5 today, please.\n")
    after.blocks[0].untransformable_reason = REASON_UNLOCATABLE
    assert verify(before, after).result == INCONCLUSIVE


# ── Errors are not results ─────────────────────────────────────────────────


def test_an_empty_before_text_is_an_error():
    with pytest.raises(VerifyError) as caught:
        verify_text("   \n", "Something.\n")
    assert caught.value.code == ERROR_EMPTY_INPUT


def test_an_empty_after_text_is_verified():
    assert verify_text("Pay £5.\n", "").result == REFUSED
    assert verify_text("Hello there.\n", "").result == INCONCLUSIVE


def test_documents_of_different_formats_are_refused_as_input():
    with pytest.raises(VerifyError) as caught:
        verify(parse_source("Hi.\n", markdown=True), parse_source("Hi.\n", markdown=False))
    assert caught.value.code == ERROR_FORMAT_MISMATCH


def test_file_errors_carry_codes(tmp_path):
    before = tmp_path / "before.md"
    before.write_text("Pay £5.\n", encoding="utf-8")
    with pytest.raises(VerifyError) as caught:
        verify_files(before, tmp_path / "missing.md")
    assert caught.value.code == ERROR_UNREADABLE_INPUT
    docx = tmp_path / "after.docx"
    docx.write_bytes(b"PK")
    with pytest.raises(VerifyError) as caught:
        verify_files(docx, before)
    assert caught.value.code == ERROR_UNSUPPORTED_INPUT
    latin = tmp_path / "latin.md"
    latin.write_bytes("caf\xe9".encode("latin-1"))
    with pytest.raises(VerifyError) as caught:
        verify_files(before, latin)
    assert caught.value.code == ERROR_UNREADABLE_INPUT


def test_file_hashes_are_the_hashes_of_the_files(tmp_path):
    import hashlib

    before, after = tmp_path / "a.md", tmp_path / "b.md"
    before.write_bytes("Pay £5 today.\r\n".encode("utf-8"))
    after.write_bytes("Pay £5 today.\n".encode("utf-8"))
    result = verify_files(before, after)
    assert result.before_sha256 == hashlib.sha256(before.read_bytes()).hexdigest()
    assert result.after_sha256 == hashlib.sha256(after.read_bytes()).hexdigest()
    assert result.result == ACCEPTED


def test_text_format_is_supported():
    assert verify_text("Pay £5 today.\n", "Pay £6 today.\n", markdown=False).result == REFUSED
    assert verify_text("Pay £5 today.\n", "Pay £5 today.\n", markdown=False).result == ACCEPTED


# ── The contract and the receipt ───────────────────────────────────────────


def test_the_json_contract():
    result = result_of(BEFORE.replace("utilize", "use"))
    data = json.loads(result.to_json())
    assert data["schema"] == VERIFY_SCHEMA
    assert data["status"] == "ok"
    assert data["result"] == ACCEPTED
    for key in ("before", "after", "engine", "verify_policy", "protected", "equivalences",
                "refusals", "unresolved", "receipt", "counts", "identical", "input_format",
                "plainspeak_version", "notes"):
        assert key in data
    assert data["before"]["sha256"] == result.before_sha256
    assert data["protected"]["count"] == len(data["protected"]["items"]) > 0
    for key in ("integrity_version", "integrity_sha256", "ruleset_version", "ruleset_sha256",
                "morphology_version", "morphology_sha256"):
        assert data["engine"][key]


def test_json_is_deterministic():
    after = BEFORE.replace("Statements arrive", "Statements leave").replace("utilize", "use")
    first, second = result_of(after).to_json(), result_of(after).to_json()
    assert first == second
    assert first.endswith("\n") and "\r" not in first


def test_the_receipt_is_deterministic_and_identifies_the_decision():
    after = BEFORE.replace("utilize", "use")
    one, two = result_of(after), result_of(after)
    assert one.receipt == two.receipt
    assert one.receipt["payload"]["schema"] == RECEIPT_SCHEMA
    assert one.receipt["payload"]["result"] == ACCEPTED
    assert one.receipt["payload"]["verify_policy"]["sha256"] == verify_policy_hash()

    import hashlib

    from plainspeak.rules import canonical_json

    payload = canonical_json(one.receipt["payload"]).encode("utf-8")
    assert one.receipt_id == hashlib.sha256(payload).hexdigest()

    other = result_of(BEFORE.replace("£42.50", "£45.50"))
    assert other.receipt_id != one.receipt_id
    assert json.loads(one.receipt_json()) == one.receipt


def test_the_receipt_moves_with_the_inputs():
    assert result_of(BEFORE).receipt_id != result_of(BEFORE + "\n").receipt_id


# ── PlainSpeak against itself ──────────────────────────────────────────────


@pytest.mark.parametrize("path", sorted(CORPUS.glob("*.md")), ids=lambda path: path.stem)
def test_every_corpus_document_verifies_against_its_own_presentation(path):
    """What `present` does must be something `verify` accepts.

    If it were not, the two halves of PlainSpeak would disagree about what a
    safe transformation is.
    """
    text = path.read_text(encoding="utf-8")
    assert verify_text(text, text).result == ACCEPTED
    presented = present_text(text, "natural").text
    result = verify_text(text, presented)
    assert result.result == ACCEPTED, (result.refusals, result.unresolved)


def test_the_walkthrough_verify_example_does_what_the_walkthrough_says():
    """WALKTHROUGH.md step 7 shows real output. If the engine changes it, the page is wrong."""
    root = Path(__file__).resolve().parent.parent
    original = (root / "examples" / "agent_reply.md").read_text(encoding="utf-8")
    walkthrough = (root / "WALKTHROUGH.md").read_text(encoding="utf-8")

    presented = present_text(original, "natural").text
    accepted = verify_text(original, presented)
    assert accepted.result == ACCEPTED
    for item in accepted.equivalences:
        assert f"PlainSpeak SAFE rule {item['kind']} '{item['before']}' -> '{item['after']}'" in walkthrough

    edited = original.replace("Nevertheless, some features will move.", "Some features are moving.") \
        .replace("at least 12 characters", "at least 10 characters")
    refused = verify_text(original, edited)
    assert refused.result == REFUSED
    assert [(item["kind"], item["before_lines"], item["after_lines"]) for item in refused.refusals] == [
        ("modal", [7], []), ("number", [11], [11]),
    ]
    assert "[modal] modal removed: will  (before line 7)" in walkthrough
    assert "[number] number changed: 12 became 10  (before line 11; after line 11)" in walkthrough
