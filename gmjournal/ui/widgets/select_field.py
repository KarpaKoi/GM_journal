"""Campo a scelta singola: mostra la scelta attuale e, con un clic, apre l'elenco delle scelte."""

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

from ... import icons, theme
from .menu import PopupMenu


class SelectField(QAbstractButton):
    changed = Signal(object)    # il valore scelto

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._options: list[tuple[object, str]] = []
        self._value = None
        self._open = False
        self.clicked.connect(self._show_menu)

    def set_options(self, options: list[tuple[object, str]], value: object) -> None:
        """Le scelte come (valore, testo) e quella attuale."""
        self._options = list(options)
        self._value = value
        self.update()

    def value(self) -> object:
        return self._value

    def _show_menu(self) -> None:
        menu = PopupMenu(self, width=self.width())
        for value, label in self._options:
            menu.add_item(None, label, lambda value=value: self._choose(value), checked=value == self._value)
        self._open = True
        menu.destroyed.connect(self._menu_closed)
        menu.popup_below(self)
        self.update()

    def _menu_closed(self) -> None:
        self._open = False
        self.update()

    def _choose(self, value: object) -> None:
        if value != self._value:
            self._value = value
            self.update()
            self.changed.emit(value)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme.ACCENT if self._open else theme.BORDER_STRONG), 1))
        painter.setBrush(QColor(theme.BG))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        label = next((text for value, text in self._options if value == self._value), "")
        painter.setFont(theme.ui_font(14))
        painter.setPen(QColor(theme.TEXT_ACTIVE if self.isEnabled() else theme.DISABLED))
        room = self.width() - 14 - 40
        painter.drawText(QRect(14, 0, room, self.height()), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(painter.font()).elidedText(label, Qt.ElideRight, room))
        icons.icon("chevron-down", theme.MUTED).paint(painter, QRect(self.width() - 30, (self.height() - 16) // 2, 16, 16))
