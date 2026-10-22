"""L'editor di testo: una QTextEdit che conosce titoli, elenchi, box, tabelle, link, menzioni «@» e immagini.

Qui c'è il comportamento dell'editor (tasti, mouse, copia e incolla, disegno dei box e delle tabelle). I comandi
di formattazione sono in `commands.py`, le regole di coerenza del testo in `normalize.py`, il formato di
salvataggio in `markup.py`, l'aspetto in `styles.py`, barra e «+» delle tabelle in `table_ui.py`.
"""

import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRect, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor, QImage, QImageReader, QKeySequence, QPainter, QPainterPath, QPen, QShortcut, QTextCursor, QTextDocument,
    QTextDocumentFragment, QTextImageFormat, QTextTable,
)
from PySide6.QtWidgets import QMessageBox, QTextEdit, QWidget

from ... import icons, theme
from ...data import links
from ...data.image_refs import safe_media_path
from ...data.models import LinkTarget
from ...data.repository import IMAGE_SUFFIXES
from ...spelling import Speller
from ..widgets.menu import PopupMenu
from ..widgets.segment_switch import SegmentSwitch
from . import commands, markup, normalize, styles
from .styles import Flags
from .encounter_box import EncounterCard, EncounterSource, card_height, render_card
from .find_ui import FindController
from .link_ui import CreateTarget, LinkPickerPopup, LinkSource, MentionController, resolve_target
from .preview_ui import LinkPreviewController, PreviewSource
from .spell_ui import SpellChecker
from .table_ui import TableControls, TableGrid, table_grid

MIME = "application/x-gmjournal-text"        # il testo copiato dall'editor, con la sua formattazione
HEADER_GAP = 10            # spazio fra l'intestazione e il testo
IMAGE_WIDTHS = (300, 500, 700)   # le dimensioni fra cui si sceglie
IMAGE_DEFAULT_WIDTH = 500        # larghezza massima di un'immagine appena inserita
IMAGE_MAX_PIXELS = 1600    # le immagini più larghe si caricano ridotte (meno memoria)
_NUMBERED = re.compile(r"\d+\.")


@dataclass(frozen=True)
class Frame:
    """Le misure dell'area di testo: larghezza della colonna (None = tutta), spazio ai lati, sopra e sotto."""
    text_width: int | None
    side: int
    top: int
    bottom: int
    floating_list: bool = False    # l'elenco «@» si apre sulla finestra, non dentro l'editor (che qui è piccolo)


PAGE_FRAME = Frame(text_width=760, side=32, top=36, bottom=160)    # una pagina di Scrittura: colonna centrata
COMPACT_FRAME = Frame(text_width=None, side=28, top=22, bottom=20, floating_list=True)  # un riquadro dentro una scheda


class RichEditor(QTextEdit):
    """L'editor. Il testo si legge e si scrive con `content()` e `set_content()`.

    Chi lo usa fornisce, se servono: `link_targets` (cosa si può collegare), `create_target` (crea l'elemento
    scelto con una riga «Crea…» dell'elenco), `import_image` (copia un file immagine nella campagna e dà il
    percorso relativo, per le immagini incollate o trascinate), `pick_images` (fa scegliere le immagini da inserire: restituisce
    i loro percorsi), `media_dir` (la cartella della campagna) e `speller` (il controllo ortografico: senza, non c'è).
    `frame` decide le misure dell'area di testo; `searchable` aggiunge «Cerca nella pagina» (`find`); `link_preview` dà ciò che mostra
    la finestrella sul collegamento su cui si ferma il mouse (senza, resta il suggerimento «Ctrl + clic per aprire»);
    `encounters` permette di inserire il box «Incontro» (senza, nel testo non ci sono incontri); un clic sul box lo apre (`link_activated`).
    """

    edited = Signal()                  # il testo è cambiato (anche solo la formattazione)
    state_changed = Signal()           # cursore o formato sono diversi: la barra si aggiorna
    link_activated = Signal(str, int)  # Ctrl+clic su un collegamento: (tipo, ID)
    focus_lost = Signal()

    def __init__(self, link_targets: LinkSource | None = None, create_target: CreateTarget | None = None,
                 import_image: Callable[[Path], str] | None = None, media_dir: Path | None = None,
                 frame: Frame = PAGE_FRAME, pick_images: Callable[[QWidget], list[str]] | None = None,
                 speller: Speller | None = None, searchable: bool = False, link_preview: PreviewSource | None = None,
                 encounters: EncounterSource | None = None):
        super().__init__()
        self._frame = frame
        self._link_targets = link_targets
        self._create_target = create_target
        self._import_image = import_image
        self._pick_images = pick_images
        self._encounters = encounters
        self._pressed_encounter: int | None = None     # il box Incontro su cui si è premuto il mouse (si apre al rilascio)
        self._cards: dict[int, EncounterCard | None] = {}     # le schede degli incontri già lette (si rileggono a ogni nuovo testo)
        self._card_heights: dict[int, int] = {}               # l'altezza con cui ogni scheda è disegnata nel documento
        self._media_dir = media_dir
        self._images: dict[str, QImage] = {}
        self._header: QWidget | None = None
        self._side = -1
        self._boxes: list[tuple[float, float, str]] | None = None   # (alto, basso, tipo) dei box, in coordinate del testo
        self._loading = False         # si sta caricando un testo: nessuna reazione
        self._busy = False            # stiamo già sistemando il testo
        self._in_history = False      # annulla/ripeti in corso: il testo è già coerente
        self._overlays: dict[str, list[QTextEdit.ExtraSelection]] = {}     # cosa è disegnato sopra il testo senza toccarlo
        self._outlines: list[QRectF] = []       # contorni disegnati sopra il testo (coordinate del documento)

        self.setObjectName("RichEditor")
        self.setFrameShape(QTextEdit.NoFrame)
        self.setAcceptRichText(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCursorWidth(2)
        self.viewport().setMouseTracking(True)
        self._mention = MentionController(self, self.window if frame.floating_list else self.viewport,
                                          link_targets, create_target, self._insert_mention)
        self._image_bar = SegmentSwitch([(width, str(width), 12) for width in IMAGE_WIDTHS], self._resize_image,
                                        segment_width=46, outlined=True)
        self._image_bar.setParent(self.viewport())
        self._image_bar.hide()
        self._table_controls = TableControls(self)
        self.spell = SpellChecker(self, speller) if speller is not None else None
        self.find = FindController(self) if searchable else None
        self._preview = LinkPreviewController(self, link_preview) if link_preview is not None else None

        doc = self.document()
        doc.contentsChange.connect(self._on_contents_change)
        doc.documentLayout().documentSizeChanged.connect(self._invalidate_boxes)
        self.cursorPositionChanged.connect(self._on_cursor_moved)
        self.currentCharFormatChanged.connect(lambda _: self.state_changed.emit())
        self.selectionChanged.connect(self.state_changed)
        self.state_changed.connect(self._place_image_bar)
        self.state_changed.connect(self._place_table_controls)
        doc.documentLayout().documentSizeChanged.connect(self._place_table_controls)
        self.verticalScrollBar().valueChanged.connect(self._place_header)
        self.verticalScrollBar().valueChanged.connect(self._place_image_bar)
        self.verticalScrollBar().valueChanged.connect(self._place_table_controls)
        self._add_shortcuts()
        self.set_content("")

    # --- Contenuto ---------------------------------------------------------------------
    def set_content(self, content: str, keep_view: bool = False) -> None:
        """Sostituisce tutto il testo; non si può annullare e non conta come modifica.

        Con `keep_view` cursore e scorrimento restano dove sono (per un testo cambiato da fuori, non per una pagina nuova).
        """
        position, scroll = self.textCursor().position(), self.verticalScrollBar().value()
        self._mention.close()
        self._hide_preview()
        if self.find is not None and not keep_view:
            self.find.close(refocus=False)          # un'altra pagina: la ricerca finisce
        self._images.clear()
        self._cards.clear()
        self._loading = True
        try:
            markup.fill_document(self.document(), content)
            self._apply_frame_margins()
            self._refresh_cards()
        finally:
            self._loading = False
        self._invalidate_boxes()
        cursor = QTextCursor(self.document())
        if keep_view:
            cursor.setPosition(min(position, self.document().characterCount() - 1))
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(scroll if keep_view else 0)
        self.document().setModified(False)
        self.state_changed.emit()
        if self.spell is not None:
            self.spell.schedule(delay=0)

    def content(self) -> str:
        return markup.export_html(self.document())

    def set_header(self, widget: QWidget) -> None:
        """Un'intestazione (il titolo della pagina) che scorre insieme al testo. Deve avere altezza fissa."""
        self._header = widget
        widget.setParent(self.viewport())
        widget.show()
        self._apply_frame_margins()
        self._place_header()

    def focus_start(self) -> None:
        """Porta il cursore all'inizio del testo, pronto a scrivere."""
        self.setTextCursor(QTextCursor(self.document()))
        self.setFocus()

    # --- Disegni sopra il testo -----------------------------------------------------------------
    def set_overlay(self, name: str, marks: list[QTextEdit.ExtraSelection]) -> None:
        """Mostra `marks` (onde, evidenziature) sopra il testo: il testo e l'«Annulla» non cambiano. Ogni `name` ha le sue."""
        self._overlays[name] = marks
        self.setExtraSelections([mark for group in self._overlays.values() for mark in group])

    def set_outlines(self, rects: list[QRectF]) -> None:
        """Disegna un contorno attorno a ciascun rettangolo (coordinate del documento), sopra il testo."""
        self._outlines = rects
        self.viewport().update()

    def visible_positions(self, margin: int = 0) -> tuple[int, int]:
        """Prima e ultima posizione del testo che si vede, più `margin` px sopra e sotto."""
        view = self.viewport().rect()
        return (self.cursorForPosition(QPoint(0, view.top() - margin)).position(),
                self.cursorForPosition(QPoint(view.right(), view.bottom() + margin)).position())

    def _apply_frame_margins(self) -> None:
        """Lascia in cima lo spazio per l'intestazione e in fondo quello per scrivere comodi."""
        top = self._frame.top + (self._header.minimumHeight() + HEADER_GAP if self._header else 0)
        doc, frame = self.document(), self.document().rootFrame()
        fmt = frame.frameFormat()
        if (fmt.topMargin(), fmt.bottomMargin()) != (top, self._frame.bottom):
            fmt.setTopMargin(top)
            fmt.setBottomMargin(self._frame.bottom)
            doc.setUndoRedoEnabled(False)       # non è una modifica dell'utente: niente «Annulla» per questo
            frame.setFrameFormat(fmt)
            doc.setUndoRedoEnabled(True)

    # --- Modifiche del testo -------------------------------------------------------------
    def _on_contents_change(self, position: int, removed: int, added: int) -> None:
        if self._loading or self._busy:
            return
        if not self._in_history:
            self._busy = True
            try:
                cursor = QTextCursor(self.document())
                cursor.joinPreviousEditBlock()      # le correzioni fanno parte dello stesso «Annulla»
                normalize.normalize(self.document(), position, position + added)
                cursor.endEditBlock()
            finally:
                self._busy = False
        self._invalidate_boxes()
        self.edited.emit()

    def _add_shortcuts(self) -> None:
        for keys, action in (
            ("Ctrl+B", lambda: commands.toggle_style(self, "bold")),
            ("Ctrl+I", lambda: commands.toggle_style(self, "italic")),
            ("Ctrl+U", lambda: commands.toggle_style(self, "underline")),
            ("Ctrl+L", self.choose_link),    # Ctrl+K è la ricerca globale della finestra
            ("Ctrl+Shift+0", lambda: commands.set_heading(self, 0)),
            ("Ctrl+Shift+1", lambda: commands.set_heading(self, 1)),
            ("Ctrl+Shift+2", lambda: commands.set_heading(self, 2)),
            ("Ctrl+Shift+3", lambda: commands.set_heading(self, 3)),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.WidgetShortcut)
            shortcut.activated.connect(action)

    # --- Tastiera -----------------------------------------------------------------------
    @contextmanager
    def _one_step(self):
        """Tutto ciò che avviene qui dentro (e le correzioni automatiche che ne derivano) è un solo «Annulla»."""
        guard, scroll = self.textCursor(), self.verticalScrollBar().value()
        guard.beginEditBlock()
        try:
            yield
        finally:
            guard.endEditBlock()
            # Dentro il blocco il testo non è ancora impaginato: Qt porta la vista in cima. Si rimette dov'era e si
            # scorre soltanto se il cursore è uscito dall'area visibile (così Invio a metà schermo non sposta nulla).
            self.verticalScrollBar().setValue(scroll)
            self.ensureCursorVisible()

    def _is_structural(self, event) -> bool:
        """Il tasto cambia la struttura (unisce o divide paragrafi)? Scrivere lettere no: così Qt continua a
        raggruppare le lettere di una parola in un solo «Annulla»."""
        cursor, key = self.textCursor(), event.key()
        if cursor.hasSelection():
            doc = self.document()
            return doc.findBlock(cursor.selectionStart()) != doc.findBlock(cursor.selectionEnd()) or event.matches(QKeySequence.Cut)
        block = cursor.block()
        return (key in (Qt.Key_Return, Qt.Key_Enter)
                or (key == Qt.Key_Backspace and cursor.position() == block.position())
                or (key == Qt.Key_Delete and cursor.position() == block.position() + block.length() - 1))

    def _hide_preview(self) -> None:
        if self._preview is not None:
            self._preview.hide()

    def keyPressEvent(self, event) -> None:
        self._hide_preview()
        if self._mention.active and self._mention.handle_key(event):
            return
        key, modifiers = event.key(), event.modifiers()
        if event.matches(QKeySequence.Undo) or event.matches(QKeySequence.Redo):
            self._history(lambda: super(RichEditor, self).keyPressEvent(event))
        elif key in (Qt.Key_Tab, Qt.Key_Backtab):
            step = -1 if key == Qt.Key_Backtab or modifiers & Qt.ShiftModifier else 1
            if self.textCursor().currentTable() is not None:
                with self._one_step():
                    commands.move_to_cell(self, step)              # dopo l'ultima cella aggiunge una riga
            elif self.textCursor().block().textList() is not None:
                commands.change_indent(self, step)
        elif key in (Qt.Key_Return, Qt.Key_Enter) and self.textCursor().currentTable() is not None:
            self.textCursor().insertText(markup.LINE_BREAK)         # in una cella Invio va a capo nella stessa cella
            self.ensureCursorVisible()
        elif key in (Qt.Key_Return, Qt.Key_Enter) and not modifiers & Qt.ShiftModifier:
            with self._one_step():
                self._press_enter(event)
        elif event.text() == " " and not modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier) \
                and self._autoformat():
            return
        elif self._is_structural(event):
            with self._one_step():
                super().keyPressEvent(event)
        else:
            if event.text().isprintable():
                self._keep_typing_outside_link()
            super().keyPressEvent(event)
            if event.text() == "@":
                self._mention.typed_at_sign()

    def _press_enter(self, event) -> None:
        block = self.textCursor().block()
        box, tlist = styles.box_of(block), block.textList()
        empty = block.length() <= 1 and not self.textCursor().hasSelection()
        if empty and tlist is not None and tlist.format().indent() > 1:
            commands.change_indent(self, -1)             # voce vuota in un sotto-elenco: torna al livello sopra
        elif empty and tlist is None and box[0] and styles.box_of(block.next()) != box:
            commands.leave_box(self)                      # riga vuota in fondo a un box: si esce dal box
        else:
            context, heading = styles.block_flags(block)
            flags = styles.flags_of(self.currentCharFormat(), context, heading)
            if empty and tlist is None and not heading:
                # Su un paragrafo vuoto Qt si limita ad azzerarne il formato (serve a chiudere un elenco): qui
                # impedirebbe di aggiungere più di una riga vuota, quindi si va a capo noi.
                cursor = self.textCursor()
                cursor.insertBlock(cursor.blockFormat(), cursor.charFormat())
                self.setTextCursor(cursor)
            else:
                super().keyPressEvent(event)
            cursor = self.textCursor()
            if cursor.block() != block and cursor.block().length() <= 1:
                # Il paragrafo nuovo è vuoto: si continua a scrivere come prima (grassetto, corsivo, dimensione);
                # dopo un titolo si riparte con il testo normale, e un link non prosegue.
                flags = Flags() if heading else replace(flags, href="", bold=flags.bold and not flags.href)
                new_context, new_heading = styles.block_flags(cursor.block())
                fmt = styles.char_format(new_context, new_heading, flags)
                cursor.setBlockCharFormat(fmt)
                self.setTextCursor(cursor)
                self.setCurrentCharFormat(fmt)

    def _autoformat(self) -> bool:
        """«- », «* », «1. » o «#» + spazio all'inizio di un paragrafo lo trasformano in elenco o titolo."""
        cursor = self.textCursor()
        block = cursor.block()
        if cursor.hasSelection() or block.textList() is not None or styles.heading_of(block) or cursor.currentTable() is not None:
            return False
        typed = block.text()[:cursor.position() - block.position()]
        if typed in ("-", "*"):
            action = lambda: commands.toggle_list(self, "ul")                       # noqa: E731
        elif _NUMBERED.fullmatch(typed):
            action = lambda: commands.toggle_list(self, "ol")                       # noqa: E731
        elif typed in ("#", "##", "###") and not styles.box_of(block)[0]:
            action = lambda: commands.set_heading(self, len(typed))                 # noqa: E731
        else:
            return False
        cursor.beginEditBlock()
        marker = QTextCursor(block)
        marker.setPosition(block.position() + len(typed), QTextCursor.KeepAnchor)
        marker.removeSelectedText()
        action()
        cursor.endEditBlock()
        return True

    def _insert_mention(self, target: LinkTarget, start: int, end: int) -> None:
        commands.insert_link(self, links.make_href(target.kind, target.id), target.name, (start, end))

    # --- Cursore e link ---------------------------------------------------------------------
    def _on_cursor_moved(self) -> None:
        if self._loading:
            return
        self._keep_typing_outside_link()
        self._mention.refresh()
        self.state_changed.emit()

    def _keep_typing_outside_link(self) -> None:
        """Quello che si scrive subito prima o dopo un link non ne fa parte: solo dentro il link lo allunga."""
        cursor = self.textCursor()
        fmt = self.currentCharFormat()
        if cursor.hasSelection() or not fmt.isAnchor():
            return
        block = cursor.block()
        inside = False
        if cursor.position() > block.position():
            found = commands.link_range(self.document(), cursor.position() - 1)
            inside = found is not None and found[0] < cursor.position() < found[1]
        if not inside:
            context, heading = styles.block_flags(block)
            flags = replace(styles.flags_of(fmt, context, heading), href="", bold=False, underline=False)
            self.setCurrentCharFormat(styles.char_format(context, heading, flags))

    def choose_link(self) -> None:
        """Apre «Collega a…» e collega alla scelta il testo selezionato (o il link su cui si è, o lo scrive)."""
        if self._link_targets is None:
            return
        popup = LinkPickerPopup(self, self._link_targets)
        target = resolve_target(popup.target, self._create_target) if popup.exec() and popup.target is not None else None
        if target is not None:
            commands.insert_link(self, links.make_href(target.kind, target.id), target.name)
        self.setFocus()

    def link_under(self, point: QPoint) -> tuple[int, int, str] | None:
        """(inizio, fine, destinazione) del link sotto il punto (coordinate dell'area di testo)."""
        href = self.anchorAt(point)
        if not href:
            return None
        hit = self.document().documentLayout().hitTest(QPointF(point.x(), point.y() + self.verticalScrollBar().value()), Qt.ExactHit)
        for position in (hit, hit - 1):      # il punto può cadere nella metà destra dell'ultima lettera
            found = commands.link_range(self.document(), position) if position >= 0 else None
            if found is not None and found[2] == href:
                return found
        return None

    def _open_link(self, href: str) -> None:
        target = links.parse_href(href)
        if target is not None:
            self.link_activated.emit(*target)

    def mouseMoveEvent(self, event) -> None:
        point = event.position().toPoint()
        href = self.anchorAt(point)
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        over_card = not event.buttons() and self._encounter_at(point) is not None
        self.viewport().setCursor(Qt.PointingHandCursor if (href and ctrl) or over_card else Qt.IBeamCursor)
        if self._preview is not None:
            self._preview.moved(point, "" if event.buttons() else href)     # tasto premuto = si seleziona: niente anteprima
        else:
            self.viewport().setToolTip("Ctrl + clic per aprire" if href else "")
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._hide_preview()
        self._pressed_encounter = None
        if event.button() == Qt.LeftButton and event.modifiers() == Qt.NoModifier:
            found = self._encounter_at(event.position().toPoint())
            if found is not None:
                self._pressed_encounter = found        # non si sposta il cursore: l'incontro si apre al rilascio
                return
        found = self._image_at(event.position().toPoint())
        if found is not None and event.button() == Qt.LeftButton and event.modifiers() == Qt.NoModifier:
            self._select_image(found[0])       # un clic su un'immagine la seleziona (compare la barra delle dimensioni)
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        pressed, self._pressed_encounter = self._pressed_encounter, None
        if pressed is not None:
            if self._encounter_at(event.position().toPoint()) == pressed and self._card(pressed) is not None:
                self.link_activated.emit(links.ENCOUNTER, pressed)
            return
        href = self.anchorAt(event.position().toPoint())
        if href and event.button() == Qt.LeftButton and event.modifiers() & Qt.ControlModifier:
            self._open_link(href)
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        point = self.viewport().mapFromGlobal(event.globalPos())
        found = self.link_under(point)
        image = self._image_at(point)
        if image is not None:
            self._select_image(image[0])
        encounter = self._encounter_at(point)
        cursor = self.textCursor()
        menu = PopupMenu(self)
        misspelled = self.spell.error_at(point) if self.spell is not None else None
        if misspelled is not None:
            menu.add_item("x", "Ignora questa volta", lambda: self.spell.ignore(misspelled))
            menu.add_separator()
        if image is not None:
            current = image[1].width()
            for width, name in zip(IMAGE_WIDTHS, ("Piccola", "Media", "Grande")):
                menu.add_item("image", f"{name} · {width} px", lambda width=width: self._resize_image(width), checked=current == width)
            menu.add_separator()
        if encounter is not None:
            if self._card(encounter) is not None:
                menu.add_item("external-link", "Apri l'incontro", lambda: self.link_activated.emit(links.ENCOUNTER, encounter))
            menu.add_item("trash", "Togli il box dal testo", lambda: commands.remove_encounter(self, encounter))
            menu.add_separator()
        if found is not None:
            menu.add_item("external-link", "Apri il collegamento", lambda: self._open_link(found[2]))
            menu.add_item("unlink", "Togli il collegamento", lambda: commands.remove_link(self, found[0], found[1]))
            menu.add_separator()
        doc = self.document()
        if doc.isUndoAvailable():
            menu.add_item("undo", "Annulla", lambda: self._history(self.undo))
        if doc.isRedoAvailable():
            menu.add_item("redo", "Ripeti", lambda: self._history(self.redo))
        if cursor.hasSelection():
            menu.add_item("scissors", "Taglia", self.cut)
            menu.add_item("copy", "Copia", self.copy)
        if self.canPaste():
            menu.add_item("clipboard", "Incolla", self.paste)
        menu.add_item("select-all", "Seleziona tutto", self.selectAll)
        menu.popup_at(event.globalPos(), align="left")

    def _history(self, action: Callable[[], None]) -> None:
        self._in_history = True
        try:
            action()
        finally:
            self._in_history = False

    # --- Copia e incolla, trascinamento -----------------------------------------------------
    def createMimeDataFromSelection(self) -> QMimeData:
        selection = self.textCursor().selection()
        data = QMimeData()
        data.setText(selection.toPlainText().replace(markup.LINE_BREAK, "\n"))
        scratch = QTextDocument()
        markup.fill_document(scratch, "")
        QTextCursor(scratch).insertFragment(selection)
        data.setData(MIME, markup.export_html(scratch).encode("utf-8"))
        return data

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        return (source.hasFormat(MIME) or source.hasText() or bool(self._image_files(source))
                or (source.hasImage() and self._import_image is not None))

    def insertFromMimeData(self, source: QMimeData) -> None:
        with self._one_step():
            self._insert_from_mime(source)
        self._refresh_cards()

    def dropEvent(self, event) -> None:
        with self._one_step():
            super().dropEvent(event)

    def _insert_from_mime(self, source: QMimeData) -> None:
        in_table = self.textCursor().currentTable() is not None
        if source.hasFormat(MIME):
            scratch = QTextDocument()
            markup.fill_document(scratch, bytes(source.data(MIME)).decode("utf-8"), commands.next_box_id(self.document()))
            if in_table:
                self._insert_inline(scratch)
            else:
                cursor = self.textCursor()
                cursor.insertFragment(QTextDocumentFragment(scratch))
                self.setTextCursor(cursor)
        elif in_table:              # in una cella si incolla solo testo, e gli «a capo» restano nella cella
            if source.hasText():
                self.insertPlainText(source.text().replace("\r\n", "\n").replace("\r", "\n").replace("\n", markup.LINE_BREAK))
        elif files := self._image_files(source):
            for path in files:
                self.insert_image_file(path)
        elif source.hasImage() and self._import_image is not None:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "immagine.png"
                image = source.imageData()
                image = image.toImage() if hasattr(image, "toImage") else image
                if image.save(str(path)):
                    self.insert_image_file(path)
        elif source.hasText():
            self.insertPlainText(source.text().replace("\r\n", "\n").replace("\r", "\n"))

    def _insert_inline(self, scratch: QTextDocument) -> None:
        """Incolla in una cella il testo di `scratch` con la sua formattazione «in riga»: i paragrafi (anche quelli
        di una tabella copiata) diventano righe della cella; titoli, elenchi, box e immagini si perdono."""
        cursor = self.textCursor()
        cursor.removeSelectedText()
        context = styles.context_of(cursor.block())
        block, first = scratch.firstBlock(), True
        while block.isValid():
            if block.length() > 1:
                if not first:
                    cursor.insertText(markup.LINE_BREAK, styles.char_format(context))
                first = False
                for start, end, fmt in styles.fragments(block):
                    text = block.text()[start - block.position():end - block.position()]
                    cursor.insertText(text, styles.char_format(context, 0, styles.flags_of(fmt, *styles.block_flags(block))))
            block = block.next()
        self.setTextCursor(cursor)

    def _image_files(self, source: QMimeData) -> list[Path]:
        if self._import_image is None:
            return []
        paths = [Path(url.toLocalFile()) for url in source.urls() if url.isLocalFile()]
        return [path for path in paths if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file()]

    # --- Incontri ---------------------------------------------------------------------------
    @property
    def has_encounters(self) -> bool:
        return self._encounters is not None

    def choose_encounter(self) -> None:
        """Fa scegliere un incontro e ne inserisce il box nel testo."""
        if self._encounters is None:
            return
        popup = LinkPickerPopup(self, self._encounters.targets, "Inserisci un incontro", "Scegli l'incontro da mostrare nel testo.", "Inserisci")
        if popup.exec() and popup.target is not None:
            commands.insert_encounter(self, popup.target.id)
            self._refresh_cards()
        self.setFocus()

    def _card(self, encounter_id: int) -> EncounterCard | None:
        """La scheda dell'incontro (None se non esiste più)."""
        if encounter_id not in self._cards:
            self._cards[encounter_id] = self._encounters.card(encounter_id)
        return self._cards[encounter_id]

    def _text_width(self) -> int:
        width = self.document().pageSize().width()
        return round(width) if width > 0 else self.viewport().width()

    def _refresh_cards(self) -> None:
        """Disegna di nuovo le schede degli incontri nel testo, larghe come la colonna: chiamata a ogni nuovo testo, incolla e
        cambio di larghezza. Il documento le prende come immagini; ridisegna solo se l'altezza è cambiata."""
        if self._encounters is None:
            return
        doc, width, ratio = self.document(), self._text_width(), self.devicePixelRatioF()
        block = doc.firstBlock()
        while block.isValid():
            found = styles.encounter_in(block)
            if found is not None:
                card = self._card(found)
                doc.addResource(QTextDocument.ImageResource, QUrl(f"{styles.ENCOUNTER_SCHEME}{found}"), render_card(card, width, ratio))
                if self._card_heights.get(found) != card_height(card):
                    self._card_heights[found] = card_height(card)
                    doc.markContentsDirty(block.position(), 1)       # l'altezza è cambiata: il testo si impagina di nuovo
            block = block.next()
        self.viewport().update()

    def _encounter_at(self, point: QPoint) -> int | None:
        """L'ID dell'incontro il cui box è sotto il punto (coordinate dell'area di testo)."""
        if self._encounters is None:
            return None
        block = self.cursorForPosition(point).block()
        found = styles.encounter_in(block)
        if found is None:
            return None
        top = self.cursorRect(QTextCursor(block)).top()
        return found if top <= point.y() < top + card_height(self._card(found)) else None

    # --- Immagini ---------------------------------------------------------------------------
    def choose_image(self) -> None:
        """Fa scegliere le immagini dalla libreria della campagna e le inserisce nel testo."""
        if self._pick_images is None:
            return
        for name in self._pick_images(self):
            self.insert_library_image(name)
        self.setFocus()

    def insert_image_file(self, path: Path) -> None:
        """Copia l'immagine nella campagna e la inserisce nel testo."""
        if not QImageReader(str(path)).canRead():
            QMessageBox.warning(self.window(), "Immagine non inserita", "Il file scelto non è un'immagine che riesco a leggere.")
            return
        try:
            name = self._import_image(path)
        except OSError as error:
            QMessageBox.warning(self.window(), "Immagine non inserita", f"Non riesco a copiare l'immagine nella campagna.\n\n{error}")
            return
        self.insert_library_image(name)

    def insert_library_image(self, name: str) -> None:
        """Inserisce nel testo un'immagine già nella campagna (`name` è il suo percorso relativo)."""
        image = self._load_image(name)
        width = min(image.width(), IMAGE_DEFAULT_WIDTH)
        commands.insert_image(self, name, width, round(image.height() * width / image.width()))

    def _image_at(self, point: QPoint) -> tuple[int, QTextImageFormat] | None:
        """(posizione, formato) dell'immagine sotto il punto (coordinate dell'area di testo)."""
        hit = self.document().documentLayout().hitTest(QPointF(point.x(), point.y() + self.verticalScrollBar().value()), Qt.FuzzyHit)
        for position in (hit, hit - 1):       # il punto può cadere dopo l'immagine, nella stessa riga
            if position >= 0 and self.document().characterAt(position) == styles.IMAGE_CHAR:
                fmt = self._image_format(position)
                if styles.encounter_id(fmt) is None and self._image_rect(position, fmt).contains(point):
                    return position, fmt
        return None

    def _image_format(self, position: int) -> QTextImageFormat:
        cursor = QTextCursor(self.document())
        cursor.setPosition(position + 1)
        return cursor.charFormat().toImageFormat()

    def _image_rect(self, position: int, fmt: QTextImageFormat) -> QRect:
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        corner = self.cursorRect(cursor).topLeft()
        return QRect(corner.x(), corner.y(), round(fmt.width()), round(fmt.height()))

    def _select_image(self, position: int) -> None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        cursor.setPosition(position + 1, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)

    def _selected_image(self) -> int | None:
        """Posizione dell'immagine se è la sola cosa selezionata."""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        if cursor.selectionEnd() - start == 1 and self.document().characterAt(start) == styles.IMAGE_CHAR \
                and styles.encounter_id(self._image_format(start)) is None:
            return start
        return None

    def _resize_image(self, width: int) -> None:
        position = self._selected_image()
        if position is None:
            return
        fmt = self._image_format(position)
        if fmt.width() > 0 and fmt.height() > 0:
            ratio = fmt.height() / fmt.width()
        else:
            image = self._load_image(fmt.name())
            ratio = image.height() / image.width()
        commands.set_image_size(self, position, width, round(width * ratio))
        self._place_image_bar()
        self.setFocus()

    def _place_image_bar(self, *_) -> None:
        """Mostra la barra delle dimensioni sopra l'immagine selezionata (dentro, in alto, se sopra non c'è posto)."""
        position = self._selected_image() if not self._loading else None
        if position is None:
            self._image_bar.hide()
            return
        fmt = self._image_format(position)
        rect = self._image_rect(position, fmt)
        self._image_bar.set_value(round(fmt.width()))
        bar = self._image_bar
        x = max(8, min(rect.right() - bar.width() - 8, self.viewport().width() - bar.width() - 8))
        y = rect.top() - bar.height() - 8
        bar.move(x, y if y >= 8 else rect.top() + 8)
        bar.setVisible(rect.bottom() > 0 and rect.top() < self.viewport().height())
        bar.raise_()

    def _load_image(self, name: str) -> QImage:
        """L'immagine `name` (percorso nella cartella della campagna), ridotta se enorme; se manca, un segnaposto."""
        if name not in self._images:
            image = QImage()
            file = safe_media_path(self._media_dir, name) if self._media_dir is not None else None   # il testo può venire da fuori: mai fuori dalla campagna
            if file is not None:
                reader = QImageReader(str(file))
                reader.setAutoTransform(True)
                size = reader.size()
                if size.width() > IMAGE_MAX_PIXELS:
                    reader.setScaledSize(size.scaled(IMAGE_MAX_PIXELS, size.height(), Qt.KeepAspectRatio))
                image = reader.read()
            self._images[name] = image if not image.isNull() else self._placeholder_image()
        return self._images[name]

    @staticmethod
    def _placeholder_image() -> QImage:
        """Al posto di un'immagine che non si trova più."""
        image = QImage(280, 150, QImage.Format_ARGB32)
        image.fill(QColor(theme.SURFACE))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.BORDER_STRONG))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(image.rect()).adjusted(1, 1, -1, -1), 10, 10)
        icons.icon("image", theme.MUTED).paint(painter, QRect(124, 44, 32, 32))
        painter.setFont(theme.ui_font(13))
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QRect(0, 86, 280, 24), Qt.AlignCenter, "Immagine non trovata")
        painter.end()
        return image

    def loadResource(self, resource_type: int, name):
        kind = getattr(resource_type, "value", resource_type)
        if kind == QTextDocument.ResourceType.ImageResource.value:
            if name.toString().startswith(styles.ENCOUNTER_SCHEME) and self._encounters is not None:
                found = int(name.toString().removeprefix(styles.ENCOUNTER_SCHEME))
                return render_card(self._card(found), self._text_width(), self.devicePixelRatioF())
            return self._load_image(name.toString())
        return super().loadResource(resource_type, name)

    # --- Disegno dei box ------------------------------------------------------------------------
    def _invalidate_boxes(self, *_) -> None:
        self._boxes = None
        self.viewport().update()

    def _box_rects(self) -> list[tuple[float, float, str]]:
        """(alto, basso, tipo) di ogni box nelle coordinate del testo: dall'etichetta in cima al bordo in fondo."""
        if self._boxes is None:
            layout = self.document().documentLayout()
            self._boxes, run = [], None
            block = self.document().firstBlock()
            while block.isValid():
                box = styles.box_of(block)
                rect = layout.blockBoundingRect(block)
                if not box[0]:
                    run = None
                elif run is not None and run[0] == box:
                    run[2] = rect.bottom()
                else:
                    run = [box, rect.top(), rect.bottom()]
                    self._boxes.append(run)
                block = block.next()
            self._boxes = [(top - styles.BOX_HEADER, bottom + styles.BOX_PAD_BOTTOM, box[0]) for box, top, bottom in self._boxes]
        return self._boxes

    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        scroll = self.verticalScrollBar().value()
        for top, bottom, kind in self._box_rects():
            if bottom >= scroll and top <= scroll + self.viewport().height():
                self._paint_box(painter, QRectF(0, top - scroll, self.viewport().width(), bottom - top), kind)
        tables = self._visible_tables()
        active = commands.current_cell(self) if self._shows_table_controls() else None
        for table, grid in tables:        # sotto il testo: fondo dell'intestazione e della cella in cui si scrive
            self._paint_table_back(painter, grid, active[1:] if active and active[0] == table else None)
        painter.end()
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        for table, grid in tables:        # sopra: bordi e righe
            self._paint_table_lines(painter, grid, active[1:] if active and active[0] == table else None)
        painter.setPen(QPen(theme.tint(theme.ACCENT, 0.65), 2))      # sopra: l'occorrenza corrente di «Cerca nella pagina»
        painter.setBrush(Qt.NoBrush)
        for rect in self._outlines:
            painter.drawRoundedRect(rect.translated(0, -scroll).adjusted(-1, 0, 1, 0), 3, 3)
        painter.end()

    @staticmethod
    def _paint_box(painter: QPainter, rect: QRectF, kind: str) -> None:
        background, accent, _ = theme.BOX_COLORS[kind]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, styles.BOX_RADIUS, styles.BOX_RADIUS)
        left, top = int(rect.left()) + styles.BOX_PAD_X, int(rect.top()) + styles.BOX_PAD_TOP
        icons.icon(styles.BOX_ICONS[kind], accent).paint(painter, QRect(left, top, 15, 15))
        painter.setFont(theme.ui_font(11, 600, 0.09))
        painter.setPen(QColor(accent))
        painter.drawText(QRect(left + 22, top, int(rect.width()), styles.BOX_LABEL_HEIGHT),
                         Qt.AlignVCenter | Qt.AlignLeft, styles.BOX_LABELS[kind].upper())

    # --- Tabelle -------------------------------------------------------------------------------
    def _visible_tables(self) -> list[tuple[QTextTable, TableGrid]]:
        """Le tabelle visibili con le loro misure, in coordinate dell'area di testo."""
        scroll, height = self.verticalScrollBar().value(), self.viewport().height()
        found = []
        for frame in self.document().rootFrame().childFrames():
            if isinstance(frame, QTextTable):
                grid = table_grid(self.document(), frame)
                if grid.rows[-1] >= scroll and grid.rows[0] <= scroll + height:
                    found.append((frame, TableGrid([y - scroll for y in grid.rows], grid.columns)))
        return found

    @staticmethod
    def _paint_table_back(painter: QPainter, grid: TableGrid, active: tuple[int, int] | None) -> None:
        outline = QPainterPath()
        outline.addRoundedRect(grid.rect(), styles.TABLE_RADIUS, styles.TABLE_RADIUS)
        painter.save()
        painter.setClipPath(outline)
        painter.fillRect(grid.cell(0, 0).united(grid.cell(0, len(grid.columns) - 2)), QColor(theme.CONTROL_BG))
        if active is not None:
            painter.fillRect(grid.cell(*active), QColor(theme.TABLE_CELL_ACTIVE))
        painter.restore()

    @staticmethod
    def _paint_table_lines(painter: QPainter, grid: TableGrid, active: tuple[int, int] | None) -> None:
        rect = grid.rect()
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        for y in grid.rows[1:-1]:
            painter.drawLine(QPointF(rect.left(), round(y) + 0.5), QPointF(rect.right(), round(y) + 0.5))
        for x in grid.columns[1:-1]:
            painter.drawLine(QPointF(round(x) + 0.5, rect.top()), QPointF(round(x) + 0.5, rect.bottom()))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), styles.TABLE_RADIUS, styles.TABLE_RADIUS)
        if active is not None:
            painter.setPen(QPen(QColor(theme.ACCENT), 2))
            painter.drawRect(grid.cell(*active).adjusted(1, 1, -1, -1))

    def _shows_table_controls(self) -> bool:
        """Barra, «+» e cella evidenziata compaiono solo mentre si scrive in una tabella."""
        return self.hasFocus() and not self._loading and self.textCursor().currentTable() is not None

    def _place_table_controls(self, *_) -> None:
        if not self._shows_table_controls():
            self._table_controls.hide()
            return
        table = self.textCursor().currentTable()
        grid = table_grid(self.document(), table)
        offset = QPointF(self.viewport().geometry().topLeft()) - QPointF(0, self.verticalScrollBar().value())
        self._table_controls.place(grid.rect().translated(offset), QRectF(self.viewport().geometry()),
                                   table.rows(), table.columns())
        self.viewport().update()

    # --- Misure --------------------------------------------------------------------------------
    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() == QEvent.Resize:
            frame = self._frame
            side = frame.side if frame.text_width is None else max(frame.side, (self.width() - frame.text_width) // 2)
            if side != self._side:
                self._side = side
                self.setViewportMargins(side, 0, side, 0)
        return handled

    def resizeEvent(self, event) -> None:      # nelle aree di scorrimento arriva quando cambia il riquadro del testo
        super().resizeEvent(event)
        self._refresh_cards()
        self._invalidate_boxes()
        self._place_header()
        self._place_table_controls()
        if self.find is not None:
            self.find.place()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._place_table_controls()
        if self.spell is not None:
            self.spell.schedule()

    def _place_header(self, *_) -> None:
        if self._header is not None:
            self._header.setGeometry(0, self._frame.top - self.verticalScrollBar().value(),
                                     self.viewport().width(), self._header.minimumHeight())

    def hideEvent(self, event) -> None:
        self._hide_preview()
        super().hideEvent(event)

    def focusOutEvent(self, event) -> None:
        self._hide_preview()
        self._mention.close()
        super().focusOutEvent(event)
        self._place_table_controls()
        if self.spell is not None:
            self.spell.schedule()
        self.focus_lost.emit()
