"""Tests for the pure logic of the field-test harness (field/runner.py).

The harness shells out to `opencode` and `plainspeak`; neither is exercised
here. These tests cover only the functions that take data in and return data
out: prompt building, event parsing, final-rewrite extraction, hashing, case
loading and protocol evaluation. Fixtures are small hand-written shapes of
opencode's `run --format json` event stream; `runner.py` is loaded by path so
it stays a standalone script with no importable package to install.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = REPO_ROOT / "field" / "runner.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("field_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


# --------------------------------------------------------------------- hashing


def test_sha256_text_is_the_utf8_digest():
    assert runner.sha256_text("abc") == hashlib.sha256(b"abc").hexdigest()
    # Known digest of the empty string.
    assert runner.sha256_text("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


# ----------------------------------------------------------------- prompt building


@pytest.fixture
def case():
    return {
        "id": "PSF-T01",
        "class": "positive_control",
        "original": "Prior to publication, you must submit all 12 documents.",
        "instruction": "Rewrite the sentence so it is clearer.",
    }


def test_governed_prompt_content(case):
    prompt = runner.governed_prompt(case)
    assert prompt.startswith(case["instruction"])
    assert case["original"] in prompt
    assert "PlainSpeak MCP verify" in prompt
    assert "Do not use PlainSpeak present or diagnose" in prompt
    assert "FINAL_REWRITE:" in prompt
    # The governed arm must name every terminal decision it reacts to.
    for decision in ("ACCEPTED", "REFUSED", "INCONCLUSIVE"):
        assert decision in prompt


def test_baseline_prompt_forbids_tools(case):
    prompt = runner.baseline_prompt(case)
    assert prompt.startswith(case["instruction"])
    assert case["original"] in prompt
    assert "Do not use PlainSpeak or any other verification tool" in prompt
    assert "FINAL_REWRITE:" in prompt
    # The baseline must not mention the verify tool at all.
    assert "verify" not in prompt.lower()


# ------------------------------------------------------------------ case loading


def test_load_cases_reads_the_cases_list(tmp_path):
    payload = {
        "schema": "plainspeak.field.cases.v1",
        "cases": [
            {"id": "A", "class": "c", "original": "o", "instruction": "i"},
            {"id": "B", "class": "c", "original": "o", "instruction": "i"},
        ],
    }
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    cases = runner.load_cases(path)
    assert [case["id"] for case in cases] == ["A", "B"]


def test_load_cases_default_path_is_the_shipped_file():
    cases = runner.load_cases()
    assert cases, "the shipped cases.json must hold at least one case"
    for case in cases:
        assert {"id", "class", "original", "instruction"} <= set(case)


# ------------------------------------------------------------------- JSON parsing


@pytest.mark.parametrize(
    "value, expected",
    [
        ('{"result": "ACCEPTED"}', {"result": "ACCEPTED"}),
        ("  {}  ", {}),
        ("not json", None),
        ("", None),
        ("   ", None),
        (None, None),
        (42, None),
    ],
)
def test_parse_json_text(value, expected):
    assert runner.parse_json_text(value) == expected


# ------------------------------------------------------------------- extraction


def tool_use_event(tool, status, input_, output, wrapper="execute"):
    """One opencode tool_use event with a nested MCP tool call."""
    return {
        "type": "tool_use",
        "sessionID": "ses_1",
        "part": {
            "tool": wrapper,
            "state": {
                "status": status,
                "output": output,
                "metadata": {"metadata": {"toolCalls": [
                    {"tool": tool, "status": status, "input": input_},
                ]}},
            },
        },
    }


def make_run():
    return {
        "events": [
            {"type": "step_start", "sessionID": "ses_1"},
            {
                "type": "text",
                "sessionID": "ses_1",
                "part": {"type": "text", "text": "First thought."},
            },
            tool_use_event(
                "plainspeak.verify",
                "completed",
                {"before": "B", "after": "A", "format": "text"},
                json.dumps({"result": "ACCEPTED", "schema": "plainspeak.verify.v1"}),
            ),
            {
                "type": "step_finish",
                "part": {
                    "cost": 0,
                    "tokens": {"input": 10, "output": 2},
                    "reason": "tool-calls",
                },
            },
            {
                "type": "text",
                "sessionID": "ses_1",
                "part": {"type": "text", "text": "FINAL_REWRITE: A"},
            },
            {
                "type": "step_finish",
                "part": {"cost": 0, "tokens": {"input": 5, "output": 1},
                         "reason": "stop"},
            },
        ]
    }


def test_extract_collects_text_sessions_usage_and_tool_calls():
    parsed = runner.extract(make_run())
    assert parsed["session_ids"] == ["ses_1"]
    assert parsed["assistant_text"] == "First thought.\nFINAL_REWRITE: A"
    assert len(parsed["usage"]) == 2
    assert parsed["usage"][0]["reason"] == "tool-calls"
    call, = parsed["tool_calls"]
    assert call["tool"] == "plainspeak.verify"
    assert call["status"] == "completed"
    assert call["input"] == {"before": "B", "after": "A", "format": "text"}
    assert call["wrapper_tool"] == "execute"
    assert call["result"] == "ACCEPTED"
    assert call["schema"] == "plainspeak.verify.v1"


def test_extract_keeps_unparseable_tool_output_raw():
    # Real MCP output can arrive wrapped ("null\n\nLogs:\n{...}"), which is
    # not JSON; the runner must keep it raw and leave result/schema None.
    event = tool_use_event(
        "plainspeak.verify", "completed", {"after": "A"},
        "null\n\nLogs:\n{\n  \"result\": \"INCONCLUSIVE\"\n}\n",
    )
    parsed = runner.extract({"events": [event]})
    call, = parsed["tool_calls"]
    assert call["result"] is None
    assert call["schema"] is None
    assert call["parsed_output"] is None
    assert call["raw_output"].startswith("null")


def test_extract_empty_event_list():
    parsed = runner.extract({"events": []})
    assert parsed == {
        "session_ids": [],
        "assistant_text": "",
        "tool_calls": [],
        "usage": [],
    }


# ---------------------------------------------------------- final-rewrite marker


@pytest.mark.parametrize(
    "text, expected",
    [
        ("FINAL_REWRITE: Send 12 documents.", "Send 12 documents."),
        ("  final_rewrite: lower case marker  ", "lower case marker"),
        ("FINAL_REWRITE: \"quoted rewrite\"", "quoted rewrite"),
        ("FINAL_REWRITE: 'single quoted'", "single quoted"),
        ("FINAL_REWRITE: keep \"inner\" quotes", 'keep "inner" quotes'),
        ("FINAL_REWRITE: first\nFINAL_REWRITE: last", "last"),
        ("FINAL_REWRITE: trailing space   ", "trailing space"),
        ("no marker anywhere", None),
        ("FINAL_REWRITE:", None),
        ("FINAL_REWRITE: \"\"", None),
    ],
)
def test_extract_final_rewrite(text, expected):
    assert runner.extract_final_rewrite(text) == expected


# ------------------------------------------------------------- protocol checks


def verify_call(result, after="A", tool="plainspeak.verify"):
    return {
        "tool": tool,
        "status": "completed",
        "input": {"before": "B", "after": after},
        "wrapper_tool": "execute",
        "result": result,
        "schema": "plainspeak.verify.v1",
        "raw_output": None,
        "parsed_output": None,
    }


def parsed_with(tool_calls):
    return {"session_ids": [], "assistant_text": "", "tool_calls": tool_calls,
            "usage": []}


def observer(result):
    return {"result": result, "schema": "plainspeak.verify.v1"}


def test_baseline_passes_with_no_tools_and_an_observer_result():
    verdict = runner.evaluate_protocol(
        "baseline", parsed_with([]), "A", observer("REFUSED"),
    )
    assert verdict == {
        "status": "PASS", "reasons": [], "verify_call_count": 0,
        "verify_results": [],
    }


def test_baseline_fails_when_it_used_a_tool():
    verdict = runner.evaluate_protocol(
        "baseline", parsed_with([verify_call("ACCEPTED")]), "A",
        observer("ACCEPTED"),
    )
    assert verdict["status"] == "FAIL"
    assert "baseline_used_tool" in verdict["reasons"]


def test_governed_passes_with_one_accepted_verify():
    verdict = runner.evaluate_protocol(
        "governed", parsed_with([verify_call("ACCEPTED")]), "A",
        observer("ACCEPTED"),
    )
    assert verdict["status"] == "PASS"
    assert verdict["verify_call_count"] == 1
    assert verdict["verify_results"] == ["ACCEPTED"]


def test_governed_passes_after_refused_then_retry():
    calls = [verify_call("REFUSED", after="A1"), verify_call("ACCEPTED", after="A2")]
    verdict = runner.evaluate_protocol(
        "governed", parsed_with(calls), "A2", observer("ACCEPTED"),
    )
    assert verdict["status"] == "PASS"
    assert verdict["verify_results"] == ["REFUSED", "ACCEPTED"]


@pytest.mark.parametrize(
    "first, reasons",
    [
        ("ACCEPTED", ["model_continued_after_terminal_result"]),
        ("INCONCLUSIVE", ["model_continued_after_terminal_result"]),
    ],
)
def test_governed_fails_when_it_continued_after_a_terminal_result(first, reasons):
    calls = [verify_call(first, after="A1"), verify_call("ACCEPTED", after="A2")]
    verdict = runner.evaluate_protocol(
        "governed", parsed_with(calls), "A2", observer("ACCEPTED"),
    )
    assert verdict["status"] == "FAIL"
    assert reasons[0] in verdict["reasons"]


def test_governed_fails_when_refused_without_exactly_one_retry():
    verdict = runner.evaluate_protocol(
        "governed", parsed_with([verify_call("REFUSED", after="A")]), "A",
        observer("REFUSED"),
    )
    assert "refused_not_retried_exactly_once" in verdict["reasons"]


def test_governed_fails_on_missing_and_recognised_problems():
    other = verify_call(None, tool="plainspeak.diagnose")
    verdict = runner.evaluate_protocol(
        "governed", parsed_with([]), None, None,
    )
    assert verdict["status"] == "FAIL"
    assert verdict["reasons"] == [
        "missing_final_rewrite_marker",
        "observer_verification_missing",
        "governed_did_not_call_verify",
    ]

    calls = [verify_call("ACCEPTED"), other]
    verdict = runner.evaluate_protocol(
        "governed", parsed_with(calls), "A", observer("ACCEPTED"),
    )
    assert "governed_used_non_verify_tool" in verdict["reasons"]


def test_governed_fails_on_unverified_final_rewrite_and_three_calls():
    calls = [
        verify_call("REFUSED", after="A1"),
        verify_call("REFUSED", after="A2"),
        verify_call("ACCEPTED", after="A3"),
    ]
    verdict = runner.evaluate_protocol(
        "governed", parsed_with(calls), "totally different", observer("ACCEPTED"),
    )
    assert "too_many_verify_calls" in verdict["reasons"]
    assert "final_rewrite_not_last_verified_text" in verdict["reasons"]


def test_governed_fails_when_observer_disagrees_with_last_tool_result():
    verdict = runner.evaluate_protocol(
        "governed", parsed_with([verify_call("ACCEPTED")]), "A",
        observer("REFUSED"),
    )
    assert "observer_result_disagrees_with_last_tool_result" in verdict["reasons"]


def test_governed_fails_on_unrecognised_first_result():
    verdict = runner.evaluate_protocol(
        "governed", parsed_with([verify_call(None)]), "A", observer("INCONCLUSIVE"),
    )
    assert "first_verify_result_unrecognized" in verdict["reasons"]
    assert verdict["status"] == "FAIL"


def test_missing_observer_never_counts_as_disagreement():
    # With no observer verification the comparison is skipped, but the
    # absence itself is a failure reason for both arms.
    for arm in ("baseline", "governed"):
        verdict = runner.evaluate_protocol(
            arm, parsed_with([]), "A", None,
        )
        assert "observer_verification_missing" in verdict["reasons"]
