"""What the style layer measures, and where it draws its lines.

Robotic prose is rarely one bad word. It is repetition, cadence and habit across
a whole document: eight paragraphs that open the same way, one transition used
six times, sentences that are all seventeen words long. A glossary cannot see
any of that, because none of it is visible in a single sentence.

This module declares what gets measured and at what point a measurement becomes
a finding. Like the ruleset, the integrity policy and morphology, it is
**versioned product behaviour** with a pinned hash — moving a threshold from 5%
to 8% changes what users are told, so it changes the identity.

### Two things this layer is not

**It is not an authorship detector.** PlainSpeak does not know who wrote a
document and will not guess. There is no "83% likely AI-generated" anywhere in
this package, and a test asserts there never will be. The output is always of
the form "8 of 12 paragraphs begin with 'The system'" — an observation a reader
can check for themselves and disagree with.

**It does not produce a score.** A single number would compress a dozen
independent observations into something that looks authoritative and hides all
of its own evidence, and the first thing anyone would do with it is treat it as
an AI detector. The output is a profile of bands, each traceable to a
measurement and a threshold.

### Where the thresholds come from

Not intuition. `tests/style/corpus/` holds project-authored samples spanning
conversational, technical, government, academic, list-heavy and deliberately
robotic prose. Every threshold here was set by measuring that corpus and
choosing a line that the natural samples sit below and the repetitive ones sit
above, with the margins recorded in `STYLE_CALIBRATION.md`. Nothing is trained;
the corpus is regression data.

### Vocabularies are diagnostic, not prohibitions

The word lists below are *not* banned words. "Robust" is a perfectly good word.
Using it eleven times in two thousand words is an observation worth surfacing,
and that is the only claim being made.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

#: Bumped when what a reader is told changes. The hash moves on any change.
STYLE_POLICY_VERSION = "2026.1"

#: Bumped only if the canonical rendering changes shape.
CANONICAL_FORM_VERSION = 1


# ── Diagnostic identities ──────────────────────────────────────────────────
#
# Deliberately a different namespace from transformation rules. `PS.LEXICAL.001`
# proposes an edit; `PS.STYLE.REPEATED_OPENER` proposes nothing at all, and a
# reader should never have to work out which kind of thing they are looking at.

SENTENCE_UNIFORMITY = "PS.STYLE.SENTENCE_UNIFORMITY"
PARAGRAPH_UNIFORMITY = "PS.STYLE.PARAGRAPH_UNIFORMITY"
REPEATED_SENTENCE_OPENER = "PS.STYLE.REPEATED_SENTENCE_OPENER"
REPEATED_PARAGRAPH_OPENER = "PS.STYLE.REPEATED_PARAGRAPH_OPENER"
TRANSITION_DENSITY = "PS.STYLE.TRANSITION_DENSITY"
REPEATED_TRANSITION = "PS.STYLE.REPEATED_TRANSITION"
CANNED_FRAMING = "PS.STYLE.CANNED_FRAMING"
VOCABULARY_OVERUSE = "PS.STYLE.VOCABULARY_OVERUSE"
RHETORICAL_REPETITION = "PS.STYLE.RHETORICAL_REPETITION"
TRIADIC_REPETITION = "PS.STYLE.TRIADIC_REPETITION"
REPEATED_PHRASE = "PS.STYLE.REPEATED_PHRASE"
LEXICAL_OVERLAP = "PS.STYLE.LEXICAL_OVERLAP"
LIST_DOMINANCE = "PS.STYLE.LIST_DOMINANCE"

DIAGNOSTIC_IDS: tuple[str, ...] = (
    CANNED_FRAMING,
    LEXICAL_OVERLAP,
    LIST_DOMINANCE,
    PARAGRAPH_UNIFORMITY,
    REPEATED_PARAGRAPH_OPENER,
    REPEATED_PHRASE,
    REPEATED_SENTENCE_OPENER,
    REPEATED_TRANSITION,
    RHETORICAL_REPETITION,
    SENTENCE_UNIFORMITY,
    TRANSITION_DENSITY,
    TRIADIC_REPETITION,
    VOCABULARY_OVERUSE,
)

#: Severity bands. Each corresponds to an explicit threshold below — nothing is
#: weighted, blended or scored.
SEVERITIES: tuple[str, ...] = ("info", "notice", "strong")


# ── Minimum sample sizes ───────────────────────────────────────────────────
#
# A three-sentence paragraph where two sentences start the same way is not
# evidence of anything. Every document-level diagnostic declares the smallest
# sample it will speak about, and says nothing below it — silence is the correct
# output when there is not enough text to have an opinion.

MINIMUM_SAMPLES: dict[str, int] = {
    SENTENCE_UNIFORMITY: 8,
    # Eight, not five. At five paragraphs the coefficient of variation is
    # noise: in the calibration corpus an academic sample scored 0.109 while
    # three deliberately repetitive samples scored higher. The measurement
    # only separates once there are enough paragraphs to average over.
    PARAGRAPH_UNIFORMITY: 8,
    REPEATED_SENTENCE_OPENER: 6,
    REPEATED_PARAGRAPH_OPENER: 4,
    TRANSITION_DENSITY: 8,
    REPEATED_TRANSITION: 6,
    CANNED_FRAMING: 4,
    VOCABULARY_OVERUSE: 200,   # words, not sentences
    RHETORICAL_REPETITION: 6,
    TRIADIC_REPETITION: 6,
    REPEATED_PHRASE: 8,
    LEXICAL_OVERLAP: 4,
    LIST_DOMINANCE: 6,
}


# ── Thresholds ─────────────────────────────────────────────────────────────
#
# `(notice, strong)` pairs. A measurement below the first value produces no
# finding at all.

THRESHOLDS: dict[str, tuple[float, float]] = {
    # Coefficient of variation of sentence length. *Low* variation is the
    # signal here, so these are floors rather than ceilings: prose reads as
    # mechanical when every sentence is the same length.
    # Calibration corpus: natural samples run 0.476-0.651, the deliberately
    # uniform sample 0.244. The line sits in the gap, nearer the uniform side so
    # that a merely tidy document is not accused of being mechanical.
    SENTENCE_UNIFORMITY: (0.34, 0.26),
    # Natural samples of eight or more paragraphs run 0.611; the deliberately
    # uniform one 0.059. A wide gap, and the line is drawn well inside it.
    PARAGRAPH_UNIFORMITY: (0.20, 0.12),
    # Share of sentences or paragraphs beginning with the same opener.
    REPEATED_SENTENCE_OPENER: (0.35, 0.50),
    REPEATED_PARAGRAPH_OPENER: (0.40, 0.60),
    # Transitions per sentence.
    TRANSITION_DENSITY: (0.20, 0.35),
    # Share of all transitions that are the same word.
    REPEATED_TRANSITION: (0.50, 0.70),
    # Canned framing phrases per paragraph.
    CANNED_FRAMING: (0.25, 0.50),
    # Occurrences per 1,000 words of any one flagged vocabulary item.
    VOCABULARY_OVERUSE: (3.0, 6.0),
    # Repeated rhetorical constructions per 10 sentences.
    RHETORICAL_REPETITION: (0.30, 0.60),
    TRIADIC_REPETITION: (0.30, 0.60),
    # Occurrences of one repeated phrase per 100 words.
    REPEATED_PHRASE: (0.60, 1.20),
    # Jaccard overlap between two paragraphs' content tokens.
    LEXICAL_OVERLAP: (0.60, 0.75),
    # Share of prose blocks that are list items.
    LIST_DOMINANCE: (0.50, 0.70),
}

#: Diagnostics where a *lower* measurement is the signal. Uniformity is the
#: whole family: prose that never varies is the thing being reported.
INVERTED: frozenset = frozenset({SENTENCE_UNIFORMITY, PARAGRAPH_UNIFORMITY})


# ── Vocabularies ───────────────────────────────────────────────────────────

#: Discourse transitions. Diagnostic vocabulary, not a banned list: a document
#: using eight different transitions is doing something quite different from one
#: using "furthermore" eight times, and both are measured separately.
TRANSITIONS: tuple[str, ...] = (
    "additionally", "accordingly", "afterwards", "alternatively", "besides",
    "consequently", "conversely", "finally", "first", "firstly", "furthermore",
    "hence", "however", "importantly", "indeed", "instead", "likewise",
    "meanwhile", "moreover", "nevertheless", "nonetheless", "notably",
    "overall", "regardless", "second", "secondly", "similarly", "specifically",
    "subsequently", "then", "thereafter", "therefore", "third", "thirdly",
    "thus", "ultimately",
)

#: Multi-word transitions, matched as phrases.
TRANSITION_PHRASES: tuple[str, ...] = (
    "in addition", "in conclusion", "in contrast", "in particular",
    "in summary", "on the other hand", "as a result", "for example",
    "for instance", "that said", "to summarise", "to summarize",
)

#: Framing that announces a statement without adding to it. Some of these are
#: also Phase 4 transformation rules; style measures how often they occur across
#: a document rather than detecting each one, which is a different question.
FRAMING_PHRASES: tuple[str, ...] = (
    "it is important to note",
    "it is worth noting",
    "it should be noted",
    "it is important to understand",
    "it is crucial to understand",
    "it is essential to recognise",
    "it is essential to recognize",
    "it is worth mentioning",
    "it is interesting to note",
    "needless to say",
    "it goes without saying",
)

#: Vocabulary worth counting when it clusters. Emphatically *not* a claim that
#: any of these words indicates anything about who wrote the text — only that
#: using one of them eleven times in two thousand words is an observation.
FLAGGED_VOCABULARY: tuple[str, ...] = (
    "comprehensive", "crucial", "delve", "dynamic", "empower", "enhance",
    "facilitate", "holistic", "innovative", "landscape", "leverage",
    "multifaceted", "nuanced", "paradigm", "pivotal", "robust", "seamless",
    "streamline", "synergy", "transformative", "underscore", "vibrant", "vital",
)

#: Bounded rhetorical constructions, as `(name, pattern)`. Ordinary English
#: every one of them — the diagnostic is about repetition, never existence.
RHETORICAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("not-only-but-also", r"\bnot only\b[^.!?]{1,80}?\bbut also\b"),
    ("not-x-but-y", r"\bit(?:'s| is) not\b[^.!?]{1,60}?\bbut\b"),
    ("whether-or", r"\bwhether\b[^.!?]{1,60}?\bor\b"),
    ("from-x-to-y", r"\bfrom\b[^.!?]{1,50}?\bto\b[^.!?]{1,50}?\b(?:and|,)"),
    ("both-and", r"\bboth\b[^.!?]{1,60}?\band\b"),
    ("more-than-just", r"\bmore than (?:just|simply)\b"),
    ("isnt-just", r"\b(?:isn't|is not) (?:just|merely|simply)\b"),
)

#: Surface templates for sentence openings. Lexical, not syntactic — the name
#: says "surface" because that is all they are. A trained tagger would do this
#: better and is not something this project is willing to depend on.
SURFACE_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("this-verb", r"^this\s+(?:is|was|are|were|means|shows|demonstrates|highlights"
                  r"|underscores|reflects|suggests|indicates|ensures|allows|enables)\b"),
    ("there-is", r"^there\s+(?:is|are|was|were)\b"),
    ("it-is-adjective", r"^it\s+is\s+\w+\b"),
    ("the-noun-verb", r"^the\s+\w+\s+(?:is|are|was|were|provides|enables|ensures"
                      r"|supports|allows|offers|delivers)\b"),
    ("in-todays", r"^in\s+today's\b"),
)

#: Words excluded from content-word statistics. Project-authored and short on
#: purpose: a long list from elsewhere would need a licence review, and the
#: statistics here do not need one.
STOP_WORDS: frozenset = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did",
    "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "may", "me", "might", "more", "most", "must", "my", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "out", "over", "own", "same", "shall", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "theirs", "them", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your",
    "yours",
})

#: Contractions counted for the contraction rate.
CONTRACTIONS: tuple[str, ...] = (
    "aren't", "can't", "couldn't", "didn't", "doesn't", "don't", "hadn't",
    "hasn't", "haven't", "he's", "here's", "i'd", "i'll", "i'm", "i've",
    "isn't", "it's", "let's", "shouldn't", "that's", "there's", "they'd",
    "they'll", "they're", "they've", "wasn't", "we'd", "we'll", "we're",
    "we've", "weren't", "what's", "won't", "wouldn't", "you'd", "you'll",
    "you're", "you've",
)

#: Pronoun families, for a future style profile to care about.
PRONOUNS: dict[str, tuple[str, ...]] = {
    "first_singular": ("i", "me", "my", "mine", "myself"),
    "first_plural": ("we", "us", "our", "ours", "ourselves"),
    "second": ("you", "your", "yours", "yourself", "yourselves"),
    "third": ("he", "him", "his", "she", "her", "hers", "it", "its",
              "they", "them", "their", "theirs"),
}

#: Punctuation counted per 1,000 words.
PUNCTUATION: dict[str, str] = {
    "em_dash": "—",
    "en_dash": "–",
    "semicolon": ";",
    "colon": ":",
    "question_mark": "?",
    "exclamation_mark": "!",
    "open_parenthesis": "(",
}


# ── Bounds ─────────────────────────────────────────────────────────────────
#
# N-gram counting and paragraph comparison both explode if left unbounded, and
# the bounds change what is reported, so they are policy rather than an
# implementation detail.

#: Phrase lengths counted for repeated-phrase analysis.
NGRAM_SIZES: tuple[int, ...] = (3, 4, 5)
#: A phrase must occur at least this often to be reported.
NGRAM_MINIMUM_OCCURRENCES = 3
#: How many repeated phrases are retained. Keeps memory bounded on a long book
#: without changing what the top findings are.
NGRAM_MAX_RETAINED = 50

#: Opener lengths analysed, in tokens.
OPENER_SIZES: tuple[int, ...] = (1, 2, 3)

#: Paragraphs shorter than this are not compared for lexical overlap: two
#: six-word paragraphs sharing four words is arithmetic, not repetition.
OVERLAP_MINIMUM_TOKENS = 20
#: Two paragraphs are only compared when they already share this many content
#: tokens, found through an inverted index. Without a filter the comparison is
#: all-pairs and a long document becomes quadratic.
OVERLAP_CANDIDATE_TOKENS = 5
#: An upper bound on comparisons, so a pathological document cannot run away.
OVERLAP_MAX_COMPARISONS = 20000


# ── Identity ───────────────────────────────────────────────────────────────


def canonical_json(value: Any) -> str:
    """Canonical rendering, byte-identical on every platform.

    Duplicated from the rules, integrity and morphology layers rather than
    imported — `style` should not depend on any of them to render JSON. A test
    asserts all four agree.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def policy_document() -> dict[str, Any]:
    """The whole style policy as canonical data."""
    return {
        "canonical_form": CANONICAL_FORM_VERSION,
        "style_policy_version": STYLE_POLICY_VERSION,
        "diagnostics": list(DIAGNOSTIC_IDS),
        "severities": list(SEVERITIES),
        "minimum_samples": {key: MINIMUM_SAMPLES[key] for key in sorted(MINIMUM_SAMPLES)},
        "thresholds": {key: list(THRESHOLDS[key]) for key in sorted(THRESHOLDS)},
        "inverted": sorted(INVERTED),
        "vocabularies": {
            "transitions": sorted(TRANSITIONS),
            "transition_phrases": sorted(TRANSITION_PHRASES),
            "framing_phrases": sorted(FRAMING_PHRASES),
            "flagged_vocabulary": sorted(FLAGGED_VOCABULARY),
            "contractions": sorted(CONTRACTIONS),
            "stop_words": sorted(STOP_WORDS),
            "pronouns": {key: sorted(PRONOUNS[key]) for key in sorted(PRONOUNS)},
            "punctuation": {key: PUNCTUATION[key] for key in sorted(PUNCTUATION)},
        },
        # Pattern order does not affect results — findings are sorted — but the
        # patterns themselves plainly do.
        "patterns": {
            "rhetorical": [list(item) for item in RHETORICAL_PATTERNS],
            "surface_templates": [list(item) for item in SURFACE_TEMPLATES],
        },
        "bounds": {
            "ngram_sizes": list(NGRAM_SIZES),
            "ngram_minimum_occurrences": NGRAM_MINIMUM_OCCURRENCES,
            "ngram_max_retained": NGRAM_MAX_RETAINED,
            "opener_sizes": list(OPENER_SIZES),
            "overlap_minimum_tokens": OVERLAP_MINIMUM_TOKENS,
            "overlap_candidate_tokens": OVERLAP_CANDIDATE_TOKENS,
            "overlap_max_comparisons": OVERLAP_MAX_COMPARISONS,
        },
    }


def policy_hash() -> str:
    """SHA-256 of the canonical style policy."""
    return hashlib.sha256(canonical_json(policy_document()).encode("utf-8")).hexdigest()


def severity_for(diagnostic: str, value: float) -> str:
    """Which band a measurement falls in, or an empty string for none.

    Every band is an explicit comparison against a declared threshold. There is
    no weighting and no blending: a reader who disagrees with a finding can see
    exactly which number produced it.
    """
    notice, strong = THRESHOLDS[diagnostic]
    if diagnostic in INVERTED:
        if value <= strong:
            return "strong"
        if value <= notice:
            return "notice"
        return ""
    if value >= strong:
        return "strong"
    if value >= notice:
        return "notice"
    return ""
