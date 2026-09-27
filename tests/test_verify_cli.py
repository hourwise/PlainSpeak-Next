"""`plainspeak verify` on the command line: output, receipts and exit status.

The exit status is part of the interface. CI reads it, so every outcome has its
own code and only ACCEPTED is zero.
"""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from plainspeak.adapters.cli import (
    EXIT_ACCEPTED,
    EXIT_INCONCLUSIVE,
    EXIT_INPUT_ERROR,
    EXIT_INTERNAL_ERROR,
    EXIT_REFUSED,
    EXIT_USAGE,
    main,
)

BEFORE = "You must pay £40 before 5pm.\n\nIn order to finish, utilize the portal.\n"


@pytest.fixture
def files(tmp_path):
    def write(name: str, text: str):
        path = tmp_path / name
        path.write_bytes(text.encode("utf-8"))
        return str(path)

    return write


def run(*arguments):
    return CliRunner().invoke(main, ["verify", *arguments])


@pytest.mark.parametrize(
    "after,expected,word",
    [
        ("You must pay £40 before 5pm.\n\nTo finish, use the portal.\n", EXIT_ACCEPTED, "ACCEPTED"),
        ("You should pay £40 before 5pm.\n\nTo finish, use the portal.\n", EXIT_REFUSED, "REFUSED"),
        ("You must pay £40 before 5pm.\n\nTo finish, use our shiny portal.\n", EXIT_INCONCLUSIVE,
         "INCONCLUSIVE"),
    ],
)
def test_each_result_has_its_own_exit_status(files, after, expected, word):
    result = run(files("before.md", BEFORE), files("after.md", after))
    assert result.exit_code == expected, result.output
    assert result.output.startswith(f"PlainSpeak verify — {word}")
    assert "does not establish that two texts mean the same thing" in result.output


def test_json_is_the_contract(files):
    result = run(files("before.md", BEFORE), files("after.md", BEFORE), "--format", "json")
    assert result.exit_code == EXIT_ACCEPTED
    data = json.loads(result.output)
    assert data["schema"] == "plainspeak.verify.v1"
    assert data["result"] == "ACCEPTED"


def test_the_receipt_file_matches_the_result(files, tmp_path):
    receipt = tmp_path / "receipt.json"
    result = run(files("before.md", BEFORE), files("after.md", BEFORE.replace("£40", "£45")),
                 "--format", "json", "--receipt", str(receipt))
    assert result.exit_code == EXIT_REFUSED
    written = json.loads(receipt.read_text(encoding="utf-8"))
    assert written == json.loads(result.output)["receipt"]
    assert written["payload"]["result"] == "REFUSED"


def test_input_errors_are_not_results(files, tmp_path):
    before = files("before.md", BEFORE)
    missing = run(before, str(tmp_path / "missing.md"), "--format", "json")
    assert missing.exit_code == EXIT_INPUT_ERROR
    assert json.loads(missing.stdout)["error"]["code"] == "unreadable_input"

    unsupported = run(files("before.pdf", "x"), before)
    assert unsupported.exit_code == EXIT_INPUT_ERROR

    empty = run(files("empty.md", "  \n"), before)
    assert empty.exit_code == EXIT_INPUT_ERROR


def test_an_internal_failure_is_not_a_result(files, monkeypatch):
    import plainspeak.adapters.cli as cli

    def explode(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "verify_files", explode)
    result = run(files("before.md", BEFORE), files("after.md", BEFORE))
    assert result.exit_code == EXIT_INTERNAL_ERROR


def test_an_input_is_never_overwritten(files):
    before = files("before.md", BEFORE)
    after = files("after.md", BEFORE)
    for flag in ("--output", "--receipt"):
        result = run(before, after, flag, after)
        assert result.exit_code == EXIT_USAGE
    assert open(after, encoding="utf-8").read() == BEFORE


def test_output_refuses_to_replace_a_file_without_overwrite(files, tmp_path):
    target = tmp_path / "result.txt"
    target.write_text("keep", encoding="utf-8")
    result = run(files("before.md", BEFORE), files("after.md", BEFORE), "--output", str(target))
    assert result.exit_code == EXIT_USAGE
    assert target.read_text(encoding="utf-8") == "keep"
    again = run(files("before.md", BEFORE), files("after.md", BEFORE), "--output", str(target),
                "--overwrite")
    assert again.exit_code == EXIT_ACCEPTED
    assert target.read_text(encoding="utf-8").startswith("PlainSpeak verify — ACCEPTED")


def test_input_format_overrides_the_extension(files):
    before = files("before.md", "Pay £5.\n")
    after = files("after.md", "Pay £5.\n")
    result = run(before, after, "--input-format", "text", "--format", "json")
    assert json.loads(result.output)["input_format"] == "text"


def test_verify_md_documents_the_exit_statuses_the_cli_uses():
    """The page a CI author reads and the code a CI job runs must agree."""
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "VERIFY.md").read_text(encoding="utf-8")
    assert f"| `ACCEPTED` |" in page and f"| {EXIT_ACCEPTED} |" in page
    assert f"| {EXIT_REFUSED} |" in page and f"| {EXIT_INCONCLUSIVE} |" in page
    for status, meaning in ((EXIT_USAGE, "invalid usage"), (EXIT_INPUT_ERROR, "the inputs could not be verified"),
                            (EXIT_INTERNAL_ERROR, "internal error")):
        assert f"**{status}** {meaning}" in page, (status, meaning)
