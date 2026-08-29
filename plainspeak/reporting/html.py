"""The self-contained HTML report."""

from datetime import datetime
from typing import Optional

from ..core.barriers import SimplificationResult
from ..core.metrics import ReadabilityScores, describe_flesch_score
from .labels import _barrier_type_label, _escape, _pct


# ── HTML template ───────────────────────────────────────────────────────────

def _build_html_template() -> str:
    """Build the HTML template string (avoiding format-string issues with CSS braces)."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PlainSpeak Readability Report</title>
<style>
/* ── Base styles (WCAG 2.1 AA compliant) ── */
:root """ + """{
  --text: #1a1a1a;
  --bg: #ffffff;
  --accent: #2563eb;
  --warning: #92400e;
  --critical: #991b1b;
  --info: #1e40af;
  --border: #d4d4d4;
  --surface: #f8fafc;
  --surface-warning: #fffbeb;
  --surface-critical: #fef2f2;
  --surface-info: #eff6ff;
  --font: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --mono: 'Courier New', Courier, monospace;
  --line-height: 1.6;
}

* """ + """{ box-sizing: border-box; margin: 0; padding: 0; }

body """ + """{
  font-family: var(--font);
  font-size: 1rem;
  line-height: var(--line-height);
  color: var(--text);
  background: var(--bg);
  max-width: 48rem;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}

h1 """ + """{ font-size: 1.75rem; margin: 1.5rem 0 0.75rem; font-weight: 700; }
h2 """ + """{ font-size: 1.375rem; margin: 1.75rem 0 0.5rem; font-weight: 600; border-bottom: 2px solid var(--border); padding-bottom: 0.25rem; }
h3 """ + """{ font-size: 1.125rem; margin: 1.25rem 0 0.5rem; font-weight: 600; }
p """ + """{ margin: 0.75rem 0; }
a """ + """{ color: var(--accent); text-decoration: underline; }
a:focus """ + """{ outline: 3px solid var(--accent); outline-offset: 2px; }

.skip-link """ + """{
  position: absolute;
  top: -100px;
  left: 0;
  background: var(--accent);
  color: white;
  padding: 0.5rem 1rem;
  z-index: 100;
}
.skip-link:focus """ + """{ top: 0; }

.score-grid """ + """{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}

.score-card """ + """{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 1rem;
}

.score-card dt """ + """{
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #666;
  margin-bottom: 0.25rem;
}

.score-card dd """ + """{
  font-size: 1.5rem;
  font-weight: 700;
  font-family: var(--mono);
}

.score-card .label """ + """{
  font-size: 0.8rem;
  color: #666;
  margin-top: 0.25rem;
  font-weight: 400;
  font-family: var(--font);
}

.consensus-banner """ + """{
  background: var(--surface);
  border: 2px solid var(--accent);
  border-radius: 0.5rem;
  padding: 1.25rem;
  margin: 1.5rem 0;
}

.consensus-banner .grade """ + """{
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--accent);
  font-family: var(--mono);
}

.consensus-banner .description """ + """{
  font-size: 1.1rem;
  margin-top: 0.5rem;
}

.issue-list """ + """{ list-style: none; margin: 1rem 0; }

.issue-item """ + """{
  padding: 0.75rem 1rem;
  margin: 0.5rem 0;
  border-radius: 0.375rem;
  border-left: 4px solid var(--border);
}

.issue-item.critical """ + """{
  background: var(--surface-critical);
  border-left-color: var(--critical);
}

.issue-item.warning """ + """{
  background: var(--surface-warning);
  border-left-color: var(--warning);
}

.issue-item.info """ + """{
  background: var(--surface-info);
  border-left-color: var(--info);
}

.issue-badge """ + """{
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  margin-right: 0.5rem;
}

.issue-badge.critical """ + """{ background: var(--critical); color: white; }
.issue-badge.warning """ + """{ background: var(--warning); color: white; }
.issue-badge.info """ + """{ background: var(--info); color: white; }

.issue-type """ + """{
  font-weight: 600;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #555;
}

.issue-quote """ + """{
  font-family: var(--mono);
  font-size: 0.9rem;
  background: rgba(0,0,0,0.04);
  padding: 0.5rem 0.75rem;
  border-radius: 0.25rem;
  margin: 0.5rem 0;
  word-break: break-word;
}

.issue-suggestion """ + """{
  margin: 0.25rem 0;
  padding: 0.25rem 0;
}

.issue-explanation """ + """{
  font-size: 0.875rem;
  color: #555;
  margin-top: 0.25rem;
}

.stats-table """ + """{
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
}

.stats-table caption """ + """{
  font-weight: 600;
  text-align: left;
  margin-bottom: 0.5rem;
}

.stats-table th """ + """{
  text-align: left;
  padding: 0.5rem 0.75rem;
  background: var(--surface);
  border-bottom: 2px solid var(--border);
  font-weight: 600;
}

.stats-table td """ + """{
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
}

footer """ + """{
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.8rem;
  color: #888;
}

.warning-note """ + """{
  background: var(--surface-warning);
  border: 1px solid var(--warning);
  border-radius: 0.375rem;
  padding: 1rem;
  margin: 1.5rem 0;
  font-size: 0.9rem;
}

.warning-note strong """ + """{ color: var(--warning); }

@media (max-width: 600px) """ + """{
  body """ + """{ padding: 1rem 0.75rem 2rem; }
  .score-grid """ + """{ grid-template-columns: 1fr; }
  .consensus-banner .grade """ + """{ font-size: 2rem; }
}

@media print """ + """{
  body """ + """{ max-width: none; }
  .issue-item """ + """{ break-inside: avoid; }
}
</style>
</head>
<body>

<a href="#main-content" class="skip-link">Skip to main content</a>

<header>
  <h1>PlainSpeak Readability Report</h1>
  <p>
    <time datetime="__TIMESTAMP_ISO__">__TIMESTAMP_DISPLAY__</time>
    &mdash; Generated by PlainSpeak __VERSION__
  </p>
</header>

<main id="main-content">
__CONTENT__
</main>

<footer>
  <p>
    PlainSpeak is an open-source readability toolkit. This report is
    generated from automated analysis of surface text features.
    Readability scores are proxies, not direct measures of human
    comprehension. All suggestions should be reviewed by a human
    before applying.
  </p>
  <p>PlainSpeak __VERSION__ &mdash; <a href="https://github.com/hourwise/Project-PlainSpeak">github.com/hourwise/Project-PlainSpeak</a></p>
</footer>

</body>
</html>"""


def generate_report(
    readability: ReadabilityScores,
    simplification: Optional[SimplificationResult] = None,
    original_text: str = "",
) -> str:
    """
    Generate a complete, self-contained HTML report.

    Args:
        readability: ReadabilityScores from analyzer.analyze().
        simplification: Optional SimplificationResult from simplifier.
        original_text: The original text (for the text preview section).

    Returns:
        A complete HTML document as a string.
    """
    from .. import __version__

    from datetime import timezone
    now = datetime.now(timezone.utc)
    timestamp_iso = now.isoformat()
    timestamp_display = now.strftime("%Y-%m-%d %H:%M UTC")

    parts: list[str] = []

    # ── Summary section ──
    parts.append('<section aria-labelledby="summary-heading">')
    parts.append(f'<h2 id="summary-heading">Summary</h2>')

    # Consensus grade
    if readability.consensus_grade_level is not None:
        parts.append('<div class="consensus-banner" role="alert" aria-live="polite">')
        parts.append(
            f'<div class="grade">Grade {readability.consensus_grade_level:.1f}</div>'
        )
        parts.append(
            f'<div class="description">{_escape(readability.reading_level_description)}</div>'
        )
        parts.append('</div>')

    # Overview stats
    parts.append('<div class="score-grid">')

    stats = [
        ("Words", str(readability.total_words)),
        ("Sentences", str(readability.total_sentences)),
        (
            "Avg. Sentence Length",
            f"{readability.avg_sentence_length:.1f} words",
        ),
        (
            "Avg. Word Length",
            f"{readability.avg_word_length:.1f} chars",
        ),
        (
            "Complex Words",
            f"{readability.total_complex_words} ({_pct(readability.total_complex_words, readability.total_words)}%)",
        ),
        (
            "Long Words (7+ chars)",
            f"{readability.total_long_words} ({_pct(readability.total_long_words, readability.total_words)}%)",
        ),
    ]

    for label, value in stats:
        parts.append('<dl class="score-card">')
        parts.append(f'<dt>{_escape(label)}</dt>')
        parts.append(f'<dd>{_escape(value)}</dd>')
        parts.append('</dl>')

    parts.append('</div>')
    parts.append('</section>')

    # ── Readability scores section ──
    parts.append('<section aria-labelledby="scores-heading">')
    parts.append(f'<h2 id="scores-heading">Readability Scores</h2>')

    metrics = [
        (
            "Flesch Reading Ease",
            f"{readability.flesch_reading_ease:.1f}" if readability.flesch_reading_ease is not None else "N/A",
            describe_flesch_score(readability.flesch_reading_ease) if readability.flesch_reading_ease is not None else "",
        ),
        (
            "Flesch-Kincaid Grade Level",
            f"{readability.flesch_kincaid_grade:.1f}" if readability.flesch_kincaid_grade is not None else "N/A",
            "US school grade level equivalent",
        ),
        (
            "Gunning Fog Index",
            f"{readability.gunning_fog_index:.1f}" if readability.gunning_fog_index is not None else "N/A",
            "Years of formal education needed to understand the text",
        ),
        (
            "SMOG Index",
            f"{readability.smog_index:.1f}" if readability.smog_index is not None else "N/A",
            "Simplified Measure of Gobbledygook — years of education needed",
        ),
        (
            "Automated Readability Index",
            f"{readability.automated_readability_index:.1f}" if readability.automated_readability_index is not None else "N/A",
            "Based on characters per word and words per sentence",
        ),
        (
            "Coleman-Liau Index",
            f"{readability.coleman_liau_index:.1f}" if readability.coleman_liau_index is not None else "N/A",
            "Based on characters instead of syllables",
        ),
    ]

    parts.append('<div class="score-grid">')
    for name, value, note in metrics:
        parts.append('<dl class="score-card">')
        parts.append(f'<dt>{_escape(name)}</dt>')
        parts.append(f'<dd>{_escape(value)}</dd>')
        if note:
            parts.append(f'<div class="label">{_escape(note)}</div>')
        parts.append('</dl>')
    parts.append('</div>')

    # Warning about grade level interpretation
    parts.append('<div class="warning-note">')
    parts.append(
        '<strong>&#9888; Important:</strong> Readability scores measure '
        'surface features of text (word length, sentence length). They do '
        'not measure clarity, accuracy, organisation, or whether the content '
        'is appropriate for the reader. A text with a low grade level can '
        'still be confusing. A text with a high grade level can still be clear. '
        'Use these scores as a starting point, not a final judgement.'
    )
    parts.append('</div>')
    parts.append('</section>')

    # ── Simplification issues section ──
    if simplification and simplification.barriers:
        parts.append('<section aria-labelledby="issues-heading">')
        parts.append(f'<h2 id="issues-heading">Readability Issues</h2>')
        parts.append(f'<p>{_escape(simplification.summary)}</p>')

        parts.append('<ol class="issue-list" aria-label="List of readability issues">')

        for i, barrier in enumerate(simplification.barriers):
            severity_class = barrier.severity
            badge = barrier.severity.upper()
            type_label = _barrier_type_label(barrier.barrier_type)

            parts.append(
                f'<li class="issue-item {severity_class}" '
                f'aria-label="Issue {i + 1}: {type_label}, severity {badge}">'
            )

            parts.append(
                f'<span class="issue-badge {severity_class}">{_escape(badge)}</span>'
            )
            parts.append(f'<span class="issue-type">{_escape(type_label)}</span>')

            if barrier.matched_text:
                parts.append(
                    f'<div class="issue-quote">'
                    f'&ldquo;{_escape(barrier.matched_text)}&rdquo;'
                    f'</div>'
                )

            if barrier.suggestion:
                parts.append(
                    f'<p class="issue-suggestion">'
                    f'<strong>Suggestion:</strong> {_escape(barrier.suggestion)}'
                    f'</p>'
                )

            if barrier.explanation:
                parts.append(
                    f'<p class="issue-explanation">{_escape(barrier.explanation)}</p>'
                )

            # Show sentence context
            sentence_preview = barrier.sentence_text
            if len(sentence_preview) > 200:
                sentence_preview = sentence_preview[:200] + "..."
            parts.append(
                f'<p class="issue-explanation">'
                f'<small>Sentence {barrier.sentence_index + 1}: '
                f'&ldquo;{_escape(sentence_preview)}&rdquo;</small>'
                f'</p>'
            )

            parts.append('</li>')

        parts.append('</ol>')
        parts.append('</section>')
    elif simplification:
        parts.append('<section aria-labelledby="issues-heading">')
        parts.append(f'<h2 id="issues-heading">Readability Issues</h2>')
        parts.append(f'<p>{_escape(simplification.summary)}</p>')
        parts.append('</section>')

    # ── Text preview section ──
    if original_text:
        parts.append('<section aria-labelledby="text-preview-heading">')
        parts.append(f'<h2 id="text-preview-heading">Analyzed Text</h2>')
        preview = original_text
        if len(preview) > 2000:
            preview = preview[:2000] + "\n\n[... text truncated for report ...]"
        parts.append(
            f'<pre style="white-space: pre-wrap; font-family: var(--mono); '
            f'font-size: 0.875rem; background: var(--surface); '
            f'padding: 1rem; border-radius: 0.375rem; '
            f'max-height: 20rem; overflow-y: auto;" '
            f'aria-label="Full analyzed text">'
            f'{_escape(preview)}'
            f'</pre>'
        )
        parts.append('</section>')

    # ── About PlainSpeak section ──
    parts.append('<section aria-labelledby="about-heading">')
    parts.append(f'<h2 id="about-heading">About This Report</h2>')
    parts.append(
        '<p>This report was generated by <strong>PlainSpeak</strong>, '
        'an open-source readability analysis toolkit. PlainSpeak operates '
        'entirely offline — no text is sent anywhere, and no data is collected.</p>'
    )
    parts.append(
        '<p>The analysis uses established readability formulas '
        '(Flesch-Kincaid, Gunning Fog, SMOG, ARI, Coleman-Liau) and '
        'pattern-based detection of readability barriers. '
        'All suggestions are advisory and should be reviewed by a human '
        'before applying changes to text.</p>'
    )
    parts.append('</section>')

    content = "\n".join(parts)

    template = _build_html_template()
    html_output = template.replace("__TIMESTAMP_ISO__", timestamp_iso)
    html_output = html_output.replace("__TIMESTAMP_DISPLAY__", timestamp_display)
    html_output = html_output.replace("__VERSION__", __version__)
    html_output = html_output.replace("__CONTENT__", content)

    return html_output
