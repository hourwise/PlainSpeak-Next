"""Generating the inflected forms of a word.

Every form comes from either an explicit reviewed table or a stated rule. There
is no fallback that guesses, and there is no stemming: this module never takes a
surface form and tries to work out what it came from. It goes one way only, from
a lemma somebody wrote down to the forms that lemma has.

That direction is the entire safety argument. The inherited simplifier worked
backwards — strip a suffix, hope the result is a word — and suggested the verb
"clare" for "clarity". Going forwards from a declared lemma, the worst case is a
form nobody uses; it cannot be a word that does not exist, because the rule that
made it was read by somebody first.
"""
from __future__ import annotations

from typing import Optional

from .policy import (
    DOUBLING_VERBS,
    FORM_CLASSES,
    GERUND_RULES,
    IRREGULAR_NOUNS,
    IRREGULAR_VERBS,
    PAST_RULES,
    PLURAL_RULES,
    THIRD_PERSON_RULES,
    UNCHANGING_NOUNS,
)

VOWELS = "aeiou"


def _split_phrasal(lemma: str) -> tuple[str, str]:
    """Split a phrasal verb into its head and everything after it."""
    parts = lemma.strip().split()
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def _is_inflectable(word: str) -> bool:
    return bool(word) and word.replace("-", "").replace("'", "").isalpha()


class MorphologyError(ValueError):
    """A lemma could not be inflected. Always fatal; never a silent fallback."""


def forms_for(lemma: str, part_of_speech: str) -> dict[str, str]:
    """Every form of `lemma`, keyed by form class.

    Raises `MorphologyError` for an unsupported part of speech or a lemma the
    rules cannot handle, rather than returning something approximate.
    """
    if part_of_speech not in FORM_CLASSES:
        raise MorphologyError(
            f"unsupported part of speech {part_of_speech!r}; known: {sorted(FORM_CLASSES)}"
        )

    head, particle = _split_phrasal(lemma)
    if not _is_inflectable(head):
        raise MorphologyError(f"not a lemma this engine can inflect: {lemma!r}")

    if FORM_CLASSES[part_of_speech] == ("base",):
        # Nothing to inflect, so nothing to get wrong. An adverb like "from now
        # on" is several words and one form; taking it verbatim is the whole of
        # its morphology.
        if not all(_is_inflectable(word) for word in lemma.split()):
            raise MorphologyError(f"not a lemma this engine can handle: {lemma!r}")
        return {"base": lemma.strip().lower()}

    if particle and part_of_speech != "verb":
        raise MorphologyError(
            f"only a verb may be phrasal; {part_of_speech} {lemma!r} has more than one word"
        )
    if particle and not all(_is_inflectable(word) for word in particle.split()):
        raise MorphologyError(f"phrasal particle is not plain words: {lemma!r}")

    if particle:
        # The head carries the inflection and the particle is copied through:
        # "find out" becomes "finds out", never "find outs".
        return {
            name: f"{form} {particle}"
            for name, form in forms_for(head, part_of_speech).items()
        }

    lower = head.lower()
    if part_of_speech == "verb":
        return _verb_forms(lower)
    if part_of_speech == "noun":
        return _noun_forms(lower)
    return {"base": lower}


def _verb_forms(lemma: str) -> dict[str, str]:
    if lemma in IRREGULAR_VERBS:
        third, past, participle, gerund = IRREGULAR_VERBS[lemma]
        return {
            "base": lemma,
            "third_person": third,
            "past": past,
            "past_participle": participle,
            "gerund": gerund,
        }

    past = _apply(lemma, PAST_RULES)
    return {
        "base": lemma,
        "third_person": _apply(lemma, THIRD_PERSON_RULES),
        "past": past,
        # Regular verbs share their past and past participle. Any verb that does
        # not is in IRREGULAR_VERBS, which is checked first.
        "past_participle": past,
        "gerund": _apply(lemma, GERUND_RULES),
    }


def _noun_forms(lemma: str) -> dict[str, str]:
    if lemma in IRREGULAR_NOUNS:
        return {"singular": lemma, "plural": IRREGULAR_NOUNS[lemma]}
    return {"singular": lemma, "plural": _apply(lemma, PLURAL_RULES)}


# ── Applying the declared rules ────────────────────────────────────────────


def _apply(word: str, rules: tuple[tuple[str, str, str], ...]) -> str:
    """Run the first rule whose condition holds.

    The rules are declared as data in `policy` so that they form part of the
    hashed identity and a reviewer can read the whole policy without reading
    this function.
    """
    for name, condition, transformation in rules:
        if _matches(word, condition):
            return _transform(word, transformation)
    raise MorphologyError(f"no inflection rule applied to {word!r}")


def _matches(word: str, condition: str) -> bool:
    if condition == "always":
        return True
    if condition == "consonant-y":
        return len(word) >= 2 and word.endswith("y") and word[-2] not in VOWELS
    if condition.startswith("endswith:"):
        return any(word.endswith(suffix) for suffix in condition[len("endswith:"):].split(","))
    if condition == "in:DOUBLING_VERBS":
        return word in DOUBLING_VERBS
    if condition == "in:UNCHANGING_NOUNS":
        return word in UNCHANGING_NOUNS
    raise MorphologyError(f"unknown inflection condition {condition!r}")


def _transform(word: str, transformation: str) -> str:
    if transformation == "same":
        return word
    if transformation.startswith("+"):
        return word + transformation[1:]
    if transformation.startswith("-e+"):
        return word[:-1] + transformation[len("-e+"):]
    if transformation.startswith("double+"):
        return word + word[-1] + transformation[len("double+"):]
    if "->" in transformation:
        source, target = transformation.split("->", 1)
        if not word.endswith(source):
            raise MorphologyError(f"cannot apply {transformation!r} to {word!r}")
        return word[: -len(source)] + target
    raise MorphologyError(f"unknown inflection transformation {transformation!r}")


# ── Pairing a source lemma with a target lemma ─────────────────────────────


def inflected_pairs(
    source_lemma: str,
    target_lemma: str,
    part_of_speech: str,
    classes: Optional[tuple[str, ...]] = None,
) -> tuple[tuple[str, str], ...]:
    """Surface-form pairs for a lexical substitution across its inflections.

    `("utilise", "use", "verb")` gives `utilise → use`, `utilises → uses`,
    `utilised → used`, `utilising → using`.

    Both sides are generated from the same form classes, so a rule can never
    pair a past tense with a gerund. Duplicate surfaces — an irregular verb
    whose past and participle coincide — are collapsed, since matching the same
    text twice would make a rule conflict with itself.
    """
    source = forms_for(source_lemma, part_of_speech)
    target = forms_for(target_lemma, part_of_speech)

    wanted = classes if classes is not None else FORM_CLASSES[part_of_speech]
    unknown = [name for name in wanted if name not in source]
    if unknown:
        raise MorphologyError(
            f"{part_of_speech} {source_lemma!r} has no form(s) {unknown}; "
            f"available: {sorted(source)}"
        )

    # A regular English verb writes its past and its past participle the same
    # way. When the *target* distinguishes them, one source surface would have
    # two possible replacements and no way to choose between them: "accomplished"
    # is "did" after a subject and "done" after "was". Producing either would be
    # wrong half the time, so the form is dropped and the rule simply does not
    # match it.
    #
    # This is the same class of defect as the inherited "clarity" -> "clare",
    # arriving from the opposite direction, and the same answer applies: when
    # the engine cannot tell, it says nothing.
    by_surface: dict[str, set[str]] = {}
    for name in wanted:
        by_surface.setdefault(source[name], set()).add(target[name])

    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in wanted:
        surface, replacement = source[name], target[name]
        if surface in seen:
            continue
        seen.add(surface)
        if len(by_surface[surface]) > 1:
            continue
        pairs.append((surface, replacement))

    if not pairs:
        raise MorphologyError(
            f"no unambiguous form pairs for {source_lemma!r} -> {target_lemma!r}"
        )
    return tuple(pairs)
