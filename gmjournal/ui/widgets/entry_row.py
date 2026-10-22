"""Una riga dell'elenco di Impostazioni: pallino colorato (con l'icona, per i tipi di pin), nome, quante volte è usata, frecce per riordinare e «Modifica»."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from ... import icons, theme
from ...settings import Entry
from .elided_label import ElidedLabel

_DOT = 28
_RADIUS = 12


class _Dot(QWidget):
    def __init__(self, color: str, icon_name: str):
        super().__init__()
        self._color, self._icon = color, icon_name
        self.setFixedSize(_DOT, _DOT)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        # Senza icona il pallino è più piccolo, come nelle pillole dei filtri.
        circle = QRectF(self.rect()) if self._icon else QRectF(self.rect()).adjusted(7, 7, -7, -7)
        painter.drawEllipse(circle)
        if self._icon:
            icons.icon(self._icon, theme.BG).paint(painter, circle.adjusted(7, 7, -7, -7).toRect())


def _button(icon_name: str, tooltip: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName("BarButton")
    button.setIcon(icons.icon(icon_name, theme.TEXT_SOFT))
    button.setIconSize(QSize(18, 18))
    button.setFixedSize(32, 32)
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setFocusPolicy(Qt.NoFocus)
    button.setCursor(Qt.PointingHandCursor)
    return button


class EntryRow(QFrame):
    edit_requested = Signal()
    move_requested = Signal(int)        # -1 = su, +1 = giù

    def __init__(self, entry: Entry, count_text: str, first: bool, last: bool):
        super().__init__()
        self.setFixedHeight(56)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        name = ElidedLabel(entry.name, theme.TEXT_ACTIVE, theme.ui_font(15, 500))
        count = QLabel(count_text)
        count.setObjectName("Muted")
        count.setFont(theme.ui_font(13))
        up, down, edit = _button("arrow-up", "Sposta su"), _button("arrow-down", "Sposta giù"), _button("pencil", "Modifica")
        up.setEnabled(not first)
        down.setEnabled(not last)
        up.clicked.connect(lambda _=False: self.move_requested.emit(-1))
        down.clicked.connect(lambda _=False: self.move_requested.emit(1))
        edit.clicked.connect(lambda _=False: self.edit_requested.emit())

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(12)
        row.addWidget(_Dot(theme.category_color(entry.color), entry.icon))
        row.addWidget(name, 1)
        row.addWidget(count)
        row.addSpacing(8)
        for button in (up, down, edit):
            row.addWidget(button)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.edit_requested.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(QColor(theme.HOVER_SOFT if self.underMouse() else theme.SURFACE))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS, _RADIUS)
