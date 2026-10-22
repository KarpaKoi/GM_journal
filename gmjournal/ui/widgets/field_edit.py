"""Un campo di testo della scheda di un elemento: si legge come testo semplice e si scrive cliccandoci sopra.

Il testo può contenere collegamenti: li si crea scrivendo «@», e un clic su un collegamento apre l'elemento.
Si salva nello stesso formato delle pagine (paragrafi `<p>` e `<a href="gmj://tipo/ID">`), così l'indice dei
collegamenti e «Citato in» funzionano allo stesso modo per le pagine e per le schede.
"""

import html
from html.parser import HTMLParser

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import QFrame, QHBoxLayout, QTextEdit

from ... import theme
from ...data import links
from ...data.models import LinkTarget
from ...elements import Field
from ..editor.link_ui import MentionController
from ..editor.markup import LINE_BREAK
from ..link_sources import LinkSources

_PADDING = (12, 9)             # spazio fra il bordo e il testo quando il campo è un riquadro (vuoto o in modifica)
_LINE_HEIGHT = 150             # interlinea in %
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "li"}


# --- Testo salvato <-> documento ---------------------------------------------------------------
def _link_format(href: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setAnchor(True)
    fmt.setAnchorHref(href)
    fmt.setFontWeight(600)
    fmt.setFontUnderline(True)
    fmt.setForeground(QColor(theme.TEXT_ACTIVE))
    return fmt


class _Reader(HTMLParser):
    """Riempie un documento dal testo salvato: paragrafi, «a capo» e collegamenti (ogni altra formattazione si ignora)."""

    def __init__(self, cursor: QTextCursor):
        super().__init__()
        self._cursor, self._href, self._started = cursor, "", False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _BLOCK_TAGS:
            if self._started:
                self._cursor.insertBlock()
            self._started = True
        elif tag == "br":
            self._cursor.insertText(LINE_BREAK)
        elif tag == "a":
            self._href = dict(attrs).get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._href = ""

    def handle_data(self, data: str) -> None:
        self._cursor.insertText(data, _link_format(self._href) if self._href else QTextCharFormat())


def fill_document(doc: QTextDocument, content: str) -> None:
    doc.clear()
    doc.setDocumentMargin(0)
    reader = _Reader(QTextCursor(doc))
    reader.feed(content)
    reader.close()


def export_content(doc: QTextDocument) -> str:
    """Il testo del documento nel formato salvato; vuoto se non c'è altro che spazi."""
    if not doc.toPlainText().strip():
        return ""
    paragraphs = []
    block = doc.firstBlock()
    while block.isValid():
        parts, fragments = [], block.begin()
        while not fragments.atEnd():
            fragment = fragments.fragment()
            text = html.escape(fragment.text(), quote=False).replace(LINE_BREAK, "<br>")
            fmt = fragment.charFormat()
            parts.append(f'<a href="{html.escape(fmt.anchorHref(), quote=True)}">{text}</a>' if fmt.isAnchor() else text)
            fragments += 1
        paragraphs.append("".join(parts))
        block = block.next()
    while paragraphs and not paragraphs[-1]:      # i paragrafi vuoti in fondo non si salvano
        paragraphs.pop()
    return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)


# --- Il testo del campo ---------------------------------------------------------------------------
class _FieldText(QTextEdit):
    """L'area di testo: alta quanto il suo testo. Finché non si modifica è di sola lettura e un clic sul testo la apre."""

    editing_requested = Signal(object)    # QPoint: clic sul testo (non su un collegamento)
    link_clicked = Signal(str, int)
    stopped = Signal()                    # il campo ha perso il fuoco o si è premuto Esc

    def __init__(self, field: Field, sources: LinkSources):
        super().__init__()
        self.setObjectName("FieldText")
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self._hint = field.placeholder        # il suggerimento a campo vuoto (lo disegna paintEvent: quello di Qt non va a capo oltre la prima riga)
        self.setCursorWidth(2)
        self.viewport().setMouseTracking(True)
        self._editing = False
        self._press_href = ""
        self._loading = False

        font = theme.serif_font(16, 400) if field.quote else theme.ui_font(14)
        font.setItalic(field.quote)
        self.setFont(font)
        self.document().setDocumentMargin(0)
        self._sources = sources
        self._mention = MentionController(self, self.window, sources.targets, sources.create, self._insert_mention)
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self.cursorPositionChanged.connect(self._on_cursor_moved)
        self.set_editing(False)

    # --- Altezza --------------------------------------------------------------------------------
    def _fit(self, *_) -> None:
        height = max(round(self.document().size().height()), self.fontMetrics().lineSpacing())
        width = self.viewport().width()
        if self.document().isEmpty() and width > 40:      # il suggerimento va a capo come un testo: serve lo spazio di tutte le sue righe
            height = max(height, self.fontMetrics().boundingRect(0, 0, width, 0, Qt.TextWordWrap, self._hint).height())
        if height != self.height():
            self.setFixedHeight(height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.document().isEmpty():
            painter = QPainter(self.viewport())
            painter.setFont(self.font())
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(self.viewport().rect(), Qt.AlignTop | Qt.TextWordWrap, self._hint)

    # --- Contenuto ------------------------------------------------------------------------------
    def set_content(self, content: str) -> None:
        self._loading = True
        try:
            fill_document(self.document(), content)
            cursor = QTextCursor(self.document())
            cursor.select(QTextCursor.Document)
            block_format = QTextBlockFormat()
            block_format.setLineHeight(_LINE_HEIGHT, QTextBlockFormat.ProportionalHeight.value)
            cursor.mergeBlockFormat(block_format)
            self.document().clearUndoRedoStacks()
            self.document().setModified(False)
        finally:
            self._loading = False
        self._fit()

    def content(self) -> str:
        return export_content(self.document())

    def is_empty(self) -> bool:
        return not self.document().toPlainText().strip()

    @property
    def loading(self) -> bool:
        return self._loading

    # --- Lettura e scrittura ----------------------------------------------------------------------
    def set_editing(self, editing: bool) -> None:
        self._editing = editing
        self.setReadOnly(not editing)
        self.setTextInteractionFlags(Qt.TextEditorInteraction if editing else Qt.LinksAccessibleByMouse)
        if not editing:
            self._mention.close()
        self.viewport().unsetCursor()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        over_link = bool(self.anchorAt(event.position().toPoint()))
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        self.viewport().setCursor(Qt.PointingHandCursor if over_link and (ctrl or not self._editing)
                                  else Qt.IBeamCursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        point = event.position().toPoint()
        self._press_href = self.anchorAt(point) if event.button() == Qt.LeftButton else ""
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
        elif not self._editing:
            if not self._press_href:
                self.editing_requested.emit(point)
        elif not (self._press_href and event.modifiers() & Qt.ControlModifier):
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        href, self._press_href = self._press_href, ""
        opens = href and self.anchorAt(event.position().toPoint()) == href and (not self._editing or event.modifiers() & Qt.ControlModifier)
        target = links.parse_href(href) if opens else None
        if target is not None:
            self.link_clicked.emit(*target)
            return
        super().mouseReleaseEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if not self._editing and event.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason):
            self.editing_requested.emit(None)      # arrivato con la tastiera: si scrive subito

    def focusOutEvent(self, event) -> None:
        self._mention.close()
        super().focusOutEvent(event)
        if self._editing:
            self.stopped.emit()

    def keyPressEvent(self, event) -> None:
        if self._mention.active and self._mention.handle_key(event):
            return
        if event.key() == Qt.Key_Escape:
            self.stopped.emit()
            return
        super().keyPressEvent(event)
        if event.text() == "@":
            self._mention.typed_at_sign()

    # --- Testo incollato e collegamenti ------------------------------------------------------------
    def canInsertFromMimeData(self, source) -> bool:
        return source.hasText()

    def insertFromMimeData(self, source) -> None:
        self.insertPlainText(source.text().replace("\r\n", "\n").replace("\r", "\n"))

    def _insert_mention(self, target: LinkTarget, start: int, end: int) -> None:
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(target.name, _link_format(links.make_href(target.kind, target.id)))
        self.setTextCursor(cursor)
        self.setCurrentCharFormat(QTextCharFormat())

    def _on_cursor_moved(self) -> None:
        if self._loading:
            return
        self._keep_typing_outside_link()
        self._mention.refresh()

    def _keep_typing_outside_link(self) -> None:
        """Quello che si scrive subito prima o dopo un link non ne fa parte: solo dentro il link lo allunga."""
        cursor = self.textCursor()
        if cursor.hasSelection() or not self.currentCharFormat().isAnchor():
            return
        block, position, inside = cursor.block(), cursor.position(), False
        if position < block.position() + block.length() - 1:          # dopo il cursore c'è ancora una lettera, nella stessa riga
            after = QTextCursor(self.document())
            after.setPosition(position + 1)
            inside = after.charFormat().isAnchor() and after.charFormat().anchorHref() == self.currentCharFormat().anchorHref()
        if not inside:
            self.setCurrentCharFormat(QTextCharFormat())


# --- Il campo --------------------------------------------------------------------------------------
class FieldEdit(QFrame):
    """Il testo con, sopra, la sua etichetta (la mette chi lo usa). Tre aspetti: testo semplice (pieno), riquadro
    tratteggiato con il suggerimento (vuoto), riquadro con il bordo colorato (in modifica)."""

    edited = Signal()                      # il testo è cambiato
    stopped = Signal()                     # si è finito di scrivere: il campo ha perso il fuoco
    link_activated = Signal(str, int)      # clic su un collegamento: (tipo, ID)

    def __init__(self, field: Field, sources: LinkSources):
        super().__init__()
        self._text = _FieldText(field, sources)
        self._text.editing_requested.connect(self._start_editing)
        self._text.stopped.connect(self._stop_editing)
        self._text.link_clicked.connect(self.link_activated)
        self._text.textChanged.connect(self._on_text_changed)
        self._layout = QHBoxLayout(self)
        self._layout.addWidget(self._text)
        self._editing = False
        self._refresh()

    def content(self) -> str:
        return self._text.content()

    def set_content(self, content: str) -> None:
        self._text.set_content(content)
        self._refresh()

    def _on_text_changed(self) -> None:
        if not self._text.loading:
            self.edited.emit()

    def _start_editing(self, point) -> None:
        self._editing = True
        self._text.set_editing(True)
        self._text.setFocus()
        if point is not None:
            self._text.setTextCursor(self._text.cursorForPosition(point))
        else:
            self._text.moveCursor(QTextCursor.End)
        self._refresh()

    def _stop_editing(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self._text.set_editing(False)
        self._text.clearFocus()
        self._refresh()
        self.stopped.emit()

    def _refresh(self) -> None:
        boxed = self._editing or self._text.is_empty()
        left, top = _PADDING if boxed else (0, 0)
        self._layout.setContentsMargins(left, top, left, top)
        self.update()

    def paintEvent(self, event) -> None:
        if not (self._editing or self._text.is_empty()):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._editing:
            painter.setBrush(QColor(theme.BG))
            painter.setPen(QPen(QColor(theme.ACCENT), 1))
        else:
            painter.setBrush(Qt.NoBrush)
            pen = QPen(QColor(theme.DISABLED), 1)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.MouseButtonPress and not self._editing and self._text.is_empty():
            self._start_editing(None)      # clic nella cornice tratteggiata (fuori dal testo)
            return True
        return super().event(event)
