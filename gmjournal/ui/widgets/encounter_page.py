"""Gli incontri: l'elenco sta nella barra sinistra dell'app (vedi `left`); nella pagina, finché nessun incontro è scelto, c'è la schermata
iniziale con l'elenco di tutti, poi l'incontro scelto con la sua difficoltà e le schede tecniche che servono."""

from PySide6.QtWidgets import QStackedWidget

from ... import theme
from ...data.models import Encounter
from ...data.repository import Repository
from ...dnd import DIFFICULTY_LABELS
from ...encounters import COMBAT, KIND_LABELS
from ..popups.base import DELETE
from ..popups.encounter import create_encounter, edit_encounter
from .difficulty_panel import assessment_of
from .empty_state import EmptyState
from .encounter_detail import EncounterDetail
from .encounter_home import EncounterHome, EncounterLine
from .item_list import ListItem
from .list_page import ListPage, action_button

_COLOR = theme.SECTION_COLORS["incontri"]


def creatures_text(row: Encounter) -> str:
    count = sum(slot.quantity for slot in row.creatures)
    return f"{count} creatur{'a' if count == 1 else 'e'}" if count else "nessuna scheda"


def players_text(row: Encounter) -> str:
    """«4 giocatori · liv. 3», «5 giocatori · liv. 3–4»."""
    players = sum(group.count for group in row.party)
    if not players:
        return "nessun giocatore"
    low, high = min(group.level for group in row.party), max(group.level for group in row.party)
    return f"{players} giocator{'e' if players == 1 else 'i'} · liv. {low if low == high else f'{low}–{high}'}"


class EncounterPage(ListPage):
    def __init__(self, repo: Repository):
        home, encounter = EncounterHome(), EncounterDetail()        # la schermata iniziale (tutti gli incontri) e un incontro
        content = QStackedWidget()
        content.addWidget(home)
        content.addWidget(encounter)
        empty = EmptyState("swords", _COLOR, "Nessun incontro", "Costruisci qui gli incontri della campagna: scegli le schede tecniche che servono "
                           "e, nei combattimenti, scopri quanto sono difficili per i tuoi giocatori.", "Crea il primo incontro")
        super().__init__(content, "", "", empty, docked=True)
        self._repo = repo
        self._home, self._encounter, self._content = home, encounter, content
        self._challenges: dict[int, str] = {}       # il grado di sfida di ogni scheda (serve alla difficoltà)
        home.chosen.connect(self._choose)
        encounter.edit_requested.connect(self._edit)
        empty.clicked.connect(self.create)
        add = action_button("Nuovo incontro", "plus", _COLOR)
        add.clicked.connect(self.create)
        self.buttons.layout().addWidget(add)

    def _read(self) -> list[Encounter]:
        self._challenges = {row.id: row.challenge for row in self._repo.creatures()}
        return self._repo.encounters()

    def _difficulty(self, row: Encounter) -> str | None:
        """La difficoltà di un combattimento, se si può calcolare."""
        return assessment_of(row, self._challenges).difficulty if row.kind == COMBAT else None

    def _item(self, row: Encounter) -> ListItem:
        """Nella barra stretta la difficoltà (nei combattimenti, se si può calcolare) prende il posto del tipo."""
        difficulty = self._difficulty(row)
        if difficulty:
            return ListItem(row.id, row.name, creatures_text(row), tag=DIFFICULTY_LABELS[difficulty], tag_color=theme.DIFFICULTY_COLORS[difficulty])
        return ListItem(row.id, row.name, f"{KIND_LABELS[row.kind]} · {creatures_text(row)}")

    def _show_selected(self) -> None:
        if self._selected is None:
            self._home.set_lines([EncounterLine(row.id, row.name, row.kind, creatures_text(row), players_text(row) if row.kind == COMBAT else "",
                                                self._difficulty(row)) for row in self._rows])
            self._encounter.forget()
            self._content.setCurrentWidget(self._home)
            return
        encounter = self._repo.encounter(self._selected)
        self._encounter.show_encounter(encounter, [self._repo.creature(slot.creature_id) for slot in encounter.creatures])
        self._content.setCurrentWidget(self._encounter)

    # --- Creare e modificare ---------------------------------------------------------------------
    def create(self) -> None:
        self._created(create_encounter(self, self._repo))

    def _edit(self) -> None:
        if self._selected is not None:
            self._edited(edit_encounter(self, self._repo, self._repo.encounter(self._selected)) == DELETE)
