"""The `present` operation and its `plainspeak.present.v1` contract.

`present` is the non-interactive form of review: every SAFE change applied,
every REVIEW proposal reported and left alone, every refusal explained. Its JSON
is a public contract that later adapters (MCP among them) will reuse, so these
tests pin what the contract promises — fields, types, determinism, the
SAFE/REVIEW/REFUSED split — and deliberately not incidental layout.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from plainspeak.adapters.cli import main
from plainspeak.pipeline import (
    ERROR_EMPTY_INPUT,
    ERROR_UNKNOWN_PROFILE,
    PRESENT_SCHEMA,
    PresentError,
    load_reviewable,
    present,
    present_text,
)
from plainspeak.style.profiles import load_profile

REPO = Path(__file__).resolve().parents[1]
#: Four transition suggestions under Natural, plus one SAFE change.
REVIEW_FIXTURE = REPO / "tests" / "style" / "stylefix" / "concessive-heavy.md"

SAMPLE = (
    "In order to apply, staff must utilize form B-12 no later than 3 June 2027. "
    "It should be noted that the fee of £1,200 is not refundable.\n"
)


@pytest.fixture
def runner():
    return CliRunner()


def _json(result) -> dict:
    return json.loads(result.stdout)


# ── Determinism and identity ───────────────────────────────────────────────


def test_the_same_input_serialises_to_identical_bytes():
    first = present_text(SAMPLE, "natural").to_json()
    second = present_text(SAMPLE, "natural").to_json()
    assert first == second


def test_json_is_canonical():
    rendered = present_text(SAMPLE, "plain").to_json()
    assert rendered.endswith("\n")
    parsed = json.loads(rendered)
    assert json.dumps(parsed, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n" == rendered


def test_schema_and_status():
    data = present_text(SAMPLE, "natural").as_dict()
    assert data["schema"] == PRESENT_SCHEMA == "plainspeak.present.v1"
    assert data["status"] == "ok"


@pytest.mark.parametrize("profile_id", ["natural", "plain", "technical", "government", "academic"])
def test_the_profile_is_named_with_its_identity(profile_id):
    data = present_text(SAMPLE, profile_id).as_dict()
    profile = load_profile(profile_id)
    assert data["profile"] == {"id": profile.id, "version": profile.version, "sha256": profile.hash}
    assert data["engine"]["profile_id"] == profile_id


def test_every_authority_is_reported():
    engine = present_text(SAMPLE, "natural").as_dict()["engine"]
    for key in (
        "ruleset_version", "ruleset_sha256", "integrity_policy_version",
        "integrity_policy_sha256", "morphology_version", "morphology_sha256",
        "style_policy_version", "style_policy_sha256", "profile_pack_version",
        "profile_pack_sha256", "profile_sha256", "plan_sha256", "input_sha256",
    ):
        assert engine[key], key


def test_input_and_output_hashes_are_those_of_the_texts():
    from plainspeak.pipeline import text_hash

    result = present_text(SAMPLE, "natural")
    data = result.as_dict()
    assert data["input"]["sha256"] == text_hash(SAMPLE)
    assert data["output"]["sha256"] == text_hash(result.text)
    assert data["output"]["text"] == result.text


def test_an_unchanged_document_keeps_its_hash():
    plain = "The cat sat on the mat.\n"
    data = present_text(plain, "natural").as_dict()
    assert data["output"]["changed"] is False
    assert data["output"]["sha256"] == data["input"]["sha256"]


def test_a_changed_presentation_changes_the_output_hash():
    data = present_text(SAMPLE, "natural").as_dict()
    assert data["output"]["changed"] is True
    assert data["output"]["sha256"] != data["input"]["sha256"]


def test_the_contract_carries_no_host_specific_data(tmp_path):
    """No paths, timestamps or host details: the same input gives the same bytes anywhere."""
    source = tmp_path / "document-with-a-distinctive-name.md"
    source.write_text(SAMPLE, encoding="utf-8")
    rendered = present(load_reviewable(source), "natural").to_json()
    assert "distinctive-name" not in rendered
    assert str(tmp_path.name) not in rendered


# ── SAFE, REVIEW, REFUSED ──────────────────────────────────────────────────


def test_safe_changes_are_applied():
    result = present_text(SAMPLE, "natural")
    assert result.applied
    assert all(item.badge == "SAFE" and item.status == "applied" for item in result.applied)
    for item in result.applied:
        assert result.text[item.revised_start:item.revised_end] == item.after


def test_review_proposals_are_reported_and_never_applied():
    result = present(load_reviewable(REVIEW_FIXTURE), "natural")
    assert len(result.review) == 4
    for item in result.review:
        assert item.badge == "REVIEW" and item.status == "review_required"
        # Unapplied: the original wording is where the proposal points.
        assert result.text[item.revised_start:item.revised_end] == item.before


def test_review_proposals_appear_in_the_json_and_not_in_the_output():
    data = present(load_reviewable(REVIEW_FIXTURE), "natural").as_dict()
    assert data["counts"]["review"] == len(data["review"]) == 4
    for item in data["review"]:
        assert item["badge"] == "REVIEW"
        assert data["output"]["text"][item["revised_start"]:item["revised_end"]] == item["before"]


def test_there_is_no_way_to_accept_a_review_proposal_through_present():
    import inspect

    for function in (present, present_text):
        parameters = set(inspect.signature(function).parameters)
        assert not parameters & {"accept", "accepted", "auto_accept", "decisions"}


def test_refusals_are_reported_with_a_reason_and_not_applied():
    result = present_text(SAMPLE, "natural")
    refused = {item.rule_id: item for item in result.refused}
    # "It should be noted that" contains the modal "should"; deleting it is refused.
    assert "PS.FRAMING.003" in refused
    item = refused["PS.FRAMING.003"]
    assert item.badge == "REFUSED" and item.refusal
    assert "It should be noted that" in result.text


def test_protected_facts_are_listed_at_their_source_offsets():
    data = present_text(SAMPLE, "natural").as_dict()
    protected = data["protected"]
    assert protected["preserved"] is True
    kinds = {fact["kind"] for fact in protected["facts"]}
    assert {"date", "currency", "modal", "negation", "comparator"} <= kinds
    for fact in protected["facts"]:
        assert SAMPLE[fact["source_start"]:fact["source_end"]] == fact["surface"]


def test_protected_facts_survive_into_the_output():
    from plainspeak.integrity import snapshot

    result = present_text(SAMPLE, "natural")
    assert snapshot(result.source_text).signature == snapshot(result.text).signature


def test_counts_agree_with_the_lists():
    data = present(load_reviewable(REVIEW_FIXTURE), "natural").as_dict()
    for key in ("applied", "review", "refused", "diagnostics"):
        assert data["counts"][key] == len(data[key]), key
    assert data["counts"]["protected"] == len(data["protected"]["facts"])


def test_marked_text_wraps_exactly_the_applied_changes():
    result = present_text(SAMPLE, "natural")
    marked = result.marked_text("[", "]")
    assert marked.replace("[", "").replace("]", "") == result.text
    for item in result.applied:
        if item.after:
            assert f"[{item.after}]" in marked


# ── Refusing to present ────────────────────────────────────────────────────


@pytest.mark.parametrize("text", ["", "   ", "\n\n"])
def test_empty_input_is_an_error_not_an_empty_result(text):
    with pytest.raises(PresentError) as caught:
        present_text(text, "natural")
    assert caught.value.code == ERROR_EMPTY_INPUT


@pytest.mark.parametrize("profile", [None, "", "casual"])
def test_a_profile_must_be_named_and_known(profile):
    with pytest.raises(PresentError) as caught:
        present_text(SAMPLE, profile)
    assert caught.value.code == ERROR_UNKNOWN_PROFILE


def test_an_error_has_its_own_contract_shape():
    error = PresentError(ERROR_EMPTY_INPUT, "the input is empty")
    assert json.loads(error.to_json()) == {
        "schema": PRESENT_SCHEMA,
        "status": "error",
        "error": {"code": ERROR_EMPTY_INPUT, "message": "the input is empty"},
    }


# ── The command ────────────────────────────────────────────────────────────


def test_cli_json_matches_the_library(runner, tmp_path):
    source = tmp_path / "doc.md"
    source.write_text(SAMPLE, encoding="utf-8")
    result = runner.invoke(main, ["present", str(source), "--profile", "natural"])
    assert result.exit_code == 0
    assert result.stdout == present(load_reviewable(source), "natural").to_json()


def test_cli_stdin_defaults_to_markdown_and_can_be_told_otherwise(runner):
    default = runner.invoke(main, ["present", "--stdin", "--profile", "natural"], input=SAMPLE)
    as_text = runner.invoke(
        main, ["present", "--stdin", "--profile", "natural", "--input-format", "text"], input=SAMPLE
    )
    assert _json(default)["input"]["format"] == "markdown"
    assert _json(as_text)["input"]["format"] == "text"


def test_cli_text_format_prints_only_the_document(runner):
    result = runner.invoke(main, ["present", "--stdin", "--profile", "natural", "--format", "text"],
                           input=SAMPLE)
    assert result.exit_code == 0
    assert result.stdout == present_text(SAMPLE, "natural").text


def test_cli_summary_names_all_three_classes(runner):
    result = runner.invoke(main, ["present", "--stdin", "--profile", "natural", "--format", "summary"],
                           input=SAMPLE)
    assert result.exit_code == 0
    for heading in ("(SAFE)", "(REVIEW, not applied)", "(REFUSED, never applied)"):
        assert heading in result.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ["present", "--profile", "natural"],                                # no input
        ["present", "--stdin"],                                             # no profile
        ["present", "--stdin", "--profile", "natural", "--format", "yaml"],  # no such format
    ],
)
def test_cli_malformed_invocations_are_usage_errors(runner, arguments):
    result = runner.invoke(main, arguments, input=SAMPLE)
    assert result.exit_code == 2


def test_cli_rejects_both_inputs_at_once(runner, tmp_path):
    source = tmp_path / "doc.md"
    source.write_text(SAMPLE, encoding="utf-8")
    result = runner.invoke(main, ["present", str(source), "--stdin", "--profile", "natural"], input=SAMPLE)
    assert result.exit_code == 2


def test_cli_input_format_is_for_stdin_only(runner, tmp_path):
    source = tmp_path / "doc.md"
    source.write_text(SAMPLE, encoding="utf-8")
    result = runner.invoke(main, ["present", str(source), "--profile", "natural", "--input-format", "text"])
    assert result.exit_code == 2


def test_cli_empty_input_reports_an_error_code(runner):
    result = runner.invoke(main, ["present", "--stdin", "--profile", "natural"], input="  \n")
    assert result.exit_code == 1
    assert _json(result)["error"]["code"] == "empty_input"


@pytest.mark.parametrize("suffix", [".docx", ".pdf", ".html", ".rtf"])
def test_cli_refuses_formats_it_cannot_present_faithfully(runner, tmp_path, suffix):
    source = tmp_path / f"doc{suffix}"
    source.write_bytes(b"placeholder")
    result = runner.invoke(main, ["present", str(source), "--profile", "natural"])
    assert result.exit_code == 1
    assert _json(result)["error"]["code"] == "unsupported_input"


def test_cli_unknown_profile_reports_an_error_code(runner):
    result = runner.invoke(main, ["present", "--stdin", "--profile", "casual"], input=SAMPLE)
    assert result.exit_code == 1
    assert _json(result)["error"]["code"] == "unknown_profile"


# ── Writing ────────────────────────────────────────────────────────────────


def test_output_writes_a_new_file_and_leaves_the_input_alone(runner, tmp_path):
    source = tmp_path / "doc.md"
    source.write_text(SAMPLE, encoding="utf-8")
    destination = tmp_path / "presented.md"
    result = runner.invoke(main, ["present", str(source), "--profile", "natural", "--format", "text",
                                  "-o", str(destination)])
    assert result.exit_code == 0
    assert destination.read_text(encoding="utf-8") == present_text(SAMPLE, "natural").text
    assert source.read_text(encoding="utf-8") == SAMPLE
    assert sorted(path.name for path in tmp_path.iterdir()) == ["doc.md", "presented.md"]


def test_output_never_replaces_the_input_even_when_asked(runner, tmp_path):
    source = tmp_path / "doc.md"
    source.write_text(SAMPLE, encoding="utf-8")
    result = runner.invoke(main, ["present", str(source), "--profile", "natural",
                                  "-o", str(source), "--overwrite"])
    assert result.exit_code == 2
    assert source.read_text(encoding="utf-8") == SAMPLE


def test_output_does_not_replace_an_existing_file_without_overwrite(runner, tmp_path):
    source = tmp_path / "doc.md"
    source.write_text(SAMPLE, encoding="utf-8")
    existing = tmp_path / "existing.json"
    existing.write_text("keep me", encoding="utf-8")
    refused = runner.invoke(main, ["present", str(source), "--profile", "natural", "-o", str(existing)])
    assert refused.exit_code == 2
    assert existing.read_text(encoding="utf-8") == "keep me"
    allowed = runner.invoke(main, ["present", str(source), "--profile", "natural",
                                   "-o", str(existing), "--overwrite"])
    assert allowed.exit_code == 0
    assert json.loads(existing.read_text(encoding="utf-8"))["schema"] == PRESENT_SCHEMA
