"""«Apri anteprima grande»: l'immagine intera, grande quanto lo permette la finestra."""

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ... import icons, theme
from ...thumbnails import Thumb
from .base import PopupDialog


class _Canvas(QWidget):
    def __init__(self, file: Path | None, width: int, height: int):
        super().__init__()
        self.setFixedSize(width, height)
        self._thumb = Thumb(crop=False)
        self._thumb.set_file(file)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        pixmap = self._thumb.pixmap(self.width(), self.height(), self.devicePixelRatioF())
        if pixmap is not None:
            size = pixmap.deviceIndependentSize().toSize()
            painter.drawPixmap((self.width() - size.width()) // 2, (self.height() - size.height()) // 2, pixmap)
        else:
            icons.icon("image", theme.MUTED).paint(painter, QRect((self.width() - 56) // 2, (self.height() - 56) // 2, 56, 56))
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(QRect(0, self.height() // 2 + 40, self.width(), 24), Qt.AlignHCenter, "Il file non si trova o non si legge.")


class ImageViewer(PopupDialog):
    def __init__(self, parent: QWidget, label: str, file: Path | None):
        window = parent.window()
        width = max(520, min(1200, window.width() - 160))
        super().__init__(parent, label, file.name if file else "", "Chiudi", width=width)
        self.body.addWidget(_Canvas(file, width - 60, max(240, window.height() - 300)), alignment=Qt.AlignCenter)
