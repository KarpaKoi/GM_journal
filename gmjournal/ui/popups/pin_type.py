"""Popup per creare o modificare un tipo di pin (e, da qui, eliminarlo): nome, icona e colore."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QDialog, QGridLayout, QMessageBox, QWidget

from ... import icons, theme
from ...data.db import DatabaseError
from ...data.repository import Repository
from ...pins import PIN_ICONS
from ...settings import BY_KEY, Entry
from .base import DELETE, labeled
from .entry import EntryPopup


class _IconButton(QAbstractButton):
    def __init__(self, icon_name: str, label: str):
        super().__init__()
        self._name = icon_name
        self.setCheckable(True)
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(38)

    def sizeHint(self) -> QSize:
        return QSize(60, 38)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.SEGMENT_ACTIVE if on else theme.HOVER if self.underMouse() else theme.SURFACE))
        painter.drawRoundedRect(QRectF(self.rect()), 9, 9)
        icons.icon(self._name, theme.TEXT_ACTIVE if on else theme.TEXT_SOFT).paint(
            painter, self.rect().adjusted((self.width() - 18) // 2, (self.height() - 18) // 2, -((self.width() - 18) // 2), -((self.height() - 18) // 2)))


class PinTypePopup(EntryPopup):
    def __init__(self, parent: QWidget, entry: Entry | None = None, others: list[Entry] = ()):
        super().__init__(parent, BY_KEY["mappe"], entry, list(others), "Es. Tesoro")

    def add_fields(self) -> None:
        current = self._entry.icon if self._entry is not None else PIN_ICONS[0][0]
        self._icons = QButtonGroup(self)
        grid = QGridLayout()
        grid.setSpacing(6)
        for position, (icon_name, label) in enumerate(PIN_ICONS):
            button = _IconButton(icon_name, label)
            self._icons.addButton(button, position)
            grid.addWidget(button, position // 6, position % 6)
            button.setChecked(icon_name == current)
        holder = QWidget()
        grid.setContentsMargins(0, 0, 0, 0)
        holder.setLayout(grid)
        self.body.addLayout(labeled("Icona", holder))

    def icon(self) -> str:
        return PIN_ICONS[self._icons.checkedId()][0]


def create_pin_type(parent: QWidget, repo: Repository) -> int | None:
    """Apre «Nuovo tipo di pin» e, se si conferma, lo crea. Restituisce il suo ID (None se annullato o fallito)."""
    popup = PinTypePopup(parent)
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_pin_type(popup.name(), popup.icon(), popup.color())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_pin_type(parent: QWidget, repo: Repository, entry: Entry, others: list[Entry]) -> int:
    """Apre «Modifica tipo di pin» e fa ciò che si sceglie. Restituisce `DELETE`, `QDialog.Accepted` o `QDialog.Rejected`."""
    popup = PinTypePopup(parent, entry, others)
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_pin_type(entry.id, popup.destination())
        elif result == QDialog.Accepted:
            repo.update_pin_type(entry.id, popup.name(), popup.icon(), popup.color())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
