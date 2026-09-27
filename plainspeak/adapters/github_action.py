"""The GitHub Action: `plainspeak verify` inside a workflow.

An adapter and nothing more. It resolves two paths, calls
`pipeline.verify_files`, and translates the `plainspeak.verify.v1` result into
what GitHub understands: step outputs, annotations on the changed file, a job
summary, a receipt on disk, and an exit status chosen by the caller's policy.
It contains no verification logic — the architecture tests forbid it.

Everything a workflow passes in arrives through environment variables, never
through text spliced into a shell script, and everything that came from a
document is treated as hostile when it is written back out: a snippet of a
pull request can contain a newline followed by `::set-output` or a Markdown
image pointing anywhere, and neither may reach the runner or the summary as
anything but text.

    PLAINSPEAK_BEFORE          path to the original text (required)
    PLAINSPEAK_AFTER           path to the transformed text (required)
    PLAINSPEAK_FAIL_ON         inconclusive (default) | refused | never
    PLAINSPEAK_INPUT_FORMAT    markdown | text (default: from BEFORE's extension)
    PLAINSPEAK_OUTPUT_DIR      where result.json and receipt.json are written
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping, Optional, TextIO

from ..pipeline import (
    VERIFY_ACCEPTED,
    VERIFY_INCONCLUSIVE,
    VERIFY_REFUSED,
    VerifyError,
    verify_files,
)

#: When the step fails. `inconclusive` is the default because unknown is not
#: safe: a transformation the model cannot vouch for should stop a pipeline
#: until a person has looked at it.
FAIL_ON = {
    "inconclusive": {VERIFY_REFUSED, VERIFY_INCONCLUSIVE},
    "refused": {VERIFY_REFUSED},
    "never": set(),
}
DEFAULT_FAIL_ON = "inconclusive"

EXIT_PASS = 0
EXIT_FAIL = 1

TITLE = "PlainSpeak verify"


class ActionError(ValueError):
    """The action was configured in a way it will not run with."""


# ── Hostile text going back out ────────────────────────────────────────────


def escape_data(value: str) -> str:
    """A workflow-command message: `%`, CR and LF may not survive as themselves."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: str) -> str:
    """A workflow-command property (`file=`, `title=`), which also ends at `:` and `,`."""
    return escape_data(value).replace(":", "%3A").replace(",", "%2C")


_MARKDOWN_SPECIAL = "\\`*_{}[]()#+-.!|<>&~"


def escape_markdown(value: str) -> str:
    """Text from a document, made inert inside the job summary.

    Every character Markdown or HTML could act on is escaped, and line breaks
    become spaces, so a snippet can neither link, embed, format nor break out
    of the table cell it is shown in.
    """
    flat = " ".join(value.split())
    out = []
    for character in flat:
        if character == "<":
            out.append("&lt;")
        elif character == ">":
            out.append("&gt;")
        elif character == "&":
            out.append("&amp;")
        elif character in _MARKDOWN_SPECIAL:
            out.append("\\" + character)
        else:
            out.append(character)
    return "".join(out)


# ── Paths ──────────────────────────────────────────────────────────────────


def resolve_input(value: str, workspace: Path, name: str) -> Path:
    """A path the workflow named, confined to the workspace.

    Verify reads files and nothing else; it has no reason to read one outside
    the repository it was asked about, and a path that could escape (`../`, an
    absolute path elsewhere, a symbolic link out) is refused rather than
    followed.
    """
    if not value or not value.strip():
        raise ActionError(f"`{name}` is required")
    if any(character in value for character in "\n\r\0"):
        raise ActionError(f"`{name}` contains a line break or NUL")
    root = workspace.resolve()
    candidate = Path(value)
    target = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if target != root and root not in target.parents:
        raise ActionError(f"`{name}` resolves outside the workspace: {value}")
    if not target.is_file():
        raise ActionError(f"`{name}` is not a file: {value}")
    return target


def _display(path: Path, workspace: Path) -> str:
    """How GitHub names a file in an annotation: relative to the workspace, `/`-separated."""
    try:
        return path.relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# ── Output ─────────────────────────────────────────────────────────────────


def annotations(result, before: str, after: str, fail: bool) -> list[str]:
    """Workflow commands pointing at the lines that caused the result."""
    lines = []
    for item in result.refusals:
        line = (item.get("after_lines") or [None])[0]
        target = after if line else before
        line = line or (item.get("before_lines") or [None])[0]
        lines.append(_command("error", target, line, f"REFUSED: {item['detail']}"))
    level = "error" if fail else "warning"
    for item in result.unresolved:
        line = item.get("after_line")
        target = after if line else before
        line = line or item.get("before_line")
        message = f"INCONCLUSIVE: {item['detail']}"
        if item.get("before") or item.get("after"):
            message += f" — before: {item['before']!r}; after: {item['after']!r}"
        lines.append(_command(level, target, line, message))
    return lines


def _command(level: str, file: str, line: Optional[int], message: str) -> str:
    properties = [f"file={escape_property(file)}"]
    if line:
        properties.append(f"line={int(line)}")
    properties.append(f"title={escape_property(TITLE)}")
    return f"::{level} {','.join(properties)}::{escape_data(message)}"


def outputs(result, result_path: Path, receipt_path: Path) -> dict[str, str]:
    return {
        "result": result.result,
        "receipt-sha256": result.receipt_id,
        "before-sha256": result.before_sha256,
        "after-sha256": result.after_sha256,
        "refusals": str(len(result.refusals)),
        "unresolved": str(len(result.unresolved)),
        "result-path": str(result_path),
        "receipt-path": str(receipt_path),
    }


def write_outputs(values: Mapping[str, str], handle: TextIO) -> None:
    """`name=value` lines. Refuses a value that could start a new line of its own."""
    for name, value in values.items():
        if any(character in value for character in "\n\r"):
            raise ActionError(f"output {name} contains a line break")
        handle.write(f"{name}={value}\n")


def summary(result, before: str, after: str, fail_on: str, failed: bool) -> str:
    verdict = {
        VERIFY_ACCEPTED: "every protected item survived and every difference is accounted for",
        VERIFY_REFUSED: "a protected item or a region PlainSpeak never rewrites was lost, "
                        "added or changed",
        VERIFY_INCONCLUSIVE: "nothing protected was lost, but something changed that the "
                             "integrity model cannot vouch for",
    }[result.result]
    rows = [
        f"## {TITLE}: {result.result}",
        "",
        f"`{escape_markdown(before)}` → `{escape_markdown(after)}`: {verdict}.",
        "",
        f"Policy `fail-on: {fail_on}` — this step **{'failed' if failed else 'passed'}**.",
        "",
        "| | |",
        "|---|---|",
        f"| Protected items in before | {result.as_dict()['protected']['count']} |",
        f"| Refused | {len(result.refusals)} |",
        f"| Not accounted for | {len(result.unresolved)} |",
        f"| Accounted for | {len(result.equivalences)} |",
        f"| Receipt | `{result.receipt_id}` |",
        "",
    ]
    findings = [("Refused", item) for item in result.refusals] + \
               [("Not accounted for", item) for item in result.unresolved]
    if findings:
        rows += ["| | Detail | Before | After |", "|---|---|---|---|"]
        for label, item in findings:
            before_text = item["before"] if isinstance(item["before"], str) else ", ".join(item["before"])
            after_text = item["after"] if isinstance(item["after"], str) else ", ".join(item["after"])
            rows.append(
                f"| {label} | {escape_markdown(item['detail'])} | {escape_markdown(before_text)} "
                f"| {escape_markdown(after_text)} |"
            )
        rows.append("")
    rows.append("Verify checks the properties PlainSpeak's integrity model represents. It does not "
                "establish that two texts mean the same thing.")
    return "\n".join(rows) + "\n"


# ── Running ────────────────────────────────────────────────────────────────


def run(environ: Mapping[str, str], stdout: TextIO) -> int:
    workspace = Path(environ.get("GITHUB_WORKSPACE") or os.getcwd())
    fail_on = (environ.get("PLAINSPEAK_FAIL_ON") or DEFAULT_FAIL_ON).strip().lower()
    if fail_on not in FAIL_ON:
        return _fatal(stdout, f"`fail-on` must be one of {', '.join(FAIL_ON)}, not {fail_on!r}")
    input_format = (environ.get("PLAINSPEAK_INPUT_FORMAT") or "").strip().lower() or None
    if input_format not in (None, "markdown", "text"):
        return _fatal(stdout, f"`input-format` must be markdown or text, not {input_format!r}")

    try:
        before = resolve_input(environ.get("PLAINSPEAK_BEFORE", ""), workspace, "before")
        after = resolve_input(environ.get("PLAINSPEAK_AFTER", ""), workspace, "after")
        result = verify_files(before, after, input_format=input_format)
    except (ActionError, VerifyError) as error:
        return _fatal(stdout, str(error))

    output_dir = Path(environ.get("PLAINSPEAK_OUTPUT_DIR") or (Path(environ.get("RUNNER_TEMP") or ".")
                                                             / "plainspeak-verify"))
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path, receipt_path = output_dir / "result.json", output_dir / "receipt.json"
    with open(result_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(result.to_json())
    with open(receipt_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(result.receipt_json())

    failed = result.result in FAIL_ON[fail_on]
    before_name, after_name = _display(before, workspace), _display(after, workspace)
    for line in annotations(result, before_name, after_name, failed):
        stdout.write(line + "\n")
    stdout.write(f"{TITLE}: {result.result} (receipt {result.receipt_id})\n")

    if environ.get("GITHUB_OUTPUT"):
        with open(environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            write_outputs(outputs(result, result_path, receipt_path), handle)
    if environ.get("GITHUB_STEP_SUMMARY"):
        with open(environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(summary(result, before_name, after_name, fail_on, failed))
    return EXIT_FAIL if failed else EXIT_PASS


def _fatal(stdout: TextIO, message: str) -> int:
    stdout.write(f"::error title={escape_property(TITLE)}::{escape_data(message)}\n")
    return EXIT_FAIL


def main() -> None:
    sys.exit(run(os.environ, sys.stdout))


if __name__ == "__main__":
    main()
