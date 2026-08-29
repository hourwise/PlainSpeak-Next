"""Bounded deterministic morphology.

This exists to stop the engine writing words that do not exist. The inherited
simplifier stripped suffixes and hoped, and suggested the verb "clare" for the
noun "clarity". Nothing here guesses: regular inflection follows stated rules,
everything those rules would get wrong is in a reviewed table, and anything the
engine cannot do it refuses to do.

The tests fall into three groups: the forms it produces, the forms it *declines*
to produce, and the identity that pins both.
"""
from __future__ import annotations

import pytest

from plainspeak.morphology import (
    CASE_SHAPES,
    FORM_CLASSES,
    MORPHOLOGY_VERSION,
    MorphologyError,
    apply_shape,
    canonical_json,
    forms_for,
    inflected_pairs,
    match_casing,
    policy_document,
    policy_hash,
    shape_of,
)
from plainspeak.morphology import policy as policy_module

#: The morphology as it currently ships, pinned so that the Windows, Linux and
#: macOS jobs all assert the same number rather than each comparing itself to
#: itself. Updating it is correct when the policy changes; a diff that touches
#: `morphology/policy.py` without touching this line has changed what the engine
#: can say without meaning to.
MORPHOLOGY_HASH = "93fba6907f874be5ec2832b5784874754c366f4c37ea5820a55a48513cf13263"


# ── Regular verbs ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "lemma,expected",
    [
        ("use", {"third_person": "uses", "past": "used", "gerund": "using"}),
        ("help", {"third_person": "helps", "past": "helped", "gerund": "helping"}),
        ("watch", {"third_person": "watches", "past": "watched", "gerund": "watching"}),
        ("pass", {"third_person": "passes", "past": "passed", "gerund": "passing"}),
        ("fix", {"third_person": "fixes", "past": "fixed", "gerund": "fixing"}),
        ("go", {"third_person": "goes", "past": "went", "gerund": "going"}),
        ("try", {"third_person": "tries", "past": "tried", "gerund": "trying"}),
        ("play", {"third_person": "plays", "past": "played", "gerund": "playing"}),
        ("agree", {"third_person": "agrees", "past": "agreed", "gerund": "agreeing"}),
        ("stop", {"third_person": "stops", "past": "stopped", "gerund": "stopping"}),
        ("permit", {"third_person": "permits", "past": "permitted", "gerund": "permitting"}),
        ("cancel", {"third_person": "cancels", "past": "cancelled", "gerund": "cancelling"}),
    ],
    ids=["silent-e", "regular", "ch", "double-s", "x", "o", "consonant-y", "vowel-y",
         "ee", "doubling", "doubling-stress", "british-doubling"],
)
def test_regular_verb_inflection(lemma: str, expected: dict) -> None:
    produced = forms_for(lemma, "verb")
    for form, want in expected.items():
        assert produced[form] == want, f"{lemma} {form}: got {produced[form]!r}, want {want!r}"


def test_a_regular_verb_shares_its_past_and_participle() -> None:
    produced = forms_for("help", "verb")
    assert produced["past"] == produced["past_participle"] == "helped"


# ── Irregular verbs ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "lemma,third,past,participle,gerund",
    [
        ("begin", "begins", "began", "begun", "beginning"),
        ("make", "makes", "made", "made", "making"),
        ("do", "does", "did", "done", "doing"),
        ("show", "shows", "showed", "shown", "showing"),
        ("spread", "spreads", "spread", "spread", "spreading"),
        ("mean", "means", "meant", "meant", "meaning"),
        ("speed", "speeds", "sped", "sped", "speeding"),
        ("undertake", "undertakes", "undertook", "undertaken", "undertaking"),
    ],
)
def test_irregular_verbs_come_from_the_table(
    lemma: str, third: str, past: str, participle: str, gerund: str
) -> None:
    """Every one of these was written out and read, not derived."""
    produced = forms_for(lemma, "verb")
    assert produced["third_person"] == third
    assert produced["past"] == past
    assert produced["past_participle"] == participle
    assert produced["gerund"] == gerund


def test_every_irregular_entry_is_complete() -> None:
    for lemma, forms in policy_module.IRREGULAR_VERBS.items():
        assert len(forms) == 4, f"{lemma} has {len(forms)} forms, expected 4"
        assert all(form and form.isalpha() for form in forms), f"{lemma} has an empty form"


# ── Nouns ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "lemma,plural",
    [
        ("part", "parts"), ("box", "boxes"), ("church", "churches"),
        ("duty", "duties"), ("day", "days"), ("half", "halves"),
        ("analysis", "analyses"), ("criterion", "criteria"), ("child", "children"),
        ("series", "series"), ("information", "information"),
    ],
)
def test_noun_plurals(lemma: str, plural: str) -> None:
    assert forms_for(lemma, "noun")["plural"] == plural


# ── Phrasal verbs ──────────────────────────────────────────────────────────


def test_a_phrasal_verb_inflects_its_head_only() -> None:
    """"Find out" becomes "finds out", never "find outs"."""
    produced = forms_for("find out", "verb")
    assert produced == {
        "base": "find out",
        "third_person": "finds out",
        "past": "found out",
        "past_participle": "found out",
        "gerund": "finding out",
    }


def test_a_multi_word_adverb_has_one_form() -> None:
    """Nothing to inflect, so nothing to get wrong."""
    assert forms_for("from now on", "adverb") == {"base": "from now on"}


def test_only_a_verb_may_be_phrasal() -> None:
    with pytest.raises(MorphologyError, match="only a verb may be phrasal"):
        forms_for("rate of pay", "noun")


# ── Pairing ────────────────────────────────────────────────────────────────


def test_pairs_line_up_form_by_form() -> None:
    assert inflected_pairs("utilise", "use", "verb") == (
        ("utilise", "use"), ("utilises", "uses"),
        ("utilised", "used"), ("utilising", "using"),
    )


def test_an_ambiguous_source_form_is_dropped_rather_than_guessed() -> None:
    """The heart of the safety argument, arriving from the opposite direction.

    A regular verb writes its past and its participle the same way. When the
    target distinguishes them, "accomplished" would be "did" after a subject and
    "done" after "was" — and the engine cannot tell which. So it produces
    neither, and the rule simply does not match that form.
    """
    pairs = dict(inflected_pairs("accomplish", "do", "verb"))

    assert "accomplished" not in pairs, "an ambiguous form must not be guessed at"
    assert pairs == {"accomplish": "do", "accomplishes": "does", "accomplishing": "doing"}


def test_an_unambiguous_irregular_source_keeps_both_forms() -> None:
    """When the source distinguishes them too, both pairs are safe."""
    pairs = dict(inflected_pairs("undertake", "do", "verb"))
    assert pairs["undertook"] == "did"
    assert pairs["undertaken"] == "done"


def test_a_target_that_collapses_forms_is_still_fine() -> None:
    """"Made" is both past and participle, so nothing is ambiguous."""
    pairs = dict(inflected_pairs("manufacture", "make", "verb"))
    assert pairs["manufactured"] == "made"


def test_pairs_never_repeat_a_source_surface() -> None:
    """Two matches at one place would make a rule conflict with itself."""
    for source, target in (("cease", "stop"), ("spread", "spread"), ("cut", "cut")):
        pairs = inflected_pairs(source, target, "verb")
        surfaces = [surface for surface, _ in pairs]
        assert len(surfaces) == len(set(surfaces))


def test_an_uninflectable_lemma_is_refused() -> None:
    for bad in ("", "   ", "5mg", "e-mail@example.com"):
        with pytest.raises(MorphologyError):
            forms_for(bad, "verb")


def test_an_unknown_part_of_speech_is_refused() -> None:
    with pytest.raises(MorphologyError, match="unsupported part of speech"):
        forms_for("utilise", "gerundive")


# ── Casing ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "surface,expected",
    [("utilise", "use"), ("Utilise", "Use"), ("UTILISE", "USE")],
    ids=["lower", "sentence", "upper"],
)
def test_casing_is_reproduced(surface: str, expected: str) -> None:
    assert match_casing(surface, "use") == expected


def test_a_title_cased_phrase_keeps_title_case() -> None:
    assert match_casing("Find Out", "work out") == "Work Out"


@pytest.mark.parametrize("surface", ["uTiLiSe", "utiLISE", "UtilisE"])
def test_unreproducible_casing_fails_closed(surface: str) -> None:
    """Inventing a pattern would mean writing a word in a casing nobody chose."""
    assert match_casing(surface, "use") is None
    assert shape_of(surface) is None


def test_every_declared_shape_can_be_applied() -> None:
    for shape in CASE_SHAPES:
        assert apply_shape("find out", shape)


def test_an_unknown_shape_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown case shape"):
        apply_shape("use", "shouting")


# ── Identity ───────────────────────────────────────────────────────────────


def test_the_morphology_has_its_expected_identity() -> None:
    assert MORPHOLOGY_VERSION == "2026.1"
    assert policy_hash() == MORPHOLOGY_HASH, (
        "The morphology hash changed.\n"
        "  If you changed the tables or rules deliberately, update MORPHOLOGY_HASH\n"
        "  here and say so in the commit message — it is what the ruleset identity\n"
        "  depends on.\n"
        "  If you did not, something platform-dependent has reached the canonical\n"
        "  form, which is a bug in the hashing rather than in this test."
    )


def test_hashing_is_stable_within_a_process() -> None:
    assert policy_hash() == policy_hash()


@pytest.mark.parametrize(
    "attribute,mutate",
    [
        ("IRREGULAR_VERBS", lambda v: {**v, "sing": ("sings", "sang", "sung", "singing")}),
        ("IRREGULAR_NOUNS", lambda v: {**v, "goose": "geese"}),
        ("DOUBLING_VERBS", lambda v: frozenset(v | {"jog"})),
        ("UNCHANGING_NOUNS", lambda v: frozenset(v | {"sheep"})),
        ("CASE_SHAPES", lambda v: v + ("shouting",)),
        ("MORPHOLOGY_VERSION", lambda v: "9999.1"),
        ("PHRASAL_HEAD_INFLECTION", lambda v: not v),
    ],
)
def test_changing_the_policy_changes_its_hash(monkeypatch, attribute: str, mutate) -> None:
    """Anything that alters what the engine can produce must alter the identity."""
    before = policy_hash()
    monkeypatch.setattr(policy_module, attribute, mutate(getattr(policy_module, attribute)))
    assert policy_hash() != before, f"changing {attribute} did not move the morphology hash"


def test_changing_an_inflection_rule_changes_the_hash(monkeypatch) -> None:
    altered = tuple(
        (name, condition, "+z") if name == "default" else (name, condition, transformation)
        for name, condition, transformation in policy_module.PAST_RULES
    )
    before = policy_hash()
    monkeypatch.setattr(policy_module, "PAST_RULES", altered)
    assert policy_hash() != before


def test_the_policy_document_is_plain_data() -> None:
    import json

    document = policy_document()
    assert json.loads(json.dumps(document)) == document


def test_canonicalisation_agrees_with_the_other_layers() -> None:
    """Three leaves each carry their own copy; none may drift from the others."""
    from plainspeak.integrity import canonical_json as integrity_canonical
    from plainspeak.rules import canonical_json as rules_canonical

    for value in ({"b": 1, "a": 2}, {"x": ["z", "y"]}, {"u": "café — 21 °C"}):
        assert canonical_json(value) == rules_canonical(value) == integrity_canonical(value)


def test_every_part_of_speech_declares_its_forms() -> None:
    for pos, classes in FORM_CLASSES.items():
        assert classes, f"{pos} declares no form classes"
        assert len(set(classes)) == len(classes), f"{pos} repeats a form class"


def test_no_stemming_api_is_exposed() -> None:
    """Morphology runs forwards only. A reverse lookup would be the old bug."""
    import plainspeak.morphology as module

    for name in dir(module):
        assert "stem" not in name.lower(), f"{name} looks like a stemmer"
