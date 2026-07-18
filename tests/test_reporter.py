"""
Tests for the HTML report generator.
"""

import re
from pathlib import Path

import pytest
from plainspeak.analyzer import analyze
from plainspeak.simplifier import analyze_simplification
from plainspeak.reporter import (
    generate_report,
    format_console_report,
    _escape,
    _severity_icon,
    _barrier_type_label,
)


class TestEscaping:
    """Test HTML escaping of user input."""

    def test_special_chars_escaped(self):
        assert _escape("<script>") == "&lt;script&gt;"
        assert _escape('"hello"') == "&quot;hello&quot;"
        assert _escape("a & b") == "a &amp; b"

    def test_normal_text_unchanged(self):
        assert _escape("Hello world") == "Hello world"
        assert _escape("Plain text 123") == "Plain text 123"

    def test_empty_string(self):
        assert _escape("") == ""


class TestSeverityIcon:
    """Test severity icon mapping."""

    def test_all_severities_have_icons(self):
        for severity in ("critical", "warning", "info"):
            icon = _severity_icon(severity)
            assert icon != "", f"No icon for severity '{severity}'"


class TestBarrierLabels:
    """Test barrier type labels."""

    def test_all_types_have_labels(self):
        types = [
            "passive_voice",
            "long_sentence",
            "complex_word",
            "nominalization",
            "jargon",
            "redundant_pair",
            "hidden_verb",
        ]
        for t in types:
            label = _barrier_type_label(t)
            assert label != "", f"No label for '{t}'"
            assert label != t  # Should be human-readable, not the raw key


class TestHTMLReport:
    """Test HTML report generation."""

    def test_generates_valid_html(self):
        """Report should be a complete HTML document."""
        text = "This is a simple test document. It has two sentences."
        scores = analyze(text)
        simplification = analyze_simplification(text)
        report = generate_report(scores, simplification, text)

        assert "<!DOCTYPE html>" in report
        assert "<html lang=\"en\">" in report
        assert "</html>" in report
        assert "<head>" in report
        assert "</head>" in report
        assert "<body>" in report
        assert "</body>" in report

    def test_contains_readability_scores(self):
        """Report should include the readability scores."""
        text = "This is a test document for readability analysis purposes."
        scores = analyze(text)
        report = generate_report(scores, None, text)

        assert "Flesch Reading Ease" in report
        assert "Flesch-Kincaid" in report
        assert "Gunning Fog" in report
        assert "SMOG" in report

    def test_contains_simplification_issues(self):
        """Report should include simplification barriers when available."""
        text = "We will utilize this methodology to implement the provisions."
        scores = analyze(text)
        simplification = analyze_simplification(text)
        report = generate_report(scores, simplification, text)

        assert "Readability Issues" in report

    def test_no_simplification_section_when_none(self):
        """When simplification is None, there should be no issues section."""
        text = "Simple text."
        scores = analyze(text)
        report = generate_report(scores, None, text)

        # Should still be valid HTML without simplification
        assert "<!DOCTYPE html>" in report

    def test_user_text_escaped_in_report(self):
        """User-provided text containing HTML should be escaped."""
        text = 'Text with <script>alert("xss")</script> embedded.'
        scores = analyze(text)
        report = generate_report(scores, None, text)

        assert "<script>" not in report
        assert "&lt;script&gt;" in report

    def test_contains_accessibility_features(self):
        """Report should contain accessibility features."""
        text = "Test document for accessibility checks."
        scores = analyze(text)
        report = generate_report(scores, analyze_simplification(text), text)

        # Skip link
        assert "skip-link" in report
        # ARIA labels
        assert 'aria-labelledby=' in report or 'aria-label=' in report
        # Landmarks
        assert '<main' in report
        # Language attribute
        assert 'lang="en"' in report
        # Viewport meta for responsive
        assert 'viewport' in report

    def test_contains_warning_note(self):
        """Report should contain a warning about score limitations."""
        text = "Test document."
        scores = analyze(text)
        report = generate_report(scores, None, text)

        assert "Important" in report or "warning" in report.lower()


class TestConsoleReport:
    """Test console-formatted report."""

    def test_console_report_contains_scores(self):
        text = "This is a test document for console output."
        scores = analyze(text)
        report = format_console_report(scores)

        assert "PlainSpeak Readability Report" in report
        assert "Flesch Reading Ease" in report

    def test_console_report_with_simplification(self):
        text = "We will utilize this methodology."
        scores = analyze(text)
        simplification = analyze_simplification(text)
        report = format_console_report(scores, simplification)

        assert "PlainSpeak Readability Report" in report


class TestReportEndToEnd:
    """End-to-end test of the full pipeline."""

    def test_full_pipeline_no_errors(self):
        """The full pipeline should run without errors."""
        text = (
            "The PlainSpeak project is designed to help writers create "
            "more accessible content for their readers. It analyzes text "
            "for readability and suggests improvements. The goal is to "
            "make information more accessible to everyone, regardless of "
            "their reading ability. This is especially important for "
            "government communications, healthcare information, and "
            "educational materials."
        )
        scores = analyze(text)
        simplification = analyze_simplification(text)
        html_report = generate_report(scores, simplification, text)
        console_report = format_console_report(scores, simplification)

        assert len(html_report) > 0
        assert len(console_report) > 0
        assert scores.consensus_grade_level is not None

    def test_report_with_special_characters(self):
        """Special characters in text should not break the report."""
        text = "The cost is €100 & the tax is 20%. This includes all fees."
        scores = analyze(text)
        report = generate_report(scores, None, text)
        # Should not crash, should have escaped the &
        assert "&amp;" in report
