"""Ruleset identity and load-order independence.

Two machines holding the same rules must compute the same ruleset hash. The
obvious implementation — hash the files — fails that, because it makes the
identity depend on directory traversal order, path separators, YAML formatting
and which folder a rule happens to be filed under. None of those change what a
rule does.

These tests attack the hash from each of those directions in turn. If any of
them can move it, the hash is not an identity for the rules; it is an identity
for one machine's filesystem.
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from plainspeak.rules import (
    BUNDLED_ROOT,
    Ruleset,
    canonical_json,
    load_ruleset,
    ruleset_hash,
)
from plainspeak.rules.canonical import CANONICAL_FORM_VERSION, canonical_rule, ruleset_document
from plainspeak.rules.loader import _rule_files

from .conftest import MANIFEST, VALID_RULE

SECOND_RULE = VALID_RULE.replace("PS.TEST.001", "PS.TEST.002").replace(
    "name: example-rule", "name: second-rule"
)
THIRD_RULE = VALID_RULE.replace("PS.TEST.001", "PS.TEST.003").replace(
    "name: example-rule", "name: third-rule"
)


# ── Identity is a property of the rules ────────────────────────────────────


def test_the_same_rules_hash_the_same(ruleset_from) -> None:
    first = ruleset_from({"a.yaml": VALID_RULE, "b.yaml": SECOND_RULE})
    second = ruleset_from({"a.yaml": VALID_RULE, "b.yaml": SECOND_RULE})
    assert first.hash == second.hash


def test_file_layout_does_not_change_the_hash(ruleset_from) -> None:
    """Moving a rule between files and folders must not rename the ruleset."""
    together = ruleset_from({"all/rules.yaml": VALID_RULE + "\n---\n" + SECOND_RULE})
    apart = ruleset_from({"clarity/one.yaml": VALID_RULE, "voice/two.yaml": SECOND_RULE})
    assert together.hash == apart.hash


def test_yaml_formatting_does_not_change_the_hash(ruleset_from) -> None:
    """Key order, quoting and comments are presentation, not semantics."""
    reordered = "\n".join(
        [
            "# a comment that means nothing to the engine",
            "version: 1",
            "mode: safe-fix",
            "id: PS.TEST.001",
            "name: example-rule",
            "description: >",
            "  A rule used by the test suite.",
            "priority: 100",
            "action:",
            "  replacement: to",
            "  type: replace",
            "match:",
            "  text: in order to",
            "  type: phrase",
            "scope:",
            "  include: [prose]",
            "case:",
            "  policy: preserve",
            "reason:",
            "  short: A shorter phrase means the same thing",
            "provenance:",
            "  licence: project-authored",
            "  reference: ''",
            "  source: PlainSpeak test suite",
            "examples:",
            "  negative:",
            "    - The items arrived in order.",
            "  positive:",
            "    - Register in order to vote.",
            "  transform:",
            "    - after: Register to vote.",
            "      before: Register in order to vote.",
            "",
        ]
    )
    assert ruleset_from(reordered).hash == ruleset_from(VALID_RULE).hash


def test_changing_a_rule_changes_the_hash(ruleset_from) -> None:
    original = ruleset_from(VALID_RULE)
    altered = ruleset_from(VALID_RULE.replace('replacement: "to"', 'replacement: "so as to"'))
    assert original.hash != altered.hash


def test_changing_published_wording_changes_the_hash(ruleset_from) -> None:
    """Reasons and descriptions are shown to users, so they are part of identity."""
    original = ruleset_from(VALID_RULE)
    altered = ruleset_from(
        VALID_RULE.replace("A shorter phrase means the same thing", "Different wording entirely")
    )
    assert original.hash != altered.hash


def test_the_ruleset_version_is_part_of_the_identity(ruleset_from) -> None:
    original = ruleset_from(VALID_RULE)
    renamed = ruleset_from(VALID_RULE, manifest='ruleset_version: "test.2"\n')
    assert original.hash != renamed.hash


def test_the_family_directory_is_not_part_of_the_identity(ruleset_from) -> None:
    here = ruleset_from({"clarity/r.yaml": VALID_RULE})
    there = ruleset_from({"voice/r.yaml": VALID_RULE})
    assert here.hash == there.hash
    # ...but it is still recorded, for reports and for `explain_rule`.
    assert here.by_id("PS.TEST.001").family == "clarity"
    assert there.by_id("PS.TEST.001").family == "voice"


# ── Load order ─────────────────────────────────────────────────────────────


def test_shuffling_the_file_order_changes_nothing(ruleset_from, monkeypatch) -> None:
    """Deliberately randomise what the filesystem hands back.

    The loader does not sort its file list, on purpose: sorting there would
    conceal an order dependency rather than remove one. The ruleset is sorted by
    rule identity afterwards, and this proves that is enough.
    """
    files = {
        "a/one.yaml": VALID_RULE,
        "b/two.yaml": SECOND_RULE,
        "c/three.yaml": THIRD_RULE,
    }
    baseline = ruleset_from(files)

    seen = set()
    for seed in range(12):
        rng = random.Random(seed)

        def shuffled(root: Path, _rng=rng):
            paths = [p for p in root.rglob("*.yaml") if p.name != "RULESET.yaml"]
            _rng.shuffle(paths)
            return paths

        monkeypatch.setattr("plainspeak.rules.loader._rule_files", shuffled)
        ruleset = ruleset_from(files)
        seen.add((ruleset.hash, ruleset.ids))

    assert len(seen) == 1, f"load order changed the ruleset: {seen}"
    assert seen == {(baseline.hash, baseline.ids)}


def test_rules_are_always_ordered_by_identity(ruleset_from) -> None:
    ruleset = ruleset_from({"z/last.yaml": THIRD_RULE, "a/first.yaml": SECOND_RULE})
    assert ruleset.ids == ("PS.TEST.002", "PS.TEST.003")


def test_the_bundled_ruleset_hash_is_stable(bundled: Ruleset) -> None:
    """Loading twice must not produce two different identities."""
    again = load_ruleset()
    assert bundled.hash == again.hash
    assert bundled.ids == again.ids


# ── Canonical form ─────────────────────────────────────────────────────────


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    rendered = canonical_json({"b": 1, "a": {"d": 2, "c": 3}})
    assert rendered == '{"a":{"c":3,"d":2},"b":1}\n'


def test_canonical_json_keeps_unicode_rather_than_escaping_it() -> None:
    """Escaped output would still be deterministic but far harder to read."""
    assert canonical_json({"x": "café — 21 °C"}) == '{"x":"café — 21 °C"}\n'


def test_the_canonical_form_carries_a_version(bundled: Ruleset) -> None:
    """A hash computed under an older layout must not look like a current one."""
    document = ruleset_document(bundled.rules, bundled.version)
    assert document["canonical_form"] == CANONICAL_FORM_VERSION


def test_the_canonical_rule_excludes_its_file_location(ruleset_from) -> None:
    ruleset = ruleset_from({"clarity/r.yaml": VALID_RULE})
    rendered = canonical_rule(ruleset.by_id("PS.TEST.001"))
    assert "family" not in rendered
    assert "clarity" not in canonical_json(rendered)


def test_the_load_location_does_not_change_the_identity(bundled: Ruleset, tmp_path) -> None:
    """Copy the bundled tree elsewhere; the ruleset must be the same ruleset.

    This is the property that string-sniffing for path separators only gestures
    at. Provenance fields legitimately contain repo-relative paths an author
    wrote, and descriptions legitimately contain escaped quotes, so the only
    honest check is whether the identity actually moves when the files do.
    """
    import shutil

    elsewhere = tmp_path / "somewhere" / "quite" / "different"
    shutil.copytree(BUNDLED_ROOT, elsewhere)
    relocated = load_ruleset(elsewhere)

    assert relocated.hash == bundled.hash
    assert relocated.ids == bundled.ids
    assert canonical_json(ruleset_document(relocated.rules, relocated.version)) == canonical_json(
        ruleset_document(bundled.rules, bundled.version)
    )


def test_hashing_is_a_pure_function_of_rules_and_version(bundled: Ruleset) -> None:
    assert ruleset_hash(bundled.rules, bundled.version) == bundled.hash
    assert ruleset_hash(reversed(list(bundled.rules)), bundled.version) == bundled.hash


# ── The ruleset object ─────────────────────────────────────────────────────


def test_a_ruleset_is_immutable(bundled: Ruleset) -> None:
    with pytest.raises(Exception):
        bundled.rules = ()  # type: ignore[misc]
    assert isinstance(bundled.rules, tuple)


def test_lookup_by_id(bundled: Ruleset) -> None:
    assert bundled.by_id("PS.CLARITY.001") is not None
    assert bundled.by_id("PS.NOSUCH.999") is None


def test_mode_partitions_cover_every_rule(bundled: Ruleset) -> None:
    total = (
        len(bundled.safe_fixes)
        + len(bundled.diagnostics)
        + len(bundled.protections)
        + len(bundled.style_fixes)
    )
    assert total == len(bundled)


def test_style_fixes_are_a_separate_partition(bundled: Ruleset) -> None:
    """Never folded in with the safe fixes.

    A caller asking for "the rules that propose edits" and receiving both would
    be one refactor away from applying a stylistic preference automatically, so
    the two sets are kept apart at the point where somebody would be tempted.
    """
    assert bundled.style_fixes
    assert not set(bundled.style_fixes) & set(bundled.safe_fixes)
    for rule in bundled.style_fixes:
        assert not rule.is_automatic


# ── Cross-platform identity ────────────────────────────────────────────────

#: The identity of the ruleset as it currently ships. Pinned deliberately.
#:
#: Every other test in this file checks that the hash does not move for reasons
#: it should not — file order, layout, formatting. None of them would catch the
#: hash differing *between platforms*, because each machine computes its own
#: value and compares it only to itself. Pinning the expected value means the
#: Windows, Linux and macOS CI jobs all assert the same number, which is the
#: only way that requirement is actually tested.
#:
#: Updating this is the correct thing to do when the rules change, and the diff
#: is a useful signal in review: a commit that touches a rule file and does not
#: touch this line has changed something it did not mean to.
#: Imported rather than pinned a second time. Two copies of the same hash in
#: two files is two places to forget, and the migration suite is where a
#: reviewer already has to look when the ruleset changes.
from .test_glossary_migration import (  # noqa: E402
    RULESET_COUNT as BUNDLED_RULE_COUNT,
    RULESET_HASH as BUNDLED_RULESET_HASH,
    RULESET_VERSION as BUNDLED_RULESET_VERSION,
)


def test_the_bundled_ruleset_has_its_expected_identity(bundled: Ruleset) -> None:
    assert bundled.version == BUNDLED_RULESET_VERSION
    assert len(bundled) == BUNDLED_RULE_COUNT
    assert bundled.hash == BUNDLED_RULESET_HASH, (
        "The bundled ruleset hash changed.\n"
        "  If you edited a rule, update BUNDLED_RULESET_HASH in this file and say so\n"
        "  in the commit message — the hash is a published identity.\n"
        "  If you did not edit a rule, something platform-dependent has reached the\n"
        "  canonical form, and that is a bug in the hashing rather than in this test."
    )


def test_the_bundled_ruleset_is_loaded_once_per_process() -> None:
    """Parsing 222 rules costs about half a second, and it is a pure function.

    Nothing called this often enough to matter until Phase 9: the transformation
    planner takes a ruleset once per document, but style planning takes one per
    document *per profile*, so comparing five profiles was paying two and a half
    seconds of YAML parsing to answer a question the first load had answered.
    """
    from plainspeak.rules import load_ruleset

    first, second = load_ruleset(), load_ruleset()
    assert first is second
    assert first.hash == second.hash


def test_an_explicit_root_is_never_cached(ruleset_from) -> None:
    """A caller naming a directory gets what is in it now.

    Only the bundled tree is cached, because only the bundled tree cannot change
    under a running process. Every test that writes a rule into a temporary
    directory depends on this.
    """
    from plainspeak.rules import load_ruleset

    first = ruleset_from(VALID_RULE)
    assert first is not load_ruleset()
    assert first.hash != load_ruleset().hash
