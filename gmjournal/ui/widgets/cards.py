"""Tessere cliccabili: la base comune, la scheda «Nuova…» tratteggiata, la scheda campagna e la tessera di un elemento."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QSizePolicy, QToolButton

from ... import icons, theme
from ...thumbnails import Thumb
from .element_thumb import paint_thumb

_RADIUS = 12


class Card(QFrame):
    """Base delle tessere: segnala il clic e tiene traccia del passaggio del mouse."""

    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, height: int):
        super().__init__()
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self._pressed = False

    def mousePressEvent(self, event):
        self._pressed = event.button() == Qt.LeftButton

    def mouseReleaseEvent(self, event):
        if self._pressed and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        self._pressed = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()

    def _outline(self, body: QRect | None = None) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(QRectF(body or self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS, _RADIUS)
        return path


class NewCard(Card):
    """Scheda tratteggiata «+ Nuova …»; `color` è quello del «+». `footer` è lo spazio vuoto lasciato in basso
    (per allinearsi alle tessere con il testo sotto la miniatura)."""

    def __init__(self, label: str, color: str = theme.ACCENT, footer: int = 0):
        super().__init__(_LARGE.height)
        self._label, self._color, self._footer = label, color, footer

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        body = self.rect().adjusted(0, 0, 0, -self._footer)
        painter.setPen(QPen(QColor(theme.ACCENT if self.underMouse() else theme.DISABLED), 1, Qt.DashLine))
        painter.drawPath(self._outline(body))

        font = theme.ui_font(15, 500)
        painter.setFont(font)
        text_height = QFontMetrics(font).height()
        top = (body.height() - (30 + 12 + text_height)) // 2
        icons.icon("plus", self._color).paint(painter, QRect((self.width() - 30) // 2, top, 30, 30))
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QRect(0, top + 42, self.width(), text_height), Qt.AlignHCenter | Qt.AlignTop, self._label)


@dataclass(frozen=True)
class _Metrics:
    height: int       # altezza iniziale (la Home la cambia in base alla larghezza)
    body: int         # altezza della parte bassa con i testi; la copertina occupa il resto
    icon: int
    pad_x: int
    pad_y: int
    title: int
    meta: int


_LARGE = _Metrics(height=206, body=88, icon=44, pad_x=18, pad_y=14, title=21, meta=13)
_SMALL = _Metrics(height=190, body=82, icon=40, pad_x=16, pad_y=12, title=19, meta=13)
_COVER_RATIO = 0.72  # altezza della copertina rispetto alla larghezza della card


def campaign_card_height(width: int) -> int:
    """Altezza di una card della Home larga `width`: resta quasi quadrata a ogni misura."""
    return round(max(width, 0) * _COVER_RATIO) + _LARGE.body


class CampaignCard(Card):
    """Scheda di una campagna. `compact=True` è la versione piccola dell'anteprima nel popup."""

    menu_clicked = Signal()

    def __init__(self, compact: bool = False):
        self._m = _SMALL if compact else _LARGE
        super().__init__(self._m.height)
        self._name = ""
        self._meta = ""
        self._color = "blue"
        self._thumb = Thumb()

        self._menu_button: QToolButton | None = None
        if compact:
            self.setCursor(Qt.ArrowCursor)
        else:
            self._menu_button = QToolButton(self)
            self._menu_button.setObjectName("CardMenuButton")
            self._menu_button.setIcon(icons.icon("more"))
            self._menu_button.setIconSize(QSize(18, 18))
            self._menu_button.setFixedSize(30, 30)
            self._menu_button.setCursor(Qt.PointingHandCursor)
            self._menu_button.setFocusPolicy(Qt.NoFocus)
            self._menu_button.setToolTip("Opzioni della campagna")
            self._menu_button.clicked.connect(self.menu_clicked)

    def set_campaign(self, name: str, meta: str, color: str, image: Path | None) -> None:
        self._name, self._meta, self._color = name, meta, color
        self._thumb.set_file(image)
        self.update()

    def menu_anchor(self) -> QPoint:
        """Dove far comparire il menu «⋯» (coordinate globali, angolo in alto a destra del menu)."""
        return self.mapToGlobal(QPoint(self.width() - 10, 44))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._menu_button is not None:
            self._menu_button.move(self.width() - 10 - 30, 10)

    def _cover_height(self) -> int:
        return self.height() - self._m.body

    def paintEvent(self, event):
        m = self._m
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outline = self._outline()

        painter.setClipPath(outline)
        painter.fillRect(self.rect(), QColor(theme.SURFACE))
        cover_height = self._cover_height()
        cover_rect = QRect(0, 0, self.width(), cover_height)
        _, color, tint = theme.CAMPAIGN_COLORS.get(self._color, theme.CAMPAIGN_COLORS["blue"])
        cover = self._thumb.pixmap(self.width(), cover_height, self.devicePixelRatioF())
        if cover is not None:
            painter.drawPixmap(cover_rect, cover)
        else:
            painter.fillRect(cover_rect, QColor(tint))
            icon_rect = QRect((self.width() - m.icon) // 2, (cover_height - m.icon) // 2, m.icon, m.icon)
            icons.icon("campaign", color).paint(painter, icon_rect)
        painter.setClipping(False)
        hovered = self.underMouse() and self._menu_button is not None
        painter.setPen(QPen(QColor(theme.BORDER_STRONG if hovered else theme.BORDER), 1))
        painter.drawPath(outline)

        text_width = self.width() - 2 * m.pad_x
        title_font, meta_font = theme.serif_font(m.title, 500), theme.ui_font(m.meta)
        title_height = QFontMetrics(title_font).height()
        title_rect = QRect(m.pad_x, cover_height + m.pad_y, text_width, title_height)
        meta_rect = QRect(m.pad_x, title_rect.bottom() + 4, text_width, QFontMetrics(meta_font).height())
        painter.setFont(title_font)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(title_font).elidedText(self._name, Qt.ElideRight, text_width))
        painter.setFont(meta_font)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, self._meta)


TILE_TEXT = 54      # altezza sotto la miniatura: nome e categoria


def element_tile_height(width: int) -> int:
    """Altezza di una tessera larga `width`: la miniatura è quadrata, sotto ci sono nome e categoria."""
    return max(width, 0) + TILE_TEXT


class ElementTile(Card):
    """La tessera di un personaggio, luogo o organizzazione: miniatura quadrata, nome e categoria."""

    def __init__(self):
        super().__init__(element_tile_height(0))
        self._name = self._category = self._initials = ""
        self._color = theme.MUTED
        self._thumb = Thumb()
        self._selected = False

    def set_element(self, name: str, initials: str, category: str, color: str, image: Path | None) -> None:
        self._name, self._initials, self._category, self._color = name, initials, category, color
        self._thumb.set_file(image)
        self.update()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def _thumb_rect(self) -> QRect:
        return QRect(0, 0, self.width(), self.height() - TILE_TEXT)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        thumb = self._thumb_rect()
        paint_thumb(painter, thumb, _RADIUS, self._initials, self._color, self._thumb.pixmap(thumb.width(), thumb.height(), self.devicePixelRatioF()))
        if self._selected or self.underMouse():
            painter.setPen(QPen(QColor(theme.ACCENT if self._selected else theme.BORDER_STRONG), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(thumb).adjusted(1, 1, -1, -1), _RADIUS, _RADIUS)

        name_font, meta_font = theme.ui_font(14, 500), theme.ui_font(12)
        top = thumb.bottom() + 9
        painter.setFont(name_font)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(QRect(2, top, self.width() - 4, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(name_font).elidedText(self._name, Qt.ElideRight, self.width() - 4))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(QRectF(2, top + 20 + 8, 7, 7))
        painter.setFont(meta_font)
        painter.setPen(QColor(theme.MUTED))
        room = self.width() - 17
        painter.drawText(QRect(15, top + 22, room, 18), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(meta_font).elidedText(self._category, Qt.ElideRight, room))
