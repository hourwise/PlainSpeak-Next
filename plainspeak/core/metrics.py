"""Readability metrics and the difficulty bands derived from them."""

import math
from dataclasses import dataclass, field
from typing import Optional

from .tokenize import (
    count_complex_words,
    count_syllables,
    split_sentences,
    split_words,
)


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
    
    # Difficulty band (replaces raw consensus grade as primary output)
    difficulty_band: str = ""           # e.g. "Very Difficult"
    difficulty_band_label: str = ""     # e.g. "Very difficult (graduate/professional level)"
    difficulty_band_explanation: str = ""  # Longer explanation for the report
    short_text_warning: str = ""        # Non-empty if text is too short for reliable metrics
    metric_spread: float = 0.0          # Range between highest and lowest grade metric
    metric_count: int = 0               # How many grade metrics were computable
    grade_warnings: list = field(default_factory=list)  # Warnings about clamped/unreliable metrics


# Maximum credible grade level — values above this are clamped and flagged
MAX_CREDIBLE_GRADE: float = 25.0


# Minimum grade level (below kindergarten)
MIN_CREDIBLE_GRADE: float = 0.0


def _classify_difficulty_band(grade: float) -> dict:
    """
    Classify a grade level into a difficulty band with explanations.
    
    Returns a dict with band, label, and explanation keys.
    Designed to communicate difficulty honestly without implying
    false precision from readability formulas.
    """
    if grade <= 3:
        return {
            "band": "Very Easy",
            "label": "Very easy (approximately early primary level)",
            "explanation": (
                "Text at this level uses very short sentences and common words. "
                "It should be accessible to almost all adult readers, including "
                "those with lower literacy, non-native speakers, and people with "
                "cognitive disabilities. This is the target level for essential "
                "public information."
            ),
        }
    elif grade <= 6:
        return {
            "band": "Easy",
            "label": "Easy (approximately upper primary level)",
            "explanation": (
                "Text at this level uses mostly short sentences and common words. "
                "It should be accessible to most adult readers. This is a good "
                "target for public-facing information, patient leaflets, and "
                "consumer communications."
            ),
        }
    elif grade <= 8:
        return {
            "band": "Fairly Easy",
            "label": "Fairly easy (approximately lower secondary level)",
            "explanation": (
                "Text at this level is generally accessible but may present "
                "difficulties for readers with lower literacy or non-native "
                "speakers. Consider whether your intended audience includes "
                "people who may struggle with this level."
            ),
        }
    elif grade <= 10:
        return {
            "band": "Standard",
            "label": "Standard (approximately mid-secondary level)",
            "explanation": (
                "Text at this level is typical of newspapers and general-interest "
                "writing. It may be challenging for readers with lower literacy, "
                "some non-native speakers, and people with cognitive fatigue. "
                "For public-service communication, consider simplification."
            ),
        }
    elif grade <= 12:
        return {
            "band": "Fairly Difficult",
            "label": "Fairly difficult (approximately upper secondary level)",
            "explanation": (
                "Text at this level requires a secondary-school reading ability. "
                "It is likely to exclude a significant portion of the general "
                "public. If this text is intended for a broad audience, "
                "substantial revision is recommended."
            ),
        }
    elif grade <= 16:
        return {
            "band": "Difficult",
            "label": "Difficult (undergraduate university level)",
            "explanation": (
                "Text at this level is comparable to undergraduate textbooks "
                "and academic writing. It assumes significant reading skill and "
                "subject knowledge. Only appropriate for specialist or "
                "professional audiences. For general-public use, this text "
                "needs major simplification."
            ),
        }
    else:
        return {
            "band": "Very Difficult",
            "label": "Very difficult (graduate/professional level)",
            "explanation": (
                "Text at this level is comparable to graduate-level academic "
                "or professional writing. It is inaccessible to the majority "
                "of adults. If this text is intended for anyone other than "
                "subject-matter specialists, it requires fundamental rewriting. "
                "Even for specialist audiences, consider whether complexity "
                "is serving communication or habit."
            ),
        }


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
        fkgl = max(MIN_CREDIBLE_GRADE, fkgl)
        if fkgl > MAX_CREDIBLE_GRADE:
            scores.grade_warnings.append(f"Flesch-Kincaid grade clamped from {fkgl:.0f} to {MAX_CREDIBLE_GRADE:.0f} (unreliable for this text)")
            fkgl = MAX_CREDIBLE_GRADE
        scores.flesch_kincaid_grade = fkgl

    # Gunning Fog Index: 0.4 * [(words/sentences) + 100 * (complex_words/words)]
    if total_sentences > 0 and total_words > 0:
        complex_pct = (total_complex_words / total_words) * 100
        gfi = 0.4 * (avg_sentence_length + complex_pct)
        gfi = max(MIN_CREDIBLE_GRADE, gfi)
        if gfi > MAX_CREDIBLE_GRADE:
            scores.grade_warnings.append(f"Gunning Fog index clamped from {gfi:.0f} to {MAX_CREDIBLE_GRADE:.0f} (unreliable for this text)")
            gfi = MAX_CREDIBLE_GRADE
        scores.gunning_fog_index = gfi

    # SMOG Index: 1.0430 * sqrt(complex_words * 30/sentences) + 3.1291
    if total_sentences > 0 and total_complex_words > 0:
        smog = 1.0430 * math.sqrt(total_complex_words * (30 / total_sentences)) + 3.1291
        smog = max(MIN_CREDIBLE_GRADE, smog)
        if smog > MAX_CREDIBLE_GRADE:
            scores.grade_warnings.append(f"SMOG index clamped from {smog:.0f} to {MAX_CREDIBLE_GRADE:.0f} (unreliable for this text)")
            smog = MAX_CREDIBLE_GRADE
        scores.smog_index = smog
    elif total_sentences > 0:
        scores.smog_index = 3.1291

    # Automated Readability Index: 4.71 * (chars/words) + 0.5 * (words/sentences) - 21.43
    if total_sentences > 0 and total_words > 0:
        ari = 4.71 * (total_characters / total_words) + 0.5 * avg_sentence_length - 21.43
        ari = max(MIN_CREDIBLE_GRADE, ari)
        if ari > MAX_CREDIBLE_GRADE:
            scores.grade_warnings.append(f"ARI clamped from {ari:.0f} to {MAX_CREDIBLE_GRADE:.0f} (unreliable for this text)")
            ari = MAX_CREDIBLE_GRADE
        scores.automated_readability_index = ari

    # Coleman-Liau Index: 0.0588 * L - 0.296 * S - 15.8
    if total_words >= 100 and total_sentences > 0:
        L = (total_characters / total_words) * 100
        S = (total_sentences / total_words) * 100
        cli = 0.0588 * L - 0.296 * S - 15.8
        cli = max(MIN_CREDIBLE_GRADE, cli)
        if cli > MAX_CREDIBLE_GRADE:
            scores.grade_warnings.append(f"Coleman-Liau index clamped from {cli:.0f} to {MAX_CREDIBLE_GRADE:.0f} (unreliable for this text)")
            cli = MAX_CREDIBLE_GRADE
        scores.coleman_liau_index = cli

    # ── Clamp and label the consensus average if any individual metric was clamped ──
    # Consensus grade level (average of available grade-level metrics)
    # Note: this averaging approach is a pragmatic summary, not a scientifically
    # validated composite. Different formulas measure different constructs.
    # The difficulty band (below) is the primary user-facing output.
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
        # Clamp consensus too
        if scores.consensus_grade_level > MAX_CREDIBLE_GRADE:
            scores.consensus_grade_level = MAX_CREDIBLE_GRADE
        scores.metric_count = len(grade_metrics)
        scores.metric_spread = max(grade_metrics) - min(grade_metrics) if len(grade_metrics) > 1 else 0.0
        
        # Classify into difficulty band
        band_info = _classify_difficulty_band(scores.consensus_grade_level)
        scores.difficulty_band = band_info["band"]
        scores.difficulty_band_label = band_info["label"]
        scores.difficulty_band_explanation = band_info["explanation"]
        
        # Legacy description (kept for backward compatibility)
        scores.reading_level_description = scores.difficulty_band_label
    
    # Short-text reliability warning
    # Readability formulas need sufficient text to produce stable estimates.
    # Below ~100 words or ~3 sentences, results should be treated as indicative only.
    if total_words < 100 or total_sentences < 3:
        scores.short_text_warning = (
            "This text is very short. Readability formulas need at least "
            "100 words and 3+ sentences to produce stable estimates. "
            "Treat these results as rough indicators, not precise measurements."
        )
    elif total_words < 300:
        scores.short_text_warning = (
            "This text is fairly short. Readability estimates may vary with "
            "small changes. For more reliable results, analyse a longer passage."
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
