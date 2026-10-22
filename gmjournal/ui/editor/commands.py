"""I comandi di formattazione dell'editor. Ognuno è un'unica azione: un solo «Annulla» la disfa.

I comandi cambiano solo i formati dei paragrafi e dei caratteri; margini, elenchi e aspetto coerente
li sistema `normalize.py` subito dopo, in un solo posto.
"""

from dataclasses import dataclass, replace
from typing import Callable

from PySide6.QtGui import QTextBlock, QTextBlockFormat, QTextCursor, QTextDocument, QTextImageFormat, QTextTable
from PySide6.QtWidgets import QTextEdit

from . import styles
from .styles import BODY, Flags


@dataclass(frozen=True)
class State:
    """Come appare la formattazione nel punto del cursore: serve alla barra degli strumenti."""
    heading: int = 0        # 0 = paragrafo, 1-3 = titolo
    bold: bool = False
    italic: bool = False
    underline: bool = False
    size: str = "md"
    list_kind: str = ""     # "", "ul" o "ol"
    box: str = ""           # "", "voice" o "master"
    link: bool = False
    highlight: str = ""     # colore dell'evidenziatore, "" = nessuno
    in_table: bool = False  # il cursore è in una cella


def state_of(editor: QTextEdit) -> State:
    block = editor.textCursor().block()
    context, heading = styles.block_flags(block)
    flags = styles.flags_of(editor.currentCharFormat(), context, heading)
    tlist = block.textList()
    return State(
        heading=heading,
        bold=flags.bold and not flags.href,     # un link è sempre in grassetto: non conta come scelta
        italic=flags.italic,
        underline=flags.underline,
        size=flags.size,
        list_kind=styles.list_kind(tlist.format()) if tlist else "",
        box=styles.box_of(block)[0],
        link=bool(flags.href),
        highlight=flags.highlight,
        in_table=styles.table_of(block) is not None,
    )


# --- Selezione ------------------------------------------------------------------------------
def selected_blocks(cursor: QTextCursor) -> list[QTextBlock]:
    """I paragrafi toccati dalla selezione (o quello del cursore). Se la selezione finisce proprio
    all'inizio di un paragrafo, quello non conta."""
    doc = cursor.document()
    start, end = cursor.selectionStart(), cursor.selectionEnd()
    block, last = doc.findBlock(start), doc.findBlock(end)
    if end > start and end == last.position():
        last = last.previous()
    blocks = []
    while block.isValid():
        blocks.append(block)
        if block == last:
            break
        block = block.next()
    return blocks


def _pieces(doc: QTextDocument, start: int, end: int) -> list[tuple]:
    """(inizio, fine, formato, contesto, titolo) dei pezzi di testo fra le due posizioni."""
    pieces = []
    block = doc.findBlock(start)
    while block.isValid() and block.position() < end:
        context, heading = styles.block_flags(block)
        for a, b, fmt in styles.fragments(block):
            a, b = max(a, start), min(b, end)
            if a < b:
                pieces.append((a, b, fmt, context, heading))
        block = block.next()
    return pieces


def _flags(piece: tuple) -> Flags:
    return styles.flags_of(piece[2], piece[3], piece[4])


def _restyle(doc: QTextDocument, pieces: list[tuple], change: Callable[[Flags], Flags]) -> None:
    for piece in pieces:
        flags = _flags(piece)
        new = change(flags)
        if new != flags:
            cursor = QTextCursor(doc)
            cursor.setPosition(piece[0])
            cursor.setPosition(piece[1], QTextCursor.KeepAnchor)
            cursor.setCharFormat(styles.char_format(piece[3], piece[4], new))


# --- Caratteri -------------------------------------------------------------------------------
def _apply_flags(editor: QTextEdit, applicable: Callable[[Flags, int], bool],
                 decide: Callable[[list[Flags]], Callable[[Flags], Flags]]) -> None:
    """Cambia la struttura del testo selezionato, o di quello che si scriverà se non c'è selezione.

    `applicable(flags, titolo)` dice se il cambiamento vale per quel testo; `decide` riceve la struttura
    attuale di tutti i pezzi e restituisce la funzione che trasforma ognuno.
    """
    cursor = editor.textCursor()
    if cursor.hasSelection():
        doc = cursor.document()
        pieces = [p for p in _pieces(doc, cursor.selectionStart(), cursor.selectionEnd()) if applicable(_flags(p), p[4])]
        if pieces:
            change = decide([_flags(p) for p in pieces])
            cursor.beginEditBlock()
            _restyle(doc, pieces, change)
            cursor.endEditBlock()
        return
    context, heading = styles.block_flags(cursor.block())
    flags = styles.flags_of(editor.currentCharFormat(), context, heading)
    if applicable(flags, heading):
        editor.setCurrentCharFormat(styles.char_format(context, heading, decide([flags])(flags)))


def toggle_style(editor: QTextEdit, name: str) -> None:
    """Attiva o toglie «bold», «italic» o «underline». I link restano sempre grassetto e sottolineati."""
    def decide(current: list[Flags]) -> Callable[[Flags], Flags]:
        turn_on = not all(getattr(flags, name) for flags in current)
        return lambda flags: replace(flags, **{name: turn_on})

    _apply_flags(editor, lambda flags, heading: not (flags.href and name != "italic"), decide)


def toggle_highlight(editor: QTextEdit, color: str) -> None:
    """Evidenzia con `color` (una chiave di `styles.HIGHLIGHTS`); se il testo lo è già tutto con quel colore,
    o se `color` è "", toglie l'evidenziatore."""
    def decide(current: list[Flags]) -> Callable[[Flags], Flags]:
        wanted = "" if not color or all(flags.highlight == color for flags in current) else color
        return lambda flags: replace(flags, highlight=wanted)

    _apply_flags(editor, lambda flags, heading: True, decide)


def set_size(editor: QTextEdit, size: str) -> None:
    """Dimensione del testo: «sm», «md» o «lg». I titoli hanno la loro."""
    _apply_flags(editor, lambda flags, heading: heading == 0, lambda current: lambda flags: replace(flags, size=size))


# --- Paragrafi -------------------------------------------------------------------------------
def _convert(block: QTextBlock, heading: int, box: tuple[str, int]) -> None:
    """Dà al paragrafo un nuovo ruolo (paragrafo, titolo, dentro un box) e ne rifà l'aspetto."""
    doc = block.document()
    old_context, old_heading = styles.block_flags(block)
    old_kind, kind = ("" if old_context == BODY else old_context), box[0]
    for start, end, fmt in styles.fragments(block):
        flags = styles.flags_of(fmt, old_context, old_heading)
        if kind != old_kind and "voice" in (kind, old_kind):
            flags = replace(flags, italic=kind == "voice")     # «Da leggere a voce» è in corsivo
        cursor = QTextCursor(doc)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.setCharFormat(styles.char_format(kind or BODY, heading, flags))

    fmt = QTextBlockFormat(block.blockFormat())
    fmt.setHeadingLevel(heading)
    if kind:
        fmt.setProperty(styles.BOX_KIND, kind)
        fmt.setProperty(styles.BOX_ID, box[1])
    else:
        fmt.clearProperty(styles.BOX_KIND)
        fmt.clearProperty(styles.BOX_ID)
    cursor = QTextCursor(block)
    cursor.setBlockFormat(fmt)
    cursor.setBlockCharFormat(styles.char_format(kind or BODY, heading, styles.default_box_flags(kind)))


def set_heading(editor: QTextEdit, level: int) -> None:
    """Trasforma i paragrafi selezionati in titolo di livello 1-3, o in paragrafo normale (0).
    Dentro i box e le tabelle non ci sono titoli; una voce di elenco esce dall'elenco."""
    cursor = editor.textCursor()
    blocks = [block for block in selected_blocks(cursor) if not styles.box_of(block)[0] and styles.table_of(block) is None]
    cursor.beginEditBlock()
    for block in blocks:
        if block.textList() is not None:
            block.textList().remove(block)
        _convert(block, level, ("", 0))
    cursor.endEditBlock()


def insert_title(editor: QTextEdit, text: str, level: int = 2) -> None:
    """Scrive un titolo (`text`) dopo il paragrafo del cursore e lascia un paragrafo vuoto sotto, dove continuare a scrivere.
    Dentro un box, un elenco o una tabella il titolo va in fondo al testo."""
    cursor = editor.textCursor()
    cursor.clearSelection()
    block = cursor.block()
    cursor.beginEditBlock()
    inside = styles.table_of(block) is not None or styles.box_of(block)[0] or block.textList() is not None
    cursor.movePosition(QTextCursor.End if inside else QTextCursor.EndOfBlock)
    if cursor.block().length() > 1:
        cursor.insertBlock(styles.block_format())
    _convert(cursor.block(), level, ("", 0))
    cursor.insertText(text)
    cursor.insertBlock(styles.block_format(), styles.char_format())
    cursor.endEditBlock()
    editor.setTextCursor(cursor)


# --- Elenchi ---------------------------------------------------------------------------------
def toggle_list(editor: QTextEdit, kind: str) -> None:
    """Trasforma i paragrafi selezionati in elenco puntato («ul») o numerato («ol»); se lo sono già, li toglie.
    Nelle tabelle non ci sono elenchi."""
    cursor = editor.textCursor()
    blocks = [block for block in selected_blocks(cursor) if styles.table_of(block) is None]
    if not blocks:
        return
    cursor.beginEditBlock()
    if all(b.textList() is not None and styles.list_kind(b.textList().format()) == kind for b in blocks):
        for block in blocks:
            block.textList().remove(block)
    else:
        for block in blocks:
            tlist = block.textList()
            if tlist is not None and styles.list_kind(tlist.format()) == kind:
                continue
            if styles.heading_of(block):
                _convert(block, 0, ("", 0))
            depth = tlist.format().indent() if tlist is not None else 1
            QTextCursor(block).createList(styles.list_format(kind, depth))
    cursor.endEditBlock()


def change_indent(editor: QTextEdit, delta: int) -> None:
    """Sposta le voci di elenco selezionate di un livello (+1 dentro, -1 fuori; dal primo livello escono dall'elenco)."""
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    for block in selected_blocks(cursor):
        tlist = block.textList()
        if tlist is None:
            continue
        depth = tlist.format().indent() + delta
        if depth < 1:
            tlist.remove(block)
        elif depth <= styles.MAX_LIST_DEPTH:
            QTextCursor(block).createList(styles.list_format(styles.list_kind(tlist.format()), depth))
    cursor.endEditBlock()


# --- Box -------------------------------------------------------------------------------------
def next_box_id(doc: QTextDocument) -> int:
    ids = []
    block = doc.firstBlock()
    while block.isValid():
        ids.append(styles.box_of(block)[1])
        block = block.next()
    return max(ids, default=0) + 1


def _whole_box(block: QTextBlock) -> list[QTextBlock]:
    box = styles.box_of(block)
    first = last = block
    while first.previous().isValid() and styles.box_of(first.previous()) == box:
        first = first.previous()
    while last.next().isValid() and styles.box_of(last.next()) == box:
        last = last.next()
    blocks = [first]
    while blocks[-1] != last:
        blocks.append(blocks[-1].next())
    return blocks


def set_box(editor: QTextEdit, kind: str) -> None:
    """Mette i paragrafi selezionati in un box «voice» o «master»; con kind="" li toglie dal box.
    Senza selezione, dentro un box, vale per tutto il box. Le tabelle non vanno nei box."""
    cursor = editor.textCursor()
    blocks = [block for block in selected_blocks(cursor) if styles.table_of(block) is None]
    if not blocks:
        return
    if not cursor.hasSelection() and styles.box_of(blocks[0])[0]:
        blocks = _whole_box(blocks[0])
    if all(styles.box_of(block)[0] == kind for block in blocks):
        return
    box = (kind, next_box_id(cursor.document())) if kind else ("", 0)
    cursor.beginEditBlock()
    for block in blocks:
        _convert(block, 0, box)
    cursor.endEditBlock()


def leave_box(editor: QTextEdit) -> None:
    """Il paragrafo del cursore esce dal suo box (un «Invio» su una riga vuota in fondo al box)."""
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    _convert(cursor.block(), 0, ("", 0))
    cursor.endEditBlock()


# --- Link ------------------------------------------------------------------------------------
def link_range(doc: QTextDocument, position: int) -> tuple[int, int, str] | None:
    """(inizio, fine, destinazione) del link che contiene il carattere in `position`, o None."""
    pieces = styles.fragments(doc.findBlock(position))
    for i, (start, end, fmt) in enumerate(pieces):
        if fmt.isAnchor() and start <= position < end:
            href = fmt.anchorHref()
            first = last = i
            while first > 0 and _continues(pieces[first - 1], pieces[first], href):
                first -= 1
            while last < len(pieces) - 1 and _continues(pieces[last], pieces[last + 1], href):
                last += 1
            return pieces[first][0], pieces[last][1], href
    return None


def _continues(before: tuple, after: tuple, href: str) -> bool:
    return before[1] == after[0] and before[2].isAnchor() and after[2].isAnchor() and after[2].anchorHref() == href


def link_at_caret(cursor: QTextCursor) -> tuple[int, int, str] | None:
    """Il link su cui si trova il cursore (anche subito dopo la sua ultima lettera)."""
    position = cursor.position()
    found = link_range(cursor.document(), position)
    if found is None and position > cursor.block().position():
        found = link_range(cursor.document(), position - 1)
    return found


def insert_link(editor: QTextEdit, href: str, label: str, replace_range: tuple[int, int] | None = None) -> None:
    """Collega il testo a `href`.

    In ordine: sostituisce il tratto `replace_range` con `label` (la «@nome» appena scritta); altrimenti
    collega la selezione; altrimenti, se il cursore è su un link, ne cambia la destinazione; altrimenti
    scrive `label` come link.
    """
    cursor = editor.textCursor()
    doc = cursor.document()
    as_link = lambda flags: replace(flags, href=href, bold=False, underline=False)   # noqa: E731
    cursor.beginEditBlock()
    if replace_range is None and cursor.hasSelection():
        _restyle(doc, _pieces(doc, cursor.selectionStart(), cursor.selectionEnd()), as_link)
    elif replace_range is None and (found := link_at_caret(cursor)):
        _restyle(doc, _pieces(doc, found[0], found[1]), as_link)
    else:
        if replace_range is not None:
            cursor.setPosition(replace_range[0])
            cursor.setPosition(replace_range[1], QTextCursor.KeepAnchor)
        context, heading = styles.block_flags(cursor.block())
        base = styles.flags_of(editor.currentCharFormat(), context, heading)
        cursor.insertText(label, styles.char_format(context, heading, as_link(base)))
    cursor.endEditBlock()
    editor.setTextCursor(cursor)


def remove_link(editor: QTextEdit, start: int, end: int) -> None:
    """Toglie il collegamento al testo fra le due posizioni (il testo resta)."""
    doc = editor.document()
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    _restyle(doc, _pieces(doc, start, end), lambda flags: replace(flags, href=""))
    cursor.endEditBlock()


# --- Immagini --------------------------------------------------------------------------------
def insert_image(editor: QTextEdit, name: str, width: int, height: int) -> None:
    """Inserisce un'immagine (percorso `name` nella cartella della campagna) in un paragrafo suo,
    e lascia il cursore nel paragrafo che segue. Nelle tabelle non ci sono immagini."""
    cursor = editor.textCursor()
    if cursor.currentTable() is not None:
        return
    cursor.beginEditBlock()
    cursor.removeSelectedText()
    if cursor.block().length() > 1:
        cursor.insertBlock()
    context, heading = styles.block_flags(cursor.block())
    fmt = QTextImageFormat()
    fmt.merge(styles.char_format(context, heading, Flags()))
    fmt.setName(name)
    fmt.setWidth(width)
    fmt.setHeight(height)
    cursor.insertImage(fmt)
    cursor.insertBlock()
    cursor.endEditBlock()
    editor.setTextCursor(cursor)


def insert_encounter(editor: QTextEdit, encounter_id: int) -> None:
    """Inserisce il box di un incontro in un paragrafo suo (dopo il box, se si è dentro uno), e lascia il cursore nel
    paragrafo che segue. Nelle tabelle non ci sono incontri."""
    cursor = editor.textCursor()
    if cursor.currentTable() is not None:
        return
    cursor.beginEditBlock()
    cursor.removeSelectedText()
    block = cursor.block()
    if styles.box_of(block)[0]:          # un incontro non sta dentro un box: va subito dopo
        while styles.box_of(block.next()) == styles.box_of(block):
            block = block.next()
        cursor.setPosition(block.position() + block.length() - 1)
        cursor.insertBlock(styles.block_format(), styles.char_format())
    elif cursor.position() > block.position():
        cursor.insertBlock()             # a metà di un paragrafo: il resto del testo va sotto
    cursor.insertText(styles.IMAGE_CHAR, styles.encounter_format(encounter_id))
    placed = cursor.block()
    cursor.insertBlock()
    if placed.textList() is not None:
        placed.textList().remove(placed)
    QTextCursor(placed).setBlockFormat(styles.block_format())
    cursor.endEditBlock()
    editor.setTextCursor(cursor)


def remove_encounter(editor: QTextEdit, encounter_id: int) -> None:
    """Toglie dal testo il box dell'incontro (e il suo paragrafo, se resta vuoto)."""
    doc = editor.document()
    block = doc.firstBlock()
    while block.isValid() and styles.encounter_in(block) != encounter_id:
        block = block.next()
    if not block.isValid():
        return
    cursor = QTextCursor(doc)
    cursor.beginEditBlock()
    cursor.setPosition(block.position() + block.text().index(styles.IMAGE_CHAR))
    cursor.deleteChar()
    if block.length() <= 1:               # il paragrafo è rimasto vuoto: sparisce anche lui
        if block.previous().isValid():
            cursor.setPosition(block.position() - 1)
            cursor.setPosition(block.position() + block.length() - 1, QTextCursor.KeepAnchor)
        else:
            cursor.setPosition(block.position())
            cursor.setPosition(min(block.position() + block.length(), doc.characterCount() - 1), QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
    cursor.endEditBlock()


def set_image_size(editor: QTextEdit, position: int, width: int, height: int) -> None:
    """Cambia la dimensione dell'immagine che si trova al carattere `position`."""
    cursor = QTextCursor(editor.document())
    cursor.setPosition(position)
    cursor.setPosition(position + 1, QTextCursor.KeepAnchor)
    fmt = QTextImageFormat()
    fmt.setWidth(width)
    fmt.setHeight(height)
    cursor.mergeCharFormat(fmt)


# --- Tabelle ---------------------------------------------------------------------------------
# L'aspetto delle celle (intestazione, margini, niente titoli o elenchi) lo sistema `normalize.py`.
def insert_table(editor: QTextEdit, rows: int, columns: int) -> None:
    """Inserisce una tabella nel punto del cursore (non in un box né in un'altra tabella) e porta il cursore
    nella prima cella. Se il cursore è su una riga vuota, la tabella prende il suo posto."""
    cursor = editor.textCursor()
    if cursor.currentTable() is not None or styles.box_of(cursor.block())[0]:
        return
    doc = cursor.document()
    cursor.beginEditBlock()
    cursor.removeSelectedText()
    block = cursor.block()
    if block.length() <= 1 and block.previous().isValid() and styles.table_of(block.previous()) is None:
        cursor.deletePreviousChar()           # la riga vuota si unisce a quella sopra: la tabella va subito dopo
    block_fmt, char_fmt = cursor.blockFormat(), cursor.blockCharFormat()
    table = cursor.insertTable(rows, columns, styles.table_format())
    after = QTextCursor(doc)
    after.setPosition(table.lastPosition() + 1)
    if after.block().length() <= 1:           # il paragrafo che Qt aggiunge dopo la tabella: testo normale
        after.setBlockFormat(styles.block_format())
        after.setBlockCharFormat(styles.char_format())
    else:                                     # la tabella ha diviso un paragrafo: la seconda parte resta com'era
        after.setBlockFormat(block_fmt)
        after.setBlockCharFormat(char_fmt)
    cursor.endEditBlock()
    editor.setTextCursor(table.cellAt(0, 0).firstCursorPosition())


def current_cell(editor: QTextEdit) -> tuple[QTextTable, int, int] | None:
    """(tabella, riga, colonna) della cella in cui si trova il cursore, o None."""
    cursor = editor.textCursor()
    table = cursor.currentTable()
    if table is None:
        return None
    cell = table.cellAt(cursor)
    return table, cell.row(), cell.column()


def _change_table(editor: QTextEdit, change: Callable[[QTextTable, int, int], tuple[int, int]]) -> None:
    """Un cambiamento della tabella del cursore; `change` restituisce la cella (riga, colonna) dove portare il cursore."""
    found = current_cell(editor)
    if found is None:
        return
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    row, column = change(*found)
    cursor.endEditBlock()
    editor.setTextCursor(found[0].cellAt(row, column).lastCursorPosition())


def add_row(editor: QTextEdit, where: str) -> None:
    """Aggiunge una riga «above» o «below» quella del cursore, o in fondo («end»). Il cursore va nella riga nuova."""
    def change(table: QTextTable, row: int, column: int) -> tuple[int, int]:
        if where == "end":
            table.appendRows(1)
            return table.rows() - 1, 0
        index = row if where == "above" else row + 1
        table.insertRows(index, 1)
        return index, column

    _change_table(editor, change)


def add_column(editor: QTextEdit, where: str) -> None:
    """Aggiunge una colonna a destra di quella del cursore («right») o in fondo a destra («end»)."""
    def change(table: QTextTable, row: int, column: int) -> tuple[int, int]:
        if where == "end":
            table.appendColumns(1)
            return row, table.columns() - 1
        table.insertColumns(column + 1, 1)
        return row, column + 1

    _change_table(editor, change)


def delete_row(editor: QTextEdit) -> None:
    """Elimina la riga del cursore (che va nella riga che prende il suo posto). L'unica riga di una tabella non si
    toglie: per quello c'è `delete_table`. Se era l'intestazione, lo diventa la riga sotto (lo sistema `normalize.py`)."""
    def change(table: QTextTable, row: int, column: int) -> tuple[int, int]:
        table.removeRows(row, 1)
        return min(row, table.rows() - 1), column

    found = current_cell(editor)
    if found is not None and found[0].rows() > 1:
        _change_table(editor, change)


def delete_column(editor: QTextEdit) -> None:
    """Elimina la colonna del cursore (che va nella colonna che prende il suo posto); l'unica colonna non si toglie."""
    def change(table: QTextTable, row: int, column: int) -> tuple[int, int]:
        table.removeColumns(column, 1)
        return row, min(column, table.columns() - 1)

    found = current_cell(editor)
    if found is not None and found[0].columns() > 1:
        _change_table(editor, change)


def move_to_cell(editor: QTextEdit, step: int) -> None:
    """Va alla cella successiva (+1) o precedente (-1); dopo l'ultima cella aggiunge una riga."""
    found = current_cell(editor)
    if found is None:
        return
    table, row, column = found
    index = row * table.columns() + column + step
    if index >= table.rows() * table.columns():
        add_row(editor, "end")
    elif index >= 0:
        editor.setTextCursor(table.cellAt(index // table.columns(), index % table.columns()).lastCursorPosition())


def delete_table(editor: QTextEdit) -> None:
    """Elimina la tabella del cursore (si annulla con Ctrl+Z come ogni modifica del testo)."""
    found = current_cell(editor)
    if found is None:
        return
    table = found[0]
    doc = editor.document()
    before = doc.findBlock(table.firstPosition() - 1)
    after = doc.findBlock(table.lastPosition() + 1)
    after_fmt, after_char = after.blockFormat(), after.charFormat()
    cursor = QTextCursor(doc)
    cursor.beginEditBlock()
    cursor.setPosition(table.firstPosition() - 1)
    cursor.setPosition(table.lastPosition() + 1, QTextCursor.KeepAnchor)
    empty_before = before.length() <= 1
    cursor.removeSelectedText()               # Qt unisce il paragrafo prima della tabella con quello dopo
    if empty_before:
        cursor.setBlockFormat(after_fmt)
        cursor.setBlockCharFormat(after_char)
    else:
        cursor.insertBlock(after_fmt, after_char)     # li separa di nuovo, ognuno com'era
    cursor.endEditBlock()
    editor.setTextCursor(cursor)
