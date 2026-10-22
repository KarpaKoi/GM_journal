"""La «faccia» di un elemento: la sua immagine ritagliata o, senza immagine, le iniziali su una tinta del colore della categoria."""

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget

from ... import theme
from ...thumbnails import Thumb


def paint_thumb(painter: QPainter, rect: QRect, radius: int, initials: str, color: str, pixmap: QPixmap | None) -> None:
    """Disegna immagine o iniziali dentro `rect` con gli angoli arrotondati. Le iniziali crescono con il riquadro."""
    outline = QPainterPath()
    outline.addRoundedRect(QRectF(rect), radius, radius)
    painter.save()
    painter.setClipPath(outline)
    if pixmap is not None:
        painter.drawPixmap(rect, pixmap)
    else:
        painter.fillRect(rect, theme.tint(color))
        painter.setFont(theme.serif_font(round(rect.height() * 0.29), 400))
        painter.setPen(QColor(color))
        painter.drawText(rect, Qt.AlignCenter, initials)
    painter.restore()


class ElementThumb(QWidget):
    """Riquadro con la faccia di un elemento (popup di modifica, pannello destro). Senza `width` si allarga quanto può."""

    def __init__(self, height: int, radius: int, width: int | None = None):
        super().__init__()
        self._radius = radius
        self._initials, self._color = "", theme.MUTED
        self._thumb = Thumb()
        self.setFixedHeight(height)
        if width is not None:
            self.setFixedWidth(width)

    def set_element(self, initials: str, color: str, image: Path | None) -> None:
        self._initials, self._color = initials, color
        self._thumb.set_file(image)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_thumb(painter, self.rect(), self._radius, self._initials, self._color,
                    self._thumb.pixmap(self.width(), self.height(), self.devicePixelRatioF()))
