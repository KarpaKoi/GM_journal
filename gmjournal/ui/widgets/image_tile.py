"""Le tessere della libreria immagini: quella di un'immagine (miniatura, nome, distintivi) e quella di una cartella."""

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolButton

from ... import icons, theme
from ...thumbnails import Thumb
from .cards import Card

_RADIUS = 10
_TEXT = 30                        # altezza del nome sotto la miniatura
_COLOR = theme.SECTION_COLORS["immagini"]
_BADGE_BG = QColor(20, 22, 26, 199)


def image_tile_height(width: int, ratio: float) -> int:
    """Altezza di una tessera larga `width`: la miniatura è `ratio` volte la larghezza, sotto c'è il nome."""
    return round(max(width, 0) * ratio) + _TEXT


class ImageTile(Card):
    """Miniatura ritagliata (o un segnaposto se il file non c'è o il suo percorso non è valido), nome sotto, bordo se scelta.

    `check` aggiunge il segno di spunta sulle immagini scelte (nei popup di scelta); `quiet` rende il nome più discreto.
    """

    def __init__(self, ratio: float, check: bool = False, quiet: bool = False):
        super().__init__(image_tile_height(0, ratio))
        self._check, self._quiet = check, quiet
        self._label = ""
        self._file: Path | None = None
        self._thumb = Thumb()
        self._selected = False
        self._badge = ""
        self._dimmed = False

    def set_image(self, label: str, file: Path | None) -> None:
        self._label, self._file = label, file
        self._thumb.set_file(file)
        self.update()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_badge(self, text: str) -> None:
        """Un'etichetta sull'angolo in alto a sinistra («Ritratto», «Già collegata»); vuota = nessuna."""
        self._badge = text
        self.update()

    def set_dimmed(self, dimmed: bool) -> None:
        self._dimmed = dimmed
        self.setCursor(Qt.ArrowCursor if dimmed else Qt.PointingHandCursor)
        self.update()

    def _thumb_rect(self) -> QRect:
        return QRect(0, 0, self.width(), self.height() - _TEXT)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(0.5 if self._dimmed else 1.0)
        thumb = self._thumb_rect()
        pixmap = self._thumb.pixmap(thumb.width(), thumb.height(), self.devicePixelRatioF())
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(thumb), _RADIUS, _RADIUS)
        painter.save()
        painter.setClipPath(outline)
        if pixmap is not None:
            painter.drawPixmap(thumb, pixmap)
        else:                                   # file mancante o illeggibile: un segnaposto
            painter.fillRect(thumb, theme.tint(_COLOR))
            size = min(34, thumb.height() // 2)
            icons.icon("image", _COLOR).paint(painter, QRect(thumb.center().x() - size // 2, thumb.center().y() - size // 2, size, size))
        painter.restore()
        if self._selected or self.underMouse() and not self._dimmed:
            painter.setPen(QPen(QColor(theme.ACCENT if self._selected else theme.BORDER_STRONG), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(thumb).adjusted(1, 1, -1, -1), _RADIUS, _RADIUS)

        text = self._badge or ("" if self._file is not None and self._file.exists() else "File mancante")
        if text:
            font = theme.ui_font(11, 600)
            width = QFontMetrics(font).horizontalAdvance(text) + 16
            painter.setPen(Qt.NoPen)
            painter.setBrush(_BADGE_BG)
            painter.drawRoundedRect(QRectF(8, 8, width, 22), 11, 11)
            painter.setFont(font)
            painter.setPen(QColor(theme.TEXT_ACTIVE))
            painter.drawText(QRect(8, 8, width, 22), Qt.AlignCenter, text)
        if self._check and self._selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.ACCENT))
            painter.drawEllipse(QRectF(thumb.right() - 30, 8, 22, 22))
            icons.icon("check", theme.BG).paint(painter, QRect(thumb.right() - 26, 12, 14, 14))

        font = theme.ui_font(12 if self._quiet else 13, 400 if self._quiet else 500)
        painter.setFont(font)
        painter.setPen(QColor(theme.MUTED if self._quiet else theme.TEXT))
        painter.drawText(QRect(2, thumb.bottom() + 6, self.width() - 4, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(font).elidedText(self._label, Qt.ElideRight, self.width() - 4))


class FolderCard(Card):
    """Una cartella: icona, nome e quante immagini contiene. Al passaggio del mouse compare il pulsante per modificarla."""

    def __init__(self, name: str, count: int):
        super().__init__(56)
        self._name, self._count = name, count
        self._edit = QToolButton(self)
        self._edit.setObjectName("BarButton")
        self._edit.setIcon(icons.icon("pencil", theme.TEXT_SOFT))
        self._edit.setIconSize(QSize(16, 16))
        self._edit.setFixedSize(30, 30)
        self._edit.setToolTip("Modifica la cartella")
        self._edit.setCursor(Qt.PointingHandCursor)
        self._edit.setFocusPolicy(Qt.NoFocus)
        self._edit.hide()
        self.edit_clicked = self._edit.clicked

    def enterEvent(self, event) -> None:
        self._edit.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._edit.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._edit.move(self.width() - 12 - 30, (self.height() - 30) // 2)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme.BORDER_STRONG if self.underMouse() else theme.BORDER), 1))
        painter.setBrush(QColor(theme.SURFACE))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS, _RADIUS)
        icons.icon("folder", _COLOR).paint(painter, QRect(16, (self.height() - 22) // 2, 22, 22))
        count_width = 40
        painter.setFont(theme.ui_font(14, 500))
        painter.setPen(QColor(theme.TEXT))
        room = self.width() - 50 - 16 - count_width
        painter.drawText(QRect(50, 0, room, self.height()), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(painter.font()).elidedText(self._name, Qt.ElideRight, room))
        if not self.underMouse():
            painter.setFont(theme.ui_font(12))
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(QRect(self.width() - 16 - count_width, 0, count_width, self.height()),
                             Qt.AlignVCenter | Qt.AlignRight, str(self._count))
