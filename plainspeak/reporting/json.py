"""The machine-readable report.

This is the contract the CLI and, later, the MCP server both answer with,
so its shape is sealed by the characterisation suite.
"""

import json
from typing import Any, Optional

from ..core.barriers import SimplificationResult
from ..core.metrics import ReadabilityScores


def generate_json(
    readability: ReadabilityScores,
    simplification: Optional[SimplificationResult] = None,
    original_text: str = "",
) -> str:
    """
    Generate a JSON report for machine readability.

    Args:
        readability: ReadabilityScores from analyzer.analyze().
        simplification: Optional SimplificationResult.
        original_text: The original text analyzed.

    Returns:
        A JSON string (indented for readability).
    """
    from .. import __version__

    output: dict[str, Any] = {
        "tool": "PlainSpeak",
        "version": __version__,
        "statistics": {
            "total_words": readability.total_words,
            "total_sentences": readability.total_sentences,
            "total_syllables": readability.total_syllables,
            "total_complex_words": readability.total_complex_words,
            "total_long_words": readability.total_long_words,
            "avg_sentence_length": round(readability.avg_sentence_length, 2),
            "avg_word_length": round(readability.avg_word_length, 2),
            "avg_syllables_per_word": round(readability.avg_syllables_per_word, 2),
        },
        "readability_scores": {
            "flesch_reading_ease": (
                round(readability.flesch_reading_ease, 1)
                if readability.flesch_reading_ease is not None
                else None
            ),
            "flesch_kincaid_grade": (
                round(readability.flesch_kincaid_grade, 1)
                if readability.flesch_kincaid_grade is not None
                else None
            ),
            "gunning_fog_index": (
                round(readability.gunning_fog_index, 1)
                if readability.gunning_fog_index is not None
                else None
            ),
            "smog_index": (
                round(readability.smog_index, 1)
                if readability.smog_index is not None
                else None
            ),
            "automated_readability_index": (
                round(readability.automated_readability_index, 1)
                if readability.automated_readability_index is not None
                else None
            ),
            "coleman_liau_index": (
                round(readability.coleman_liau_index, 1)
                if readability.coleman_liau_index is not None
                else None
            ),
        },
        "consensus": {
            "grade_level": (
                round(readability.consensus_grade_level, 1)
                if readability.consensus_grade_level is not None
                else None
            ),
            "description": readability.reading_level_description,
        },
    }

    if simplification:
        output["simplification"] = {
            "total_barriers": simplification.total_barriers,
            "critical_count": simplification.critical_count,
            "warning_count": simplification.warning_count,
            "info_count": simplification.info_count,
            "summary": simplification.summary,
            "barriers": [
                {
                    "type": b.barrier_type,
                    "severity": b.severity,
                    "sentence_index": b.sentence_index,
                    "matched_text": b.matched_text,
                    "suggestion": b.suggestion,
                    "explanation": b.explanation,
                    "sentence_context": (
                        b.sentence_text[:200] + "..."
                        if len(b.sentence_text) > 200
                        else b.sentence_text
                    ),
                }
                for b in simplification.barriers
            ],
        }

    if original_text:
        # Truncate for JSON output
        if len(original_text) > 5000:
            output["text_preview"] = original_text[:5000] + "... [truncated]"
        else:
            output["text_preview"] = original_text

    return json.dumps(output, indent=2, ensure_ascii=False)
