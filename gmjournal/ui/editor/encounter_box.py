"""Il box «Incontro» nel testo: una scheda con nome, riepilogo, difficoltà e creature dell'incontro.

Nel documento è un'immagine (vedi `styles.encounter_format`) che sta da sola nel suo paragrafo e che qui si disegna.
I dati (nome, creature…) non sono nel testo salvato, che contiene solo l'ID dell'incontro: si rileggono dalla
campagna, quindi la scheda è sempre aggiornata.
"""

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QImage, QPainter, QPen

from ... import icons, theme
from ...data.models import LinkTarget
from ...dnd import DIFFICULTY_LABELS
from . import styles

_PAD_X, _PAD_TOP, _PAD_BOTTOM = styles.BOX_PAD_X, 14, 16
_LABEL_H, _NAME_H, _SUMMARY_H = 15, 30, 20
_LIST_GAP, _ROW_H, _COUNT_W = 14, 24, 34
_MISSING_H = 64


@dataclass(frozen=True)
class EncounterCard:
    """Ciò che la scheda mostra di un incontro."""
    name: str
    kind_icon: str                              # l'icona del tipo di incontro
    summary: str                                # «Combattimento · 4 giocatori · liv. 3 · 7 creature»
    difficulty: str | None                      # la chiave della difficoltà; None se non è un combattimento o non si può calcolare
    creatures: tuple[tuple[str, int], ...]      # (nome della scheda, copie)


@dataclass(frozen=True)
class EncounterSource:
    """Cosa chiede l'editor per inserire e mostrare gli incontri: cercarli per nome e leggerne la scheda (None se non esiste più)."""
    targets: Callable[[str, int], list[LinkTarget]]
    card: Callable[[int], EncounterCard | None]


def card_height(card: EncounterCard | None) -> int:
    """L'altezza della scheda (o del segnaposto se l'incontro non c'è più): dipende solo da ciò che contiene, non dalla larghezza."""
    return _MISSING_H if card is None else _card_height(card)


def render_card(card: EncounterCard | None, width: int, ratio: float = 1.0) -> QImage:
    """L'immagine della scheda, larga `width` px (nitida anche a `ratio` volte la risoluzione)."""
    height = card_height(card)
    image = QImage(round(width * ratio), round(height * ratio), QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(0, 0, width, height)
    _paint_card(painter, rect, card) if card is not None else _paint_missing(painter, rect)
    painter.end()
    return image


def _card_height(card: EncounterCard) -> float:
    height = _PAD_TOP + _LABEL_H + 6 + _NAME_H + _SUMMARY_H + _PAD_BOTTOM
    return height + (_LIST_GAP * 2 + 1 + len(card.creatures) * _ROW_H - 6 if card.creatures else 0)


def _paint_card(painter: QPainter, rect: QRectF, card: EncounterCard) -> None:
    background, accent, text = theme.ENCOUNTER_BOX
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(background))
    painter.drawRoundedRect(rect, styles.BOX_RADIUS, styles.BOX_RADIUS)
    left, right, top = int(rect.left()) + _PAD_X, int(rect.right()) - _PAD_X, int(rect.top()) + _PAD_TOP

    # In alto: icona ed etichetta a sinistra; a destra la difficoltà e la freccia «apri».
    icons.icon(card.kind_icon, accent).paint(painter, QRect(left, top, 15, 15))
    painter.setFont(theme.ui_font(11, 600, 0.09))
    painter.setPen(QColor(accent))
    painter.drawText(QRect(left + 22, top, 200, _LABEL_H), Qt.AlignVCenter | Qt.AlignLeft, "INCONTRO")
    icons.icon("external-link", theme.MUTED).paint(painter, QRect(right - 14, top, 14, 14))
    if card.difficulty:
        color, label = theme.DIFFICULTY_COLORS[card.difficulty], DIFFICULTY_LABELS[card.difficulty]
        font = theme.ui_font(12, 600)
        label_w = QFontMetrics(font).horizontalAdvance(label)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(QRect(right - 14 - 12 - label_w, top - 1, label_w, _LABEL_H + 2), Qt.AlignVCenter | Qt.AlignRight, label)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(right - 14 - 12 - label_w - 14, top + 3.5, 8, 8))

    width = right - left
    y = top + _LABEL_H + 6
    name_font = theme.serif_font(21, 600)
    painter.setFont(name_font)
    painter.setPen(QColor(theme.TEXT_ACTIVE))
    painter.drawText(QRect(left, y, width, _NAME_H), Qt.AlignVCenter | Qt.AlignLeft,
                     QFontMetrics(name_font).elidedText(card.name, Qt.ElideRight, width))
    y += _NAME_H
    summary_font = theme.ui_font(13)
    painter.setFont(summary_font)
    painter.setPen(QColor(theme.MUTED))
    painter.drawText(QRect(left, y, width, _SUMMARY_H), Qt.AlignVCenter | Qt.AlignLeft,
                     QFontMetrics(summary_font).elidedText(card.summary, Qt.ElideRight, width))
    if not card.creatures:
        return

    y += _SUMMARY_H + _LIST_GAP
    painter.setPen(QPen(theme.tint(accent, 0.25), 1))
    painter.drawLine(left, y, right, y)
    y += 1 + _LIST_GAP - 6
    name_font = theme.ui_font(14)
    for name, copies in card.creatures:
        painter.setFont(theme.ui_font(13, 600))
        painter.setPen(QColor(accent))
        painter.drawText(QRect(left, y, _COUNT_W, _ROW_H), Qt.AlignVCenter | Qt.AlignLeft, f"×{copies}")
        painter.setFont(name_font)
        painter.setPen(QColor(text))
        painter.drawText(QRect(left + _COUNT_W, y, width - _COUNT_W, _ROW_H), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(name_font).elidedText(name, Qt.ElideRight, width - _COUNT_W))
        y += _ROW_H


def _paint_missing(painter: QPainter, rect: QRectF) -> None:
    """Al posto di un incontro che non c'è più."""
    painter.setPen(QPen(QColor(theme.BORDER_STRONG), 1, Qt.DashLine))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), styles.BOX_RADIUS, styles.BOX_RADIUS)
    icons.icon("swords", theme.MUTED).paint(painter, QRect(int(rect.left()) + _PAD_X, int(rect.center().y()) - 8, 16, 16))
    painter.setFont(theme.ui_font(14))
    painter.setPen(QColor(theme.MUTED))
    painter.drawText(QRect(int(rect.left()) + _PAD_X + 26, int(rect.top()), int(rect.width()), int(rect.height())),
                     Qt.AlignVCenter | Qt.AlignLeft, "Incontro eliminato")
