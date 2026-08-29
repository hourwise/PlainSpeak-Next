"""Applying vocabulary substitutions to text.

The only transformation the inherited engine performs. It is mechanical
word and phrase replacement with no understanding of grammar or meaning,
which is precisely why its output is marked up for review rather than
presented as a finished rewrite.
"""

import re

from .glossary import GLOSSARY, SIMPLE_WORD_MAP
from .lexicon import stem_word


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
