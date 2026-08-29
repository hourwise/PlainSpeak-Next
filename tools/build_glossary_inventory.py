"""Inventory and classify every entry in the inherited PlainSpeak glossary.

The inherited glossary is source material, not a transformation policy. This
script accounts for every entry in it — no rounding, no "roughly 600" — and
assigns each one a classification that either came from a human review in
`migration/decisions.yaml` or from a stated default rule.

    python tools/build_glossary_inventory.py            # write the inventory
    python tools/build_glossary_inventory.py --rules    # also emit rule files
    python tools/build_glossary_inventory.py --check    # fail if either is stale

Default classifications, applied to anything the decisions file does not name:

    PROTECTED   the term is in the inherited protected-term register
    DEFERRED    a multi-word phrase — restructuring needs its own review
    DEFERRED    anything else, as "not yet individually reviewed"

The default is DEFERRED rather than DIAGNOSTIC on purpose. A diagnostic is a
claim that the term is worth flagging; deferring says only that nobody has
looked yet, which is the honest description of an entry inherited in bulk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from plainspeak.integrity.protected import PROTECTED_TERMS, get_protected_domain
from plainspeak.morphology import MorphologyError, inflected_pairs

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_DIR = REPO_ROOT / "migration"
DECISIONS_PATH = MIGRATION_DIR / "decisions.yaml"
INVENTORY_PATH = MIGRATION_DIR / "glossary-inventory.json"
RULES_DIR = REPO_ROOT / "plainspeak" / "rules" / "bundled" / "lexical"
DIAGNOSTIC_DIR = REPO_ROOT / "plainspeak" / "rules" / "bundled" / "ambiguous"

#: Rules per generated file. The loader caps a rule file at 64 KB, and a
#: batch this size also keeps a review diff readable — which is the point of
#: migrating in batches rather than all at once.
RULES_PER_FILE = 30

SAFE_FIX = "safe-fix"
DIAGNOSTIC = "diagnostic"
PROTECTED = "protected"
DEFERRED = "deferred"
REJECTED = "rejected"
#: Already handled by a hand-authored rule from an earlier phase. Counted
#: separately so the reconciliation stays exact: these entries are migrated,
#: just not by this script, and their existing rule IDs are never renumbered.
ALREADY_COVERED = "already-covered"

#: Rule IDs for migrated entries start here, leaving the Phase 4 block
#: (PS.LEXICAL.001–012) untouched. Existing IDs are never renumbered.
MIGRATED_ID_BASE = 100


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def readable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


# ── Reading the inherited glossary ─────────────────────────────────────────


def inherited_entries() -> dict[str, dict[str, Any]]:
    """Every inherited entry, merged and deduplicated, in a stable order.

    GLOSSARY carries an explanation; SIMPLE_WORD_MAP does not. Where both name
    a term, GLOSSARY wins and the overlap is recorded — those 55 duplicates are
    part of the reconciliation, not something to quietly drop.
    """
    from plainspeak.core.glossary import GLOSSARY, SIMPLE_WORD_MAP

    entries: dict[str, dict[str, Any]] = {}

    for term in sorted(GLOSSARY):
        replacement, explanation = GLOSSARY[term]
        entries[term] = {
            "term": term,
            "replacement": replacement,
            "explanation": explanation,
            "sources": ["GLOSSARY"],
        }

    for term in sorted(SIMPLE_WORD_MAP):
        replacement = SIMPLE_WORD_MAP[term]
        if term in entries:
            entries[term]["sources"].append("SIMPLE_WORD_MAP")
            entries[term]["alternate_replacement"] = (
                replacement if replacement != entries[term]["replacement"] else None
            )
        else:
            entries[term] = {
                "term": term,
                "replacement": replacement,
                "explanation": "",
                "sources": ["SIMPLE_WORD_MAP"],
            }

    return dict(sorted(entries.items()))


def load_decisions() -> dict[str, dict[str, Any]]:
    """The reviewed classifications, keyed by term."""
    data = yaml.safe_load(DECISIONS_PATH.read_bytes().decode("utf-8"))
    decisions: dict[str, dict[str, Any]] = {}

    def add(term: str, payload: dict[str, Any]) -> None:
        if term in decisions:
            raise SystemExit(f"{DECISIONS_PATH.name}: {term!r} is classified twice")
        decisions[term] = payload

    for entry in data.get("safe_fix_verbs", []):
        add(entry["term"], {"classification": SAFE_FIX, "pos": "verb", "target": entry["target"]})
    for entry in data.get("safe_fix_nouns", []):
        add(entry["term"], {"classification": SAFE_FIX, "pos": "noun", "target": entry["target"]})
    for entry in data.get("safe_fix_words", []):
        add(entry["term"], {"classification": SAFE_FIX, "pos": "other", "target": entry["target"]})
    for entry in data.get("diagnostic", []):
        add(entry["term"], {"classification": DIAGNOSTIC, "reason": entry["reason"]})
    for entry in data.get("rejected", []):
        add(entry["term"], {"classification": REJECTED, "reason": entry["reason"]})

    return decisions


# ── Classifying ────────────────────────────────────────────────────────────


def classify(entries: dict[str, dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> list[dict]:
    """Assign every inherited entry a classification and a reason."""
    unknown = sorted(set(decisions) - set(entries))
    if unknown:
        raise SystemExit(
            f"{DECISIONS_PATH.name} classifies terms that are not in the inherited "
            f"glossary: {unknown}"
        )

    covered = existing_coverage()
    rows: list[dict[str, Any]] = []
    next_id = MIGRATED_ID_BASE
    next_diagnostic_id = 1

    for term, entry in entries.items():
        protected = term in PROTECTED_TERMS
        decision = decisions.get(term)
        row: dict[str, Any] = {
            "term": term,
            "replacement": entry["replacement"],
            "explanation": entry["explanation"],
            "sources": entry["sources"],
            "duplicate": len(entry["sources"]) > 1,
            "conflicting_replacement": entry.get("alternate_replacement"),
            "protected": protected,
            "protected_domain": get_protected_domain(term) if protected else "",
            "multi_word": " " in term,
            "rule_id": "",
            "forms": [],
        }

        # The protected register outranks any review: a term of art is not made
        # substitutable by somebody deciding it reads awkwardly.
        if protected:
            row["classification"] = PROTECTED
            row["reason"] = (
                f"in the inherited protected-term register"
                + (f" ({row['protected_domain']})" if row["protected_domain"] else "")
            )
        elif term in covered:
            row["classification"] = ALREADY_COVERED
            row["rule_id"] = covered[term]
            row["reason"] = f"already matched by the hand-authored rule {covered[term]}"
        elif decision and decision["classification"] == SAFE_FIX:
            row["classification"] = SAFE_FIX
            row["reason"] = "individually reviewed as a mechanical substitution"
            row["part_of_speech"] = decision["pos"]
            row["target"] = decision["target"]
            row["rule_id"] = f"PS.LEXICAL.{next_id:03d}"
            next_id += 1
            row["forms"] = [list(pair) for pair in _forms_for(term, decision)]
        elif decision and decision["classification"] == DIAGNOSTIC:
            row["classification"] = DIAGNOSTIC
            row["reason"] = decision["reason"]
            row["rule_id"] = f"PS.AMBIGUOUS.{next_diagnostic_id:03d}"
            next_diagnostic_id += 1
        elif decision:
            row["classification"] = decision["classification"]
            row["reason"] = decision["reason"]
        elif row["multi_word"]:
            row["classification"] = DEFERRED
            row["reason"] = "multi-word entry; phrase rewriting needs its own review"
        else:
            row["classification"] = DEFERRED
            row["reason"] = "not yet individually reviewed"

        rows.append(row)

    return rows


def existing_coverage() -> dict[str, str]:
    """Surfaces the hand-authored rules already match, mapped to their rule ID.

    Read from the bundled tree with the generated files excluded, so the script
    can be run repeatedly without seeing its own output. Without this, migrating
    "utilise" would add a second rule for a word Phase 4 already handles, and the
    two would meet in conflict resolution for no reason.
    """
    import shutil
    import tempfile

    from plainspeak.rules import load_ruleset

    with tempfile.TemporaryDirectory() as scratch:
        staged = Path(scratch) / "bundled"
        shutil.copytree(
            RULES_DIR.parent,
            staged,
            ignore=shutil.ignore_patterns("migrated_*.yaml"),
        )
        # A family directory left empty by the filter would still load fine, but
        # an entirely empty tree would not — the hand-authored rules guarantee it
        # is not empty.
        handwritten = load_ruleset(staged)

    coverage: dict[str, str] = {}
    for rule in handwritten.rules:
        if rule.match.inflections:
            surfaces = [surface for surface, _ in rule.match.inflections]
        else:
            surfaces = list(rule.match.literals)
        for surface in surfaces:
            coverage.setdefault(surface.lower(), rule.id)
    return coverage


def _forms_for(term: str, decision: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    try:
        return inflected_pairs(term, decision["target"], decision["pos"])
    except MorphologyError as exc:
        raise SystemExit(f"cannot inflect reviewed entry {term!r}: {exc}") from exc


# ── Output ─────────────────────────────────────────────────────────────────


def build_inventory() -> dict[str, Any]:
    entries = inherited_entries()
    rows = classify(entries, load_decisions())

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1

    return {
        "source": {
            "repository": "hourwise/Project-PlainSpeak",
            "module": "plainspeak/core/glossary.py",
            "licence": "MIT (inherited)",
            "note": "Source material for classification, not a transformation policy.",
        },
        "totals": {
            "inherited_entries": len(rows),
            "duplicate_across_sources": sum(1 for row in rows if row["duplicate"]),
            "conflicting_replacements": sum(
                1 for row in rows if row.get("conflicting_replacement")
            ),
            "by_classification": dict(sorted(counts.items())),
        },
        "entries": rows,
    }


def inventory_hash(inventory: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(inventory).encode("utf-8")).hexdigest()


def emit_rules(inventory: dict[str, Any]) -> str:
    """Render the classified entries as bundled rule files, in batches."""
    written: list[str] = []

    safe = [row for row in inventory["entries"] if row["classification"] == SAFE_FIX]
    by_pos: dict[str, list[dict]] = {}
    for row in safe:
        by_pos.setdefault(row["part_of_speech"], []).append(row)

    for path in list(RULES_DIR.glob("migrated_*.yaml")):
        path.unlink()

    for pos, rows in sorted(by_pos.items()):
        ordered = sorted(rows, key=lambda item: item["rule_id"])
        for index, batch in enumerate(_batched(ordered, RULES_PER_FILE), start=1):
            documents = [_rule_document(row) for row in batch]
            path = RULES_DIR / f"migrated_{pos}s_{index:02d}.yaml"
            path.write_text(
                _rules_header(pos, len(documents), index) + "\n---\n".join(documents),
                encoding="utf-8",
                newline="\n",
            )
            written.append(f"{path.name} ({len(documents)})")

    diagnostics = sorted(
        (row for row in inventory["entries"] if row["classification"] == DIAGNOSTIC),
        key=lambda item: item["rule_id"],
    )
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    for path in list(DIAGNOSTIC_DIR.glob("migrated_*.yaml")):
        path.unlink()
    for index, batch in enumerate(_batched(diagnostics, RULES_PER_FILE), start=1):
        documents = [_diagnostic_document(row) for row in batch]
        path = DIAGNOSTIC_DIR / f"migrated_ambiguous_{index:02d}.yaml"
        path.write_text(
            _diagnostics_header(len(documents)) + "\n---\n".join(documents),
            encoding="utf-8",
            newline="\n",
        )
        written.append(f"{path.name} ({len(documents)})")

    return ", ".join(written)


def _batched(rows: list[dict], size: int) -> list[list[dict]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _diagnostics_header(count: int) -> str:
    return (
        f"# {count} terms the inherited glossary would substitute, and this engine\n"
        f"# will not.\n"
        f"#\n"
        f"# Each is worth flagging and cannot be replaced mechanically: a word with two\n"
        f"# senses, a gloss standing in for a definition, or a replacement the integrity\n"
        f"# firewall would veto. The reason travels with the rule, because a reader told\n"
        f"# only that a word is complex has been given nothing to act on.\n"
        f"#\n"
        f"# Generated by tools/build_glossary_inventory.py from migration/decisions.yaml.\n"
        f"\n"
    )


def _diagnostic_document(row: dict[str, Any]) -> str:
    term = row["term"]
    reason = row["reason"].replace('"', "'")
    short = reason if len(reason) <= 110 else reason[:107] + "..."
    return (
        f'id: {row["rule_id"]}\n'
        f"version: 1\n"
        f"name: {term}-is-ambiguous\n"
        f"mode: diagnostic\n"
        f"description: >\n"
        f'  The inherited glossary suggested replacing "{term}" with\n'
        f'  "{row["replacement"]}". This engine reports it instead: {reason}.\n'
        f'match:\n  type: word\n  text: "{term}"\n'
        f"scope:\n  include: [prose]\n"
        f"priority: 70\n"
        f'reason:\n  short: "{short}"\n'
        f"provenance:\n"
        f'  source: "PlainSpeak inherited glossary, reviewed and kept as a diagnostic"\n'
        f'  reference: "plainspeak/core/glossary.py"\n'
        f'  licence: "project-authored"\n'
        f"examples:\n"
        f'  positive:\n    - "The notice used the word {term} here."\n'
        f'  negative:\n    - "A different word entirely appears instead."\n'
    )


def _rules_header(pos: str, count: int, batch: int) -> str:
    return (
        f"# {count} lexical rules migrated from the inherited PlainSpeak glossary\n"
        f"# ({pos}s, batch {batch}).\n"
        f"#\n"
        f"# Generated by tools/build_glossary_inventory.py from the reviewed decisions\n"
        f"# in migration/decisions.yaml. Do not edit by hand: change the decision and\n"
        f"# regenerate, so the inventory and the rules cannot disagree.\n"
        f"#\n"
        f"# Every entry here was individually reviewed. The inherited glossary\n"
        f"# suggested many more; the rest are diagnostics, deferred or rejected, and\n"
        f"# GLOSSARY_MIGRATION.md accounts for all of them.\n"
        f"\n"
    )


def _rule_document(row: dict[str, Any]) -> str:
    pos = row["part_of_speech"]
    term, target = row["term"], row["target"]
    forms = row["forms"]

    if pos == "other":
        match_block = f'match:\n  type: word\n  text: "{term}"\n'
        action_block = f'action:\n  type: replace\n  replacement: "{target}"\n'
    else:
        match_block = f'match:\n  type: lemma\n  lemma: "{term}"\n  pos: {pos}\n'
        action_block = f'action:\n  type: replace\n  lemma: "{target}"\n'

    positive, negative, transform = _examples(row)

    return (
        f'id: {row["rule_id"]}\n'
        f"version: 1\n"
        f"name: {term}-to-{target.replace(' ', '-')}\n"
        f"mode: safe-fix\n"
        f"description: >\n"
        f'  "{term.capitalize()}" is "{target}" in plainer words. Migrated from the\n'
        f"  inherited glossary after individual review; the forms this matches are\n"
        f"  listed in the rule explanation rather than inferred.\n"
        f"{match_block}"
        f"{action_block}"
        f"scope:\n  include: [prose]\n"
        f"case:\n  policy: preserve\n"
        f"priority: 100\n"
        f'reason:\n  short: "\\"{target}\\" is the everyday word"\n'
        f"provenance:\n"
        f'  source: "PlainSpeak inherited glossary, individually reviewed and re-authored"\n'
        f'  reference: "plainspeak/core/glossary.py"\n'
        f'  licence: "project-authored"\n'
        f"examples:\n"
        f"  positive:\n{positive}"
        f"  negative:\n{negative}"
        f"  transform:\n{transform}"
    )


#: Frame sentences for generated examples. A mention frame works for every part
#: of speech, which matters when the same generator has to serve verbs, nouns
#: and adverbs: "The report used the word additionally" is grammatical where
#: "The report will additionally it" is not.
EXAMPLE_FRAME = "The report used the word {}."

#: Filler words in the frames above. A generated example must not accidentally
#: contain one of the rule's own surfaces, and these are the words it could
#: collide with.
FRAME_WORDS = frozenset({"the", "report", "used", "word", "token", "is", "a", "different"})

#: Suffixes tried when building a negative example: a longer token that shares a
#: prefix with the term, to prove the rule's word boundaries hold. The first one
#: that is not itself a form of the rule wins.
NEGATIVE_SUFFIXES = ("r", "ment", "ness", "ability", "oid")


def _examples(row: dict[str, Any]) -> tuple[str, str, str]:
    """Worked examples for a migrated rule, verified as they are generated.

    The first attempt at this produced negatives like "manufactured-up", which
    contains the rule's own past tense — the rule fired on its own
    counter-example. Generated test data is still test data, so it is checked
    here rather than trusted.
    """
    forms = row["forms"]
    surfaces = {surface for surface, _ in forms}
    base_surface, base_target = forms[0]

    positive = "".join(
        f'    - "{EXAMPLE_FRAME.format(surface)}"\n' for surface, _ in forms[:2]
    )

    negative_token = next(
        (
            base_surface + suffix
            for suffix in NEGATIVE_SUFFIXES
            if (base_surface + suffix) not in surfaces
        ),
        base_surface + "-oid",
    )
    negative = f'    - "The token {negative_token} is a different word."\n'

    transform = (
        f'    - before: "{EXAMPLE_FRAME.format(base_surface)}"\n'
        f'      after: "{EXAMPLE_FRAME.format(base_target)}"\n'
    )

    _verify_examples(row, surfaces, negative_token)
    return positive, negative, transform


def _verify_examples(row: dict[str, Any], surfaces: set[str], negative_token: str) -> None:
    """Fail the build if a generated example contradicts its own rule."""
    if negative_token in surfaces:
        raise SystemExit(f"{row['rule_id']}: negative example {negative_token!r} is a real form")

    negative_words = FRAME_WORDS | {negative_token.lower()}
    clash = sorted(surfaces & negative_words)
    if clash:
        raise SystemExit(
            f"{row['rule_id']}: negative example contains the rule's own form(s) {clash}"
        )

    frame_clash = sorted(surfaces & FRAME_WORDS)
    if frame_clash:
        raise SystemExit(
            f"{row['rule_id']}: the example frame contains the rule's own form(s) {frame_clash}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory the inherited glossary.")
    parser.add_argument("--rules", action="store_true", help="also emit bundled rule files")
    parser.add_argument("--check", action="store_true", help="fail if the inventory is stale")
    args = parser.parse_args(argv)

    inventory = build_inventory()
    rendered = readable_json(inventory)

    if args.check:
        if not INVENTORY_PATH.exists() or INVENTORY_PATH.read_text(encoding="utf-8") != rendered:
            print("the glossary inventory is stale; regenerate it", file=sys.stderr)
            return 1
        print(f"inventory up to date ({inventory_hash(inventory)[:12]})")
        return 0

    MIGRATION_DIR.mkdir(exist_ok=True)
    INVENTORY_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote {INVENTORY_PATH.relative_to(REPO_ROOT)}")
    print(f"  entries: {inventory['totals']['inherited_entries']}")
    for name, count in inventory["totals"]["by_classification"].items():
        print(f"    {name:12} {count}")
    print(f"  inventory sha256: {inventory_hash(inventory)}")

    if args.rules:
        print(f"wrote rules: {emit_rules(inventory)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
