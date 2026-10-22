"""L'elenco delle schede tecniche: una riga per scheda (nome e, sotto, taglia, tipo e grado di sfida).

È una lista vera e non una colonna di widget, così regge anche migliaia di schede senza rallentare.
"""

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QStyle, QStyledItemDelegate

from ... import theme
from ...data.models import CreatureRow

_ID, _CAPTION = Qt.UserRole, Qt.UserRole + 1
_ROW_HEIGHT = 50


def caption(row: CreatureRow) -> str:
    """«Large aberration · GS 10»."""
    kind = " ".join(part for part in (row.size, row.kind) if part)
    return " · ".join(part for part in (kind, f"GS {row.challenge}" if row.challenge else "") if part)


class _Delegate(QStyledItemDelegate):
    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(100, _ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(0, 1, 0, -1)
        selected, hovered = option.state & QStyle.State_Selected, option.state & QStyle.State_MouseOver
        if selected or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER if selected else theme.HOVER_SOFT))
            painter.drawRoundedRect(rect, theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        room = rect.width() - 24
        for font, color, text, top in ((theme.ui_font(14, 500), theme.TEXT, index.data(Qt.DisplayRole), 6),
                                       (theme.ui_font(12), theme.MUTED, index.data(_CAPTION), 27)):
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(QRectF(rect.left() + 12, rect.top() + top, room, 18), Qt.AlignVCenter | Qt.AlignLeft,
                             QFontMetrics(font).elidedText(text, Qt.ElideRight, int(room)))
        painter.restore()


class CreatureList(QListView):
    chosen = Signal(int)        # l'ID della scheda scelta

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
        self.clicked.connect(lambda index: self.chosen.emit(index.data(_ID)))

    def set_rows(self, rows: list[CreatureRow], selected: int | None) -> None:
        """Mostra queste schede (nell'ordine dato) e evidenzia quella con ID `selected`, se c'è."""
        self._model.clear()
        for row in rows:
            item = QStandardItem(row.name)
            item.setData(row.id, _ID)
            item.setData(caption(row), _CAPTION)
            self._model.appendRow(item)
        self.select(selected)

    def select(self, creature_id: int | None) -> None:
        """Evidenzia la scheda (e la porta in vista) senza segnalare nulla."""
        for number in range(self._model.rowCount()):
            index = self._model.index(number, 0)
            if index.data(_ID) == creature_id:
                self.setCurrentIndex(index)
                self.scrollTo(index)
                return
        self.clearSelection()
        self.setCurrentIndex(QModelIndex())
