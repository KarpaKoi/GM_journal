"""Popup per scegliere le schede tecniche da aggiungere a un incontro (una o più)."""

from PySide6.QtWidgets import QDialog, QLabel, QWidget

from ...data.models import CreatureRow
from ..creature_items import creature_item, matches
from ..widgets.item_list import DISABLED, MARKED, ItemList
from ..widgets.search_field import SearchField
from .base import PopupDialog, note

_LIST_HEIGHT = 360


class CreaturePickerPopup(PopupDialog):
    """`taken`: gli ID delle schede già nell'incontro (si vedono, ma non si scelgono di nuovo)."""

    def __init__(self, parent: QWidget, rows: list[CreatureRow], taken: set[int]):
        super().__init__(parent, "Aggiungi schede", "Tocca le schede che servono a questo incontro: puoi sceglierne più d'una.", "Aggiungi", width=640)
        self._rows = rows
        self._taken = taken
        self._marked: list[int] = []        # nell'ordine in cui sono state scelte
        self._search = SearchField("SearchBox", "Cerca per nome, tipo o fonte")
        self._search.edited.connect(self._refresh)
        self._list = ItemList()
        self._list.setFixedHeight(_LIST_HEIGHT)
        self._list.chosen.connect(self._toggle)
        self._none = QLabel("Nessuna scheda corrisponde.")
        self._none.setObjectName("Muted")
        if rows:
            self.body.setSpacing(12)
            self.body.addWidget(self._search)
            self.body.addWidget(self._list)
            self.body.addWidget(self._none)
            self._search.focus()
        else:
            self.body.addWidget(note("Non ci sono ancora schede tecniche. Compilale a mano o importale da un file XML dalla pagina «Schede tecniche»."))
        self._refresh()

    def _refresh(self) -> None:
        shown = [row for row in self._rows if matches(row, self._search.text())]
        self._list.set_items([creature_item(row, DISABLED if row.id in self._taken else MARKED if row.id in self._marked else "",
                                            "già nell'incontro" if row.id in self._taken else "") for row in shown], None)
        self._none.setVisible(bool(self._rows) and not shown)
        self._list.setVisible(bool(shown))
        self._update_button()

    def _update_button(self) -> None:
        count = len(self._marked)
        self.set_primary_enabled(bool(count))
        self.set_primary_text("Aggiungi" if not count else "Aggiungi 1 scheda" if count == 1 else f"Aggiungi {count} schede")

    def _toggle(self, creature_id: int) -> None:
        if creature_id in self._marked:
            self._marked.remove(creature_id)
        else:
            self._marked.append(creature_id)
        self._list.set_state(creature_id, MARKED if creature_id in self._marked else "")
        self._update_button()

    def chosen(self) -> list[int]:
        return list(self._marked)


def pick_creatures(parent: QWidget, rows: list[CreatureRow], taken: set[int]) -> list[int]:
    """Fa scegliere le schede da aggiungere. Restituisce i loro ID nell'ordine di scelta (vuoto se si annulla)."""
    popup = CreaturePickerPopup(parent, rows, taken)
    return popup.chosen() if popup.exec() == QDialog.Accepted else []
