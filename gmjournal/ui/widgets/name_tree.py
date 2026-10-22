"""L'elenco della barra sinistra (le mappe, i grafi): un albero con tanti livelli, ogni voce con le sue sottovoci che si aprono e si chiudono.

Se nessuna voce sta dentro un'altra (i grafi) è un semplice elenco."""

from collections import defaultdict

from PySide6.QtCore import QModelIndex, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractItemView, QFrame, QStyle, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

from ... import icons, theme

_ID = Qt.UserRole
_ROW = 34
_INDENT = 16        # rientro per ogni livello
_ARROW = 18         # lato dell'area della freccia che apre e chiude
_DOTS = 26          # lato dell'area del pulsante «⋯»


def _depth(index: QModelIndex) -> int:
    depth, parent = 0, index.parent()
    while parent.isValid():
        depth, parent = depth + 1, parent.parent()
    return depth


def _arrow_rect(row: QRect, depth: int) -> QRect:
    return QRect(row.left() + 4 + depth * _INDENT, row.top() + (row.height() - _ARROW) // 2, _ARROW, _ARROW)


def _dots_rect(row: QRect) -> QRect:
    return QRect(row.right() - _DOTS - 2, row.top() + (row.height() - _DOTS) // 2, _DOTS, _DOTS)


class _Delegate(QStyledItemDelegate):
    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(option.rect.width(), _ROW)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        row = option.rect.adjusted(0, 1, 0, -1)
        if selected or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER if selected else theme.HOVER_SOFT))
            painter.drawRoundedRect(QRectF(row), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)

        depth = _depth(index)
        arrow = _arrow_rect(row, depth)
        if index.model().hasChildren(index):
            name = "chevron-down" if option.state & QStyle.State_Open else "chevron-right"
            icons.icon(name, theme.MUTED).paint(painter, arrow.adjusted(2, 2, -2, -2))
        font = theme.ui_font(14, 500 if selected or depth == 0 else 400)
        text_left = arrow.right() + 4
        room = row.right() - _DOTS - 6 - text_left
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_ACTIVE if selected else theme.TEXT if depth == 0 else theme.TEXT_SOFT))
        painter.drawText(QRect(text_left, row.top(), room, row.height()), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(font).elidedText(index.data(Qt.DisplayRole), Qt.ElideRight, room))
        if selected or hovered:
            icons.icon("more", theme.MUTED).paint(painter, _dots_rect(row).adjusted(3, 3, -3, -3))
        painter.restore()


class NameTree(QTreeWidget):
    selected = Signal(int)                  # l'utente ha scelto una voce
    menu_requested = Signal(int, QPoint)    # menu di una voce: ID e punto sullo schermo

    def __init__(self):
        super().__init__()
        self.setObjectName("PageTree")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setUniformRowHeights(True)
        self.setExpandsOnDoubleClick(False)
        self.setItemDelegate(_Delegate(self))
        self.setMouseTracking(True)
        self._closed: set[int] = set()      # le voci che l'utente ha chiuso: restano chiuse quando l'albero si ricostruisce
        self.currentItemChanged.connect(self._on_current_changed)

    # --- Contenuto ------------------------------------------------------------------
    def set_items(self, items: list[tuple[int, int | None, str]], select_id: int | None) -> None:
        """Ricostruisce l'albero; `items` sono (ID, ID di chi la contiene o None, nome) in ordine alfabetico, `select_id` è la voce evidenziata."""
        self.blockSignals(True)
        scroll = self.verticalScrollBar().value()
        self.clear()
        inside = defaultdict(list)
        for item_id, parent_id, name in items:
            inside[parent_id].append((item_id, name))
        rows: dict[int, QTreeWidgetItem] = {}

        def add(parent: QTreeWidgetItem, parent_id: int | None) -> None:
            for item_id, name in inside[parent_id]:
                row = QTreeWidgetItem([name])
                row.setData(0, _ID, item_id)
                row.setToolTip(0, name)
                parent.addChild(row)
                rows[item_id] = row
                add(row, item_id)

        add(self.invisibleRootItem(), None)
        for item_id, row in rows.items():
            row.setExpanded(item_id not in self._closed)
        if select_id in rows:
            self.setCurrentItem(rows[select_id])
        self.blockSignals(False)
        self.doItemsLayout()
        self.verticalScrollBar().setValue(scroll)
        self.viewport().update()

    # --- Scelta e menu ------------------------------------------------------------------
    def _on_current_changed(self, current: QTreeWidgetItem | None, _previous) -> None:
        if current is not None:
            self.selected.emit(current.data(0, _ID))

    def mousePressEvent(self, event) -> None:
        point = event.position().toPoint()
        item = self.itemAt(point)
        if item is not None and event.button() == Qt.LeftButton:
            row = self.visualItemRect(item).adjusted(0, 1, 0, -1)
            if _dots_rect(row).contains(point):
                self.menu_requested.emit(item.data(0, _ID), self.viewport().mapToGlobal(_dots_rect(row).bottomRight()))
                return
            if item.childCount() and _arrow_rect(row, _depth(self.indexFromItem(item))).contains(point):
                self._toggle(item)
                return
        super().mousePressEvent(event)

    def _toggle(self, item: QTreeWidgetItem) -> None:
        item.setExpanded(not item.isExpanded())
        (self._closed.discard if item.isExpanded() else self._closed.add)(item.data(0, _ID))

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(self.viewport().mapFromGlobal(event.globalPos()))
        if item is not None:
            self.menu_requested.emit(item.data(0, _ID), event.globalPos())
