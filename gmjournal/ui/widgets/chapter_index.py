"""Pagina generale di Scrittura: l'elenco dei capitoli e dei sottocapitoli. Un clic apre la pagina."""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import PageNode

_ROW_HEIGHT = 46
_SUB_INDENT = 34       # rientro dei sottocapitoli
_COLUMN_WIDTH = 760


class _Row(QAbstractButton):
    def __init__(self, node: PageNode, number: str):
        super().__init__()
        self._node, self._number = node, number
        self.setFixedHeight(_ROW_HEIGHT)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def sizeHint(self) -> QSize:
        return QSize(100, _ROW_HEIGHT)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        hovered = self.underMouse()
        if hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER_SOFT))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        chapter = self._node.parent_id is None
        left = 14 + (0 if chapter else _SUB_INDENT)
        number_font = theme.ui_font(13, 500)
        painter.setFont(number_font)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QRect(left, 0, 40, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self._number)

        title_font = theme.ui_font(16, 600) if chapter else theme.ui_font(15)
        text_left = left + 44
        room = self.width() - text_left - 44
        painter.setFont(title_font)
        painter.setPen(QColor(theme.TEXT_ACTIVE if chapter else theme.TEXT_SOFT))
        title = QFontMetrics(title_font).elidedText(self._node.title, Qt.ElideRight, room)
        painter.drawText(QRect(text_left, 0, room, self.height()), Qt.AlignVCenter | Qt.AlignLeft, title)
        if hovered:
            icons.icon("chevron-right", theme.MUTED).paint(painter, QRect(self.width() - 32, (self.height() - 16) // 2, 16, 16))


class ChapterIndex(QScrollArea):
    chosen = Signal(int)            # ID della pagina scelta
    create_requested = Signal()     # «Nuovo capitolo»

    def __init__(self):
        super().__init__()
        title = QLabel("Scrittura")
        title.setFont(theme.serif_font(46, 500, -0.01))
        self._summary = QLabel()
        self._summary.setObjectName("Muted")
        self._summary.setFont(theme.ui_font(16))
        add = QPushButton("Nuovo capitolo")
        add.setObjectName("DashedButton")
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: self.create_requested.emit())

        self._rows = QVBoxLayout()
        self._rows.setSpacing(2)
        column = QWidget()
        column.setMaximumWidth(_COLUMN_WIDTH)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(self._summary)
        layout.addSpacing(36)
        layout.addLayout(self._rows)
        layout.addSpacing(18)
        layout.addWidget(add, alignment=Qt.AlignLeft)
        layout.addStretch()

        content = QWidget()
        outer = QHBoxLayout(content)
        outer.setContentsMargins(48, 72, 48, 48)
        outer.addStretch()
        outer.addWidget(column, 1)
        outer.addStretch()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)

    def set_pages(self, rows: list[tuple[PageNode, str]]) -> None:
        """Ricostruisce l'elenco da (pagina, numero) nell'ordine dell'albero."""
        while self._rows.count():
            widget = self._rows.takeAt(0).widget()      # gli spazi non hanno un widget
            if widget is not None:
                widget.deleteLater()
        for node, number in rows:
            if node.parent_id is None and self._rows.count():
                self._rows.addSpacing(8)                # un po' d'aria prima di ogni capitolo
            row = _Row(node, number)
            row.clicked.connect(lambda _=False, page_id=node.id: self.chosen.emit(page_id))
            self._rows.addWidget(row)
        chapters = sum(1 for node, _ in rows if node.parent_id is None)
        subs = len(rows) - chapters
        self._summary.setText(f"{chapters} {'capitolo' if chapters == 1 else 'capitoli'} · "
                              f"{subs} {'sottocapitolo' if subs == 1 else 'sottocapitoli'}")
