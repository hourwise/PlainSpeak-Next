"""
Readability analysis engine.

Computes established readability metrics and identifies text features
that affect comprehension. All computations are deterministic and based
on surface-level text features — no semantic understanding is implied.

Metrics implemented:
- Flesch Reading Ease (FRE)
- Flesch-Kincaid Grade Level (FKGL)
- Gunning Fog Index (GFI)
- SMOG Index
- Automated Readability Index (ARI)
- Coleman-Liau Index (CLI)
"""

import re
import math
from dataclasses import dataclass, field
from typing import Optional


# ── Text segmentation ──────────────────────────────────────────────────────

# Abbreviations that should not trigger sentence boundaries
ABBREVIATIONS: set[str] = {
    "mr", "mrs", "ms", "dr", "prof", "rev", "hon", "st", "sr", "jr",
    "dept", "univ", "assn", "bros", "inc", "ltd", "co", "corp",
    "etc", "vs", "viz", "al", "approx", "appt", "apt", "ave",
    "blvd", "bldg", "capt", "col", "comdr", "gen", "gov", "lt",
    "maj", "mgr", "ph.d", "phd", "md", "rn", "esq",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec", "a.m", "p.m", "am", "pm",
    "u.s", "u.k", "e.g", "i.e", "a.d", "b.c", "c.e", "b.c.e",
    "no", "nos", "vol", "vols", "pp", "p", "ch", "ed", "eds",
    "fig", "figs", "eq", "eqs", "ref", "refs",
    "dept", "est", "temp",
}


def count_syllables(word: str) -> int:
    """
    Estimate the number of syllables in an English word.

    Uses a pattern-based heuristic. Accuracy is approximately 85-95%
    for common English words. Known to fail on:
    - Words with irregular vowel patterns (e.g., 'people', 'every')
    - Words where silent 'e' rules don't apply
    - Irregular loanwords
    - Some compound words

    Returns at least 1 for any non-empty alphabetic string.
    """
    word = word.lower().strip()
    if not word or not word.isalpha():
        return 0

    # Special cases for very short words
    if len(word) <= 2:
        return 1

    original = word

    # Check for -le and -les patterns BEFORE removing silent e
    # These form a syllable: table -> ta-ble, little -> lit-tle
    le_syllable = False
    if word.endswith("le") and len(word) > 2 and word[-3] not in "aeiouy":
        le_syllable = True
    if word.endswith("les") and len(word) > 3 and word[-4] not in "aeiouy":
        le_syllable = True

    # Remove silent e at end
    # But keep it if the word is short or the e is part of a vowel digraph
    if word.endswith("e") and len(word) > 3:
        # Don't remove if preceded by a vowel (e.g., 'see', 'bee', 'free')
        if word[-2] not in "aeiouy":
            word = word[:-1]

    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    # Add syllable for -le pattern
    if le_syllable:
        count += 1

    # ed-endings: 'wanted', 'needed' keep the syllable, others lose it
    if original.endswith("ed") and len(original) > 3:
        if original[-3] in "dt":
            pass  # 'wanted', 'needed' — ed IS a syllable
        else:
            count = max(1, count - 1)

    return max(1, count)


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using regex heuristics.

    Handles common abbreviations but will fail on:
    - Abbreviations not in the ABBREVIATIONS set
    - Decimal numbers at end of sentence: "...worth 3.5. Next..."
    - Some dialogue and quotation patterns
    - Lists with complex punctuation
    - Titles with periods (Mr., Mrs., Dr. are handled)

    Returns a list of sentence strings with whitespace stripped.
    """
    if not text:
        return []

    # Replace common abbreviations to protect their periods
    protected = text
    for abbr in sorted(ABBREVIATIONS, key=len, reverse=True):
        pattern = re.compile(
            r"\b" + re.escape(abbr) + r"\.",
            re.IGNORECASE,
        )
        placeholder = f"__ABBR_{abbr.replace('.', '_')}__"
        protected = pattern.sub(placeholder, protected)

    # Also protect decimal numbers and URLs
    protected = re.sub(r"(\d)\.(\d)", r"\1__DOT__\2", protected)
    protected = re.sub(r"(\w)\.(\w)\.(\w)", r"\1__DOT__\2__DOT__\3", protected)

    # Split on sentence-ending punctuation followed by whitespace and capital letter
    # or end of string
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected)
    
    # Also split on sentence-ending punctuation at end of string
    result = []
    for s in sentences:
        # Restore protected periods
        s = re.sub(r"__DOT__", ".", s)
        for abbr in ABBREVIATIONS:
            placeholder = f"__ABBR_{abbr.replace('.', '_')}__"
            s = s.replace(placeholder, abbr + ".")
        stripped = s.strip()
        if stripped:
            result.append(stripped)

    # If no splits found, treat the whole text as one sentence
    if not result:
        stripped = text.strip()
        if stripped:
            result = [stripped]

    return result


def split_words(text: str) -> list[str]:
    """Split text into words, keeping only alphabetic sequences."""
    return re.findall(r"[a-zA-Z]+", text.lower())


def count_complex_words(words: list[str], syllable_threshold: int = 3) -> int:
    """
    Count words with syllable_threshold or more syllables.
    Default threshold is 3 (standard for Gunning Fog and Flesch).
    """
    return sum(1 for w in words if count_syllables(w) >= syllable_threshold)


# ── Readability metrics ────────────────────────────────────────────────────


@dataclass
class ReadabilityScores:
    """Container for all computed readability scores."""

    # Input statistics
    total_words: int = 0
    total_sentences: int = 0
    total_syllables: int = 0
    total_complex_words: int = 0  # Words with 3+ syllables
    total_long_words: int = 0  # Words with 7+ characters
    avg_sentence_length: float = 0.0
    avg_word_length: float = 0.0  # In characters
    avg_syllables_per_word: float = 0.0

    # Readability scores
    flesch_reading_ease: Optional[float] = None
    flesch_kincaid_grade: Optional[float] = None
    gunning_fog_index: Optional[float] = None
    smog_index: Optional[float] = None
    automated_readability_index: Optional[float] = None
    coleman_liau_index: Optional[float] = None

    # Consensus
    consensus_grade_level: Optional[float] = None

    # Interpretation
    reading_level_description: str = ""


def analyze(text: str) -> ReadabilityScores:
    """
    Compute all readability metrics for the given text.

    Args:
        text: The text to analyze.

    Returns:
        ReadabilityScores with all computed metrics.

    Raises:
        ValueError: If text is empty or has no parseable content.
    """
    if not text or not text.strip():
        raise ValueError("Cannot analyze empty text")

    # Segment text
    sentences = split_sentences(text)
    words = split_words(text)

    if not words:
        raise ValueError("Text contains no recognizable words")

    total_words = len(words)
    total_sentences = len(sentences)
    total_syllables = sum(count_syllables(w) for w in words)
    total_complex_words = count_complex_words(words, 3)
    total_long_words = sum(1 for w in words if len(w) >= 7)
    
    # Count characters (letters + digits only)
    total_characters = sum(len(w) for w in words)

    # Averages
    avg_sentence_length = total_words / total_sentences if total_sentences > 0 else total_words
    avg_word_length = total_characters / total_words if total_words > 0 else 0
    avg_syllables_per_word = total_syllables / total_words if total_words > 0 else 0

    scores = ReadabilityScores(
        total_words=total_words,
        total_sentences=total_sentences,
        total_syllables=total_syllables,
        total_complex_words=total_complex_words,
        total_long_words=total_long_words,
        avg_sentence_length=avg_sentence_length,
        avg_word_length=avg_word_length,
        avg_syllables_per_word=avg_syllables_per_word,
    )

    # Flesch Reading Ease: 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)
    if total_sentences > 0 and total_words > 0:
        fre = 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
        scores.flesch_reading_ease = max(0, min(100, fre))

    # Flesch-Kincaid Grade Level: 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
    if total_sentences > 0 and total_words > 0:
        fkgl = 0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59
        scores.flesch_kincaid_grade = max(0, fkgl)

    # Gunning Fog Index: 0.4 * [(words/sentences) + 100 * (complex_words/words)]
    if total_sentences > 0 and total_words > 0:
        complex_pct = (total_complex_words / total_words) * 100
        gfi = 0.4 * (avg_sentence_length + complex_pct)
        scores.gunning_fog_index = max(0, gfi)

    # SMOG Index: 1.0430 * sqrt(complex_words * 30/sentences) + 3.1291
    # Use the simplified formula for consistency
    if total_sentences > 0 and total_complex_words > 0:
        smog = 1.0430 * math.sqrt(total_complex_words * (30 / total_sentences)) + 3.1291
        scores.smog_index = max(0, smog)
    elif total_sentences > 0:
        scores.smog_index = 3.1291  # Minimum score

    # Automated Readability Index: 4.71 * (chars/words) + 0.5 * (words/sentences) - 21.43
    if total_sentences > 0 and total_words > 0:
        ari = 4.71 * (total_characters / total_words) + 0.5 * avg_sentence_length - 21.43
        scores.automated_readability_index = max(0, ari)

    # Coleman-Liau Index: 0.0588 * L - 0.296 * S - 15.8
    # L = average letters per 100 words, S = average sentences per 100 words
    if total_words >= 100 and total_sentences > 0:
        L = (total_characters / total_words) * 100
        S = (total_sentences / total_words) * 100
        cli = 0.0588 * L - 0.296 * S - 15.8
        scores.coleman_liau_index = max(0, cli)

    # Consensus grade level (average of available grade-level metrics)
    grade_metrics = [
        g for g in [
            scores.flesch_kincaid_grade,
            scores.gunning_fog_index,
            scores.smog_index,
            scores.automated_readability_index,
            scores.coleman_liau_index,
        ] if g is not None
    ]
    if grade_metrics:
        scores.consensus_grade_level = sum(grade_metrics) / len(grade_metrics)
        scores.reading_level_description = _describe_grade_level(
            scores.consensus_grade_level
        )

    return scores


def _describe_grade_level(grade: float) -> str:
    """Convert a grade level number to a human-readable description."""
    if grade <= 1:
        return "Very easy to read (approximately Grade 1 level or below)"
    elif grade <= 3:
        return "Easy to read (approximately Grades 1-3)"
    elif grade <= 6:
        return "Fairly easy to read (approximately Grades 4-6)"
    elif grade <= 8:
        return "Plain English (approximately Grades 7-8). Suitable for general public."
    elif grade <= 10:
        return "Fairly difficult (approximately Grades 9-10)"
    elif grade <= 12:
        return "Difficult (approximately Grades 11-12)"
    elif grade <= 16:
        return "Very difficult (undergraduate university level)"
    else:
        return "Extremely difficult (graduate/professional level)"


def describe_flesch_score(score: float) -> str:
    """Interpret a Flesch Reading Ease score."""
    if score >= 90:
        return "Very easy — understood by an average 11-year-old."
    elif score >= 80:
        return "Easy — conversational English."
    elif score >= 70:
        return "Fairly easy — plain English suitable for general audience."
    elif score >= 60:
        return "Standard — understood by 13-15 year olds."
    elif score >= 50:
        return "Fairly difficult — some high school education helpful."
    elif score >= 30:
        return "Difficult — best understood by college graduates."
    elif score >= 0:
        return "Very difficult — university graduate level."
    else:
        return "Score out of range."
