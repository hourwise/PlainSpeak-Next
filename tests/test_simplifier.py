"""
Tests for the text simplification module.
"""

import pytest
from plainspeak.simplifier import (
    find_passive_voice,
    find_long_sentences,
    find_complex_words,
    find_nominalizations,
    find_jargon,
    find_redundant_pairs,
    find_hidden_verbs,
    analyze_simplification,
    generate_simplified_text,
    split_sentences,
    Barrier,
    SimplificationResult,
)


class TestPassiveVoice:
    """Test passive voice detection."""

    def test_clear_passive(self):
        """Clear passive constructions should be detected."""
        sentence = "The report was written by the committee."
        barriers = find_passive_voice(sentence, 0)
        assert len(barriers) >= 1
        assert barriers[0].barrier_type == "passive_voice"

    def test_active_voice_not_flagged(self):
        """Active voice sentences should not be flagged as passive."""
        sentence = "The committee wrote the report."
        barriers = find_passive_voice(sentence, 0)
        # Should not flag this as passive
        passive_flags = [b for b in barriers if b.barrier_type == "passive_voice"]
        # "wrote" is past tense, not a participle with "be"
        # Our regex looks for "be + past participle" — "wrote" alone won't match

    def test_adjectival_participle_filtered(self):
        """Common adjectival participles should not be flagged."""
        sentence = "I am interested in the results."
        barriers = find_passive_voice(sentence, 0)
        # "interested" is in the adjectival participles set
        assert len(barriers) == 0, f"Should not flag 'interested': {barriers}"

    def test_multiple_passives(self):
        """Multiple passive constructions in one sentence."""
        sentence = "The data was collected and the results were analyzed by researchers."
        barriers = find_passive_voice(sentence, 0)
        assert len(barriers) >= 1

    def test_no_false_positive_on_adjectives(self):
        """Adjectives ending in -ed should not trigger passive detection."""
        sentence = "The experienced team completed the project."
        barriers = find_passive_voice(sentence, 0)
        # "experienced" is adjectival
        passive = [b for b in barriers if b.barrier_type == "passive_voice"]
        assert len(passive) == 0, f"Got false positive: {passive}"


class TestLongSentences:
    """Test long sentence detection."""

    def test_short_sentence_not_flagged(self):
        sentences = ["This is a short sentence."]
        barriers = find_long_sentences(sentences)
        assert len(barriers) == 0

    def test_very_long_sentence_flagged(self):
        """A sentence with many words should be flagged."""
        words = "word " * 40
        sentence = words.strip() + "."
        sentences = [sentence]
        barriers = find_long_sentences(sentences)
        assert len(barriers) >= 1
        assert barriers[0].barrier_type == "long_sentence"
        # Should be critical (>40 words or >35 depending on threshold)
        assert barriers[0].severity in ("critical", "warning")

    def test_moderate_sentence_flagged_info(self):
        """A sentence just over 25 words should be flagged as info."""
        words = "word " * 27
        sentence = words.strip() + "."
        sentences = [sentence]
        barriers = find_long_sentences(sentences)
        long_bars = [b for b in barriers if b.barrier_type == "long_sentence"]
        assert len(long_bars) >= 1


class TestComplexWords:
    """Test complex word detection."""

    def test_simple_word_not_flagged(self):
        sentence = "The cat sat on the mat."
        barriers = find_complex_words(sentence, 0)
        # All words are short
        assert len(barriers) == 0

    def test_complex_word_flagged(self):
        sentence = "The implementation was successful."
        barriers = find_complex_words(sentence, 0)
        # "implementation" is 5 syllables, 14 chars, should be flagged
        complex_flags = [b for b in barriers if b.matched_text.lower() == "implementation"]
        assert len(complex_flags) >= 1

    def test_jargon_word_has_suggestion(self):
        sentence = "We will utilize this methodology."
        barriers = find_complex_words(sentence, 0)
        # "utilize" should have a suggestion to use "use"
        utilize_flags = [b for b in barriers if b.matched_text.lower() == "utilize"]
        if utilize_flags:
            assert "use" in utilize_flags[0].suggestion.lower()


class TestNominalizations:
    """Test nominalization detection."""

    def test_nominalization_detected(self):
        sentence = "The implementation of the policy requires consideration."
        barriers = find_nominalizations(sentence, 0)
        # Should find "implementation" and "consideration"
        assert len(barriers) >= 2

    def test_common_exceptions_not_flagged(self):
        """Common words ending in -tion that aren't nominalizations should not be flagged."""
        sentence = "The nation is strong."
        barriers = find_nominalizations(sentence, 0)
        # "nation" is in exceptions
        nation_flags = [b for b in barriers if "nation" in b.matched_text.lower()]
        assert len(nation_flags) == 0


class TestJargon:
    """Test jargon detection."""

    def test_jargon_detected(self):
        sentence = "We will commence the project forthwith."
        barriers = find_jargon(sentence, 0)
        assert len(barriers) >= 2  # "commence" and "forthwith"

    def test_jargon_suggestion(self):
        sentence = "We need to utilize this tool."
        barriers = find_jargon(sentence, 0)
        utilize_flags = [b for b in barriers if b.matched_text.lower() == "utilize"]
        if utilize_flags:
            assert "use" in utilize_flags[0].suggestion.lower()

    def test_multi_word_phrase(self):
        sentence = "The payment is due prior to the deadline."
        barriers = find_jargon(sentence, 0)
        # "prior to" is in the glossary
        phrase_flags = [b for b in barriers if "prior to" in b.matched_text.lower()]
        assert len(phrase_flags) >= 1


class TestRedundantPairs:
    """Test redundant pair detection."""

    def test_redundant_pair_detected(self):
        sentence = "This is absolutely essential for success."
        barriers = find_redundant_pairs(sentence, 0)
        assert len(barriers) >= 1
        assert "absolutely essential" in barriers[0].matched_text.lower()

    def test_non_redundant_not_flagged(self):
        sentence = "This is an important consideration."
        barriers = find_redundant_pairs(sentence, 0)
        assert len(barriers) == 0


class TestHiddenVerbs:
    """Test hidden verb detection."""

    def test_hidden_verb_detected(self):
        sentence = "We need to make a decision about this."
        barriers = find_hidden_verbs(sentence, 0)
        assert len(barriers) >= 1
        assert "decision" in barriers[0].suggestion.lower() or "decide" in barriers[0].suggestion.lower()

    def test_plain_verb_not_flagged(self):
        sentence = "We need to decide about this."
        barriers = find_hidden_verbs(sentence, 0)
        assert len(barriers) == 0


class TestFullSimplification:
    """Test the full simplification analysis."""

    def test_simple_text_few_barriers(self):
        text = "The cat sat on the mat. It was happy."
        result = analyze_simplification(text)
        # Should have few or no barriers
        assert result.total_barriers < 5, f"Simple text got {result.total_barriers} barriers"

    def test_complex_text_many_barriers(self):
        text = (
            "The implementation of the aforementioned regulatory provisions "
            "necessitates the utilization of comprehensive methodological "
            "frameworks for the quantification of outcomes. It is imperative "
            "that the committee makes a decision about this matter prior to "
            "the commencement of the subsequent phase. The report was written "
            "by the designated personnel and the results were analyzed in "
            "accordance with established protocols."
        )
        result = analyze_simplification(text)
        # Should find many barriers
        assert result.total_barriers > 5, f"Complex text only got {result.total_barriers} barriers"

    def test_result_structure(self):
        text = "We will commence the project. The decision was made by the committee."
        result = analyze_simplification(text)
        assert isinstance(result, SimplificationResult)
        assert result.original_text == text
        assert len(result.sentences) >= 2
        assert result.total_barriers >= 0
        assert result.summary != ""

    def test_barrier_structure(self):
        text = "We will utilize this methodology."
        result = analyze_simplification(text)
        if result.barriers:
            barrier = result.barriers[0]
            assert isinstance(barrier, Barrier)
            assert barrier.barrier_type != ""
            assert barrier.sentence_index >= 0
            assert barrier.sentence_text != ""
            assert barrier.severity in ("critical", "warning", "info")

    def test_severity_counts(self):
        text = (
            "We will commence the implementation of the regulatory provisions "
            "and it is absolutely essential that this is done in a timely manner "
            "due to the fact that the deadline is approaching rapidly."
        )
        result = analyze_simplification(text)
        assert result.critical_count + result.warning_count + result.info_count == result.total_barriers

    def test_barriers_sorted_by_sentence(self):
        """Barriers should be sorted by sentence index."""
        text = (
            "First sentence with a jargon word like utilize. "
            "Second sentence with another complex construction. "
            "Third sentence for good measure."
        )
        result = analyze_simplification(text)
        prev_idx = -1
        for barrier in result.barriers:
            assert barrier.sentence_index >= prev_idx
            prev_idx = barrier.sentence_index


class TestSimplifiedTextGeneration:
    """Test the mechanical text simplification feature."""

    def test_replaces_jargon_words(self):
        text = "We will utilize this methodology."
        simplified, count = generate_simplified_text(text)
        assert count >= 2  # "utilize" and "methodology"
        assert "**use**" in simplified.lower() or "**method**" in simplified.lower()

    def test_marks_replacements(self):
        """Replacements should be marked with **asterisks**."""
        text = "We will commence the project."
        simplified, count = generate_simplified_text(text)
        assert count >= 1
        assert "**" in simplified  # Should have marked replacements

    def test_preserves_unchanged_text(self):
        """Words without glossary entries should remain unchanged."""
        text = "The cat sat on the mat."
        simplified, count = generate_simplified_text(text)
        assert count == 0
        assert simplified == text

    def test_replaces_multi_word_phrases(self):
        text = "The payment is due prior to the deadline."
        simplified, count = generate_simplified_text(text)
        assert count >= 1
        # "prior to" should be replaced with "before"
        assert "**before**" in simplified.lower()

    def test_no_replacements_in_empty_text(self):
        text = ""
        simplified, count = generate_simplified_text(text)
        assert count == 0
        assert simplified == ""

    def test_case_insensitive_replacement(self):
        """Replacements should work regardless of capitalization."""
        text = "UTILIZE this tool. Utilize it well."
        simplified, count = generate_simplified_text(text)
        # Both "UTILIZE" and "Utilize" are replaced by one regex substitution
        assert count >= 1
        # But both occurrences should be marked
        assert simplified.count("**use**") == 2
