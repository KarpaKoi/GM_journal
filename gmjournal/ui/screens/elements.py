"""Personaggi, Luoghi, Organizzazioni: la stessa schermata per i tre tipi. Griglia di tessere con filtri per categoria
e, a destra, l'anteprima dell'elemento scelto; «Apri scheda» (o un doppio clic) mostra al suo posto la scheda completa.

La schermata non tocca il database: legge e scrive solo tramite il `Repository`.
"""

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from ... import icons, theme
from ...data import links
from ...data.models import Category, Element
from ...data.repository import Repository
from ...elements import KINDS, ElementKind
from ...formatting import initials
from ..encounter_target import EncounterTarget
from ..graph_target import GraphTarget
from ..map_target import MapTarget
from ..popups.base import DELETE
from ..popups.element import create_element, edit_element
from ..widgets.card_grid import CardGrid
from ..widgets.cards import TILE_TEXT, ElementTile, NewCard, element_tile_height
from ..widgets.element_preview import ElementPreview
from ..widgets.empty_state import EmptyState
from ..widgets.filter_chip import FilterChip
from ..sheet.sheet import ElementSheet
from ..widgets.strip import HorizontalStrip
from .base import Screen

_LIST_VIEW, _EMPTY_VIEW, _SHEET_VIEW = 0, 1, 2


@dataclass(frozen=True)
class ElementTarget:
    """Dove si trova la schermata: l'elemento scelto e se se ne vede la scheda completa. Serve alla cronologia."""
    element_id: int
    sheet: bool = False


def link_destination(kind: str, target_id: int) -> tuple[str, object]:
    """Dove si apre ciò che un collegamento (o un risultato di ricerca) indica: (schermata, cosa mostrarvi).
    Un elemento si apre con la sua scheda, una mappa, un grafo o un incontro nella loro schermata, una pagina in Scrittura."""
    if kind in KINDS:
        return KINDS[kind].section, ElementTarget(target_id, True)
    if kind == links.ENCOUNTER:
        return "incontri", EncounterTarget(item_id=target_id)
    if kind == links.MAP:
        return "mappe", MapTarget(target_id)
    if kind == links.GRAPH:
        return "grafi", GraphTarget(target_id)
    return "scrittura", target_id


class ElementsScreen(Screen):
    def __init__(self, repo: Repository, kind: ElementKind):
        super().__init__()
        self._repo, self._kind = repo, kind
        self._elements: list[Element] = []
        self._categories: dict[int, Category] = {}
        self._selected: int | None = None
        self._sheet_open = False               # al posto della lista si vede la scheda dell'elemento scelto
        self._tiles: dict[int, ElementTile] = {}
        self._filter: int | None = None        # categoria scelta nei filtri (None = tutte)

        title = QLabel(kind.title)
        title.setFont(theme.serif_font(36, 500, -0.01))
        add = QPushButton(" " + kind.new)
        add.setIcon(icons.icon("plus", theme.BG))
        add.setIconSize(QSize(18, 18))
        add.setFixedHeight(38)
        add.setStyleSheet(theme.solid_button_style(kind.color))
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(self._create)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(title, alignment=Qt.AlignBottom)
        header.addStretch()
        header.addWidget(add)

        self._chips = QHBoxLayout()
        self._chips.setContentsMargins(0, 2, 0, 2)
        self._chips.setSpacing(8)
        chip_row = QWidget()
        chip_row.setLayout(self._chips)
        strip = HorizontalStrip(chip_row)
        strip.setFixedHeight(40)

        self._grid = CardGrid(max_columns=8, min_card_width=150, h_gap=16, v_gap=20, card_height=element_tile_height)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self._grid)

        listing = QWidget()
        column = QVBoxLayout(listing)
        column.setContentsMargins(32, 28, 32, 0)
        column.setSpacing(0)
        column.addLayout(header)
        column.addSpacing(20)
        column.addWidget(strip)
        column.addSpacing(16)
        column.addWidget(scroll, 1)

        empty = EmptyState(kind.icon, kind.color, kind.none, kind.empty_text, kind.first)
        empty.clicked.connect(self._create)
        self._views = QStackedWidget()
        self._views.addWidget(listing)      # _LIST_VIEW
        self._views.addWidget(empty)        # _EMPTY_VIEW
        self._sheet = ElementSheet(repo, kind)
        self._sheet.back_requested.connect(self._close_sheet)
        self._sheet.edit_requested.connect(self._edit)
        self._sheet.link_requested.connect(self._open_link)
        self._sheet.map_requested.connect(lambda target: self.open_requested.emit("mappe", target))
        self._views.addWidget(self._sheet)  # _SHEET_VIEW
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._views)

        self._preview = ElementPreview(f"Scegli {kind.the} per vederne i dettagli.")
        self._preview.edit_requested.connect(self._edit)
        self._preview.sheet_requested.connect(lambda: self._open_sheet(self._selected))
        self._preview.cited_chosen.connect(lambda target: self._open_link(target.kind, target.id))
        self.reload()

    def create_side_panel(self) -> QWidget:
        return self._preview

    # --- Posizione e cronologia ---------------------------------------------------------------
    def current_target(self) -> ElementTarget | None:
        return ElementTarget(self._selected, self._sheet_open) if self._selected is not None else None

    def bookmark_target(self) -> tuple[str, int] | None:
        return (self._kind.key, self._selected) if self._selected is not None else None

    def panel_visible(self) -> bool:
        return not self._sheet_open

    def show_target(self, target: object) -> None:
        """Mostra un elemento scelto (`ElementTarget`, o solo il suo ID) se esiste ancora; con `None` la lista resta com'è."""
        if target is None:
            if self._sheet_open:
                self._close_sheet(record=False)
            return
        if isinstance(target, int):
            target = ElementTarget(target)
        element = next((e for e in self._elements if e.id == target.element_id), None)
        if element is None:
            return
        reset_filter = self._filter not in (None, element.category_id)
        if reset_filter:
            self._filter = None
        self._selected = element.id
        if target.sheet:
            self._open_sheet(element.id, record=False)
        elif reset_filter or self._sheet_open:
            self._sheet_open = False
            self.reload()
        else:
            self._show(element.id)

    def flush(self) -> bool:
        return self._sheet.flush()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload()      # un elemento può essere stato creato o cambiato altrove (es. dal testo)
        if self._sheet_open:
            self._sheet.reload()

    # --- Contenuto --------------------------------------------------------------------------
    def reload(self) -> None:
        """Rilegge dati e ridisegna filtri, tessere e anteprima."""
        self._elements = self._repo.elements(self._kind.key)
        self._categories = {category.id: category for category in self._repo.categories(self._kind.key)}
        if self._filter not in self._categories:
            self._filter = None
        shown = self._visible()
        if not (self._sheet_open and any(element.id == self._selected for element in self._elements)):
            self._sheet_open = False        # la scheda aperta resta tale finché l'elemento esiste, qualunque sia il filtro
            if self._selected not in {element.id for element in shown}:       # la selezione sta sempre fra gli elementi visibili
                self._selected = shown[0].id if shown else None
        self._views.setCurrentIndex(_SHEET_VIEW if self._sheet_open else _LIST_VIEW if self._elements else _EMPTY_VIEW)
        self._build_chips()
        self._build_tiles(shown)
        self._refresh_preview()

    def _visible(self) -> list[Element]:
        return [element for element in self._elements if self._filter in (None, element.category_id)]

    def _build_chips(self) -> None:
        while self._chips.count():
            item = self._chips.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        options = [(None, "Tutti", theme.TEXT, len(self._elements))] + [
            (category.id, category.name, theme.category_color(category.color),
             sum(1 for element in self._elements if element.category_id == category.id))
            for category in self._categories.values()]
        for category_id, label, color, count in options:
            chip = FilterChip(label, color, count)
            chip.setChecked(category_id == self._filter)
            chip.clicked.connect(lambda _=False, category_id=category_id: self._set_filter(category_id))
            self._chips.addWidget(chip)
        self._chips.addStretch()

    def _build_tiles(self, shown: list[Element]) -> None:
        new = NewCard("Nuovo", self._kind.color, footer=TILE_TEXT)
        new.clicked.connect(self._create)
        tiles: list[QWidget] = [new]
        self._tiles.clear()
        for element in shown:
            category = self._categories[element.category_id]
            tile = ElementTile()
            tile.set_element(element.name, initials(element.name), category.name, theme.category_color(category.color),
                             self._repo.media_file(element.image))
            tile.set_selected(element.id == self._selected)
            tile.clicked.connect(lambda element_id=element.id: self._select(element_id))
            tile.double_clicked.connect(lambda element_id=element.id: self._open_sheet(element_id))
            tiles.append(tile)
            self._tiles[element.id] = tile
        self._grid.set_cards(tiles)

    def _refresh_preview(self) -> None:
        element = next((e for e in self._elements if e.id == self._selected), None)
        if element is None:
            if self._elements:
                self._preview.show_element(None, None, None, [])
            else:
                self._preview.clear()
            return
        self._preview.show_element(element, self._categories[element.category_id],
                                   self._repo.media_file(element.image),
                                   self._repo.cited_by(element.kind, element.id))

    def _set_filter(self, category_id: int | None) -> None:
        self._filter = category_id
        self.reload()

    def _show(self, element_id: int) -> None:
        """Evidenzia la tessera dell'elemento e ne mostra l'anteprima (senza ridisegnare la lista)."""
        self._selected = element_id
        for tile_id, tile in self._tiles.items():
            tile.set_selected(tile_id == element_id)
        self._refresh_preview()

    def _select(self, element_id: int) -> None:
        """L'utente ha scelto una tessera: va nella cronologia."""
        if element_id != self._selected:
            self._show(element_id)
            self.navigated.emit(element_id)

    def _open_link(self, kind: str, target_id: int) -> None:
        """Apre ciò che un collegamento indica: un elemento (di questo o di un altro tipo) con la sua scheda, una pagina in Scrittura."""
        self.open_requested.emit(*link_destination(kind, target_id))

    def _open_sheet(self, element_id: int | None, record: bool = True) -> None:
        if element_id is None:
            return
        self._selected, self._sheet_open = element_id, True
        self._sheet.open(element_id)
        self._views.setCurrentIndex(_SHEET_VIEW)
        if record:
            self.navigated.emit(self.current_target())

    def _close_sheet(self, record: bool = True) -> None:
        """Torna alla lista; l'elemento appena visto resta scelto (e visibile, anche se un filtro lo escluderebbe)."""
        self._sheet.flush()
        self._sheet_open = False
        element = next((e for e in self._elements if e.id == self._selected), None)
        if element is not None and self._filter not in (None, element.category_id):
            self._filter = None
        self.reload()
        if record:
            self.navigated.emit(self.current_target())

    # --- Creare, modificare, eliminare ---------------------------------------------------------
    def _create(self) -> None:
        element_id = create_element(self, self._repo, self._kind)
        if element_id is not None:
            self._filter = None
            self._selected = element_id
            self.reload()
            self.navigated.emit(element_id)

    def _edit(self) -> None:
        element = next((e for e in self._elements if e.id == self._selected), None)
        if element is None:
            return
        result = edit_element(self, self._repo, element)
        was_open = self._sheet_open
        self.reload()
        if self._sheet_open:
            self._sheet.refresh_header()
        if result == DELETE:
            self.navigated.emit(self.current_target())
        elif was_open and not self._sheet_open:
            self.navigated.emit(self.current_target())
