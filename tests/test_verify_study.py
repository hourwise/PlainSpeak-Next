"""The V2 validation study, held as a regression suite.

validation/verify-study/cases.yaml holds 97 before/after pairs with a manual
judgement each, written before Verify was run. results.json records what
Verify said. These tests re-run the study and require:

- no false acceptance at all — ACCEPTED on a transformation judged to have
  changed meaning — and in particular none of protected meaning;
- every PlainSpeak transformation ACCEPTED;
- results identical to the recorded ones, so a change to Verify's behaviour on
  any case is a deliberate, reviewed update of results.json and VERIFY_STUDY.md
  rather than a silent drift.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

STUDY = Path(__file__).resolve().parent.parent / "validation" / "verify-study"


@pytest.fixture(scope="module")
def study():
    spec = importlib.util.spec_from_file_location("run_study", STUDY / "run_study.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def results(study):
    return study.run()


def test_there_is_no_false_acceptance(results):
    false = {key: value["note"] for key, value in results.items()
             if value["outcome"].startswith("false acceptance")}
    assert not false, false


def test_plainspeak_accepts_its_own_work(results):
    own = {key: value for key, value in results.items() if value["class"] == "plainspeak"}
    assert len(own) == 27
    assert {value["result"] for value in own.values()} == {"ACCEPTED"}


def test_the_probes_that_found_defects_stay_fixed(results):
    """X02 was a false acceptance of protected meaning under policy 2026.1; X04 another."""
    assert results["X02"]["result"] == "INCONCLUSIVE"
    assert results["X04"]["result"] == "INCONCLUSIVE"
    assert results["X03"]["result"] == "ACCEPTED"


def test_every_judgement_is_complete(study):
    for case in study.cases():
        assert case["meaning"] in ("preserved", "changed"), case["id"]
        assert isinstance(case["protected"], bool), case["id"]
        assert case["producer"] and case["note"], case["id"]
        if case["meaning"] == "preserved":
            assert case["protected"] is False, case["id"]


def test_the_recorded_results_are_current(results):
    recorded = json.loads((STUDY / "results.json").read_text(encoding="utf-8"))
    assert results == recorded


def test_the_independent_review_bundle_is_current():
    """REVIEW_BUNDLE.md is generated; a stale one would show a reviewer old results."""
    spec = importlib.util.spec_from_file_location("review_bundle", STUDY / "review_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.render() == (STUDY / "REVIEW_BUNDLE.md").read_bytes().decode("utf-8")
