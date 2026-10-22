"""Un elenco di voci a due righe (titolo e, sotto, una breve descrizione): le schede tecniche, gli incontri, le scelte dei popup.

È una lista vera e non una colonna di widget, così regge anche migliaia di voci senza rallentare.
"""

from dataclasses import dataclass

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QStyle, QStyledItemDelegate

from ... import icons, theme

_ID, _CAPTION, _STATE, _TAG, _TAG_COLOR = (Qt.UserRole + number for number in range(5))
_ROW_HEIGHT = 50
MARKED, DISABLED = "marked", "disabled"     # una voce scelta (con la spunta) e una che non si può scegliere (attenuata)


@dataclass(frozen=True)
class ListItem:
    id: int
    title: str
    caption: str
    state: str = ""
    tag: str = ""           # una parola in coda alla descrizione, nel suo colore (la difficoltà di un incontro): non viene mai accorciata
    tag_color: str = ""


class _Delegate(QStyledItemDelegate):
    @staticmethod
    def _write(painter: QPainter, font: QFont, color: str, text: str, left: float, top: float, room: float) -> float:
        """Scrive `text` su una riga (con «…» se non sta in `room`) e dice quanto spazio ha preso."""
        shown = QFontMetrics(font).elidedText(text, Qt.ElideRight, int(room))
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(QRectF(left, top, room, 18), Qt.AlignVCenter | Qt.AlignLeft, shown)
        return QFontMetrics(font).horizontalAdvance(shown)

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(100, _ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(0, 1, 0, -1)
        state = index.data(_STATE)
        selected, hovered = option.state & QStyle.State_Selected, option.state & QStyle.State_MouseOver
        if selected or hovered or state == MARKED:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER if selected or state == MARKED else theme.HOVER_SOFT))
            painter.drawRoundedRect(rect, theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        room = rect.width() - (48 if state == MARKED else 24)
        dim = state == DISABLED
        left, small, tag = rect.left() + 12, theme.ui_font(12), index.data(_TAG)
        self._write(painter, theme.ui_font(14, 500), theme.DISABLED if dim else theme.TEXT, index.data(Qt.DisplayRole), left, rect.top() + 6, room)
        caption = index.data(_CAPTION) + (" · " if tag else "")
        used = self._write(painter, small, theme.DISABLED if dim else theme.MUTED, caption, left, rect.top() + 27,
                           room - QFontMetrics(small).horizontalAdvance(tag))
        if tag:
            self._write(painter, small, theme.DISABLED if dim else index.data(_TAG_COLOR), tag, left + used, rect.top() + 27, room - used)
        if state == MARKED:
            icons.icon("check", theme.ACCENT).paint(painter, int(rect.right() - 34), int(rect.center().y() - 9), 18, 18)
        painter.restore()


class ItemList(QListView):
    chosen = Signal(int)        # l'ID della voce scelta

    def __init__(self):
        super().__init__()
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self.setItemDelegate(_Delegate(self))
        self.setFrameShape(QFrame.NoFrame)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.viewport().setAutoFillBackground(False)
        self.clicked.connect(self._clicked)

    def _clicked(self, index: QModelIndex) -> None:
        if index.data(_STATE) != DISABLED:
            self.chosen.emit(index.data(_ID))

    def set_items(self, items: list[ListItem], selected: int | None) -> None:
        """Mostra queste voci (nell'ordine dato) e evidenzia quella con ID `selected`, se c'è."""
        self._model.clear()
        for entry in items:
            item = QStandardItem(entry.title)
            item.setData(entry.id, _ID)
            item.setData(entry.caption, _CAPTION)
            item.setData(entry.state, _STATE)
            item.setData(entry.tag, _TAG)
            item.setData(entry.tag_color, _TAG_COLOR)
            self._model.appendRow(item)
        self.select(selected)

    def select(self, item_id: int | None) -> None:
        """Evidenzia la voce (e la porta in vista) senza segnalare nulla."""
        for number in range(self._model.rowCount()):
            index = self._model.index(number, 0)
            if index.data(_ID) == item_id:
                self.setCurrentIndex(index)
                self.scrollTo(index)
                return
        self.clearSelection()
        self.setCurrentIndex(QModelIndex())

    def set_state(self, item_id: int, state: str) -> None:
        """Cambia lo stato di una voce (`MARKED`, `DISABLED` o vuoto) senza ricostruire l'elenco."""
        for number in range(self._model.rowCount()):
            item = self._model.item(number)
            if item.data(_ID) == item_id:
                item.setData(state, _STATE)
                return
