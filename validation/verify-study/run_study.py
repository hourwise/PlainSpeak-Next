"""Run the Verify validation study and classify every outcome.

    python validation/verify-study/run_study.py            # print the summary
    python validation/verify-study/run_study.py --write    # also write results.json
    python validation/verify-study/run_study.py --check    # fail if results.json is stale

Each case in cases.yaml carries a manual judgement written before verify was
run. An outcome is classified against it:

    ACCEPTED      + preserved  correct
    ACCEPTED      + changed    FALSE ACCEPTANCE (release-blocking when protected)
    REFUSED       + changed    correct
    REFUSED       + preserved  false refusal
    INCONCLUSIVE  + changed    caution, correctly withheld
    INCONCLUSIVE  + preserved  caution, at a cost
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CORPUS = ROOT / "tests" / "acceptance" / "corpus"
SOURCES = HERE / "sources"
RESULTS = HERE / "results.json"

sys.path.insert(0, str(ROOT))

from plainspeak.pipeline import present_text, verify_text  # noqa: E402

OUTCOMES = {
    ("ACCEPTED", "preserved"): "correct",
    ("ACCEPTED", "changed"): "false acceptance",
    ("REFUSED", "changed"): "correct",
    ("REFUSED", "preserved"): "false refusal",
    ("INCONCLUSIVE", "changed"): "caution (correct)",
    ("INCONCLUSIVE", "preserved"): "caution (cost)",
}


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def cases() -> list[dict]:
    manifest = yaml.safe_load(_read(HERE / "cases.yaml"))
    expanded = []
    for case in manifest["cases"]:
        if case.get("before_corpus") == "*":
            for path in sorted(CORPUS.glob("*.md")):
                expanded.append({**case, "id": f"P-{path.stem}", "before_text": _read(path),
                                 "source": f"corpus/{path.stem}"})
            continue
        if "before_corpus" in case:
            before, source = _read(CORPUS / f"{case['before_corpus']}.md"), f"corpus/{case['before_corpus']}"
        elif "before_source" in case:
            before, source = _read(SOURCES / f"{case['before_source']}.md"), f"sources/{case['before_source']}"
        else:
            before, source = case["before"], "inline"
        expanded.append({**case, "before_text": before, "source": source})

    for case in expanded:
        after = case["after"]
        if isinstance(after, dict) and "present" in after:
            case["after_text"] = present_text(case["before_text"], after["present"]).text
        elif isinstance(after, dict) and after.get("same"):
            case["after_text"] = case["before_text"]
        else:
            case["after_text"] = after
    return expanded


def run() -> dict:
    results = {}
    for case in cases():
        verdict = verify_text(case["before_text"], case["after_text"])
        outcome = OUTCOMES[(verdict.result, case["meaning"])]
        if outcome == "false acceptance" and case["protected"]:
            outcome = "false acceptance (protected)"
        results[case["id"]] = {
            "class": case["class"],
            "source": case["source"],
            "meaning": case["meaning"],
            "protected": case["protected"],
            "note": case["note"],
            "result": verdict.result,
            "outcome": outcome,
            "refused": sorted({item["kind"] for item in verdict.refusals}),
            "unresolved": sorted({item["code"] for item in verdict.unresolved}),
            "accounted_for": sorted({item["code"] for item in verdict.equivalences}),
            "receipt": verdict.receipt_id,
        }
    return results


def summary(results: dict) -> str:
    by_class: dict[str, Counter] = defaultdict(Counter)
    for item in results.values():
        by_class[item["class"]][item["outcome"]] += 1
    columns = ["correct", "false acceptance (protected)", "false acceptance", "false refusal",
               "caution (correct)", "caution (cost)"]
    lines = ["| class | cases | " + " | ".join(columns) + " |",
             "|---|---|" + "---|" * len(columns)]
    totals = Counter()
    for name in sorted(by_class):
        counts = by_class[name]
        totals.update(counts)
        lines.append(f"| {name} | {sum(counts.values())} | "
                     + " | ".join(str(counts.get(column, 0)) for column in columns) + " |")
    lines.append(f"| **all** | **{sum(totals.values())}** | "
                 + " | ".join(f"**{totals.get(column, 0)}**" for column in columns) + " |")
    lines.append("")
    for heading, wanted in (("False acceptances", "false acceptance"),
                            ("False refusals", "false refusal"),
                            ("Inconclusive, meaning preserved", "caution (cost)"),
                            ("Inconclusive, meaning changed", "caution (correct)")):
        found = [(key, value) for key, value in results.items() if value["outcome"].startswith(wanted)]
        lines.append(f"{heading}: {len(found)}")
        for key, value in found:
            detail = ", ".join(value["refused"] or value["unresolved"])
            lines.append(f"  {key:12} {value['result']:13} {value['note']}  [{detail}]")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    results = run()
    rendered = json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    print(summary(results))
    if options.write:
        with open(RESULTS, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    if options.check and (not RESULTS.exists() or _read(RESULTS) != rendered):
        print("results.json is stale", file=sys.stderr)
        return 1
    blocking = [key for key, value in results.items() if value["outcome"] == "false acceptance (protected)"]
    if blocking:
        print(f"RELEASE-BLOCKING false acceptance: {', '.join(blocking)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
