"""Grafi: l'elenco dei grafi a schede, il grafo interattivo (mappa mentale) e, a destra, i suoi nodi o i campi del nodo o dell'arco scelto.

La schermata non tocca il database: legge e scrive solo tramite il `Repository`.
"""

from dataclasses import replace

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data import links
from ...data.db import DatabaseError
from ...data.models import Graph, GraphEdge, GraphNode, NodeInput
from ...data.repository import Repository
from ...graphs import KIND_EDGE, KIND_NODE, NEW_NODE_COLOR, NEW_NODE_TITLE, Endpoint
from ..editor.link_ui import LinkPickerPopup
from ..graph_target import GraphTarget
from ..kinds import kind_icon, target_caption
from ..popups.graph import create_graph, edit_graph
from ..sheet.saves import PendingSaves
from ..widgets.card_grid import CardGrid
from ..widgets.cards import NewCard
from ..widgets.empty_state import EmptyState
from ..widgets.graph_canvas import SELECT, GraphCanvas
from ..widgets.graph_card import GraphCard
from ..widgets.graph_panel import EndInfo, GraphPanel
from ..widgets.map_card import map_card_height
from ..widgets.menu import PopupMenu
from ..widgets.name_tree import NameTree
from ..widgets.sidebar_list import sidebar_list
from .base import Screen
from .elements import link_destination

_COLOR = theme.SECTION_COLORS["grafi"]
_OVERVIEW_VIEW, _GRAPH_VIEW, _EMPTY_VIEW = 0, 1, 2
_NO_NODES = "Nessun nodo. Scegli lo strumento «Nodo» e clicca sulla tela."
_FREE_NODE = "Nodo libero"
_NO_LABEL = "Arco senza etichetta"


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


class GraphsScreen(Screen):
    def __init__(self, repo: Repository):
        super().__init__()
        self._repo = repo
        self._graphs: list[Graph] = []
        self._nodes: dict[int, GraphNode] = {}          # i nodi del grafo aperto (anche con le modifiche non ancora salvate)
        self._edges: dict[int, GraphEdge] = {}
        self._graph_id: int | None = None               # grafo aperto (None = l'elenco dei grafi)
        self._node_id: int | None = None                # nodo scelto
        self._edge_id: int | None = None                # oppure arco scelto
        self._shown: int | None = None                  # grafo già nell'area: così non si re-inquadra a ogni ridisegno
        self._saves = PendingSaves(self, lambda message: QMessageBox.warning(self, "GM Journal", message))

        self._tree = NameTree()
        self._panel = GraphPanel()
        self._canvas = GraphCanvas()
        self._sidebar_list = sidebar_list("GRAFI", "Nuovo grafo", self._create_graph, self._tree)
        self._views = QStackedWidget()
        self._grid = CardGrid(max_columns=5, min_card_width=250, h_gap=16, v_gap=20, card_height=map_card_height)
        self._build_center()

        self._tree.selected.connect(self._open_graph, Qt.QueuedConnection)   # dopo il clic: aprire un grafo ridisegna l'elenco
        self._tree.menu_requested.connect(self._show_graph_menu)
        self._canvas.node_clicked.connect(self._select_node)
        self._canvas.edge_clicked.connect(self._select_edge)
        self._canvas.background_clicked.connect(self._deselect)
        self._canvas.node_moved.connect(self._move_node)
        self._canvas.add_requested.connect(self._add_node)
        self._canvas.connect_requested.connect(self._connect)
        self._panel.back_requested.connect(self._deselect)
        self._panel.node_chosen.connect(self._select_node)
        self._panel.edge_chosen.connect(self._select_edge)
        self._panel.title_edited.connect(lambda text: self._edit_node(title=text))
        self._panel.description_edited.connect(lambda text: self._edit_node(description=text))
        self._panel.color_chosen.connect(lambda color: self._edit_node(color=color, now=True))
        self._panel.label_edited.connect(lambda text: self._edit_edge(label=text))
        self._panel.direction_chosen.connect(lambda direction: self._edit_edge(direction=direction, now=True))
        self._panel.link_requested.connect(self._choose_link)
        self._panel.open_link_requested.connect(self._open_link)
        self._panel.unlink_requested.connect(self._unlink)
        self._panel.node_delete_confirmed.connect(self._delete_node)
        self._panel.edge_delete_confirmed.connect(self._delete_edge)
        self.reload()

    # --- Costruzione -------------------------------------------------------------------------------
    def _build_center(self) -> None:
        title = QLabel("Grafi")
        title.setFont(theme.serif_font(36, 500, -0.01))
        add = QPushButton(" Nuovo grafo")
        add.setIcon(icons.icon("plus", theme.BG))
        add.setIconSize(QSize(18, 18))
        add.setFixedHeight(38)
        add.setStyleSheet(theme.solid_button_style(_COLOR))
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: self._create_graph())
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

        empty = EmptyState("graph", _COLOR, "Nessun grafo", "Crea il primo grafo della tua campagna: una trama, i legami di una corte, un complotto. "
                           "Sopra ci metti nodi e li colleghi.", "Crea il primo grafo")
        empty.clicked.connect(lambda: self._create_graph())
        self._views.addWidget(overview)         # _OVERVIEW_VIEW
        self._views.addWidget(self._canvas)     # _GRAPH_VIEW
        self._views.addWidget(empty)            # _EMPTY_VIEW
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._views)

    def create_side_panel(self) -> QWidget:
        return self._panel

    def create_sidebar_list(self) -> QWidget:
        return self._sidebar_list

    def panel_visible(self) -> bool:
        return self._graph_id is not None

    def flush(self) -> bool:
        return self._saves.flush()

    # --- Posizione e cronologia ------------------------------------------------------------------
    def current_target(self) -> GraphTarget | None:
        return GraphTarget(self._graph_id, self._node_id, self._edge_id) if self._graph_id is not None else None

    def bookmark_target(self) -> tuple[str, int] | None:
        return (links.GRAPH, self._graph_id) if self._graph_id is not None else None

    def show_target(self, target: object) -> None:
        """Mostra un grafo e un suo nodo o arco (`GraphTarget`); con `None` l'elenco dei grafi."""
        target = target or GraphTarget()
        self._open_graph(target.graph_id, record=False)
        if self._graph_id is None:
            return
        if target.node_id in self._nodes:
            self._select_node(target.node_id, record=False)
        elif target.edge_id in self._edges:
            self._select_edge(target.edge_id, record=False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload()          # grafi, pagine ed elementi possono essere cambiati mentre si era altrove

    # --- Contenuto ------------------------------------------------------------------------------------
    def reload(self) -> None:
        """Rilegge i grafi (e quello aperto) e ridisegna ciò che si vede."""
        self._saves.flush()
        self._graphs = self._repo.graphs()
        if self._graph_id not in {graph.id for graph in self._graphs}:
            self._graph_id = None
        self._tree.set_items([(graph.id, None, graph.name) for graph in self._graphs], self._graph_id)
        self._build_overview()
        if self._graph_id is None:
            self._node_id = self._edge_id = self._shown = None
            self._nodes, self._edges = {}, {}
            self._views.setCurrentIndex(_OVERVIEW_VIEW if self._graphs else _EMPTY_VIEW)
            return
        self._refresh_graph(refit=self._shown != self._graph_id)
        self._shown = self._graph_id
        self._views.setCurrentIndex(_GRAPH_VIEW)

    def _build_overview(self) -> None:
        cards: list[QWidget] = []
        for graph in self._graphs:
            nodes, edges = self._repo.graph_nodes(graph.id), self._repo.graph_edges(graph.id)
            card = GraphCard()
            card.set_graph(graph.name, f"{_count(len(nodes), 'nodo', 'nodi')} · {_count(len(edges), 'arco', 'archi')}", nodes, edges)
            card.clicked.connect(lambda graph_id=graph.id: self._open_graph(graph_id))
            card.edit_clicked.connect(lambda graph=graph: self._edit_graph(graph))
            cards.append(card)
        new = NewCard("Nuovo grafo", _COLOR)
        new.clicked.connect(lambda: self._create_graph())
        cards.append(new)
        self._grid.set_cards(cards)

    def _graph(self, graph_id: int) -> Graph:
        return next(graph for graph in self._graphs if graph.id == graph_id)

    def _refresh_graph(self, refit: bool = False) -> None:
        """Rilegge nodi e archi del grafo aperto e ridisegna la tela e il pannello."""
        self._nodes = {node.id: node for node in self._repo.graph_nodes(self._graph_id)}
        self._edges = {edge.id: edge for edge in self._repo.graph_edges(self._graph_id)}
        if self._node_id not in self._nodes:
            self._node_id = None
        if self._edge_id not in self._edges:
            self._edge_id = None
        self._canvas.set_graph(list(self._nodes.values()), list(self._edges.values()), refit)
        self._canvas.set_selection(self._node_id, self._edge_id)
        self._refresh_panel()

    def _info(self, end: Endpoint) -> EndInfo:
        """Come si presenta un nodo o un arco nel pannello. Un arco si riconosce dalla sua etichetta e, sotto, dai suoi due estremi."""
        if end.kind == KIND_NODE:
            node = self._nodes[end.id]
            return EndInfo(end, node.title, target_caption(node.link) if node.link is not None else _FREE_NODE,
                           theme.category_color(node.color), kind_icon(node.link.kind) if node.link is not None else "graph")
        edge = self._edges[end.id]
        return EndInfo(end, edge.label or _NO_LABEL, f"{self._info(edge.a).title} – {self._info(edge.b).title}", theme.category_color("gray"), "connect")

    def _arcs_on(self, end: Endpoint) -> list[tuple[GraphEdge, EndInfo]]:
        """Gli archi che finiscono su questo nodo o arco, ognuno con ciò che sta dall'altra parte."""
        return [(edge, self._info(edge.b if edge.a == end else edge.a)) for edge in self._edges.values() if end in (edge.a, edge.b)]

    def _refresh_panel(self) -> None:
        name = self._graph(self._graph_id).name
        if self._node_id is not None:
            self._panel.show_node(name, self._nodes[self._node_id], self._arcs_on(Endpoint(KIND_NODE, self._node_id)))
        elif self._edge_id is not None:
            edge = self._edges[self._edge_id]
            self._panel.show_edge(name, edge, self._info(edge.a), self._info(edge.b), self._arcs_on(Endpoint(KIND_EDGE, edge.id)))
        else:
            self._panel.show_overview(name, [self._info(Endpoint(KIND_NODE, node_id)) for node_id in self._nodes], _NO_NODES)

    # --- Aprire, creare, modificare i grafi ------------------------------------------------------
    def _open_graph(self, graph_id: int | None, record: bool = True) -> None:
        """Apre il grafo `graph_id` (None = l'elenco). `record`: l'ha scelto l'utente (va nella cronologia)."""
        self._node_id = self._edge_id = None
        self._graph_id = graph_id
        self.reload()
        if record:
            self.navigated.emit(self.current_target())

    def _create_graph(self) -> None:
        new_id = create_graph(self, self._repo)
        if new_id is not None:
            self._open_graph(new_id)

    def _edit_graph(self, graph: Graph) -> None:
        opened = self._graph_id
        if edit_graph(self, self._repo, graph) != QDialog.Rejected:
            self.reload()
            if self._graph_id != opened:          # il grafo aperto è stato eliminato: si torna all'elenco
                self.navigated.emit(self.current_target())

    def _show_graph_menu(self, graph_id: int, point: QPoint) -> None:
        graph = self._graph(graph_id)
        menu = PopupMenu(self, width=220)
        menu.add_item("pencil", "Modifica…", lambda: self._edit_graph(graph))
        menu.add_separator()
        menu.add_item("trash", "Elimina…", lambda: self._edit_graph(graph), danger=True)   # si elimina dal popup di modifica
        menu.popup_at(point)

    # --- Scegliere un nodo o un arco ---------------------------------------------------------------
    def _select(self, node_id: int | None, edge_id: int | None, record: bool) -> None:
        self._saves.flush()
        self._node_id, self._edge_id = node_id, edge_id
        self._canvas.set_selection(node_id, edge_id)
        if node_id is not None:
            self._canvas.reveal(node_id)
        self._refresh_panel()
        if record:
            self.navigated.emit(self.current_target())
            self.panel_requested.emit()

    def _select_node(self, node_id: int, record: bool = True) -> None:
        self._select(node_id, None, record)

    def _select_edge(self, edge_id: int, record: bool = True) -> None:
        self._select(None, edge_id, record)

    def _deselect(self) -> None:
        self._select(None, None, record=False)

    # --- Nodi ----------------------------------------------------------------------------------------
    def _add_node(self, x: float, y: float) -> None:
        """Clic sulla tela con lo strumento «Nodo»: il nodo nasce subito e il cursore è già nel suo titolo."""
        try:
            node_id = self._repo.create_node(self._graph_id, x, y, NodeInput(NEW_NODE_TITLE, "", NEW_NODE_COLOR, None))
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
            return
        self._canvas.set_tool(SELECT)
        self._saves.flush()
        self._refresh_graph()
        self._select_node(node_id)
        self._panel.focus_title()

    def _move_node(self, node_id: int, x: float, y: float) -> None:
        try:
            self._repo.move_node(node_id, x, y)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
            self._refresh_graph()
            return
        self._nodes[node_id] = replace(self._nodes[node_id], x=x, y=y)

    def _edit_node(self, now: bool = False, **changes) -> None:
        """Cambia titolo, descrizione o colore del nodo scelto: si vede subito sulla tela e si salva poco dopo (con `now`, subito)."""
        node = self._nodes[self._node_id] = replace(self._nodes[self._node_id], **changes)
        self._canvas.preview_node(node)
        self._saves.add(("node", node.id), lambda: self._save_node(node.id))
        if now:
            self._saves.flush()
            self._refresh_panel()

    def _save_node(self, node_id: int) -> None:
        node = self._nodes[node_id]
        link = (node.link.kind, node.link.id) if node.link is not None else None
        self._repo.update_node(node_id, NodeInput(node.title, node.description, node.color, link))

    def _delete_node(self) -> None:
        self._saves.flush()
        try:
            self._repo.delete_node(self._node_id)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self._node_id = None
        self._refresh_graph()

    # --- Il collegamento di un nodo con una pagina o un elemento ------------------------------------
    def _choose_link(self) -> None:
        popup = LinkPickerPopup(self, lambda query, limit: self._repo.link_targets(query, limit=limit, views=False), "Collega il nodo a…",
                                "Il nodo prenderà il titolo dalla pagina o dall'elemento che scegli; la descrizione resta sua.")
        if popup.exec() == QDialog.Accepted:
            self._edit_node(link=popup.target, title=popup.target.name, now=True)
            self._refresh_graph()          # il titolo ora è quello di ciò a cui è collegato

    def _open_link(self) -> None:
        link = self._nodes[self._node_id].link
        self.open_requested.emit(*link_destination(link.kind, link.id))

    def _unlink(self) -> None:
        """Il nodo non è più collegato: tiene come titolo quello che aveva."""
        self._edit_node(link=None, now=True)
        self._refresh_graph()

    # --- Archi ----------------------------------------------------------------------------------------
    def _connect(self, first: Endpoint, second: Endpoint) -> None:
        """Con lo strumento «Collega»: crea l'arco fra i due estremi, nodi o archi (se c'è già, sceglie quello) e lo sceglie, pronto per l'etichetta."""
        self._saves.flush()
        try:
            edge_id = self._repo.create_edge(first, second)
        except DatabaseError as error:
            existing = next((edge for edge in self._edges.values() if {edge.a, edge.b} == {first, second}), None)
            if existing is None:
                QMessageBox.warning(self, "GM Journal", str(error))
                return
            edge_id = existing.id
        self._canvas.set_tool(SELECT)
        self._refresh_graph()
        self._select_edge(edge_id)
        self._panel.focus_label()

    def _edit_edge(self, now: bool = False, **changes) -> None:
        """Cambia l'etichetta o la direzione dell'arco scelto: si vede subito sulla tela e si salva poco dopo (con `now`, subito)."""
        edge = self._edges[self._edge_id] = replace(self._edges[self._edge_id], **changes)
        self._canvas.preview_edge(edge)
        self._saves.add(("edge", edge.id), lambda: self._save_edge(edge.id))
        if now:
            self._saves.flush()
            self._refresh_panel()

    def _save_edge(self, edge_id: int) -> None:
        edge = self._edges[edge_id]
        self._repo.update_edge(edge_id, edge.label, edge.direction)

    def _delete_edge(self) -> None:
        self._saves.flush()
        try:
            self._repo.delete_edge(self._edge_id)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self._edge_id = None
        self._refresh_graph()
