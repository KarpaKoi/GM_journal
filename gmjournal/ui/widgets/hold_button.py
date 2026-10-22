"""Pulsante «tieni premuto» per eliminare: l'unico modo di eliminare nell'app, senza finestre di conferma."""

from PySide6.QtCore import QRect, QRectF, QVariantAnimation, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton

from ... import icons, theme

HOLD_MS = 1500


class HoldButton(QAbstractButton):
    confirmed = Signal()  # tenuto premuto fino in fondo

    def __init__(self, accessible_name: str = "Tieni premuto per eliminare"):
        super().__init__()
        self.setFixedSize(268, 40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAccessibleName(accessible_name)
        self._progress = 0.0
        self._animation = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=HOLD_MS)
        self._animation.valueChanged.connect(self._set_progress)
        self._animation.finished.connect(self._on_finished)

    def _set_progress(self, value: float) -> None:
        self._progress = value
        self.update()

    def _on_finished(self) -> None:
        if self._progress >= 1.0:
            self._set_progress(0.0)
            self.confirmed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._animation.start()

    def mouseReleaseEvent(self, event):
        if self._animation.state() == QVariantAnimation.Running:  # rilasciato troppo presto: non succede nulla
            self._animation.stop()
            self._set_progress(0.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)

        fill_width = round(self.width() * self._progress)
        if fill_width:
            painter.save()
            painter.setClipPath(outline)
            painter.fillRect(QRect(0, 0, fill_width, self.height()), QColor(227, 154, 166, 97))
            if fill_width < self.width():
                painter.fillRect(QRect(fill_width - 2, 0, 2, self.height()), QColor(theme.DANGER))
            painter.restore()
        painter.setPen(QPen(QColor(227, 154, 166, 128), 1))
        painter.drawPath(outline)

        label = "Tieni premuto per eliminare" if self._progress == 0 else "Continua a tenere premuto…"
        font = theme.ui_font(14, 600)
        painter.setFont(font)
        text_width = painter.fontMetrics().horizontalAdvance(label)
        left = (self.width() - (16 + 10 + text_width)) // 2
        icons.icon("trash", theme.DANGER_TEXT).paint(painter, QRect(left, (self.height() - 16) // 2, 16, 16))
        painter.setPen(QColor(theme.DANGER_TEXT))
        painter.drawText(QRect(left + 26, 0, text_width + 4, self.height()), Qt.AlignVCenter | Qt.AlignLeft, label)
