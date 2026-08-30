"""View models: engine data shaped for Qt, with no decisions of their own.

Every model here is read-only over a `SessionSnapshot`. They translate — a
change becomes a row, a diagnostic becomes a row — and nothing more. A model
that could alter review state would put the engine's authority behind a table
widget, which is precisely the direction this whole design pushes against.

Rows are addressed by identifier, never by visible text. Two proposals for the
same phrase in different paragraphs read identically, and an interface that
matched on the label would act on the wrong one.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from ..pipeline.review import (
    KIND_REFUSED,
    KIND_SAFE,
    KIND_STYLE,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    ChangeView,
    DiagnosticView,
)
from ..pipeline.style_plan import STATUS_REVIEW_REQUIRED

#: Custom roles, so a view can retrieve the identifier without parsing a label.
CHANGE_ID_ROLE = int(Qt.ItemDataRole.UserRole) + 1
CHANGE_ROLE = int(Qt.ItemDataRole.UserRole) + 2

#: Human wording for each state. The badge text carries the meaning on its own,
#: so nothing here depends on a reader distinguishing two colours.
BADGE_DESCRIPTION = {
    "SAFE": "Applied automatically — a mechanically safe change",
    "REVIEW": "Awaiting your decision",
    "ACCEPTED": "You accepted this change",
    "REJECTED": "You rejected this change; the original wording is kept",
    "REFUSED": "Refused by PlainSpeak — this cannot be applied",
}


class ChangesModel(QAbstractTableModel):
    """Every change in one navigable list, safe and style and refused alike.

    One list rather than three, because a reader working through a document
    wants them in document order. The badge column keeps the kinds distinct, and
    the accessible text says which is which in words.
    """

    COLUMNS = ("Status", "Rule", "Before", "After")

    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._rows: tuple[ChangeView, ...] = ()

    def set_changes(self, changes: tuple[ChangeView, ...]) -> None:
        self.beginResetModel()
        self._rows = tuple(changes)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def change_at(self, row: int) -> Optional[ChangeView]:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def row_of(self, change_id: str) -> int:
        for index, item in enumerate(self._rows):
            if item.change_id == change_id:
                return index
        return -1

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return self.COLUMNS[section]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._rows[index.row()]

        if role == CHANGE_ID_ROLE:
            return item.change_id
        if role == CHANGE_ROLE:
            return item
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                item.badge,
                item.rule_id,
                _one_line(item.before),
                _one_line(item.after) if item.status != STATUS_REJECTED else "—",
            )[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return item.reason or item.refusal or BADGE_DESCRIPTION.get(item.badge, "")
        if role == Qt.ItemDataRole.AccessibleTextRole:
            # Spoken by a screen reader. States the badge in words rather than
            # relying on the reader seeing a colour or a shape.
            return (
                f"{BADGE_DESCRIPTION.get(item.badge, item.badge)}. "
                f"Rule {item.rule_id}. "
                f"{item.before!r} becomes {item.after!r}."
            )
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class DiagnosticsModel(QAbstractTableModel):
    """Style observations under the selected profile, with their evidence.

    No authorship claim and no score, here or anywhere else. The desktop
    inherits the engine's policy in full: what it shows is what was measured,
    the line it crossed and where to look.
    """

    COLUMNS = ("Severity", "Diagnostic", "Observation", "Evidence")

    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._rows: tuple[DiagnosticView, ...] = ()

    def set_diagnostics(self, diagnostics: tuple[DiagnosticView, ...]) -> None:
        self.beginResetModel()
        self._rows = tuple(diagnostics)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def diagnostic_at(self, row: int) -> Optional[DiagnosticView]:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return self.COLUMNS[section]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                item.severity.upper(),
                item.id.rsplit(".", 1)[-1].replace("_", " ").title(),
                item.message,
                "; ".join(item.evidence[:3]),
            )[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"{item.message}\n"
                f"Measured {item.value:.3f} against a line of {item.threshold:.3f}, "
                f"over a sample of {item.sample_size}."
            )
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"{item.severity}. {item.message}"
        return None


class RefusalsModel(QAbstractTableModel):
    """Changes PlainSpeak refused. Deliberately inert.

    There is no override control anywhere in this application, and this model
    offers no editable flag a future one could hang off.
    """

    COLUMNS = ("Rule", "Text", "Would have become", "Why refused")

    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._rows: tuple[ChangeView, ...] = ()

    def set_refusals(self, changes: tuple[ChangeView, ...]) -> None:
        self.beginResetModel()
        self._rows = tuple(item for item in changes if item.kind == KIND_REFUSED)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def refusal_at(self, row: int) -> Optional[ChangeView]:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return self.COLUMNS[section]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                item.rule_id,
                _one_line(item.before),
                _one_line(item.after),
                item.refusal,
            )[index.column()]
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"Refused. Rule {item.rule_id}. {item.refusal}"
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        # Selectable so it can be read; never editable, and never checkable.
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


def _one_line(text: str, limit: int = 80) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"
