"""Il controllo ortografico nell'editor: le onde rosse sotto le parole sbagliate e la parola su cui si apre il menu.

Le onde sono selezioni temporanee dell'editor (`RichEditor.set_overlay`): non toccano il testo, quindi non finiscono nel
salvataggio né nell'«Annulla». Si controlla solo la parte di testo in vista (con un po' di margine) e si rifà ogni volta
che ci si ferma dopo aver scritto o scorso. Le regole su quali parole vanno bene sono in `spelling.py`.
"""

import threading

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QColor, QTextBlock, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from ... import spelling, theme
from . import styles

REFRESH_MS = 150          # pausa, dopo l'ultima lettera scritta o scorrimento, prima di ricontrollare
VIEW_MARGIN = 400         # px sopra e sotto la parte in vista che si controllano già (così scorrendo le onde ci sono)
_HIT_TOLERANCE = 6        # px: quanto fuori dalla riga di una parola si può ancora cliccare


class DictionaryLoader(QObject):
    """Carica il dizionario una volta sola, in un altro thread (circa 1 s), e avvisa quando ha finito (o non l'ha trovato)."""

    ready = Signal()
    _instance: "DictionaryLoader | None" = None

    @classmethod
    def instance(cls) -> "DictionaryLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._started = False

    def start(self) -> None:
        if self._started or spelling.is_loaded() or spelling.is_missing():
            return
        self._started = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        spelling.load_dictionary()
        self.ready.emit()


def _wave() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
    fmt.setUnderlineColor(QColor(theme.SPELL_ERROR))
    return fmt


class SpellChecker(QObject):
    """Sottolinea con un'onda rossa le parole sbagliate del testo in vista di `editor`. Si può spegnere (`set_enabled`)."""

    changed = Signal()            # acceso o spento, o il dizionario è pronto (o manca): la barra si aggiorna

    def __init__(self, editor: QTextEdit, speller: spelling.Speller):
        super().__init__(editor)
        self._editor, self._speller = editor, speller
        self._enabled = True
        self._wave = _wave()
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self.refresh)
        editor.document().contentsChange.connect(self.schedule)
        editor.verticalScrollBar().valueChanged.connect(self.schedule)
        editor.cursorPositionChanged.connect(self.schedule)
        loader = DictionaryLoader.instance()
        loader.ready.connect(self._loaded)
        loader.start()

    # --- Stato ----------------------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def available(self) -> bool:
        """Il dizionario c'è (o si sta ancora caricando)? Se manca la libreria o i file il controllo non si può accendere."""
        return not spelling.is_missing()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.schedule(delay=0)
        self.changed.emit()

    def _loaded(self) -> None:
        self.schedule(delay=0)
        self.changed.emit()

    # --- Onde -----------------------------------------------------------------------------------
    def schedule(self, *_, delay: int = REFRESH_MS) -> None:
        """Ricontrolla fra poco (di nuovo da capo a ogni chiamata: scrivendo di continuo non si controlla mai)."""
        self._timer.start(delay)

    def refresh(self) -> None:
        marks = []
        if self._enabled and self._speller.ready:
            editor, doc = self._editor, self._editor.document()
            caret = editor.textCursor()
            typing = caret.position() if editor.hasFocus() and not caret.hasSelection() else -1
            first, last = editor.visible_positions(VIEW_MARGIN)
            block = doc.findBlock(first)
            while block.isValid() and block.position() <= last:
                for start, end in self._block_errors(block):
                    if not start <= typing - block.position() <= end:        # la parola che si sta scrivendo non si sottolinea
                        marks.append(self._mark(block.position() + start, block.position() + end))
                block = block.next()
        self._editor.set_overlay("spell", marks)

    def _block_errors(self, block: QTextBlock) -> list[tuple[int, int]]:
        """Le parole sbagliate del paragrafo, come (inizio, fine) nel suo testo."""
        text = block.text()
        if len(text) < 2:
            return []
        links = [(start - block.position(), end - block.position()) for start, end, fmt in styles.fragments(block) if fmt.isAnchor()]
        return self._speller.errors(text, links)

    def _mark(self, start: int, end: int) -> QTextEdit.ExtraSelection:
        cursor = QTextCursor(self._editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        mark = QTextEdit.ExtraSelection()
        mark.cursor = cursor
        mark.format = self._wave
        return mark

    # --- Menu -----------------------------------------------------------------------------------
    def error_at(self, point: QPoint) -> str | None:
        """La parola sbagliata sotto il punto (coordinate dell'area di testo), o None. Vale anche per quella che si sta scrivendo."""
        if not (self._enabled and self._speller.ready):
            return None
        cursor = self._editor.cursorForPosition(point)
        block, offset = cursor.block(), cursor.position() - cursor.block().position()
        for start, end in self._block_errors(block):
            if start <= offset <= end and self._covers(point, block, start, end):
                return block.text()[start:end]
        return None

    def _covers(self, point: QPoint, block: QTextBlock, start: int, end: int) -> bool:
        """Il punto è proprio sulla parola (e non solo vicino, sulla stessa riga)?"""
        rects = []
        for offset in (start, end):
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + offset)
            rects.append(self._editor.cursorRect(cursor))
        first, last = rects
        if first.top() != last.top():            # la parola va a capo: basta che sia la sua riga
            return True
        return (first.left() - _HIT_TOLERANCE <= point.x() <= last.left() + _HIT_TOLERANCE
                and first.top() - _HIT_TOLERANCE <= point.y() <= first.bottom() + _HIT_TOLERANCE)

    def ignore(self, word: str) -> None:
        self._speller.ignore(word)
        self.schedule(delay=0)
