"""«Cerca nella pagina»: la barra in alto a destra dell'editor e l'evidenziazione delle occorrenze.

La ricerca guarda il testo senza cambiarlo: le occorrenze si evidenziano con le selezioni temporanee dell'editor
(`RichEditor.set_overlay`, solo quelle in vista) e quella corrente ha in più un contorno (`RichEditor.set_outlines`), quindi
il testo, il cursore e l'«Annulla» restano come sono. Maiuscole e accenti non contano (stessa regola della ricerca globale,
`data/search.py`); si cerca anche nelle celle delle tabelle.
"""

from bisect import bisect_left, bisect_right

from PySide6.QtCore import QObject, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QTextEdit, QToolButton, QWidget

from ... import icons, theme
from ...data.search import fold
from ..widgets.search_field import SearchField

BAR_WIDTH = 368
BAR_MARGIN = 20           # distanza della barra dal bordo destro
BAR_TOP = 12
REFRESH_MS = 150          # pausa dopo l'ultima lettera scritta nella pagina, prima di rifare la ricerca
VIEW_MARGIN = 200         # px sopra e sotto la parte in vista in cui le occorrenze sono già evidenziate
REVEAL_MARGIN = 60        # px: l'occorrenza corrente si porta in vista se è più vicina di così al bordo


# --- Dove sono le occorrenze --------------------------------------------------------------------
def _folded(text: str) -> tuple[str, list[int] | None]:
    """`text` senza maiuscole e accenti e, se la lunghezza cambia («ﬁ» diventa «fi»), da dove viene ogni lettera."""
    folded = fold(text).replace("’", "'")          # l'apostrofo dritto e quello tipografico sono la stessa cosa
    if len(folded) == len(text):
        return folded, None
    pieces, origin = [], []
    for index, char in enumerate(text):
        piece = fold(char).replace("’", "'")
        pieces.append(piece)
        origin.extend([index] * len(piece))
    return "".join(pieces), origin


def find_matches(doc: QTextDocument, query: str) -> list[tuple[int, int]]:
    """Le posizioni (inizio, fine) di `query` nel documento, in ordine; un'occorrenza non attraversa i paragrafi."""
    needle = fold(query).replace("’", "'")
    if not query.strip() or not needle:
        return []
    found, block = [], doc.begin()
    while block.isValid():
        text = block.text()
        if len(text) >= len(needle):
            folded, origin = _folded(text)
            index = folded.find(needle)
            while index >= 0:
                end = index + len(needle)
                start, stop = (index, end) if origin is None else (origin[index], origin[end - 1] + 1)
                found.append((block.position() + start, block.position() + stop))
                index = folded.find(needle, end)
        block = block.next()
    return found


def match_rects(doc: QTextDocument, start: int, end: int) -> list[QRectF]:
    """I rettangoli (uno per riga, in coordinate del documento) occupati dal testo fra `start` e `end`."""
    block = doc.findBlock(start)
    corner = doc.documentLayout().blockBoundingRect(block).topLeft()      # impagina fin qui, se non l'ha già fatto
    layout, rects = block.layout(), []
    first, last = start - block.position(), end - block.position()
    for number in range(layout.lineCount()):
        line = layout.lineAt(number)
        a, b = max(first, line.textStart()), min(last, line.textStart() + line.textLength())
        if a < b:
            left, right = line.cursorToX(a)[0], line.cursorToX(b)[0]
            rects.append(QRectF(corner.x() + left, corner.y() + line.y(), right - left, line.height()))
    return rects


# --- La barra -------------------------------------------------------------------------------------
class FindBar(QFrame):
    """Campo, «1 di N», precedente, successivo e chiudi. Non cerca da solo: segnala ciò che l'utente fa."""

    edited = Signal(str)
    stepped = Signal(int)         # -1 precedente, +1 successivo (anche Invio)
    closed = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("FindBar")
        self.setFixedWidth(BAR_WIDTH)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 128))
        self.setGraphicsEffect(shadow)
        self._count = QLabel()
        self._count.setObjectName("Muted")
        self._count.setFont(theme.ui_font(12))
        self._field = SearchField("FindField", "Cerca nella pagina", self._count)
        self._field.edited.connect(self.edited)
        self._field.submitted.connect(lambda: self.stepped.emit(1))
        self._field.dismissed.connect(self.closed)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(4)
        row.addWidget(self._field, 1)
        row.addWidget(self._button("chevron-up", "Risultato precedente", lambda: self.stepped.emit(-1)))
        row.addWidget(self._button("chevron-down", "Risultato successivo", lambda: self.stepped.emit(1)))
        row.addWidget(self._button("x", "Chiudi la ricerca", self.closed.emit))
        self.hide()

    @staticmethod
    def _button(icon_name: str, tooltip: str, action) -> QToolButton:
        button = QToolButton()
        button.setObjectName("FindButton")
        button.setIcon(icons.icon(icon_name, theme.TEXT_SOFT))
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(30, 30)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.NoFocus)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _=False: action())
        return button

    def text(self) -> str:
        return self._field.text()

    def focus(self) -> None:
        self._field.focus()

    def show_count(self, current: int, total: int) -> None:
        """«1 di 3»; senza risultati «Nessun risultato», e finché il campo è vuoto niente."""
        if not self.text().strip():
            self._count.clear()
        else:
            self._count.setText(f"{current + 1} di {total}" if total else "Nessun risultato")


# --- La ricerca -----------------------------------------------------------------------------------
class FindController(QObject):
    """La ricerca nella pagina di `editor`: apre e chiude la barra, trova le occorrenze e le evidenzia."""

    toggled = Signal(bool)        # la barra si è aperta (True) o chiusa (False)

    def __init__(self, editor: QTextEdit):
        super().__init__(editor)
        self._editor = editor
        self._bar = FindBar(editor)
        self._matches: list[tuple[int, int]] = []
        self._current = 0
        self._anchor = 0                  # la ricerca riparte da qui: la prima occorrenza non prima di questa posizione
        self._plain, self._active = self._format(theme.FIND_MATCH, 0.32), self._format(theme.ACCENT, 0.4)
        self._timer = QTimer(self, singleShot=True, interval=REFRESH_MS)
        self._timer.timeout.connect(lambda: self._search(reveal=False))
        self._bar.edited.connect(lambda _: self._search(reveal=True))
        self._bar.stepped.connect(self._step)
        self._bar.closed.connect(self.close)
        editor.document().contentsChange.connect(self._document_changed)
        editor.verticalScrollBar().valueChanged.connect(self._show_marks)

    @staticmethod
    def _format(color: str, alpha: float) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setBackground(theme.tint(color, alpha))
        return fmt

    @property
    def is_open(self) -> bool:
        return not self._bar.isHidden()

    def toggle(self) -> None:
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self) -> None:
        self._anchor = self._editor.visible_positions()[0]
        self.place()
        self._bar.show()
        self._bar.raise_()
        self._bar.focus()
        self._search(reveal=False)
        self.toggled.emit(True)

    def close(self, refocus: bool = True) -> None:
        """Chiude la barra e toglie le evidenziature; `refocus` riporta il cursore nel testo."""
        was_open = self.is_open
        self._timer.stop()
        self._bar.hide()
        self._matches = []
        self._editor.set_overlay("find", [])
        self._editor.set_outlines([])
        if was_open:
            self.toggled.emit(False)
        if refocus:
            self._editor.setFocus()

    def place(self) -> None:
        """La barra sta in alto a destra del testo (a sinistra della barra di scorrimento)."""
        editor, bar = self._editor, self._bar
        scrollbar = editor.verticalScrollBar()
        right = editor.width() - (scrollbar.width() if scrollbar.isVisible() else 0)
        bar.move(max(0, right - bar.width() - BAR_MARGIN), BAR_TOP)

    # --- Occorrenze -------------------------------------------------------------------------------
    def _document_changed(self, *_) -> None:
        if self.is_open:
            self._timer.start()

    def _search(self, reveal: bool) -> None:
        """Rifà la ricerca; la corrente è la prima occorrenza da `_anchor` in poi (o la prima in assoluto)."""
        self._matches = find_matches(self._editor.document(), self._bar.text())
        self._current = bisect_left([start for start, _ in self._matches], self._anchor) % len(self._matches) if self._matches else 0
        self._show(reveal)

    def _step(self, direction: int) -> None:
        if self._matches:
            self._current = (self._current + direction) % len(self._matches)
            self._anchor = self._matches[self._current][0]
            self._show(reveal=True)

    def _show(self, reveal: bool) -> None:
        self._bar.show_count(self._current, len(self._matches))
        rects = match_rects(self._editor.document(), *self._matches[self._current]) if self._matches else []
        self._editor.set_outlines(rects)
        if reveal and rects:
            self._reveal(rects[0])
        self._show_marks()

    def _reveal(self, rect: QRectF) -> None:
        """Porta in vista l'occorrenza corrente (se già si vede, non si scorre)."""
        scrollbar, height = self._editor.verticalScrollBar(), self._editor.viewport().height()
        if rect.top() < scrollbar.value() + REVEAL_MARGIN or rect.bottom() > scrollbar.value() + height - REVEAL_MARGIN:
            scrollbar.setValue(round(rect.center().y() - height / 2))

    def _show_marks(self, *_) -> None:
        """Evidenzia le occorrenze in vista (con un po' di margine): sono tante solo se si cerca una lettera."""
        if not self.is_open:
            return
        editor = self._editor
        first, last = editor.visible_positions(VIEW_MARGIN)
        starts = [start for start, _ in self._matches]
        marks = []
        for index in range(bisect_left(starts, first), bisect_right(starts, last)):
            cursor = QTextCursor(editor.document())
            cursor.setPosition(self._matches[index][0])
            cursor.setPosition(self._matches[index][1], QTextCursor.KeepAnchor)
            mark = QTextEdit.ExtraSelection()
            mark.cursor = cursor
            mark.format = self._active if index == self._current else self._plain
            marks.append(mark)
        editor.set_overlay("find", marks)
