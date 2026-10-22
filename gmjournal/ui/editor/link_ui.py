"""Scegliere a cosa collegare un testo: l'elenco che compare scrivendo «@» e il popup «Collega a…»."""

from typing import Callable

from PySide6.QtCore import QEvent, QModelIndex, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate, QTextEdit, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data import links
from ...data.models import LinkTarget
from ...elements import KINDS
from ..kinds import kind_icon
from ..popups.base import PopupDialog

_ROW_HEIGHT = 38
_MAX_ROWS = 8
MENTION_MAX_LENGTH = 30    # oltre questa lunghezza la «@…» non è più una ricerca
_BREAKS = ("\u2028", "\u2029")   # «a capo» dentro un paragrafo e fine paragrafo: una ricerca non li attraversa
_WORD_STARTS = (" ", "(", "[", _BREAKS[0])   # prima della «@» deve esserci uno di questi (o l'inizio del paragrafo)

LinkSource = Callable[[str, int], list[LinkTarget]]   # (testo cercato, quanti risultati) -> bersagli
CreateTarget = Callable[[LinkTarget], LinkTarget | None]   # una richiesta «crea nuovo…» -> il bersaglio creato (None se annullato)
InsertLink = Callable[[LinkTarget, int, int], None]   # (bersaglio, inizio, fine) del tratto «@nome» da sostituire con il link


def resolve_target(target: LinkTarget, create_target: CreateTarget | None) -> LinkTarget | None:
    """Il bersaglio scelto; se è una riga «Crea…», prima crea l'elemento (None se non si crea)."""
    if target.kind.startswith(links.CREATE):
        return create_target(target) if create_target is not None else None
    return target


class _RowDelegate(QStyledItemDelegate):
    """Una riga: icona, nome e, a destra, la sua descrizione («Pagina 1.2»). Una riga «crea» dice «Crea personaggio “Mira”»."""

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(option.rect.width(), _ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        target: LinkTarget = index.data(Qt.UserRole)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        row = QRectF(option.rect).adjusted(4, 1, -4, -1)
        if option.state & QStyle.State_Selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.MENU_HOVER))
            painter.drawRoundedRect(row, theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        icons.icon(kind_icon(target.kind), theme.TEXT_SOFT).paint(painter, QRect(int(row.left()) + 10, int(row.top()) + 10, 16, 16))

        creating = target.kind.startswith(links.CREATE)
        name = f"Crea {KINDS[target.kind.removeprefix(links.CREATE)].noun} “{target.name}”" if creating else target.name
        detail_font, name_font = theme.ui_font(12), theme.ui_font(14)
        detail_width = QFontMetrics(detail_font).horizontalAdvance(target.detail)
        text_left, right = int(row.left()) + 38, int(row.right()) - 10
        painter.setFont(detail_font)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QRect(right - detail_width, int(row.top()), detail_width, int(row.height())), Qt.AlignVCenter | Qt.AlignRight, target.detail)
        painter.setFont(name_font)
        painter.setPen(QColor(theme.TEXT_ACTIVE))
        room = max(40, right - detail_width - 12 - text_left)
        painter.drawText(QRect(text_left, int(row.top()), room, int(row.height())), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(name_font).elidedText(name, Qt.ElideRight, room))
        painter.restore()


class TargetList(QListWidget):
    """Elenco di bersagli. La riga evidenziata si cambia con `move_selection`; il mouse sceglie con un clic."""

    chosen = Signal(object)   # LinkTarget

    def __init__(self):
        super().__init__()
        self.setObjectName("TargetList")
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setItemDelegate(_RowDelegate(self))
        self.setMouseTracking(True)
        self.itemEntered.connect(lambda item: self.setCurrentItem(item))
        self.itemClicked.connect(lambda item: self.chosen.emit(item.data(Qt.UserRole)))

    def set_targets(self, targets: list[LinkTarget]) -> None:
        self.clear()
        for target in targets:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, target)
            self.addItem(item)
        if targets:
            self.setCurrentRow(0)
        self.viewport().update()

    def current_target(self) -> LinkTarget | None:
        item = self.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def move_selection(self, delta: int) -> None:
        if self.count():
            self.setCurrentRow((self.currentRow() + delta) % self.count())


class TargetPopup(QFrame):
    """Elenco di risultati sotto un punto della finestra: sotto il cursore scrivendo «@», sotto il campo di ricerca in alto.
    Vive dentro un widget della finestra (non è una finestra a sé), quindi non toglie mai il cursore a chi sta scrivendo."""

    chosen = Signal(object)   # LinkTarget

    def __init__(self, host: QWidget, width: int = 340):
        super().__init__(host)
        self.setObjectName("TargetPopup")
        self.setFixedWidth(width)
        self.setFocusPolicy(Qt.NoFocus)
        self._list = TargetList()
        self._list.chosen.connect(self.chosen)
        self._empty = QLabel("Nessun risultato")
        self._empty.setObjectName("Muted")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setFixedHeight(_ROW_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        layout.addWidget(self._list)
        layout.addWidget(self._empty)
        self.hide()

    def show_results(self, targets: list[LinkTarget], anchor: QRect) -> None:
        """Mostra i risultati sotto `anchor` (un rettangolo, nelle coordinate del widget che contiene l'elenco)."""
        self._list.set_targets(targets)
        self._list.setVisible(bool(targets))
        self._empty.setVisible(not targets)
        rows = max(1, min(len(targets), _MAX_ROWS))
        self._list.setFixedHeight(rows * _ROW_HEIGHT if targets else 0)
        self.setFixedHeight(rows * _ROW_HEIGHT + 8)
        area = self.parentWidget().rect()
        x = max(4, min(anchor.left(), area.width() - self.width() - 4))
        y = anchor.bottom() + 6
        if y + self.height() > area.height() - 4:       # non c'è posto sotto: si apre sopra la riga
            y = max(4, anchor.top() - self.height() - 6)
        self.move(x, y)
        self.show()
        self.raise_()

    def current_target(self) -> LinkTarget | None:
        return self._list.current_target()

    def move_selection(self, delta: int) -> None:
        self._list.move_selection(delta)


class MentionController:
    """Fa funzionare la «@» in una casella di testo: scrivendola compare l'elenco sotto il cursore, le frecce scelgono,
    Invio o Tab inseriscono il link, Esc chiude. La casella chiama `typed_at_sign`, `refresh`, `handle_key` e `close`
    al momento giusto; l'elenco vive dentro `host` (lo si crea alla prima «@»)."""

    def __init__(self, editor: QTextEdit, host: Callable[[], QWidget], link_targets: LinkSource | None,
                 create_target: CreateTarget | None, insert_link: InsertLink):
        self._editor, self._host = editor, host
        self._link_targets, self._create_target, self._insert_link = link_targets, create_target, insert_link
        self._popup: TargetPopup | None = None
        self._start: int | None = None      # posizione della «@» in corso

    @property
    def active(self) -> bool:
        return self._start is not None

    def typed_at_sign(self) -> None:
        """Il cursore è subito dopo una «@» appena scritta: se inizia una parola, apre l'elenco."""
        cursor = self._editor.textCursor()
        before = cursor.position() - 2
        starts_word = before < cursor.block().position() or self._editor.document().characterAt(before) in _WORD_STARTS
        if self._link_targets is not None and starts_word:
            self._start = cursor.position() - 1
            self.refresh()

    def refresh(self) -> None:
        """Aggiorna l'elenco in base a ciò che è stato scritto dopo la «@»; lo chiude quando non serve più."""
        if self._start is None:
            return
        cursor = self._editor.textCursor()
        typed = QTextCursor(self._editor.document())
        typed.setPosition(self._start)
        typed.setPosition(max(cursor.position(), self._start), QTextCursor.KeepAnchor)
        text = typed.selectedText()
        query = text[1:]
        if (cursor.hasSelection() or cursor.position() <= self._start or not text.startswith("@")
                or len(query) > MENTION_MAX_LENGTH or any(mark in text for mark in _BREAKS)):
            self.close()
            return
        targets = self._link_targets(query, _MAX_ROWS)
        if not targets and query.endswith(" "):
            self.close()
            return
        start = QTextCursor(self._editor.document())
        start.setPosition(self._start)
        host = self._host()
        if self._popup is None:
            self._popup = TargetPopup(host)
            self._popup.chosen.connect(self._accept)
        local = self._editor.cursorRect(start)
        self._popup.show_results(targets, QRect(self._editor.viewport().mapTo(host, local.topLeft()), local.size()))

    def handle_key(self, event) -> bool:
        """I tasti che governano l'elenco aperto. True se il tasto è stato usato."""
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_Down):
            self._popup.move_selection(-1 if key == Qt.Key_Up else 1)
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
            target = self._popup.current_target()
            if target is not None:
                self._accept(target)
                return True
            self.close()
            return key == Qt.Key_Tab
        if key == Qt.Key_Escape:
            self.close()
            return True
        return False

    def close(self) -> None:
        self._start = None
        if self._popup is not None:
            self._popup.hide()

    def _accept(self, target: LinkTarget) -> None:
        start, end = self._start, self._editor.textCursor().position()
        self.close()
        target = resolve_target(target, self._create_target)
        if target is not None:
            self._insert_link(target, start, end)
        self._editor.setFocus()


class LinkPickerPopup(PopupDialog):
    """«Collega a…»: ricerca per nome fra tutto ciò a cui si può collegare. Il risultato è in `target`."""

    def __init__(self, parent: QWidget, targets: Callable[[str, int], list[LinkTarget]], title: str = "Collega a…",
                 subtitle: str = "Scegli la pagina o l'elemento a cui collegare il testo.", button: str = "Collega"):
        super().__init__(parent, title, subtitle, button, width=540)
        self._targets = targets
        self.target: LinkTarget | None = None

        self._search = QLineEdit()
        self._search.setPlaceholderText("Cerca per nome…")
        self._search.setFixedHeight(40)
        self._search.installEventFilter(self)
        self._list = TargetList()
        self._list.setFixedHeight(_MAX_ROWS * _ROW_HEIGHT)
        self._list.itemSelectionChanged.connect(self._update_primary)
        self._list.chosen.connect(self._choose)
        self.body.setSpacing(10)
        self.body.addWidget(self._search)
        self.body.addWidget(self._list)

        self._search.textChanged.connect(self._refresh)
        self._refresh()
        self._search.setFocus()

    def _refresh(self) -> None:
        self._list.set_targets(self._targets(self._search.text(), 50))
        self._update_primary()

    def _update_primary(self) -> None:
        self.set_primary_enabled(self._list.current_target() is not None)

    def _choose(self, target: LinkTarget) -> None:
        self.target = target
        self.accept()

    def accept(self) -> None:
        self.target = self.target or self._list.current_target()
        if self.target is not None:
            super().accept()

    def eventFilter(self, watched, event: QEvent) -> bool:
        if watched is self._search and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Up, Qt.Key_Down):
            self._list.move_selection(-1 if event.key() == Qt.Key_Up else 1)
            return True
        return super().eventFilter(watched, event)
