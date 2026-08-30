"""The inherited glossary migration.

The inherited glossary is source material, not a transformation policy. Nothing
in it became an automatic fix because upstream suggested it — 449 of its
single-word entries were candidates, and 140 became rules.

Three things are tested here, and the first is the one that matters most:

**Reconciliation.** Every one of the 706 inherited entries has a classification
and a reason. Not "roughly 600 migrated" — a total that adds up.

**Collision safety.** No two rules claim the same surface, no rule's output is
another rule's input, no generated form collides with a protected term, and no
surface comes from two different lemmas. Any of those would make the engine's
behaviour depend on rule ordering.

**Grammar.** Every generated form is pinned in a committed snapshot, so a
reviewer reads actual word pairs and a change to morphology shows up as a diff
of English rather than a diff of hashes.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest

from plainspeak.integrity.protected import PROTECTED_TERMS, is_protected_term
from plainspeak.rules import MODE_DIAGNOSTIC, MODE_SAFE_FIX, find_matches, load_ruleset

REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = REPO_ROOT / "migration" / "glossary-inventory.json"

#: The inventory as it currently stands, pinned so every platform asserts the
#: same number. It moves when a classification decision changes, which is
#: exactly when a reviewer should be looking.
INVENTORY_HASH = "b1657b20e4a4a0768d9c4b6b9d783d2293e1b20f98b6ae8bfbed91d72bc5fc3d"

#: The ruleset as it currently ships. Phase 4 was 2026.1 / 38 / 2110d4ed…;
#: the glossary migration made it 2026.2 / 214 / e5aaf376…; Phase 9 activated
#: the `style-fix` mode and added eight transition substitutions, making it
#: 2026.3 / 222. Each step bumps the version rather than quietly retaining an
#: old hash, because each changes what the engine will do to a document.
#:
#: The migration figures below are unchanged: Phase 9 added rules in a new
#: family and renumbered nothing.
RULESET_VERSION = "2026.3"
RULESET_COUNT = 222
#: How many of those came from the glossary migration. Pinned separately so a
#: later phase adding rules cannot silently change what this file is about.
MIGRATED_RULESET_COUNT = 214
RULESET_HASH = "7eddd0710ec15b7bdc940321d08dd2c4882e1561e11f8473fb1f2148709c0461"

#: Rule IDs that existed before the migration. These must never be renumbered:
#: an ID is a permanent public identity that an audit record may already name.
PHASE_FOUR_IDS = frozenset(
    [f"PS.CLARITY.{n:03d}" for n in range(1, 11)]
    + [f"PS.FRAMING.{n:03d}" for n in range(1, 7)]
    + [f"PS.LEXICAL.{n:03d}" for n in range(1, 13)]
    + [f"PS.PROTECT.{n:03d}" for n in range(1, 7)]
    + [f"PS.VOICE.{n:03d}" for n in range(1, 5)]
)


@pytest.fixture(scope="module")
def inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ruleset():
    return load_ruleset()


def surfaces_of(rule) -> list[tuple[str, str]]:
    if rule.match.inflections:
        return list(rule.match.inflections)
    return [(literal, rule.action.replacement) for literal in rule.match.literals]


# ── Reconciliation ─────────────────────────────────────────────────────────


def test_the_inventory_covers_every_inherited_entry(inventory: dict) -> None:
    from plainspeak.core.glossary import GLOSSARY, SIMPLE_WORD_MAP

    inherited = set(GLOSSARY) | set(SIMPLE_WORD_MAP)
    inventoried = {entry["term"] for entry in inventory["entries"]}

    assert inventoried == inherited, (
        f"missing from the inventory: {sorted(inherited - inventoried)[:10]}; "
        f"invented by it: {sorted(inventoried - inherited)[:10]}"
    )
    assert inventory["totals"]["inherited_entries"] == len(inherited)


def test_the_classifications_add_up(inventory: dict) -> None:
    """The reconciliation the phase brief asks for, as an assertion."""
    by_class = inventory["totals"]["by_classification"]
    assert sum(by_class.values()) == inventory["totals"]["inherited_entries"]


def test_every_entry_has_a_classification_and_a_reason(inventory: dict) -> None:
    known = {"safe-fix", "diagnostic", "protected", "deferred", "rejected", "already-covered"}
    for entry in inventory["entries"]:
        assert entry["classification"] in known, entry
        assert entry["reason"], f"{entry['term']} has no reason recorded"


def test_the_inventory_is_deterministic(inventory: dict) -> None:
    canonical = json.dumps(inventory, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest()
    assert digest == INVENTORY_HASH, (
        "The glossary inventory changed.\n"
        "  Regenerate with `python tools/build_glossary_inventory.py --rules`,\n"
        "  read the diff, and update INVENTORY_HASH here."
    )


def test_the_inventory_is_not_stale() -> None:
    """The committed file matches what the builder produces now."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "tools/build_glossary_inventory.py", "--check"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


# ── No entry is promoted merely because upstream suggested it ──────────────


def test_most_inherited_entries_did_not_become_rules(inventory: dict) -> None:
    """The hard safety invariant, as a number.

    If this ever inverts — most entries becoming automatic — somebody has
    started trusting the inherited glossary as a policy rather than reading it.
    """
    by_class = inventory["totals"]["by_classification"]
    total = inventory["totals"]["inherited_entries"]
    assert by_class["safe-fix"] < total / 2


def test_no_protected_term_became_a_rule(inventory: dict) -> None:
    for entry in inventory["entries"]:
        if entry["term"] in PROTECTED_TERMS:
            assert entry["classification"] == "protected", (
                f"{entry['term']} is a protected term but was classified "
                f"{entry['classification']}"
            )


def test_rejected_entries_record_why(inventory: dict) -> None:
    """Bad inherited suggestions are dropped, with the reason written down."""
    rejected = [entry for entry in inventory["entries"] if entry["classification"] == "rejected"]
    assert rejected
    for entry in rejected:
        assert len(entry["reason"]) > 20, f"{entry['term']} was rejected without an argument"


def test_multi_word_entries_were_not_migrated_wholesale(inventory: dict) -> None:
    """Phrase rewriting needs its own review; none was smuggled in as lexical."""
    for entry in inventory["entries"]:
        if entry["multi_word"] and entry["classification"] == "safe-fix":
            pytest.fail(f"multi-word entry {entry['term']!r} became an automatic rule")


def test_nominalisation_reversal_did_not_arrive(ruleset) -> None:
    """The `clarity` -> `clare` class of defect must not reach the new path."""
    for rule in ruleset.safe_fixes:
        for surface, replacement in surfaces_of(rule):
            assert surface != "clarity", "the inherited nominalisation bug has been migrated"
            assert replacement != "clare"


# ── Rule identity ──────────────────────────────────────────────────────────


def test_the_ruleset_has_its_expected_identity(ruleset) -> None:
    assert ruleset.version == RULESET_VERSION
    assert len(ruleset) == RULESET_COUNT
    assert ruleset.hash == RULESET_HASH, (
        "The ruleset hash changed. Regenerate the migrated rules, read the diff, "
        "and update RULESET_HASH here."
    )


def test_existing_rule_ids_are_untouched(ruleset) -> None:
    """A rule ID is permanent. Migration adds; it never renumbers."""
    present = set(ruleset.ids)
    missing = sorted(PHASE_FOUR_IDS - present)
    assert not missing, f"rule IDs that existed before migration have gone: {missing}"


def test_migrated_ids_use_their_own_block(ruleset) -> None:
    migrated = [
        rule.id for rule in ruleset.rules
        if rule.id.startswith("PS.LEXICAL.") and rule.id not in PHASE_FOUR_IDS
    ]
    assert migrated
    for rule_id in migrated:
        assert int(rule_id.rsplit(".", 1)[1]) >= 100, (
            f"{rule_id} collides with the block reserved for hand-authored rules"
        )


def test_the_ruleset_records_the_morphology_that_built_it(ruleset) -> None:
    from plainspeak.morphology import MORPHOLOGY_VERSION, policy_hash

    assert ruleset.morphology_version == MORPHOLOGY_VERSION
    assert ruleset.morphology_hash == policy_hash()


# ── Collision audit ────────────────────────────────────────────────────────


def test_no_two_rules_claim_the_same_surface(ruleset) -> None:
    owner: dict[str, list[str]] = defaultdict(list)
    for rule in ruleset.rules:
        if rule.match.type == "regex":
            continue
        for surface, _ in surfaces_of(rule):
            owner[surface.lower()].append(rule.id)

    clashes = {surface: ids for surface, ids in owner.items() if len(ids) > 1}
    assert not clashes, f"surfaces claimed by more than one rule: {dict(list(clashes.items())[:8])}"


def test_no_rule_output_is_another_rule_input(ruleset) -> None:
    """A cycle would break idempotence and hide behind rule priority."""
    cycles = []
    for rule in ruleset.safe_fixes:
        for _, replacement in surfaces_of(rule):
            if not replacement:
                continue
            for match in find_matches(replacement, ruleset.rules):
                if match.mode == MODE_SAFE_FIX:
                    cycles.append(f"{rule.id} produces {replacement!r}, matched by {match.rule_id}")
    assert not cycles, "replacement cycles: " + "; ".join(cycles[:6])


def test_no_generated_surface_is_a_protected_term(ruleset) -> None:
    offenders = [
        f"{rule.id}:{surface}"
        for rule in ruleset.safe_fixes
        for surface, _ in surfaces_of(rule)
        if is_protected_term(surface)
    ]
    assert not offenders, f"safe fixes targeting protected terms: {offenders}"


def test_no_surface_comes_from_two_lemmas(ruleset) -> None:
    lemmas: dict[str, set[str]] = defaultdict(set)
    for rule in ruleset.rules:
        for surface, _ in rule.match.inflections:
            lemmas[surface.lower()].add(rule.match.lemma)
    clashes = {surface: sorted(names) for surface, names in lemmas.items() if len(names) > 1}
    assert not clashes, f"surfaces generated by more than one lemma: {clashes}"


def test_no_replacement_is_empty_for_a_safe_fix(ruleset) -> None:
    for rule in ruleset.safe_fixes:
        if rule.action.type != "replace":
            continue
        for surface, replacement in surfaces_of(rule):
            assert replacement, f"{rule.id} would replace {surface!r} with nothing"


# ── Generated forms, pinned for review ─────────────────────────────────────

FORMS_SNAPSHOT = REPO_ROOT / "tests" / "morphology" / "generated-forms.txt"


def render_forms(ruleset) -> str:
    """Every generated surface pair, as readable text.

    A hash tells a reviewer that something changed. This tells them *what*, in
    English, which is the only way to notice that a rule has started producing a
    word nobody would write.
    """
    lines = []
    for rule in sorted(ruleset.rules, key=lambda item: item.id):
        if not rule.match.inflections:
            continue
        pairs = "  ".join(f"{surface} -> {replacement}" for surface, replacement in rule.match.inflections)
        lines.append(f"{rule.id}  [{rule.match.part_of_speech}]  {pairs}")
    return "\n".join(lines) + "\n"


def test_generated_forms_match_the_reviewed_snapshot(ruleset) -> None:
    produced = render_forms(ruleset)
    assert FORMS_SNAPSHOT.exists(), (
        "no generated-forms snapshot; write one with the current output and read it"
    )
    assert produced == FORMS_SNAPSHOT.read_bytes().decode("utf-8"), (
        "the generated word forms changed.\n"
        "  Read the diff — this is the file where a nonsense form like 'clare' would\n"
        "  show up as plain English — then update the snapshot."
    )


@pytest.mark.parametrize(
    "surface,forbidden",
    [("concurred", "concured"), ("prohibited", "baned"), ("intervened", "steped in"),
     ("signified", "meaned"), ("disseminated", "spreaded")],
)
def test_specific_defects_the_review_found_stay_fixed(ruleset, surface: str, forbidden: str) -> None:
    """Regression cases from the first pass over the generated forms."""
    for rule in ruleset.safe_fixes:
        for candidate, replacement in surfaces_of(rule):
            if candidate == surface:
                assert replacement != forbidden, f"{rule.id} regressed to {forbidden!r}"
