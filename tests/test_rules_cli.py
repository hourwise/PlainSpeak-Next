"""The `plainspeak rules` commands.

These are deliberately thin. They list and explain; they do not match, resolve
or apply. Exposing a destructive `fix` through the public CLI can wait until the
engine has been used in anger — the tests drive the pipeline directly in the
meantime, which is where the real coverage is.

What is worth testing here is that the adapter stays an adapter: the same rule
metadata, rendered, with no decisions of its own.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from plainspeak.adapters.cli import main
from plainspeak.rules import load_ruleset


@pytest.fixture
def run():
    runner = CliRunner()

    def invoke(*args: str):
        return runner.invoke(main, list(args))

    return invoke


def test_rules_list_shows_every_rule(run, bundled) -> None:
    result = run("rules", "list")

    assert result.exit_code == 0
    assert f"{len(bundled)} of {len(bundled)} rules" in result.output
    for rule in bundled.rules:
        assert rule.id in result.output


def test_rules_list_names_the_ruleset_identity(run, bundled) -> None:
    """A reader should be able to tell which rules produced a report."""
    result = run("rules", "list")
    assert bundled.version in result.output
    assert bundled.hash[:12] in result.output


@pytest.mark.parametrize("mode", ["safe-fix", "diagnostic", "protected"])
def test_rules_list_can_filter_by_mode(run, bundled, mode: str) -> None:
    result = run("rules", "list", "--mode", mode)
    expected = [rule for rule in bundled.rules if rule.mode == mode]

    assert result.exit_code == 0
    assert f"{len(expected)} of {len(bundled)} rules" in result.output
    for rule in expected:
        assert rule.id in result.output
    for rule in bundled.rules:
        if rule.mode != mode:
            assert rule.id not in result.output


def test_rules_explain_shows_the_whole_rule(run) -> None:
    result = run("rules", "explain", "PS.CLARITY.001")

    assert result.exit_code == 0
    for expected in ("PS.CLARITY.001", "safe-fix", "clarity", "in order to",
                     "Should match:", "Should not match:", "Produces:",
                     "project-authored"):
        assert expected in result.output


def test_rules_explain_accepts_a_lower_case_id(run) -> None:
    assert run("rules", "explain", "ps.clarity.001").exit_code == 0


def test_rules_explain_on_an_unknown_id_fails_helpfully(run) -> None:
    result = run("rules", "explain", "PS.NOSUCH.999")

    assert result.exit_code != 0
    assert "No rule with ID" in result.output
    assert "rules list" in result.output, "the error should say how to find the right ID"


def test_a_diagnostic_says_it_proposes_nothing(run) -> None:
    result = run("rules", "explain", "PS.VOICE.001")
    assert "reports only" in result.output
    assert "Produces:" not in result.output


def test_the_cli_exposes_only_read_only_rule_commands() -> None:
    """Deliberate: the rule engine is new and a `fix` command would edit files.

    Checked against the registered command names rather than the help text —
    the group's own docstring explains why applying is absent, so searching the
    prose for "apply" finds the explanation rather than a command.
    """
    from plainspeak.adapters.cli import rules

    assert set(rules.commands) == {"list", "explain"}
