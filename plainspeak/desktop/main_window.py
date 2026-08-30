"""The application window.

Layout, wiring and presentation. Every decision it displays was made by the
pipeline and every review decision it collects goes back through the Phase 9
contract; the window itself decides nothing about prose.

Both text panes are read-only, on purpose. Free-form editing would introduce
text that no rule proposed, no source mapping authorised, no integrity preflight
validated and no proposal identifies — and then the revised pane would no longer
be something the engine could vouch for. An editor mode can be added later as a
clearly separate thing; the first desktop should demonstrate the governed engine
exactly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..pipeline.review import (
    KIND_STYLE,
    REVIEWABLE_SUFFIXES,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    UNSUPPORTED_MESSAGE,
    ChangeView,
    ReviewError,
    load_reviewable,
)
from ..pipeline.style_plan import STATUS_REVIEW_REQUIRED
from .models import CHANGE_ROLE, ChangesModel, DiagnosticsModel, RefusalsModel
from .session import (
    DEFAULT_PROFILE,
    ReviewSession,
    SaveError,
    SessionSnapshot,
    State,
    save_revised,
)
from .workers import AnalysisFailure, AnalysisRequest, AnalysisRunner, AnalysisSuccess

#: Offered in the selector, in the pack's canonical display order. Resolved from
#: the engine rather than hard-coded, so a new bundled profile appears here
#: without anybody remembering to add it.
def _profile_choices() -> list[tuple[str, str]]:
    from ..pipeline import list_profiles

    return [(item["id"], item["name"]) for item in list_profiles()]


FILE_FILTER = "Text and Markdown (*.txt *.md *.markdown);;All files (*)"


class MainWindow(QMainWindow):
    """Open, analyse, review, save. In that order and no other."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PlainSpeak")
        # Usable at 1024x768: the minimum is set below that so the window can be
        # made smaller still without any control becoming unreachable.
        self.setMinimumSize(QSize(880, 620))
        self.resize(1280, 800)

        self.session = ReviewSession(DEFAULT_PROFILE)
        self.runner = AnalysisRunner(self)
        self.runner.completed.connect(self._on_analysis_complete)

        self._document = None
        self._last_saved: Optional[Path] = None

        self._build_actions()
        self._build_toolbar()
        self._build_central()
        self._build_status()
        self._refresh()

    # ── Construction ───────────────────────────────────────────────────────

    def _build_actions(self) -> None:
        self.open_action = QAction("&Open…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setToolTip("Open a plain text or Markdown document (Ctrl+O)")
        self.open_action.triggered.connect(self.open_document)

        self.analyze_action = QAction("&Analyze", self)
        self.analyze_action.setShortcut(QKeySequence("Ctrl+R"))
        self.analyze_action.setToolTip("Analyse the document against the selected profile")
        self.analyze_action.triggered.connect(self.start_analysis)

        self.save_as_action = QAction("Save &As…", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.setToolTip(
            "Write the revised document to a new file (Ctrl+Shift+S). "
            "The document you opened is never changed."
        )
        self.save_as_action.triggered.connect(self.save_as)

        self.copy_revised_action = QAction("&Copy Revised", self)
        self.copy_revised_action.setToolTip("Copy the revised document to the clipboard")
        self.copy_revised_action.triggered.connect(self.copy_revised)

        self.next_change_action = QAction("&Next change", self)
        self.next_change_action.setShortcut(QKeySequence("F7"))
        self.next_change_action.triggered.connect(lambda: self._step_change(1))

        self.previous_change_action = QAction("&Previous change", self)
        self.previous_change_action.setShortcut(QKeySequence("F6"))
        self.previous_change_action.triggered.connect(lambda: self._step_change(-1))

        for action in (
            self.next_change_action,
            self.previous_change_action,
            self.copy_revised_action,
        ):
            self.addAction(action)

    def _build_toolbar(self) -> None:
        bar = QToolBar("Main", self)
        bar.setObjectName("main-toolbar")
        bar.setMovable(False)
        self.addToolBar(bar)

        bar.addAction(self.open_action)
        bar.addSeparator()

        label = QLabel("Profile:", self)
        label.setObjectName("profile-label")
        bar.addWidget(label)

        self.profile_box = QComboBox(self)
        self.profile_box.setObjectName("profile-selector")
        self.profile_box.setAccessibleName("Style profile")
        self.profile_box.setToolTip(
            "The kind of prose this document is meant to be. Changing it clears "
            "any review decisions, because a decision belongs to one profile."
        )
        for identifier, name in _profile_choices():
            self.profile_box.addItem(name, identifier)
        self.profile_box.setCurrentIndex(max(0, self.profile_box.findData(DEFAULT_PROFILE)))
        self.profile_box.currentIndexChanged.connect(self._on_profile_changed)
        bar.addWidget(self.profile_box)

        bar.addSeparator()
        bar.addAction(self.analyze_action)
        bar.addAction(self.save_as_action)
        bar.addAction(self.copy_revised_action)

    def _build_central(self) -> None:
        self.panes = QSplitter(Qt.Orientation.Horizontal, self)
        self.panes.setObjectName("document-panes")

        self.original_view = self._document_pane("ORIGINAL", "original-view")
        self.revised_view = self._document_pane("REVISED", "revised-view")
        self.panes.addWidget(self.original_view.parentWidget())
        self.panes.addWidget(self.revised_view.parentWidget())
        self.panes.setSizes([640, 640])

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("review-tabs")

        self.changes_model = ChangesModel(self)
        self.changes_view = self._table(self.changes_model, "changes-table")
        self.changes_view.selectionModel().currentRowChanged.connect(self._on_change_selected)
        self.tabs.addTab(self._changes_tab(), "Changes")

        self.diagnostics_model = DiagnosticsModel(self)
        self.diagnostics_view = self._table(self.diagnostics_model, "diagnostics-table")
        self.tabs.addTab(self.diagnostics_view, "Style")

        self.refusals_model = RefusalsModel(self)
        self.refusals_view = self._table(self.refusals_model, "refusals-table")
        self.tabs.addTab(self.refusals_view, "Integrity")

        self.details_view = QPlainTextEdit(self)
        self.details_view.setObjectName("details-view")
        self.details_view.setReadOnly(True)
        self.details_view.setAccessibleName("Deterministic identities")
        self.tabs.addTab(self.details_view, "Details")

        vertical = QSplitter(Qt.Orientation.Vertical, self)
        vertical.setObjectName("main-splitter")
        vertical.addWidget(self.panes)
        vertical.addWidget(self.tabs)
        vertical.setSizes([520, 280])
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 2)
        self.setCentralWidget(vertical)

    def _document_pane(self, title: str, name: str) -> QPlainTextEdit:
        holder = QWidget(self)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        heading = QLabel(title, holder)
        heading.setObjectName(f"{name}-label")
        layout.addWidget(heading)

        editor = QPlainTextEdit(holder)
        editor.setObjectName(name)
        # Read-only, and stated in the accessible name rather than implied by a
        # cursor that does not blink.
        editor.setReadOnly(True)
        editor.setAccessibleName(f"{title.title()} document, read only")
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        heading.setBuddy(editor)
        layout.addWidget(editor, 1)
        return editor

    def _changes_tab(self) -> QWidget:
        holder = QWidget(self)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.changes_view, 1)

        controls = QWidget(holder)
        row = QHBoxLayout(controls)
        row.setContentsMargins(4, 4, 4, 4)

        self.selected_label = QLabel("No change selected", controls)
        self.selected_label.setObjectName("selected-change-label")
        self.selected_label.setWordWrap(True)
        row.addWidget(self.selected_label, 1)

        self.accept_button = QPushButton("&Accept", controls)
        self.accept_button.setObjectName("accept-button")
        self.accept_button.setAccessibleName("Accept the selected style suggestion")
        self.accept_button.clicked.connect(self.accept_selected)
        row.addWidget(self.accept_button)

        self.reject_button = QPushButton("&Reject", controls)
        self.reject_button.setObjectName("reject-button")
        self.reject_button.setAccessibleName("Reject the selected style suggestion")
        self.reject_button.clicked.connect(self.reject_selected)
        row.addWidget(self.reject_button)

        layout.addWidget(controls)
        return holder

    def _table(self, model, name: str) -> QTableView:
        view = QTableView(self)
        view.setObjectName(name)
        view.setModel(model)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.verticalHeader().setVisible(False)
        view.horizontalHeader().setStretchLastSection(True)
        view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        view.setAlternatingRowColors(True)
        return view

    def _build_status(self) -> None:
        self.setStatusBar(QStatusBar(self))
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("status-label")
        self.statusBar().addWidget(self.status_label, 1)

    # ── Commands ───────────────────────────────────────────────────────────

    @Slot()
    def open_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open document", "", FILE_FILTER)
        if path:
            self.load_path(Path(path))

    def load_path(self, path: Path) -> bool:
        """Open a document, or explain precisely why it cannot be opened.

        Unsupported types are refused by name rather than opened through the
        plain-text degradation path. A reader shown a revised .docx would
        reasonably assume its structure had survived, and nothing in the engine
        can promise that yet.
        """
        try:
            document = load_reviewable(path)
        except ReviewError as error:
            self._error("Cannot open this document", str(error))
            return False
        except UnicodeDecodeError:
            self._error(
                "Cannot open this document",
                "The file is not valid UTF-8 text, so PlainSpeak cannot read it safely.",
            )
            return False
        except OSError as error:
            self._error("The file could not be read", str(error))
            return False

        self._document = document
        self.session.load(Path(path), document.source)
        self._last_saved = None
        self.setWindowTitle(f"PlainSpeak — {Path(path).name}")
        self._refresh()
        self.start_analysis()
        return True

    @Slot()
    def start_analysis(self) -> None:
        if self._document is None or not self.session.snapshot().can_analyze:
            return
        generation = self.session.begin_analysis()
        self._refresh()
        self.runner.start(
            AnalysisRequest(
                generation=generation,
                profile_id=self.session.profile_id,
                document=self._document,
            )
        )

    @Slot(object)
    def _on_analysis_complete(self, outcome) -> None:
        if isinstance(outcome, AnalysisFailure):
            if self.session.fail_analysis(outcome.message, outcome.generation):
                self._error("Analysis failed", outcome.message)
                self._refresh()
            return

        assert isinstance(outcome, AnalysisSuccess)
        if not self.session.accept_analysis(outcome.bundle, outcome.generation):
            # Superseded while it ran. Dropping it is the whole point of the
            # generation token: a slow natural analysis must never land on top
            # of a newer technical one.
            return
        self._refresh()

    @Slot(int)
    def _on_profile_changed(self, _index: int) -> None:
        identifier = self.profile_box.currentData()
        if identifier is None:
            return
        previous = self.session.profile_id
        self.session.set_profile(identifier)
        if previous != identifier and self._document is not None:
            self._note(
                f"Profile changed to {identifier}. Review decisions from the "
                f"previous profile no longer apply and have been cleared."
            )
            self._refresh()
            self.start_analysis()
        else:
            self._refresh()

    @Slot()
    def accept_selected(self) -> None:
        self._decide(accept=True)

    @Slot()
    def reject_selected(self) -> None:
        self._decide(accept=False)

    def _decide(self, accept: bool) -> None:
        change = self._selected_change()
        if change is None or not change.is_reviewable:
            return
        try:
            if accept:
                self.session.accept(change.change_id)
            else:
                self.session.reject(change.change_id)
        except Exception as error:  # noqa: BLE001 - surfaced, never raised into Qt
            self._error("This suggestion could not be recorded", str(error))
            return
        self._refresh(keep_selection=change.change_id)

    @Slot()
    def save_as(self) -> None:
        snapshot = self.session.snapshot()
        if not snapshot.can_save or snapshot.preview is None:
            return

        suggestion = ""
        if snapshot.path is not None:
            suggestion = str(snapshot.path.with_name(
                f"{snapshot.path.stem}.plainspeak{snapshot.path.suffix}"
            ))
        path, _ = QFileDialog.getSaveFileName(self, "Save revised document as", suggestion, FILE_FILTER)
        if not path:
            return
        self.save_to(Path(path))

    def save_to(self, destination: Path) -> bool:
        """Write the pipeline's revised text — never the widget's contents."""
        snapshot = self.session.snapshot()
        if snapshot.preview is None:
            return False
        try:
            written = save_revised(
                snapshot.preview.revised_text, destination, snapshot.path
            )
        except SaveError as error:
            self._error("Save failed", str(error))
            return False

        self.session.mark_saved(written)
        self._last_saved = written
        self._refresh()
        self._note(f"Saved to {written}. The document you opened is unchanged.")
        return True

    @Slot()
    def copy_revised(self) -> None:
        snapshot = self.session.snapshot()
        if snapshot.preview is None:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(snapshot.preview.revised_text)
        self._note("Revised document copied to the clipboard.")

    # ── Navigation ─────────────────────────────────────────────────────────

    @Slot()
    def _on_change_selected(self, current, _previous) -> None:
        change = self._selected_change()
        self._update_review_controls(change)
        if change is not None:
            self._highlight(change)

    def _step_change(self, direction: int) -> None:
        rows = self.changes_model.rowCount()
        if rows == 0:
            return
        current = self.changes_view.currentIndex().row()
        target = 0 if current < 0 else (current + direction) % rows
        self.changes_view.selectRow(target)
        self.changes_view.setFocus()

    def _highlight(self, change: ChangeView) -> None:
        """Show the change in both panes. Display only; never touches state."""
        _select(self.original_view, change.source_start, change.source_end)
        _select(self.revised_view, change.revised_start, change.revised_end)

    def _selected_change(self) -> Optional[ChangeView]:
        index = self.changes_view.currentIndex()
        if not index.isValid():
            return None
        return self.changes_model.data(index, CHANGE_ROLE)

    # ── Rendering ──────────────────────────────────────────────────────────

    def _refresh(self, keep_selection: Optional[str] = None) -> None:
        snapshot = self.session.snapshot()

        if self.original_view.toPlainText() != snapshot.source_text:
            self.original_view.setPlainText(snapshot.source_text)
        if self.revised_view.toPlainText() != snapshot.revised_text:
            self.revised_view.setPlainText(snapshot.revised_text)

        self.changes_model.set_changes(snapshot.changes)
        self.diagnostics_model.set_diagnostics(snapshot.diagnostics)
        self.refusals_model.set_refusals(snapshot.changes)
        self.details_view.setPlainText(_details_text(snapshot))

        self._apply_enabled_states(snapshot)
        self._update_status(snapshot)

        if keep_selection:
            row = self.changes_model.row_of(keep_selection)
            if row >= 0:
                self.changes_view.selectRow(row)
        self._update_review_controls(self._selected_change())

    def _apply_enabled_states(self, snapshot: SessionSnapshot) -> None:
        busy = snapshot.busy
        self.open_action.setEnabled(not busy)
        self.analyze_action.setEnabled(snapshot.can_analyze and not busy)
        self.save_as_action.setEnabled(snapshot.can_save and not busy)
        self.copy_revised_action.setEnabled(snapshot.preview is not None and not busy)
        self.profile_box.setEnabled(not busy)
        self.changes_view.setEnabled(not busy)

    def _update_review_controls(self, change: Optional[ChangeView]) -> None:
        snapshot = self.session.snapshot()
        reviewable = (
            change is not None
            and change.kind == KIND_STYLE
            and change.is_reviewable
            and snapshot.can_review
            and not snapshot.busy
        )
        self.accept_button.setEnabled(bool(reviewable))
        self.reject_button.setEnabled(bool(reviewable))

        if change is None:
            self.selected_label.setText("No change selected")
            return
        if change.kind == KIND_STYLE:
            self.selected_label.setText(
                f"{change.badge} · {change.rule_id} · profile {change.profile_id} · "
                f"triggered by {change.trigger_diagnostic.rsplit('.', 1)[-1]} "
                f"({change.trigger_severity}) · integrity "
                f"{'checked' if change.integrity_checked else 'not checked'}\n"
                f"{change.reason}"
            )
        elif change.kind == "safe":
            self.selected_label.setText(
                f"{change.badge} · {change.rule_id} · applied automatically. {change.reason}"
            )
        else:
            self.selected_label.setText(
                f"{change.badge} · {change.rule_id} · {change.refusal}"
            )

    def _update_status(self, snapshot: SessionSnapshot) -> None:
        if snapshot.state is State.EMPTY:
            self.status_label.setText("Open a plain text or Markdown document to begin.")
            return
        if snapshot.busy:
            self.status_label.setText("Analyzing…")
            return
        if snapshot.state is State.ERROR:
            self.status_label.setText(snapshot.message or "Something went wrong.")
            return

        safe = sum(1 for item in snapshot.changes if item.kind == "safe")
        awaiting = len(snapshot.undecided)
        refused = sum(1 for item in snapshot.changes if item.kind == "refused")
        parts = [
            f"profile {snapshot.profile_id}",
            f"{safe} safe change{'' if safe == 1 else 's'}",
            f"{awaiting} awaiting review",
            f"{refused} refused",
        ]
        if snapshot.saved_to is not None:
            parts.append(f"saved to {snapshot.saved_to.name}")
        self.status_label.setText(" · ".join(parts))

    # ── Dialogs ────────────────────────────────────────────────────────────

    def _error(self, title: str, detail: str) -> None:
        QMessageBox.warning(self, title, detail)

    def _note(self, message: str) -> None:
        self.status_label.setText(message)

    def should_prompt_before_closing(self) -> bool:
        """Whether closing now would lose review decisions nobody saved.

        Separated from `closeEvent` so the decision can be checked without
        opening a dialog. A modal dialog cannot be answered from the thread it
        blocks, so anything worth asserting has to live outside one — and the
        first version of this window proved the point by hanging its own test
        suite on teardown.
        """
        return self.session.snapshot().has_unsaved_decisions

    def confirm_discard(self) -> bool:
        """Ask whether to discard an unsaved review.

        An attribute rather than a private call, so a test can substitute it and
        drive the real `closeEvent`. The alternative is a close path that goes
        untested because it cannot be reached.
        """
        answer = QMessageBox.question(
            self,
            "Discard reviewed preview?",
            "You have accepted or rejected suggestions but have not saved the "
            "revised document.\n\n"
            "The document you opened has not been changed and will not be.",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        """Ask before discarding an unsaved review.

        The wording says explicitly that the source is safe. Somebody closing a
        window they have made decisions in should not have to wonder whether
        their original document is about to be damaged — it is not, and never
        was.
        """
        if not self.should_prompt_before_closing():
            event.accept()
            return
        event.accept() if self.confirm_discard() else event.ignore()


def _select(editor: QPlainTextEdit, start: int, end: int) -> None:
    if start < 0 or end < start:
        return
    cursor = editor.textCursor()
    cursor.setPosition(min(start, len(editor.toPlainText())))
    cursor.setPosition(min(end, len(editor.toPlainText())), QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.ensureCursorVisible()


def _details_text(snapshot: SessionSnapshot) -> str:
    """Every authority behind the current reading, in one inspectable place.

    Not decoration. A deterministic engine is only useful if a person can check
    which version of it produced a given answer, and burying that in a log would
    make it unavailable exactly when somebody is asking.
    """
    if not snapshot.identities:
        return "No analysis yet."

    lines = [f"Document        {snapshot.path}" if snapshot.path else "Document        (none)"]
    order = [
        ("input_sha256", "Input SHA-256"),
        ("ruleset_version", "Ruleset version"),
        ("ruleset_sha256", "Ruleset SHA-256"),
        ("integrity_policy_version", "Integrity version"),
        ("integrity_policy_sha256", "Integrity SHA-256"),
        ("morphology_version", "Morphology version"),
        ("morphology_sha256", "Morphology SHA-256"),
        ("style_policy_version", "Style policy version"),
        ("style_policy_sha256", "Style policy SHA-256"),
        ("profile_pack_version", "Profile pack version"),
        ("profile_pack_sha256", "Profile pack SHA-256"),
        ("profile_id", "Selected profile"),
        ("profile_version", "Profile version"),
        ("profile_sha256", "Profile SHA-256"),
        ("plan_sha256", "Style plan SHA-256"),
        ("engine_version", "Engine version"),
    ]
    for key, label in order:
        if key in snapshot.identities:
            lines.append(f"{label:<24}{snapshot.identities[key]}")
    if snapshot.preview is not None:
        lines.append(f"{'Output SHA-256':<24}{snapshot.preview.output_hash}")
    if snapshot.saved_to is not None:
        lines.append(f"{'Saved to':<24}{snapshot.saved_to}")
    return "\n".join(lines)
