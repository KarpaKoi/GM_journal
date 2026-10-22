"""Aspetto del testo nell'editor: l'unico posto dove si decide come appare un titolo, un paragrafo, un box.

Il testo salvato descrive solo la struttura (titolo 2, grassetto, box «Nota del Master»…): è questo modulo
a trasformarla in formati Qt, e a riportare i formati alla struttura quando si salva.
"""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QFont, QTextBlock, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QTextImageFormat,
    QTextLength, QTextListFormat, QTextTable, QTextTableFormat,
)

from ... import theme

# Proprietà aggiunte ai paragrafi: i paragrafi di un box portano il tipo (voice/master) e il numero del box.
BOX_KIND = QTextFormat.UserProperty + 1
BOX_ID = QTextFormat.UserProperty + 2
HIGHLIGHT = QTextFormat.UserProperty + 3      # sui caratteri: il colore dell'evidenziatore («sabbia», «verde»…)
ENCOUNTER_SCHEME = "gmj-encounter:"           # il box Incontro nel documento è un'immagine con questo nome (seguito dall'ID), disegnata da encounter_box.py

BODY = "body"                 # testo fuori dai box; dentro un box il contesto è il tipo del box
HEAD, CELL = "head", "cell"   # dentro una tabella: la prima riga (intestazione) e le altre
TABLE_CONTEXTS = (HEAD, CELL)
HIGHLIGHTS = tuple(theme.HIGHLIGHT_COLORS)    # i colori dell'evidenziatore, nell'ordine in cui si scelgono
_HIGHLIGHT_ALPHA = 0.26       # il colore sotto il testo evidenziato è trasparente: il testo resta del suo colore
BOX_KINDS = tuple(theme.BOX_COLORS)   # "voice" (Da leggere a voce) e "master" (Nota del Master)
BOX_LABELS = {"voice": "Da leggere a voce", "master": "Nota del Master"}
BOX_ICONS = {"voice": "message-square", "master": "sticky-note"}
SIZES = ("sm", "md", "lg")    # piccolo, medio (predefinito), grande
_SIZE_PX = {"body": (15, 18, 22), "voice": (14, 17, 21), "master": (12, 14, 17)}
_HEADING_PX = {1: 36, 2: 28, 3: 22}
_HEADING_MARGINS = {1: (28, 12), 2: (24, 8), 3: (18, 6)}   # sopra, sotto
_HEADING_LINE = {1: 120, 2: 120, 3: 125}                    # interlinea in %
IMAGE_CHAR = "\ufffc"   # nel testo di un paragrafo, il posto occupato da un'immagine
_BODY_LINE = 168
_BOX_LINE = 160
_PARAGRAPH_GAP, _LIST_GAP, _BOX_INNER_GAP = 12, 4, 6

# Geometria dei box (pixel): disegnati dall'editor, qui servono per lasciare lo spazio giusto.
BOX_PAD_X = 18
BOX_PAD_TOP = 14
BOX_LABEL_HEIGHT = 15
BOX_LABEL_GAP = 6
BOX_PAD_BOTTOM = 16
BOX_GAP_ABOVE = 18
BOX_GAP_BELOW = 14
BOX_RADIUS = 10
BOX_HEADER = BOX_PAD_TOP + BOX_LABEL_HEIGHT + BOX_LABEL_GAP   # dall'alto del box al primo rigo di testo

# Tabelle: misure delle celle e del riquadro (bordi e intestazione li disegna l'editor).
TABLE_PAD_Y = 8               # spazio sopra e sotto il testo di una cella
TABLE_PAD_X = 14              # spazio ai lati
TABLE_RADIUS = 10
TABLE_GAP_ABOVE = 6
TABLE_GAP_BELOW = 32          # c'è anche il «+» per aggiungere una riga
_CELL_LINE = 120          # Qt mette lo spazio dell'interlinea sotto la riga: poco, o il testo non sta al centro

LIST_INDENT_PX = 24
MAX_LIST_DEPTH = 3            # quanti livelli si possono creare con i comandi (il testo salvato non ha limiti)

_STYLE = QTextListFormat.Style
# Simbolo di ogni livello: puntato (disco, cerchio, quadrato) o numerato (1. a. i.)
_LIST_STYLES = {"ul": (_STYLE.ListDisc, _STYLE.ListCircle, _STYLE.ListSquare),
                "ol": (_STYLE.ListDecimal, _STYLE.ListLowerAlpha, _STYLE.ListLowerRoman)}


@dataclass(frozen=True)
class Flags:
    """La struttura di un pezzo di testo, come viene salvata."""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    size: str = "md"
    href: str = ""
    highlight: str = ""       # colore dell'evidenziatore (una chiave di HIGHLIGHTS), "" = nessuno


# --- Caratteri --------------------------------------------------------------------------
def char_format(context: str = BODY, heading: int = 0, flags: Flags = Flags()) -> QTextCharFormat:
    """Il formato Qt di un pezzo di testo nel `context` (BODY, tipo di box o cella di tabella) e, se titolo, di livello `heading`."""
    bold = flags.bold or bool(flags.href)         # un link è sempre in grassetto e sottolineato
    underline = flags.underline or bool(flags.href)
    if heading:
        font, color = theme.serif_font(_HEADING_PX[heading], 600 if bold else 500), theme.TEXT_ACTIVE
    elif context == HEAD:                         # intestazione: sempre piccola, in maiuscolo e in grassetto
        font, color = theme.ui_font(12, 600, 0.06), theme.MUTED
        font.setCapitalization(QFont.AllUppercase)
    elif context == CELL:
        font, color = theme.ui_font(14, 600 if bold else 400), theme.TEXT
    else:
        px = _SIZE_PX[context][SIZES.index(flags.size)]
        if context == "master":
            font = theme.ui_font(px, 600 if bold else 400)
        else:
            font = theme.serif_font(px, 600 if bold else 400)
        color = theme.BOX_COLORS[context][2] if context != BODY else theme.EDITOR_TEXT
    if flags.href:
        color = theme.TEXT_ACTIVE
    font.setItalic(flags.italic)
    font.setUnderline(underline)
    fmt = QTextCharFormat()
    fmt.setFont(font)
    fmt.setForeground(QColor(color))
    if flags.href:
        fmt.setAnchor(True)
        fmt.setAnchorHref(flags.href)
    if flags.highlight in theme.HIGHLIGHT_COLORS:
        fmt.setProperty(HIGHLIGHT, flags.highlight)
        fmt.setBackground(theme.tint(theme.HIGHLIGHT_COLORS[flags.highlight][1], _HIGHLIGHT_ALPHA))
    return fmt


def flags_of(fmt: QTextCharFormat, context: str = BODY, heading: int = 0) -> Flags:
    """La struttura di un formato Qt (l'inverso di `char_format`)."""
    size = "md"
    if not heading and context not in TABLE_CONTEXTS:     # nelle tabelle il testo ha una sola dimensione
        px = fmt.font().pixelSize()
        sizes = _SIZE_PX[context]
        size = SIZES[sizes.index(px)] if px in sizes else "md"
    highlight = fmt.stringProperty(HIGHLIGHT)
    return Flags(
        # L'intestazione è sempre in grassetto (e in maiuscolo): non è una scelta, nemmeno se la riga smette di esserlo.
        bold=fmt.fontWeight() >= 600 and context != HEAD and fmt.font().capitalization() != QFont.AllUppercase,
        italic=fmt.fontItalic(),
        underline=fmt.fontUnderline() and not fmt.isAnchor(),
        size=size,
        href=fmt.anchorHref() if fmt.isAnchor() else "",
        highlight=highlight if highlight in theme.HIGHLIGHT_COLORS else "",
    )


def encounter_format(encounter_id: int) -> QTextImageFormat:
    """Il formato del carattere che nel testo rappresenta il box di un incontro: un'immagine di cui l'editor fornisce il disegno."""
    fmt = QTextImageFormat()
    fmt.merge(char_format())
    fmt.setName(f"{ENCOUNTER_SCHEME}{encounter_id}")
    return fmt


def encounter_id(fmt: QTextCharFormat) -> int | None:
    """L'ID dell'incontro se il formato è quello di un box Incontro, altrimenti None."""
    if fmt.isImageFormat() and fmt.toImageFormat().name().startswith(ENCOUNTER_SCHEME):
        return int(fmt.toImageFormat().name().removeprefix(ENCOUNTER_SCHEME))
    return None


def encounter_in(block: QTextBlock) -> int | None:
    """L'ID dell'incontro mostrato dal paragrafo (che di solito contiene solo il suo box), None se non ne ha."""
    it = block.begin()
    while not it.atEnd():
        found = encounter_id(it.fragment().charFormat())
        if found is not None:
            return found
        it += 1
    return None


def fragments(block: QTextBlock) -> list[tuple[int, int, QTextCharFormat]]:
    """(inizio, fine, formato) dei pezzi di testo del paragrafo, immagini (e box Incontro) esclusi."""
    pieces = []
    it = block.begin()
    while not it.atEnd():
        fragment = it.fragment()
        if not fragment.charFormat().isImageFormat():
            pieces.append((fragment.position(), fragment.position() + fragment.length(), fragment.charFormat()))
        it += 1
    return pieces


def same_look(a: QTextCharFormat, b: QTextCharFormat) -> bool:
    """Due formati si vedono allo stesso modo? (carattere, corpo, peso, corsivo, sottolineato, maiuscole, colore, link, evidenziatore)"""
    def look(fmt: QTextCharFormat):
        font = fmt.font()
        background = fmt.background().color().rgba() if fmt.hasProperty(QTextFormat.BackgroundBrush) else None
        return (font.families(), font.pixelSize(), font.weight(), font.italic(), font.underline(), font.capitalization(),
                fmt.foreground().color().rgba(), fmt.anchorHref() if fmt.isAnchor() else None, background)
    return look(a) == look(b)


def default_box_flags(box_kind: str) -> Flags:
    """Come appare di base il testo in un box: «Da leggere a voce» è in corsivo."""
    return Flags(italic=box_kind == "voice")


# --- Elenchi ------------------------------------------------------------------------------
def list_format(kind: str, depth: int) -> QTextListFormat:
    """Formato di un elenco puntato ("ul") o numerato ("ol") al livello `depth` (1 = primo livello)."""
    styles = _LIST_STYLES[kind]
    fmt = QTextListFormat()
    fmt.setStyle(styles[(depth - 1) % len(styles)])
    fmt.setIndent(depth)
    return fmt


def list_kind(fmt: QTextListFormat) -> str:
    """"ul" o "ol": il tipo di elenco descritto da un formato (l'inverso di `list_format`)."""
    return "ol" if fmt.style() in _LIST_STYLES["ol"] else "ul"


# --- Paragrafi ----------------------------------------------------------------------------
def block_format(heading: int = 0, box_kind: str = "", box_id: int = 0) -> QTextBlockFormat:
    """Formato di un paragrafo con la sua natura; margini e interlinea li sistema `apply_layout`."""
    fmt = QTextBlockFormat()
    fmt.setHeadingLevel(heading)
    if box_kind:
        fmt.setProperty(BOX_KIND, box_kind)
        fmt.setProperty(BOX_ID, box_id)
    return fmt


def heading_of(block: QTextBlock) -> int:
    return block.blockFormat().headingLevel()


def box_of(block: QTextBlock) -> tuple[str, int]:
    """(tipo, numero) del box a cui appartiene il paragrafo; ("", 0) se è fuori da ogni box."""
    fmt = block.blockFormat()
    return fmt.stringProperty(BOX_KIND), fmt.intProperty(BOX_ID)


def table_of(block: QTextBlock) -> QTextTable | None:
    """La tabella che contiene il paragrafo (None se non è in una cella)."""
    return QTextCursor(block).currentTable() if block.isValid() else None


def context_of(block: QTextBlock) -> str:
    table = table_of(block)
    if table is not None:
        return HEAD if table.cellAt(block.position()).row() == 0 else CELL
    return box_of(block)[0] or BODY


def table_format() -> QTextTableFormat:
    """Il formato di ogni tabella: larga quanto la colonna di testo, senza bordi di Qt (li disegna l'editor)."""
    fmt = QTextTableFormat()
    fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
    fmt.setBorder(0)
    fmt.setCellSpacing(0)
    fmt.setCellPadding(TABLE_PAD_Y)
    fmt.setTopMargin(TABLE_GAP_ABOVE)
    fmt.setBottomMargin(TABLE_GAP_BELOW)
    fmt.setHeaderRowCount(1)
    fmt.setAlignment(Qt.AlignLeft)
    return fmt


def block_flags(block: QTextBlock) -> tuple[str, int]:
    """(contesto, titolo) del paragrafo: servono per tradurre i suoi formati di carattere."""
    return context_of(block), heading_of(block)


def apply_layout(doc: QTextDocument, start: int = 0, end: int | None = None) -> int:
    """Porta margini e interlinea di ogni paragrafo a ciò che prevede la sua natura (titolo, elenco, box,
    primo o ultimo di un box). Con `start` e `end` (posizioni nel testo) si limita a quella zona più i
    paragrafi vicini, da cui il risultato dipende. Restituisce quanti paragrafi ha modificato."""
    first, last = block_range(doc, start, end)
    changed = 0
    block = first
    while block.isValid():
        wanted = _wanted_layout(block)
        if IMAGE_CHAR in block.text():        # l'interlinea del testo moltiplicherebbe l'altezza dell'immagine
            wanted = (*wanted[:4], 100.0, wanted[5])
        fmt = block.blockFormat()
        current = (fmt.topMargin(), fmt.bottomMargin(), fmt.leftMargin(), fmt.rightMargin(), fmt.lineHeight(), fmt.indent())
        if current != wanted:
            top, bottom, left, right, line, indent = wanted
            new = QTextBlockFormat(fmt)
            new.setTopMargin(top)
            new.setBottomMargin(bottom)
            new.setLeftMargin(left)
            new.setRightMargin(right)
            new.setLineHeight(line, QTextBlockFormat.ProportionalHeight.value)
            new.setIndent(int(indent))
            QTextCursor(block).setBlockFormat(new)
            changed += 1
        if block == last:
            break
        block = block.next()
    return changed


def block_range(doc: QTextDocument, start: int = 0, end: int | None = None) -> tuple[QTextBlock, QTextBlock]:
    """Primo e ultimo paragrafo da controllare dopo una modifica fra le posizioni `start` e `end`:
    quelli toccati più un vicino per parte. Senza `end`: tutto il documento."""
    if end is None:
        return doc.firstBlock(), doc.lastBlock()
    top = doc.characterCount() - 1
    first = doc.findBlock(max(0, min(start, top)))
    last = doc.findBlock(max(0, min(end, top)))
    return (first.previous() if first.previous().isValid() else first,
            last.next() if last.next().isValid() else last)


def _wanted_layout(block: QTextBlock) -> tuple[float, float, float, float, float, float]:
    """(sopra, sotto, sinistra, destra, interlinea %, rientro) voluti per il paragrafo."""
    if table_of(block) is not None:     # cella: il resto dello spazio ai lati è il margine della cella stessa
        side = float(TABLE_PAD_X - TABLE_PAD_Y)
        return 0.0, 0.0, side, side, float(_CELL_LINE), 0.0
    box = box_of(block)
    heading = heading_of(block)
    prev, following = block.previous(), block.next()
    first = not (prev.isValid() and box_of(prev) == box)
    last = not (following.isValid() and box_of(following) == box)
    if heading:
        top, bottom = _HEADING_MARGINS[heading]
        return float(top), float(bottom), 0.0, 0.0, float(_HEADING_LINE[heading]), 0.0
    next_is_item = (block.textList() is not None and following.isValid()
                    and following.textList() is not None and box_of(following) == box)
    top, bottom = 0, _LIST_GAP if next_is_item else (_BOX_INNER_GAP if box[0] else _PARAGRAPH_GAP)
    if not box[0]:
        return float(top), float(bottom), 0.0, 0.0, float(_BODY_LINE), 0.0
    if first:
        top = BOX_GAP_ABOVE + BOX_HEADER
        if prev.isValid() and box_of(prev)[0]:
            top += BOX_PAD_BOTTOM      # Qt tiene il margine maggiore fra due paragrafi, non la somma: qui serve la somma
    if last:
        bottom = BOX_PAD_BOTTOM + BOX_GAP_BELOW
    return float(top), float(bottom), float(BOX_PAD_X), float(BOX_PAD_X), float(_BOX_LINE), 0.0
