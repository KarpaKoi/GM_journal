"""Le schede tecniche di mostri e PNG: elenco con ricerca a sinistra, la scheda scelta a destra.

Le schede si compilano a mano o si importano da file XML (anche più d'uno alla volta). La pagina non tocca il database: legge e
scrive solo tramite il `Repository`.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from ... import theme
from ...data.compendium import LARGE_FILE, read_compendium
from ...data.db import DatabaseError
from ...data.models import CreatureRow
from ...data.repository import Repository
from ..creature_files import choose_compendium_files, confirm_large_file, import_summary
from ..creature_items import creature_item, matches
from ..popups.base import DELETE
from ..popups.creature import create_creature, edit_creature
from .creature_detail import CreatureDetail
from .empty_state import EmptyState
from .item_list import ListItem
from .list_page import ListPage, action_button

_COLOR = theme.SECTION_COLORS["incontri"]


class CreaturePage(ListPage):
    def __init__(self, repo: Repository):
        detail = CreatureDetail("Scegli una scheda per vederla.")
        empty = EmptyState("swords", _COLOR, "Nessuna scheda tecnica", "Qui tieni i mostri e i PNG dei tuoi incontri. Compila una scheda a mano "
                           "oppure importa un file XML di schede (Fight Club, Game Master 5e).", "Crea la prima scheda")
        super().__init__(detail, "Cerca per nome, tipo o fonte", "Nessuna scheda corrisponde.", empty)
        self._repo = repo
        detail.edit_requested.connect(self._edit)
        empty.clicked.connect(self._create)
        import_button = action_button("Importa schede…", "upload")
        import_button.setToolTip("Aggiunge le schede contenute in uno o più file XML")
        import_button.clicked.connect(self._import)
        add = action_button("Nuova scheda", "plus", _COLOR)
        add.clicked.connect(self._create)
        self.buttons.layout().addWidget(import_button)
        self.buttons.layout().addWidget(add)

    def _read(self) -> list[CreatureRow]:
        return self._repo.creatures()

    def _item(self, row: CreatureRow) -> ListItem:
        return creature_item(row)

    def _matches(self, row: CreatureRow, query: str) -> bool:
        return matches(row, query)

    def _show_selected(self) -> None:
        self._detail.show_creature(self._repo.creature(self._selected) if self._selected is not None else None)

    # --- Creare, modificare, importare ---------------------------------------------------------
    def _create(self) -> None:
        self._created(create_creature(self, self._repo))

    def _edit(self) -> None:
        if self._selected is not None:
            self._edited(edit_creature(self, self._repo, self._repo.creature(self._selected)) == DELETE)

    def _import(self) -> None:
        added = skipped = 0
        for path in choose_compendium_files(self):
            try:
                items = read_compendium(path)
                if len(items) >= LARGE_FILE and not confirm_large_file(self, path.name, len(items)):
                    continue
                QApplication.setOverrideCursor(Qt.WaitCursor)
                try:
                    result = self._repo.import_creatures(items)
                finally:
                    QApplication.restoreOverrideCursor()
            except DatabaseError as error:
                QMessageBox.warning(self, "GM Journal", str(error))
                continue
            added, skipped = added + result.added, skipped + result.skipped
        if added or skipped:
            self.reload()
            QMessageBox.information(self, "GM Journal", import_summary(added, skipped))
