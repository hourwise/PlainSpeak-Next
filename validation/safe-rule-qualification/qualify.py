"""Qualify every rule that was automatic in ruleset 2026.7, and write the ledger.

    python validation/safe-rule-qualification/qualify.py            # print the summary
    python validation/safe-rule-qualification/qualify.py --write    # also write the ledger
    python validation/safe-rule-qualification/qualify.py --check    # fail if either is stale

Three inputs:

    ruleset-2026.7/     the audited ruleset, frozen verbatim; its hash is checked
    probes.yaml         sentences for each rule: normal, adversarial, specialist
                        and control contexts
    dispositions.yaml   one judgement for each rule, QUALIFIED_SAFE or DEMOTED,
                        naming the probes that failed

Every probe is run through `present` twice, once under the audited ruleset and
once under the bundled one, so the ledger shows what each rule did and what it
does now. Before anything is written the script refuses unless:

- the frozen ruleset is 2026.7, byte for byte, and all 97 of its automatic
  rules have a disposition, with nothing extra;
- every sentence a DEMOTED rule is said to fail on did fire under 2026.7;
- every QUALIFIED_SAFE rule is still automatic, still fires on every sentence
  it fired on, and fires on every one of its control sentences;
- every DEMOTED rule is now a diagnostic under the same ID and fires on
  nothing;
- the bundled automatic rules are exactly the QUALIFIED_SAFE ones.

Outputs: ledger.json beside this script, and SAFE_RULE_QUALIFICATION.md at the
repository root.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AUDITED = HERE / "ruleset-2026.7"
LEDGER = HERE / "ledger.json"
REPORT = ROOT / "SAFE_RULE_QUALIFICATION.md"

sys.path.insert(0, str(ROOT))

from plainspeak.pipeline import present_text  # noqa: E402
from plainspeak.rules import load_ruleset  # noqa: E402

SCHEMA = "plainspeak.safe-rule-qualification.v1"
AUDITED_VERSION = "2026.7"
AUDITED_SHA256 = "dc414694104982b26328a493243e30aa94eab399ce8f155d18b60b1ab005e050"
AUDITED_AUTOMATIC = 97
GROUPS = ("normal", "adversarial", "specialist", "control")
PROFILE = "natural"
DISPOSITIONS = ("QUALIFIED_SAFE", "DEMOTED")
FINDINGS = ("ungrammatical", "meaning-shift", "term-of-art", "never-applied")


class QualificationError(Exception):
    pass


def _read_yaml(path: Path):
    return yaml.safe_load(path.read_bytes().decode("utf-8"))


def _source(rule) -> str:
    match = rule.match
    if match.type == "lemma":
        return f'lemma "{match.lemma}" ({match.part_of_speech})'
    if match.type in ("word", "phrase"):
        return f'{match.type} "{match.text.strip()}"'
    return f"{match.type} {match.pattern or match.text!r}"


def _replacement(rule) -> str:
    action = rule.action
    if action.type == "delete":
        return "(deleted)"
    if rule.match.inflections:
        return f'lemma "{action.lemma}"' if action.lemma else action.replacement
    return f'"{action.replacement}"'


def _reachability(rule) -> str:
    match = rule.match
    case = "case-insensitive" if match.case == "insensitive" else f"case {match.case}"
    if match.inflections:
        forms = ", ".join(f"{source} → {target}" for source, target in match.inflections)
        reach = (f"whole-word, {case} match of the generated forms: {forms}. "
                 f"Part of speech is used to generate the forms and is not checked when matching")
    elif match.type == "phrase":
        reach = f'{case} match of the phrase "{match.text.strip()}" at word boundaries'
    else:
        reach = f'whole-word, {case} match of "{match.text}" only; no other form'
    scope = ", ".join(rule.scope.include)
    if rule.scope.exclude:
        scope += f"; not in {', '.join(rule.scope.exclude)}"
    return f"{reach}. Scope: {scope}."


def _observe(sentence: str, rule_id: str, ruleset) -> dict:
    result = present_text(sentence + "\n", PROFILE, ruleset=ruleset).as_dict()
    return {
        "fired": any(item["rule_id"] == rule_id for item in result["applied"]),
        "refused": sorted({item["refusal"] for item in result["refused"] if item["rule_id"] == rule_id}),
        "output": result["output"]["text"].rstrip("\n"),
    }


def run() -> dict:
    audited = load_ruleset(AUDITED)
    current = load_ruleset()
    problems: list[str] = []

    if audited.version != AUDITED_VERSION or audited.hash != AUDITED_SHA256:
        raise QualificationError(
            f"{AUDITED.name} is {audited.version} {audited.hash[:12]}, not the audited ruleset")
    automatic = {rule.id: rule for rule in audited.rules if rule.mode == "safe-fix"}
    if len(automatic) != AUDITED_AUTOMATIC:
        raise QualificationError(f"{len(automatic)} automatic rules in {AUDITED.name}")
    now = {rule.id: rule for rule in current.rules}

    probes = _read_yaml(HERE / "probes.yaml")["rules"]
    manifest = _read_yaml(HERE / "dispositions.yaml")
    dispositions = manifest["rules"]
    for name, found in (("probes.yaml", set(probes)), ("dispositions.yaml", set(dispositions))):
        if found != set(automatic):
            raise QualificationError(
                f"{name}: missing {sorted(set(automatic) - found)}, extra {sorted(found - set(automatic))}")

    families = {}
    for family, spec in manifest["families"].items():
        unknown = set(spec["members"]) - set(automatic)
        if unknown:
            problems.append(f"family {family}: not audited rules {sorted(unknown)}")
        families[family] = {"note": spec["note"], "members": list(spec["members"])}
    family_of = {member: family for family, spec in families.items() for member in spec["members"]}

    ledger = []
    for rule_id in sorted(automatic):
        rule, entry, spec = automatic[rule_id], dispositions[rule_id], probes[rule_id]
        disposition = entry["disposition"]
        if disposition not in DISPOSITIONS:
            problems.append(f"{rule_id}: disposition {disposition!r}")
        failing = list(entry.get("failing", []))
        rows = []
        for group in GROUPS:
            for sentence in spec[group]:
                before = _observe(sentence, rule_id, audited)
                after = _observe(sentence, rule_id, current)
                if sentence in failing:
                    verdict = "fails"
                elif before["fired"]:
                    verdict = "correct" if disposition == "QUALIFIED_SAFE" else "fired"
                elif before["refused"]:
                    verdict = "refused"
                else:
                    verdict = "not reached"
                rows.append({
                    "group": group,
                    "input": sentence,
                    "verdict": verdict,
                    "fired_2026_7": before["fired"],
                    "output_2026_7": before["output"],
                    "refused_2026_7": before["refused"],
                    "fired_now": after["fired"],
                    "output_now": after["output"],
                })

        inputs = {row["input"] for row in rows}
        for sentence in failing:
            if sentence not in inputs:
                problems.append(f"{rule_id}: failing sentence is not a probe: {sentence!r}")
        fired_before = [row for row in rows if row["fired_2026_7"]]
        if not fired_before and entry.get("finding") != "never-applied":
            problems.append(f"{rule_id}: fired on no probe under 2026.7")

        live = now.get(rule_id)
        if live is None:
            problems.append(f"{rule_id}: no longer in the bundled ruleset")
        elif disposition == "QUALIFIED_SAFE":
            if failing or entry.get("finding"):
                problems.append(f"{rule_id}: QUALIFIED_SAFE with a failing sentence or finding")
            if live.mode != "safe-fix":
                problems.append(f"{rule_id}: QUALIFIED_SAFE but {live.mode} in the bundled ruleset")
            for row in rows:
                if row["fired_2026_7"] != row["fired_now"]:
                    problems.append(f"{rule_id}: behaves differently now on {row['input']!r}")
                if row["group"] == "control" and not row["fired_now"]:
                    problems.append(f"{rule_id}: control sentence not applied: {row['input']!r}")
        else:
            if entry.get("finding") not in FINDINGS:
                problems.append(f"{rule_id}: DEMOTED without a known finding")
            if entry["finding"] == "never-applied":
                if fired_before:
                    problems.append(f"{rule_id}: said never to apply, but it fired")
            elif not failing:
                problems.append(f"{rule_id}: DEMOTED without a failing sentence")
            for row in rows:
                if row["verdict"] == "fails" and not row["fired_2026_7"]:
                    problems.append(f"{rule_id}: failing sentence did not fire under 2026.7: {row['input']!r}")
                if row["fired_now"]:
                    problems.append(f"{rule_id}: DEMOTED but still applied to {row['input']!r}")
            if live.mode != "diagnostic":
                problems.append(f"{rule_id}: DEMOTED but {live.mode} in the bundled ruleset")

        ledger.append({
            "rule_id": rule_id,
            "name": rule.name,
            "source": _source(rule),
            "replacement": _replacement(rule),
            "category": spec["category"],
            "family": family_of.get(rule_id, ""),
            "reachability": _reachability(rule),
            "disposition": disposition,
            "finding": entry.get("finding", ""),
            "rationale": entry["rationale"],
            "residual": entry.get("residual", ""),
            "mode_now": live.mode if live else "",
            "probes": rows,
        })

    qualified = {row["rule_id"] for row in ledger if row["disposition"] == "QUALIFIED_SAFE"}
    automatic_now = {rule.id for rule in current.rules if rule.mode == "safe-fix"}
    if qualified != automatic_now:
        problems.append(f"bundled automatic rules differ from QUALIFIED_SAFE: "
                        f"unqualified {sorted(automatic_now - qualified)}, "
                        f"not automatic {sorted(qualified - automatic_now)}")
    if problems:
        raise QualificationError("\n".join(problems))

    counts = Counter(row["disposition"] for row in ledger)
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "audited_ruleset": {"version": audited.version, "sha256": audited.hash,
                            "rules": len(audited.rules), "automatic": len(automatic)},
        "result_ruleset": {"version": current.version, "sha256": current.hash,
                           "rules": len(current.rules), "automatic": len(automatic_now)},
        "counts": {
            "rules": len(ledger),
            "qualified_safe": counts["QUALIFIED_SAFE"],
            "demoted": counts["DEMOTED"],
            "probes": sum(len(row["probes"]) for row in ledger),
            "findings": dict(sorted(Counter(row["finding"] for row in ledger if row["finding"]).items())),
        },
        "families": families,
        "rules": ledger,
    }


# ── The report ─────────────────────────────────────────────────────────────


def _probe_lines(rows: list[dict]) -> list[str]:
    lines = []
    for group in GROUPS:
        for row in (row for row in rows if row["group"] == group):
            if row["fired_2026_7"]:
                after = f"→ {row['output_2026_7']}"
            elif row["refused_2026_7"]:
                after = f"→ refused: {'; '.join(row['refused_2026_7'])}"
            else:
                after = "→ not reached"
            lines.append(f"| {group} | {row['verdict']} | {row['input']} | {after} |")
    return lines


def _entry(row: dict) -> list[str]:
    lines = [
        f"### {row['rule_id']} — {row['source']} → {row['replacement']}",
        "",
        f"- **Category:** {row['category']}",
        f"- **Reachability:** {row['reachability']}",
    ]
    if row["family"]:
        lines.append(f"- **Family:** {row['family']}")
    verdict = row["disposition"] + (f" ({row['finding']})" if row["finding"] else "")
    lines += [f"- **Disposition:** {verdict}", f"- **Rationale:** {row['rationale']}"]
    if row["residual"]:
        lines.append(f"- **Residual uncertainty:** {row['residual']}")
    lines += ["", "| context | verdict | sentence | under 2026.7 |", "|---|---|---|---|"]
    lines += _probe_lines(row["probes"])
    lines.append("")
    return lines


def render(ledger: dict) -> str:
    counts, audited, result = ledger["counts"], ledger["audited_ruleset"], ledger["result_ruleset"]
    rules = ledger["rules"]
    retained = [row for row in rules if row["disposition"] == "QUALIFIED_SAFE"]
    demoted = [row for row in rules if row["disposition"] == "DEMOTED"]
    by_id = {row["rule_id"]: row for row in rules}
    lines = [
        "# Safe-rule qualification",
        "",
        "<!-- Generated by validation/safe-rule-qualification/qualify.py from probes.yaml and",
        "     dispositions.yaml. Do not edit by hand: change the inputs and regenerate. -->",
        "",
        f"Every rule that could change text automatically in ruleset {audited['version']} "
        f"(`{audited['sha256'][:12]}`) — {audited['automatic']} of {audited['rules']} — "
        f"was probed and given one disposition. {counts['qualified_safe']} are qualified "
        f"and stay automatic; {counts['demoted']} are demoted to diagnostics under the "
        f"same IDs. The result is ruleset {result['version']} (`{result['sha256'][:12]}`), "
        f"in which {result['automatic']} of {result['rules']} rules are automatic: exactly "
        f"the qualified ones.",
        "",
        "## Method",
        "",
        f"Each rule has sentences in four groups ({counts['probes']} in all), run through "
        f"`present` under the `{ledger['profile']}` profile:",
        "",
        "- **normal** — the uses the rule was written for;",
        "- **adversarial** — sentence position, part of speech, participles used as "
        "adjectives, pronoun objects, phrasal verbs, infinitive complements, fixed "
        "expressions, punctuation and capitalisation;",
        "- **specialist** — legal and procedural, finance and accounting, clinical, "
        "technical and software, and government language, wherever the word is "
        "plausibly a term there;",
        "- **control** — further ordinary uses, which a qualified rule must still apply.",
        "",
        "A rule is qualified only if every sentence it fired on stayed grammatical, "
        "kept its meaning at full strength, and left any term of art intact. A rule is "
        "demoted if one realistic sentence fails; no context guard was added to keep "
        "a rule automatic, no new rule was written, and neither Verify nor the "
        "integrity firewall was changed.",
        "",
        "Most probes were written before anything was run. After the first run, a "
        "second pass added sentences for the rules that the first pass had not "
        "settled. `qualify.py` re-runs every probe under both the audited ruleset "
        "(frozen verbatim in `validation/safe-rule-qualification/ruleset-2026.7/`, "
        "hash checked) and the bundled one. It refuses to write the ledger unless the "
        "dispositions, the probes and both rulesets agree; the module docstring lists "
        "the checks. `tests/test_safe_rule_qualification.py` holds the ledger to the "
        "live engine.",
        "",
        "Verdicts: **fails** — the sentence that decided a demotion; **correct** — "
        "fired and judged correct (qualified rules); **fired** — fired, on a rule "
        "already demoted by a failing sentence; **refused** — matched, and the engine "
        "refused to apply it; **not reached** — the matcher did not match.",
        "",
        "## Summary",
        "",
        "| | rules |",
        "|---|---|",
        f"| qualified (still automatic) | {counts['qualified_safe']} |",
        f"| demoted | {counts['demoted']} |",
    ]
    for finding, number in counts["findings"].items():
        lines.append(f"| — {finding} | {number} |")
    lines += [f"| **total** | **{counts['rules']}** |", "",
              "Qualified: " + ", ".join(f"`{row['rule_id']}`" for row in retained) + ".", "",
              "## Retained", ""]
    for row in retained:
        lines += _entry(row)
    lines += ["## Demoted", ""]
    for row in demoted:
        lines += _entry(row)
    lines += ["## Families", "",
              "Rules that share a word, a spelling or a defect shape, and whether they "
              "were judged alike.", ""]
    for family, spec in ledger["families"].items():
        members = ", ".join(f"`{member}` {by_id[member]['disposition']}" for member in spec["members"])
        lines += [f"- **{family}** — {spec['note']} {members}."]
    lines += ["", "## Residual uncertainty", "",
              "What remains for the retained rules, as judged:", ""]
    for row in retained:
        if row["residual"]:
            lines.append(f"- `{row['rule_id']}` — {row['residual']}")
    lines += [
        "",
        "And for the audit itself:",
        "",
        "- The probes were written by the same agent that judged them. They "
        "cover the dimensions above for every rule, but a probe set is a sample, not "
        "a proof. A retained rule could still meet a context nobody thought of. The "
        "ledger makes each such context a one-line addition to `probes.yaml`.",
        "- The lemma matcher generates forms by part of speech but does not check "
        "part of speech when matching. A retained lemma rule reaches every one of its "
        "forms, wherever they occur. The probes for retained rules were written with "
        "that in mind.",
        "- A demoted rule is a diagnostic. The engine still matches it and "
        "records the match in its plan, but never applies it. `present` and "
        "`diagnose` do not list rule diagnostics today, so in practice a demoted "
        "rule's matches are not shown to anyone. Like every migrated diagnostic, "
        "a demoted migrated rule matches only the base form of its term.",
        "",
    ]
    return "\n".join(lines)


def ledger_json(ledger: dict) -> str:
    return json.dumps(ledger, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        ledger = run()
    except QualificationError as exc:
        print(f"qualification refused:\n{exc}", file=sys.stderr)
        return 1
    counts = ledger["counts"]
    print(f"{counts['rules']} rules, {counts['probes']} probes: "
          f"{counts['qualified_safe']} qualified, {counts['demoted']} demoted {counts['findings']}")
    outputs = {LEDGER: ledger_json(ledger), REPORT: render(ledger)}
    if args.write:
        for path, text in outputs.items():
            path.write_bytes(text.encode("utf-8"))
        print("wrote", ", ".join(path.name for path in outputs))
    if args.check:
        stale = [path.name for path, text in outputs.items()
                 if not path.exists() or path.read_bytes().decode("utf-8") != text]
        if stale:
            print("stale:", ", ".join(stale), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
