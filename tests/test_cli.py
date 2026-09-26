"""
Tests for the CLI module.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner
from plainspeak.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_file(tmp_path):
    """Create a temporary text file for testing."""
    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "This is a simple test document. "
        "It contains multiple sentences for testing purposes. "
        "The readability of this text should be fairly easy to assess."
    )
    return str(file_path)


class TestCLIAnalyze:
    """Test the `analyze` command."""

    def test_analyze_file(self, runner, sample_file):
        result = runner.invoke(main, ["analyze", sample_file, "--console"])
        assert result.exit_code == 0
        assert "PlainSpeak Readability Report" in result.output
        assert "Flesch Reading Ease" in result.output

    def test_analyze_stdin(self, runner):
        result = runner.invoke(
            main,
            ["analyze", "--stdin", "--console"],
            input="This is a test. It has two sentences.",
        )
        assert result.exit_code == 0
        assert "PlainSpeak" in result.output

    def test_analyze_with_output(self, runner, sample_file, tmp_path):
        output_path = tmp_path / "report.html"
        result = runner.invoke(
            main, ["analyze", sample_file, "--output", str(output_path)]
        )
        assert result.exit_code == 0
        assert output_path.exists()
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content

    def test_analyze_with_json_output(self, runner, sample_file, tmp_path):
        json_path = tmp_path / "report.json"
        result = runner.invoke(
            main, ["analyze", sample_file, "--json", str(json_path)]
        )
        assert result.exit_code == 0
        assert json_path.exists()
        content = json_path.read_text()
        assert '"tool": "PlainSpeak"' in content

    def test_analyze_no_simplify(self, runner, sample_file):
        result = runner.invoke(
            main, ["analyze", sample_file, "--no-simplify", "--console"]
        )
        assert result.exit_code == 0
        # Should still have scores
        assert "Flesch Reading Ease" in result.output

    def test_analyze_missing_file(self, runner):
        result = runner.invoke(main, ["analyze", "nonexistent_file.txt", "--console"])
        assert result.exit_code != 0

    def test_analyze_empty_input(self, runner):
        result = runner.invoke(main, ["analyze", "--stdin"], input="   ")
        assert result.exit_code != 0

    def test_analyze_no_input(self, runner):
        result = runner.invoke(main, ["analyze"])
        assert result.exit_code != 0


class TestCLIScore:
    """Test the `score` command."""

    def test_score_text(self, runner):
        result = runner.invoke(
            main, ["score", "This is a simple test for scoring purposes."]
        )
        assert result.exit_code == 0
        assert "Words:" in result.output
        assert "Flesch Reading Ease:" in result.output
        assert "Consensus Grade:" in result.output

    def test_score_stdin(self, runner):
        result = runner.invoke(
            main, ["score", "--stdin"],
            input="Testing from standard input for quick scoring.",
        )
        assert result.exit_code == 0
        assert "Words:" in result.output

    def test_score_empty(self, runner):
        result = runner.invoke(main, ["score", ""])
        assert result.exit_code != 0


class TestCLISimplify:
    """`simplify` is a deprecated alias for `present --format marked`.

    It once ran the inherited substitution engine directly. That contract is
    superseded: it now runs the governed pipeline, so it needs a profile like
    every other governed command, and it cannot produce what the old engine did.
    """

    def test_simplify_file(self, runner, sample_file):
        result = runner.invoke(main, ["simplify", sample_file, "--profile", "natural"])
        assert result.exit_code == 0
        assert "deprecated" in result.stderr
        assert result.stdout.startswith("This is a simple test document.")

    def test_simplify_stdin_marks_governed_changes(self, runner):
        result = runner.invoke(
            main, ["simplify", "--stdin", "--profile", "natural"],
            input="We will utilize this methodology to implement the provisions.",
        )
        assert result.exit_code == 0
        assert "**use**" in result.stdout

    def test_simplify_no_longer_reaches_the_inherited_engine(self, runner):
        """The two failures that made the old path unacceptable."""
        result = runner.invoke(
            main, ["simplify", "--stdin", "--profile", "natural"],
            input="The system leverages a cache. Staff shall not utilize it.",
        )
        assert result.exit_code == 0
        assert "borrowed money" not in result.stdout
        assert "shall not" in result.stdout

    def test_simplify_with_output(self, runner, sample_file, tmp_path):
        output_path = tmp_path / "simplified.txt"
        result = runner.invoke(
            main, ["simplify", sample_file, "--profile", "natural", "--output", str(output_path)]
        )
        assert result.exit_code == 0
        assert output_path.exists()

    def test_simplify_needs_a_profile(self, runner, sample_file):
        result = runner.invoke(main, ["simplify", sample_file])
        assert result.exit_code == 2

    def test_simplify_no_input(self, runner):
        result = runner.invoke(main, ["simplify", "--profile", "natural"])
        assert result.exit_code != 0


class TestCLIVersion:
    """Test the `version` command."""

    def test_version(self, runner):
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "PlainSpeak" in result.output

    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "PlainSpeak" in result.output


class TestCLIHelp:
    """Test help output."""

    def test_main_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "PlainSpeak" in result.output
        assert "analyze" in result.output
        assert "score" in result.output

    def test_analyze_help(self, runner):
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--json" in result.output
        assert "--no-simplify" in result.output


class TestOneEngine:
    """Every command that rewrites text does it through the governed pipeline."""

    def test_simplify_help_points_at_present(self, runner):
        result = runner.invoke(main, ["simplify", "--help"])
        text = " ".join(result.output.split())
        assert "Deprecated: use `plainspeak present --format marked`" in text
        assert "LEGACY" not in text

    def test_command_list_no_longer_advertises_a_legacy_path(self, runner):
        result = runner.invoke(main, ["--help"])
        assert "LEGACY" not in result.output
        assert "present" in result.output

    def test_web_help_describes_the_governed_presentation(self, runner):
        result = runner.invoke(main, ["web", "--help"])
        text = " ".join(result.output.split())
        assert "governed presentation" in text
