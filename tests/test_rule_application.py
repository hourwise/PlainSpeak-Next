"""Applying plans: atomicity, freshness, idempotence and audit determinism.

Application is the only place PlainSpeak changes anything, so the preconditions
are checked before a single character moves and a failure changes nothing at
all. A half-applied plan would leave a document in a state no rule intended and
no audit record describes, with no way to tell from the result which half ran.

Idempotence is the other property under test here. Running the engine over its
own output must propose nothing further; if it did, "fixed" would not be a
stable state and a document could drift each time somebody ran the tool.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plainspeak.document import parse_markdown, parse_text
from plainspeak.document.model import Span
from plainspeak.pipeline.apply import (
    ABORT_OVERLAP,
    ABORT_STALE,
    ABORT_WRONG_DOCUMENT,
    ApplicationError,
    apply_plan,
)
from plainspeak.pipeline.audit import (
    plan_digest,
    plan_to_dict,
    plan_to_json,
    result_to_dict,
    result_to_json,
)
from plainspeak.pipeline.planner import build_plan

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = sorted((REPO_ROOT / "tests" / "characterisation" / "corpus").glob("*.txt"))

#: Written via chr() so the literals survive any tooling that rewrites
#: escape sequences in source files.
LF = chr(10)
CRLF = chr(13) + chr(10)


def md(source: str):
    return parse_markdown.parse(source)


def run(source: str, ruleset=None):
    document = md(source)
    plan = build_plan(document, ruleset)
    return document, plan, apply_plan(document, plan)


# ── Applying ───────────────────────────────────────────────────────────────


def test_a_plan_applies_its_accepted_changes() -> None:
    _, _, result = run("Staff utilise the register in order to apply.\n")
    assert result.output == "Staff use the register to apply.\n"
    assert result.change_count == 2
    assert result.changed


def test_the_original_document_is_never_mutated() -> None:
    source = "Staff utilise the register.\n"
    document, plan, result = run(source)

    assert document.source == source
    assert document.source_hash == plan.input_hash
    assert result.output != source


def test_changes_are_applied_right_to_left_without_shifting_each_other() -> None:
    """Several edits in one line must all land where they were mapped."""
    source = "In order to utilise it, ascertain approximately how many.\n"
    _, plan, result = run(source)

    assert len(plan.accepted) == 4
    assert result.output == "To use it, find out about how many.\n"


def test_a_document_with_nothing_to_fix_is_returned_unchanged() -> None:
    source = "This sentence is already plain and short.\n"
    document, _, result = run(source)
    assert result.output == source
    assert not result.changed
    assert result.change_count == 0


def test_markup_survives_application() -> None:
    source = "Staff **utilise** the register, as [the guide](https://e.org/g) says.\n"
    _, _, result = run(source)
    assert result.output == (
        "Staff **use** the register, as [the guide](https://e.org/g) says.\n"
    )


def test_a_quote_survives_application() -> None:
    source = "> Staff utilise the register.\n\nStaff utilise the register.\n"
    _, _, result = run(source)
    assert result.output == "> Staff utilise the register.\n\nStaff use the register.\n"


# ── Atomicity ──────────────────────────────────────────────────────────────


def test_a_plan_for_another_document_is_refused() -> None:
    _, plan, _ = run("Staff utilise the register.\n")
    other = md("An entirely different document.\n")

    with pytest.raises(ApplicationError, match=ABORT_WRONG_DOCUMENT):
        apply_plan(other, plan)


def test_a_stale_plan_is_refused(monkeypatch) -> None:
    """The document changed under the plan; nothing may be applied.

    Forced by rewriting the document's source while keeping its recorded hash,
    which is exactly the shape of the bug this check exists to catch: an
    in-memory document edited by something else between planning and applying.
    """
    source = "Staff utilise the register.\n"
    document = md(source)
    plan = build_plan(document)

    object.__setattr__(document, "source", "Staff employ the register.\n")

    with pytest.raises(ApplicationError, match=ABORT_STALE):
        apply_plan(document, plan)


def test_nothing_is_applied_when_one_change_is_stale() -> None:
    """Atomicity: one bad proposal aborts the whole plan, not just itself."""
    from dataclasses import replace

    source = "Staff utilise the register in order to apply.\n"
    document = md(source)
    plan = build_plan(document)
    assert len(plan.accepted) == 2

    poisoned = replace(plan.accepted[0], original_hash="0" * 64)
    broken = replace(plan, accepted=(poisoned,) + plan.accepted[1:])

    with pytest.raises(ApplicationError, match=ABORT_STALE):
        apply_plan(document, broken)
    assert document.source == source, "the document must be untouched after an abort"


def test_overlapping_accepted_changes_are_refused() -> None:
    """Conflict resolution should prevent this; application checks anyway."""
    from dataclasses import replace

    from plainspeak.document.model import content_hash

    source = "Staff utilise the register.\n"
    document = md(source)
    plan = build_plan(document)
    original = plan.accepted[0]

    overlapping = replace(
        original,
        rule_id="PS.TEST.999",
        source_spans=(Span(original.source_span.start, original.source_span.end - 1),),
        original_text=source[original.source_span.start : original.source_span.end - 1],
        original_hash=content_hash(source[original.source_span.start : original.source_span.end - 1]),
    )
    broken = replace(plan, accepted=(original, overlapping))

    with pytest.raises(ApplicationError, match=ABORT_OVERLAP):
        apply_plan(document, broken)


def test_an_aborted_application_leaves_no_partial_output() -> None:
    from dataclasses import replace

    source = "Staff utilise the register in order to apply.\n"
    document = md(source)
    plan = build_plan(document)
    broken = replace(plan, input_hash="0" * 64)

    with pytest.raises(ApplicationError):
        apply_plan(document, broken)
    assert document.source == source


# ── Idempotence ────────────────────────────────────────────────────────────


def test_every_safe_fix_states_a_transformation_the_engine_produces(bundled) -> None:
    """A rule's own worked example must be what the engine actually does.

    Rules the integrity firewall vetoes are excluded and checked separately by
    `test_integrity_vetoes_exactly_the_documented_rules`, which pins the set so
    it cannot grow without somebody noticing.
    """
    from .test_bundled_rules import INTEGRITY_VETOED

    failures = []
    for rule in bundled.safe_fixes:
        if rule.id in INTEGRITY_VETOED:
            continue
        for example in rule.examples.transform:
            _, _, result = run(example.before + "\n", bundled)
            produced = result.output.rstrip("\n")
            if produced != example.after:
                failures.append(f"{rule.id}: expected {example.after!r}, produced {produced!r}")
    assert not failures, "\n  ".join(["rules disagree with their own examples:"] + failures)


def test_every_safe_fix_is_idempotent(bundled) -> None:
    """Running the engine over its own output must propose nothing further."""
    failures = []
    for rule in bundled.safe_fixes:
        for example in rule.examples.transform:
            _, _, once = run(example.before + "\n", bundled)
            _, second_plan, twice = run(once.output, bundled)
            if twice.change_count != 0 or twice.output != once.output:
                failures.append(
                    f"{rule.id}: a second pass changed {twice.change_count} more thing(s)"
                )
    assert not failures, "\n  ".join(["rules are not idempotent:"] + failures)


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_the_corpus_is_idempotent(path: Path, bundled) -> None:
    source = path.read_bytes().decode("utf-8")
    _, _, once = run(source, bundled)
    _, plan_two, twice = run(once.output, bundled)

    assert plan_two.accepted == (), f"a second pass wanted {len(plan_two.accepted)} more changes"
    assert twice.output == once.output


def test_a_combined_document_is_idempotent(bundled) -> None:
    source = (
        "# Guidance\n\n"
        "It is important to note that staff utilise the register in order to "
        "ascertain approximately how many additional forms are needed.\n\n"
        "- Prior to the hearing, evidence is filed on a regular basis.\n"
        "- In the event that you disagree, you may appeal.\n\n"
        "> It is important to note that quoted text is left alone.\n\n"
        "```\nutilise commence approximately\n```\n\n"
        "Due to the fact that demand is high, a large number of applications "
        "were received in the near future.\n"
    )
    _, first_plan, once = run(source, bundled)
    _, second_plan, twice = run(once.output, bundled)

    assert first_plan.accepted, "the fixture should exercise several rules"
    assert second_plan.accepted == ()
    assert twice.output == once.output
    # The code fence and the quotation must both have survived intact.
    assert "utilise commence approximately" in once.output
    assert "> It is important to note that quoted text is left alone." in once.output


# ── Audit ──────────────────────────────────────────────────────────────────


def test_the_audit_is_deterministic(bundled) -> None:
    source = "It is important to note that staff utilise the register in order to apply.\n"
    _, first, _ = run(source, bundled)
    _, second, _ = run(source, bundled)
    assert plan_to_json(first) == plan_to_json(second)
    assert plan_digest(first) == plan_digest(second)


def test_the_audit_contains_no_timestamp(bundled) -> None:
    """Its hash must identify the decision, not the moment it was taken."""
    import re

    _, plan, result = run("Staff utilise the register.\n", bundled)
    for rendered in (plan_to_json(plan), result_to_json(result)):
        assert not re.search(r"\d{4}-\d{2}-\d{2}", rendered)
        for key in ("timestamp", "generated", "date", "time"):
            assert key not in rendered.lower()


def test_the_audit_is_canonical_json(bundled) -> None:
    _, plan, _ = run("Staff utilise the register in order to apply.\n", bundled)
    rendered = plan_to_json(plan)

    assert rendered.endswith("\n")
    assert json.dumps(json.loads(rendered), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")) + "\n" == rendered


def test_the_audit_records_every_outcome(bundled) -> None:
    source = (
        "It is important to note that staff utilise the register.\n\n"
        "> Staff utilise the register.\n\n"
        "The application was refused.\n"
    )
    _, plan, _ = run(source, bundled)
    record = plan_to_dict(plan)

    statuses = {entry["status"] for entry in record["changes"]}
    assert {"accepted", "refused", "diagnostic"} <= statuses

    for entry in record["changes"]:
        assert entry["rule_id"]
        assert entry["rule_version"] >= 1
        assert entry["mode"] in {"safe-fix", "diagnostic", "protected"}
        if entry["status"] != "accepted":
            assert entry["reason"], f"{entry['rule_id']} was not accepted but gives no reason"


def test_the_audit_names_the_engine_ruleset_and_input(bundled) -> None:
    _, plan, _ = run("Staff utilise the register.\n", bundled)
    record = plan_to_dict(plan)

    assert record["ruleset_sha256"] == bundled.hash
    assert record["ruleset_version"] == bundled.version
    assert len(record["input_sha256"]) == 64
    assert len(record["projection_sha256"]) == 64
    assert record["engine_version"]


def test_the_audit_entry_order_does_not_depend_on_rule_order(bundled) -> None:
    import random

    from plainspeak.rules import Ruleset

    source = "In order to utilise it, ascertain approximately how many.\n"
    document = md(source)
    baseline = plan_to_json(build_plan(document, bundled))

    for seed in range(6):
        shuffled = list(bundled.rules)
        random.Random(seed).shuffle(shuffled)
        reordered = Ruleset(version=bundled.version, hash=bundled.hash, rules=tuple(shuffled))
        assert plan_to_json(build_plan(document, reordered)) == baseline


def test_the_application_record_names_what_changed(bundled) -> None:
    _, _, result = run("Staff utilise the register.\n", bundled)
    record = result_to_dict(result)

    assert record["changed"] is True
    assert record["counts"]["applied"] == 1
    entry = record["applied"][0]
    assert entry["rule_id"] == "PS.LEXICAL.001"
    assert entry["before"] == "utilise"
    assert entry["after"] == "use"
    assert record["output_sha256"] != record["input_sha256"]


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.stem)
def test_line_endings_do_not_change_the_audit(path: Path, bundled) -> None:
    """The same canonical document must audit identically either way."""
    lf = path.read_bytes().decode("utf-8")
    crlf = lf.replace("\n", "\r\n")

    lf_plan = build_plan(md(lf), bundled)
    crlf_plan = build_plan(md(crlf), bundled)

    lf_record = plan_to_dict(lf_plan)
    crlf_record = plan_to_dict(crlf_plan)

    # Source offsets legitimately differ, because a CRLF document is longer, and
    # matched source text spanning a line break legitimately carries the line
    # ending the author used. Everything about the *decision* must not differ,
    # so those fields are normalised rather than dropped: the matched text is
    # still compared, just without its line terminator.
    for record in (lf_record, crlf_record):
        for entry in record["changes"]:
            for key in ("source_start", "source_end", "source_spans", "before_sha256"):
                entry.pop(key)
            entry["before"] = entry["before"].replace(CRLF, LF)
        record.pop("input_sha256")
        record.pop("conflicts")

    assert lf_record == crlf_record
