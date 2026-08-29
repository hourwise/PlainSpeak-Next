"""Schema validation for declarative rules.

A malformed rule must be a build failure, not a warning. The failure mode this
guards against is quiet: a rule that fails to load looks exactly like a rule
that decided not to fire, and the only symptom is prose that silently stops
being improved.

Each test breaks exactly one thing in an otherwise-valid rule, so a failure
names the field it meant to test rather than whichever field the validator
happened to reach first.
"""
from __future__ import annotations

import pytest

from plainspeak.rules import RuleError, RulesetError
from plainspeak.rules.schema import (
    MAX_PATTERN_LENGTH,
    MODE_SAFE_FIX,
    build_rule,
)

from .conftest import VALID_RULE


def test_a_valid_rule_loads(ruleset_from) -> None:
    ruleset = ruleset_from(VALID_RULE)
    rule = ruleset.by_id("PS.TEST.001")

    assert rule is not None
    assert rule.version == 1
    assert rule.mode == MODE_SAFE_FIX
    assert rule.match.text == "in order to"
    assert rule.action.replacement == "to"
    assert rule.provenance.licence == "project-authored"
    assert rule.examples.transform[0].after == "Register to vote."


def replace_line(prefix: str, new_line: str) -> str:
    """Rewrite the single line of the valid rule starting with `prefix`."""
    lines = VALID_RULE.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = new_line
            return "\n".join(lines) + "\n"
    raise AssertionError(f"no line starting {prefix!r} in the fixture rule")


def drop_block(prefix: str) -> str:
    """Remove a top-level key and everything indented under it."""
    lines = VALID_RULE.splitlines()
    out, skipping = [], False
    for line in lines:
        if line.startswith(prefix):
            skipping = True
            continue
        if skipping and (line.startswith(" ") or line.startswith("-") or not line.strip()):
            continue
        skipping = False
        out.append(line)
    return "\n".join(out) + "\n"


# ── Required fields ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "prefix",
    ["id:", "version:", "name:", "mode:", "description:", "match:", "reason:",
     "provenance:", "examples:"],
)
def test_every_required_field_is_required(ruleset_from, prefix: str) -> None:
    with pytest.raises((RuleError, RulesetError)) as caught:
        ruleset_from(drop_block(prefix))
    assert prefix.rstrip(":") in str(caught.value) or "missing" in str(caught.value)


def test_an_unknown_field_is_rejected(ruleset_from) -> None:
    """A typo must fail loudly, not create a rule that does something else."""
    with pytest.raises(RuleError, match="unknown field"):
        ruleset_from(VALID_RULE + "\nseverity: high\n")


# ── Identity ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_id",
    ["clarity-001", "PS.CLARITY", "PS.clarity.001", "PS.CLARITY.1", "PS.CLARITY.0001", "001"],
)
def test_an_invalid_id_is_rejected(ruleset_from, bad_id: str) -> None:
    with pytest.raises(RuleError, match="id must match"):
        ruleset_from(replace_line("id:", f"id: {bad_id}"))


@pytest.mark.parametrize("bad_version", ["0", "-1", "1.5", "'one'", "true"])
def test_an_invalid_version_is_rejected(ruleset_from, bad_version: str) -> None:
    with pytest.raises(RuleError, match="version must be a positive integer"):
        ruleset_from(replace_line("version:", f"version: {bad_version}"))


def test_duplicate_ids_are_rejected(ruleset_from) -> None:
    """An ID is a permanent public identity; two rules cannot share one."""
    second = VALID_RULE.replace("name: example-rule", "name: other-rule")
    with pytest.raises(RulesetError, match="duplicate rule id"):
        ruleset_from({"a/one.yaml": VALID_RULE, "b/two.yaml": second})


def test_duplicate_ids_across_documents_in_one_file_are_rejected(ruleset_from) -> None:
    with pytest.raises(RulesetError, match="duplicate rule id"):
        ruleset_from(VALID_RULE + "\n---\n" + VALID_RULE)


def test_the_same_id_at_a_different_version_is_still_a_duplicate(ruleset_from) -> None:
    """Two live versions of one ID would make an audit record ambiguous."""
    second = replace_line("version:", "version: 2")
    with pytest.raises(RulesetError, match="duplicate rule id"):
        ruleset_from({"a/one.yaml": VALID_RULE, "b/two.yaml": second})


# ── Modes and actions ──────────────────────────────────────────────────────


def test_an_unknown_mode_is_rejected(ruleset_from) -> None:
    with pytest.raises(RuleError, match="mode must be one of"):
        ruleset_from(replace_line("mode:", "mode: rewrite"))


def test_style_fix_is_reserved_and_says_so(ruleset_from) -> None:
    """A reserved mode should fail with an explanation, not a generic error."""
    with pytest.raises(RuleError, match="reserved for style profiles"):
        ruleset_from(replace_line("mode:", "mode: style-fix"))


def test_a_diagnostic_may_not_carry_an_action(ruleset_from) -> None:
    """A diagnostic that could replace text would not be a diagnostic."""
    source = replace_line("mode:", "mode: diagnostic")
    with pytest.raises(RuleError, match="may only use action"):
        ruleset_from(source)


def test_a_safe_fix_may_not_protect(ruleset_from) -> None:
    source = VALID_RULE.replace("  type: replace\n  replacement: \"to\"", "  type: protect")
    with pytest.raises(RuleError, match="may only use action"):
        ruleset_from(source)


def test_a_replace_action_requires_a_replacement(ruleset_from) -> None:
    source = VALID_RULE.replace('  replacement: "to"\n', "")
    with pytest.raises(RuleError, match="replacement is required"):
        ruleset_from(source)


def test_a_replacement_on_a_delete_action_is_rejected(ruleset_from) -> None:
    source = VALID_RULE.replace("  type: replace\n", "  type: delete\n")
    with pytest.raises(RuleError, match="meaningless for a delete"):
        ruleset_from(source)


def test_recapitalize_only_applies_to_deletion(ruleset_from) -> None:
    source = VALID_RULE.replace(
        '  replacement: "to"\n', '  replacement: "to"\n  recapitalize: true\n'
    )
    with pytest.raises(RuleError, match="only applies to a delete"):
        ruleset_from(source)


# ── Matchers ───────────────────────────────────────────────────────────────


def test_an_unknown_match_type_is_rejected(ruleset_from) -> None:
    with pytest.raises(RuleError, match="match.type must be one of"):
        ruleset_from(VALID_RULE.replace("  type: phrase", "  type: fuzzy"))


def test_a_phrase_match_requires_text(ruleset_from) -> None:
    source = VALID_RULE.replace('  text: "in order to"\n', "")
    with pytest.raises(RuleError, match="match.text must be a non-empty string"):
        ruleset_from(source)


def test_a_regex_match_may_not_use_text(ruleset_from) -> None:
    source = VALID_RULE.replace("  type: phrase", "  type: regex")
    with pytest.raises(RuleError, match="takes 'pattern'"):
        ruleset_from(source)


def test_a_phrase_match_may_not_use_a_pattern(ruleset_from) -> None:
    source = VALID_RULE.replace('  text: "in order to"', '  pattern: "in order to"')
    with pytest.raises(RuleError, match="takes 'text'"):
        ruleset_from(source)


def test_a_word_match_may_not_contain_spaces(ruleset_from) -> None:
    """Whitespace in a word match means the author wanted a phrase."""
    source = VALID_RULE.replace("  type: phrase", "  type: word")
    with pytest.raises(RuleError, match="only contain letters"):
        ruleset_from(source)


def test_forms_are_only_meaningful_for_a_word_match(ruleset_from) -> None:
    source = VALID_RULE.replace(
        '  text: "in order to"\n', '  text: "in order to"\n  forms: ["so as to"]\n'
    )
    with pytest.raises(RuleError, match="only meaningful for a word match"):
        ruleset_from(source)


def test_duplicate_forms_are_rejected(ruleset_from) -> None:
    source = VALID_RULE.replace(
        "  type: phrase\n  text: \"in order to\"",
        '  type: word\n  text: "utilise"\n  forms: ["utilize", "utilize"]',
    )
    with pytest.raises(RuleError, match="duplicates"):
        ruleset_from(source)


# ── Regex safety ───────────────────────────────────────────────────────────


def regex_rule(pattern: str) -> str:
    return (
        VALID_RULE.replace("mode: safe-fix", "mode: diagnostic")
        .replace('  type: phrase\n  text: "in order to"', f"  type: regex\n  pattern: {pattern}")
        .replace('action:\n  type: replace\n  replacement: "to"\n', "")
        .replace(
            "  transform:\n"
            '    - before: "Register in order to vote."\n'
            '      after: "Register to vote."\n',
            "",
        )
    )


def test_a_valid_regex_rule_loads(ruleset_from) -> None:
    ruleset = ruleset_from(regex_rule('"\\\\bin order to\\\\b"'))
    assert ruleset.by_id("PS.TEST.001").match.pattern


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ('"(a+)+"', "catastrophic backtracking"),
        ('"(x*)*y"', "catastrophic backtracking"),
        ('"(a)\\\\1"', "backreferences"),
        ('"(?i)abc"', "inline global flags"),
        ('"(?(1)a|b)"', "conditional patterns"),
        ('"["', "does not compile"),
    ],
    ids=["nested-plus", "nested-star", "backref", "inline-flags", "conditional", "uncompilable"],
)
def test_pathological_regexes_are_rejected(ruleset_from, pattern: str, expected: str) -> None:
    with pytest.raises(RuleError, match=expected):
        ruleset_from(regex_rule(pattern))


def test_an_overlong_pattern_is_rejected(ruleset_from) -> None:
    long_pattern = '"' + ("a" * (MAX_PATTERN_LENGTH + 1)) + '"'
    with pytest.raises(RuleError, match="limit is"):
        ruleset_from(regex_rule(long_pattern))


def test_a_regex_may_not_drive_a_replacement(ruleset_from) -> None:
    """The matched text varies, so the replacement could not be reviewed."""
    source = VALID_RULE.replace(
        '  type: phrase\n  text: "in order to"', '  type: regex\n  pattern: "in order to"'
    )
    with pytest.raises(RuleError, match="may not drive a replacement"):
        ruleset_from(source)


# ── Scope, priority, provenance ────────────────────────────────────────────


def test_an_unknown_scope_is_rejected(ruleset_from) -> None:
    with pytest.raises(RuleError, match="unknown scope"):
        ruleset_from(VALID_RULE.replace("  include: [prose]", "  include: [paragraphs]"))


def test_a_scope_cannot_be_both_included_and_excluded(ruleset_from) -> None:
    source = VALID_RULE.replace(
        "  include: [prose]", "  include: [prose, quote]\n  exclude: [quote]"
    )
    with pytest.raises(RuleError, match="both included and excluded"):
        ruleset_from(source)


@pytest.mark.parametrize("bad", ["-1", "1001", "'high'", "1.5"])
def test_an_invalid_priority_is_rejected(ruleset_from, bad: str) -> None:
    with pytest.raises(RuleError, match="priority must be"):
        ruleset_from(replace_line("priority:", f"priority: {bad}"))


@pytest.mark.parametrize("field", ["source", "reference", "licence"])
def test_provenance_fields_are_required(ruleset_from, field: str) -> None:
    source = "\n".join(
        line for line in VALID_RULE.splitlines() if not line.strip().startswith(f"{field}:")
    ) + "\n"
    with pytest.raises(RuleError, match="provenance is missing"):
        ruleset_from(source)


def test_an_empty_provenance_source_is_rejected(ruleset_from) -> None:
    source = VALID_RULE.replace('  source: "PlainSpeak test suite"', '  source: ""')
    with pytest.raises(RuleError, match="provenance.source must not be empty"):
        ruleset_from(source)


def test_an_empty_reference_is_allowed(ruleset_from) -> None:
    """An independently authored rule has no external reference to cite."""
    ruleset = ruleset_from(VALID_RULE)
    assert ruleset.by_id("PS.TEST.001").provenance.reference == ""


# ── Examples ───────────────────────────────────────────────────────────────


def test_positive_and_negative_examples_are_both_required(ruleset_from) -> None:
    """The negative cases are the half that forces thought about false positives."""
    source = VALID_RULE.replace('  negative:\n    - "The items arrived in order."\n', "")
    with pytest.raises(RuleError, match="examples.negative"):
        ruleset_from(source)


def test_a_safe_fix_must_state_its_expected_transformation(ruleset_from) -> None:
    source = VALID_RULE.replace(
        '  transform:\n    - before: "Register in order to vote."\n      after: "Register to vote."\n',
        "",
    )
    with pytest.raises(RuleError, match="must state at least one examples.transform"):
        ruleset_from(source)


def test_a_diagnostic_may_not_state_a_transformation(ruleset_from) -> None:
    source = (
        replace_line("mode:", "mode: diagnostic")
        .replace('action:\n  type: replace\n  replacement: "to"\n', "")
    )
    with pytest.raises(RuleError, match="proposes no edit"):
        ruleset_from(source)


# ── Loader-level failures ──────────────────────────────────────────────────


def test_invalid_yaml_fails_loudly(ruleset_from) -> None:
    with pytest.raises(RuleError, match="invalid YAML"):
        ruleset_from("id: [unclosed\n")


def test_a_non_mapping_document_is_rejected(ruleset_from) -> None:
    with pytest.raises(RuleError, match="expected a mapping"):
        ruleset_from("- just\n- a\n- list\n")


def test_a_missing_manifest_is_rejected(tmp_path) -> None:
    from plainspeak.rules import load_ruleset

    root = tmp_path / "empty"
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "r.yaml").write_text(VALID_RULE, encoding="utf-8")
    with pytest.raises(RulesetError, match="manifest not found"):
        load_ruleset(root)


def test_a_manifest_without_a_version_is_rejected(ruleset_from) -> None:
    with pytest.raises(RulesetError, match="ruleset_version"):
        ruleset_from(VALID_RULE, manifest="description: no version here\n")


def test_an_empty_ruleset_is_rejected(tmp_path) -> None:
    from plainspeak.rules import load_ruleset

    root = tmp_path / "none"
    root.mkdir()
    (root / "RULESET.yaml").write_text('ruleset_version: "x"\n', encoding="utf-8")
    with pytest.raises(RulesetError, match="no rules found"):
        load_ruleset(root)


def test_an_oversized_rule_file_is_rejected(tmp_path) -> None:
    from plainspeak.rules import load_ruleset
    from plainspeak.rules.loader import MAX_RULE_FILE_BYTES

    root = tmp_path / "big"
    (root / "rules").mkdir(parents=True)
    (root / "RULESET.yaml").write_text('ruleset_version: "x"\n', encoding="utf-8")
    padding = "# " + ("x" * MAX_RULE_FILE_BYTES) + "\n"
    (root / "rules" / "r.yaml").write_text(padding + VALID_RULE, encoding="utf-8")
    with pytest.raises(RulesetError, match="limit is"):
        load_ruleset(root)


def test_yaml_cannot_construct_python_objects(tmp_path) -> None:
    """safe_load only: a rule file must never be able to reach the interpreter."""
    from plainspeak.rules import load_ruleset

    root = tmp_path / "hostile"
    (root / "rules").mkdir(parents=True)
    (root / "RULESET.yaml").write_text('ruleset_version: "x"\n', encoding="utf-8")
    (root / "rules" / "r.yaml").write_text(
        "!!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8"
    )
    with pytest.raises(RuleError, match="invalid YAML"):
        load_ruleset(root)


def test_error_messages_name_the_file_without_platform_paths(ruleset_from) -> None:
    """A validation message must read the same on every operating system."""
    with pytest.raises(RuleError) as caught:
        ruleset_from({"clarity/broken.yaml": replace_line("mode:", "mode: nonsense")})
    message = str(caught.value)
    assert "clarity/broken.yaml" in message
    assert "\\" not in message
