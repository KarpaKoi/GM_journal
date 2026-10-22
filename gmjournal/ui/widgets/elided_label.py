"""Un'etichetta su una riga che, se non c'è posto, finisce con «…» invece di allargare la finestra."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class ElidedLabel(QWidget):
    def __init__(self, text: str = "", color: str = "", font=None):
        super().__init__()
        self._text, self._color = text, color
        if font is not None:
            self.setFont(font)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setFixedHeight(self.fontMetrics().height())

    def setText(self, text: str) -> None:
        self._text = text
        self.setToolTip(text)
        self.update()

    def setColor(self, color: str) -> None:
        self._color = color
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance(self._text), self.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(QColor(self._color or self.palette().windowText().color()))
        text = QFontMetrics(self.font()).elidedText(self._text, Qt.ElideRight, self.width())
        painter.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, text)
