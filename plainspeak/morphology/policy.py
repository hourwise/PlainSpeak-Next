"""What forms of a word PlainSpeak knows how to make, and how.

Morphology exists here for one reason: to stop the engine producing words that
do not exist. The inherited simplifier derived forms by stripping suffixes and
suggested the verb "clare" for the noun "clarity". Nothing in this module
guesses. Regular inflection follows a small set of stated rules; everything the
rules would get wrong is in an explicit table somebody read.

Like the ruleset and the integrity policy, this is **versioned product
behaviour**. Its identity covers the irregular tables, the inflection rules, the
casing policy, the supported form classes and every exception, so a change to
what the engine can say moves the hash.

### On `inflect`

The build plan proposed adopting `inflect`. It was evaluated and not adopted,
for reasons worth recording rather than relitigating:

- **It does not do the job.** `inflect` is excellent at noun plurals, singulars
  and `a`/`an`. It has no verb tense or aspect API at all — `plural_verb`
  concerns number agreement, not conjugation. The dominant need here is verb
  inflection (`utilise` → `utilises`/`utilised`/`utilising`), which it cannot
  express.
- **It would couple a safety identity to a third party.** The morphology hash is
  pinned and asserted cross-platform. Deriving forms from an external package
  means the identity moves whenever that package changes its heuristics, for
  reasons unrelated to anything this project decided.
- **The remainder is small and reviewable.** The noun pluralisation this project
  actually needs is a bounded list, not the long tail `inflect` handles well.

Its licence (MIT) and Python support would both have been fine. The decision is
about fit, not compatibility. If a later phase needs broad noun morphology over
open vocabulary, `inflect` is the right place to look.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

#: Bumped when what the engine can produce changes in a way a reader would
#: notice. The hash below moves on any change at all.
MORPHOLOGY_VERSION = "2026.1"

#: Bumped only if the canonical rendering changes shape.
CANONICAL_FORM_VERSION = 1


# ── Form classes ───────────────────────────────────────────────────────────

#: The inflections this release can generate. Deliberately short: these are the
#: forms the inherited glossary actually needs, and nothing else has been
#: tested. Comparatives and superlatives are absent because no shipped rule
#: needs them and an untested form class is a liability.
VERB_FORMS: tuple[str, ...] = ("base", "third_person", "past", "past_participle", "gerund")
NOUN_FORMS: tuple[str, ...] = ("singular", "plural")
ADJECTIVE_FORMS: tuple[str, ...] = ("base",)

FORM_CLASSES: dict[str, tuple[str, ...]] = {
    "verb": VERB_FORMS,
    "noun": NOUN_FORMS,
    "adjective": ADJECTIVE_FORMS,
    "adverb": ("base",),
    "other": ("base",),
}

PARTS_OF_SPEECH: tuple[str, ...] = tuple(sorted(FORM_CLASSES))


# ── Irregular verbs ────────────────────────────────────────────────────────

#: Verbs whose forms the regular rules would get wrong, as reviewed tables.
#: `(third_person, past, past_participle, gerund)`.
#:
#: Every entry here was written out and read, not derived. That is the whole
#: point: a table somebody checked is worth more than a rule that is right most
#: of the time, because the failures of such a rule are exactly the words that
#: read as nonsense.
IRREGULAR_VERBS: dict[str, tuple[str, str, str, str]] = {
    "be": ("is", "was", "been", "being"),
    "begin": ("begins", "began", "begun", "beginning"),
    "break": ("breaks", "broke", "broken", "breaking"),
    "bring": ("brings", "brought", "brought", "bringing"),
    "build": ("builds", "built", "built", "building"),
    "buy": ("buys", "bought", "bought", "buying"),
    "choose": ("chooses", "chose", "chosen", "choosing"),
    "come": ("comes", "came", "come", "coming"),
    "cut": ("cuts", "cut", "cut", "cutting"),
    "deal": ("deals", "dealt", "dealt", "dealing"),
    "do": ("does", "did", "done", "doing"),
    "draw": ("draws", "drew", "drawn", "drawing"),
    "feed": ("feeds", "fed", "fed", "feeding"),
    "find": ("finds", "found", "found", "finding"),
    "get": ("gets", "got", "got", "getting"),
    "give": ("gives", "gave", "given", "giving"),
    "go": ("goes", "went", "gone", "going"),
    "have": ("has", "had", "had", "having"),
    "hold": ("holds", "held", "held", "holding"),
    "keep": ("keeps", "kept", "kept", "keeping"),
    "know": ("knows", "knew", "known", "knowing"),
    "lead": ("leads", "led", "led", "leading"),
    "leave": ("leaves", "left", "left", "leaving"),
    "let": ("lets", "let", "let", "letting"),
    "lose": ("loses", "lost", "lost", "losing"),
    "make": ("makes", "made", "made", "making"),
    "mean": ("means", "meant", "meant", "meaning"),
    "meet": ("meets", "met", "met", "meeting"),
    "pay": ("pays", "paid", "paid", "paying"),
    "put": ("puts", "put", "put", "putting"),
    "read": ("reads", "read", "read", "reading"),
    "run": ("runs", "ran", "run", "running"),
    "say": ("says", "said", "said", "saying"),
    "see": ("sees", "saw", "seen", "seeing"),
    "seek": ("seeks", "sought", "sought", "seeking"),
    "sell": ("sells", "sold", "sold", "selling"),
    "send": ("sends", "sent", "sent", "sending"),
    "set": ("sets", "set", "set", "setting"),
    "show": ("shows", "showed", "shown", "showing"),
    "speak": ("speaks", "spoke", "spoken", "speaking"),
    "speed": ("speeds", "sped", "sped", "speeding"),
    "spend": ("spends", "spent", "spent", "spending"),
    "spread": ("spreads", "spread", "spread", "spreading"),
    "take": ("takes", "took", "taken", "taking"),
    "teach": ("teaches", "taught", "taught", "teaching"),
    "tell": ("tells", "told", "told", "telling"),
    "think": ("thinks", "thought", "thought", "thinking"),
    "undertake": ("undertakes", "undertook", "undertaken", "undertaking"),
    "understand": ("understands", "understood", "understood", "understanding"),
    "write": ("writes", "wrote", "written", "writing"),
}

#: Verbs whose final consonant doubles before `-ed` and `-ing`. Stated
#: explicitly rather than derived from a stress rule: English doubles in
#: "commit" and not in "benefit", and the difference is stress, which is not
#: recoverable from spelling.
DOUBLING_VERBS: frozenset = frozenset({
    "admit", "allot", "ban", "commit", "compel", "concur", "control", "equip",
    "excel", "expel", "fit", "forget", "occur", "omit", "permit", "plan",
    "prefer", "refer", "regret", "remit", "step", "stop", "submit", "transfer",
    "transmit",
    # British doubling. This project writes British English throughout, so
    # "cancel" gives "cancelled" rather than "canceled".
    "cancel", "label", "model", "signal", "travel",
})


# ── Irregular nouns ────────────────────────────────────────────────────────

#: Nouns whose plural the regular rules would get wrong.
IRREGULAR_NOUNS: dict[str, str] = {
    "analysis": "analyses",
    "appendix": "appendices",
    "basis": "bases",
    "child": "children",
    "criterion": "criteria",
    "crisis": "crises",
    "datum": "data",
    "diagnosis": "diagnoses",
    "foot": "feet",
    "hypothesis": "hypotheses",
    "index": "indices",
    "man": "men",
    "matrix": "matrices",
    "medium": "media",
    "memorandum": "memoranda",
    "person": "people",
    "phenomenon": "phenomena",
    "prognosis": "prognoses",
    "thesis": "theses",
    "tooth": "teeth",
    "woman": "women",
}

#: Nouns with no distinct plural form.
UNCHANGING_NOUNS: frozenset = frozenset({
    "advice", "aircraft", "equipment", "evidence", "guidance", "information",
    "series", "software", "species", "staff",
})


# ── Inflection rules ───────────────────────────────────────────────────────
#
# Applied in order; the first whose condition holds wins. Written as data so
# that they are part of the hashed identity and so a reviewer can read the
# whole policy without reading the code that applies it.

#: `(name, condition, transformation)` — see `forms._apply`.
THIRD_PERSON_RULES: tuple[tuple[str, str, str], ...] = (
    ("sibilant", "endswith:s,x,z,ch,sh,ss", "+es"),
    ("consonant-y", "consonant-y", "y->ies"),
    ("vowel-o", "endswith:o", "+es"),
    ("default", "always", "+s"),
)

PAST_RULES: tuple[tuple[str, str, str], ...] = (
    ("silent-e", "endswith:e", "+d"),
    ("consonant-y", "consonant-y", "y->ied"),
    ("doubling", "in:DOUBLING_VERBS", "double+ed"),
    ("default", "always", "+ed"),
)

GERUND_RULES: tuple[tuple[str, str, str], ...] = (
    ("keep-ee", "endswith:ee,ye,oe", "+ing"),
    ("drop-e", "endswith:e", "-e+ing"),
    ("doubling", "in:DOUBLING_VERBS", "double+ing"),
    ("default", "always", "+ing"),
)

PLURAL_RULES: tuple[tuple[str, str, str], ...] = (
    ("unchanging", "in:UNCHANGING_NOUNS", "same"),
    ("sibilant", "endswith:s,x,z,ch,sh,ss", "+es"),
    ("consonant-y", "consonant-y", "y->ies"),
    ("f-to-ves", "endswith:f", "f->ves"),
    ("fe-to-ves", "endswith:fe", "fe->ves"),
    ("default", "always", "+s"),
)


# ── Casing ─────────────────────────────────────────────────────────────────

#: Whether a multi-word verb inflects its head and keeps the rest.
#:
#: "Find out" is a phrasal verb: it becomes "finds out", "found out", "finding
#: out". Plain-language guidance recommends exactly this shape of replacement —
#: a Latinate verb for a phrasal one — so the glossary is full of them, and
#: refusing to inflect them would strand a whole class of good substitutions at
#: base form. The particle never changes, which is what makes it mechanical.
#:
#: Declared here because it changes what the engine can produce, and everything
#: that does belongs in the hashed identity.
PHRASAL_HEAD_INFLECTION = True

#: Capitalisation shapes the engine can reproduce. Anything else fails closed:
#: "uTiLiSe" has no mechanical equivalent, and inventing one would mean writing
#: a word the author did not.
CASE_SHAPES: tuple[str, ...] = ("lower", "sentence", "title", "upper")


# ── Identity ───────────────────────────────────────────────────────────────


def canonical_json(value: Any) -> str:
    """Canonical rendering, byte-identical on every platform.

    Duplicated from the rules and integrity layers rather than imported, for
    the same reason: this package is a leaf and must not depend on another.
    A test asserts all three renderings agree.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def policy_document() -> dict[str, Any]:
    """The whole morphology policy as canonical data."""
    return {
        "canonical_form": CANONICAL_FORM_VERSION,
        "morphology_version": MORPHOLOGY_VERSION,
        "form_classes": {key: list(FORM_CLASSES[key]) for key in sorted(FORM_CLASSES)},
        "case_shapes": list(CASE_SHAPES),
        "phrasal_head_inflection": PHRASAL_HEAD_INFLECTION,
        # Rule order is behaviour, so these lists are not sorted.
        "rules": {
            "third_person": [list(rule) for rule in THIRD_PERSON_RULES],
            "past": [list(rule) for rule in PAST_RULES],
            "gerund": [list(rule) for rule in GERUND_RULES],
            "plural": [list(rule) for rule in PLURAL_RULES],
        },
        "irregular_verbs": {
            lemma: list(IRREGULAR_VERBS[lemma]) for lemma in sorted(IRREGULAR_VERBS)
        },
        "irregular_nouns": {noun: IRREGULAR_NOUNS[noun] for noun in sorted(IRREGULAR_NOUNS)},
        "doubling_verbs": sorted(DOUBLING_VERBS),
        "unchanging_nouns": sorted(UNCHANGING_NOUNS),
    }


def policy_hash() -> str:
    """SHA-256 of the canonical morphology policy."""
    return hashlib.sha256(canonical_json(policy_document()).encode("utf-8")).hexdigest()
