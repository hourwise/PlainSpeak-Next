"""What changes between profiles, and — more importantly — what does not.

The claim Phase 8 makes is narrow and needs to be checked from both sides: the
same document read against five profiles produces five interpretations of *one*
measurement. If the metrics differ by profile, profile semantics have leaked into
measurement and the layering has failed silently, so that invariant is asserted
byte-for-byte rather than approximately.

The other half is that Phase 7 still answers exactly what it answered before.
Profiles exist alongside the baseline, not instead of it, and an existing caller
must not be able to tell that this phase happened.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plainspeak.document import parse_markdown
from plainspeak.pipeline.styling import (
    analyze_style,
    analyze_style_with_profile,
    compare_style_profiles,
    observe_style,
)
from plainspeak.style import (
    analysis_digest,
    analysis_to_json,
    compare_profiles,
    interpret,
    interpret_baseline,
    observe,
    policy,
    profile_ids,
    profiled_digest,
    profiled_to_json,
)
from plainspeak.style.profiles import load_pack, pack_hash

CORPUS = Path(__file__).resolve().parent / "style" / "corpus"
PROFILES = Path(__file__).resolve().parent / "style" / "profiles"

ALL = tuple(profile_ids())


def document(path: Path):
    return parse_markdown.parse(path.read_text(encoding="utf-8"))


def everything() -> list[Path]:
    return sorted(
        [path for path in CORPUS.glob("*.md") if path.stem != "README"]
        + [path for path in PROFILES.rglob("*.md")]
    )


# ── Metrics do not move ────────────────────────────────────────────────────


@pytest.mark.parametrize("path", everything(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_every_profile_sees_identical_metrics(path: Path) -> None:
    """The invariant the whole architecture exists to guarantee.

    A profile holds numbers to compare against. It never touches the text, so it
    cannot change what the text measures. If this ever fails, interpretation has
    acquired a measurement of its own and the two halves need separating again —
    relaxing the test would be the wrong repair.
    """
    results = compare_style_profiles(document(path))
    rendered = {
        identifier: json.dumps(analysis.metrics.as_dict(), sort_keys=True)
        for identifier, analysis in results.items()
    }
    assert len(set(rendered.values())) == 1, (
        f"{path.name}: profiles disagree about the metrics — "
        f"{sorted(rendered)} produced {len(set(rendered.values()))} distinct sets"
    )


@pytest.mark.parametrize("path", everything(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_profiled_metrics_match_the_baseline_metrics(path: Path) -> None:
    """And they match what the unprofiled analysis reports, too."""
    doc = document(path)
    baseline = analyze_style(doc).metrics.as_dict()
    for identifier in ALL:
        assert analyze_style_with_profile(doc, identifier).metrics.as_dict() == baseline


@pytest.mark.parametrize("path", everything(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_evidence_does_not_move_between_profiles(path: Path) -> None:
    """Where a diagnostic speaks under two profiles, it quotes the same places.

    Severity may differ. The occurrences behind it may not — a second pattern
    recogniser per profile would be a second thing that could disagree with the
    first.
    """
    results = compare_style_profiles(document(path))
    seen: dict[str, tuple] = {}
    for identifier, analysis in results.items():
        for finding in analysis.findings:
            fingerprint = (
                finding.value,
                finding.sample_size,
                tuple(
                    (item.label, item.count, tuple(o.location for o in item.occurrences))
                    for item in finding.evidence
                ),
            )
            if finding.id in seen:
                assert seen[finding.id] == fingerprint, (
                    f"{path.name}: {finding.id} reports different evidence under "
                    f"{identifier} than under another profile"
                )
            seen[finding.id] = fingerprint


# ── Baseline compatibility ─────────────────────────────────────────────────

#: Pinned before Phase 8 began, from the Phase 7 suite. Profiles must not move it.
BASELINE_DIGESTS = {
    "transition_heavy": "903209e323beff7326aa496a025fcc1d33e17bf49542d7f7b867e0a7dc37cd4a",
    "long_natural": "4d0a1510e029d798cf094142c0224fcd76c9e264652550d29974f719051722ca",
}


@pytest.mark.parametrize("name,expected", sorted(BASELINE_DIGESTS.items()))
def test_the_baseline_analysis_is_byte_identical_to_phase_seven(
    name: str, expected: str
) -> None:
    """The compatibility guarantee, checked against digests that predate Phase 8.

    `analyze` was rewritten this phase — measurement and judgement were split so
    that one measurement could feed many profiles — and these two numbers are the
    evidence that the rewrite changed nothing an existing caller can observe.
    """
    assert analysis_digest(analyze_style(document(CORPUS / f"{name}.md"))) == expected


def test_the_baseline_report_names_no_profile() -> None:
    """An unprofiled analysis is not secretly the natural profile."""
    rendered = analysis_to_json(analyze_style(document(CORPUS / "transition_heavy.md")))
    record = json.loads(rendered)

    assert "profile_pack_sha256" not in record
    for identifier in ALL:
        assert f'"{identifier}"' not in rendered


def test_observe_then_interpret_baseline_equals_analyze() -> None:
    for path in everything()[:6]:
        doc = document(path)
        direct = analyze_style(doc)
        staged = interpret_baseline(observe_style(doc))
        assert analysis_digest(direct) == analysis_digest(staged)


# ── Interpretation differs ─────────────────────────────────────────────────


def test_the_same_document_gets_different_severities() -> None:
    """The brief's first example, checked on the document it describes."""
    results = compare_style_profiles(document(PROFILES / "technical" / "queue-consumer.md"))

    technical = {finding.id for finding in results["technical"].findings}
    natural = {finding.id for finding in results["natural"].findings}

    assert policy.LIST_DOMINANCE not in technical, "expected structure in a specification"
    assert policy.LIST_DOMINANCE in natural, "the same structure read as an essay"


def test_a_finding_disappears_legitimately() -> None:
    """Instructional parallelism is correct in one register and a tic in another."""
    results = compare_style_profiles(document(PROFILES / "plain" / "appeal-a-decision.md"))

    assert policy.REPEATED_PARAGRAPH_OPENER in {f.id for f in results["natural"].findings}
    assert policy.REPEATED_PARAGRAPH_OPENER not in {f.id for f in results["plain"].findings}

    # And the underlying number is the same in both.
    natural = next(
        f for f in results["natural"].findings if f.id == policy.REPEATED_PARAGRAPH_OPENER
    )
    observed = observe_style(document(PROFILES / "plain" / "appeal-a-decision.md")).by_id()
    assert observed[policy.REPEATED_PARAGRAPH_OPENER].value == natural.value


def test_a_target_range_result_differs() -> None:
    """The brief's second example: an academic mean is above a plain range."""
    doc = document(PROFILES / "academic" / "measurement-and-construct.md")
    results = compare_style_profiles(doc)

    academic = {t.metric: t.state for t in results["academic"].targets}
    plain = {t.metric: t.state for t in results["plain"].targets}

    assert academic["sentence_words_mean"] == "within"
    assert plain["sentence_words_mean"] == "above"

    # The measurement itself is identical; only the range moved.
    values = {t.metric: t.value for t in results["academic"].targets}
    assert values["sentence_words_mean"] == next(
        t.value for t in results["plain"].targets if t.metric == "sentence_words_mean"
    )


def test_a_contraction_rate_reads_differently_by_register() -> None:
    """The brief's third example."""
    results = compare_style_profiles(
        document(PROFILES / "natural" / "learning-to-cook-late.md")
    )
    natural = {t.metric: t.state for t in results["natural"].targets}
    academic = {t.metric: t.state for t in results["academic"].targets}

    assert natural["contraction_per_1000"] == "within"
    assert academic["contraction_per_1000"] == "above"


def test_outside_a_target_range_is_not_called_a_defect() -> None:
    """Language matters here more than it usually does.

    A document outside a range is very often a document aimed at a different
    reader, and calling that a defect would make the feature actively misleading.
    """
    doc = document(PROFILES / "academic" / "measurement-and-construct.md")
    rendered = profiled_to_json(analyze_style_with_profile(doc, "plain")).lower()

    for word in ("bad", "wrong", "poor", "defect", "violation", "error", "fail"):
        assert word not in rendered, f"target reporting used the word {word!r}"
    assert '"state":"above"' in rendered


def test_profiles_produce_meaningfully_different_answers_somewhere() -> None:
    """Guards against five profiles that agree about every document."""
    differing = 0
    for path in everything():
        results = compare_style_profiles(document(path))
        bands = {
            identifier: tuple(sorted((f.id, f.severity) for f in analysis.findings))
            for identifier, analysis in results.items()
        }
        states = {
            identifier: tuple(sorted((t.metric, t.state) for t in analysis.targets))
            for identifier, analysis in results.items()
        }
        if len(set(bands.values())) > 1 or len(set(states.values())) > 1:
            differing += 1
    assert differing >= 8, f"only {differing} documents are read differently by any profile"


# ── The report ─────────────────────────────────────────────────────────────


def test_a_profiled_report_always_names_its_profile() -> None:
    for identifier in ALL:
        record = json.loads(
            profiled_to_json(
                analyze_style_with_profile(document(CORPUS / "technical.md"), identifier)
            )
        )
        assert record["profile"]["id"] == identifier
        assert record["profile"]["version"] >= 1
        assert len(record["profile"]["sha256"]) == 64
        assert len(record["profile_pack_sha256"]) == 64
        assert record["style_policy"]["sha256"] == policy.policy_hash()


def test_the_profiled_report_is_canonical_json() -> None:
    rendered = profiled_to_json(
        analyze_style_with_profile(document(CORPUS / "technical.md"), "technical")
    )
    assert rendered.endswith("\n")
    assert json.dumps(
        json.loads(rendered), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ) + "\n" == rendered


def test_the_profiled_report_carries_no_timestamp() -> None:
    import re

    rendered = profiled_to_json(
        analyze_style_with_profile(document(CORPUS / "technical.md"), "natural")
    )
    assert not re.search(r"\d{4}-\d{2}-\d{2}", rendered)
    for key in ("timestamp", "generated", "date", "time"):
        assert key not in rendered.lower()


def test_there_is_still_no_score() -> None:
    """Profiles change what is reported, not whether it collapses to a number."""
    from plainspeak.style import ProfiledAnalysis

    fields = set(ProfiledAnalysis.__dataclass_fields__)
    for forbidden in ("score", "rating", "probability", "confidence", "likelihood"):
        assert not any(forbidden in name for name in fields)

    rendered = profiled_to_json(
        analyze_style_with_profile(document(CORPUS / "technical.md"), "natural")
    ).lower()
    for forbidden in ("score", "probability", "likelihood", "authorship", "ai-generated"):
        assert forbidden not in rendered


def test_the_profile_bands_say_what_was_not_assessed() -> None:
    """"Nothing found" and "not looked for" must not read the same."""
    analysis = analyze_style_with_profile(document(CORPUS / "technical.md"), "natural")
    bands = analysis.profile

    assert set(bands) == set(policy.DIAGNOSTIC_IDS)
    assert set(bands.values()) <= {"none", "not-assessed", "info", "notice", "strong"}


def test_profiled_analysis_is_deterministic() -> None:
    doc = document(PROFILES / "technical" / "queue-consumer.md")
    for identifier in ALL:
        first = profiled_digest(analyze_style_with_profile(doc, identifier))
        second = profiled_digest(analyze_style_with_profile(doc, identifier))
        assert first == second


def test_line_endings_do_not_change_a_profiled_analysis() -> None:
    source = (PROFILES / "government" / "help-with-housing-costs.md").read_text(encoding="utf-8")
    lf = parse_markdown.parse(source)
    crlf = parse_markdown.parse(source.replace("\n", "\r\n"))
    for identifier in ALL:
        left = analyze_style_with_profile(lf, identifier)
        right = analyze_style_with_profile(crlf, identifier)
        assert [f.id for f in left.findings] == [f.id for f in right.findings]
        assert [f.severity for f in left.findings] == [f.severity for f in right.findings]
        assert [(t.metric, t.state) for t in left.targets] == [
            (t.metric, t.state) for t in right.targets
        ]


# ── One measurement, many profiles ─────────────────────────────────────────


def test_comparing_five_profiles_measures_once(monkeypatch) -> None:
    """Asserted by counting measurement calls, not by timing.

    A desktop pane that let someone flick between Natural, Technical and Plain
    should not cost three analyses, and the only way to keep that true is to make
    a regression fail the build rather than merely feel slow.
    """
    import sys

    # `plainspeak.style.analyze` the *name* is the function, re-exported by the
    # package. The module is reached through sys.modules.
    analyze_module = sys.modules["plainspeak.style.analyze"]

    calls = {"n": 0}
    original = analyze_module.measure

    def counted(text, structure):
        calls["n"] += 1
        return original(text, structure)

    monkeypatch.setattr(analyze_module, "measure", counted)

    doc = document(PROFILES / "technical" / "queue-consumer.md")
    results = compare_style_profiles(doc)

    assert len(results) == 5
    assert calls["n"] == 1, f"comparing five profiles measured {calls['n']} times"


def test_interpretation_never_touches_the_text(monkeypatch) -> None:
    """The structural reason the metric invariant holds.

    Interpretation is arithmetic over numbers that already exist. If it ever
    started tokenising, the invariant above would become a thing to hope for
    rather than a consequence of the design.
    """
    from plainspeak.style import metrics as metrics_module

    observed = observe_style(document(PROFILES / "natural" / "craft-of-revision.md"))

    calls = {"n": 0}
    original = metrics_module.sentences_of

    def counted(text):
        calls["n"] += 1
        return original(text)

    monkeypatch.setattr(metrics_module, "sentences_of", counted)
    for identifier in ALL:
        interpret(observed, identifier)

    assert calls["n"] == 0, "interpretation re-segmented the text"


def test_comparing_all_profiles_returns_canonical_order() -> None:
    observed = observe_style(document(CORPUS / "technical.md"))
    assert list(compare_profiles(observed)) == list(ALL)


def test_compare_takes_observations_rather_than_a_document() -> None:
    """A signature that took text would invite measuring once per profile."""
    import inspect

    signature = inspect.signature(compare_profiles)
    assert list(signature.parameters) == ["observed", "profiles"]


# ── Independence from the other identities ─────────────────────────────────


def test_no_profile_changes_the_other_four_identities() -> None:
    """Interpretation cannot reach measurement, transformation or safety.

    Loading and applying every profile must leave the ruleset, the integrity
    policy, morphology and the base style policy exactly where they were. This is
    the executable form of the architectural claim.
    """
    from plainspeak.integrity import policy_hash as integrity_hash
    from plainspeak.morphology import policy_hash as morphology_hash
    from plainspeak.rules import load_ruleset

    before = (
        load_ruleset().hash,
        integrity_hash(),
        morphology_hash(),
        policy.policy_hash(),
    )

    doc = document(PROFILES / "technical" / "queue-consumer.md")
    for identifier in ALL:
        analyze_style_with_profile(doc, identifier)

    after = (
        load_ruleset().hash,
        integrity_hash(),
        morphology_hash(),
        policy.policy_hash(),
    )
    assert before == after


def test_the_identities_do_not_vary_by_profile() -> None:
    doc = document(CORPUS / "technical.md")
    reported = {
        analyze_style_with_profile(doc, identifier).policy_hash for identifier in ALL
    }
    assert reported == {policy.policy_hash()}

    packs = {analyze_style_with_profile(doc, identifier).pack_hash for identifier in ALL}
    assert packs == {pack_hash(load_pack())}


def test_style_fix_is_still_rejected() -> None:
    """Phase 8 defines the reference frame. It does not grant edit authority."""
    from plainspeak.rules.schema import MODES

    assert "style-fix" not in MODES


def test_no_profile_can_be_turned_into_an_edit() -> None:
    """Nothing in a resolved profile carries a replacement of any kind."""
    for profile in load_pack():
        rendered = json.dumps(profile.as_dict())
        for word in ("replacement", "rewrite", "synonym", "substitut"):
            assert word not in rendered.lower()
