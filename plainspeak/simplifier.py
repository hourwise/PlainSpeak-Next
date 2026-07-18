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
            # Check if we have a simpler alternative
            suggestion = ""
            if word_lower in GLOSSARY:
                simpler, explanation = GLOSSARY[word_lower]
                suggestion = f'Consider using "{simpler}" instead. {explanation}'
            elif word_lower in SIMPLE_WORD_MAP:
                simpler = SIMPLE_WORD_MAP[word_lower]
                suggestion = f'Consider using "{simpler}" instead of "{word_lower}".'

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
    """Attempt to convert a nominalization back to its verb form."""
    word = word.lower()
    # Common transformations
    if word.endswith("ization"):
        return word[:-6] + "e"  # organization -> organize
    if word.endswith("isation"):
        return word[:-6] + "e"  # organisation -> organise
    if word.endswith("tion"):
        base = word[:-4]
        if base.endswith("a"):
            return base[:-1] + "e"  # creation -> create
        if base.endswith("i"):
            return base[:-1] + "y"  # justification -> justify?
        return base + "e"  # completion -> complete (approx)
    if word.endswith("sion"):
        base = word[:-4]
        if base.endswith("mis"):
            return base[:-3] + "mit"  # submission -> submit
        if base.endswith("ci"):
            return base[:-2] + "de"  # decision -> decide
        return base + "e"
    if word.endswith("ment"):
        return word[:-4]  # development -> develop
    if word.endswith("ance"):
        base = word[:-4]
        if base.endswith("r"):
            return base  # performance -> perform
        return base + "e"  # guidance -> guide? (not perfect)
    if word.endswith("ence"):
        base = word[:-4]
        return base + "e"  # existence -> exist (approx)
    if word.endswith("ness"):
        return word[:-4]  # happiness -> happy (adjective, not verb)
    if word.endswith("ity"):
        base = word[:-3]
        return base + "e"  # creativity -> creative (adjective, not verb)
    return None


def find_jargon(sentence: str, sentence_index: int) -> list[Barrier]:
    """
    Find jargon terms and bureaucratic language with plain-language alternatives.
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
            barriers.append(Barrier(
                barrier_type="jargon",
                sentence_index=sentence_index,
                sentence_text=sentence,
                start_char=idx,
                end_char=idx + len(phrase),
                matched_text=phrase,
                suggestion=f'Consider using "{simpler}" instead. {explanation}',
                explanation=f'"{phrase}" is bureaucratic or formal language. Using plain alternatives makes text more accessible.',
                severity="warning" if len(phrase.split()) >= 3 else "info",
            ))

    # Then check single words
    for word in words:
        word_lower = word.lower()
        if word_lower in GLOSSARY:
            simpler, explanation = GLOSSARY[word_lower]
            barriers.append(Barrier(
                barrier_type="jargon",
                sentence_index=sentence_index,
                sentence_text=sentence,
                matched_text=word,
                suggestion=f'Consider using "{simpler}" instead. {explanation}',
                explanation=f'"{word}" can often be replaced with a simpler word.',
                severity="info",
            ))
        elif word_lower in SIMPLE_WORD_MAP:
            simpler = SIMPLE_WORD_MAP[word_lower]
            barriers.append(Barrier(
                barrier_type="jargon",
                sentence_index=sentence_index,
                sentence_text=sentence,
                matched_text=word,
                suggestion=f'Consider using "{simpler}" instead of "{word}".',
                explanation=f'A simpler alternative exists for "{word}".',
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
