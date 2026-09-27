"""The GitHub Action adapter: outputs, annotations, policy and hostile input.

The action runs on pull requests, so every path and every snippet of text it
handles may have been written by somebody trying to make it misbehave. These
tests assume exactly that.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest
import yaml

from plainspeak.adapters.github_action import (
    DEFAULT_FAIL_ON,
    EXIT_FAIL,
    EXIT_PASS,
    FAIL_ON,
    ActionError,
    escape_data,
    escape_markdown,
    escape_property,
    outputs,
    resolve_input,
    run,
    write_outputs,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "verify"


@pytest.fixture
def workspace(tmp_path):
    for path in FIXTURES.glob("*.md"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    return tmp_path


def invoke(workspace: Path, after: str, fail_on: str | None = None, **extra):
    output = workspace / "github_output.txt"
    summary = workspace / "summary.md"
    environ = {
        "GITHUB_WORKSPACE": str(workspace),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
        "RUNNER_TEMP": str(workspace / "temp"),
        "PLAINSPEAK_BEFORE": "original.md",
        "PLAINSPEAK_AFTER": after,
        **({"PLAINSPEAK_FAIL_ON": fail_on} if fail_on is not None else {}),
        **extra,
    }
    stdout = io.StringIO()
    code = run(environ, stdout)
    values = {}
    if output.exists():
        for line in output.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            values[name] = value
    return code, stdout.getvalue(), values, summary.read_text(encoding="utf-8") if summary.exists() else ""


# ── The fixtures the dogfood workflow relies on ────────────────────────────


@pytest.mark.parametrize("name,expected", [("accepted", "ACCEPTED"), ("refused", "REFUSED"),
                                           ("inconclusive", "INCONCLUSIVE")])
def test_the_fixtures_give_the_results_their_readme_promises(workspace, name, expected):
    _code, _out, values, _summary = invoke(workspace, f"{name}.md", fail_on="never")
    assert values["result"] == expected


# ── Policy ─────────────────────────────────────────────────────────────────


def test_the_default_policy_is_conservative():
    assert DEFAULT_FAIL_ON == "inconclusive"
    assert FAIL_ON[DEFAULT_FAIL_ON] == {"REFUSED", "INCONCLUSIVE"}


@pytest.mark.parametrize(
    "after,fail_on,expected",
    [
        ("accepted.md", None, EXIT_PASS),
        ("refused.md", None, EXIT_FAIL),
        ("inconclusive.md", None, EXIT_FAIL),
        ("inconclusive.md", "refused", EXIT_PASS),
        ("refused.md", "refused", EXIT_FAIL),
        ("refused.md", "never", EXIT_PASS),
        ("inconclusive.md", "INCONCLUSIVE", EXIT_FAIL),
    ],
)
def test_the_step_fails_according_to_policy(workspace, after, fail_on, expected):
    code, *_ = invoke(workspace, after, fail_on=fail_on)
    assert code == expected


def test_an_unknown_policy_is_refused(workspace):
    code, out, values, _ = invoke(workspace, "accepted.md", fail_on="sometimes")
    assert code == EXIT_FAIL
    assert out.startswith("::error ")
    assert values == {}


# ── Outputs, files and annotations ─────────────────────────────────────────


def test_outputs_and_files(workspace):
    code, out, values, summary = invoke(workspace, "refused.md", fail_on="never")
    assert code == EXIT_PASS
    assert set(values) == {"result", "receipt-sha256", "before-sha256", "after-sha256",
                           "refusals", "unresolved", "result-path", "receipt-path"}
    assert re.fullmatch(r"[0-9a-f]{64}", values["receipt-sha256"])
    result = json.loads(Path(values["result-path"]).read_text(encoding="utf-8"))
    receipt = json.loads(Path(values["receipt-path"]).read_text(encoding="utf-8"))
    assert result["schema"] == "plainspeak.verify.v1"
    assert receipt == result["receipt"]
    assert receipt["sha256"] == values["receipt-sha256"]
    assert int(values["refusals"]) >= 1
    assert "## PlainSpeak verify: REFUSED" in summary


def test_refusals_are_annotated_where_they_happened(workspace):
    """On the changed file where it has the line; on the original where only it does.

    A removed negation has no line in the after text, so it is pointed at in
    the before text rather than not pointed at all.
    """
    _code, out, _values, _summary = invoke(workspace, "refused.md")
    errors = [line for line in out.splitlines() if line.startswith("::error ")]
    assert errors
    assert all(re.search(r"file=(refused|original)\.md,line=\d+,", line) for line in errors)
    assert any("file=refused.md" in line for line in errors)
    assert any("file=original.md" in line and "negation" in line for line in errors)


def test_inconclusive_findings_are_errors_only_when_they_fail_the_step(workspace):
    _code, strict, _values, _summary = invoke(workspace, "inconclusive.md")
    assert any(line.startswith("::error ") for line in strict.splitlines())
    _code, lenient, _values, _summary = invoke(workspace, "inconclusive.md", fail_on="refused")
    assert not any(line.startswith("::error ") for line in lenient.splitlines())
    assert any(line.startswith("::warning ") for line in lenient.splitlines())


def test_several_runs_in_one_job_keep_their_own_files(workspace):
    """Found by the dogfood workflow: a shared directory let a later run
    overwrite an earlier run's receipt while its output still pointed at it."""
    runs = [invoke(workspace, name, fail_on="never")[2]
            for name in ("accepted.md", "refused.md", "inconclusive.md")]
    assert len({values["receipt-path"] for values in runs}) == 3
    for values in runs:
        receipt = json.loads(Path(values["receipt-path"]).read_text(encoding="utf-8"))
        result = json.loads(Path(values["result-path"]).read_text(encoding="utf-8"))
        assert receipt["sha256"] == values["receipt-sha256"]
        assert result["result"] == values["result"]


def test_the_same_inputs_give_the_same_receipt(workspace):
    _c, _o, first, _s = invoke(workspace, "accepted.md")
    _c, _o, second, _s = invoke(workspace, "accepted.md")
    assert first["receipt-sha256"] == second["receipt-sha256"]


# ── Hostile input ──────────────────────────────────────────────────────────


def test_a_snippet_cannot_inject_a_workflow_command(workspace):
    """A document line that tries to smuggle in `::set-output` stays inside one message."""
    hostile = "# Changing your payment date\n\nhello%0A::add-mask::x\n::error::fake %25\n"
    (workspace / "hostile.md").write_text(hostile, encoding="utf-8")
    _code, out, _values, _summary = invoke(workspace, "hostile.md")
    for line in out.splitlines():
        assert line.startswith(("::error ", "::warning ", "PlainSpeak verify:")), line
    assert "::add-mask::" not in out.replace("%3A%3Aadd-mask", "")
    assert all(line.count("::") >= 2 for line in out.splitlines() if line.startswith("::"))


def test_escaping_workflow_commands():
    assert escape_data("a\nb\r%c") == "a%0Ab%0D%25c"
    assert escape_property("x:y,z\n") == "x%3Ay%2Cz%0A"


@pytest.mark.parametrize("addition", [
    "Click ![pixel](https://evil.example/p.png) <img src=x onerror=alert(1)> | cell",
    "Click [here](javascript:alert(1)) **now** | `x` <script>alert(1)</script>",
    "Plain words with a | pipe and ![alt](x) and <b>bold</b>",
])
def test_the_summary_cannot_be_made_to_link_embed_or_break_its_table(workspace, addition):
    original = (workspace / "original.md").read_text(encoding="utf-8")
    (workspace / "hostile.md").write_text(original + "\n" + addition + "\n", encoding="utf-8")
    _code, _out, _values, summary = invoke(workspace, "hostile.md")
    for raw in ("<img", "<script", "<b>", "![", "](", "javascript:alert(1))"):
        assert raw not in summary, raw
    for line in summary.splitlines():
        if line.startswith(("| Refused", "| Not accounted for")) and not re.fullmatch(
                r"\| [A-Za-z ]+ \| \d+ \|", line):
            unescaped = re.findall(r"(?<!\\)\|", line)
            assert len(unescaped) == 5, line  # four cells: the document's pipes are escaped


def test_escape_markdown_neutralises_everything_it_must():
    escaped = escape_markdown("[a](b) `c` <d> & *e* _f_ | g\nh")
    assert re.search(r"(?<!\\)[\[\]()`*_|<>]", escaped) is None, escaped
    assert "&lt;d&gt;" in escaped and "&amp;" in escaped
    assert "\n" not in escaped


def test_outputs_refuse_a_value_with_a_line_break():
    with pytest.raises(ActionError):
        write_outputs({"result-path": "a\nevil=1"}, io.StringIO())


@pytest.mark.parametrize("value", ["../outside.md", "sub/../../outside.md"])
def test_a_path_may_not_escape_the_workspace(workspace, value):
    (workspace.parent / "outside.md").write_text("Pay £5.\n", encoding="utf-8")
    with pytest.raises(ActionError, match="outside the workspace"):
        resolve_input(value, workspace, "before")


def test_a_backslash_path_is_refused_on_every_platform(workspace):
    """A separator on Windows; on Linux and macOS, part of a file name that does not exist.

    Refused either way. Found when the first version of this test assumed the
    Windows reading and failed on Linux and macOS in CI.
    """
    import os

    (workspace.parent / "outside.md").write_text("Pay £5.\n", encoding="utf-8")
    expected = "outside the workspace" if os.sep == "\\" else "not a file"
    with pytest.raises(ActionError, match=expected):
        resolve_input("..\\outside.md", workspace, "before")


def test_an_absolute_path_elsewhere_is_refused(workspace):
    outside = workspace.parent / "elsewhere.md"
    outside.write_text("Pay £5.\n", encoding="utf-8")
    with pytest.raises(ActionError, match="outside the workspace"):
        resolve_input(str(outside), workspace, "before")


def test_a_symbolic_link_out_of_the_workspace_is_refused(workspace):
    outside = workspace.parent / "secret.md"
    outside.write_text("Pay £5.\n", encoding="utf-8")
    link = workspace / "link.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available here")
    with pytest.raises(ActionError, match="outside the workspace"):
        resolve_input("link.md", workspace, "before")


@pytest.mark.parametrize("value,message", [("", "required"), ("a\nb.md", "line break"),
                                           ("missing.md", "not a file"), (".", "not a file")])
def test_bad_paths_are_refused(workspace, value, message):
    with pytest.raises(ActionError, match=message):
        resolve_input(value, workspace, "before")


def test_a_path_error_fails_the_step_without_outputs(workspace):
    code, out, values, _ = invoke(workspace, "../../etc/passwd")
    assert code == EXIT_FAIL
    assert out.startswith("::error ")
    assert values == {}


# ── action.yml ─────────────────────────────────────────────────────────────


def _action() -> dict:
    return yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))


def test_no_input_is_spliced_into_a_script():
    """Inputs reach scripts through `env:` only. `${{ … }}` inside `run:` is injection."""
    for step in _action()["runs"]["steps"]:
        assert "${{" not in step.get("run", ""), step.get("name")


def test_the_action_runs_the_adapter_and_nothing_else():
    runs = [step.get("run", "") for step in _action()["runs"]["steps"]]
    assert any("-m plainspeak.adapters.github_action" in script for script in runs)
    assert not any("plainspeak verify" in script for script in runs)


def test_third_party_actions_are_pinned_by_commit():
    for step in _action()["runs"]["steps"]:
        if "uses" in step:
            assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


def test_the_action_leaves_the_jobs_python_alone():
    setup = next(step for step in _action()["runs"]["steps"] if "setup-python" in step.get("uses", ""))
    assert setup["with"]["update-environment"] is False


def test_the_declared_defaults_and_outputs_match_the_adapter(tmp_path):
    action = _action()
    assert action["inputs"]["fail-on"]["default"] == DEFAULT_FAIL_ON
    from plainspeak.pipeline import verify_text

    result = verify_text("Pay £5.\n", "Pay £5.\n")
    assert set(action["outputs"]) == set(outputs(result, tmp_path / "r", tmp_path / "c"))


def test_the_dogfood_workflow_uses_this_repository():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "verify-action.yml").read_text(
        encoding="utf-8"))
    steps = workflow["jobs"]["dogfood"]["steps"]
    assert [step["uses"] for step in steps if step.get("uses") == "./"]
    assert workflow["permissions"] == {"contents": "read"}
    assert "${{" not in steps[-1]["run"]
