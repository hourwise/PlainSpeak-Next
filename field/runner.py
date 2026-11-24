import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import time


ROOT = pathlib.Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"
RESULTS = ROOT / "results"


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cases(path=None):
    cases_path = CASES_PATH if path is None else pathlib.Path(path)
    return json.loads(
        cases_path.read_text(encoding="utf-8")
    )["cases"]


def governed_prompt(case):
    return f"""\
{case["instruction"]}

Produce the rewrite yourself.

After producing your proposed rewrite, you MUST use the PlainSpeak MCP verify
tool to compare your rewrite with the original.

Use PlainSpeak verify only. Do not use PlainSpeak present or diagnose.

If PlainSpeak returns ACCEPTED, stop and report ACCEPTED.

If PlainSpeak returns REFUSED, revise the rewrite once and verify the revised
rewrite exactly once.

If PlainSpeak returns INCONCLUSIVE, stop immediately and report INCONCLUSIVE.

After a second verification attempt, stop regardless of its result.

At the very end of your response, output exactly one line in this format:

FINAL_REWRITE: <the last rewrite you actually verified>

Do not put quotation marks around the rewrite on that final line.

Original:
{case["original"]}
"""


def baseline_prompt(case):
    return f"""\
{case["instruction"]}

Do not use PlainSpeak or any other verification tool.

At the very end of your response, output exactly one line in this format:

FINAL_REWRITE: <your rewrite>

Do not put quotation marks around the rewrite on that final line.

Original:
{case["original"]}
"""


def run_opencode(prompt, model=None, config=None):
    opencode = shutil.which("opencode")

    if not opencode:
        raise RuntimeError("opencode was not found on PATH")

    # Windows command shims can mishandle embedded newlines.
    # Flatten only the transported argument. The original multiline
    # prompt is still preserved in the experiment record.
    prompt_arg = " ".join(
        line.strip()
        for line in prompt.splitlines()
        if line.strip()
    )

    cmd = [
        opencode,
        "run",
        "--format",
        "json",
    ]

    if model:
        cmd += ["--model", model]

    cmd.append(prompt_arg)

    started = time.time()

    if config:
        # opencode discovers its project config as "opencode.json" in
        # the working directory. To select another config, run it from
        # a scratch directory that holds the chosen file under that
        # name. Without --config the run stays in ROOT and picks up the
        # repo default exactly as before.
        config_path = pathlib.Path(config)

        if not config_path.is_file():
            raise SystemExit(
                f"Config file not found: {config}"
            )

        with tempfile.TemporaryDirectory(
            prefix="plainspeak-field-config-"
        ) as temp_dir:
            shutil.copyfile(
                config_path,
                pathlib.Path(temp_dir) / "opencode.json",
            )

            proc = subprocess.run(
                cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
    else:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    ended = time.time()

    events = []

    for line in proc.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({
                "type": "_unparsed_stdout",
                "text": line,
            })

    return {
        "command": cmd[:-1] + ["<PROMPT>"],
        "exit_code": proc.returncode,
        "duration_seconds": round(ended - started, 3),
        "stdout_raw": proc.stdout,
        "stderr_raw": proc.stderr,
        "events": events,
    }


def parse_json_text(value):
    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def extract(run):
    final_texts = []
    tool_calls = []
    usage = []
    session_ids = set()

    for event in run["events"]:
        sid = event.get("sessionID")

        if sid:
            session_ids.add(sid)

        if event.get("type") == "text":
            text = event.get("part", {}).get("text")

            if text:
                final_texts.append(text)

        if event.get("type") == "step_finish":
            part = event.get("part", {})

            usage.append({
                "cost": part.get("cost"),
                "tokens": part.get("tokens"),
                "reason": part.get("reason"),
            })

        if event.get("type") != "tool_use":
            continue

        state = event.get("part", {}).get("state", {})
        metadata = state.get("metadata", {})
        nested_metadata = metadata.get("metadata", {})
        calls = nested_metadata.get("toolCalls", [])

        for call in calls:
            raw_output = state.get("output")
            parsed_output = parse_json_text(raw_output)

            result = None
            schema = None

            if isinstance(parsed_output, dict):
                result = parsed_output.get("result")
                schema = parsed_output.get("schema")

            tool_calls.append({
                "tool": call.get("tool"),
                "status": call.get("status"),
                "input": call.get("input"),
                "wrapper_tool": event.get("part", {}).get("tool"),
                "result": result,
                "schema": schema,
                "raw_output": raw_output,
                "parsed_output": parsed_output,
            })

    assistant_text = "\n".join(final_texts)

    return {
        "session_ids": sorted(session_ids),
        "assistant_text": assistant_text,
        "tool_calls": tool_calls,
        "usage": usage,
    }


def extract_final_rewrite(assistant_text):
    matches = re.findall(
        r"(?im)^\s*FINAL_REWRITE:\s*(.+?)\s*$",
        assistant_text,
    )

    if not matches:
        return None

    value = matches[-1].strip()

    # Be mildly tolerant if the model adds simple outer quotes despite
    # being instructed not to.
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"'", '"'}
    ):
        value = value[1:-1].strip()

    return value or None


def verify_with_plainspeak(before, after):
    plainspeak = shutil.which("plainspeak")

    if not plainspeak:
        raise RuntimeError("plainspeak was not found on PATH")

    with tempfile.TemporaryDirectory(
        prefix="plainspeak-field-"
    ) as temp_dir:
        temp = pathlib.Path(temp_dir)

        before_path = temp / "before.txt"
        after_path = temp / "after.txt"

        before_path.write_text(
            before,
            encoding="utf-8",
        )

        after_path.write_text(
            after,
            encoding="utf-8",
        )

        cmd = [
            plainspeak,
            "verify",
            "--format",
            "json",
            "--input-format",
            "text",
            str(before_path),
            str(after_path),
        ]

        started = time.time()

        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        ended = time.time()

    parsed = parse_json_text(proc.stdout)

    result = None
    schema = None

    if isinstance(parsed, dict):
        result = parsed.get("result")
        schema = parsed.get("schema")

    return {
        "result": result,
        "schema": schema,
        "exit_code": proc.returncode,
        "duration_seconds": round(ended - started, 3),
        "stdout_raw": proc.stdout,
        "stderr_raw": proc.stderr,
        "parsed": parsed,
    }


def evaluate_protocol(
    arm,
    parsed,
    final_rewrite,
    observer_verification,
):
    reasons = []

    tool_calls = parsed["tool_calls"]

    verify_calls = [
        call
        for call in tool_calls
        if call.get("tool") == "plainspeak.verify"
    ]

    other_calls = [
        call
        for call in tool_calls
        if call.get("tool") != "plainspeak.verify"
    ]

    decisions = [
        call.get("result")
        for call in verify_calls
    ]

    if final_rewrite is None:
        reasons.append(
            "missing_final_rewrite_marker"
        )

    if observer_verification is None:
        reasons.append(
            "observer_verification_missing"
        )

    if arm == "baseline":
        if tool_calls:
            reasons.append(
                "baseline_used_tool"
            )

    if arm == "governed":
        if not verify_calls:
            reasons.append(
                "governed_did_not_call_verify"
            )

        if other_calls:
            reasons.append(
                "governed_used_non_verify_tool"
            )

        if len(verify_calls) > 2:
            reasons.append(
                "too_many_verify_calls"
            )

        if verify_calls:
            first = decisions[0]

            if first == "REFUSED":
                if len(verify_calls) != 2:
                    reasons.append(
                        "refused_not_retried_exactly_once"
                    )

            elif first in {
                "ACCEPTED",
                "INCONCLUSIVE",
            }:
                if len(verify_calls) != 1:
                    reasons.append(
                        "model_continued_after_terminal_result"
                    )

            else:
                reasons.append(
                    "first_verify_result_unrecognized"
                )

        if (
            verify_calls
            and final_rewrite is not None
        ):
            last_input = (
                verify_calls[-1].get("input")
                or {}
            )

            last_after = last_input.get("after")

            if last_after != final_rewrite:
                reasons.append(
                    "final_rewrite_not_last_verified_text"
                )

        if (
            verify_calls
            and observer_verification
            and observer_verification.get(
                "result"
            )
        ):
            last_tool_result = (
                verify_calls[-1].get("result")
            )

            observer_result = (
                observer_verification.get(
                    "result"
                )
            )

            if last_tool_result != observer_result:
                reasons.append(
                    "observer_result_disagrees_with_last_tool_result"
                )

    return {
        "status": (
            "PASS"
            if not reasons
            else "FAIL"
        ),
        "reasons": reasons,
        "verify_call_count": len(
            verify_calls
        ),
        "verify_results": decisions,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--model")
    parser.add_argument("--case")
    parser.add_argument(
        "--config",
        help=(
            "Path to an opencode config file to use instead of "
            "the opencode.json next to this runner, for example "
            "opencode.local.example.json for a local model."
        ),
    )

    parser.add_argument(
        "--arm",
        choices=[
            "baseline",
            "governed",
            "both",
        ],
        default="both",
    )

    args = parser.parse_args()

    cases = load_cases()

    if args.case:
        cases = [
            case
            for case in cases
            if case["id"] == args.case
        ]

    if not cases:
        raise SystemExit(
            "No matching cases."
        )

    run_id = dt.datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    outdir = RESULTS / run_id

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = {
        "schema": "plainspeak.field.run.v2",
        "run_id": run_id,
        "model": args.model,
        "cases": [],
    }

    for case in cases:
        if args.arm == "both":
            arms = [
                "baseline",
                "governed",
            ]
        else:
            arms = [
                args.arm,
            ]

        for arm in arms:
            if arm == "baseline":
                prompt = baseline_prompt(
                    case
                )
            else:
                prompt = governed_prompt(
                    case
                )

            print(
                f"Running "
                f"{case['id']} / "
                f"{arm} ..."
            )

            raw = run_opencode(
                prompt,
                args.model,
                args.config,
            )

            parsed = extract(raw)

            final_rewrite = (
                extract_final_rewrite(
                    parsed[
                        "assistant_text"
                    ]
                )
            )

            observer_verification = None

            if final_rewrite is not None:
                observer_verification = (
                    verify_with_plainspeak(
                        case["original"],
                        final_rewrite,
                    )
                )

            protocol = evaluate_protocol(
                arm,
                parsed,
                final_rewrite,
                observer_verification,
            )

            record = {
                "schema": (
                    "plainspeak.field."
                    "result.v2"
                ),
                "run_id": run_id,
                "case_id": case["id"],
                "class": case["class"],
                "arm": arm,
                "model": args.model,
                "original": (
                    case["original"]
                ),
                "original_sha256": (
                    sha256_text(
                        case["original"]
                    )
                ),
                "prompt": prompt,
                "prompt_sha256": (
                    sha256_text(prompt)
                ),
                "exit_code": (
                    raw["exit_code"]
                ),
                "duration_seconds": (
                    raw[
                        "duration_seconds"
                    ]
                ),
                "session_ids": (
                    parsed[
                        "session_ids"
                    ]
                ),
                "assistant_text": (
                    parsed[
                        "assistant_text"
                    ]
                ),
                "assistant_sha256": (
                    sha256_text(
                        parsed[
                            "assistant_text"
                        ]
                    )
                ),
                "final_rewrite": (
                    final_rewrite
                ),
                "final_rewrite_sha256": (
                    sha256_text(
                        final_rewrite
                    )
                    if final_rewrite
                    else None
                ),
                "tool_calls": (
                    parsed[
                        "tool_calls"
                    ]
                ),
                "usage": (
                    parsed[
                        "usage"
                    ]
                ),
                "observer_verification": (
                    observer_verification
                ),
                "protocol": protocol,
                "stderr": (
                    raw["stderr_raw"]
                ),
                "events": (
                    raw["events"]
                ),
            }

            filename = (
                outdir
                / (
                    f"{case['id']}-"
                    f"{arm}.json"
                )
            )

            filename.write_text(
                json.dumps(
                    record,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            observer_result = None

            if observer_verification:
                observer_result = (
                    observer_verification.get(
                        "result"
                    )
                )

            manifest["cases"].append({
                "case_id": case["id"],
                "arm": arm,
                "file": filename.name,
                "exit_code": (
                    raw["exit_code"]
                ),
                "tool_calls": len(
                    parsed[
                        "tool_calls"
                    ]
                ),
                "final_rewrite": (
                    final_rewrite
                ),
                "observer_result": (
                    observer_result
                ),
                "protocol_status": (
                    protocol["status"]
                ),
            })

            print(
                "  Observer result:",
                observer_result,
            )

            print(
                "  Protocol:",
                protocol["status"],
            )

            if protocol["reasons"]:
                print(
                    "  Reasons:",
                    ", ".join(
                        protocol["reasons"]
                    ),
                )

    manifest_path = (
        outdir / "manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"Finished. Results: "
        f"{outdir}"
    )


if __name__ == "__main__":
    main()