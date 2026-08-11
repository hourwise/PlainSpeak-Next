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
    # Titles & honorifics
    "mr", "mrs", "ms", "miss", "dr", "prof", "rev", "hon", "st", "sr", "jr",
    "esq", "sir", "madam", "mx", "fr", "br", "hrh",
    # Military & professional ranks
    "capt", "col", "comdr", "gen", "gov", "lt", "maj", "sgt", "cpl", "adm",
    "cmdr", "ltcol", "bg", "mg", "lg", "pfc", "po", "cpt",
    # Academic degrees & certifications
    "ph.d", "phd", "md", "rn", "jd", "dds", "dvm", "edd", "psyd",
    "ba", "bs", "ma", "ms", "mfa", "mba", "mpa", "mph", "llb", "llm",
    "cpa", "cfa", "pe", "ra", "aia",
    # Business entities
    "inc", "ltd", "co", "corp", "llc", "llp", "plc", "pty", "bros",
    "assn", "assoc", "dept", "univ", "inst", "soc", "org",
    # Common Latin abbreviations
    "etc", "vs", "viz", "al", "et al", "ca", "cf", "ibid", "op cit",
    "loc cit", "et seq", "q.v", "s.v", "n.b",
    # Common English abbreviations
    "approx", "appt", "apt", "ave", "blvd", "bldg", "est", "temp",
    "mgr", "admin", "dept", "div", "ext", "fax", "tel", "ph",
    # Months
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
    # Time
    "a.m", "p.m", "am", "pm",
    # Countries/regions (common abbreviations)
    "u.s", "u.k", "u.s.a", "u.a.e", "e.u", "n.z",
    # Latin phrases
    "e.g", "i.e", "a.d", "b.c", "c.e", "b.c.e",
    # References & citations
    "no", "nos", "vol", "vols", "pp", "p", "ch", "ed", "eds",
    "fig", "figs", "eq", "eqs", "ref", "refs", "sec", "secs",
    "art", "arts", "para", "paras", "sch", "sched", "reg", "regs",
    # Units of measurement
    "kg", "lb", "lbs", "oz", "fl oz", "ml", "l", "gal", "qt", "pt",
    "cm", "m", "km", "mm", "in", "ft", "yd", "mi", "sq", "cu",
    "mph", "kph", "rpm", "psi", "v", "w", "kw", "mw", "hz", "khz",
    # States (US)
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    # Additional common multi-word abbreviations
    "u.s", "u.k", "e.g", "i.e",
    # Ordinal indicators
    "st", "nd", "rd", "th",
}


def count_syllables(word: str) -> int:
    """
    Estimate the number of syllables in an English word.

    Uses the CMU Pronouncing Dictionary for known words (125,000+ entries,
    near-100% accuracy) and falls back to a pattern-based heuristic for
    unknown words (~85-95% accuracy).

    Returns at least 1 for any non-empty alphabetic string.
    """
    word = word.lower().strip()
    if not word or not word.isalpha():
        return 0

    # Special cases for very short words
    if len(word) <= 2:
        return 1

    # Try the CMU dictionary first (lazy-loaded, cached in memory)
    try:
        from .syllable_data import get_syllable_count
        syllable_dict = get_syllable_count()
        if word in syllable_dict:
            return syllable_dict[word]
    except (ImportError, FileNotFoundError):
        pass  # Fall back to heuristic if data file not available

    # Fall back to heuristic for words not in the dictionary
    return _count_syllables_heuristic(word)


def _count_syllables_heuristic(word: str) -> int:
    """
    Pattern-based syllable counter. Used as fallback when the CMU dictionary
    doesn't contain the word.
    """
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

    Handles common abbreviations, decimal numbers, URLs, initials,
    numbered lists, and ellipses. Known limitations:
    - Some abbreviations not in ABBREVIATIONS set
    - Dialogue with complex punctuation
    - Lists with complex formatting

    Returns a list of sentence strings with whitespace stripped.
    """
    if not text:
        return []

    # Phase 1: Protect patterns that contain periods but are not
    # sentence boundaries.

    protected = text

    # 1a. Protect URLs and email addresses
    # Match http/https/ftp URLs and email addresses
    url_pattern = re.compile(
        r'(?:https?://|ftp://|www\.)[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE,
    )
    url_placeholders: dict[str, str] = {}
    url_counter = [0]

    def _protect_url(match: re.Match) -> str:
        key = f"__URL_{url_counter[0]}__"
        url_counter[0] += 1
        url_placeholders[key] = match.group(0)
        return key

    protected = url_pattern.sub(_protect_url, protected)

    # Also protect email addresses
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    email_placeholders: dict[str, str] = {}
    email_counter = [0]

    def _protect_email(match: re.Match) -> str:
        key = f"__EMAIL_{email_counter[0]}__"
        email_counter[0] += 1
        email_placeholders[key] = match.group(0)
        return key

    protected = email_pattern.sub(_protect_email, protected)

    # 1b. Protect decimal numbers (3.14, 99.9%, $5.00, etc.)
    protected = re.sub(r'(\d)\.(\d)', r'\1__DECIMAL__\2', protected)

    # 1c. Protect known abbreviations (longest first to avoid partial matches)
    for abbr in sorted(ABBREVIATIONS, key=len, reverse=True):
        # Match abbreviation followed by a period, at word boundaries
        pattern = re.compile(
            r'\b' + re.escape(abbr) + r'\.',
            re.IGNORECASE,
        )
        placeholder = f'__ABBR_{abbr.replace(".", "_").replace(" ", "_")}__'
        protected = pattern.sub(placeholder, protected)

    # 1d. Protect single-letter initials in names (J.K. Rowling, J. R. R. Tolkien)
    # Pattern: uppercase letter + period, possibly repeated with spaces
    # This is tricky; we target the common "X. X. Lastname" pattern
    initial_pattern = re.compile(
        r'\b([A-Z])\.(?=\s+[A-Z]\.)',
    )
    protected = initial_pattern.sub(r'\1__INITIAL__', protected)

    # Also protect single initial before surname: "J. Smith"
    initial_surname_pattern = re.compile(
        r'\b([A-Z])\.(?=\s+[A-Z][a-z])',
    )
    protected = initial_surname_pattern.sub(r'\1__INITIAL__', protected)

    # 1e. Protect ellipsis (...)
    protected = protected.replace('...', '__ELLIPSIS__')

    # 1f. Protect numbered list markers at start of line
    # Like "1." or "1.1" or "a." or "i." at the beginning of a line
    numbered_list_pattern = re.compile(
        r'(^|\n)\s*((?:\d+\.)+(?:\d+)?|[a-zA-Z]\.|\([a-zA-Z0-9]+\))\s*',
        re.MULTILINE,
    )
    list_placeholders: dict[str, str] = {}
    list_counter = [0]

    def _protect_list(match: re.Match) -> str:
        key = f'__LIST_{list_counter[0]}__'
        list_counter[0] += 1
        list_placeholders[key] = match.group(0)
        return key

    protected = numbered_list_pattern.sub(_protect_list, protected)

    # Phase 2: Split on sentence-ending punctuation

    # Split on [.!?] followed by one or more whitespace characters
    # and then a capital letter or a number (start of next sentence)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', protected)

    # Also handle sentence-ending punctuation followed by newline + capital
    # (already handled above since \s+ includes \n)

    # Phase 3: Restore protected patterns
    result = []
    for s in sentences:
        # Restore URLs
        for key, url in url_placeholders.items():
            s = s.replace(key, url)
        # Restore emails
        for key, email in email_placeholders.items():
            s = s.replace(key, email)
        # Restore decimal numbers
        s = s.replace('__DECIMAL__', '.')
        # Restore abbreviations
        for abbr in ABBREVIATIONS:
            placeholder = f'__ABBR_{abbr.replace(".", "_").replace(" ", "_")}__'
            s = s.replace(placeholder, abbr + '.')
        # Restore initials
        s = s.replace('__INITIAL__', '.')
        # Restore ellipsis
        s = s.replace('__ELLIPSIS__', '...')
        # Restore list markers
        for key, marker in list_placeholders.items():
            s = s.replace(key, marker)

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
