"""The review session and the save service, with no Qt anywhere.

These are the parts of the desktop that decide things: which state the session
is in, what that state permits, which review decisions are held, and whether a
file may be written. None of them needs an event loop, a widget or a display,
and none of them is allowed to acquire one — a behaviour that can only be
checked by driving a GUI is a behaviour that will stop being checked.

The file-safety group is the important half. PlainSpeak reads a document it does
not own and must not damage it, and every claim about that is asserted against
the filesystem rather than argued from the code.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from plainspeak.desktop.session import (
    DEFAULT_PROFILE,
    ReviewSession,
    SaveError,
    SessionError,
    State,
    save_revised,
)
from plainspeak.pipeline import build_review_bundle, load_reviewable, parse_source

FIXTURES = Path(__file__).resolve().parent / "style" / "stylefix"


def fixture_path(name: str = "concessive-heavy") -> Path:
    return FIXTURES / f"{name}.md"


@pytest.fixture
def ready_session():
    path = fixture_path()
    document = load_reviewable(path)
    session = ReviewSession(DEFAULT_PROFILE)
    session.load(path, document.source)
    generation = session.begin_analysis()
    session.accept_analysis(build_review_bundle(document, DEFAULT_PROFILE), generation)
    return session


# ── The state machine ──────────────────────────────────────────────────────


def test_a_new_session_is_empty_and_can_do_almost_nothing() -> None:
    snapshot = ReviewSession().snapshot()

    assert snapshot.state is State.EMPTY
    assert not snapshot.can_analyze
    assert not snapshot.can_review
    assert not snapshot.can_save


def test_saving_from_empty_is_impossible() -> None:
    """`EMPTY -> SAVE` must not be reachable.

    Checked through the permission the interface actually consults, because that
    is what a disabled menu item is wired to.
    """
    session = ReviewSession()
    assert not session.snapshot().can_save
    with pytest.raises(SessionError):
        session.begin_analysis()


def test_reviewing_before_analysis_is_impossible() -> None:
    session = ReviewSession()
    session.load(fixture_path(), "Some prose.\n")
    with pytest.raises(SessionError, match="cannot review"):
        session.accept("SP-anything")


def test_the_expected_progression(ready_session) -> None:
    assert ready_session.state is State.READY
    proposal = ready_session.bundle.reviewable[0].proposal_id

    ready_session.accept(proposal)
    assert ready_session.state is State.REVIEWED

    ready_session.mark_saved(Path("somewhere.md"))
    assert ready_session.state is State.SAVED
    assert ready_session.snapshot().can_review, "a saved session is still inspectable"


def test_a_failed_analysis_lands_in_error() -> None:
    session = ReviewSession()
    session.load(fixture_path(), "Some prose.\n")
    generation = session.begin_analysis()

    assert session.fail_analysis("the engine exploded", generation)
    assert session.state is State.ERROR
    assert session.snapshot().message == "the engine exploded"
    assert session.snapshot().can_analyze, "an error is recoverable by analysing again"


# ── Review decisions ───────────────────────────────────────────────────────


def test_accepting_changes_the_preview_and_nothing_else(ready_session) -> None:
    before = ready_session.snapshot()
    proposal = ready_session.bundle.reviewable[0].proposal_id

    ready_session.accept(proposal)
    after = ready_session.snapshot()

    assert after.source_text == before.source_text, "the source never moves"
    assert after.revised_text != before.revised_text
    assert proposal in after.accepted


def test_rejecting_preserves_the_original_wording(ready_session) -> None:
    """A rejected suggestion leaves the text as the author wrote it.

    And leaves the observation standing: the document is still repetitive, the
    reader simply disagreed about what to do. The diagnostic must survive the
    rejection.
    """
    proposal = ready_session.bundle.reviewable[0]
    ready_session.reject(proposal.proposal_id)
    snapshot = ready_session.snapshot()

    assert proposal.proposal_id in snapshot.rejected
    assert snapshot.revised_text.count("Nevertheless,") >= 1
    assert snapshot.diagnostics, "rejecting a suggestion does not silence the diagnostic"


def test_a_decision_can_be_changed(ready_session) -> None:
    proposal = ready_session.bundle.reviewable[0].proposal_id

    ready_session.accept(proposal)
    accepted_text = ready_session.snapshot().revised_text
    ready_session.reject(proposal)
    rejected_text = ready_session.snapshot().revised_text

    assert accepted_text != rejected_text
    assert proposal not in ready_session.snapshot().accepted


def test_deciding_on_an_unknown_proposal_is_refused(ready_session) -> None:
    with pytest.raises(SessionError, match="not awaiting review"):
        ready_session.accept("SP-doesnotexist")


def test_deciding_on_a_safe_change_is_refused(ready_session) -> None:
    """Safe fixes are already accepted by the engine and are not up for review."""
    safe = next(
        item for item in ready_session.snapshot().changes if item.kind == "safe"
    )
    with pytest.raises(SessionError, match="not awaiting review"):
        ready_session.accept(safe.change_id)


def test_the_plan_does_not_move_while_decisions_are_made(ready_session) -> None:
    """One immutable plan per session. Deciding never re-plans.

    If it did, proposal identifiers would move under somebody halfway through
    reading them, and a decision recorded a moment ago would refer to nothing.
    """
    plan_hash = ready_session.bundle.style_plan.plan_hash
    identifiers = [item.proposal_id for item in ready_session.bundle.reviewable]

    for identifier in identifiers:
        ready_session.accept(identifier)

    assert ready_session.bundle.style_plan.plan_hash == plan_hash
    assert [item.proposal_id for item in ready_session.bundle.reviewable] == identifiers


# ── Staleness ──────────────────────────────────────────────────────────────


def test_a_stale_generation_is_discarded() -> None:
    """The guard that stops slow old work replacing newer state.

    A second analysis cannot simply be started while one is running — the
    interface disables the control, and the session refuses. What *does*
    supersede an in-flight analysis is opening another document or changing the
    profile, and both bump the generation.
    """
    document = load_reviewable(fixture_path())
    session = ReviewSession()
    session.load(fixture_path(), document.source)

    first = session.begin_analysis()
    assert not session.snapshot().can_analyze, "one analysis at a time"

    # Opening another document supersedes the one in flight.
    second = session.load(fixture_path("signposted"), load_reviewable(
        fixture_path("signposted")).source)
    assert second != first

    bundle = build_review_bundle(document, DEFAULT_PROFILE)
    assert not session.accept_analysis(bundle, first), "the older generation must be dropped"


def test_a_superseded_result_cannot_be_applied_even_with_a_current_token() -> None:
    """Two guards, because they protect different things.

    The generation token stops a superseded *request* landing. The document and
    profile checks stop a delivered result being applied to state that has moved
    since — which is the case a token alone would miss if the token were reused.
    """
    session = ReviewSession()
    session.load(fixture_path(), load_reviewable(fixture_path()).source)
    generation = session.begin_analysis()

    wrong = build_review_bundle(load_reviewable(fixture_path("signposted")), DEFAULT_PROFILE)
    assert not session.accept_analysis(wrong, generation)
    assert session.state is State.ANALYZING, "a rejected result leaves the state alone"


def test_a_result_for_the_wrong_profile_is_discarded() -> None:
    """The scenario from the brief, in full.

    Natural starts, the reader switches to technical, natural finishes last. The
    window must not end up showing natural results labelled technical.
    """
    document = load_reviewable(fixture_path())
    session = ReviewSession("natural")
    session.load(fixture_path(), document.source)

    natural_generation = session.begin_analysis()
    natural_bundle = build_review_bundle(document, "natural")

    technical_generation = session.set_profile("technical")
    assert technical_generation != natural_generation

    # The slow natural result arrives now, carrying its own token.
    assert not session.accept_analysis(natural_bundle, natural_generation)
    assert session.profile_id == "technical"
    assert session.snapshot().preview is None


def test_a_result_for_a_different_document_is_discarded() -> None:
    session = ReviewSession()
    session.load(fixture_path(), "Completely different text.\n")
    generation = session.begin_analysis()

    other = build_review_bundle(load_reviewable(fixture_path()), DEFAULT_PROFILE)
    assert not session.accept_analysis(other, generation)


def test_changing_profile_clears_decisions(ready_session) -> None:
    """A decision belongs to one profile and does not travel.

    Phase 9 makes this safe at the engine level — proposal identifiers are scoped
    to the profile — but silently failing later would be a poor way to learn it.
    """
    ready_session.accept(ready_session.bundle.reviewable[0].proposal_id)
    assert ready_session.snapshot().accepted

    ready_session.set_profile("technical")
    snapshot = ready_session.snapshot()

    assert snapshot.accepted == frozenset()
    assert snapshot.rejected == frozenset()
    assert snapshot.preview is None
    assert snapshot.source_text, "the document itself is kept"


# ── Saving ─────────────────────────────────────────────────────────────────


def test_save_writes_the_text_it_was_given(tmp_path) -> None:
    destination = tmp_path / "out.md"
    written = save_revised("revised content\n", destination, tmp_path / "source.md")

    assert written == destination
    assert destination.read_text(encoding="utf-8") == "revised content\n"


def test_save_refuses_to_overwrite_the_source(tmp_path) -> None:
    """A refusal, not a warning with an override button.

    PlainSpeak reads a document it does not own. Overwriting it is a feature that
    deserves to be designed rather than arrived at, and until then the answer is
    no.
    """
    source = tmp_path / "document.md"
    source.write_text("original\n", encoding="utf-8")

    with pytest.raises(SaveError, match="does not overwrite"):
        save_revised("revised\n", source, source)

    assert source.read_text(encoding="utf-8") == "original\n"


def test_save_refuses_a_different_spelling_of_the_source(tmp_path) -> None:
    """Resolved paths, so `./doc.md` and `doc.md` are the same file."""
    source = tmp_path / "document.md"
    source.write_text("original\n", encoding="utf-8")
    disguised = tmp_path / "." / "document.md"

    with pytest.raises(SaveError, match="does not overwrite"):
        save_revised("revised\n", disguised, source)
    assert source.read_text(encoding="utf-8") == "original\n"


def test_a_failed_write_leaves_the_destination_untouched(tmp_path) -> None:
    """The atomic guarantee, with the failure injected.

    A half-written export is worse than no export: it destroys the previous one
    and looks like a complete file.
    """
    destination = tmp_path / "out.md"
    destination.write_text("PREVIOUS EXPORT\n", encoding="utf-8")

    def explode(path: Path, payload: bytes) -> None:
        path.write_bytes(payload[: len(payload) // 2])
        raise OSError("disk full")

    with pytest.raises(SaveError, match="could not be saved"):
        save_revised("a much longer revised document\n", destination, None, writer=explode)

    assert destination.read_text(encoding="utf-8") == "PREVIOUS EXPORT\n"


def test_a_failed_write_leaves_no_partial_file_behind(tmp_path) -> None:
    destination = tmp_path / "out.md"

    def explode(path: Path, payload: bytes) -> None:
        path.write_bytes(payload)
        raise OSError("commit failed")

    with pytest.raises(SaveError):
        save_revised("content\n", destination, None, writer=explode)

    assert not destination.exists()
    assert list(tmp_path.glob("*.plainspeak-partial")) == []


def test_the_write_goes_through_a_temporary_file(tmp_path) -> None:
    """Content reaches its final name only once it is complete."""
    seen = []

    def observe(path: Path, payload: bytes) -> None:
        seen.append(path.name)
        path.write_bytes(payload)

    destination = tmp_path / "out.md"
    save_revised("content\n", destination, None, writer=observe)

    assert seen == ["out.md.plainspeak-partial"]
    assert destination.read_text(encoding="utf-8") == "content\n"


def test_save_creates_missing_directories(tmp_path) -> None:
    destination = tmp_path / "nested" / "deeper" / "out.md"
    save_revised("content\n", destination, None)
    assert destination.read_text(encoding="utf-8") == "content\n"


# ── Nothing but Save As writes ─────────────────────────────────────────────


def test_no_step_before_saving_writes_anything(tmp_path) -> None:
    """Open, analyse, accept and reject are all read-only against the disk.

    Asserted by watching the whole directory rather than by inspecting the code,
    so a future `open` that quietly wrote a cache file would fail here.
    """
    source = tmp_path / "document.md"
    source.write_text(
        (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    before = _tree_state(tmp_path)

    document = load_reviewable(source)
    session = ReviewSession(DEFAULT_PROFILE)
    session.load(source, document.source)
    generation = session.begin_analysis()
    session.accept_analysis(build_review_bundle(document, DEFAULT_PROFILE), generation)

    proposals = [item.proposal_id for item in session.bundle.reviewable]
    session.accept(proposals[0])
    session.reject(proposals[1])
    session.snapshot()

    assert _tree_state(tmp_path) == before, "something wrote to disk before Save As"


def test_saving_leaves_the_source_byte_identical(tmp_path) -> None:
    source = tmp_path / "document.md"
    source.write_text(
        (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    original_bytes = source.read_bytes()

    document = load_reviewable(source)
    session = ReviewSession(DEFAULT_PROFILE)
    session.load(source, document.source)
    generation = session.begin_analysis()
    session.accept_analysis(build_review_bundle(document, DEFAULT_PROFILE), generation)
    session.accept(session.bundle.reviewable[0].proposal_id)

    destination = tmp_path / "revised.md"
    save_revised(session.snapshot().preview.revised_text, destination, source)

    assert source.read_bytes() == original_bytes
    assert destination.read_bytes() != original_bytes


def _tree_state(root: Path) -> dict:
    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
