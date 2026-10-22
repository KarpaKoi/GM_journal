"""La scheda di una mappa nell'elenco: lo sfondo ritagliato, il nome e quanti pin ha. Al passaggio del mouse compare il pulsante per modificarla."""

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QToolButton

from ... import icons, theme
from ...thumbnails import Thumb
from .cards import Card

_RADIUS = 12
_COLOR = theme.SECTION_COLORS["mappe"]
_RATIO = 0.62       # altezza dello sfondo rispetto alla larghezza della scheda
TEXT_HEIGHT = 62    # altezza sotto lo sfondo: nome e dettagli


def map_card_height(width: int) -> int:
    return round(max(width, 0) * _RATIO) + TEXT_HEIGHT


class MapCard(Card):
    edit_clicked = Signal()
    action_clicked = Signal()       # il pulsante di `add_action`

    def __init__(self):
        super().__init__(map_card_height(0))
        self._name = self._meta = ""
        self._action: QPushButton | None = None
        self._thumb = Thumb()
        self._edit = QToolButton(self)
        self._edit.setObjectName("CardMenuButton")
        self._edit.setIcon(icons.icon("pencil"))
        self._edit.setIconSize(QSize(16, 16))
        self._edit.setFixedSize(30, 30)
        self._edit.setToolTip("Modifica la mappa")
        self._edit.setCursor(Qt.PointingHandCursor)
        self._edit.setFocusPolicy(Qt.NoFocus)
        self._edit.clicked.connect(self.edit_clicked)
        self._edit.hide()

    def add_action(self, label: str) -> None:
        """Un pulsante a destra, sotto lo sfondo (per esempio «Apri la mappa»)."""
        self._action = QPushButton(label, self)
        self._action.setFixedHeight(34)
        self._action.setCursor(Qt.PointingHandCursor)
        self._action.setFocusPolicy(Qt.NoFocus)
        self._action.setStyleSheet(f"QPushButton {{ border: 1px solid {theme.BORDER_STRONG}; border-radius: 8px; padding: 0 14px; "
                                   f"background: transparent; color: {theme.TEXT}; font-weight: 600; }}"
                                   f"QPushButton:hover {{ background: {theme.HOVER}; }}")
        self._action.adjustSize()
        self._action.clicked.connect(self.action_clicked)
        self._place_action()
        self._action.show()

    def _place_action(self) -> None:
        if self._action is not None:
            self._action.move(self.width() - 16 - self._action.width(), self.height() - TEXT_HEIGHT + (TEXT_HEIGHT - self._action.height()) // 2)

    def set_map(self, name: str, meta: str, file: Path | None) -> None:
        self._name, self._meta = name, meta
        self._thumb.set_file(file)
        self.update()

    def _cover(self) -> QRect:
        return QRect(0, 0, self.width(), self.height() - TEXT_HEIGHT)

    def enterEvent(self, event) -> None:
        self._edit.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._edit.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._edit.move(self.width() - 10 - 30, 10)
        self._place_action()

    def _paint_cover(self, painter: QPainter, cover: QRect) -> None:
        """La parte alta della scheda: lo sfondo della mappa o, senza, una tinta con l'icona."""
        pixmap = self._thumb.pixmap(cover.width(), cover.height(), self.devicePixelRatioF())
        if pixmap is not None:
            painter.drawPixmap(cover, pixmap)
        else:
            painter.fillRect(cover, theme.tint(_COLOR))
            icons.icon("map", _COLOR).paint(painter, QRect(cover.center().x() - 22, cover.center().y() - 22, 44, 44))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outline = self._outline()
        painter.setClipPath(outline)
        painter.fillRect(self.rect(), QColor(theme.SURFACE))
        cover = self._cover()
        self._paint_cover(painter, cover)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(theme.BORDER_STRONG if self.underMouse() else theme.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(outline)

        room = self.width() - 32 - (self._action.width() + 12 if self._action is not None else 0)
        title_font, meta_font = theme.serif_font(19, 500), theme.ui_font(13)
        painter.setFont(title_font)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(QRect(16, cover.bottom() + 8, room, 28), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(title_font).elidedText(self._name, Qt.ElideRight, room))
        painter.setFont(meta_font)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QRect(16, cover.bottom() + 36, room, 18), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(meta_font).elidedText(self._meta, Qt.ElideRight, room))
