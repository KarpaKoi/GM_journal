"""L'albero dei capitoli (barra sinistra): numerazione automatica, due livelli, trascinamento per riordinare."""

from PySide6.QtCore import QModelIndex, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractItemView, QFrame, QStyle, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

from ... import icons, theme
from ...data.models import PageNode

_ID = Qt.UserRole
_NUMBER = Qt.UserRole + 1
_ROW = 34
_INDENT = 16        # rientro dei sottocapitoli
_DOTS = 26          # lato dell'area del pulsante «⋯»


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

        left = row.left() + 10 + (_INDENT if index.parent().isValid() else 0)
        number_font, title_font = theme.ui_font(12, 500), theme.ui_font(14, 500 if selected else 400)
        number = index.data(_NUMBER)
        number_width = QFontMetrics(number_font).horizontalAdvance(number)
        painter.setFont(number_font)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QRect(left, row.top(), number_width, row.height()), Qt.AlignVCenter | Qt.AlignLeft, number)

        text_left = left + number_width + 8
        room = row.right() - _DOTS - 6 - text_left
        painter.setFont(title_font)
        painter.setPen(QColor(theme.TEXT_ACTIVE if selected else theme.TEXT_SOFT))
        title = QFontMetrics(title_font).elidedText(index.data(Qt.DisplayRole), Qt.ElideRight, room)
        painter.drawText(QRect(text_left, row.top(), room, row.height()), Qt.AlignVCenter | Qt.AlignLeft, title)
        if selected or hovered:
            icons.icon("more", theme.MUTED).paint(painter, _dots_rect(row).adjusted(3, 3, -3, -3))
        painter.restore()


class PageTree(QTreeWidget):
    selected = Signal(int)                  # l'utente ha scelto una pagina
    menu_requested = Signal(int, QPoint)    # menu di una pagina: ID e punto sullo schermo
    moved = Signal(int, object, int)        # pagina trascinata: ID, nuovo capitolo (o None), posto fra i fratelli

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
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.currentItemChanged.connect(self._on_current_changed)

    # --- Contenuto ------------------------------------------------------------------
    def set_pages(self, rows: list[tuple[PageNode, str]], select_id: int | None) -> None:
        """Ricostruisce l'albero da (pagina, numero) nell'ordine dell'albero; `select_id` è la pagina evidenziata."""
        self.blockSignals(True)
        scroll = self.verticalScrollBar().value()
        self.clear()
        items: dict[int, QTreeWidgetItem] = {}
        for node, number in rows:
            item = QTreeWidgetItem([node.title])
            item.setData(0, _ID, node.id)
            item.setData(0, _NUMBER, number)
            item.setToolTip(0, f"{number}  {node.title}")
            (items[node.parent_id] if node.parent_id is not None else self.invisibleRootItem()).addChild(item)
            items[node.id] = item
        self.expandAll()
        if select_id in items:
            self.setCurrentItem(items[select_id])
        self.blockSignals(False)
        self.doItemsLayout()                       # senza questo la barra di scorrimento non ha ancora la sua estensione
        self.verticalScrollBar().setValue(scroll)
        self.viewport().update()

    def select_page(self, page_id: int | None) -> None:
        """Evidenzia una pagina senza che il cambio venga scambiato per una scelta dell'utente."""
        self.blockSignals(True)
        self.setCurrentItem(self._item(page_id) if page_id is not None else None)
        self.blockSignals(False)
        self.viewport().update()

    def page_ids(self) -> list[int]:
        """Le pagine nell'ordine in cui compaiono."""
        ids, stack = [], [self.topLevelItem(i) for i in reversed(range(self.topLevelItemCount()))]
        while stack:
            item = stack.pop()
            ids.append(item.data(0, _ID))
            stack.extend(item.child(i) for i in reversed(range(item.childCount())))
        return ids

    def _item(self, page_id: int) -> QTreeWidgetItem | None:
        stack = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while stack:
            item = stack.pop()
            if item.data(0, _ID) == page_id:
                return item
            stack.extend(item.child(i) for i in range(item.childCount()))
        return None

    # --- Scelta e menu ------------------------------------------------------------------
    def _on_current_changed(self, current: QTreeWidgetItem | None, _previous) -> None:
        if current is not None:
            self.selected.emit(current.data(0, _ID))

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if item is not None and event.button() == Qt.LeftButton:
            row = self.visualItemRect(item).adjusted(0, 1, 0, -1)
            if _dots_rect(row).contains(event.position().toPoint()):
                self.menu_requested.emit(item.data(0, _ID), self.viewport().mapToGlobal(_dots_rect(row).bottomRight()))
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(self.viewport().mapFromGlobal(event.globalPos()))
        if item is not None:
            self.menu_requested.emit(item.data(0, _ID), event.globalPos())

    # --- Trascinamento -------------------------------------------------------------------
    def dropEvent(self, event) -> None:
        """Calcola dove va la pagina trascinata e lo comunica; a spostare e ridisegnare pensa la schermata."""
        dragged = self.currentItem()
        target = self.itemAt(event.position().toPoint())
        position = self.dropIndicatorPosition()
        event.setDropAction(Qt.IgnoreAction)       # l'albero non si sposta da solo: si ricostruisce dopo il salvataggio
        event.accept()
        destination = self._destination(dragged, target, position) if dragged is not None else None
        if destination is not None:
            self.moved.emit(dragged.data(0, _ID), *destination)

    def _destination(self, dragged: QTreeWidgetItem, target: QTreeWidgetItem | None, position) -> tuple[int | None, int] | None:
        """(capitolo, posto fra i fratelli) in cui finisce la pagina trascinata; None se lì non può stare."""
        page_id = dragged.data(0, _ID)
        if target is None or position == QAbstractItemView.OnViewport:
            return None, len(self._siblings(None, page_id))                       # in fondo, fra i capitoli principali
        target_id, target_parent = target.data(0, _ID), target.parent()
        if target_id == page_id or (target_parent is not None and target_parent.data(0, _ID) == page_id):
            return None                                                           # non dentro se stessa
        if position == QAbstractItemView.OnItem and target_parent is None:
            parent_id, index = target_id, len(self._siblings(target_id, page_id))  # dentro il capitolo, in fondo
        else:
            parent_id = target_parent.data(0, _ID) if target_parent is not None else None
            below = position in (QAbstractItemView.BelowItem, QAbstractItemView.OnItem)
            index = self._siblings(parent_id, page_id).index(target_id) + below
        if parent_id is not None and dragged.childCount():
            return None                                                           # un capitolo con sottocapitoli non può diventarlo
        return parent_id, index

    def _siblings(self, parent_id: int | None, excluded_id: int) -> list[int]:
        """Gli ID delle pagine di un gruppo (capitoli principali o sottocapitoli di `parent_id`), senza `excluded_id`."""
        parent = self.invisibleRootItem() if parent_id is None else self._item(parent_id)
        ids = [parent.child(i).data(0, _ID) for i in range(parent.childCount())]
        return [i for i in ids if i != excluded_id]
