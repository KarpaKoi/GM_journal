"""Il formato in cui una pagina viene salvata, e la conversione da e verso il documento dell'editor.

Il testo salvato è un piccolo HTML pulito che descrive solo la struttura, mai l'aspetto:

    <h1>…</h1> <h2>… <h3>…  <p>…</p>  <ul><li>…</li></ul>  <ol>…  <div class="box voice|master"><p>…</p></div>
    <table><tr><th>…</th></tr><tr><td>…</td></tr></table>   (la prima riga è sempre l'intestazione)
    <b> <i> <u>  <span class="sm|lg">  <span class="hl hl-sabbia">  <a href="gmj://tipo/ID">  <br>
    <img src="immagini/x.png" width= height=>
    <div class="encounter" data-id="N"></div>   (il box di un incontro: sta sempre da solo, fuori dagli altri box)

Nelle celle delle tabelle c'è solo testo con formattazione «in riga» (niente titoli, elenchi, box, immagini).

L'aspetto (caratteri, misure, colori) viene da `styles.py`: cambiando il design, anche le pagine già scritte
cambiano di conseguenza. Questo formato lo scrive e lo legge solo questo modulo.
"""

import html
from dataclasses import replace
from html.parser import HTMLParser

from PySide6.QtGui import QTextCursor, QTextDocument, QTextImageFormat, QTextList

from . import styles
from .styles import BODY, Flags

LINE_BREAK = " "   # «a capo» dentro un paragrafo (Maiusc+Invio)


# --- Documento -> testo salvato -----------------------------------------------------------
def export_html(doc: QTextDocument) -> str:
    return _Exporter().run(doc)


class _Exporter:
    def __init__(self):
        self._out: list[str] = []
        self._lists: list[str] = []          # un elemento per ogni livello di elenco aperto: "ul" o "ol"
        self._box: tuple[str, int] = ("", 0)

    def run(self, doc: QTextDocument) -> str:
        last = doc.lastBlock()
        while last.isValid() and _is_empty_plain(last):   # i paragrafi vuoti in fondo non si salvano
            last = last.previous()
        block = doc.firstBlock()
        if _is_empty_plain(block) and styles.table_of(block.next()) is not None:
            block = block.next()      # prima di una tabella in cima al testo Qt tiene sempre un paragrafo vuoto
        while block.isValid() and last.isValid() and block.position() <= last.position():
            table = styles.table_of(block)
            if table is None:
                self._block(block)
                block = block.next()
            else:
                self._table(table)
                block = doc.findBlock(table.lastPosition() + 1)
        self._close_lists(0)
        self._set_box(("", 0))
        return "".join(self._out)

    def _set_box(self, box: tuple[str, int]) -> None:
        if box == self._box:
            return
        self._close_lists(0)
        if self._box[0]:
            self._out.append("</div>")
        if box[0]:
            self._out.append(f'<div class="box {box[0]}">')
        self._box = box

    def _close_lists(self, keep: int) -> None:
        while len(self._lists) > keep:
            self._out.append(f"</li></{self._lists.pop()}>")

    def _block(self, block) -> None:
        if styles.encounter_in(block) is not None:
            self._encounter_block(block)
            return
        self._set_box(styles.box_of(block))
        context, heading = styles.block_flags(block)
        inline = self._inline(block, context, heading)
        tlist = block.textList()
        if tlist is None:
            self._close_lists(0)
            tag = f"h{heading}" if heading else "p"
            self._out.append(f"<{tag}>{inline}</{tag}>")
            return
        depth = max(1, tlist.format().indent())
        tag = styles.list_kind(tlist.format())
        while len(self._lists) > depth or (len(self._lists) == depth and self._lists[-1] != tag):
            self._out.append(f"</li></{self._lists.pop()}>")
        if len(self._lists) == depth:
            self._out.append("</li><li>")
        while len(self._lists) < depth:
            self._lists.append(tag)
            # i livelli «saltati» (elenco che comincia già annidato) sono contenitori senza voce: li segna class="gap"
            self._out.append(f"<{tag}><li>" if len(self._lists) == depth else f'<{tag}><li class="gap">')
        self._out.append(inline)

    def _encounter_block(self, block) -> None:
        """Il box di un incontro sta da solo, fuori da elenchi e box; il testo scritto accanto diventa paragrafo."""
        self._close_lists(0)
        self._set_box(("", 0))
        context, heading = styles.block_flags(block)
        run: list[str] = []
        for fragment in _fragments(block):
            found = styles.encounter_id(fragment.charFormat())
            if found is None:
                run.append(self._fragment(fragment, context, heading))
                continue
            self._flush(run)
            self._out.append(f'<div class="encounter" data-id="{found}"></div>')
        self._flush(run)

    def _flush(self, run: list[str]) -> None:
        if run:
            self._out.append(f"<p>{''.join(run)}</p>")
            run.clear()

    def _table(self, table) -> None:
        self._close_lists(0)          # una tabella non sta in un elenco né in un box
        self._set_box(("", 0))
        rows = []
        for row in range(table.rows()):
            tag = "th" if row == 0 else "td"
            cells = "".join(f"<{tag}>{self._cell(table.cellAt(row, column))}</{tag}>" for column in range(table.columns()))
            rows.append(f"<tr>{cells}</tr>")
        self._out.append(f"<table>{''.join(rows)}</table>")

    def _cell(self, cell) -> str:
        """Il testo di una cella; se ha più paragrafi (un incolla) diventano righe della stessa cella."""
        block, last = cell.firstCursorPosition().block(), cell.lastCursorPosition().block()
        parts = []
        while block.isValid():
            parts.append(self._inline(block, *styles.block_flags(block)))
            if block == last:
                break
            block = block.next()
        return "<br>".join(parts)

    def _inline(self, block, context: str, heading: int) -> str:
        return "".join(self._fragment(fragment, context, heading) for fragment in _fragments(block))

    @staticmethod
    def _fragment(fragment, context: str, heading: int) -> str:
        fmt = fragment.charFormat()
        if fmt.isImageFormat():
            image = fmt.toImageFormat()
            size = "".join(f' {name}="{round(value)}"' for name, value in
                           (("width", image.width()), ("height", image.height())) if value > 0)
            return f'<img src="{html.escape(image.name(), quote=True)}"{size}>' * fragment.text().count(styles.IMAGE_CHAR)
        return _span(fragment.text(), styles.flags_of(fmt, context, heading), heading)


def _fragments(block):
    """I pezzi di un paragrafo (Qt) nell'ordine in cui compaiono."""
    it = block.begin()
    while not it.atEnd():
        yield it.fragment()
        it += 1


def _is_empty_plain(block) -> bool:
    return (block.length() <= 1 and block.textList() is None and not styles.box_of(block)[0]
            and styles.table_of(block) is None)


def _span(text: str, flags: Flags, heading: int) -> str:
    if not text:
        return ""
    inner = html.escape(text, quote=False).replace(LINE_BREAK, "<br>")
    if heading == 0 and flags.size != "md":
        inner = f'<span class="{flags.size}">{inner}</span>'
    if flags.underline:
        inner = f"<u>{inner}</u>"
    if flags.italic:
        inner = f"<i>{inner}</i>"
    if flags.bold and not flags.href:
        inner = f"<b>{inner}</b>"
    if flags.href:
        inner = f'<a href="{html.escape(flags.href, quote=True)}">{inner}</a>'
    if flags.highlight:
        inner = f'<span class="hl hl-{flags.highlight}">{inner}</span>'
    return inner


# --- Testo salvato -> documento ----------------------------------------------------------
def fill_document(doc: QTextDocument, content: str, first_box_id: int = 1) -> None:
    """Sostituisce tutto il contenuto di `doc` con quello descritto da `content`.

    I box ricevono numeri a partire da `first_box_id` (per non confondersi con quelli già presenti).
    """
    parser = _TreeParser()
    parser.feed(content)
    parser.close()
    doc.clear()
    doc.setDocumentMargin(0)
    doc.setIndentWidth(styles.LIST_INDENT_PX)
    doc.setDefaultFont(styles.char_format().font())
    doc.setUndoRedoEnabled(False)   # niente «annulla» per il caricamento stesso
    guard = QTextCursor(doc)
    guard.beginEditBlock()          # un'unica modifica: il documento si ridisegna una volta sola, non a ogni paragrafo
    try:
        _Builder(doc, first_box_id).build(parser.root.children)
    finally:
        guard.endEditBlock()
    # Le tabelle create in un blocco di modifica Qt le riconosce solo a blocco chiuso: margini e interlinea dopo.
    guard.beginEditBlock()
    try:
        styles.apply_layout(doc)
    finally:
        guard.endEditBlock()
    doc.setModified(False)
    doc.setUndoRedoEnabled(True)


class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict[str, str | None]):
        self.tag, self.attrs, self.children = tag, attrs, []


class _TreeParser(HTMLParser):
    _VOID = {"br", "img"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {})
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs))
        self._stack[-1].children.append(node)
        if tag not in self._VOID:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._stack[-1].children.append(_Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        if any(node.tag == tag for node in self._stack[1:]):   # tag di chiusura inatteso: si ignora
            while self._stack[-1].tag != tag:
                self._stack.pop()
            self._stack.pop()

    def handle_data(self, data):
        self._stack[-1].children.append(data)


class _Builder:
    def __init__(self, doc: QTextDocument, first_box_id: int):
        self._cursor = QTextCursor(doc)
        self._fresh = True            # il paragrafo corrente è quello vuoto di partenza: va riempito, non aggiunto
        self._next_box_id = first_box_id

    def build(self, nodes: list) -> None:
        self._blocks(nodes, ("", 0))
        if self._fresh:               # contenuto vuoto: il primo paragrafo prende comunque il formato di base
            self._new_block(styles.block_format(), styles.char_format())

    def _blocks(self, nodes: list, box: tuple[str, int]) -> None:
        for node in nodes:
            if isinstance(node, str):
                if node.strip():      # testo senza paragrafo attorno: lo si accetta come paragrafo
                    self._text_block([node], 0, box)
            elif node.tag in ("h1", "h2", "h3"):
                self._text_block(node.children, 0 if box[0] else int(node.tag[1]), box)
            elif node.tag == "p":
                self._text_block(node.children, 0, box)
            elif node.tag in ("ul", "ol"):
                self._list(node, 1, box)
            elif node.tag == "table":
                self._table(node)
            elif node.tag == "div" and not box[0] and (found := _encounter_id(node)) is not None:
                self._encounter(found)
            elif node.tag == "div" and not box[0] and (kind := _box_kind(node)):
                self._blocks(node.children, (kind, self._next_box_id))
                self._next_box_id += 1
            elif node.tag not in ("br", "img"):
                self._blocks(node.children, box)

    def _new_block(self, bfmt, cfmt) -> None:
        if self._fresh:
            self._cursor.setBlockFormat(bfmt)
            self._cursor.setBlockCharFormat(cfmt)
            self._fresh = False
        else:
            self._cursor.insertBlock(bfmt, cfmt)

    def _text_block(self, children: list, heading: int, box: tuple[str, int]) -> None:
        kind = box[0]
        self._new_block(styles.block_format(heading, *box),
                        styles.char_format(kind or BODY, heading, styles.default_box_flags(kind)))
        self._inline(children, kind or BODY, heading, Flags())

    def _encounter(self, encounter_id: int) -> None:
        self._new_block(styles.block_format(), styles.char_format())
        self._cursor.insertText(styles.IMAGE_CHAR, styles.encounter_format(encounter_id))

    def _table(self, node: _Node) -> None:
        rows = [[cell for cell in tr.children if not isinstance(cell, str) and cell.tag in ("th", "td")] for tr in _rows(node)]
        rows = [row for row in rows if row]
        if not rows:
            return
        if self._fresh:               # la tabella è la prima cosa: il paragrafo che Qt tiene prima di lei è normale
            self._new_block(styles.block_format(), styles.char_format())
        columns = max(len(row) for row in rows)
        table = self._cursor.insertTable(len(rows), columns, styles.table_format())
        outside = self._cursor
        for r, row in enumerate(rows):
            context = styles.HEAD if r == 0 else styles.CELL     # la prima riga è sempre l'intestazione
            for c in range(columns):
                self._cursor = table.cellAt(r, c).firstCursorPosition()
                self._cursor.setBlockFormat(styles.block_format())
                self._cursor.setBlockCharFormat(styles.char_format(context))
                if c < len(row):
                    self._inline(row[c].children, context, 0, Flags())
        self._cursor = outside
        # Dopo la tabella Qt tiene sempre un paragrafo: è quello che riceverà il contenuto seguente.
        self._cursor.setPosition(table.lastPosition() + 1)
        self._cursor.setBlockFormat(styles.block_format())
        self._cursor.setBlockCharFormat(styles.char_format())
        self._fresh = True

    def _list(self, node: _Node, depth: int, box: tuple[str, int]) -> None:
        fmt = styles.list_format(node.tag, depth)
        current: QTextList | None = None
        for item in node.children:
            if isinstance(item, str) or item.tag != "li":
                continue
            lead = []                 # il testo della voce: tutto ciò che precede un eventuale elenco annidato
            rest = list(item.children)
            while rest and not (not isinstance(rest[0], str) and rest[0].tag in ("ul", "ol")):
                lead.append(rest.pop(0))
            if item.attrs.get("class") != "gap":     # le voci vuote vere si tengono; i contenitori «gap» no
                self._text_block(lead, 0, box)
                if current is None:
                    current = self._cursor.createList(fmt)
                else:
                    current.add(self._cursor.block())
            for nested in rest:
                if not isinstance(nested, str) and nested.tag in ("ul", "ol"):
                    self._list(nested, depth + 1, box)
                elif not isinstance(nested, str) or nested.strip():      # testo dopo l'elenco annidato: nuova voce
                    self._text_block([nested], 0, box)
                    if current is None:
                        current = self._cursor.createList(fmt)
                    else:
                        current.add(self._cursor.block())

    def _inline(self, nodes: list, context: str, heading: int, flags: Flags) -> None:
        for node in nodes:
            if isinstance(node, str):
                text = node.replace("\r", "").replace("\n", " ")
                if text:
                    self._cursor.insertText(text, styles.char_format(context, heading, flags))
                continue
            attrs, tag = node.attrs, node.tag
            if tag == "br":
                self._cursor.insertText(LINE_BREAK, styles.char_format(context, heading, flags))
            elif tag == "img":
                if context not in styles.TABLE_CONTEXTS:      # nelle celle niente immagini
                    self._image(attrs, context, heading, flags)
            else:
                inner = flags
                if tag in ("b", "strong"):
                    inner = replace(flags, bold=True)
                elif tag in ("i", "em"):
                    inner = replace(flags, italic=True)
                elif tag == "u":
                    inner = replace(flags, underline=True)
                elif tag == "span":
                    classes = (attrs.get("class") or "").split()
                    size = next((name for name in classes if name in styles.SIZES), flags.size)
                    color = next((name[3:] for name in classes if name[3:] in styles.HIGHLIGHTS and name.startswith("hl-")), flags.highlight)
                    inner = replace(flags, size=size, highlight=color)
                elif tag == "a" and attrs.get("href"):
                    inner = replace(flags, href=attrs["href"])
                self._inline(node.children, context, heading, inner)

    def _image(self, attrs: dict, context: str, heading: int, flags: Flags) -> None:
        src = attrs.get("src")
        if not src:
            return
        fmt = QTextImageFormat()
        fmt.merge(styles.char_format(context, heading, flags))
        fmt.setName(src)
        for key, setter in (("width", fmt.setWidth), ("height", fmt.setHeight)):
            if (attrs.get(key) or "").isdigit():
                setter(float(attrs[key]))
        self._cursor.insertImage(fmt)


def _rows(table: _Node):
    """Le righe <tr> di una tabella (anche dentro <thead>/<tbody>, che il programma non scrive ma potrebbe trovare)."""
    for child in table.children:
        if isinstance(child, str):
            continue
        if child.tag == "tr":
            yield child
        elif child.tag in ("thead", "tbody", "tfoot"):
            yield from _rows(child)


def _box_kind(node: _Node) -> str:
    """«voice» o «master» se il <div> è un box (class="box voice"), altrimenti stringa vuota."""
    classes = (node.attrs.get("class") or "").split()
    return next((kind for kind in styles.BOX_KINDS if "box" in classes and kind in classes), "")


def _encounter_id(node: _Node) -> int | None:
    """L'ID dell'incontro se il <div> è il box di un incontro (class="encounter" data-id="N"), altrimenti None."""
    found = node.attrs.get("data-id") or ""
    return int(found) if "encounter" in (node.attrs.get("class") or "").split() and found.isdigit() else None
