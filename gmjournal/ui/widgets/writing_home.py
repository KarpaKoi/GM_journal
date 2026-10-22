"""La schermata iniziale di Scrittura: titolo e riepilogo, «Nuovo capitolo» e l'elenco dei capitoli con i loro sottocapitoli
(parole, ultima modifica, menu). Un clic su una riga apre la pagina; la freccia di un capitolo apre o chiude i suoi sottocapitoli."""

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import PageNode
from ...formatting import short_date
from .row_table import RowTable

_CHAPTER_H, _SUB_H = 48, 44
_GAP = 12
_COUNT_W, _WORDS_W, _DATE_W, _DOTS_W = 108, 92, 70, 30     # le colonne a destra, come nel disegno
_ICON = 15
_SUB_LEFT = 14 + _ICON + _GAP + 24          # un sottocapitolo comincia più a destra del numero del suo capitolo


def _plural(count: int, one: str, many: str) -> str:
    return f"{count:,} {one if count == 1 else many}".replace(",", ".")


@dataclass(frozen=True)
class _Line:
    """Una riga dell'elenco, già pronta da disegnare."""
    node: PageNode
    number: str
    is_chapter: bool
    count: str          # «3 sottocapitoli» (solo i capitoli che ne hanno)
    words: str
    when: str
    open: bool          # capitolo con i sottocapitoli visibili
    foldable: bool      # capitolo con almeno un sottocapitolo


class _Table(RowTable):
    """Le righe dell'elenco: capitoli e sottocapitoli."""
    chosen = Signal(int)
    toggled = Signal(int)                  # ID del capitolo da aprire o chiudere
    menu_requested = Signal(int, QPoint)   # ID e punto sullo schermo

    def __init__(self):
        super().__init__()
        self._lines: list[_Line] = []
        self.row_clicked.connect(self._clicked)

    def set_lines(self, lines: list[_Line]) -> None:
        self._lines = lines
        self.set_count(len(lines))

    def row_height(self, index: int) -> int:
        return _CHAPTER_H if self._lines[index].is_chapter else _SUB_H

    # --- Geometria di una riga ----------------------------------------------------------------
    def _dots_rect(self, index: int) -> QRect:
        return QRect(self.width() - 1 - 10 - _DOTS_W, self.top(index), _DOTS_W, self.row_height(index))

    def _chevron_rect(self, index: int) -> QRect:
        return QRect(1, self.top(index), 14 + _ICON + 8, _CHAPTER_H)       # la freccia e un po' d'aria intorno

    # --- Disegno --------------------------------------------------------------------------------
    def paint_row(self, painter: QPainter, index: int, row: QRect, hovered: bool) -> None:
        line, top, height = self._lines[index], row.top(), row.height()
        muted = QColor(theme.MUTED)

        right = row.right() - 10 + 1
        dots = QRect(right - _DOTS_W, top, _DOTS_W, height)
        if hovered:
            icons.icon("more", theme.MUTED).paint(painter, QRect(dots.center().x() - 8, top + (height - 16) // 2, 16, 16))
        date = QRect(dots.left() - _GAP - _DATE_W, top, _DATE_W, height)
        words = QRect(date.left() - _GAP - _WORDS_W, top, _WORDS_W, height)
        count = QRect(words.left() - _GAP - _COUNT_W, top, _COUNT_W, height)
        painter.setFont(theme.ui_font(13))
        painter.setPen(muted)
        painter.drawText(date, Qt.AlignVCenter | Qt.AlignRight, line.when)
        painter.drawText(words, Qt.AlignVCenter | Qt.AlignRight, line.words)
        painter.drawText(count, Qt.AlignVCenter | Qt.AlignLeft, line.count)

        left = row.left() + (14 if line.is_chapter else _SUB_LEFT)
        if line.is_chapter:
            if line.foldable:
                icons.icon("chevron-down" if line.open else "chevron-right", theme.MUTED).paint(
                    painter, QRect(left, top + (height - _ICON) // 2, _ICON, _ICON))
            left += _ICON + _GAP
        number_width = 22 if line.is_chapter else 34
        painter.setFont(theme.ui_font(14, 600) if line.is_chapter else theme.ui_font(13))
        painter.drawText(QRect(left, top, number_width, height), Qt.AlignVCenter | Qt.AlignLeft, line.number)
        left += number_width + _GAP

        font = theme.ui_font(15, 600) if line.is_chapter else theme.ui_font(14, 500)
        room = count.left() - _GAP - left
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_ACTIVE if line.is_chapter else theme.TEXT))
        painter.drawText(QRect(left, top, room, height), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(font).elidedText(line.node.title, Qt.ElideRight, room))

    # --- Mouse -------------------------------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        index = self.index_at(int(event.position().y()))
        self.setToolTip("Altre azioni" if index >= 0 and self._dots_rect(index).contains(event.position().toPoint()) else "")

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.setToolTip("")

    def _clicked(self, index: int, point: QPoint) -> None:
        line = self._lines[index]
        if self._dots_rect(index).contains(point):
            dots = self._dots_rect(index)
            self.menu_requested.emit(line.node.id, self.mapToGlobal(dots.bottomRight()))
        elif line.is_chapter and line.foldable and self._chevron_rect(index).contains(point):
            self.toggled.emit(line.node.id)
        else:
            self.chosen.emit(line.node.id)


class WritingHome(QScrollArea):
    chosen = Signal(int)                   # ID della pagina scelta
    create_requested = Signal()            # «Nuovo capitolo»
    menu_requested = Signal(int, QPoint)   # menu «⋯» di una pagina

    def __init__(self):
        super().__init__()
        self._rows: list[tuple[PageNode, str]] = []
        self._folded: set[int] = set()      # i capitoli chiusi: finché la campagna è aperta restano come li ha lasciati l'utente

        title = QLabel("Scrittura")
        title.setFont(theme.serif_font(38, 500, -0.01))
        self._summary = QLabel()
        self._summary.setObjectName("Muted")
        self._summary.setFont(theme.ui_font(13))
        add = QPushButton("Nuovo capitolo")
        add.setIcon(icons.icon("plus", theme.TEXT))
        add.setIconSize(QSize(16, 16))
        add.setFixedHeight(36)
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: self.create_requested.emit())
        self._table = _Table()
        self._table.chosen.connect(self.chosen)
        self._table.toggled.connect(self._toggle)
        self._table.menu_requested.connect(self.menu_requested)

        heading = QVBoxLayout()
        heading.setSpacing(4)
        heading.addWidget(title)
        heading.addWidget(self._summary)
        header = QHBoxLayout()
        header.addLayout(heading, 1)
        header.addWidget(add, alignment=Qt.AlignBottom)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(44, 34, 44, 34)
        layout.setSpacing(24)
        layout.addLayout(header)
        layout.addWidget(self._table)
        layout.addStretch()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)
        self._refresh()

    def set_pages(self, rows: list[tuple[PageNode, str]]) -> None:
        """Ricostruisce l'elenco da (pagina, numero) nell'ordine dell'albero."""
        self._rows = rows
        self._folded &= {node.id for node, _ in rows}
        self._refresh()

    def _toggle(self, chapter_id: int) -> None:
        self._folded ^= {chapter_id}
        self._refresh()

    def _refresh(self) -> None:
        subs: dict[int, list[PageNode]] = {}
        for node, _ in self._rows:
            if node.parent_id is not None:
                subs.setdefault(node.parent_id, []).append(node)
        lines = []
        for node, number in self._rows:
            if node.parent_id is None:
                family = [node, *subs.get(node.id, [])]        # un capitolo conta le parole e l'ultima modifica anche dei suoi sottocapitoli
                lines.append(_Line(node, number, True, _plural(len(family) - 1, "sottocapitolo", "sottocapitoli") if len(family) > 1 else "",
                                   _plural(sum(n.words for n in family), "parola", "parole"),
                                   short_date(max(n.modified_at for n in family)), node.id not in self._folded, len(family) > 1))
            elif node.parent_id not in self._folded:
                lines.append(_Line(node, number, False, "", _plural(node.words, "parola", "parole"), short_date(node.modified_at), False, False))
        self._table.set_lines(lines)
        chapters = sum(1 for node, _ in self._rows if node.parent_id is None)
        self._summary.setText(" · ".join((_plural(chapters, "capitolo", "capitoli"),
                                         _plural(len(self._rows) - chapters, "sottocapitolo", "sottocapitoli"),
                                         _plural(sum(node.words for node, _ in self._rows), "parola", "parole"))))
