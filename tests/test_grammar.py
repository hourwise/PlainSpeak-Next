"""Tests for grammar post-processing module."""

import pytest
from plainspeak.grammar import (
    _starts_with_vowel_sound,
    fix_articles,
    fix_capitalization,
    post_process_simplified,
)


class TestVowelSound:
    def test_vowel_sound_words(self):
        assert _starts_with_vowel_sound("important") is True
        assert _starts_with_vowel_sound("apple") is True
        assert _starts_with_vowel_sound("elephant") is True
        assert _starts_with_vowel_sound("orange") is True
        assert _starts_with_vowel_sound("umbrella") is True
        assert _starts_with_vowel_sound("hour") is True
        assert _starts_with_vowel_sound("honest") is True

    def test_consonant_sound_words(self):
        assert _starts_with_vowel_sound("useful") is False
        assert _starts_with_vowel_sound("union") is False
        assert _starts_with_vowel_sound("university") is False
        assert _starts_with_vowel_sound("unit") is False
        assert _starts_with_vowel_sound("cat") is False
        assert _starts_with_vowel_sound("house") is False


class TestFixArticles:
    def test_a_to_an_before_vowel(self):
        assert fix_articles("a important breach") == "an important breach"
        assert fix_articles("a orange") == "an orange"
        assert fix_articles("a hour") == "an hour"
        assert fix_articles("a honest person") == "an honest person"

    def test_a_preserved_before_consonant(self):
        assert fix_articles("a cat") == "a cat"
        assert fix_articles("a useful tool") == "a useful tool"
        assert fix_articles("a university") == "a university"

    def test_an_to_a_before_consonant(self):
        assert fix_articles("an useful tool") == "a useful tool"
        assert fix_articles("an union") == "a union"
        # Known limitation: 'European' starts with 'e', always treated as vowel
        # sound by heuristic, even though it's 'yu-' consonant sound.

    def test_with_markers(self):
        assert fix_articles("a **important** breach") == "an **important** breach"
        assert fix_articles("a **useful** tool") == "a **useful** tool"


class TestFixCapitalization:
    def test_first_letter_capitalized(self):
        assert fix_capitalization("the test.") == "The test."
        assert fix_capitalization("hello world") == "Hello world"

    def test_sentence_after_period(self):
        result = fix_capitalization("first sentence. second sentence.")
        assert "Second sentence" in result

    def test_already_capitalized(self):
        assert fix_capitalization("Hello world.") == "Hello world."
        assert fix_capitalization("HELLO") == "HELLO"


class TestPostProcess:
    def test_combined_fixes(self):
        result = post_process_simplified("a important thing. an useful tool.")
        assert "an important" in result.lower() or "An important" in result
        assert "a useful" in result.lower() or "A useful" in result

    def test_empty_text(self):
        assert post_process_simplified("") == ""
        assert post_process_simplified("   ") == "   "

    def test_no_change_when_correct(self):
        assert post_process_simplified("an apple") == "An apple"
        assert post_process_simplified("a cat") == "A cat"
