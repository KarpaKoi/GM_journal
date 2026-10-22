"""Icona statica (non cliccabile), nitida a qualsiasi scala dello schermo."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from ... import icons, theme


class IconLabel(QWidget):
    def __init__(self, name: str, color: str = theme.TEXT, size: int = 20):
        super().__init__()
        self._icon = icons.icon(name, color)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_icon(self, name: str, color: str = theme.TEXT) -> None:
        self._icon = icons.icon(name, color)
        self.update()

    def paintEvent(self, event):
        self._icon.paint(QPainter(self), self.rect())
