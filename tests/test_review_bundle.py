"""The review facade: the join the desktop is forbidden to make itself.

Four authorities have something to say about a document, and something has to
put them together. That something is the pipeline, and these tests are what stop
it being a widget instead.

The mapping group is the sharp end. "Source offset plus accumulated lengths" is
the obvious way to work out where a change ended up, it is wrong the first time
two edits are adjacent, and it is wrong in a way nobody notices until a
highlight lands two characters off in a document nobody is looking at closely.
Every case below asserts that a mapped range actually contains the text it
claims to.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from plainspeak.pipeline import (
    REVIEWABLE_SUFFIXES,
    build_review_bundle,
    engine_identities,
    is_reviewable_path,
    load_reviewable,
    parse_source,
)
from plainspeak.pipeline.review import (
    KIND_REFUSED,
    KIND_SAFE,
    KIND_STYLE,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    ReviewError,
)
from plainspeak.pipeline.style_plan import STATUS_REVIEW_REQUIRED

FIXTURES = Path(__file__).resolve().parent / "style" / "stylefix"
CORPUS = Path(__file__).resolve().parent / "style" / "corpus"
PROFILES = Path(__file__).resolve().parent / "style" / "profiles"


def bundle_for(path: Path, profile: str = "natural"):
    return build_review_bundle(load_reviewable(path), profile)


def every_range_is_accurate(preview) -> list[str]:
    """Check that each change's ranges contain what the change says they do."""
    problems = []
    for item in preview.changes:
        source = preview.source_text[item.source_start:item.source_end]
        if source != item.before:
            problems.append(f"{item.change_id}: source has {source!r}, expected {item.before!r}")

        expected = item.after if item.status in ("applied", STATUS_ACCEPTED) else item.before
        revised = preview.revised_text[item.revised_start:item.revised_end]
        if revised != expected:
            problems.append(
                f"{item.change_id}: revised has {revised!r}, expected {expected!r}"
            )
    return problems


# ── Supported formats ──────────────────────────────────────────────────────


def test_only_text_and_markdown_are_reviewable() -> None:
    assert REVIEWABLE_SUFFIXES == (".txt", ".md", ".markdown")
    for name in ("a.txt", "a.md", "a.markdown", "A.MD"):
        assert is_reviewable_path(name)
    for name in ("a.docx", "a.pdf", "a.html", "a.rtf", "a"):
        assert not is_reviewable_path(name)


@pytest.mark.parametrize("suffix", [".docx", ".pdf", ".html"])
def test_a_structured_format_is_refused_with_an_explanation(suffix: str, tmp_path) -> None:
    """Refused by name, not opened through the plain-text degradation path.

    Those formats do load — as undifferentiated text — and analysing them that
    way is an honest fallback. Presenting a *revised* one would not be: a reader
    would reasonably assume the structure had survived, and nothing in the
    engine can promise that.
    """
    target = tmp_path / f"document{suffix}"
    target.write_bytes(b"content")

    with pytest.raises(ReviewError, match="Markdown"):
        load_reviewable(target)


def test_a_missing_file_is_named(tmp_path) -> None:
    with pytest.raises(ReviewError, match="not found"):
        load_reviewable(tmp_path / "absent.md")


# ── The bundle ─────────────────────────────────────────────────────────────


def test_a_profile_is_mandatory() -> None:
    with pytest.raises(ReviewError, match="explicit profile"):
        build_review_bundle(parse_source("Some prose.\n"), None)


def test_the_bundle_carries_every_authority() -> None:
    identities = bundle_for(FIXTURES / "concessive-heavy.md").identities()

    for key in (
        "input_sha256", "ruleset_sha256", "ruleset_version",
        "integrity_policy_sha256", "morphology_sha256", "style_policy_sha256",
        "profile_pack_sha256", "profile_sha256", "profile_id", "plan_sha256",
    ):
        assert identities.get(key), f"{key} missing"


def test_the_bundle_reports_all_four_authorities_worth_of_findings() -> None:
    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    preview = bundle.preview()
    kinds = {item.kind for item in preview.changes}

    assert KIND_SAFE in kinds, "the rule engine"
    assert KIND_STYLE in kinds, "the style layer, read through a profile"
    assert bundle.diagnostics(), "the style measurements"
    assert bundle.identities(), "the identities behind all of it"


def test_diagnostics_carry_their_evidence() -> None:
    for item in bundle_for(FIXTURES / "concessive-heavy.md").diagnostics():
        assert item.message and item.severity
        assert item.sample_size > 0
        assert item.evidence, f"{item.id} has no evidence a reader could check"


# ── Mapping ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    sorted(
        [p for p in CORPUS.glob("*.md") if p.stem != "README"]
        + list(FIXTURES.glob("*.md"))
        + list(PROFILES.rglob("*.md"))
    ),
    ids=lambda p: f"{p.parent.name}/{p.stem}",
)
def test_every_mapped_range_is_accurate_with_no_decisions(path: Path) -> None:
    """Across both corpora and every fixture, with safe fixes applied."""
    assert every_range_is_accurate(bundle_for(path).preview()) == []


def test_mapping_survives_multiple_earlier_edits() -> None:
    """Every combination of accepted and rejected, on a document with four.

    Multiple earlier insertions and deletions are exactly the case a naive
    accumulation gets wrong, so all sixteen combinations are checked rather than
    a representative one.
    """
    from itertools import combinations

    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    identifiers = [item.proposal_id for item in bundle.reviewable]
    assert len(identifiers) == 4

    for size in range(len(identifiers) + 1):
        for accepted in combinations(identifiers, size):
            rejected = [i for i in identifiers if i not in accepted]
            preview = bundle.preview(accepted=accepted, rejected=rejected)
            assert every_range_is_accurate(preview) == [], f"accepted={accepted}"


def test_mapping_is_accurate_with_adjacent_edits() -> None:
    """Two changes that touch, so one begins exactly where the other ends."""
    source = "The team utilise the register. The team utilise the archive.\n"
    bundle = build_review_bundle(parse_source(source), "natural")
    preview = bundle.preview()

    assert len(preview.of_kind(KIND_SAFE)) >= 2
    assert every_range_is_accurate(preview) == []


def test_mapping_is_accurate_with_non_ascii_text() -> None:
    """Offsets are in characters, and the text has some worth counting."""
    source = (
        "# Café notes — 21 °C\n\n"
        "The team utilise the naïve method. Results were «good».\n\n"
        "Nevertheless, the café closed. Nevertheless, it reopened.\n"
        "Nevertheless, nobody noticed. Nevertheless, the sign stayed.\n"
    )
    preview = build_review_bundle(parse_source(source), "natural").preview()

    assert every_range_is_accurate(preview) == []
    assert "café" in preview.revised_text and "°C" in preview.revised_text


def test_mapping_is_accurate_with_crlf_source() -> None:
    source = (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8")
    bundle = build_review_bundle(parse_source(source.replace("\n", "\r\n")), "natural")
    identifiers = [item.proposal_id for item in bundle.reviewable]

    preview = bundle.preview(accepted=identifiers[:2], rejected=identifiers[2:])
    assert every_range_is_accurate(preview) == []


def test_mapping_is_accurate_across_markdown_markup() -> None:
    """Prose spans separated by emphasis, links and code, which are not prose."""
    source = (
        "# Heading\n\n"
        "The team **utilise** the register, and `utilise` appears in code too.\n\n"
        "See [the guide](https://example.invalid/utilise) for more.\n\n"
        "Nevertheless, the team utilise it. Nevertheless, so does everyone.\n"
        "Nevertheless, nobody minds. Nevertheless, the guide stands.\n"
    )
    bundle = build_review_bundle(parse_source(source), "natural")
    preview = bundle.preview(accepted=[i.proposal_id for i in bundle.reviewable])

    assert every_range_is_accurate(preview) == []
    # Code and a URL are not prose and must be untouched.
    assert "`utilise`" in preview.revised_text
    assert "https://example.invalid/utilise" in preview.revised_text


# ── Decisions ──────────────────────────────────────────────────────────────


def test_accepting_uses_the_phase_nine_review_contract() -> None:
    """Not a boolean the interface keeps to itself.

    Acceptance builds a real `ReviewSubmission` bound to the plan hash and goes
    through `approve_style_changes`, so freshness and atomicity apply here
    exactly as they do anywhere else.
    """
    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    with pytest.raises(Exception) as raised:
        bundle.preview(accepted=["SP-notarealproposal"])
    assert "does not contain" in str(raised.value)


def test_a_rejected_proposal_keeps_the_original_text() -> None:
    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    identifiers = [item.proposal_id for item in bundle.reviewable]
    preview = bundle.preview(rejected=identifiers)

    assert preview.revised_text.count("Nevertheless,") == 6
    assert all(
        item.status == STATUS_REJECTED
        for item in preview.changes
        if item.change_id in identifiers
    )


def test_a_rejected_proposal_does_not_silence_the_diagnostic() -> None:
    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    before = {item.id for item in bundle.diagnostics()}
    bundle.preview(rejected=[item.proposal_id for item in bundle.reviewable])

    assert {item.id for item in bundle.diagnostics()} == before


def test_accepting_and_rejecting_the_same_proposal_prefers_acceptance() -> None:
    """A contradiction the interface should not send, resolved deterministically."""
    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    identifier = bundle.reviewable[0].proposal_id
    preview = bundle.preview(accepted=[identifier], rejected=[identifier])

    assert preview.change(identifier).status == STATUS_ACCEPTED


def test_previewing_never_re_plans() -> None:
    """The bundle is a snapshot. Deciding selects; it does not re-decide."""
    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    plan_hash = bundle.style_plan.plan_hash
    identifiers = [item.proposal_id for item in bundle.reviewable]

    for size in range(len(identifiers) + 1):
        bundle.preview(accepted=identifiers[:size])
        assert bundle.style_plan.plan_hash == plan_hash


def test_the_preview_is_deterministic() -> None:
    bundle = bundle_for(FIXTURES / "concessive-heavy.md")
    identifiers = [item.proposal_id for item in bundle.reviewable]

    first = bundle.preview(accepted=identifiers[:2])
    second = bundle.preview(accepted=identifiers[:2])
    assert first.output_hash == second.output_hash
    assert first.revised_text == second.revised_text


# ── Refusals ───────────────────────────────────────────────────────────────


def test_refusals_are_reported_and_never_applicable() -> None:
    for path in sorted(CORPUS.glob("*.md")):
        if path.stem == "README":
            continue
        preview = bundle_for(path).preview()
        for item in preview.of_kind(KIND_REFUSED):
            assert item.refusal, "a refusal with no reason is not reviewable"
            assert item.badge == "REFUSED"
            assert not item.is_reviewable


def test_a_refused_change_is_not_in_the_revised_text() -> None:
    bundle = bundle_for(CORPUS / "government.md")
    preview = bundle.preview()
    for item in preview.of_kind(KIND_REFUSED):
        assert preview.revised_text[item.revised_start:item.revised_end] == item.before


# ── Identity facade ────────────────────────────────────────────────────────


def test_engine_identities_reports_every_family() -> None:
    """The desktop needs these and may not gather them from five packages."""
    identity = engine_identities()

    assert identity["ruleset_version"] == "2026.3"
    assert identity["ruleset_count"] == 222
    assert identity["style_fix_count"] == 8
    assert identity["style_fixes_all_review_required"] is True
    assert identity["profiles"] == ("natural", "plain", "technical", "government", "academic")
    assert len(identity["profile_hashes"]) == 5
    assert identity["syllable_entries"] >= 100_000
    assert identity["syllable_uses_dictionary"] is True
    for key in (
        "ruleset_sha256", "integrity_sha256", "morphology_sha256",
        "style_policy_sha256", "profile_pack_sha256",
    ):
        assert len(identity[key]) == 64


def test_engine_identities_matches_what_a_bundle_reports() -> None:
    """One source of truth, checked from both ends."""
    identity = engine_identities()
    bundle = bundle_for(FIXTURES / "concessive-heavy.md").identities()

    assert bundle["ruleset_sha256"] == identity["ruleset_sha256"]
    assert bundle["style_policy_sha256"] == identity["style_policy_sha256"]
    assert bundle["profile_pack_sha256"] == identity["profile_pack_sha256"]
