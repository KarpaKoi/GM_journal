"""Mappe: l'elenco delle mappe a schede, la mappa interattiva con i suoi pin e, a destra, l'elenco dei pin.

La schermata non tocca il database: legge e scrive solo tramite il `Repository`.
"""

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data import links, trees
from ...data.db import DatabaseError
from ...data.models import LinkTarget, Map, Pin, PinType
from ...data.repository import Repository
from ...elements import KINDS
from ..editor.link_ui import LinkPickerPopup
from ..map_target import MapTarget
from ..popups.map import create_map, edit_map
from ..popups.pin_type import create_pin_type
from ..widgets.card_grid import CardGrid
from ..widgets.cards import NewCard
from ..widgets.empty_state import EmptyState
from ..widgets.map_canvas import ADD, GHOST, SELECT, MapCanvas
from ..widgets.map_card import MapCard, map_card_height
from ..widgets.menu import PopupMenu
from ..widgets.name_tree import NameTree
from ..widgets.pin_card import PinCard
from ..widgets.pin_form import PinForm
from ..widgets.pins_panel import PinsPanel
from ..widgets.sidebar_list import sidebar_list
from .base import Screen
from .elements import link_destination

_COLOR = theme.SECTION_COLORS["mappe"]
_OVERVIEW_VIEW, _MAP_VIEW, _EMPTY_VIEW = 0, 1, 2
_NO_MAP = "Nessuna mappa"


class MapsScreen(Screen):
    def __init__(self, repo: Repository):
        super().__init__()
        self._repo = repo
        self._maps: list[Map] = []
        self._types: list[PinType] = []
        self._pins: list[Pin] = []
        self._map_id: int | None = None                # mappa aperta (None = l'elenco delle mappe)
        self._selected: int | None = None              # pin scelto
        self._shown: tuple[int, str | None] | None = None   # (mappa, sfondo) già nell'area: così non si re-inquadra a ogni ridisegno
        self._form: PinForm | None = None              # la finestrella aperta per posare o modificare un pin
        self._form_pin: Pin | None = None              # il pin che si sta modificando (None = se ne sta posando uno nuovo)
        self._ghost = (0.0, 0.0)                       # dove si sta posando il pin nuovo
        self._last_type: int | None = None             # l'ultimo tipo usato: il prossimo pin parte da quello
        self._armed: LinkTarget | None = None          # arrivando da una scheda: il pin che si posa sarà collegato a questo elemento

        self._tree = NameTree()
        self._panel = PinsPanel()
        self._canvas = MapCanvas()
        self._sidebar_list = sidebar_list("MAPPE", "Nuova mappa", self._create_map, self._tree)
        self._views = QStackedWidget()
        self._grid = CardGrid(max_columns=5, min_card_width=250, h_gap=16, v_gap=20, card_height=map_card_height)
        self._build_center()

        self._tree.selected.connect(self._open_map, Qt.QueuedConnection)   # dopo il clic: aprire una mappa ridisegna l'albero
        self._tree.menu_requested.connect(self._show_map_menu)
        self._panel.chosen.connect(self._select_pin)
        self._canvas.pin_clicked.connect(self._select_pin)
        self._canvas.pin_moved.connect(self._move_pin)
        self._canvas.background_clicked.connect(self._deselect)
        self._canvas.add_requested.connect(self._begin_pin)
        self._canvas.tool_changed.connect(self._on_tool_changed)
        self._canvas.type_requested.connect(self._new_type)
        self._canvas.image_requested.connect(lambda: self._edit_map(self._map(self._map_id)))
        self.reload()

    # --- Costruzione -------------------------------------------------------------------------------
    def _build_center(self) -> None:
        title = QLabel("Mappe")
        title.setFont(theme.serif_font(36, 500, -0.01))
        add = QPushButton(" Nuova mappa")
        add.setIcon(icons.icon("plus", theme.BG))
        add.setIconSize(QSize(18, 18))
        add.setFixedHeight(38)
        add.setStyleSheet(theme.solid_button_style(_COLOR))
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: self._create_map())
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(title, alignment=Qt.AlignBottom)
        header.addStretch()
        header.addWidget(add)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self._grid)
        overview = QWidget()
        column = QVBoxLayout(overview)
        column.setContentsMargins(32, 28, 32, 0)
        column.setSpacing(0)
        column.addLayout(header)
        column.addSpacing(24)
        column.addWidget(scroll, 1)

        empty = EmptyState("map", _COLOR, _NO_MAP, "Crea la prima mappa della tua campagna: un regno, una città, un sotterraneo. Sopra ci posi i pin.",
                           "Crea la prima mappa")
        empty.clicked.connect(lambda: self._create_map())
        self._views.addWidget(overview)         # _OVERVIEW_VIEW
        self._views.addWidget(self._canvas)     # _MAP_VIEW
        self._views.addWidget(empty)            # _EMPTY_VIEW
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._views)

    def create_side_panel(self) -> QWidget:
        return self._panel

    def create_sidebar_list(self) -> QWidget:
        return self._sidebar_list

    def panel_visible(self) -> bool:
        return self._map_id is not None

    # --- Posizione e cronologia ------------------------------------------------------------------
    def current_target(self) -> MapTarget | None:
        return MapTarget(self._map_id, self._selected) if self._map_id is not None else None

    def bookmark_target(self) -> tuple[str, int] | None:
        return (links.MAP, self._map_id) if self._map_id is not None else None

    def trail(self) -> list[tuple[str, MapTarget]]:
        """Le mappe che contengono quella aperta, fino a lei («Mondo › Regno › Città»)."""
        return [(node.name, MapTarget(node.id)) for node in trees.chain(self._maps, self._map_id)]

    def show_target(self, target: object) -> None:
        """Mostra una mappa e un suo pin (`MapTarget`); con `None` l'elenco delle mappe.
        Se il bersaglio ha un elemento (`place`), la mappa si apre con lo strumento «Aggiungi pin» già scelto per posarlo."""
        target = target or MapTarget()
        self._open_map(target.map_id, record=False)
        if self._map_id is None:
            return
        if target.pin_id in {pin.id for pin in self._pins}:
            self._select_pin(target.pin_id, record=False)
        if target.place is not None:
            self._canvas.set_tool(ADD)
            self._armed = target.place          # dopo `set_tool`: cambiare strumento la azzera

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._abandon_form()
        self.reload()          # mappe e pin possono essere cambiati mentre si era altrove

    # --- Contenuto ------------------------------------------------------------------------------------
    def reload(self) -> None:
        """Rilegge mappe e tipi di pin e ridisegna ciò che si vede."""
        self._maps = self._repo.maps()
        self._types = self._repo.pin_types()
        if self._map_id not in {node.id for node in self._maps}:
            self._map_id = None
        if self._map_id is None:
            self._selected = self._shown = None
            self._close_card()
        self._refresh_tree()
        self._build_overview()
        if self._map_id is None:
            self._views.setCurrentIndex(_OVERVIEW_VIEW if self._maps else _EMPTY_VIEW)
            return
        node = self._map(self._map_id)
        if (node.id, node.image) != self._shown:        # un'altra mappa, o un altro sfondo
            self._close_card()
            self._canvas.set_image(self._repo.media_file(node.image))
            self._shown = (node.id, node.image)
        self._canvas.set_types(self._types)
        self._refresh_pins()
        self._views.setCurrentIndex(_MAP_VIEW)

    def _refresh_tree(self) -> None:
        self._tree.set_items([(node.id, node.parent_id, node.name) for node in self._maps], self._map_id)
        self.trail_changed.emit()          # i nomi delle mappe possono essere cambiati

    def _build_overview(self) -> None:
        counts = self._repo.pin_counts()
        names = {node.id: node.name for node in self._maps}
        cards: list[QWidget] = []
        for node in self._maps:
            card = MapCard()
            meta = f"{counts.get(node.id, 0)} pin" + (f" · dentro {names[node.parent_id]}" if node.parent_id is not None else "")
            card.set_map(node.name, meta, self._repo.media_file(node.image))
            card.clicked.connect(lambda map_id=node.id: self._open_map(map_id))
            card.edit_clicked.connect(lambda node=node: self._edit_map(node))
            cards.append(card)
        new = NewCard("Nuova mappa", _COLOR)
        new.clicked.connect(lambda: self._create_map())
        cards.append(new)
        self._grid.set_cards(cards)

    def _map(self, map_id: int) -> Map:
        return next(node for node in self._maps if node.id == map_id)

    def _pin(self, pin_id: int) -> Pin:
        return next(pin for pin in self._pins if pin.id == pin_id)

    def _type(self, type_id: int) -> PinType:
        return next(pin_type for pin_type in self._types if pin_type.id == type_id)

    def _refresh_pins(self) -> None:
        """Rilegge i pin della mappa aperta e ridisegna l'area e il pannello."""
        self._pins = self._repo.pins(self._map_id)
        if self._selected not in {pin.id for pin in self._pins}:
            self._selected = None
            self._close_card()
        self._canvas.set_pins(self._pins)
        self._canvas.set_selected(self._selected)
        self._refresh_panel()

    def _refresh_panel(self) -> None:
        node = self._map(self._map_id)
        path = trees.PATH_SEPARATOR.join(parent.name for parent in trees.chain(self._maps, node.parent_id))
        empty = ("Nessun pin. Scegli lo strumento «Aggiungi pin» e clicca sulla mappa." if self._canvas.has_image()
                 else "Nessun pin. Prima scegli lo sfondo della mappa: i pin si posano sopra.")
        self._panel.show_pins(node.name, path, [(pin, self._type(pin.type_id)) for pin in self._pins], self._selected, empty)

    # --- Aprire, creare, modificare le mappe ----------------------------------------------------
    def _open_map(self, map_id: int | None, record: bool = True) -> None:
        """Apre la mappa `map_id` (None = l'elenco). `record`: l'ha scelta l'utente (va nella cronologia)."""
        self._abandon_form()
        self._selected = None
        self._map_id = map_id
        self.reload()
        if record:
            self.navigated.emit(self.current_target())

    def _create_map(self, parent_id: int | None = None) -> None:
        new_id = create_map(self, self._repo, parent_id)
        if new_id is not None:
            self._open_map(new_id)

    def _edit_map(self, node: Map) -> None:
        self._abandon_form()
        opened = self._map_id
        if edit_map(self, self._repo, node) != QDialog.Rejected:
            self.reload()
            if self._map_id != opened:          # la mappa aperta è stata eliminata: si torna all'elenco
                self.navigated.emit(self.current_target())

    def _show_map_menu(self, map_id: int, point: QPoint) -> None:
        node = self._map(map_id)
        menu = PopupMenu(self, width=220)
        menu.add_item("pencil", "Modifica…", lambda: self._edit_map(node))
        menu.add_item("plus", "Nuova sottomappa", lambda: self._create_map(map_id))
        menu.add_separator()
        menu.add_item("trash", "Elimina…", lambda: self._edit_map(node), danger=True)   # si elimina dal popup di modifica
        menu.popup_at(point)

    # --- Scegliere un pin ----------------------------------------------------------------------------
    def _select_pin(self, pin_id: int, record: bool = True) -> None:
        """Sceglie il pin: lo evidenzia, mostra la sua finestrella e lo elenca nel pannello."""
        if self._form is not None:          # si sta compilando un pin: prima si finisce o si annulla
            return
        self._close_card()
        self._selected = pin_id
        pin = self._pin(pin_id)
        self._canvas.set_selected(pin_id)
        self._canvas.reveal(pin_id)
        self._refresh_panel()
        opens = next((node for node in self._maps if node.id == pin.opens_map_id), None)
        card = PinCard(pin, self._type(pin.type_id), opens)
        card.close_requested.connect(self._deselect)
        card.edit_requested.connect(lambda: self._edit_pin(pin))
        card.map_requested.connect(lambda: self._open_map(pin.opens_map_id))
        if pin.link is not None:
            card.page_requested.connect(lambda: self.open_requested.emit(*link_destination(pin.link.kind, pin.link.id)))
        self._canvas.show_card(card, pin_id, "above")
        if record:
            self.navigated.emit(self.current_target())
            self.panel_requested.emit()

    def _deselect(self) -> None:
        self._selected = None
        self._close_card()
        self._canvas.set_selected(None)
        self._refresh_panel()

    def _close_card(self) -> None:
        """Chiude la finestrella aperta sulla mappa (e il pin appena posato, se non è stato salvato)."""
        self._canvas.close_card()
        self._canvas.clear_ghost()
        self._form = self._form_pin = None

    # --- Posare e modificare un pin -----------------------------------------------------------
    def _begin_pin(self, x: float, y: float) -> None:
        """Clic sulla mappa con lo strumento «Aggiungi pin»: compare il pin e la finestrella per compilarlo."""
        self._selected = None
        self._close_card()
        self._canvas.set_selected(None)
        self._refresh_panel()
        self._ghost = (x, y)
        start = next((t for t in self._types if t.id == self._last_type), self._types[0])
        form = PinForm(edit=False)
        if self._armed is not None:
            form.set_link(self._armed, self._link_brief(self._armed))
        self._canvas.show_ghost(x, y, start)
        self._open_form(form, GHOST, start.id)

    def _edit_pin(self, pin: Pin) -> None:
        self._close_card()
        form = PinForm(edit=True, name="" if pin.link else pin.name, brief="" if pin.link else pin.brief)
        self._form_pin = pin
        form.set_link(pin.link, pin.brief)
        form.set_opens(next((node for node in self._maps if node.id == pin.opens_map_id), None))
        form.delete_confirmed.connect(self._delete_pin)
        self._open_form(form, pin.id, pin.type_id)

    def _open_form(self, form: PinForm, pin_id: int, type_id: int) -> None:
        """Mostra `form` accanto al pin; `type_id` è il tipo da cui parte."""
        self._form = form
        form.set_types(self._types, type_id)
        form.type_changed.connect(self._restyle_ghost)
        form.new_type_requested.connect(self._new_type)
        form.link_requested.connect(self._choose_link)
        form.map_requested.connect(self._choose_map)
        form.submitted.connect(self._save_pin)
        form.cancelled.connect(self._cancel_form)
        self._canvas.show_card(form, pin_id, "right", locked=True)
        form.focus_name()

    def _on_tool_changed(self, tool: str) -> None:
        if tool != ADD:
            self._armed = None

    def _link_brief(self, target: LinkTarget) -> str:
        """Il testo «in breve» di ciò a cui è collegato un pin (le pagine non ne hanno)."""
        return self._repo.element(target.id).brief if target.kind in KINDS else ""

    def _restyle_ghost(self, type_id: int) -> None:
        if self._form_pin is None:
            self._canvas.show_ghost(*self._ghost, self._type(type_id))

    def _abandon_form(self) -> None:
        """Se si stava compilando un pin, lo lascia stare (lo si perde: nessuno l'ha salvato)."""
        if self._form is not None:
            self._cancel_form(reselect=False)

    def _cancel_form(self, reselect: bool = True) -> None:
        editing = self._form_pin
        self._close_card()
        self._canvas.set_tool(SELECT)
        if editing is not None and reselect:
            self._select_pin(editing.id, record=False)

    def _save_pin(self) -> None:
        data = self._form.data()
        editing = self._form_pin
        try:
            if editing is None:
                pin_id = self._repo.create_pin(self._map_id, *self._ghost, data)
            else:
                pin_id = editing.id
                self._repo.update_pin(pin_id, data)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
            return
        self._last_type = data.type_id
        self._canvas.reveal_type(data.type_id)        # se quel tipo era nascosto dai filtri, il pin sparirebbe appena posato
        self._close_card()
        self._canvas.set_tool(SELECT)
        self._selected = None
        self._refresh_pins()
        self._select_pin(pin_id, record=editing is None)

    def _delete_pin(self) -> None:
        pin = self._form_pin
        self._close_card()
        self._selected = None
        try:
            self._repo.delete_pin(pin.id)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self._refresh_pins()

    def _move_pin(self, pin_id: int, x: float, y: float) -> None:
        if pin_id == GHOST:
            self._ghost = (x, y)
            return
        try:
            self._repo.move_pin(pin_id, x, y)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self._refresh_pins()

    # --- Le scelte dentro la finestrella di un pin --------------------------------------------------
    def _new_type(self) -> None:
        type_id = create_pin_type(self, self._repo)
        if type_id is None:
            return
        self._types = self._repo.pin_types()
        self._canvas.set_types(self._types)
        if self._form is not None:        # il tipo nuovo è subito quello scelto
            self._form.set_types(self._types, type_id)
            self._restyle_ghost(type_id)

    def _choose_link(self) -> None:
        popup = LinkPickerPopup(self, lambda query, limit: self._repo.link_targets(query, limit=limit, views=False), "Collega il pin a…",
                                "Il pin prenderà il nome e il testo dalla pagina o dall'elemento che scegli.")
        if popup.exec() == QDialog.Accepted:
            self._form.set_link(popup.target, self._link_brief(popup.target))

    def _choose_map(self) -> None:
        """Il menu delle mappe che il pin può aprire (non quella su cui sta), con «Nessuna mappa» e «Crea una nuova mappa…»."""
        form = self._form
        menu = PopupMenu(self, width=300)
        current = form.data().opens_map_id
        if current is not None:
            menu.add_item("x", _NO_MAP, lambda: form.set_opens(None))
            menu.add_separator()
        for map_id, path in trees.named_paths(self._maps):
            if map_id != self._map_id:
                menu.add_item("map", path, lambda map_id=map_id: form.set_opens(self._map(map_id)), checked=map_id == current)
        menu.add_separator()
        menu.add_item("plus", "Crea una nuova mappa…", lambda: self._create_map_for(form))
        menu.popup_below(form.map_anchor())

    def _create_map_for(self, form: PinForm) -> None:
        """Crea una mappa dentro quella aperta e la sceglie come quella che il pin apre."""
        new_id = create_map(self, self._repo, self._map_id)
        if new_id is not None:
            self._maps = self._repo.maps()
            self._refresh_tree()
            form.set_opens(self._map(new_id))
