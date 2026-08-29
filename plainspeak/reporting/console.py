"""The terminal report."""

from typing import Optional

from ..core.barriers import SimplificationResult
from ..core.metrics import ReadabilityScores, describe_flesch_score
from .labels import _barrier_type_label


def format_console_report(
    readability: ReadabilityScores,
    simplification: Optional[SimplificationResult] = None,
) -> str:
    """
    Generate a plain-text console-friendly report.

    Args:
        readability: ReadabilityScores from analyzer.analyze().
        simplification: Optional SimplificationResult.

    Returns:
        A formatted string for terminal output.
    """
    lines: list[str] = []

    lines.append("=" * 60)
    lines.append("  PlainSpeak Readability Report")
    lines.append("=" * 60)
    lines.append("")

    # Consensus
    if readability.consensus_grade_level is not None:
        lines.append(
            f"  Consensus Grade Level: {readability.consensus_grade_level:.1f}"
        )
        lines.append(f"  {readability.reading_level_description}")
        lines.append("")

    # Stats
    lines.append("  Text Statistics:")
    lines.append(f"    Words:               {readability.total_words}")
    lines.append(f"    Sentences:           {readability.total_sentences}")
    lines.append(f"    Avg Sentence Length:  {readability.avg_sentence_length:.1f} words")
    lines.append(f"    Avg Word Length:      {readability.avg_word_length:.1f} characters")
    lines.append(f"    Complex Words (3+ syl): {readability.total_complex_words}")
    lines.append("")

    # Scores
    lines.append("  Readability Scores:")
    if readability.flesch_reading_ease is not None:
        lines.append(
            f"    Flesch Reading Ease:        {readability.flesch_reading_ease:.1f}"
        )
        lines.append(
            f"      {describe_flesch_score(readability.flesch_reading_ease)}"
        )
    if readability.flesch_kincaid_grade is not None:
        lines.append(
            f"    Flesch-Kincaid Grade Level:  {readability.flesch_kincaid_grade:.1f}"
        )
    if readability.gunning_fog_index is not None:
        lines.append(
            f"    Gunning Fog Index:           {readability.gunning_fog_index:.1f}"
        )
    if readability.smog_index is not None:
        lines.append(
            f"    SMOG Index:                  {readability.smog_index:.1f}"
        )
    if readability.automated_readability_index is not None:
        lines.append(
            f"    Automated Readability Index: {readability.automated_readability_index:.1f}"
        )
    if readability.coleman_liau_index is not None:
        lines.append(
            f"    Coleman-Liau Index:          {readability.coleman_liau_index:.1f}"
        )
    lines.append("")

    # Issues summary
    if simplification:
        lines.append(f"  {simplification.summary}")
        lines.append("")
        if simplification.barriers:
            lines.append("  Top issues:")
            shown = 0
            for barrier in simplification.barriers:
                if shown >= 10:
                    break
                lines.append(
                    f"    [{barrier.severity.upper()}] {_barrier_type_label(barrier.barrier_type)}: "
                    f'"{barrier.matched_text[:60]}"'
                )
                if barrier.suggestion:
                    lines.append(f"           -> {barrier.suggestion[:100]}")
                shown += 1
            remaining = len(simplification.barriers) - shown
            if remaining > 0:
                lines.append(f"    ... and {remaining} more issue(s).")
            lines.append("")

    lines.append("  " + "—" * 56)
    lines.append(
        "  Note: Readability scores are proxies, not direct measures of"
    )
    lines.append(
        "  comprehension. All suggestions should be reviewed by a human."
    )
    lines.append("=" * 60)

    return "\n".join(lines)
