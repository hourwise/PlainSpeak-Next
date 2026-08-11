"""
Text simplification engine.

Identifies readability barriers in text and suggests improvements.
All analysis is rule-based and deterministic — suggestions are
advisory and should be reviewed by a human before applying.

Barriers identified:
- Passive voice constructions
- Overly long sentences
- Complex words (3+ syllables, or 7+ characters)
- Nominalizations (verbs turned into nouns)
- Jargon terms with plain-language alternatives
- Hidden verbs (noun phrases that could be verbs)
- Redundant word pairs
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .glossary import GLOSSARY, SIMPLE_WORD_MAP
from .analyzer import split_sentences, split_words, count_syllables


# ── Protected terms of art ─────────────────────────────────────────────────
# Domain terms whose meaning must not be altered by word substitution.
# These may still be FLAGGED as difficult/jargon, with a recommendation to
# define or explain on first use, but the engine must NEVER propose a
# replacement word that changes the term's legal/clinical/financial meaning.
PROTECTED_TERMS: dict[str, str] = {
    # Legal terms of art
    "shall": "legal",
    "may": "legal",
    "consideration": "legal",
    "party": "legal",
    "execute": "legal",
    "remedy": "legal",
    "damages": "legal",
    "liable": "legal",
    "indemnify": "legal",
    "warrant": "legal",
    "negligence": "legal",
    "covenant": "legal",
    "waive": "legal",
    "construe": "legal",
    "prejudice": "legal",
    "instrument": "legal",
    "serve": "legal",
    "notice": "legal",
    "provision": "legal",
    "estate": "legal",
    "deemed": "legal",
    "material": "legal",
    "notwithstanding": "legal",
    "heretofore": "legal",
    "thereto": "legal",
    "hereunder": "legal",
    "thereunder": "legal",
    "forthwith": "legal",
    "thereby": "legal",
    "hereby": "legal",
    "herein": "legal",
    "thereof": "legal",
    # Medical/clinical terms of art
    "acute": "medical",
    "chronic": "medical",
    "negative": "medical",
    "positive": "medical",
    "stable": "medical",
    "expired": "medical",
    "gross": "medical",
    "occult": "medical",
    "frank": "medical",
    "guarded": "medical",
    "labile": "medical",
    "refractory": "medical",
    "adverse": "medical",
    "titrate": "medical",
    "dose": "medical",
    "indicated": "medical",
    "contraindicated": "medical",
    "administer": "medical",
    "medication": "medical",
    "dosage": "medical",
    "significant": "medical",
    # Financial terms of art
    "principal": "financial",
    "securities": "financial",
    "maturity": "financial",
    "interest": "financial",
    "accrue": "financial",
    "default": "financial",
}


def is_protected_term(word: str) -> bool:
    """Check if a word is a protected domain term of art."""
    return word.lower() in PROTECTED_TERMS


def get_protected_domain(word: str) -> str:
    """Get the domain tag for a protected term."""
    return PROTECTED_TERMS.get(word.lower(), "")


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

    Args:
        word: The word to look up.

    Returns:
        (simpler_alternative, explanation) if found, None otherwise.
    """
    word_lower = word.lower()

    # Exact match in GLOSSARY
    if word_lower in GLOSSARY:
        return GLOSSARY[word_lower]

    # Exact match in SIMPLE_WORD_MAP
    if word_lower in SIMPLE_WORD_MAP:
        return (SIMPLE_WORD_MAP[word_lower], "A simpler word is available.")

    # Try stemmed match
    stemmed = stem_word(word_lower)
    if stemmed != word_lower:
        if stemmed in GLOSSARY:
            return GLOSSARY[stemmed]
        if stemmed in SIMPLE_WORD_MAP:
            return (SIMPLE_WORD_MAP[stemmed], "A simpler word is available.")

    return None


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class Barrier:
    """A single readability barrier found in text."""
    barrier_type: str  # e.g., "passive_voice", "long_sentence", "complex_word"
    sentence_index: int  # 0-based index into the sentences list
    sentence_text: str  # The full sentence containing the barrier
    start_char: int = 0  # Character offset within sentence
    end_char: int = 0  # Character offset within sentence
    matched_text: str = ""  # The specific text that triggered the barrier
    suggestion: str = ""  # Optional plain-language alternative
    explanation: str = ""  # Why this is a barrier
    severity: str = "info"  # "info", "warning", "critical"


@dataclass
class SimplificationResult:
    """Complete simplification analysis of a text."""
    original_text: str
    sentences: list[str] = field(default_factory=list)
    barriers: list[Barrier] = field(default_factory=list)
    total_barriers: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    summary: str = ""


# ── Pattern definitions ────────────────────────────────────────────────────

# Passive voice patterns: form of "be" + past participle
# This is a simplified heuristic; true passive detection needs parsing.
PASSIVE_PATTERNS: list[re.Pattern] = [
    # is/are/was/were + past participle (ending in -ed, -en, -t, etc.)
    re.compile(
        r"\b(?:is|are|was|were|be|been|being|am)\s+"
        r"(\w+(?:ed|en|t|ied|ded|sed|ned|red|ged|zed|ped|ked|ched|shed)\b)",
        re.IGNORECASE,
    ),
    # has been / have been / had been + past participle
    re.compile(
        r"\b(?:has|have|had)\s+been\s+(\w+(?:ed|en|t)\b)",
        re.IGNORECASE,
    ),
    # will be / shall be + past participle
    re.compile(
        r"\b(?:will|shall)\s+be\s+(\w+(?:ed|en|t)\b)",
        re.IGNORECASE,
    ),
    # can be / must be / should be / may be + past participle
    re.compile(
        r"\b(?:can|must|should|may|might|could|would)\s+be\s+(\w+(?:ed|en|t)\b)",
        re.IGNORECASE,
    ),
]

# Words that look like past participles but are often adjectives
# in common use — reduces false positives for "passive" detection.
ADJECTIVAL_PARTICIPLES: set[str] = {
    "interested", "excited", "bored", "tired", "worried", "surprised",
    "pleased", "annoyed", "confused", "satisfied", "disappointed",
    "frightened", "shocked", "amazed", "delighted", "depressed",
    "embarrassed", "fascinated", "terrified", "thrilled",
    "experienced", "qualified", "skilled", "talented", "gifted",
    "complicated", "sophisticated", "dedicated", "committed",
    "limited", "united", "related", "involved", "concerned",
    "prepared", "determined", "established", "recognized",
    "respected", "renowned", "distinguished", "celebrated",
    "advanced", "refined", "cultured", "educated",
    "marked", "noted", "pointed", "jagged", "rugged",
    "learned", "blessed", "cursed", "dogged", "jagged",
    "beloved", "supposed", "marked",
}

# Nominalization suffixes: verbs turned into nouns
NOMINALIZATION_PATTERN = re.compile(
    r"\b(\w+(?:tion|sion|ment|ance|ence|ity|ness|al|age|ure|sis|cy|dom)\b)",
    re.IGNORECASE,
)

# Words that are typically nominalizations we should flag
NOMINALIZATION_EXCEPTIONS: set[str] = {
    "nation", "station", "vision", "television", "mention", "question",
    "section", "attention", "direction", "position", "condition",
    "information", "situation", "population", "education", "president",
    "student", "accident", "moment", "government", "department",
    "development", "agreement", "management", "environment",
    "city", "pity", "duty", "army", "navy", "body", "lady",
    "pretty", "busy", "noisy", "dirty", "thirsty",
    "mission", "passion", "fashion", "cushion",
    "equation", "relation", "foundation",
    "occasion", "invasion", "decision", "division",
}

# Hidden verb patterns: "make a [noun]" where [noun] has a verb form
HIDDEN_VERB_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(make|makes|made|making)\s+a\s+(\w+)\b", re.IGNORECASE), "make"),
    (re.compile(r"\b(give|gives|gave|given|giving)\s+a\s+(\w+)\b", re.IGNORECASE), "give"),
    (re.compile(r"\b(conduct|conducts|conducted|conducting)\s+a\s+(\w+)\b", re.IGNORECASE), "conduct"),
    (re.compile(r"\b(perform|performs|performed|performing)\s+a\s+(\w+)\b", re.IGNORECASE), "perform"),
    (re.compile(r"\b(carry|carries|carried|carrying)\s+out\s+a\s+(\w+)\b", re.IGNORECASE), "carry out"),
    (re.compile(r"\b(take|takes|took|taken|taking)\s+a\s+(\w+)\b", re.IGNORECASE), "take"),
    (re.compile(r"\b(hold|holds|held|holding)\s+a\s+(\w+)\b", re.IGNORECASE), "hold"),
    (re.compile(r"\b(provide|provides|provided|providing)\s+a\s+(\w+)\b", re.IGNORECASE), "provide"),
    (re.compile(r"\b(undertake|undertakes|undertook|undertaken|undertaking)\s+a\s+(\w+)\b", re.IGNORECASE), "undertake"),
]

# Redundant pairs: two words that mean almost the same thing
REDUNDANT_PAIRS: list[tuple[str, str, str]] = [
    ("absolutely essential", "essential", "'Essential' already means absolutely necessary."),
    ("actual facts", "facts", "Facts are actual by definition."),
    ("advance planning", "planning", "Planning is done in advance."),
    ("alternative choice", "choice", "A choice is between alternatives."),
    ("basic fundamentals", "fundamentals", "Fundamentals are basic."),
    ("brief summary", "summary", "A summary is brief."),
    ("close proximity", "proximity", "Proximity means closeness."),
    ("collaborate together", "collaborate", "Collaboration is done together."),
    ("combine together", "combine", "Combining brings things together."),
    ("complete monopoly", "monopoly", "A monopoly is complete control."),
    ("consensus of opinion", "consensus", "Consensus is an agreement of opinion."),
    ("cooperate together", "cooperate", "Cooperation is done together."),
    ("each and every", "each", "Use one or the other, not both."),
    ("end result", "result", "Results come at the end."),
    ("exact same", "same", "'Same' is exact."),
    ("final conclusion", "conclusion", "A conclusion is final."),
    ("first and foremost", "first", "Use one word."),
    ("free gift", "gift", "A gift is free by definition."),
    ("future plans", "plans", "Plans are for the future."),
    ("general public", "public", "The public is general."),
    ("honest truth", "truth", "Truth is honest."),
    ("joint collaboration", "collaboration", "Collaboration is joint."),
    ("knowledgeable expert", "expert", "An expert is knowledgeable."),
    ("last and final", "last", "These mean the same."),
    ("mix together", "mix", "Mixing brings things together."),
    ("mutual cooperation", "cooperation", "Cooperation is mutual."),
    ("new beginning", "beginning", "A beginning is new."),
    ("new innovation", "innovation", "Innovation is new."),
    ("overall plan", "plan", "A plan is overall."),
    ("past experience", "experience", "Experience is from the past."),
    ("personal opinion", "opinion", "An opinion is personal."),
    ("plan ahead", "plan", "Planning looks ahead."),
    ("postpone until later", "postpone", "Postponing means until later."),
    ("proposed plan", "plan", "A plan is proposed."),
    ("repeat again", "repeat", "Repeating is doing again."),
    ("reply back", "reply", "Replying is responding back."),
    ("return back", "return", "Returning is going back."),
    ("safe haven", "haven", "A haven is safe."),
    ("same identical", "identical", "Identical means the same."),
    ("still remains", "remains", "Remaining is still being there."),
    ("sudden crisis", "crisis", "A crisis is often sudden."),
    ("surrounded on all sides", "surrounded", "Surrounded means on all sides."),
    ("total destruction", "destruction", "Destruction can be total."),
    ("true facts", "facts", "Facts are true."),
    ("ultimate goal", "goal", "A goal is what you ultimately want."),
    ("unexpected surprise", "surprise", "A surprise is unexpected."),
    ("usual custom", "custom", "A custom is usual."),
    ("very unique", "unique", "Unique means one of a kind — cannot be 'very' unique."),
    ("visible to the eye", "visible", "Visible means can be seen."),
]


# ── Detection functions ────────────────────────────────────────────────────


def find_passive_voice(sentence: str, sentence_index: int) -> list[Barrier]:
    """
    Find passive voice constructions in a sentence.

    Uses regex heuristics. Will produce false positives for:
    - Adjectives that look like past participles (e.g., "I am interested")
    - Some participial phrases used as adjectives
    - Sentences where the agent is genuinely unknown and passive is appropriate

    Will miss:
    - Passives without an explicit "be" auxiliary
    - Reduced relative clauses in passive
    - Get-passives ("got fired")
    """
    barriers = []
    for pattern in PASSIVE_PATTERNS:
        for match in pattern.finditer(sentence):
            participle = match.group(1).lower()
            # Skip common adjectival participles
            if participle in ADJECTIVAL_PARTICIPLES:
                continue
            # Skip if the participle is immediately followed by "by" — that's
            # a clearer case, but we still flag it
            barriers.append(Barrier(
                barrier_type="passive_voice",
                sentence_index=sentence_index,
                sentence_text=sentence,
                start_char=match.start(),
                end_char=match.end(),
                matched_text=match.group(0),
                suggestion="Consider rewriting in active voice. Identify who is doing the action and make them the subject.",
                explanation=(
                    "Passive voice can hide who is responsible for an action, "
                    "making text harder to follow. Active voice is usually clearer "
                    "and more direct."
                ),
                severity="warning",
            ))
    return barriers


def find_long_sentences(sentences: list[str]) -> list[Barrier]:
    """
    Flag sentences that exceed recommended length thresholds.

    Plain language guidelines suggest:
    - Ideal: 15-20 words per sentence
    - Acceptable: up to 25 words
    - Concerning: 25-35 words
    - Problematic: >35 words
    """
    from .analyzer import split_words as sw

    barriers = []
    for i, sentence in enumerate(sentences):
        word_count = len(sw(sentence))
        if word_count > 35:
            barriers.append(Barrier(
                barrier_type="long_sentence",
                sentence_index=i,
                sentence_text=sentence,
                matched_text=sentence[:100] + ("..." if len(sentence) > 100 else ""),
                suggestion=f"This sentence has {word_count} words. Consider splitting it into two or more shorter sentences.",
                explanation=(
                    f"Sentences over 25 words are harder to follow. "
                    f"This one has {word_count} words. "
                    "Try breaking it at natural pause points."
                ),
                severity="critical" if word_count > 40 else "warning",
            ))
        elif word_count > 25:
            barriers.append(Barrier(
                barrier_type="long_sentence",
                sentence_index=i,
                sentence_text=sentence,
                matched_text=sentence[:100] + ("..." if len(sentence) > 100 else ""),
                suggestion=f"Consider shortening this {word_count}-word sentence or splitting it.",
                explanation=(
                    f"This sentence is {word_count} words long. "
                    "Sentences over 25 words begin to strain working memory."
                ),
                severity="info",
            ))
    return barriers


def find_complex_words(sentence: str, sentence_index: int) -> list[Barrier]:
    """
    Find complex words (3+ syllables or 7+ characters) and suggest
    simpler alternatives where available.
    """
    words = split_words(sentence)
    barriers = []

    for word in words:
        word_lower = word.lower()
        syllables = count_syllables(word_lower)

        if syllables >= 3 or len(word) >= 7:
            # Check if we have a simpler alternative (with stemming)
            suggestion = ""
            match = find_glossary_match(word_lower)
            if match:
                simpler, explanation = match
                suggestion = f'Consider using "{simpler}" instead. {explanation}'

            if suggestion or syllables >= 4 or len(word) >= 9:
                severity = "warning" if (syllables >= 4 or len(word) >= 10) else "info"
                barriers.append(Barrier(
                    barrier_type="complex_word",
                    sentence_index=sentence_index,
                    sentence_text=sentence,
                    matched_text=word,
                    suggestion=suggestion or f'"{word}" has {syllables} syllables. Is there a simpler word you could use?',
                    explanation=(
                        f'"{word}" has {syllables} syllables and {len(word)} characters. '
                        "Shorter, more common words are understood by more readers."
                    ),
                    severity=severity,
                ))

    return barriers


def find_nominalizations(sentence: str, sentence_index: int) -> list[Barrier]:
    """
    Find nominalizations — verbs turned into nouns — that could be more
    directly expressed as verbs.
    """
    barriers = []
    for match in NOMINALIZATION_PATTERN.finditer(sentence):
        word = match.group(1)
        word_lower = word.lower()
        if word_lower in NOMINALIZATION_EXCEPTIONS:
            continue
        # Suggest converting to verb form
        verb_form = _nominalization_to_verb(word_lower)
        if verb_form:
            barriers.append(Barrier(
                barrier_type="nominalization",
                sentence_index=sentence_index,
                sentence_text=sentence,
                start_char=match.start(),
                end_char=match.end(),
                matched_text=word,
                suggestion=(
                    f'"{word}" is a nominalization. '
                    f'Consider using the verb "{verb_form}" instead '
                    f'to make the sentence more direct.'
                ),
                explanation=(
                    "Nominalizations (verbs turned into nouns) make writing "
                    "feel heavy and abstract. Using the verb form directly "
                    "usually makes sentences shorter and clearer."
                ),
                severity="info",
            ))
    return barriers


def _nominalization_to_verb(word: str) -> Optional[str]:
    """Attempt to convert a nominalization back to its verb form.
    
    Only returns a verb if the derived form is a validated real English word
    (checked against the CMU Pronouncing Dictionary). Bogus derivations like
    'medication' -> 'medice' are suppressed.
    """
    word = word.lower()
    candidate = None
    
    if word.endswith("ization"):
        candidate = word[:-7] + "ize"
    elif word.endswith("isation"):
        candidate = word[:-7] + "ise"
    elif word.endswith("ation"):
        # implementation -> implement, consideration -> consider
        candidate = word[:-5]
    elif word.endswith("tion"):
        base = word[:-4]
        if base.endswith("a"):
            candidate = base[:-1] + "e"
        elif base.endswith("i"):
            candidate = base[:-1] + "y"
        else:
            candidate = base + "e"
    elif word.endswith("sion"):
        base = word[:-4]
        if base.endswith("mis"):
            candidate = base[:-3] + "mit"
        elif base.endswith("ci"):
            candidate = base[:-2] + "de"
        else:
            candidate = base + "e"
    elif word.endswith("ment"):
        candidate = word[:-4]
    elif word.endswith("ance"):
        base = word[:-4]
        if base.endswith("r"):
            candidate = base
        else:
            candidate = base + "e"
    elif word.endswith("ence"):
        base = word[:-4]
        candidate = base + "e"
    elif word.endswith("ness"):
        candidate = word[:-4]
    elif word.endswith("ity"):
        base = word[:-3]
        candidate = base + "e"
    
    if candidate and _is_real_word(candidate):
        return candidate
    return None


def _is_real_word(word: str) -> bool:
    """Check if a word is a real English word using the CMU dictionary."""
    try:
        from .syllable_data import get_syllable_count
        syllable_dict = get_syllable_count()
        return word.lower() in syllable_dict
    except (ImportError, FileNotFoundError):
        vowels = set('aeiou')
        return len(word) >= 3 and bool(vowels & set(word.lower()))


def find_jargon(sentence: str, sentence_index: int) -> list[Barrier]:
    """
    Find jargon terms and bureaucratic language with plain-language alternatives.
    
    Protected domain terms of art are flagged as potentially difficult but
    are NOT given meaning-changing replacements. Instead, the suggestion
    recommends defining or explaining the term on first use.
    """
    barriers = []
    words = split_words(sentence)
    checked_positions: set[int] = set()

    # Check multi-word phrases first (longest first)
    phrases = sorted(
        [(k, v) for k, v in GLOSSARY.items() if " " in k],
        key=lambda x: len(x[0].split()),
        reverse=True,
    )
    sentence_lower = sentence.lower()
    for phrase, (simpler, explanation) in phrases:
        idx = sentence_lower.find(phrase)
        if idx != -1:
            # Check if any word in the phrase is a protected term
            phrase_words = phrase.lower().split()
            is_protected = any(w in PROTECTED_TERMS for w in phrase_words)
            
            if is_protected:
                suggestion = (
                    f'"{phrase}" is a domain term of art. '
                    f'Consider defining or explaining it on first use rather than replacing it.'
                )
            else:
                suggestion = f'Consider using "{simpler}" instead. {explanation}'
            
            barriers.append(Barrier(
                barrier_type="jargon",
                sentence_index=sentence_index,
                sentence_text=sentence,
                start_char=idx,
                end_char=idx + len(phrase),
                matched_text=phrase,
                suggestion=suggestion,
                explanation=f'"{phrase}" is bureaucratic or formal language. Using plain alternatives makes text more accessible.',
                severity="warning" if len(phrase.split()) >= 3 else "info",
            ))

    # Then check single words
    for word in words:
        word_lower = word.lower()
        match = find_glossary_match(word_lower)
        if match:
            simpler, explanation = match
            # Protected term: flag but don't suggest replacement
            if is_protected_term(word_lower):
                domain = get_protected_domain(word_lower)
                suggestion = (
                    f'"{word}" is a {domain} term of art with specific meaning. '
                    f'Consider defining or explaining it on first use.'
                )
            else:
                suggestion = f'Consider using "{simpler}" instead. {explanation}'
            
            barriers.append(Barrier(
                barrier_type="jargon",
                sentence_index=sentence_index,
                sentence_text=sentence,
                matched_text=word,
                suggestion=suggestion,
                explanation=f'"{word}" can often be replaced with a simpler word.',
                severity="info",
            ))

    return barriers


def find_redundant_pairs(sentence: str, sentence_index: int) -> list[Barrier]:
    """Find redundant word pairs like 'absolutely essential'."""
    barriers = []
    sentence_lower = sentence.lower()
    for redundant, replacement, explanation in REDUNDANT_PAIRS:
        idx = sentence_lower.find(redundant)
        if idx != -1:
            barriers.append(Barrier(
                barrier_type="redundant_pair",
                sentence_index=sentence_index,
                sentence_text=sentence,
                start_char=idx,
                end_char=idx + len(redundant),
                matched_text=redundant,
                suggestion=f'Use just "{replacement}". {explanation}',
                explanation="Redundant word pairs add words without adding meaning.",
                severity="info",
            ))
    return barriers


def find_hidden_verbs(sentence: str, sentence_index: int) -> list[Barrier]:
    """Find hidden verb constructions like 'make a decision' -> 'decide'."""
    barriers = []
    for pattern, verb_type in HIDDEN_VERB_PATTERNS:
        for match in pattern.finditer(sentence):
            noun = match.group(2)
            noun_lower = noun.lower()
            # Check if this noun has a verb form (simple heuristic: remove common suffixes)
            verb_form = _noun_to_verb(noun_lower)
            if verb_form:
                barriers.append(Barrier(
                    barrier_type="hidden_verb",
                    sentence_index=sentence_index,
                    sentence_text=sentence,
                    start_char=match.start(),
                    end_char=match.end(),
                    matched_text=match.group(0),
                    suggestion=(
                        f'Consider using "{verb_form}" instead of "{match.group(0)}". '
                        f'This makes the action more direct.'
                    ),
                    explanation=(
                        "Hidden verbs (noun phrases where a verb would work) "
                        "make sentences longer and less direct."
                    ),
                    severity="info",
                ))
    return barriers


def _noun_to_verb(noun: str) -> Optional[str]:
    """Convert a noun to its verb form if possible."""
    noun = noun.lower()
    if noun.endswith("ment"):
        return noun[:-4]  # arrangement -> arrange, statement -> state
    if noun.endswith("tion"):
        base = noun[:-4]
        if base.endswith("a"):
            return base[:-1] + "e"
        return base
    if noun.endswith("sion"):
        base = noun[:-4]
        if base.endswith("mis"):
            return base[:-3] + "mit"
        return base
    if noun.endswith("ance"):
        return noun[:-4]  # performance -> perform
    if noun.endswith("ence"):
        return noun[:-4]  # reference -> refer
    if noun.endswith("al"):
        return noun[:-2]  # approval -> approve
    if noun.endswith("ure"):
        return noun[:-3]  # failure -> fail
    if noun.endswith("sis"):
        return noun[:-3] + "e"  # analysis -> analyze
    if noun.endswith("sis"):
        return noun[:-3] + "ze"
    # Many nouns are the same as their verb form
    return noun  # "change", "plan", "report", "study", "review", etc.


# ── Main analysis function ─────────────────────────────────────────────────


def _deduplicate_barriers(barriers: list[Barrier]) -> list[Barrier]:
    """
    Remove duplicate barriers produced by overlapping detectors.
    
    Two barriers are considered duplicates if they share the same
    (sentence_index, barrier_type, matched_text). The highest-severity
    instance is kept.
    """
    severity_order = {"critical": 3, "warning": 2, "info": 1}
    seen: dict[tuple, Barrier] = {}
    
    for b in barriers:
        key = (b.sentence_index, b.barrier_type, b.matched_text.lower().strip())
        if key in seen:
            # Keep the higher-severity instance
            existing = seen[key]
            if severity_order.get(b.severity, 0) > severity_order.get(existing.severity, 0):
                seen[key] = b
        else:
            seen[key] = b
    
    return list(seen.values())


def analyze_simplification(text: str) -> SimplificationResult:
    """
    Perform a full simplification analysis of the given text.

    Args:
        text: The text to analyze.

    Returns:
        SimplificationResult with all detected barriers and summary.
    """
    sentences = split_sentences(text)
    all_barriers: list[Barrier] = []

    for i, sentence in enumerate(sentences):
        all_barriers.extend(find_passive_voice(sentence, i))
        all_barriers.extend(find_complex_words(sentence, i))
        all_barriers.extend(find_nominalizations(sentence, i))
        all_barriers.extend(find_jargon(sentence, i))
        all_barriers.extend(find_redundant_pairs(sentence, i))
        all_barriers.extend(find_hidden_verbs(sentence, i))

    # Add long sentence barriers
    all_barriers.extend(find_long_sentences(sentences))

    # ── De-duplicate barriers ──
    # Overlapping detectors can produce the same finding. Keep the
    # highest-severity instance per (sentence_index, barrier_type, matched_text).
    all_barriers = _deduplicate_barriers(all_barriers)

    # Sort by sentence index then severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_barriers.sort(key=lambda b: (b.sentence_index, severity_order.get(b.severity, 3)))

    # Count severities
    critical = sum(1 for b in all_barriers if b.severity == "critical")
    warnings = sum(1 for b in all_barriers if b.severity == "warning")
    infos = sum(1 for b in all_barriers if b.severity == "info")

    # Generate summary
    summary_parts = []
    if critical:
        summary_parts.append(f"{critical} critical issue(s)")
    if warnings:
        summary_parts.append(f"{warnings} warning(s)")
    if infos:
        summary_parts.append(f"{infos} suggestion(s)")
    if not summary_parts:
        summary_parts.append("No significant readability barriers found")

    summary = (
        f"Found {len(all_barriers)} readability issue(s) across "
        f"{len(sentences)} sentence(s): {', '.join(summary_parts)}."
    )

    return SimplificationResult(
        original_text=text,
        sentences=sentences,
        barriers=all_barriers,
        total_barriers=len(all_barriers),
        critical_count=critical,
        warning_count=warnings,
        info_count=infos,
        summary=summary,
    )


def generate_simplified_text(text: str) -> tuple[str, int]:
    """
    Generate a version of the text with plain-language substitutions applied.

    This is a MECHANICAL transformation only — it applies glossary-based
    word replacements. It does NOT restructure sentences, fix passive voice,
    or make any semantic changes. The output MUST be reviewed by a human
    before use, especially for legal, medical, or safety-critical content.

    Now includes basic stemming so inflected forms like "commencement"
    can match the glossary entry for "commence."

    Args:
        text: The text to simplify.

    Returns:
        Tuple of (simplified_text, number_of_replacements_made).
    """
    import re

    result = text
    replacements = 0

    # Sort phrases by length (longest first) to avoid partial matches
    phrases = sorted(
        [(k, v[0]) for k, v in GLOSSARY.items() if " " in k],
        key=lambda x: len(x[0].split()),
        reverse=True,
    )

    # Replace multi-word phrases first
    for phrase, simpler in phrases:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        count = len(pattern.findall(result))
        if count > 0:
            result = pattern.sub(f"**{simpler}**", result)
            replacements += count

    # Handle hyphenated single-token glossary entries (e.g., "pro-rata")
    # These aren't caught by the phrase matcher (no space) or the word
    # matcher (regex only matches [a-zA-Z]+).
    hyphenated_terms = [
        (k, v[0]) for k, v in GLOSSARY.items()
        if " " not in k and "-" in k
    ]
    for term, simpler in hyphenated_terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        count = len(pattern.findall(result))
        if count > 0:
            result = pattern.sub(f"**{simpler}**", result)
            replacements += count

    # Build a combined word-replacement map from GLOSSARY + SIMPLE_WORD_MAP
    # (deduplicating — GLOSSARY takes precedence for richer explanations)
    word_replacements: dict[str, str] = {}
    for word, (simpler, _) in GLOSSARY.items():
        if " " not in word:
            word_replacements[word] = simpler
    for word, simpler in SIMPLE_WORD_MAP.items():
        if word not in word_replacements:
            word_replacements[word] = simpler

    # Extract words from text, excluding those already inside **...** markup
    # Process word replacements segment-by-segment to avoid double-replacement
    segments = re.split(r'(\*\*[^*]+\*\*)', result)
    result_parts: list[str] = []
    replaced_words: set[str] = set()
    
    for seg in segments:
        if seg.startswith('**'):
            # Already-marked segment — keep as-is
            result_parts.append(seg)
            continue
        
        # Non-marked segment — apply word replacements
        working = seg
        seg_words = set(w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', working))
        
        for match_word in seg_words:
            if match_word in replaced_words:
                continue
            
            if match_word in word_replacements:
                simpler = word_replacements[match_word]
            else:
                stemmed = stem_word(match_word)
                if stemmed != match_word and stemmed in word_replacements:
                    simpler = word_replacements[stemmed]
                else:
                    continue
            
            pattern = re.compile(r'\b' + re.escape(match_word) + r'\b', re.IGNORECASE)
            new_working = pattern.sub(f"**{simpler}**", working)
            if new_working != working:
                replacements += 1
                working = new_working
                replaced_words.add(match_word)
        
        result_parts.append(working)
    
    result = ''.join(result_parts)
    return result, replacements


# ── Barrier metadata: confidence and priority ──────────────────────────────

# Confidence levels for each barrier type, based on what the implementation
# can honestly establish from surface-level text analysis.
BARRIER_CONFIDENCE: dict[str, str] = {
    "long_sentence": "high",       # Word count is objective
    "complex_word": "medium",      # Syllable/char heuristics are approximate
    "jargon": "medium",            # Glossary is curated but context-free
    "passive_voice": "medium",     # Regex-based, ~70-80% precision
    "nominalization": "medium",    # Suffix-based, reasonable but not perfect
    "hidden_verb": "uncertain",    # Highly context-dependent
    "redundant_pair": "medium",    # Pattern-based, generally reliable
}

# Priority levels: how much each barrier type affects comprehension
BARRIER_PRIORITY: dict[str, str] = {
    "long_sentence": "high",       # Strongest predictor of reading difficulty
    "passive_voice": "consider",   # Can obscure agency but sometimes appropriate
    "jargon": "high",              # Directly blocks comprehension for many readers
    "complex_word": "consider",    # Individual words less critical than overall
    "nominalization": "consider",  # Contributes to density but not always harmful
    "hidden_verb": "consider",     # Can make text feel bureaucratic
    "redundant_pair": "info",      # Minor efficiency issue, rarely blocks comprehension
}

BARRIER_LABELS: dict[str, str] = {
    "long_sentence": "Long sentence",
    "complex_word": "Complex word",
    "jargon": "Jargon or formal language",
    "passive_voice": "Passive voice",
    "nominalization": "Nominalization",
    "hidden_verb": "Hidden verb",
    "redundant_pair": "Redundant word pair",
}


def get_barrier_confidence(barrier_type: str) -> str:
    """Return the confidence level for a barrier type."""
    return BARRIER_CONFIDENCE.get(barrier_type, "medium")


def get_barrier_priority(barrier_type: str) -> str:
    """Return the priority level for a barrier type."""
    return BARRIER_PRIORITY.get(barrier_type, "consider")


def get_barrier_label(barrier_type: str) -> str:
    """Return a human-readable label for a barrier type."""
    return BARRIER_LABELS.get(barrier_type, barrier_type.replace("_", " ").title())


def group_barriers_by_sentence(barriers: list) -> list[dict]:
    """
    Group barriers by sentence, deduplicating by type within each sentence.
    
    Returns a list of sentence-group dicts sorted by priority (high first).
    """
    from collections import defaultdict
    
    # Group by sentence index
    by_sentence: dict[int, list] = defaultdict(list)
    for b in barriers:
        by_sentence[b.sentence_index].append(b)
    
    result = []
    for sent_idx in sorted(by_sentence.keys()):
        sent_barriers = by_sentence[sent_idx]
        sentence_text = sent_barriers[0].sentence_text if sent_barriers else ""
        word_count = len(sentence_text.split()) if sentence_text else 0
        
        # Deduplicate by type within this sentence
        seen_types: set[str] = set()
        unique_barriers = []
        for b in sent_barriers:
            if b.barrier_type not in seen_types:
                seen_types.add(b.barrier_type)
                unique_barriers.append(b)
        
        # Determine sentence priority (highest among its barriers)
        priorities = {"high": 3, "consider": 2, "info": 1}
        sent_priority = "info"
        sent_priority_score = 0
        issue_types = []
        for b in unique_barriers:
            p = get_barrier_priority(b.barrier_type)
            ps = priorities.get(p, 0)
            if ps > sent_priority_score:
                sent_priority = p
                sent_priority_score = ps
            issue_types.append({
                "type": b.barrier_type,
                "label": get_barrier_label(b.barrier_type),
                "confidence": get_barrier_confidence(b.barrier_type),
                "priority": p,
                "count": sum(1 for x in sent_barriers if x.barrier_type == b.barrier_type),
                "matched_text": b.matched_text,
                "suggestion": b.suggestion,
                "explanation": b.explanation,
            })
        
        # Sort issues by priority
        issue_types.sort(key=lambda x: priorities.get(x["priority"], 0), reverse=True)
        
        result.append({
            "sentence_index": sent_idx,
            "sentence_text": sentence_text[:300] + ("..." if len(sentence_text) > 300 else ""),
            "word_count": word_count,
            "priority": sent_priority,
            "total_issues": len(sent_barriers),
            "unique_issue_types": len(unique_barriers),
            "issues": issue_types,
        })
    
    # Sort sentences by priority
    result.sort(key=lambda x: priorities.get(x["priority"], 0), reverse=True)
    
    return result


def build_top_improvements(grouped_barriers: list[dict], max_items: int = 7) -> list[dict]:
    """
    Build a prioritized "Top improvements" summary from grouped barriers.
    
    Returns up to max_items actions, each with a clear recommendation.
    """
    improvements = []
    seen = set()
    
    for group in grouped_barriers:
        for issue in group["issues"]:
            key = (group["sentence_index"], issue["type"])
            if key in seen:
                continue
            seen.add(key)
            
            if len(improvements) >= max_items:
                break
            
            # Build a specific, actionable recommendation
            rec = _build_recommendation(group, issue)
            if rec:
                improvements.append(rec)
        
        if len(improvements) >= max_items:
            break
    
    return improvements


def _build_recommendation(group: dict, issue: dict) -> dict | None:
    """Build a single actionable recommendation."""
    sent_idx = group["sentence_index"]
    priority = issue["priority"]
    btype = issue["type"]
    
    if btype == "long_sentence":
        return {
            "priority": priority,
            "location": f"Sentence {sent_idx + 1}",
            "issue": f"This sentence is {group['word_count']} words long",
            "action": "Break into 2-3 shorter sentences. Aim for 15-25 words per sentence.",
            "impact": "Shorter sentences are the single most effective way to improve readability.",
        }
    elif btype == "passive_voice":
        return {
            "priority": priority,
            "location": f"Sentence {sent_idx + 1}",
            "issue": "Uses passive voice",
            "action": "Rewrite in active voice: identify who is doing what.",
            "impact": "Active voice is more direct and easier to follow.",
        }
    elif btype == "jargon":
        return {
            "priority": priority,
            "location": f"Sentence {sent_idx + 1}",
            "issue": f"Contains jargon or formal language: '{issue['matched_text']}'",
            "action": f"Consider replacing with: {issue['suggestion']}" if issue.get("suggestion") else "Replace with a plain-language alternative.",
            "impact": "Jargon is the most common barrier for non-specialist readers.",
        }
    elif btype == "complex_word":
        return {
            "priority": priority,
            "location": f"Sentence {sent_idx + 1}",
            "issue": f"Contains complex words (e.g. '{issue['matched_text']}')",
            "action": "Replace complex words with shorter, more common alternatives where possible.",
            "impact": "Familiar words reduce cognitive load for all readers.",
        }
    elif btype == "nominalization":
        return {
            "priority": priority,
            "location": f"Sentence {sent_idx + 1}",
            "issue": "Uses nominalizations (verbs turned into nouns)",
            "action": "Rewrite using active verbs instead of abstract nouns.",
            "impact": "Active verbs make writing more direct and easier to process.",
        }
    
    return None
