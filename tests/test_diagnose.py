"""`diagnose`: everything `present` observes, applied to nothing.

Built from the same review bundle as `present`, so the two must agree about
every item; these tests hold them to it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from plainspeak.adapters.cli import main
from plainspeak.pipeline import DIAGNOSE_SCHEMA, PresentError, diagnose_text, present_text

CORPUS = Path(__file__).resolve().parent / "acceptance" / "corpus"
TEXT = "In order to finish, you must utilize the new portal prior to 30 June 2027.\n"


def test_the_contract():
    data = json.loads(diagnose_text(TEXT, "natural").to_json())
    assert data["schema"] == DIAGNOSE_SCHEMA
    assert data["status"] == "ok"
    for key in ("profile", "input", "engine", "counts", "safe", "review", "refused", "protected",
                "diagnostics", "style_coverage", "readability", "plainspeak_version"):
        assert key in data
    assert "output" not in data and "applied" not in data
    # utilize -> use and prior to -> before; "in order to" is a diagnostic since ruleset 2026.7.
    assert data["counts"]["safe"] == len(data["safe"]) == 2


@pytest.mark.parametrize("path", sorted(CORPUS.glob("*.md"))[:9], ids=lambda path: path.stem)
@pytest.mark.parametrize("profile", ["natural", "technical"])
def test_diagnose_and_present_agree_about_every_item(path, profile):
    text = path.read_text(encoding="utf-8")
    diagnosed = diagnose_text(text, profile).as_dict()
    presented = present_text(text, profile).as_dict()
    assert diagnosed["safe"] == presented["applied"]
    for key in ("review", "refused", "diagnostics", "style_coverage", "profile", "input", "engine"):
        assert diagnosed[key] == presented[key]
    assert diagnosed["protected"]["facts"] == presented["protected"]["facts"]


def test_it_is_deterministic():
    assert diagnose_text(TEXT, "plain").to_json() == diagnose_text(TEXT, "plain").to_json()


def test_readability_is_rounded_so_it_cannot_drift():
    readability = diagnose_text(TEXT, "natural").as_dict()["readability"]
    for value in readability.values():
        if isinstance(value, float):
            assert round(value, 2) == value


def test_it_refuses_what_present_refuses():
    with pytest.raises(PresentError) as caught:
        diagnose_text("  \n", "natural")
    assert caught.value.code == "empty_input"
    with pytest.raises(PresentError) as caught:
        diagnose_text(TEXT, "casual")
    assert caught.value.code == "unknown_profile"


def test_the_cli(tmp_path):
    source = tmp_path / "doc.md"
    source.write_text(TEXT, encoding="utf-8")
    result = CliRunner().invoke(main, ["diagnose", str(source), "--profile", "natural"])
    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(diagnose_text(TEXT, "natural").to_json())
    assert source.read_text(encoding="utf-8") == TEXT  # nothing is written

    empty = tmp_path / "empty.md"
    empty.write_text(" ", encoding="utf-8")
    failed = CliRunner().invoke(main, ["diagnose", str(empty), "--profile", "natural"])
    assert failed.exit_code == 1
    assert json.loads(failed.stdout)["error"]["code"] == "empty_input"

    both = CliRunner().invoke(main, ["diagnose", "--profile", "natural"])
    assert both.exit_code == 2
