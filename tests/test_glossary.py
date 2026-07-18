"""
Tests for the glossary module.
"""

import pytest
from plainspeak.glossary import GLOSSARY, SIMPLE_WORD_MAP


class TestGlossary:
    """Test the plain-language glossary."""

    def test_glossary_not_empty(self):
        """Glossary should contain a substantial number of entries."""
        assert len(GLOSSARY) > 100, f"Glossary only has {len(GLOSSARY)} entries"
        assert len(SIMPLE_WORD_MAP) > 100

    def test_glossary_entry_structure(self):
        """Each entry should be a (simpler_alternative, explanation) tuple."""
        for term, entry in GLOSSARY.items():
            assert isinstance(entry, tuple), f"Entry for '{term}' is not a tuple"
            assert len(entry) == 2, f"Entry for '{term}' has {len(entry)} elements"
            simpler, explanation = entry
            assert isinstance(simpler, str), f"Simpler for '{term}' is not a string"
            assert isinstance(explanation, str), f"Explanation for '{term}' is not a string"
            assert len(simpler) > 0, f"Simpler for '{term}' is empty"
            assert len(explanation) > 0, f"Explanation for '{term}' is empty"

    def test_simple_word_map_structure(self):
        """SIMPLE_WORD_MAP should map words to simpler alternatives."""
        for complex_word, simpler in SIMPLE_WORD_MAP.items():
            assert isinstance(complex_word, str)
            assert isinstance(simpler, str)
            assert len(simpler) > 0
            # The simpler alternative should generally be shorter
            # (Not always — phrasal verbs can be longer but clearer)

    def test_no_duplicate_keys(self):
        """No term should appear in both GLOSSARY and SIMPLE_WORD_MAP."""
        overlap = set(GLOSSARY.keys()) & set(SIMPLE_WORD_MAP.keys())
        assert len(overlap) == 0, f"Duplicate keys: {overlap}"

    def test_key_terms_present(self):
        """Essential plain-language substitutions should be in the glossary."""
        essential_terms = [
            "utilize",
            "implement",
            "facilitate",
            "leverage",
            "commence",
            "terminate",
            "demonstrate",
            "regarding",
            "in order to",
            "prior to",
            "due to the fact that",
            "in the event of",
        ]
        for term in essential_terms:
            found = term in GLOSSARY or term in SIMPLE_WORD_MAP
            assert found, f"Essential term '{term}' not in glossary"

    def test_all_terms_lowercase(self):
        """All glossary keys should be lowercase for consistent matching."""
        for term in GLOSSARY:
            assert term == term.lower(), f"Term '{term}' is not lowercase"
        for term in SIMPLE_WORD_MAP:
            assert term == term.lower(), f"Term '{term}' is not lowercase"

    def test_no_simpler_same_as_term(self):
        """The simpler alternative should not be identical to the original."""
        for term, (simpler, _) in GLOSSARY.items():
            assert simpler.lower() != term.lower(), (
                f"Simpler '{simpler}' is same as term '{term}'"
            )
        for term, simpler in SIMPLE_WORD_MAP.items():
            assert simpler.lower() != term.lower(), (
                f"Simpler '{simpler}' is same as term '{term}'"
            )
