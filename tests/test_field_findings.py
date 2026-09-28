"""Field findings from testing the published 1.0.0, held as permanent regressions.

FIELD-001  an unsafe SAFE rule: "facilitate the completion of" became
           "help the completion of"; and the bounded audit that followed.
FIELD-002  piped text without --stdin, and the required profile, were hard to
           discover from the CLI.
FIELD-003  `analyze` presented a three-word text as grade 2, "Very easy", with
           "no significant readability barriers".

Also here: the behaviours field testing confirmed, so they stay confirmed.
See V2_FIELD_FINDINGS.md.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from plainspeak.adapters.cli import main
from plainspeak.pipeline import present_text
from plainspeak.rules import load_ruleset

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def ruleset():
    return load_ruleset()


# ── FIELD-001 ───────────────────────────────────────────────────────────────

PUBLISHED_INPUT = "In order to facilitate the completion of the task, the user should verify the configuration.\n"


def test_field_001_the_published_failure_is_fixed():
    result = present_text(PUBLISHED_INPUT, "natural")
    # Ruleset 2026.6 stopped "facilitate" -> "help"; 2026.7 also stopped
    # "in order to" -> "to" (V2-F), so the published sentence is now left as it is.
    assert result.text == PUBLISHED_INPUT
    assert result.applied == ()


@pytest.mark.parametrize("sentence", [
    "In order to facilitate the completion of the task, the user should verify the configuration.",
    "The portal facilitates access to your records.",
    "The new tool facilitates communication between teams.",
    "This service facilitates the transfer of funds.",
    "The chair will facilitate discussion.",
    "The app is designed to facilitate payment.",
    "We facilitated a workshop for staff.",
    "She was facilitating the meeting.",
])
def test_field_001_facilitate_is_never_rewritten_automatically(sentence):
    """"Facilitate X" is "make X easier"; "help X" is "assist X". No context rule separates them."""
    text = present_text(sentence + "\n", "natural").text
    assert "facilitat" in text and not re.search(r"\bhelp(s|ed|ing)?\b", text)


#: Every rule the field review reclassified, with a sentence it broke. The
#: failure must stay gone, the rule must stay a diagnostic, and its ID must not
#: move: an audit record may name it.
RECLASSIFIED = {
    "PS.LEXICAL.153": ("facilitate", "The portal facilitates access to your records.", "helps access"),
    "PS.LEXICAL.120": ("comprise", "The committee comprises five members.", "makes up five"),
    "PS.LEXICAL.125": ("constitute", "This action constitutes a breach of contract.", "makes up a breach"),
    "PS.LEXICAL.211": ("reimburse", "We will reimburse you for the cost.", "pay back you"),
    "PS.LEXICAL.212": ("relinquish", "You must relinquish it before leaving.", "give up it"),
    "PS.LEXICAL.226": ("substantiate", "Please substantiate it with evidence.", "back up it"),
    "PS.LEXICAL.231": ("transcribe", "Please transcribe it by Friday.", "write down it"),
    "PS.LEXICAL.151": ("expedite", "We can expedite it for you.", "speed up it"),
    "PS.LEXICAL.142": ("effectuate", "The board will effectuate it.", "carry out it"),
    "PS.LEXICAL.139": ("disburse", "The fund will disburse them monthly.", "pay out them"),
    "PS.LEXICAL.010": ("ascertain", "We will ascertain it quickly.", "find out it"),
    "PS.LEXICAL.115": ("cease", "The company will cease to exist.", "stop to exist"),
    "PS.LEXICAL.113": ("augment", "Augmented reality is growing.", "Added to reality"),
    "PS.LEXICAL.168": ("impair", "Impaired vision can be treated.", "Harmed vision"),
    "PS.LEXICAL.204": ("preserve", "Preserved food lasts longer.", "Kept food"),
    "PS.LEXICAL.102": ("acquire", "The data was acquired over three years.", "was got"),
    "PS.LEXICAL.124": ("consolidate", "We will consolidate our position.", "combine our position"),
    "PS.LEXICAL.180": ("mitigate", "We must mitigate against flooding.", "reduce against"),
    "PS.LEXICAL.237": ("validate", "We validate the input.", "confirm the input"),
    "PS.LEXICAL.189": ("obligation", "Your payment obligations are listed below.", "payment duties"),
    "PS.LEXICAL.119": ("comprehensive", "You need comprehensive insurance for the car.", "full insurance"),
    "PS.LEXICAL.128": ("contemporary", "Contemporary accounts describe the fire of 1666.", "Modern accounts"),
    "PS.LEXICAL.203": ("preliminary", "The preliminary hearing is on Monday.", "early hearing"),
    "PS.LEXICAL.239": ("viable", "A viable pregnancy was confirmed.", "workable pregnancy"),
    "PS.LEXICAL.236": ("unilateral", "It was a unilateral decision by the landlord.", "one-sided decision"),
    "PS.LEXICAL.209": ("quantitative", "The bank began quantitative easing.", "numerical easing"),
    "PS.LEXICAL.208": ("qualitative", "We used qualitative research methods.", "descriptive research"),
    "PS.LEXICAL.155": ("feasible", "It is feasible to finish by Friday.", "workable to finish"),
    # V2-F: the independent review of the Verify study's accepted SAFE substitutions.
    "PS.LEXICAL.186": ("notify", "The tenant must notify the authority in writing within 14 days.",
                       "must tell the authority"),
    "PS.LEXICAL.221": ("retain", "The company reported £5 million in retained earnings.", "kept earnings"),
    "PS.LEXICAL.182": ("modify", "The patient must not crush modified-release tablets.", "changed-release"),
    "PS.LEXICAL.147": ("enhance", "Staff need an enhanced DBS check.", "improved DBS"),
    "PS.LEXICAL.200": ("possess", "It is an offence to possess a controlled drug.", "to have a controlled"),
    "PS.LEXICAL.161": ("furthermore", "The tenant, furthermore, must pay the fee.", ", also,"),
    "PS.LEXICAL.183": ("moreover", "The rent, moreover, is due monthly.", ", also,"),
    "PS.LEXICAL.103": ("additionally", "The fee is, additionally, non-refundable.", ", also,"),
    "PS.LEXICAL.009": ("additional", "You pay tax at the additional rate.", "extra rate"),
    "PS.CLARITY.001": ("in-order-to", "Keep your papers in order to avoid delays.", "papers to avoid"),
    # Found alongside the V2-F review, the same defect shape.
    "PS.LEXICAL.101": ("accordingly", "Please act accordingly.", "act so"),
    "PS.LEXICAL.122": ("consequently", "The rent was, consequently, increased.", ", so,"),
    "PS.LEXICAL.164": ("hereafter", "The Company (hereafter the Seller) agrees.", "from now on"),
    "PS.CLARITY.007": ("a-large-number-of", "A large number of them were late.", "Many them"),
}


@pytest.mark.parametrize("rule_id", sorted(RECLASSIFIED))
def test_field_001_reclassified_rules_stay_diagnostics_under_their_ids(ruleset, rule_id):
    term, sentence, broken = RECLASSIFIED[rule_id]
    rule = next(rule for rule in ruleset.rules if rule.id == rule_id)
    assert rule.mode == "diagnostic"
    assert term in rule.name
    text = present_text(sentence + "\n", "natural").text
    assert broken not in text
    assert text.strip() == sentence


HAND_AUTHORED = {"PS.LEXICAL.010", "PS.LEXICAL.009", "PS.CLARITY.001", "PS.CLARITY.007"}


def test_field_001_rule_ids_are_bound_to_their_terms():
    registry = json.loads((ROOT / "migration" / "rule-ids.json").read_text(encoding="utf-8"))
    for rule_id, (term, _sentence, _broken) in RECLASSIFIED.items():
        if rule_id not in HAND_AUTHORED:  # not in the migration registry
            assert registry[term] == rule_id


#: "approximately", "obtain", "reside" and "henceforth" passed this audit and
#: were here too, until the safe-rule qualification (ruleset 2026.8) probed
#: every automatic rule more widely and demoted them; see
#: SAFE_RULE_QUALIFICATION.md, which holds the qualified rules to their controls.
@pytest.mark.parametrize("before,after", [
    ("Please utilise the form.", "Please use the form."),
    ("Work will commence on Monday.", "Work will start on Monday."),
    ("We will relocate the office.", "We will move the office."),
    ("Stress can exacerbate symptoms.", "Stress can worsen symptoms."),
])
def test_field_001_audited_rules_that_passed_still_apply(before, after):
    assert present_text(before + "\n", "natural").text.strip() == after


#: Particles that make a phrasal verb separable: "find out" must become
#: "find it out" before a pronoun, which a context-free substitution cannot do.
SEPARABLE_PARTICLES = {"up", "out", "down", "back", "off", "over", "away"}
#: Phrasal replacements that take no object, so nothing can come between.
INTRANSITIVE_PHRASAL = {"step in"}


def test_field_001_no_automatic_rule_replaces_a_verb_with_a_separable_phrasal_verb(ruleset):
    """The defect shape the audit found eight times ("pay back you", "give up it")."""
    offenders = []
    for rule in ruleset.rules:
        if rule.mode != "safe-fix" or rule.match.type not in ("lemma", "word"):
            continue
        replacement = (getattr(rule.action, "lemma", None) or rule.action.replacement or "").lower()
        words = replacement.split()
        if len(words) == 2 and words[1] in SEPARABLE_PARTICLES and replacement not in INTRANSITIVE_PHRASAL:
            offenders.append(f"{rule.id} -> {replacement}")
    assert not offenders, offenders


def test_field_001_the_ruleset_records_the_reclassification(ruleset):
    assert ruleset.version == "2026.8"
    assert len(ruleset) == 220
    assert len([rule for rule in ruleset.rules if rule.mode == "safe-fix"]) == 23


# ── FIELD-003 ───────────────────────────────────────────────────────────────


def analyze(text: str, *extra: str):
    return CliRunner().invoke(main, ["analyze", "--stdin", *extra], input=text)


def test_field_003_a_tiny_text_is_an_insufficient_sample_not_a_verdict():
    result = analyze("Please check this.")
    assert result.exit_code == 0
    assert "INSUFFICIENT SAMPLE" in result.output
    assert "3 words in 1 sentence" in result.output
    assert "Very easy" not in result.output
    assert "too little text to call the" in result.output
    # The raw formula outputs are kept.
    assert "Flesch Reading Ease:        100.0" in result.output
    assert "Consensus Grade Level: 2.0  (this sample only)" in result.output


def test_field_003_json_gains_a_sample_object_and_keeps_every_field(tmp_path):
    target = tmp_path / "report.json"
    assert analyze("Please check this.", "--json", str(target)).exit_code == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["sample"]["status"] == "insufficient_sample"
    assert data["sample"]["minimum_words"] == 100 and data["sample"]["minimum_sentences"] == 3
    assert data["readability_scores"]["flesch_reading_ease"] == 100.0
    assert data["consensus"]["grade_level"] == 2.0
    assert set(data) >= {"tool", "version", "statistics", "readability_scores", "consensus",
                         "simplification", "text_preview", "sample"}


def _words(count: int, sentences: int) -> str:
    per = count // sentences
    extra = count - per * sentences
    parts = []
    for index in range(sentences):
        size = per + (1 if index < extra else 0)
        # Capitalised, so the sentence splitter sees each full stop as a boundary.
        parts.append(" ".join(["Word"] + ["word"] * (size - 1)) + ".")
    return " ".join(parts)


@pytest.mark.parametrize("words,sentences,status", [
    (3, 1, "insufficient_sample"),
    (99, 5, "insufficient_sample"),
    (150, 2, "insufficient_sample"),
    (100, 3, "limited_sample"),
    (299, 10, "limited_sample"),
    (300, 10, "sufficient"),
])
def test_field_003_the_threshold_is_deterministic(words, sentences, status):
    from plainspeak.core.metrics import analyze as measure, sample_status

    scores = measure(_words(words, sentences))
    assert (scores.total_words, scores.total_sentences) == (words, sentences)
    assert sample_status(scores) == status


def test_field_003_the_html_report_does_not_call_a_tiny_text_easy(tmp_path):
    target = tmp_path / "report.html"
    assert analyze("Please check this.", "--output", str(target)).exit_code == 0
    page = target.read_text(encoding="utf-8")
    assert "Insufficient sample." in page
    assert "Not a judgement of the text: insufficient sample" in page


def test_field_003_diagnose_reports_the_sample_status():
    from plainspeak.pipeline import diagnose_text

    assert diagnose_text("Please check this.\n", "natural").as_dict()["readability"]["sample_status"] \
        == "insufficient_sample"


def test_field_003_the_web_page_says_not_enough_text():
    pytest.importorskip("flask")
    from plainspeak.adapters.web import create_app

    client = create_app().test_client()
    data = client.post("/api/analyze", json={"text": "Please check this."}).get_json()
    assert data["sample_status"] == "insufficient_sample"
    source = (ROOT / "plainspeak" / "adapters" / "web.py").read_text(encoding="utf-8")
    assert "'Not enough text'" in source


# ── FIELD-002 ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("command,code", [
    (["analyze"], 1),
    (["present", "--profile", "natural"], 2),
    (["diagnose", "--profile", "natural"], 2),
])
def test_field_002_piped_text_without_stdin_is_explained_not_guessed(command, code):
    result = CliRunner().invoke(main, command, input="Some text.")
    assert result.exit_code == code  # unchanged: nothing is read implicitly
    assert "Add --stdin" in result.output
    assert "--stdin" in result.output and "Found 0" not in result.output


def test_field_002_help_shows_stdin_and_the_required_profile():
    for command in ("present", "analyze"):
        page = CliRunner().invoke(main, [command, "--help"]).output
        assert "--stdin" in page and "| plainspeak" in page
    assert "no default" in CliRunner().invoke(main, ["present", "--help"]).output


# ── Behaviours field testing confirmed ─────────────────────────────────────


def test_file_and_stdin_give_the_same_transformation(tmp_path):
    text = "Prior to finishing, utilise the portal.\n"
    source = tmp_path / "doc.md"
    source.write_bytes(text.encode("utf-8"))
    from_file = json.loads(CliRunner().invoke(main, ["present", str(source), "--profile", "natural"]).output)
    from_stdin = json.loads(CliRunner().invoke(main, ["present", "--stdin", "--profile", "natural"],
                                               input=text).output)
    assert from_file["output"]["text"] == from_stdin["output"]["text"]
    assert from_file["input"]["sha256"] == from_stdin["input"]["sha256"]
    assert from_file["applied"] == from_stdin["applied"]


def test_hashes_see_a_terminal_newline():
    with_newline = present_text("Please use the form.\n", "natural").as_dict()["input"]["sha256"]
    without = present_text("Please use the form.", "natural").as_dict()["input"]["sha256"]
    assert with_newline != without


@pytest.mark.parametrize("text", [
    "# In order to utilise the portal\n\nBody text.\n",
    "Run `utilise --now` in order to start.\n",
    "See [the guide](https://example.com/utilise?in-order-to=1) for approximately 5 steps.\n",
    "Visit https://example.com/prior-to/utilise today.\n",
])
def test_markdown_structure_code_and_links_survive(text):
    result = present_text(text, "natural").text
    for kept in ("# ", "`utilise --now`", "(https://example.com/utilise?in-order-to=1)",
                 "https://example.com/prior-to/utilise"):
        if kept in text:
            assert kept in result


@pytest.mark.parametrize("text", [
    "You must not utilise the old portal.\n",
    "You may not commence work before 1 July.\n",
    "Staff should never exceed 0.5 mg.\n",
])
def test_negation_and_modals_survive(text):
    result = present_text(text, "natural")
    from plainspeak.pipeline import verify_text

    assert result.as_dict()["protected"]["preserved"] is True
    assert verify_text(text, result.text).result == "ACCEPTED"
    for word in ("must not", "may not", "never", "should"):
        if word in text:
            assert word in result.text
