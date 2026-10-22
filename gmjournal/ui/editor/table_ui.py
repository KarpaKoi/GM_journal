"""Le parti visibili delle tabelle nel testo: la griglia per sceglierne la misura, la barra che compare sopra
la tabella in cui si scrive, i «+» ai bordi e le misure di righe e colonne (per disegnarle).

Le operazioni sulla tabella sono in `commands.py`; qui ci sono solo pulsanti che le chiamano.
"""

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QTextDocument, QTextTable
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QToolButton, QWidget

from ... import icons, theme
from ..widgets.group_label import group_label
from ..widgets.menu import PopupMenu
from ..widgets.strip import HorizontalStrip
from . import commands

GRID_COLUMNS, GRID_ROWS = 8, 6      # la misura più grande che si sceglie dalla griglia (poi la tabella può crescere)
_GRID_CELL, _GRID_GAP = 22, 3
_BAR_GAP = 12                       # fra la barra e il bordo alto della tabella
_PLUS = 24                          # diametro dei «+»
_PLUS_GAP = 10                      # fra un «+» e il bordo della tabella
_EDGE = 8                           # distanza minima dai bordi dell'editor


@dataclass(frozen=True)
class TableGrid:
    """I bordi di righe e colonne di una tabella in coordinate del documento: `rows` ha un valore in più del numero
    di righe (l'alto di ognuna e, in fondo, il basso dell'ultima), `columns` uno in più del numero di colonne."""
    rows: list[float]
    columns: list[float]

    def rect(self) -> QRectF:
        return QRectF(self.columns[0], self.rows[0], self.columns[-1] - self.columns[0], self.rows[-1] - self.rows[0])

    def cell(self, row: int, column: int) -> QRectF:
        return QRectF(self.columns[column], self.rows[row], self.columns[column + 1] - self.columns[column],
                      self.rows[row + 1] - self.rows[row])


def table_grid(doc: QTextDocument, table: QTextTable) -> TableGrid:
    """Misura la tabella dalle posizioni del testo nelle celle (Qt non dà i rettangoli delle celle)."""
    layout = doc.documentLayout()
    pad = table.format().cellPadding()

    def first(row: int, column: int) -> QRectF:
        return layout.blockBoundingRect(table.cellAt(row, column).firstCursorPosition().block())

    last_row = table.rows() - 1
    bottom = max(layout.blockBoundingRect(table.cellAt(last_row, column).lastCursorPosition().block()).bottom()
                 for column in range(table.columns()))
    rows = [first(row, 0).top() - pad for row in range(table.rows())] + [bottom + pad]
    columns = [first(0, column).left() - pad for column in range(table.columns())]
    return TableGrid(rows, columns + [columns[0] + doc.textWidth()])      # la tabella è larga quanto il testo


# --- Scelta della misura -------------------------------------------------------------------------
def size_label(rows: int, columns: int) -> str:
    return f"{columns} {'colonna' if columns == 1 else 'colonne'} × {rows} {'riga' if rows == 1 else 'righe'}"


class _SizeGrid(QWidget):
    """La griglia di quadratini: passando il mouse si sceglie la misura, il clic la conferma."""

    def __init__(self, on_hover: Callable[[int, int], None], on_choose: Callable[[int, int], None]):
        super().__init__()
        self._on_hover, self._on_choose = on_hover, on_choose
        self._size = (3, 3)           # (righe, colonne) evidenziate
        step = _GRID_CELL + _GRID_GAP
        self.setFixedSize(GRID_COLUMNS * step - _GRID_GAP, GRID_ROWS * step - _GRID_GAP)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def size_chosen(self) -> tuple[int, int]:
        return self._size

    def _cell_at(self, point: QPoint) -> tuple[int, int]:
        step = _GRID_CELL + _GRID_GAP
        return (max(1, min(GRID_ROWS, point.y() // step + 1)), max(1, min(GRID_COLUMNS, point.x() // step + 1)))

    def mouseMoveEvent(self, event) -> None:
        size = self._cell_at(event.position().toPoint())
        if size != self._size:
            self._size = size
            self._on_hover(*size)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._on_choose(*self._cell_at(event.position().toPoint()))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        step = _GRID_CELL + _GRID_GAP
        chosen_fill = theme.tint(theme.ACCENT, 0.35)
        for row in range(GRID_ROWS):
            for column in range(GRID_COLUMNS):
                on = row < self._size[0] and column < self._size[1]
                painter.setPen(QColor(theme.ACCENT if on else theme.TABLE_GRID_LINE))
                painter.setBrush(chosen_fill if on else Qt.NoBrush)
                painter.drawRoundedRect(QRectF(column * step + 0.5, row * step + 0.5, _GRID_CELL - 1, _GRID_CELL - 1), 4, 4)


class TableSizePopup(PopupMenu):
    """Il riquadro sotto il pulsante «tabella»: griglia 8 × 6 e la misura scelta («3 colonne × 3 righe»)."""

    def __init__(self, parent: QWidget, on_choose: Callable[[int, int], None]):
        super().__init__(parent, width=236)
        self._on_choose = on_choose
        title = group_label("Inserisci tabella")
        title.setContentsMargins(2, 0, 0, 10)
        self._grid = _SizeGrid(self._show_size, self._choose)
        self._label = QLabel(size_label(*self._grid.size_chosen()))
        self._label.setFont(theme.ui_font(13))
        self._label.setContentsMargins(2, 10, 0, 0)
        for widget in (title, self._grid, self._label):
            self._items.addWidget(widget)
        self._items.setContentsMargins(12, 12, 12, 12)

    def _show_size(self, rows: int, columns: int) -> None:
        self._label.setText(size_label(rows, columns))

    def _choose(self, rows: int, columns: int) -> None:
        self.close()
        self._on_choose(rows, columns)


# --- Barra sopra la tabella e «+» ai bordi --------------------------------------------------------
class _BarButton(QToolButton):
    def __init__(self, icon_name: str, text: str, color: str):
        super().__init__()
        self.setObjectName("TableBarButton")
        self.setText(text)
        self.setIcon(icons.icon(icon_name, color))
        self.setIconSize(QSize(14, 14))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setFixedHeight(28)
        self.setFont(theme.ui_font(13, 500))
        self.setStyleSheet(f"QToolButton {{ color: {color}; }} QToolButton:disabled {{ color: {theme.DISABLED}; }}")
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)


class _PlusButton(QToolButton):
    def __init__(self, tooltip: str):
        super().__init__()
        self.setObjectName("TablePlus")
        self.setIcon(icons.icon("plus", theme.TEXT))
        self.setIconSize(QSize(14, 14))
        self.setFixedSize(_PLUS, _PLUS)
        self.setToolTip(tooltip)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)


class TableControls:
    """La barra «Riga sopra · Riga sotto · Colonna a destra | Elimina riga · Elimina colonna · Elimina tabella» e i due
    «+» (colonna a destra, riga in fondo) della tabella in cui si trova il cursore. Sono figli dell'editor, non del testo: il «+» di destra sta fuori
    dalla colonna di testo. Se l'editor è stretto la barra si accorcia e scorre di lato con la rotella (come la barra
    degli strumenti)."""

    def __init__(self, editor):
        self._editor = editor
        self.bar = QFrame(editor)
        self.bar.setObjectName("TableBar")
        shadow = QGraphicsDropShadowEffect(self.bar)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 128))
        self.bar.setGraphicsEffect(shadow)
        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        def add(icon_name: str, text: str, color: str, action: Callable[[], None]) -> _BarButton:
            button = _BarButton(icon_name, text, color)
            button.clicked.connect(lambda _=False: self._run(action))
            row.addWidget(button)
            return button

        add("plus", "Riga sopra", theme.TEXT, lambda: commands.add_row(editor, "above"))
        add("plus", "Riga sotto", theme.TEXT, lambda: commands.add_row(editor, "below"))
        add("plus", "Colonna a destra", theme.TEXT, lambda: commands.add_column(editor, "right"))
        line = QFrame()
        line.setObjectName("ToolbarDivider")
        line.setFixedSize(1, 20)
        row.addSpacing(6)
        row.addWidget(line)
        row.addSpacing(6)
        self._delete_row = add("minus", "Elimina riga", theme.DANGER, lambda: commands.delete_row(editor))
        self._delete_column = add("minus", "Elimina colonna", theme.DANGER, lambda: commands.delete_column(editor))
        add("trash", "Elimina tabella", theme.DANGER, lambda: commands.delete_table(editor))
        frame = QHBoxLayout(self.bar)
        frame.setContentsMargins(4, 4, 4, 4)
        frame.addWidget(HorizontalStrip(buttons))
        self.add_column = _PlusButton("Aggiungi una colonna")
        self.add_column.setParent(editor)
        self.add_column.clicked.connect(lambda _=False: self._run(lambda: commands.add_column(editor, "end")))
        self.add_row = _PlusButton("Aggiungi una riga")
        self.add_row.setParent(editor)
        self.add_row.clicked.connect(lambda _=False: self._run(lambda: commands.add_row(editor, "end")))
        self.hide()

    def _run(self, action: Callable[[], None]) -> None:
        action()
        self._editor.setFocus()

    def hide(self) -> None:
        for widget in (self.bar, self.add_column, self.add_row):
            widget.hide()

    def place(self, table: QRectF, area: QRectF, rows: int, columns: int) -> None:
        """Mette barra e «+» attorno a `table`; `area` è la parte visibile del testo (entrambi in coordinate dell'editor).
        Con una riga o una colonna sola non c'è nulla da togliere: i pulsanti relativi si spengono."""
        if table.bottom() < area.top() or table.top() > area.bottom():
            self.hide()
            return
        self._delete_row.setEnabled(rows > 1)
        self._delete_column.setEnabled(columns > 1)
        bar = self.bar
        width = self._editor.width()
        natural = bar.sizeHint()
        bar.resize(min(natural.width(), width - 2 * _EDGE), natural.height())
        x = max(_EDGE, min(round(table.left()), width - bar.width() - _EDGE))
        y = max(round(area.top()) + _EDGE, round(table.top()) - bar.height() - _BAR_GAP)   # tabella in cima: la barra resta visibile
        bar.move(x, y)
        plus_x = min(round(table.right()) + _PLUS_GAP, width - _PLUS - 2)
        plus_y = round(max(area.top(), table.top()) + min(area.bottom(), table.bottom())) // 2 - _PLUS // 2
        self.add_column.move(plus_x, plus_y)
        self.add_row.move(round(table.center().x()) - _PLUS // 2, round(table.bottom()) + 6)
        bar.show()
        self.add_column.show()
        self.add_row.setVisible(table.bottom() + 6 + _PLUS <= area.bottom())
        for widget in (bar, self.add_column, self.add_row):
            widget.raise_()
