"""The adversarial integrity corpus, run against the firewall.

Every case in `tests/integrity/corpus.py` is a transformation paired with the
verdict the firewall must return. Two halves, and both are load-bearing:

`MUST_REFUSE` is the point of the phase — 50 edits that read as small and change
what the document says.

`MUST_ALLOW` is what stops the firewall being useless. A safety layer that
refused everything would be trivially correct and would be switched off inside a
week, so the controls matter as much as the attacks: ordinary word
substitutions, reformattings that change no value, and prose that merely looks
like a protected fact.
"""
from __future__ import annotations

import pytest

from plainspeak.integrity import check, snapshot

from .integrity.corpus import ALL_CASES, MUST_ALLOW, MUST_REFUSE, Case


def labels(cases) -> list:
    return [case.label for case in cases]


@pytest.mark.parametrize("case", MUST_REFUSE, ids=labels(MUST_REFUSE))
def test_meaning_changing_transformations_are_refused(case: Case) -> None:
    verdict = check(case.before, case.after)

    assert not verdict.passed, (
        f"the firewall allowed a meaning change ({case.label}):\n"
        f"  {case.before!r}\n  became\n  {case.after!r}"
    )
    assert verdict.violations, "a refusal must say what it found"
    assert verdict.summary != "integrity preserved"


@pytest.mark.parametrize("case", MUST_ALLOW, ids=labels(MUST_ALLOW))
def test_harmless_transformations_are_allowed(case: Case) -> None:
    verdict = check(case.before, case.after)

    assert verdict.passed, (
        f"the firewall blocked a harmless change ({case.label}):\n"
        f"  {case.before!r}\n  became\n  {case.after!r}\n"
        f"  {verdict.summary}"
    )


@pytest.mark.parametrize("case", MUST_REFUSE, ids=labels(MUST_REFUSE))
def test_a_refusal_names_the_category_it_belongs_to(case: Case) -> None:
    """The audit shows this to a reader, so it has to be the right category."""
    verdict = check(case.before, case.after)
    kinds = {violation.kind for violation in verdict.violations}

    if case.category == "control":
        return
    assert case.category in kinds, (
        f"{case.label} was refused for {sorted(kinds)}, expected {case.category}"
    )


# ── Properties that must hold across the whole corpus ──────────────────────


@pytest.mark.parametrize("case", ALL_CASES, ids=labels(ALL_CASES))
def test_a_transformation_to_itself_always_passes(case: Case) -> None:
    """The firewall must never object to text that did not change."""
    assert check(case.before, case.before).passed
    assert check(case.after, case.after).passed


@pytest.mark.parametrize("case", MUST_REFUSE, ids=labels(MUST_REFUSE))
def test_refusal_is_symmetric(case: Case) -> None:
    """Information moving in either direction is a change.

    Removing a negation turns a prohibition into a permission; introducing one
    does the same in reverse. The firewall does not care which way it went.
    """
    assert not check(case.after, case.before).passed


@pytest.mark.parametrize("case", ALL_CASES, ids=labels(ALL_CASES))
def test_verdicts_are_deterministic(case: Case) -> None:
    first = check(case.before, case.after)
    second = check(case.before, case.after)
    assert first.passed == second.passed
    assert [v.as_dict() for v in first.violations] == [v.as_dict() for v in second.violations]


@pytest.mark.parametrize("case", ALL_CASES, ids=labels(ALL_CASES))
def test_line_endings_do_not_change_a_verdict(case: Case) -> None:
    """The same canonical text must be judged the same either way."""
    plain = check(case.before, case.after)
    windows = check(case.before.replace("\n", "\r\n"), case.after.replace("\n", "\r\n"))
    assert plain.passed == windows.passed


@pytest.mark.parametrize("case", ALL_CASES, ids=labels(ALL_CASES))
def test_every_snapshot_names_the_policy_that_made_it(case: Case) -> None:
    """A snapshot from another policy says nothing about this one."""
    for text in (case.before, case.after):
        taken = snapshot(text)
        assert taken.policy_version
        assert len(taken.policy_hash) == 64
        assert taken.text_hash == snapshot(text).text_hash


# ── The corpus itself ──────────────────────────────────────────────────────


def test_the_corpus_covers_every_protected_category() -> None:
    """A category with no adversarial case is a category nobody has attacked."""
    from plainspeak.integrity import KINDS

    covered = {case.category for case in MUST_REFUSE}
    missing = sorted(set(KINDS) - covered)
    assert not missing, f"protected categories with no must-refuse case: {missing}"


def test_the_corpus_has_meaningful_controls() -> None:
    """Enough must-allow cases that the firewall cannot pass by refusing all."""
    controls = [case for case in MUST_ALLOW if case.category == "control"]
    assert len(MUST_ALLOW) >= 20
    assert len(controls) >= 8, "look-alike controls are what keep the firewall usable"


def test_every_case_actually_changes_the_text() -> None:
    """A pair whose halves are identical would prove nothing either way."""
    for case in ALL_CASES:
        assert case.before != case.after, f"{case.label} is not a transformation"


def test_case_labels_are_unique() -> None:
    """Duplicate ids would make a failure report ambiguous."""
    seen = [case.label for case in ALL_CASES]
    duplicates = sorted({label for label in seen if seen.count(label) > 1})
    assert not duplicates, f"duplicate corpus labels: {duplicates}"
