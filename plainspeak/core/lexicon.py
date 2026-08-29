"""Looking a word up in the bundled vocabulary.

This is the single gate through which every glossary substitution passes,
including the protected-term check. Detectors must not read `GLOSSARY`
directly to decide on a replacement, or the protection is trivially bypassed.
"""

from typing import Optional

from ..integrity.protected import is_protected_term
from .glossary import GLOSSARY, SIMPLE_WORD_MAP


# ── Basic stemming ─────────────────────────────────────────────────────────

# Common English suffixes to strip for glossary matching
# CRITICAL: Must be ordered longest-to-shortest to prevent shorter suffixes
# from matching before longer ones (e.g., "ied" before "ed", "ies" before "s").
SUFFIXES_TO_STRIP = [
    "alization", "alisation",  # normalization -> normalize
    "izations", "isations",
    "ization", "isation",  # organization -> organize
    "fulness", "fulnesses",
    "abilities",
    "ability",  # readability -> readable -> read
    "alities",
    "ality",  # functionality -> functional
    "iveness",
    "nesses",
    "ational",  # organizational -> organize (approx)
    "ations",  # implementations -> implement
    "ments",  # agreements -> agreement
    "ment",  # agreement -> agree
    "tions",  # implementations -> implementa (fallback)
    "sions",
    "ation",  # implementation -> implement
    "tion",  # implementation -> implementa (fallback)
    "sion",
    "ances",  # performances -> perform
    "ences",
    "ance",  # performance -> perform
    "ence",
    "ables",
    "able",  # manageable -> manage
    "ibles",
    "ible",
    "ings",  # workings -> work
    "ingly",
    "edly",
    "ied",   # carried -> carry (MUST come before 'ed' and 'ing')
    "ies",   # carries -> carry (MUST come before 's' and 'ly')
    "ing",   # working -> work
    "ed",    # worked -> work (MUST come after 'ied')
    "ers",   # writers -> write
    "ors",
    "er",    # writer -> write (MUST come after 'ers')
    "or",
    "est",   # biggest -> big
    "ly",    # quickly -> quick (MUST come after 'ingly', 'edly')
    "ify",
    "ise",   # organise -> organ
    "ize",   # organize -> organ
    "al",    # functional -> function
    "s",     # cats -> cat (keep VERY LAST)
]


# Words that should not be stemmed (stemming would create non-words or wrong base forms)
STEM_EXCEPTIONS: set[str] = {
    "is", "was", "has", "had", "does", "goes", "says", "said",
    "us", "yes", "this", "thus", "plus", "minus", "versus",
    "its", "his", "hers", "ours", "yours", "theirs",
    "always", "perhaps", "sometimes", "nowadays",
    "analysis", "basis", "crisis", "thesis", "emphasis",
    "series", "species",
    "news", "lens", "atlas", "canvas", "surplus",
    "process", "progress", "success", "access", "excess",
    "across", "address", "assess", "discuss", "express",
    "miss", "kiss", "boss", "loss", "toss", "cross",
    "class", "glass", "grass", "mass", "pass",
    "press", "dress", "stress",
    "less", "unless", "nevertheless", "nonetheless",
    "business", "witness", "fairness", "darkness",
    "happiness", "sadness",
    # Words whose suffixes look strippable but are part of the root:
    # -ance/-ence that is part of the base word
    "enhance", "advance", "finance", "balance", "distance", "instance",
    "substance", "resistance", "assistance", "insurance", "performance",
    "maintenance", "significance", "experience", "science", "conscience",
    "audience", "convenience", "obedience",
    # -al that is part of the base word  
    "several", "moral", "legal", "royal", "loyal", "rural",
    # -ize/-ise that is part of a short base
    "size", "rise", "wise",
    # Short words that get mangled
    "phase", "phrase", "cause", "because", "please", "release",
    "disease", "increase", "decrease", "purpose", "suppose",
    "oppose", "expose", "impose", "compose", "propose",
    "refuse", "confuse", "accuse", "excuse",
    "office", "notice", "practice", "service", "justice",
    "surface", "replace", "displace",
    # -ate words that aren't suffix-derived
    "debate", "relate", "create", "estate", "update", "donate",
}


def stem_word(word: str) -> str:
    """
    Apply basic suffix stripping to reduce a word to its base form.

    This is a SIMPLISTIC stemmer — it does not handle irregular forms,
    vowel changes, or morphology rules. It is designed solely to improve
    glossary matching for the simplification feature.

    Args:
        word: A lowercase word to stem.

    Returns:
        The stemmed form.
    """
    word = word.lower().strip()
    if not word or len(word) <= 3:
        return word
    if word in STEM_EXCEPTIONS:
        return word

    for suffix in SUFFIXES_TO_STRIP:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[:-len(suffix)]
            # Handle doubled consonants from -ing/-ed (running -> run)
            if suffix in ("ing", "ed", "er", "est") and len(stem) >= 3:
                if stem[-1] == stem[-2] and stem[-1] not in "aeiouy":
                    stem = stem[:-1]
            # Handle -ies -> -y (carries -> carry)
            if suffix in ("ies", "ied"):
                stem += "y"
            # Handle silent-e restoration for -ed and -ing:
            # demonstrate -> demonstrated (e dropped), stripping -ed -> demonstrat
            # enhance -> enhanced (e dropped), stripping -ed -> enhanc
            # Try adding 'e' back; only accept if it produces a known glossary word.
            if suffix in ("ed", "ing") and len(stem) >= 3:
                e_stem = stem + "e"
                if e_stem in GLOSSARY or e_stem in SIMPLE_WORD_MAP:
                    return e_stem
            return stem

    return word


def find_glossary_match(word: str) -> Optional[tuple[str, str]]:
    """
    Find a glossary entry for a word, trying exact match first,
    then stemmed match.

    Protected domain terms of art (legal, medical, financial) will
    NEVER receive a meaning-changing replacement from this function.
    Detectors should flag them as difficult but suggest definition
    or explanation rather than substitution.

    Args:
        word: The word to look up.

    Returns:
        (simpler_alternative, explanation) if found and safe, None otherwise.
    """
    word_lower = word.lower()

    # Protected terms of art: never propose a replacement word
    if is_protected_term(word_lower):
        return None

    # Exact match in GLOSSARY
    if word_lower in GLOSSARY:
        return GLOSSARY[word_lower]

    # Exact match in SIMPLE_WORD_MAP
    if word_lower in SIMPLE_WORD_MAP:
        return (SIMPLE_WORD_MAP[word_lower], "A simpler word is available.")

    # Try stemmed match
    stemmed = stem_word(word_lower)
    if stemmed != word_lower:
        # Check stemmed form is not a protected term
        if is_protected_term(stemmed):
            return None
        if stemmed in GLOSSARY:
            return GLOSSARY[stemmed]
        if stemmed in SIMPLE_WORD_MAP:
            return (SIMPLE_WORD_MAP[stemmed], "A simpler word is available.")

    return None
