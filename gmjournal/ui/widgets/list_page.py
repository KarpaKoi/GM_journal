"""Una pagina «elenco con ricerca, dettaglio a destra»: la base delle schede tecniche e degli incontri.

Chi la usa dice come leggere le voci (`_read`), come mostrarle in elenco (`_item`), come si cercano (`_matches`) e che cosa far
vedere a destra (`_show_selected`); qui ci sono il resto: ricerca, scelta, schermata vuota, cronologia.
L'elenco sta a sinistra della pagina oppure, se la pagina è `docked`, lo mette dove vuole chi la usa (la barra sinistra dell'app).
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from ... import icons, theme
from .empty_state import EmptyState
from .item_list import ItemList, ListItem
from .search_field import SearchField

_LIST_WIDTH = 380
_LISTING, _EMPTY = 0, 1             # cosa si vede: l'elenco con il dettaglio, oppure l'invito a creare la prima voce
_RESULTS, _NO_MATCH = 0, 1          # a sinistra: l'elenco, oppure «nessuna voce corrisponde»


def action_button(label: str, icon: str, color: str | None = None) -> QPushButton:
    """Un pulsante dell'intestazione: pieno nel colore della sezione se `color` c'è, altrimenti normale."""
    button = QPushButton(f" {label}")
    button.setIcon(icons.icon(icon, theme.BG if color else theme.TEXT))
    button.setIconSize(QSize(18, 18))
    button.setFixedHeight(38)
    button.setCursor(Qt.PointingHandCursor)
    if color:
        button.setStyleSheet(theme.solid_button_style(color))
    return button


class ListPage(QWidget):
    navigated = Signal(object)      # l'utente ha scelto (o creato, o eliminato) una voce: l'ID, o None se non c'è più nulla di scelto
    changed = Signal()              # una voce è stata creata, modificata o eliminata

    def __init__(self, detail: QWidget, search_hint: str, no_match: str, empty: EmptyState, docked: bool = False):
        """`docked`: l'elenco (senza ricerca) non sta nella pagina ma in `left`, da mettere dove si vuole."""
        super().__init__()
        self._rows: list = []
        self._selected: int | None = None
        self.buttons = QWidget()        # i pulsanti dell'intestazione, a cura di chi usa la pagina
        QHBoxLayout(self.buttons).setContentsMargins(0, 0, 0, 0)
        self.buttons.layout().setSpacing(12)
        self.buttons.layout().addStretch()          # i pulsanti restano della loro misura: senza, l'unico pulsante si allarga quanto la pagina più larga

        self._search = SearchField("SearchBox", search_hint)
        self._search.edited.connect(self._filter)
        self._list = ItemList()
        self._list.chosen.connect(self._choose)
        none = QLabel(no_match)
        none.setObjectName("Muted")
        none.setAlignment(Qt.AlignCenter)
        self._results = QStackedWidget()
        self._results.addWidget(self._list)         # _RESULTS
        self._results.addWidget(none)               # _NO_MATCH
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        column.addWidget(self._search)
        column.addWidget(self._results, 1)
        self.left = QWidget()           # l'elenco con la sua ricerca
        self.left.setLayout(column)

        self._detail = detail
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(24)
        if docked:
            self._search.hide()         # in una barra stretta non c'è posto per la ricerca: il campo resta vuoto
        else:
            self.left.setFixedWidth(_LIST_WIDTH)
            body.addWidget(self.left)
        body.addWidget(detail, 1)
        listing = QWidget()
        listing.setLayout(body)
        self._empty = empty
        self._views = QStackedWidget()
        self._views.addWidget(listing)      # _LISTING
        self._views.addWidget(empty)        # _EMPTY
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._views)

    # --- Da definire ---------------------------------------------------------------------------
    def _read(self) -> list:
        """Rilegge le voci dal database (ognuna ha un `id`), nell'ordine in cui si mostrano."""
        raise NotImplementedError

    def _item(self, row) -> ListItem:
        raise NotImplementedError

    def _matches(self, row, query: str) -> bool:
        """Se la voce corrisponde alla ricerca; chi ha la ricerca nella pagina lo dice, le altre mostrano tutto."""
        return True

    def _show_selected(self) -> None:
        """Mostra a destra la voce scelta (`self._selected`), o il suggerimento se non c'è."""
        raise NotImplementedError

    # --- Posizione e contenuto -------------------------------------------------------------------
    def current_id(self) -> int | None:
        return self._selected

    def has(self, item_id: int) -> bool:
        return any(row.id == item_id for row in self._rows)

    def show_id(self, item_id: int | None) -> None:
        """Mostra la voce con questo ID; senza ID (o se non c'è più) non ce n'è nessuna scelta."""
        self._selected = item_id if item_id is not None and self.has(item_id) else None
        self._list.select(self._selected)
        self._show_selected()

    def unmark(self) -> None:
        """Toglie l'evidenziazione dall'elenco (la voce scelta resta): serve quando l'elenco si vede ma la pagina no."""
        self._list.select(None)

    def reload(self) -> None:
        """Rilegge le voci e ridisegna elenco e dettaglio."""
        self._rows = self._read()
        if self._selected not in {row.id for row in self._rows}:
            self._selected = None
        self._views.setCurrentIndex(_LISTING if self._rows else _EMPTY)
        self._filter()
        self._show_selected()

    def _filter(self) -> None:
        query = self._search.text()
        shown = [row for row in self._rows if self._matches(row, query)]
        self._list.set_items([self._item(row) for row in shown], self._selected)
        self._results.setCurrentIndex(_RESULTS if shown or not self._rows else _NO_MATCH)

    def _choose(self, item_id: int) -> None:
        """L'utente ha scelto una voce dall'elenco: va nella cronologia (anche la voce già scelta, se la pagina non si vede)."""
        if item_id != self._selected or not self.isVisibleTo(self.window()):
            self.show_id(item_id)
            self.navigated.emit(item_id)

    # --- Dopo aver creato o modificato ---------------------------------------------------------------
    def _created(self, item_id: int | None) -> None:
        """La voce appena creata (None se annullato) si sceglie e si mostra."""
        if item_id is not None:
            self._search.clear()
            self._selected = item_id
            self.reload()
            self.navigated.emit(item_id)
            self.changed.emit()

    def _edited(self, deleted: bool) -> None:
        self.reload()
        if deleted:
            self.navigated.emit(None)
        self.changed.emit()
