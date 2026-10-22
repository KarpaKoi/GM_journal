"""Pastiglia con un pallino colorato, un testo e, se serve, un conteggio: filtri delle liste e scelta della categoria."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

from ... import theme

_DOT = 8
_PAD = 14


class FilterChip(QAbstractButton):
    """Acceso (`checked`) = sfondo evidenziato. Senza `count` mostra solo il testo."""

    def __init__(self, label: str, color: str, count: int | None = None, height: int = 34, font_px: int = 13):
        super().__init__()
        self.setCheckable(True)
        self.setText(label)
        self._color, self._count, self._font_px = color, count, font_px
        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def _count_text(self) -> str:
        return "" if self._count is None else str(self._count)

    def sizeHint(self) -> QSize:
        font = theme.ui_font(self._font_px, 500)
        width = 2 * _PAD + _DOT + 8 + QFontMetrics(font).horizontalAdvance(self.text())
        if self._count is not None:
            width += 8 + QFontMetrics(font).horizontalAdvance(self._count_text())
        return QSize(width, self.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        on, radius = self.isChecked(), self.height() / 2
        painter.setPen(QPen(QColor(theme.BORDER_STRONG if on else theme.BORDER), 1))
        painter.setBrush(QColor(theme.HOVER) if on else QColor(theme.HOVER_SOFT) if self.underMouse() else Qt.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

        middle = self.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(QRectF(_PAD, middle - _DOT / 2, _DOT, _DOT))
        font = theme.ui_font(self._font_px, 500)
        painter.setFont(font)
        left = _PAD + _DOT + 8
        text_width = QFontMetrics(font).horizontalAdvance(self.text())
        painter.setPen(QColor(theme.TEXT_ACTIVE if on else theme.TEXT_SOFT))
        painter.drawText(QRectF(left, 0, text_width, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        if self._count is not None:
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(QRectF(left + text_width + 8, 0, 60, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self._count_text())
