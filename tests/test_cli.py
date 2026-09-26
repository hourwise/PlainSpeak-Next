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
    """Test the `simplify` command."""

    def test_simplify_file(self, runner, sample_file):
        result = runner.invoke(main, ["simplify", sample_file])
        assert result.exit_code == 0
        assert "Made" in result.output
        assert "substitution" in result.output

    def test_simplify_stdin(self, runner):
        result = runner.invoke(
            main, ["simplify", "--stdin"],
            input="We will utilize this methodology to implement the provisions.",
        )
        assert result.exit_code == 0
        # Should have replaced "utilize" and "implement" and "provisions"
        assert "substitution" in result.output

    def test_simplify_with_output(self, runner, sample_file, tmp_path):
        output_path = tmp_path / "simplified.txt"
        result = runner.invoke(
            main, ["simplify", sample_file, "--output", str(output_path)]
        )
        assert result.exit_code == 0
        assert output_path.exists()

    def test_simplify_no_input(self, runner):
        result = runner.invoke(main, ["simplify"])
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


class TestLegacyPathsAreLabelled:
    """`simplify` and `web` bypass the governed pipeline, and must say so.

    They predate the declarative rules, the integrity firewall and review, so a
    person meeting them anywhere should be told they carry none of PlainSpeak
    Next's guarantees. The label is asserted rather than trusted, because the
    likeliest way to lose it is an unrelated edit to a docstring.
    """

    @pytest.mark.parametrize("command", ["simplify", "web"])
    def test_command_list_labels_it(self, runner, command):
        result = runner.invoke(main, ["--help"])
        line = next(l for l in result.output.splitlines() if l.strip().startswith(command))
        assert "LEGACY, UNGUARDED" in line

    @pytest.mark.parametrize("command", ["simplify", "web"])
    def test_own_help_labels_it(self, runner, command):
        result = runner.invoke(main, [command, "--help"])
        assert result.exit_code == 0
        # Click re-wraps help to the terminal width, so compare word runs.
        text = " ".join(result.output.split())
        assert "LEGACY, UNGUARDED" in text
        assert "integrity firewall" in text

    def test_simplify_warns_on_stderr_and_leaves_stdout_alone(self, runner, sample_file):
        result = runner.invoke(main, ["simplify", sample_file])
        assert result.exit_code == 0
        assert "legacy, unguarded" in result.stderr
        assert "legacy" not in result.stdout.lower()
        assert result.stdout.startswith("Made ")

    def test_the_web_page_labels_its_simplified_text(self):
        from plainspeak.adapters import web

        source = Path(web.__file__).read_text(encoding="utf-8")
        assert "Legacy, unguarded." in source
