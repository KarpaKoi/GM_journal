"""Selettore a segmenti: una riga di scelte affiancate, una sola attiva (dimensione del testo, dimensione dell'immagine)."""

from typing import Callable, Hashable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ... import theme

_HEIGHT = 32
_PADDING = 2


class SegmentSwitch(QWidget):
    """`options`: (valore, etichetta, grandezza del carattere in px). Con `outlined` ha il bordo e il fondo dei menu
    (per stare sopra al testo)."""

    def __init__(self, options: list[tuple[Hashable, str, int]], on_choose: Callable[[Hashable], None],
                 segment_width: int = 30, outlined: bool = False):
        super().__init__()
        self._options = options
        self._on_choose = on_choose
        self._segment_width = segment_width
        self._outlined = outlined
        self._current: Hashable | None = None
        self.setFixedSize(segment_width * len(options) + 2 * _PADDING, _HEIGHT)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)

    def set_value(self, value: Hashable | None) -> None:
        self._current = value
        self.update()

    def mousePressEvent(self, event) -> None:
        if self.isEnabled() and event.button() == Qt.LeftButton:
            index = max(0, min(len(self._options) - 1, int((event.position().x() - _PADDING) // self._segment_width)))
            self._on_choose(self._options[index][0])

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._outlined:
            painter.setPen(QColor(theme.BORDER_STRONG))
            painter.setBrush(QColor(theme.MENU_BG))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.CONTROL_BG))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        for i, (value, label, font_px) in enumerate(self._options):
            rect = QRectF(_PADDING + i * self._segment_width, _PADDING, self._segment_width, self.height() - 2 * _PADDING)
            active = self.isEnabled() and value == self._current
            painter.setPen(Qt.NoPen)
            if active:
                painter.setBrush(QColor(theme.SEGMENT_ACTIVE))
                painter.drawRoundedRect(rect, 6, 6)
            painter.setFont(theme.ui_font(font_px, 600))
            painter.setPen(QColor(theme.TEXT_ACTIVE if active else theme.MUTED if self.isEnabled() else theme.DISABLED))
            painter.drawText(rect, Qt.AlignCenter, label)
