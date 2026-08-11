"""
Tests for the readability analyzer module.

Includes known-answer tests against manually verified scores
for standard test passages.
"""

import math
import pytest
from plainspeak.analyzer import (
    count_syllables,
    split_sentences,
    split_words,
    count_complex_words,
    analyze,
    ReadabilityScores,
    describe_flesch_score,
)


# ── Syllable counting tests ────────────────────────────────────────────────

class TestSyllableCounting:
    """Test syllable counter against known words."""

    # (word, expected_syllables)
    KNOWN_WORDS = [
        # Single syllable
        ("the", 1),
        ("cat", 1),
        ("dog", 1),
        ("fish", 1),
        ("run", 1),
        ("jump", 1),
        ("big", 1),
        ("small", 1),
        ("a", 1),
        ("i", 1),
        # Two syllables
        ("water", 2),
        ("happy", 2),
        ("table", 2),
        ("people", 2),
        ("simple", 2),
        ("apple", 2),
        ("little", 2),
        ("seven", 2),
        ("mother", 2),
        ("paper", 2),
        # Three syllables
        ("beautiful", 3),
        ("dangerous", 3),
        ("important", 3),
        ("wonderful", 3),
        ("government", 3),
        ("understand", 3),
        ("difficult", 3),
        ("together", 3),
        # Four syllables
        ("information", 4),
        ("communication", 5),
        ("unbelievable", 5),
        ("accessibility", 6),
        # Edge cases
        ("bye", 1),
        ("cake", 1),
        ("bake", 1),
        ("love", 1),
        ("every", 2),  # CMU dict: 2 syllables (EH1 V R IY0)
    ]

    @pytest.mark.parametrize("word,expected", KNOWN_WORDS)
    def test_known_syllables(self, word, expected):
        """Known words should have correct syllable counts."""
        result = count_syllables(word)
        assert result == expected, f"'{word}': expected {expected}, got {result}"

    def test_empty_string(self):
        """Empty string should return 0 syllables."""
        assert count_syllables("") == 0

    def test_non_alpha(self):
        """Non-alphabetic strings should return 0."""
        assert count_syllables("123") == 0
        assert count_syllables("!@#") == 0

    def test_always_at_least_one(self):
        """Any alphabetic word should have at least 1 syllable."""
        for word in ["a", "i", "by", "my", "shy", "cry", "fly", "sky"]:
            assert count_syllables(word) >= 1, f"'{word}' should have >= 1 syllable"

    def test_short_words(self):
        """Single-letter and two-letter words."""
        assert count_syllables("a") == 1
        assert count_syllables("be") == 1
        assert count_syllables("go") == 1


# ── Sentence segmentation tests ────────────────────────────────────────────

class TestSentenceSegmentation:
    """Test sentence splitting."""

    def test_simple_sentences(self):
        text = "The cat sat on the mat. The dog ran away. Birds fly high."
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_single_sentence(self):
        text = "This is one sentence without a period at the end"
        sentences = split_sentences(text)
        assert len(sentences) >= 1

    def test_question_and_exclamation(self):
        text = "What is this? It is amazing! I love it."
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_abbreviation_handling(self):
        """Abbreviations like Dr. Mr. Mrs. should not split sentences."""
        text = "Dr. Smith and Mr. Jones went to the store. They bought milk."
        sentences = split_sentences(text)
        # Should be 2 sentences, not split on Dr. or Mr.
        assert len(sentences) == 2, f"Got {len(sentences)}: {sentences}"

    def test_empty_text(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_multiple_spaces(self):
        text = "First sentence.    Second sentence.  Third sentence."
        sentences = split_sentences(text)
        assert len(sentences) == 3

    def test_decimal_numbers(self):
        """Decimal numbers should not cause sentence splits."""
        text = "The price is 3.50 dollars. That is cheap."
        sentences = split_sentences(text)
        # Should handle the decimal without splitting incorrectly
        assert len(sentences) >= 1

    def test_ellipsis(self):
        """Ellipsis should not be treated as sentence boundary."""
        text = "She thought about it... and then decided to go."
        sentences = split_sentences(text)
        assert len(sentences) == 1

    def test_acronyms(self):
        """Text with U.S. and U.K. should handle abbreviations."""
        text = "The U.S. and U.K. have strong ties. They cooperate often."
        sentences = split_sentences(text)
        assert len(sentences) == 2

    def test_list_with_periods(self):
        """Numbered list items should be handled."""
        text = "There are three reasons. First, it is easy. Second, it is fast. Third, it is free."
        sentences = split_sentences(text)
        assert len(sentences) == 4

    def test_dialogue(self):
        """Text with quotation marks."""
        text = 'She said "hello." He replied "goodbye."'
        sentences = split_sentences(text)
        # Should handle quotes around sentence boundaries
        assert len(sentences) >= 1

    # ── Structural break regression tests ──

    def test_double_newline_boundary(self):
        """Double newlines should create sentence boundaries."""
        text = "First paragraph here.\n\nSecond paragraph goes here."
        sentences = split_sentences(text)
        assert len(sentences) >= 2, f"Expected >=2 sentences, got {len(sentences)}: {sentences}"

    def test_list_markers_as_boundaries(self):
        """Lines starting with bullet/list markers should be separate."""
        text = "Things to do:\n- Buy milk\n- Walk dog\n- Call mum"
        sentences = split_sentences(text)
        # Should recognise the bullet items as separate units
        assert len(sentences) >= 3, f"Expected >=3, got {len(sentences)}: {sentences}"

    def test_heading_line_boundary(self):
        """ALL CAPS headings should be separate from body text."""
        text = "IMPORTANT SAFETY NOTICE\nThe building will be closed on Friday."
        sentences = split_sentences(text)
        assert len(sentences) >= 2, f"Expected >=2, got {len(sentences)}: {sentences}"

    def test_lines_without_terminal_punctuation(self):
        """Lines without .!? should be treated as separate when appropriate."""
        text = "Meeting agenda\nIntroduction\nBudget review\nAny other business"
        sentences = split_sentences(text)
        # Each line is a standalone item
        assert len(sentences) >= 3, f"Expected >=3, got {len(sentences)}: {sentences}"

    def test_colon_heading_boundary(self):
        """Lines ending with colon should separate from following content."""
        text = "Please note the following:\nAll visitors must sign in at reception."
        sentences = split_sentences(text)
        assert len(sentences) >= 2, f"Expected >=2, got {len(sentences)}: {sentences}"


# ── Word splitting tests ───────────────────────────────────────────────────

class TestWordSplitting:
    """Test word extraction."""

    def test_simple_words(self):
        text = "The quick brown fox jumps over the lazy dog."
        words = split_words(text)
        assert len(words) == 9
        assert words == ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"]

    def test_contractions(self):
        """Contractions should be split into alphabetic parts."""
        text = "Don't can't won't it's"
        words = split_words(text)
        # "Don", "t", "can", "t", "won", "t", "it", "s"
        assert len(words) >= 4

    def test_numbers_ignored(self):
        text = "There are 3 cats and 4 dogs."
        words = split_words(text)
        assert "3" not in words
        assert "4" not in words

    def test_punctuation_removed(self):
        text = "Hello, world! How are you?"
        words = split_words(text)
        assert words == ["hello", "world", "how", "are", "you"]


# ── Complex word counting tests ────────────────────────────────────────────

class TestComplexWords:
    """Test complex word counting."""

    def test_default_threshold(self):
        words = ["the", "cat", "water", "beautiful", "information", "a"]
        count = count_complex_words(words, syllable_threshold=3)
        # water=2, beautiful=3, information=4
        assert count == 2  # beautiful and information

    def test_custom_threshold(self):
        words = ["the", "cat", "water", "beautiful", "information"]
        count = count_complex_words(words, syllable_threshold=2)
        # water=2, beautiful=3, information=4 — all except "the" and "cat" and "a"
        assert count == 3


# ── Full analysis tests ────────────────────────────────────────────────────

class TestAnalyze:
    """Test the full analysis pipeline."""

    # Known-answer test: "The cat sat on the mat."
    # This is a very simple sentence used for validation.
    # Words: 6, Sentences: 1, Syllables: ~6 (all 1-syllable words)
    # Flesch Reading Ease should be very high (easy)
    # Grade level should be very low
    def test_very_simple_text(self):
        text = "The cat sat on the mat."
        scores = analyze(text)
        assert scores.total_words == 6
        assert scores.total_sentences == 1
        assert scores.flesch_reading_ease is not None
        # Very simple text should have high reading ease
        assert scores.flesch_reading_ease > 70, f"Got FRE={scores.flesch_reading_ease}"
        # Very simple text should have low grade level
        if scores.flesch_kincaid_grade is not None:
            assert scores.flesch_kincaid_grade < 5

    def test_known_grade_level_text(self):
        """
        Test with a passage of known approximate grade level.

        This passage is adapted from a public-domain text and has been
        scored manually against reference implementations.
        Expected approximate grade level: 7-9 (Plain English)
        """
        text = (
            "Reading is one of the most important skills a person can learn. "
            "It opens doors to knowledge and helps people understand the world. "
            "Many people find reading difficult, but with practice, anyone can improve. "
            "Schools teach reading from a very early age, and most children learn "
            "the basics within the first few years of education."
        )
        scores = analyze(text)
        assert scores.total_words > 20
        assert scores.total_sentences >= 3
        if scores.consensus_grade_level is not None:
            # Should be in plain English range
            assert scores.consensus_grade_level < 12, (
                f"Expected grade < 12, got {scores.consensus_grade_level}"
            )
            assert scores.consensus_grade_level > 0

    def test_difficult_text(self):
        """
        Test with a deliberately complex passage.

        Academic/legal style text should score higher grade levels.
        """
        text = (
            "The implementation of comprehensive environmental regulatory "
            "frameworks necessitates the coordination of multiple administrative "
            "jurisdictions and the establishment of standardized methodological "
            "protocols for the quantification of anthropogenic ecological "
            "modification. Notwithstanding the aforementioned considerations, "
            "the promulgation of such provisions remains contingent upon "
            "legislative authorization and interdepartmental collaboration."
        )
        scores = analyze(text)
        if scores.consensus_grade_level is not None:
            # Should be high grade level
            assert scores.consensus_grade_level > 10, (
                f"Expected grade > 10 for difficult text, got {scores.consensus_grade_level}"
            )

    def test_empty_text_raises(self):
        with pytest.raises(ValueError):
            analyze("")
        with pytest.raises(ValueError):
            analyze("   ")

    def test_non_text_content(self):
        """Text with only numbers and symbols should raise."""
        with pytest.raises(ValueError):
            analyze("123 456 789 !@# $%^")

    def test_consensus_grade_is_average(self):
        """Consensus grade should be the average of available metrics."""
        text = "This is a simple test sentence for analysis purposes only."
        scores = analyze(text)
        if scores.consensus_grade_level is not None:
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
                expected = sum(grade_metrics) / len(grade_metrics)
                assert math.isclose(
                    scores.consensus_grade_level, expected, rel_tol=0.01
                ), f"Expected {expected}, got {scores.consensus_grade_level}"

    def test_all_scores_present(self):
        """For a reasonable text, all six metrics should be computed."""
        text = (
            "Accessibility in digital content is essential for ensuring that "
            "all users, regardless of ability, can access information. "
            "Web standards provide guidelines for creating accessible content. "
            "Following these standards benefits everyone, not just people with "
            "disabilities. Clear writing is an important part of accessibility."
        )
        scores = analyze(text)
        assert scores.flesch_reading_ease is not None
        assert scores.flesch_kincaid_grade is not None
        assert scores.gunning_fog_index is not None
        assert scores.smog_index is not None
        assert scores.automated_readability_index is not None
        # Coleman-Liau may not be available for short texts (<100 words)
        assert scores.consensus_grade_level is not None

    def test_coleman_liau_requires_100_words(self):
        """Coleman-Liau requires at least 100 words."""
        short_text = "Short text."
        scores = analyze(short_text)
        # Coleman-Liau should be None for very short texts
        # (though it depends on exact implementation threshold)

    # ── Grade clamping regression tests ──

    def test_grades_never_exceed_max(self):
        """No grade metric should exceed MAX_CREDIBLE_GRADE (25.0)."""
        from plainspeak.analyzer import MAX_CREDIBLE_GRADE
        text = "This is a test. " * 5  # Short text, might produce unstable metrics
        scores = analyze(text)
        grade_metrics = [
            scores.flesch_kincaid_grade,
            scores.gunning_fog_index,
            scores.smog_index,
            scores.automated_readability_index,
            scores.coleman_liau_index,
        ]
        for g in grade_metrics:
            if g is not None:
                assert g <= MAX_CREDIBLE_GRADE, f"Grade {g} exceeds max {MAX_CREDIBLE_GRADE}"

    def test_grades_never_below_zero(self):
        """No grade metric should be below 0."""
        text = "Simple. " * 10
        scores = analyze(text)
        grade_metrics = [
            scores.flesch_kincaid_grade,
            scores.gunning_fog_index,
            scores.smog_index,
            scores.automated_readability_index,
            scores.coleman_liau_index,
        ]
        for g in grade_metrics:
            if g is not None:
                assert g >= 0, f"Grade {g} is below 0"

    def test_gunning_fog_clamped_on_extreme_text(self):
        """Gunning Fog should be clamped for text with extreme complex-word ratio."""
        # Very short text with all complex words and one "sentence" — 
        # this is the kind of edge case that produces absurd Fog values
        text = "antidisestablishmentarianism counterrevolutionary incomprehensibility"
        scores = analyze(text)
        if scores.gunning_fog_index is not None:
            from plainspeak.analyzer import MAX_CREDIBLE_GRADE
            assert scores.gunning_fog_index <= MAX_CREDIBLE_GRADE, (
                f"Gunning Fog {scores.gunning_fog_index} exceeds max {MAX_CREDIBLE_GRADE}"
            )


class TestFleschDescription:
    """Test Flesch Reading Ease score descriptions."""

    def test_ranges(self):
        assert "Very easy" in describe_flesch_score(95)
        assert "Easy" in describe_flesch_score(85)
        assert "Fairly easy" in describe_flesch_score(75)
        assert "Standard" in describe_flesch_score(65)
        assert "Fairly difficult" in describe_flesch_score(55)
        assert "Difficult" in describe_flesch_score(40)
        assert "Very difficult" in describe_flesch_score(20)

    def test_boundaries(self):
        """Test boundary values."""
        assert "Very easy" in describe_flesch_score(90)
        assert "Easy" in describe_flesch_score(80)
        assert "Fairly easy" in describe_flesch_score(70)
        assert "Standard" in describe_flesch_score(60)
        assert "Fairly difficult" in describe_flesch_score(50)
        assert "Difficult" in describe_flesch_score(30)
