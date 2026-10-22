"""Dopo ogni modifica riporta il testo alla forma che il resto del programma si aspetta.

Qt da solo non mantiene alcune regole: un Invio, un Canc o un incolla possono lasciare un paragrafo con
caratteri del box sbagliato, due elenchi vicini che per Qt sono separati (la numerazione ricomincia) ma
una volta salvati diventano uno solo, margini non più adatti, un titolo o un elenco dentro una cella di tabella.
Qui le regole sono in un posto solo, e si applicano alla sola zona modificata (con le tabelle che tocca, intere).
"""

from PySide6.QtGui import QTextBlock, QTextCursor, QTextDocument, QTextList

from . import styles


def normalize(doc: QTextDocument, start: int = 0, end: int | None = None) -> None:
    """Sistema la zona del testo fra le posizioni `start` e `end` (senza indicarle: tutto)."""
    if end is not None:
        start, end = _with_whole_tables(doc, start, end)
    first, last = styles.block_range(doc, start, end)
    _fix_cells(first, last)
    _fix_characters(first, last)
    _fix_lists(first, last)
    styles.apply_layout(doc, start, end)


def _with_whole_tables(doc: QTextDocument, start: int, end: int) -> tuple[int, int]:
    """Allarga la zona alle tabelle che tocca, se la modifica riguarda più paragrafi (righe o colonne aggiunte: con una
    riga in cima, per esempio, cambia l'intestazione). Scrivendo in una cella basta la cella."""
    top = doc.characterCount() - 1
    if doc.findBlock(max(0, min(start, top))) == doc.findBlock(max(0, min(end, top))):
        return start, end
    for position in (start, end):
        table = styles.table_of(doc.findBlock(max(0, min(position, top))))
        if table is not None:
            start, end = min(start, table.firstPosition()), max(end, table.lastPosition())
    return start, end


# --- Tabelle -------------------------------------------------------------------------------
def _fix_cells(first: QTextBlock, last: QTextBlock) -> None:
    """In una cella c'è solo testo «in riga»: niente titoli, elenchi, box o immagini (arrivano solo da un incolla)."""
    block = first
    while block.isValid():
        if styles.table_of(block) is not None:
            if block.textList() is not None:
                block.textList().remove(block)
            fmt = block.blockFormat()
            if fmt.headingLevel() or fmt.hasProperty(styles.BOX_KIND):
                fmt.setHeadingLevel(0)
                fmt.clearProperty(styles.BOX_KIND)
                fmt.clearProperty(styles.BOX_ID)
                QTextCursor(block).setBlockFormat(fmt)
            context = styles.context_of(block)       # una cella vuota: si scriverà con l'aspetto giusto
            wanted = styles.char_format(context, 0, styles.flags_of(block.charFormat(), context, 0))
            if block.length() <= 1 and not styles.same_look(block.charFormat(), wanted):
                QTextCursor(block).setBlockCharFormat(wanted)
            text = block.text()
            for offset in reversed([i for i, char in enumerate(text) if char == styles.IMAGE_CHAR]):
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + offset)
                cursor.deleteChar()
        if block == last:
            break
        block = block.next()


# --- Caratteri -----------------------------------------------------------------------------
def _fix_characters(first: QTextBlock, last: QTextBlock) -> None:
    """Ogni pezzo di testo ha l'aspetto previsto dal suo paragrafo (corpo, box, titolo)."""
    block = first
    while block.isValid():
        context, heading = styles.block_flags(block)
        for start, end, fmt in styles.fragments(block):
            wanted = styles.char_format(context, heading, styles.flags_of(fmt, context, heading))
            if not styles.same_look(fmt, wanted):
                cursor = QTextCursor(block.document())
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.setCharFormat(wanted)
        if block == last:
            break
        block = block.next()


# --- Elenchi -------------------------------------------------------------------------------
def _fix_lists(first: QTextBlock, last: QTextBlock) -> None:
    """Un elenco di Qt corrisponde esattamente a un <ul>/<ol> del testo salvato.

    Si ripercorrono le voci come fa il salvataggio (stessi livelli, stessi cambi di tipo) e a ogni voce si
    dà l'elenco che le spetta: continua quello sopra, oppure ne comincia uno nuovo.
    """
    while first.previous().isValid() and _in_run(first.previous(), first):
        first = first.previous()
    while last.next().isValid() and _in_run(last, last.next()):
        last = last.next()

    levels: list[list] = []        # per ogni livello aperto: [tipo, elenco di Qt o None]
    run_box = None
    block = first
    while block.isValid():
        tlist = block.textList()
        if tlist is None or styles.box_of(block) != run_box:
            levels.clear()
        if tlist is not None:
            run_box = styles.box_of(block)
            _place_item(block, tlist, levels)
        if block == last:
            break
        block = block.next()


def _in_run(a: QTextBlock, b: QTextBlock) -> bool:
    """Le due voci appartengono alla stessa serie ininterrotta di elenchi?"""
    return a.textList() is not None and b.textList() is not None and styles.box_of(a) == styles.box_of(b)


def _place_item(block: QTextBlock, tlist: QTextList, levels: list[list]) -> None:
    depth = max(1, tlist.format().indent())
    kind = styles.list_kind(tlist.format())
    while len(levels) > depth or (len(levels) == depth and levels[-1][0] != kind):
        levels.pop()
    while len(levels) < depth:
        levels.append([kind, None])
    level = levels[-1]
    if level[1] is None:
        # Nuovo elenco: se la voce è già la prima del suo elenco lo si tiene, altrimenti se ne crea uno
        # (la voce sta in un elenco che continua altrove, ma qui il testo salvato ne comincerebbe uno nuovo).
        level[1] = tlist if tlist.itemNumber(block) == 0 else QTextCursor(block).createList(styles.list_format(kind, depth))
    elif tlist != level[1]:
        level[1].add(block)
