"""Una riga cliccabile dei pannelli di destra: un pallino colorato con un'icona, un nome e una riga più piccola sotto."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton

from ... import icons, theme

_ROW_HEIGHT = 44
_DOT = 28


class ListRow(QAbstractButton):
    def __init__(self, color: str, icon_name: str, name: str, caption: str, selected: bool = False):
        """`color` è quello del pallino (un colore vero, non una chiave del tema)."""
        super().__init__()
        self._color, self._icon, self._name, self._caption, self._selected = color, icon_name, name, caption, selected
        self.setFixedHeight(_ROW_HEIGHT)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_caption(self, caption: str) -> None:
        self._caption = caption
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(100, _ROW_HEIGHT)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._selected or self.underMouse():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER if self._selected else theme.HOVER_SOFT))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        dot = QRectF(8, (self.height() - _DOT) / 2, _DOT, _DOT)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(dot)
        icons.icon(self._icon, theme.BG).paint(painter, dot.adjusted(7, 7, -7, -7).toRect())
        room = self.width() - 52 - 8
        for font, color, text, top in ((theme.ui_font(14, 500), theme.TEXT, self._name, 5), (theme.ui_font(12), theme.MUTED, self._caption, 24)):
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(QRectF(48, top, room, 18), Qt.AlignVCenter | Qt.AlignLeft, QFontMetrics(font).elidedText(text, Qt.ElideRight, room))
