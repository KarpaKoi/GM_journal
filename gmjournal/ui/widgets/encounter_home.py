"""La schermata iniziale degli incontri: tutti quelli della campagna, uno per riga, con tipo, creature, giocatori e difficoltà.
Un clic su una riga apre l'incontro."""

from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget, QVBoxLayout

from ... import icons, theme
from ...dnd import DIFFICULTY_LABELS
from ...encounters import KIND_ICONS, KIND_LABELS
from .row_table import RowTable

_ROW_H, _HEADER_H = 56, 38
_PAD, _GAP = 20, 16
_KIND_W, _CREATURES_W, _PLAYERS_W, _DIFFICULTY_W = 150, 120, 190, 120       # le colonne, da destra: il nome prende ciò che avanza
_COLOR = theme.SECTION_COLORS["incontri"]
_TITLES = ("Incontro", "Tipo", "Creature", "Giocatori", "Difficoltà")


@dataclass(frozen=True)
class EncounterLine:
    """Una riga dell'elenco, già pronta da disegnare."""
    id: int
    name: str
    kind: str
    creatures: str              # «7 creature»
    players: str                # «4 giocatori · liv. 3» (vuoto nelle interazioni)
    difficulty: str | None      # la chiave della difficoltà; None se non è un combattimento o non si può calcolare


class _Table(RowTable):
    chosen = Signal(int)

    def __init__(self):
        super().__init__(_HEADER_H)
        self._lines: list[EncounterLine] = []
        self.row_clicked.connect(lambda index, _point: self.chosen.emit(self._lines[index].id))

    def set_lines(self, lines: list[EncounterLine]) -> None:
        self._lines = lines
        self.set_count(len(lines))

    def row_height(self, index: int) -> int:
        return _ROW_H

    @staticmethod
    def _cells(row: QRect) -> tuple[QRect, ...]:
        """Le caselle di una riga (o dell'intestazione): incontro, tipo, creature, giocatori, difficoltà."""
        right = row.right() + 1 - _PAD
        cells = []
        for width in (_DIFFICULTY_W, _PLAYERS_W, _CREATURES_W, _KIND_W):
            cells.append(QRect(right - width, row.top(), width, row.height()))
            right -= width + _GAP
        left = row.left() + _PAD
        return QRect(left, row.top(), max(right - left, 0), row.height()), *reversed(cells)

    def paint_header(self, painter: QPainter, header: QRect) -> None:
        painter.setFont(theme.ui_font(11, 600, 0.08))
        painter.setPen(QColor(theme.MUTED))
        for cell, title in zip(self._cells(header), _TITLES):
            painter.drawText(cell, Qt.AlignVCenter | Qt.AlignLeft, title.upper())

    def paint_row(self, painter: QPainter, index: int, row: QRect, hovered: bool) -> None:
        line = self._lines[index]
        name, kind, creatures, players, difficulty = self._cells(row)
        font = theme.ui_font(15, 600)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_ACTIVE))
        painter.drawText(name, Qt.AlignVCenter | Qt.AlignLeft, QFontMetrics(font).elidedText(line.name, Qt.ElideRight, name.width()))

        icons.icon(KIND_ICONS[line.kind], _COLOR).paint(painter, QRect(kind.left(), row.top() + (row.height() - 16) // 2, 16, 16))
        painter.setFont(theme.ui_font(13))
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(kind.adjusted(24, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, KIND_LABELS[line.kind])
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(creatures, Qt.AlignVCenter | Qt.AlignLeft, line.creatures)
        painter.drawText(players, Qt.AlignVCenter | Qt.AlignLeft, QFontMetrics(theme.ui_font(13)).elidedText(line.players, Qt.ElideRight, players.width()))
        if line.difficulty:
            color = QColor(theme.DIFFICULTY_COLORS[line.difficulty])
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(difficulty.left(), row.top() + (row.height() - 8) // 2, 8, 8)
            painter.setFont(theme.ui_font(14, 600))
            painter.setPen(color)
            painter.drawText(difficulty.adjusted(16, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, DIFFICULTY_LABELS[line.difficulty])
        elif line.players:          # un combattimento di cui non si può ancora dire la difficoltà
            painter.setFont(theme.ui_font(13))
            painter.setPen(QColor(theme.MUTED))
            painter.drawText(difficulty, Qt.AlignVCenter | Qt.AlignLeft, "—")


class EncounterHome(QScrollArea):
    chosen = Signal(int)        # l'ID dell'incontro scelto

    def __init__(self):
        super().__init__()
        self._table = _Table()
        self._table.chosen.connect(self.chosen)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 14, 28)
        layout.addWidget(self._table)
        layout.addStretch()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)
        content.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)

    def set_lines(self, lines: list[EncounterLine]) -> None:
        self._table.set_lines(lines)
