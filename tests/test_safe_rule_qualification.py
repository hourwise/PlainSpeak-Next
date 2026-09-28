"""The safe-rule qualification, held to the ruleset it qualified.

validation/safe-rule-qualification/ gives each of the 97 rules that were
automatic in ruleset 2026.7 one disposition, QUALIFIED_SAFE or DEMOTED, with
the probe sentences that decided it. These tests re-run it and require:

- a ledger entry for every one of those 97 rules, and no other;
- the bundled automatic rules to be exactly the QUALIFIED_SAFE ones, so no
  rule can be automatic without having been qualified;
- every DEMOTED rule to be a diagnostic under the same ID;
- ledger.json and SAFE_RULE_QUALIFICATION.md to be exactly what the probes,
  the dispositions and the live engine produce now.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from plainspeak.pipeline import present_text
from plainspeak.rules import load_ruleset

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "validation" / "safe-rule-qualification"


@pytest.fixture(scope="module")
def qualify():
    spec = importlib.util.spec_from_file_location("qualify", HERE / "qualify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ledger(qualify):
    # run() itself refuses on any disagreement between the dispositions, the
    # probes, the frozen 2026.7 ruleset and the bundled one.
    return qualify.run()


@pytest.fixture(scope="module")
def recorded():
    return json.loads((HERE / "ledger.json").read_bytes().decode("utf-8"))


def test_the_recorded_ledger_and_report_are_current(qualify, ledger, recorded):
    assert recorded == json.loads(qualify.ledger_json(ledger))
    report = (ROOT / "SAFE_RULE_QUALIFICATION.md").read_bytes().decode("utf-8")
    assert report == qualify.render(ledger)


def test_every_rule_that_was_automatic_has_exactly_one_entry(qualify, recorded):
    audited = load_ruleset(HERE / "ruleset-2026.7")
    assert (audited.version, audited.hash) == ("2026.7", qualify.AUDITED_SHA256)
    automatic = sorted(rule.id for rule in audited.rules if rule.mode == "safe-fix")
    assert len(automatic) == 97
    assert [row["rule_id"] for row in recorded["rules"]] == automatic
    assert {row["disposition"] for row in recorded["rules"]} <= {"QUALIFIED_SAFE", "DEMOTED"}


def test_the_automatic_rules_are_exactly_the_qualified_ones(recorded):
    bundled = load_ruleset()
    automatic = {rule.id for rule in bundled.rules if rule.mode == "safe-fix"}
    qualified = {row["rule_id"] for row in recorded["rules"] if row["disposition"] == "QUALIFIED_SAFE"}
    assert automatic == qualified
    assert len(automatic) == recorded["counts"]["qualified_safe"] == 23
    assert recorded["result_ruleset"] == {
        "version": bundled.version, "sha256": bundled.hash,
        "rules": len(bundled.rules), "automatic": len(automatic),
    }


def test_every_demoted_rule_is_a_diagnostic_under_the_same_id(recorded):
    audited_ids = {rule.id for rule in load_ruleset(HERE / "ruleset-2026.7").rules}
    bundled = {rule.id: rule for rule in load_ruleset().rules}
    assert set(bundled) == audited_ids
    demoted = [row for row in recorded["rules"] if row["disposition"] == "DEMOTED"]
    assert len(demoted) == recorded["counts"]["demoted"] == 74
    for row in demoted:
        assert bundled[row["rule_id"]].mode == "diagnostic", row["rule_id"]
        assert bundled[row["rule_id"]].action.type == "none", row["rule_id"]
        assert bundled[row["rule_id"]].version == 1, row["rule_id"]


def test_each_demotion_rests_on_a_sentence_it_broke(recorded):
    for row in recorded["rules"]:
        failing = [probe for probe in row["probes"] if probe["verdict"] == "fails"]
        if row["disposition"] == "QUALIFIED_SAFE":
            assert not failing and not row["finding"], row["rule_id"]
        elif row["finding"] == "never-applied":
            assert not any(probe["fired_2026_7"] for probe in row["probes"]), row["rule_id"]
            assert all(probe["refused_2026_7"] for probe in row["probes"]), row["rule_id"]
        else:
            assert failing, row["rule_id"]
            for probe in failing:
                assert probe["fired_2026_7"], (row["rule_id"], probe["input"])
                assert probe["output_2026_7"] != probe["input"], (row["rule_id"], probe["input"])


def test_every_retained_rule_covers_every_context_group(recorded):
    for row in recorded["rules"]:
        groups = {probe["group"] for probe in row["probes"]}
        assert groups == {"normal", "adversarial", "specialist", "control"}, row["rule_id"]


def _retained_controls():
    data = json.loads((HERE / "ledger.json").read_bytes().decode("utf-8"))
    return [
        (row["rule_id"], probe["input"], probe["output_now"])
        for row in data["rules"] if row["disposition"] == "QUALIFIED_SAFE"
        for probe in row["probes"] if probe["group"] == "control"
    ]


@pytest.mark.parametrize("rule_id,sentence,expected", _retained_controls(),
                         ids=lambda value: value if isinstance(value, str) and value.startswith("PS.") else "")
@pytest.mark.parametrize("profile", ["natural", "plain", "technical", "government", "academic"])
def test_retained_rules_still_apply_their_controls_under_every_profile(rule_id, sentence, expected, profile):
    result = present_text(sentence + "\n", profile)
    assert rule_id in {item.rule_id for item in result.applied}
    assert result.text.rstrip("\n") == expected
