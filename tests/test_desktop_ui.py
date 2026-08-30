"""The window itself, driven headlessly against the real engine.

Nothing here is mocked. These tests open checked-in fixtures, run the actual
pipeline, and assert on what the application ends up showing and writing — which
is the only way to catch the failure this phase is most exposed to, an adapter
that quietly disagrees with the engine it is supposed to be presenting.

They interact with actions, models, signals and session state. Never with
pixels: Qt renders differently on three operating systems and at four scaling
factors, and a test that depended on any of that would fail for reasons nobody
could act on.
"""
from __future__ import annotations

import gc
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# `importorskip("PySide6")` is not enough. The Python package imports fine on a
# machine that lacks the Qt shared libraries; the failure arrives later, from
# `QtWidgets`, as an ImportError about libEGL. Skipping on the package alone
# turns "no Qt runtime here" into a collection error, which is what happened on
# the Linux CI runner the first time this ran.
try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtWidgets import QApplication
except ImportError as error:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"the Qt runtime is not usable here: {error}", allow_module_level=True
    )

from plainspeak.desktop.main_window import MainWindow  # noqa: E402
from plainspeak.desktop.models import CHANGE_ROLE  # noqa: E402
from plainspeak.desktop.session import State  # noqa: E402
from plainspeak.pipeline import build_review_bundle, load_reviewable  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "style" / "stylefix"
CORPUS = Path(__file__).resolve().parent / "style" / "corpus"


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(application):
    """A fresh window per test, and genuinely destroyed afterwards.

    The teardown is more careful than it looks because it has to be. A window
    holds a thread pool and a whole `ReviewBundle`; `deleteLater` only queues
    the destruction, and a queued destruction with no event loop running is a
    leak. Thirty of those accumulate into a suite that appears to hang.
    """
    view = MainWindow()
    # Answer the close confirmation without a dialog. A modal dialog cannot be
    # answered from the thread it blocks, which is why the seam exists: teardown
    # becomes possible and the close path stays testable.
    view.confirm_discard = lambda: True
    # Shown so that visibility and layout questions have real answers. The
    # offscreen platform means nothing reaches a screen.
    view.show()
    QApplication.processEvents()
    yield view

    view.runner.wait(10_000)
    view.close()
    view.setParent(None)
    view.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    gc.collect()


def opened(window, path: Path, profile: str = "natural"):
    """Open a document and wait for its analysis, the way the window would."""
    if profile != window.session.profile_id:
        window.profile_box.setCurrentIndex(window.profile_box.findData(profile))
        QApplication.processEvents()
    window.load_path(path)
    window.runner.wait(60_000)
    QApplication.processEvents()
    return window


# ── The window exists and is shaped as specified ───────────────────────────


def test_the_window_has_two_document_panes_and_four_panels(window) -> None:
    assert window.original_view is not None and window.revised_view is not None
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
        "Changes", "Style", "Integrity", "Details"
    ]


def test_both_document_panes_are_read_only(window) -> None:
    """No free-form editing in this phase.

    Text a person typed would be text no rule proposed, no source mapping
    authorised, no integrity preflight validated and no proposal identifies — and
    the revised pane would stop being something the engine could vouch for.
    """
    assert window.original_view.isReadOnly()
    assert window.revised_view.isReadOnly()


def test_the_profile_selector_offers_every_bundled_profile(window) -> None:
    identifiers = [window.profile_box.itemData(i) for i in range(window.profile_box.count())]
    assert identifiers == ["natural", "plain", "technical", "government", "academic"]
    assert window.profile_box.currentData() == "natural", "a UI default, not an engine one"


def test_the_window_is_usable_at_the_smallest_supported_size(window) -> None:
    """1024x768 must leave every control reachable."""
    window.resize(1024, 768)
    QApplication.processEvents()

    assert window.width() == 1024 and window.height() == 768
    assert window.minimumWidth() <= 1024 and window.minimumHeight() <= 768
    for widget in (window.profile_box, window.accept_button, window.reject_button,
                   window.changes_view, window.original_view, window.revised_view):
        assert widget.isVisibleTo(window), f"{widget.objectName()} is unreachable"


# ── Opening ────────────────────────────────────────────────────────────────


def test_opening_a_markdown_document_analyses_it(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")

    assert window.session.state is State.READY
    assert window.original_view.toPlainText() == (
        FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8")
    assert window.revised_view.toPlainText()


def test_an_unsupported_format_is_refused_by_name(window, tmp_path, monkeypatch) -> None:
    """Not opened through the plain-text degradation path and presented as safe.

    A reader shown a revised .docx would reasonably assume its structure had
    survived, and nothing in the engine can promise that yet.
    """
    shown = {}
    monkeypatch.setattr(
        "plainspeak.desktop.main_window.QMessageBox.warning",
        lambda parent, title, detail: shown.update(title=title, detail=detail),
    )
    target = tmp_path / "report.docx"
    target.write_bytes(b"not really a docx")

    assert window.load_path(target) is False
    assert "Markdown" in shown["detail"]
    assert window.session.state is State.EMPTY


def test_a_missing_file_is_reported_not_raised(window, tmp_path, monkeypatch) -> None:
    shown = {}
    monkeypatch.setattr(
        "plainspeak.desktop.main_window.QMessageBox.warning",
        lambda parent, title, detail: shown.update(title=title, detail=detail),
    )
    assert window.load_path(tmp_path / "nothing.md") is False
    assert "not found" in shown["detail"].lower()


# ── The safe-fix flow ──────────────────────────────────────────────────────


def test_safe_changes_appear_and_are_already_applied(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    safe = [item for item in window.session.snapshot().changes if item.kind == "safe"]

    assert safe, "this fixture has a safe fix"
    for item in safe:
        assert item.badge == "SAFE"
        assert item.after in window.revised_view.toPlainText()


def test_safe_and_style_rows_are_visibly_distinct(window) -> None:
    """Distinguished in words, not by colour alone."""
    opened(window, FIXTURES / "concessive-heavy.md")
    badges = set()
    for row in range(window.changes_model.rowCount()):
        badges.add(window.changes_model.data(window.changes_model.index(row, 0)))
    assert {"SAFE", "REVIEW"} <= badges


def test_the_revised_pane_matches_the_pipeline_exactly(window) -> None:
    """The window shows what the engine produced, character for character."""
    path = FIXTURES / "concessive-heavy.md"
    opened(window, path)

    expected = build_review_bundle(load_reviewable(path), "natural").preview()
    assert window.revised_view.toPlainText() == expected.revised_text


# ── The style-review flow ──────────────────────────────────────────────────


def select_first_reviewable(window):
    for row in range(window.changes_model.rowCount()):
        change = window.changes_model.data(window.changes_model.index(row, 0), CHANGE_ROLE)
        if change.kind == "style" and change.is_reviewable:
            window.changes_view.selectRow(row)
            QApplication.processEvents()
            return change
    raise AssertionError("no reviewable style proposal in this document")


def test_a_style_proposal_offers_accept_and_reject(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    change = select_first_reviewable(window)

    assert window.accept_button.isEnabled()
    assert window.reject_button.isEnabled()
    assert change.rule_id in window.selected_label.text()
    assert change.profile_id in window.selected_label.text()
    assert "integrity" in window.selected_label.text().lower()


def test_accepting_changes_the_preview(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    before = window.revised_view.toPlainText()
    change = select_first_reviewable(window)

    window.accept_button.click()
    QApplication.processEvents()

    assert window.revised_view.toPlainText() != before
    assert change.change_id in window.session.snapshot().accepted
    assert change.after in window.revised_view.toPlainText()


def test_rejecting_preserves_the_original_phrase(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    change = select_first_reviewable(window)

    window.reject_button.click()
    QApplication.processEvents()

    assert change.change_id in window.session.snapshot().rejected
    assert change.before in window.revised_view.toPlainText()
    assert window.session.snapshot().diagnostics, "the observation survives the rejection"


def test_a_safe_change_offers_no_review_controls(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    for row in range(window.changes_model.rowCount()):
        change = window.changes_model.data(window.changes_model.index(row, 0), CHANGE_ROLE)
        if change.kind == "safe":
            window.changes_view.selectRow(row)
            QApplication.processEvents()
            assert not window.accept_button.isEnabled()
            assert not window.reject_button.isEnabled()
            return
    pytest.fail("no safe change in this fixture")


def test_there_is_no_accept_all_control(window) -> None:
    """Explicit judgement is the point of a review-required change."""
    names = {
        child.objectName().lower()
        for child in window.findChildren(object)
        if hasattr(child, "objectName")
    }
    assert not any("all" in name and "accept" in name for name in names)
    texts = {a.text().lower() for a in window.findChildren(type(window.open_action))}
    assert not any("accept all" in text for text in texts)


# ── The integrity flow ─────────────────────────────────────────────────────


def test_refusals_are_shown_and_cannot_be_overridden(window) -> None:
    opened(window, CORPUS / "government.md")

    model = window.refusals_model
    for row in range(model.rowCount()):
        index = model.index(row, 0)
        flags = model.flags(index)
        assert not (flags & Qt.ItemFlag.ItemIsEditable)
        assert not (flags & Qt.ItemFlag.ItemIsUserCheckable)

    labels = {a.text().lower() for a in window.findChildren(type(window.open_action))}
    assert not any("override" in text or "anyway" in text for text in labels)


# ── Diagnostics ────────────────────────────────────────────────────────────


def test_style_diagnostics_are_listed_with_evidence(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    model = window.diagnostics_model

    assert model.rowCount() > 0
    first = model.diagnostic_at(0)
    assert first.severity and first.message and first.sample_size > 0
    assert first.evidence


def test_the_diagnostics_panel_makes_no_authorship_claim(window) -> None:
    """The desktop inherits the engine's policy in full."""
    opened(window, FIXTURES / "concessive-heavy.md")
    model = window.diagnostics_model
    rendered = " ".join(
        str(model.data(model.index(row, column)))
        for row in range(model.rowCount())
        for column in range(model.columnCount())
    ).lower()

    for phrase in ("ai", "human score", "probability", "generated", "authorship", "detector"):
        if phrase == "ai":
            assert " ai " not in f" {rendered} "
        else:
            assert phrase not in rendered


# ── Navigation ─────────────────────────────────────────────────────────────


def test_selecting_a_change_highlights_it_in_both_panes(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    change = select_first_reviewable(window)

    original = window.original_view.textCursor()
    revised = window.revised_view.textCursor()

    assert original.selectedText().replace(" ", "\n") == change.before
    assert revised.selectedText().replace(" ", "\n") == change.before
    assert original.selectionStart() == change.source_start
    assert revised.selectionStart() == change.revised_start


def test_navigation_after_acceptance_points_at_the_new_text(window) -> None:
    """The mapping must follow the edits, including earlier ones."""
    opened(window, FIXTURES / "concessive-heavy.md")
    first = select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()

    for row in range(window.changes_model.rowCount()):
        change = window.changes_model.data(window.changes_model.index(row, 0), CHANGE_ROLE)
        window.changes_view.selectRow(row)
        QApplication.processEvents()
        expected = change.after if change.status in ("applied", "accepted") else change.before
        actual = window.revised_view.textCursor().selectedText().replace(" ", "\n")
        assert actual == expected, f"{change.change_id} highlighted {actual!r}"


def test_navigation_never_changes_review_state(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    before = window.session.snapshot()

    for row in range(window.changes_model.rowCount()):
        window.changes_view.selectRow(row)
        QApplication.processEvents()
    window._step_change(1)
    window._step_change(-1)
    QApplication.processEvents()

    after = window.session.snapshot()
    assert after.accepted == before.accepted
    assert after.rejected == before.rejected
    assert after.revised_text == before.revised_text


# ── Profile change ─────────────────────────────────────────────────────────


def test_changing_profile_clears_decisions_and_re_analyses(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()
    assert window.session.snapshot().accepted

    window.profile_box.setCurrentIndex(window.profile_box.findData("technical"))
    window.runner.wait(60_000)
    QApplication.processEvents()

    snapshot = window.session.snapshot()
    assert snapshot.profile_id == "technical"
    assert snapshot.accepted == frozenset()
    assert snapshot.rejected == frozenset()


def test_the_profile_reaches_the_engine_explicitly(window) -> None:
    opened(window, FIXTURES / "signposted.md", profile="plain")
    identities = window.session.snapshot().identities

    assert identities["profile_id"] == "plain"
    assert window.session.bundle.profile_id == "plain"


# ── Details ────────────────────────────────────────────────────────────────


def test_the_details_panel_exposes_every_authority(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    text = window.details_view.toPlainText()

    for label in (
        "Input SHA-256", "Ruleset SHA-256", "Integrity SHA-256", "Morphology SHA-256",
        "Style policy SHA-256", "Profile pack SHA-256", "Profile SHA-256",
        "Style plan SHA-256", "Output SHA-256",
    ):
        assert label in text, f"{label} missing from the details panel"


# ── Saving ─────────────────────────────────────────────────────────────────


def test_save_as_writes_the_pipeline_output_not_the_widget(window, tmp_path) -> None:
    """The widget is a display. The artifact comes from the engine."""
    path = tmp_path / "document.md"
    path.write_text(
        (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    opened(window, path)
    change = select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()

    # Corrupt the display. The saved file must be unaffected.
    window.revised_view.setPlainText("THIS IS NOT THE DOCUMENT")

    destination = tmp_path / "revised.md"
    assert window.save_to(destination)

    expected = build_review_bundle(load_reviewable(path), "natural").preview(
        accepted=[change.change_id]
    )
    assert destination.read_text(encoding="utf-8") == expected.revised_text
    assert "THIS IS NOT THE DOCUMENT" not in destination.read_text(encoding="utf-8")


def test_save_as_refuses_the_source_path(window, tmp_path, monkeypatch) -> None:
    shown = {}
    monkeypatch.setattr(
        "plainspeak.desktop.main_window.QMessageBox.warning",
        lambda parent, title, detail: shown.update(title=title, detail=detail),
    )
    path = tmp_path / "document.md"
    original = (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8")
    path.write_text(original, encoding="utf-8")
    opened(window, path)

    assert window.save_to(path) is False
    assert "does not overwrite" in shown["detail"]
    assert path.read_text(encoding="utf-8") == original


def test_the_source_survives_the_whole_workflow(window, tmp_path) -> None:
    path = tmp_path / "document.md"
    path.write_text(
        (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    before = path.read_bytes()

    opened(window, path)
    select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()
    window.save_to(tmp_path / "revised.md")

    assert path.read_bytes() == before


def test_after_saving_the_session_still_shows_the_original(window, tmp_path) -> None:
    """The output is a new artifact, not a mutation of the session."""
    path = tmp_path / "document.md"
    path.write_text(
        (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    opened(window, path)
    select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()

    destination = tmp_path / "revised.md"
    window.save_to(destination)
    snapshot = window.session.snapshot()

    assert snapshot.state is State.SAVED
    assert snapshot.path == path, "the session did not switch to the saved file"
    assert window.original_view.toPlainText() == path.read_text(encoding="utf-8")
    assert snapshot.saved_to == destination
    assert destination.name in window.status_label.text()


def test_copy_revised_copies_the_pipeline_output(window) -> None:
    from PySide6.QtGui import QGuiApplication

    opened(window, FIXTURES / "concessive-heavy.md")
    window.revised_view.setPlainText("NOT THE DOCUMENT")
    window.copy_revised()
    QApplication.processEvents()

    clipboard = QGuiApplication.clipboard()
    assert clipboard.text() == window.session.snapshot().preview.revised_text


# ── Busy state ─────────────────────────────────────────────────────────────


def test_controls_are_disabled_while_analysing(window) -> None:
    path = FIXTURES / "concessive-heavy.md"
    document = load_reviewable(path)
    window._document = document
    window.session.load(path, document.source)
    window.session.begin_analysis()
    window._refresh()

    assert not window.analyze_action.isEnabled()
    assert not window.save_as_action.isEnabled()
    assert not window.profile_box.isEnabled()
    assert "Analyz" in window.status_label.text()
    assert window.original_view.toPlainText() == document.source, "the source stays visible"


def test_the_status_line_reports_what_was_found(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    text = window.status_label.text()

    assert "profile natural" in text
    assert "safe change" in text
    assert "awaiting review" in text
    assert "refused" in text


# ── Accessibility ──────────────────────────────────────────────────────────


def test_controls_carry_accessible_names(window) -> None:
    assert window.profile_box.accessibleName()
    assert window.accept_button.accessibleName()
    assert window.reject_button.accessibleName()
    assert "read only" in window.original_view.accessibleName().lower()
    assert "read only" in window.revised_view.accessibleName().lower()


def test_status_is_carried_in_words_not_only_colour(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    model = window.changes_model

    for row in range(model.rowCount()):
        badge = model.data(model.index(row, 0))
        spoken = model.data(model.index(row, 0), Qt.ItemDataRole.AccessibleTextRole)
        assert badge in ("SAFE", "REVIEW", "ACCEPTED", "REJECTED", "REFUSED")
        assert spoken and len(spoken) > len(badge)


def test_review_actions_are_keyboard_reachable(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    select_first_reviewable(window)

    assert window.accept_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert window.reject_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert "&" in window.accept_button.text(), "no keyboard mnemonic"
    assert "&" in window.reject_button.text()


def test_the_documented_shortcuts_are_bound(window) -> None:
    from PySide6.QtGui import QKeySequence

    assert window.open_action.shortcut() == QKeySequence.StandardKey.Open
    assert window.save_as_action.shortcut() == QKeySequence.StandardKey.SaveAs
    assert window.next_change_action.shortcut() == QKeySequence("F7")
    assert window.previous_change_action.shortcut() == QKeySequence("F6")


def test_no_hard_coded_colours_in_the_widgets() -> None:
    """Native styling only, so light and dark system themes both work."""
    import re

    root = Path(__file__).resolve().parent.parent / "plainspeak" / "desktop"
    offences = []
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"#[0-9a-fA-F]{6}\b|setStyleSheet\(", source):
            offences.append(f"{path.name}: {match.group(0)}")
    assert not offences, f"hard-coded appearance: {offences}"


# ── Closing ────────────────────────────────────────────────────────────────


def test_closing_without_decisions_asks_nothing(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    assert not window.should_prompt_before_closing()


def test_closing_with_unsaved_decisions_asks_first(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()

    assert window.should_prompt_before_closing()


def test_cancelling_the_close_keeps_the_window(window) -> None:
    opened(window, FIXTURES / "concessive-heavy.md")
    select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()

    window.confirm_discard = lambda: False
    window.close()
    QApplication.processEvents()
    assert window.isVisible(), "cancelling must not close the window"

    window.confirm_discard = lambda: True


def test_saving_removes_the_close_prompt(window, tmp_path) -> None:
    """Nothing is at stake once the revised document has been written out."""
    path = tmp_path / "document.md"
    path.write_text(
        (FIXTURES / "concessive-heavy.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    opened(window, path)
    select_first_reviewable(window)
    window.accept_button.click()
    QApplication.processEvents()
    assert window.should_prompt_before_closing()

    window.save_to(tmp_path / "revised.md")
    assert not window.should_prompt_before_closing()
