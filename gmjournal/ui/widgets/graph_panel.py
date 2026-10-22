"""Il pannello destro dei Grafi: l'elenco dei nodi del grafo aperto oppure, scelto un nodo o un arco, i suoi campi.

Il pannello mostra e raccoglie: dice con dei segnali cosa è stato scritto o premuto, e la schermata salva."""

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

from ... import icons, theme
from ...data.models import GraphEdge, GraphNode
from ...data.repository import NAME_MAX
from ...graphs import BOTH, DESCRIPTION_MAX, KIND_NODE, LABEL_MAX, NO_ARROW, TO_A, TO_B, Endpoint
from ..kinds import kind_icon, target_caption
from ..popups.base import field_label
from .color_swatch import ColorPicker
from .group_label import group_label
from .hold_button import HoldButton
from .icon_label import IconLabel
from .list_row import ListRow

_OVERVIEW_PAGE, _NODE_PAGE, _EDGE_PAGE = 0, 1, 2
_NO_LABEL = "Senza etichetta"
_DIRECTIONS = ((NO_ARROW, "minus", "Nessuna freccia"), (TO_B, "arrow-down", "Freccia verso l'elemento in basso"),
               (TO_A, "arrow-up", "Freccia verso l'elemento in alto"), (BOTH, "arrow-up-down", "Frecce da entrambe le parti"))
_LINK_NAME_WIDTH = 150          # larghezza oltre la quale il nome di ciò a cui è collegato il nodo viene accorciato


@dataclass(frozen=True)
class EndInfo:
    """Come si presenta nel pannello un nodo o un arco (un estremo di un arco): la schermata la prepara, il pannello la mostra."""
    end: Endpoint
    title: str
    caption: str
    color: str          # colore già risolto (esadecimale)
    icon: str


def _text_button(text: str, object_name: str, on_click) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(object_name)
    button.setCursor(Qt.PointingHandCursor)
    button.setFocusPolicy(Qt.NoFocus)
    button.clicked.connect(lambda _=False: on_click())
    return button


class _Page(QScrollArea):
    """Una pagina del pannello: una colonna che scorre se non ci sta."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(14, 18, 14, 14)
        self.column = QVBoxLayout()
        self.column.setSpacing(0)
        outer.addLayout(self.column)
        outer.addStretch(1)          # lo spazio che avanza va in fondo, non fra i campi
        self.setWidget(content)
        content.setAutoFillBackground(False)     # lo sfondo è quello del pannello


class GraphPanel(QFrame):
    back_requested = Signal()                   # «‹ nome del grafo»
    node_chosen = Signal(int)                   # un nodo o un arco scelto in un elenco
    edge_chosen = Signal(int)
    title_edited = Signal(str)
    description_edited = Signal(str)
    color_chosen = Signal(str)                  # chiave in theme.CATEGORY_COLORS
    label_edited = Signal(str)
    direction_chosen = Signal(int)              # uno di NO_ARROW, TO_B, TO_A, BOTH
    link_requested = Signal()                   # «Collega a…» e «Cambia»
    open_link_requested = Signal()
    unlink_requested = Signal()
    node_delete_confirmed = Signal()
    edge_delete_confirmed = Signal()

    def __init__(self):
        super().__init__()
        self._saved_title = ""                  # l'ultimo titolo valido: se si svuota il campo e si esce, torna questo
        self._stack = QStackedWidget()
        self._stack.addWidget(self._make_overview())    # _OVERVIEW_PAGE
        self._stack.addWidget(self._make_node_page())   # _NODE_PAGE
        self._stack.addWidget(self._make_edge_page())   # _EDGE_PAGE
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

    # --- Costruzione -------------------------------------------------------------------------------
    def _back_button(self) -> QToolButton:
        back = QToolButton()
        back.setObjectName("BackLink")
        back.setIcon(icons.icon("chevron-left", theme.MUTED))
        back.setIconSize(QSize(15, 15))
        back.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        back.setCursor(Qt.PointingHandCursor)
        back.setFocusPolicy(Qt.NoFocus)
        back.clicked.connect(lambda _=False: self.back_requested.emit())
        return back

    def _make_overview(self) -> QWidget:
        page = _Page()
        self._overview_title = QLabel()
        self._overview_title.setFont(theme.serif_font(24, 500, -0.01))
        self._overview_title.setWordWrap(True)
        self._overview_count = group_label()
        self._overview_rows = QVBoxLayout()
        self._overview_rows.setSpacing(1)
        self._overview_empty = QLabel()
        self._overview_empty.setObjectName("Muted")
        self._overview_empty.setWordWrap(True)
        page.column.addWidget(self._overview_title)
        page.column.addSpacing(18)
        page.column.addWidget(self._overview_count)
        page.column.addSpacing(6)
        page.column.addLayout(self._overview_rows)
        page.column.addWidget(self._overview_empty)
        return page

    def _make_node_page(self) -> QWidget:
        page = _Page()
        self._node_back = self._back_button()

        self._title = QLineEdit()
        self._title.setFixedHeight(40)
        self._title.setMaxLength(NAME_MAX)
        self._title.setFont(theme.ui_font(15))
        self._title.textEdited.connect(self._on_title_edited)
        self._title.editingFinished.connect(self._restore_title)
        self._free = QWidget()
        free = QVBoxLayout(self._free)
        free.setContentsMargins(0, 0, 0, 0)
        free.setSpacing(8)
        free.addWidget(field_label("Titolo"))
        free.addWidget(self._title)
        link = QPushButton(" Collega a una pagina o un elemento…")
        link.setObjectName("DashedButton")
        link.setIcon(icons.icon("link", theme.ACCENT))
        link.setIconSize(QSize(15, 15))
        link.setCursor(Qt.PointingHandCursor)
        link.setFocusPolicy(Qt.NoFocus)
        link.clicked.connect(lambda _=False: self.link_requested.emit())
        free.addWidget(link)

        self._link_icon = IconLabel("file", theme.TEXT_SOFT, 16)
        self._link_name, self._link_caption = QLabel(), QLabel()
        self._link_name.setFont(theme.ui_font(14, 500))
        self._link_caption.setObjectName("Muted")
        self._link_caption.setFont(theme.ui_font(12))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(self._link_name)
        texts.addWidget(self._link_caption)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self._link_icon)
        head.addLayout(texts, 1)
        actions = QHBoxLayout()
        actions.setSpacing(0)
        actions.addWidget(_text_button("Apri", "LinkButton", self.open_link_requested.emit))
        actions.addWidget(_text_button("Cambia", "LinkButton", self.link_requested.emit))
        actions.addWidget(_text_button("Scollega", "LinkButton", self.unlink_requested.emit))
        actions.addStretch()
        box = QFrame()
        box.setObjectName("InfoBox")
        inside = QVBoxLayout(box)
        inside.setContentsMargins(12, 10, 12, 4)
        inside.setSpacing(2)
        inside.addLayout(head)
        inside.addLayout(actions)
        self._linked = QWidget()
        linked = QVBoxLayout(self._linked)
        linked.setContentsMargins(0, 0, 0, 0)
        linked.setSpacing(8)
        linked.addWidget(field_label("Titolo", "(è quello della pagina o dell'elemento)"))
        linked.addWidget(box)

        self._description = QPlainTextEdit()
        self._description.setFixedHeight(120)
        self._description.setPlaceholderText("Di cosa si tratta, in poche righe…")
        self._description.textChanged.connect(self._on_description_changed)

        self._colors = ColorPicker(spacing=4)
        self._colors.chosen.connect(self.color_chosen)

        self._arcs_label, self._arcs = group_label(), self._rows_layout()
        delete = HoldButton("Tieni premuto per eliminare il nodo")
        delete.confirmed.connect(self.node_delete_confirmed)

        column = page.column
        column.addWidget(self._node_back, alignment=Qt.AlignLeft)
        column.addSpacing(14)
        column.addWidget(self._free)
        column.addWidget(self._linked)
        column.addSpacing(16)
        column.addWidget(field_label("Descrizione", f"(max {DESCRIPTION_MAX} caratteri)"))
        column.addSpacing(6)
        column.addWidget(self._description)
        column.addSpacing(16)
        column.addWidget(field_label("Colore"))
        column.addSpacing(4)
        column.addWidget(self._colors)
        column.addSpacing(20)
        column.addWidget(self._arcs_label)
        column.addSpacing(6)
        column.addLayout(self._arcs)
        column.addSpacing(24)
        column.addWidget(delete, alignment=Qt.AlignLeft)
        return page

    def _make_edge_page(self) -> QWidget:
        page = _Page()
        self._edge_back = self._back_button()
        self._from_row, self._to_row = QVBoxLayout(), QVBoxLayout()
        self._edge_arcs_label, self._edge_arcs = group_label(), self._rows_layout()
        self._directions = QButtonGroup(self)
        arrows = QHBoxLayout()
        arrows.setSpacing(4)
        arrows.setContentsMargins(8, 0, 0, 0)
        for value, icon_name, tooltip in _DIRECTIONS:
            button = QToolButton()
            button.setObjectName("BarButton")
            button.setCheckable(True)
            button.setIcon(icons.icon(icon_name, theme.TEXT_SOFT))
            button.setIconSize(QSize(18, 18))
            button.setFixedSize(36, 36)
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            self._directions.addButton(button, value)
            arrows.addWidget(button)
        arrows.addStretch()
        self._directions.idClicked.connect(self.direction_chosen)
        self._label = QLineEdit()
        self._label.setFixedHeight(40)
        self._label.setMaxLength(LABEL_MAX)
        self._label.setFont(theme.ui_font(15))
        self._label.setPlaceholderText("Es. è alleato di, tradisce…")
        self._label.textEdited.connect(self.label_edited)
        delete = HoldButton("Tieni premuto per eliminare l'arco")
        delete.confirmed.connect(self.edge_delete_confirmed)

        column = page.column
        column.addWidget(self._edge_back, alignment=Qt.AlignLeft)
        column.addSpacing(14)
        title = QLabel("Arco")
        title.setFont(theme.serif_font(24, 500, -0.01))
        column.addWidget(title)
        column.addSpacing(18)
        column.addWidget(group_label("ELEMENTI COLLEGATI"))
        column.addSpacing(6)
        column.addLayout(self._from_row)
        column.addLayout(arrows)
        column.addLayout(self._to_row)
        column.addSpacing(18)
        column.addWidget(field_label("Etichetta", "(facoltativa)"))
        column.addSpacing(6)
        column.addWidget(self._label)
        column.addSpacing(20)
        column.addWidget(self._edge_arcs_label)
        column.addSpacing(6)
        column.addLayout(self._edge_arcs)
        column.addSpacing(24)
        column.addWidget(delete, alignment=Qt.AlignLeft)
        return page

    # --- Mostrare ----------------------------------------------------------------------------------
    @staticmethod
    def _rows_layout() -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(1)
        return layout

    @staticmethod
    def _clear(layout: QVBoxLayout) -> None:
        while layout.count():
            layout.takeAt(0).widget().deleteLater()

    def _row(self, info: EndInfo, caption: str | None = None, edge_id: int | None = None) -> ListRow:
        """Una riga con un nodo o un arco; premendola si passa a lui (o, con `edge_id`, a quell'arco)."""
        row = ListRow(info.color, info.icon, info.title, info.caption if caption is None else caption)
        if edge_id is not None:
            row.clicked.connect(lambda _=False: self.edge_chosen.emit(edge_id))
        else:
            signal = self.node_chosen if info.end.kind == KIND_NODE else self.edge_chosen
            row.clicked.connect(lambda _=False: signal.emit(info.end.id))
        return row

    def _fill_arcs(self, label: QLabel, layout: QVBoxLayout, arcs: list[tuple[GraphEdge, EndInfo]]) -> None:
        """L'elenco degli archi che finiscono su un nodo o su un arco: ogni riga mostra l'elemento dall'altra parte e, sotto, l'etichetta
        dell'arco; premendola si passa all'arco."""
        self._clear(layout)
        for edge, other in arcs:
            layout.addWidget(self._row(other, edge.label or _NO_LABEL, edge.id))
        label.setText(f"ARCHI  ·  {len(arcs)}")

    def show_overview(self, name: str, nodes: list[EndInfo], empty: str) -> None:
        """Il grafo aperto con l'elenco dei suoi nodi. `empty` è ciò che si legge se non ce ne sono."""
        self._overview_title.setText(name)
        self._clear(self._overview_rows)
        for info in nodes:
            self._overview_rows.addWidget(self._row(info))
        self._overview_count.setText(f"NODI DEL GRAFO  ·  {len(nodes)}")
        self._overview_empty.setText(empty)
        self._overview_empty.setVisible(not nodes)
        self._stack.setCurrentIndex(_OVERVIEW_PAGE)

    def show_node(self, graph_name: str, node: GraphNode, arcs: list[tuple[GraphEdge, EndInfo]]) -> None:
        """I campi di un nodo. `arcs`: i suoi archi, ognuno con ciò che sta dall'altra parte."""
        self._node_back.setText(graph_name)
        linked = node.link is not None
        self._free.setVisible(not linked)
        self._linked.setVisible(linked)
        if linked:
            self._link_icon.set_icon(kind_icon(node.link.kind), theme.TEXT_SOFT)
            self._link_name.setText(QFontMetrics(self._link_name.font()).elidedText(node.title, Qt.ElideRight, _LINK_NAME_WIDTH))
            self._link_caption.setText(target_caption(node.link))
        else:
            self._saved_title = node.title
            self._set_text(self._title, node.title)
        self._set_text(self._description, node.description)
        self._colors.set_value(node.color)
        self._fill_arcs(self._arcs_label, self._arcs, arcs)
        self._stack.setCurrentIndex(_NODE_PAGE)

    def show_edge(self, graph_name: str, edge: GraphEdge, a: EndInfo, b: EndInfo, arcs: list[tuple[GraphEdge, EndInfo]]) -> None:
        """I campi di un arco: i suoi due estremi e gli archi che finiscono sulla sua etichetta (`arcs`, come per un nodo)."""
        self._edge_back.setText(graph_name)
        for layout, info in ((self._from_row, a), (self._to_row, b)):
            self._clear(layout)
            layout.addWidget(self._row(info))
        self._set_text(self._label, edge.label)
        self._directions.button(edge.direction).setChecked(True)
        self._fill_arcs(self._edge_arcs_label, self._edge_arcs, arcs)
        self._stack.setCurrentIndex(_EDGE_PAGE)

    def focus_title(self) -> None:
        """Il cursore nel titolo del nodo (con tutto il testo selezionato, pronto da sostituire)."""
        self._title.setFocus()
        self._title.selectAll()

    def focus_label(self) -> None:
        self._label.setFocus()

    # --- Scrivere ----------------------------------------------------------------------------------
    @staticmethod
    def _set_text(field: QLineEdit | QPlainTextEdit, text: str) -> None:
        """Scrive nel campo senza far credere che l'abbia scritto l'utente."""
        current = field.toPlainText() if isinstance(field, QPlainTextEdit) else field.text()
        if current == text:
            return
        field.blockSignals(True)
        if isinstance(field, QPlainTextEdit):
            field.setPlainText(text)
        else:
            field.setText(text)
        field.blockSignals(False)

    def _on_title_edited(self, text: str) -> None:
        if text.strip():            # un titolo vuoto non si salva: si aspetta che ne scriva un altro
            self._saved_title = text
            self.title_edited.emit(text)

    def _restore_title(self) -> None:
        if not self._title.text().strip():
            self._set_text(self._title, self._saved_title)

    def _on_description_changed(self) -> None:
        text = self._description.toPlainText()
        if len(text) > DESCRIPTION_MAX:
            text = text[:DESCRIPTION_MAX]
            self._set_text(self._description, text)
            self._description.moveCursor(QTextCursor.End)
        self.description_edited.emit(text)
