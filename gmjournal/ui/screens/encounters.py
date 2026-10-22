"""Incontri: due pagine, gli incontri (di combattimento e di interazione) e le schede tecniche di mostri e PNG che servono a costruirli.

La pagina degli incontri si apre sull'elenco di tutti (la schermata iniziale); un incontro mostra solo le schede che servono a portarlo
avanti e, nei combattimenti, quanto è difficile (regole del 2014). Lo stesso elenco sta anche nella barra sinistra dell'app, accanto alle
voci delle sezioni. La schermata non tocca il database: ogni pagina legge e scrive solo tramite il `Repository`.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedLayout, QVBoxLayout, QWidget

from ... import theme
from ...data import links
from ...data.repository import Repository
from ..encounter_target import CREATURES, ENCOUNTERS, EncounterTarget
from ..widgets.creature_page import CreaturePage
from ..widgets.encounter_page import EncounterPage
from ..widgets.list_page import ListPage
from ..widgets.segment_switch import SegmentSwitch
from ..widgets.sidebar_list import sidebar_list
from .base import Screen

_TITLES = {ENCOUNTERS: "Incontri", CREATURES: "Schede tecniche"}


class _TitleLink(QLabel):
    """Il titolo della schermata: un clic riporta all'elenco degli incontri (passando il mouse si sottolinea)."""
    clicked = Signal()

    def __init__(self, text: str):
        super().__init__(text)
        self.setFont(theme.serif_font(36, 500, -0.01))
        self.setCursor(Qt.PointingHandCursor)

    def _underline(self, on: bool) -> None:
        font = self.font()
        font.setUnderline(on)
        self.setFont(font)

    def enterEvent(self, event) -> None:
        self._underline(True)

    def leaveEvent(self, event) -> None:
        self._underline(False)

    def mousePressEvent(self, event) -> None:
        event.accept()          # il clic vero è al rilascio: senza questo il rilascio non arriva

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()


class EncountersScreen(Screen):
    def __init__(self, repo: Repository):
        super().__init__()
        self._pages: dict[str, ListPage] = {ENCOUNTERS: EncounterPage(repo), CREATURES: CreaturePage(repo)}
        self._page = ENCOUNTERS

        self._title = _TitleLink(_TITLES[ENCOUNTERS])       # resta «Incontri» anche guardando le schede tecniche
        self._title.clicked.connect(self._show_list)
        self._switch = SegmentSwitch([(key, title, 13) for key, title in _TITLES.items()], self._choose_page, segment_width=130)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(self._title, alignment=Qt.AlignBottom)
        header.addSpacing(16)
        header.addWidget(self._switch, alignment=Qt.AlignBottom)
        header.addStretch()

        self._stack = QStackedLayout()
        self._buttons = QStackedLayout()
        for key, page in self._pages.items():
            self._stack.addWidget(page)
            self._buttons.addWidget(page.buttons)
            page.navigated.connect(lambda item_id, key=key: self._navigated(key, item_id))
        buttons = QWidget()
        buttons.setLayout(self._buttons)
        header.addWidget(buttons, alignment=Qt.AlignBottom)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addSpacing(20)
        layout.addLayout(self._stack, 1)
        self._pages[CREATURES].changed.connect(self._refresh_encounters)
        self._open_page(ENCOUNTERS)

    def create_sidebar_list(self) -> QWidget:
        encounters = self._pages[ENCOUNTERS]
        return sidebar_list("INCONTRI", "Nuovo incontro", encounters.create, encounters.left)

    # --- Posizione e cronologia ---------------------------------------------------------------
    def current_target(self) -> EncounterTarget:
        return EncounterTarget(self._page, self._pages[self._page].current_id())

    def bookmark_target(self) -> tuple[str, int] | None:
        incontro = self._pages[ENCOUNTERS].current_id() if self._page == ENCOUNTERS else None
        return (links.ENCOUNTER, incontro) if incontro is not None else None

    def show_target(self, target: object) -> None:
        """Mostra una pagina e la sua voce scelta (senza target: l'elenco degli incontri). Una voce che non esiste più si ignora."""
        if target is None:
            self._open_page(ENCOUNTERS)
            self._pages[ENCOUNTERS].show_id(None)
        elif isinstance(target, EncounterTarget):
            self._open_page(target.page)
            if target.item_id is None or self._pages[target.page].has(target.item_id):
                self._pages[target.page].show_id(target.item_id)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._pages[self._page].reload()

    # --- Pagine ---------------------------------------------------------------------------------
    def _open_page(self, key: str) -> None:
        """Mostra la pagina (rileggendola: le schede cambiate in un'altra pagina cambiano anche gli incontri)."""
        self._page = key
        self._switch.set_value(key)
        self._stack.setCurrentWidget(self._pages[key])
        self._buttons.setCurrentWidget(self._pages[key].buttons)
        self._pages[key].reload()
        if key != ENCOUNTERS:
            self._pages[ENCOUNTERS].unmark()        # l'elenco degli incontri resta nella barra, ma senza una voce evidenziata

    def _refresh_encounters(self) -> None:
        """Una scheda è cambiata: nell'elenco degli incontri (nella barra) cambiano creature e difficoltà."""
        self._pages[ENCOUNTERS].reload()
        self._pages[ENCOUNTERS].unmark()

    def _navigated(self, key: str, item_id: int | None) -> None:
        """Una pagina ha cambiato voce. Gli incontri si scelgono dalla barra anche guardando le schede: si passa alla loro pagina."""
        if key != self._page:
            self._open_page(key)
        self.navigated.emit(EncounterTarget(key, item_id))

    def _show_list(self) -> None:
        """Il titolo riporta all'elenco degli incontri, da dove si sia (va nella cronologia)."""
        if self._page != ENCOUNTERS or self._pages[ENCOUNTERS].current_id() is not None:
            self.show_target(None)
            self.navigated.emit(self.current_target())

    def _choose_page(self, key: str) -> None:
        """L'utente passa da una pagina all'altra: va nella cronologia."""
        if key != self._page:
            self._open_page(key)
            self.navigated.emit(self.current_target())
