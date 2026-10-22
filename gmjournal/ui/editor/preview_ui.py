"""L'anteprima di un collegamento: il mouse si ferma mezzo secondo su un link e sotto la riga compare una finestrella con chi è.

Sparisce appena si fa altro (si scrive, si scorre, si clicca, il mouse esce dal testo o va su un altro link) e non ricompare finché
il mouse non lascia il link. La finestrella sta sopra la finestra intera, così non viene tagliata dai bordi dell'editor.
"""

from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit

from ...data import links
from ..widgets.link_preview import WIDTH, LinkPreviewCard, LinkPreviewData

PreviewSource = Callable[[str, int], LinkPreviewData | None]     # (tipo, ID) -> cosa mostrare (None = niente)
DELAY_MS = 500
_GAP = 8             # distanza dalla riga del link
_MARGIN = 8          # distanza minima dal bordo della finestra
_LEFT = 12           # la finestrella parte un po' prima dell'inizio del link


class LinkPreviewController(QObject):
    def __init__(self, editor: QTextEdit, source: PreviewSource):       # l'editor è un RichEditor
        super().__init__(editor)
        self._editor, self._source = editor, source
        self._card: LinkPreviewCard | None = None
        self._href = ""                  # il collegamento su cui si trova il mouse
        self._point = QPoint()
        self._timer = QTimer(self, singleShot=True, interval=DELAY_MS)
        self._timer.timeout.connect(self._show)
        editor.viewport().installEventFilter(self)
        editor.verticalScrollBar().valueChanged.connect(self.hide)

    @property
    def visible(self) -> bool:
        return self._card is not None and self._card.isVisible()

    def moved(self, point: QPoint, href: str) -> None:
        """Il mouse è su `point` (coordinate dell'area di testo), dove c'è il collegamento `href` (vuoto = nessuno)."""
        if href == self._href:
            return
        self._href, self._point = href, point
        self.hide()
        if href:
            self._timer.start()

    def hide(self) -> None:
        """Toglie la finestrella (se il mouse resta su questo link, non ricompare)."""
        self._timer.stop()
        if self._card is not None:
            self._card.hide()

    def leave(self) -> None:
        self._href = ""
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Leave:
            self.leave()
        return False

    def _show(self) -> None:
        target = links.parse_href(self._href)
        data = self._source(*target) if target is not None else None
        if data is None or not self._editor.isVisible():
            return
        window = self._editor.window()
        if self._card is None or self._card.parent() is not window:
            self._card = LinkPreviewCard(window)
        self._card.show_data(data)
        self._card.move(self._place(window))
        self._card.raise_()
        self._card.show()

    def _place(self, window) -> QPoint:
        """Sotto la riga del link, allineata al suo inizio; sopra se sotto non c'è posto; sempre dentro la finestra."""
        editor, card = self._editor, self._card
        under = editor.cursorRect(editor.cursorForPosition(self._point))
        x = under.left()
        found = editor.link_under(self._point)
        if found is not None:
            cursor = QTextCursor(editor.document())
            cursor.setPosition(found[0])
            start = editor.cursorRect(cursor)
            if start.top() == under.top():              # il link inizia su questa riga (altrimenti si parte dal mouse)
                x = start.left()
        top = editor.viewport().mapTo(window, QPoint(x - _LEFT, under.top())).y()
        left = editor.viewport().mapTo(window, QPoint(x - _LEFT, 0)).x()
        y = top + under.height() + _GAP
        if y + card.height() > window.height() - _MARGIN:
            y = top - _GAP - card.height()
        y = max(_MARGIN, min(y, window.height() - card.height() - _MARGIN))
        x = max(_MARGIN, min(left, window.width() - WIDTH - _MARGIN))
        return QPoint(x, y)
