"""Il selettore «Collega un luogo…»: si apre sotto il pulsante, si cerca per nome e si sceglie con un clic o con Invio."""

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QModelIndex, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate, QWidget,
)

from ... import icons, theme
from ...data.search import rank
from ...elements import ElementKind
from .group_label import group_label
from .menu import PopupMenu

_ROW_HEIGHT = 46
_VISIBLE_ROWS = 5
_ICON_BOX = 28


@dataclass(frozen=True)
class PickerRow:
    element_id: int
    name: str
    detail: str        # la categoria
    linked: bool       # già collegato: si vede ma non si può scegliere


class _RowDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget, kind: ElementKind):
        super().__init__(parent)
        self._kind = kind

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(option.rect.width(), _ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        row: PickerRow = index.data(Qt.UserRole)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(0, 1, 0, -1)
        if row.linked:
            painter.setOpacity(0.55)
        elif option.state & QStyle.State_Selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.MENU_HOVER))
            painter.drawRoundedRect(rect, theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        box = QRect(int(rect.left()) + 10, int(rect.top()) + (int(rect.height()) - _ICON_BOX) // 2, _ICON_BOX, _ICON_BOX)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.tint(self._kind.color))
        painter.drawRoundedRect(box, 8, 8)
        icons.icon(self._kind.icon, self._kind.color).paint(painter, box.adjusted(6, 6, -6, -6))

        right = int(rect.right()) - 10
        if row.linked:
            painter.setFont(theme.ui_font(12))
            painter.setPen(QColor(theme.MUTED))
            label = "Già collegato"
            width = QFontMetrics(painter.font()).horizontalAdvance(label)
            painter.drawText(QRect(right - width, int(rect.top()), width, int(rect.height())), Qt.AlignVCenter | Qt.AlignRight, label)
            icons.icon("check", theme.MUTED).paint(painter, QRect(right - width - 20, int(rect.top()) + (int(rect.height()) - 14) // 2, 14, 14))
            right -= width + 28
        text_left = box.right() + 12
        room = max(40, right - text_left)
        for font, color, text, top in ((theme.ui_font(14, 500), theme.TEXT_ACTIVE, row.name, 5),
                                       (theme.ui_font(12), theme.MUTED, row.detail, 24)):
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(QRect(text_left, int(rect.top()) + top, room, 20), Qt.AlignVCenter | Qt.AlignLeft,
                             QFontMetrics(font).elidedText(text, Qt.ElideRight, room))
        painter.restore()


class _CreateButton(QAbstractButton):
    """La riga «Crea un luogo “Va”»: un riquadro tratteggiato con il +, poi il testo."""

    def __init__(self, color: str):
        super().__init__()
        self._color = color
        self.setFixedHeight(_ROW_HEIGHT - 4)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.MENU_HOVER))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        box = QRect(10, (self.height() - _ICON_BOX) // 2, _ICON_BOX, _ICON_BOX)
        pen = QPen(QColor(theme.DISABLED), 1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(box).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        icons.icon("plus", self._color).paint(painter, box.adjusted(6, 6, -6, -6))
        painter.setFont(theme.ui_font(14, 500))
        painter.setPen(QColor(theme.TEXT))
        room = self.width() - box.right() - 22
        painter.drawText(QRect(box.right() + 12, 0, room, self.height()), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(painter.font()).elidedText(self.text(), Qt.ElideRight, room))


class ElementPicker(PopupMenu):
    """Elenca gli elementi di un tipo (`rows`, già in ordine) e restituisce quello scelto. Si chiude da solo."""

    chosen = Signal(int)              # ID dell'elemento scelto
    create_requested = Signal(str)    # «Crea…»: il nome scritto finora

    def __init__(self, parent: QWidget, kind: ElementKind, rows: list[PickerRow], width: int):
        super().__init__(parent, width=width)
        self._kind, self._rows = kind, rows
        self._search = QLineEdit()
        self._search.setPlaceholderText(f"Cerca {kind.a}…")
        self._search.setFixedHeight(38)
        self._search.addAction(icons.icon("search", theme.MUTED), QLineEdit.LeadingPosition)
        self._search.installEventFilter(self)
        self._search.textChanged.connect(self._refresh)
        self._heading = group_label()
        self._heading.setContentsMargins(10, 8, 0, 4)
        self._list = QListWidget()
        self._list.setObjectName("TargetList")
        self._list.setFrameShape(QFrame.NoFrame)
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._list.setItemDelegate(_RowDelegate(self._list, kind))
        self._list.setMouseTracking(True)
        self._list.itemEntered.connect(lambda item: item.flags() & Qt.ItemIsEnabled and self._list.setCurrentItem(item))
        self._list.itemClicked.connect(lambda item: self._choose(item.data(Qt.UserRole)))
        self._create = _CreateButton(kind.color)
        self._create.clicked.connect(self._request_create)
        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        hint = QLabel("Invio per collegare · Esc per chiudere")
        hint.setObjectName("Muted")
        hint.setFont(theme.ui_font(11))
        hint.setContentsMargins(10, 8, 0, 4)

        for widget in (self._search, self._heading, self._list, divider, self._create, hint):
            self._items.addWidget(widget)
        self._items.setContentsMargins(6, 6, 6, 4)
        self._items.setSpacing(4)
        self._refresh()

    def _refresh(self) -> None:
        query = self._search.text().strip()
        found = [(rank(query, row.name), row) for row in self._rows] if query else [(0, row) for row in self._rows]
        shown = [row for score, row in sorted((f for f in found if f[0] is not None), key=lambda f: f[0])]
        self._heading.setText(f"RISULTATI · {self._kind.title.upper()}" if query else self._kind.title.upper())
        self._list.clear()
        for row in shown:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, row)
            if row.linked:
                item.setFlags(Qt.NoItemFlags)
            self._list.addItem(item)
        self._list.setVisible(bool(shown))
        self._list.setFixedHeight(min(len(shown), _VISIBLE_ROWS) * _ROW_HEIGHT)
        first = next((i for i, row in enumerate(shown) if not row.linked), None)
        if first is not None:
            self._list.setCurrentRow(first)
        self._create.setText(f"Crea {self._kind.a} “{query}”" if query else f"Crea {self._kind.a} nuovo")
        self.adjustSize()

    def _move(self, delta: int) -> None:
        enabled = [i for i in range(self._list.count()) if self._list.item(i).flags() & Qt.ItemIsEnabled]
        if enabled:
            current = self._list.currentRow()
            position = enabled.index(current) if current in enabled else -1
            self._list.setCurrentRow(enabled[(position + delta) % len(enabled)])

    def _choose(self, row: PickerRow) -> None:
        self.close()
        self.chosen.emit(row.element_id)

    def _request_create(self) -> None:
        query = self._search.text().strip()
        self.close()
        self.create_requested.emit(query)

    def popup_below(self, widget: QWidget) -> None:
        super().popup_below(widget)
        self._search.setFocus()

    def eventFilter(self, watched, event: QEvent) -> bool:
        if watched is self._search and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Up, Qt.Key_Down):
                self._move(-1 if key == Qt.Key_Up else 1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                item = self._list.currentItem()
                if item is not None and item.flags() & Qt.ItemIsEnabled:
                    self._choose(item.data(Qt.UserRole))
                elif self._search.text().strip() and not any(self._list.item(i).flags() & Qt.ItemIsEnabled for i in range(self._list.count())):
                    self._request_create()      # nessun risultato: Invio crea ciò che si è scritto
                return True
            if key == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)
