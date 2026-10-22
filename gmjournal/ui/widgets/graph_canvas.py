"""La tela di un grafo: nodi trascinabili collegati da archi con etichetta (un arco può finire anche su un altro arco, cioè sulla sua
etichetta), strumenti «Nodo» e «Collega», zoom e spostamento.

Il widget mostra e raccoglie i gesti; non tocca i dati: dice cosa è successo con dei segnali e la schermata decide.
Le posizioni dei nodi sono coordinate della tela (il loro centro); la tela è molto più grande di qualunque grafo.
"""

import math
from functools import cache

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsScene, QLabel

from ... import icons, theme
from ...data.models import GraphEdge, GraphNode
from ...graphs import BOTH, KIND_EDGE, KIND_NODE, TO_A, TO_B, Endpoint
from ..kinds import kind_icon
from .canvas_base import HintPill, ToolBar, ZoomView

SELECT, NODE, CONNECT = "select", "node", "connect"      # gli strumenti
NODE_WIDTH = 200
_COLOR = theme.SECTION_COLORS["grafi"]
_TOOLS = ((SELECT, "pointer", "Seleziona"), (NODE, "circle-plus", "Nodo"), (CONNECT, "connect", "Collega"))
_HINTS = {NODE: "Clicca sulla tela per aggiungere un nodo", CONNECT: "Clicca il primo nodo o arco, poi il secondo"}
_HINT_SECOND = "Ora clicca il secondo nodo o arco"
_EMPTY = "Questo grafo è vuoto. Scegli lo strumento «Nodo» e clicca sulla tela."
_SCENE = 20000                  # la tela va da -_SCENE a +_SCENE in entrambe le direzioni
_MIN_SCALE, _MAX_SCALE = 0.2, 3.0
_FIT_MARGIN = 60
_TOOLS_ROOM = 64                  # a sinistra l'inquadratura lascia posto alla barra degli strumenti
_GRID = 28                      # distanza fra i puntini dello sfondo
_PAD = 12
_STRIP = 4                       # altezza della striscia colorata in cima al nodo
_MAX_LINES = 3                  # righe della descrizione che si vedono nel nodo
_ARROW = 12                     # lunghezza della punta di una freccia, in pixel dello schermo
_ARROW_ROOM = 8 + 5 * _ARROW    # margine attorno all'arco per la punta (a zoom piccolo, in coordinate della tela, è più grande)
_DOT = 5                         # raggio del puntino che mostra dove finisce un arco su un arco senza etichetta
_DRAG_START = 4                 # pixel di spostamento oltre i quali un clic diventa un trascinamento
_TEXT_LOD = 0.3                 # sotto questo zoom i testi sarebbero illeggibili: non si disegnano (e un grafo grande resta fluido)


def _pen(color: str, width: float, cosmetic: bool = False) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCosmetic(cosmetic)
    return pen


# penne e colori fissi, creati una volta sola: ogni nodo e ogni arco si ridisegna a ogni gesto di zoom o di spostamento
_SHADOW, _SURFACE, _BG = QColor(0, 0, 0, 90), QColor(theme.SURFACE), QColor(theme.BG)
_TITLE_TEXT, _BODY_TEXT = QColor(theme.TEXT_ACTIVE), QColor(theme.TEXT_SOFT)
_NODE_BORDER, _NODE_BORDER_HOVER = _pen(theme.BORDER_STRONG, 1), _pen(theme.MUTED, 1)
_EDGE_LINE, _EDGE_LINE_HOVER, _EDGE_LINE_SELECTED = _pen(theme.DISABLED, 1.6, True), _pen(theme.MUTED, 1.6, True), _pen(theme.ACCENT, 2.2, True)
_PILL_BORDER, _PILL_BORDER_SELECTED = _pen(theme.BORDER_STRONG, 1), _pen(theme.ACCENT, 1)


@cache
def _title_font() -> QFont:
    return theme.ui_font(14, 600)


@cache
def _text_font() -> QFont:
    return theme.ui_font(12)


def _wrap(text: str, metrics: QFontMetrics, width: int, max_lines: int) -> list[str]:
    """`text` spezzato in righe larghe al massimo `width`; oltre `max_lines` l'ultima finisce con «…»."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if metrics.horizontalAdvance(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while metrics.horizontalAdvance(word) > width:      # una parola più larga della riga va spezzata
                cut = next(n for n in range(len(word) - 1, 0, -1) if metrics.horizontalAdvance(word[:n]) <= width or n == 1)
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        if current:
            lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = metrics.elidedText(lines[-1] + "…", Qt.ElideRight, width)
    return lines


class NodeItem(QGraphicsItem):
    """Un nodo: una scheda con una striscia del suo colore in alto, il titolo e le prime righe della descrizione. La posizione è il suo centro."""

    def __init__(self, node: GraphNode):
        super().__init__()
        self.node_id = node.id
        self.endpoint = Endpoint(KIND_NODE, node.id)
        self.edges: list["EdgeItem"] = []            # gli archi che finiscono su questo nodo
        self._selected = self._hovered = self._armed = False
        self._rect = QRectF()
        self._outline, self._strip = QPainterPath(), QPainterPath()     # il contorno e la striscia del colore, tagliata sugli angoli
        self._lines: list[str] = []
        self._title, self._icon, self._color = "", None, QColor(theme.CATEGORY_COLORS["gray"][1])
        self._title_at, self._icon_rect, self._lines_at = QPointF(), QRectF().toRect(), []    # dove si disegnano i testi
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(5)
        self.setPos(node.x, node.y)
        self.set_node(node)

    def set_node(self, node: GraphNode) -> None:
        """Titolo, descrizione, colore e collegamento; la scheda si ridimensiona."""
        self.prepareGeometryChange()
        self._color = QColor(theme.category_color(node.color))
        self._icon = kind_icon(node.link.kind) if node.link is not None else None
        title_metrics, text_metrics = QFontMetrics(_title_font()), QFontMetrics(_text_font())
        text_width = NODE_WIDTH - 2 * _PAD - (22 if self._icon else 0)
        self._title = title_metrics.elidedText(node.title, Qt.ElideRight, text_width)
        self._lines = _wrap(node.description, text_metrics, NODE_WIDTH - 2 * _PAD, _MAX_LINES)
        height = _STRIP + 2 * _PAD + title_metrics.height() + (6 + len(self._lines) * text_metrics.lineSpacing() if self._lines else 0)
        self._rect = QRectF(-NODE_WIDTH / 2, -height / 2, NODE_WIDTH, height)
        self._outline = QPainterPath()
        self._outline.addRoundedRect(self._rect, 10, 10)
        strip = QPainterPath()
        strip.addRect(QRectF(self._rect.left(), self._rect.top(), self._rect.width(), _STRIP))
        self._strip = self._outline.intersected(strip)
        left, top = self._rect.left() + _PAD, self._rect.top() + _STRIP + _PAD
        self._title_at = QPointF(left, top + title_metrics.ascent())
        size = 14
        self._icon_rect = QRectF(self._rect.right() - _PAD - size, top + (title_metrics.height() - size) / 2, size, size).toRect()
        y = top + title_metrics.height() + 6
        self._lines_at = []
        for _ in self._lines:
            self._lines_at.append(QPointF(left, y + text_metrics.ascent()))
            y += text_metrics.lineSpacing()
        for edge in self.edges:
            edge.refresh()
        self.update()

    def center(self) -> QPointF:
        return self.pos()

    def body(self) -> QRectF:
        """Il rettangolo del nodo, attorno al suo centro (l'origine)."""
        return self._rect

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setZValue(10 if selected else 5)
        self.update()

    def set_hovered(self, hovered: bool) -> None:
        self._hovered = hovered
        self.update()

    def set_armed(self, armed: bool) -> None:
        self._armed = armed
        self.update()

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-8, -8, 8, 10)

    def shape(self) -> QPainterPath:
        return self._outline

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges:
                edge.refresh()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(_SHADOW)
        painter.drawRoundedRect(self._rect.translated(0, 3), 10, 10)
        painter.setBrush(_SURFACE)
        painter.drawPath(self._outline)
        painter.fillPath(self._strip, self._color)
        if self._selected or self._armed:
            painter.setPen(QPen(QColor(theme.ACCENT) if self._armed else self._color, 2, Qt.DashLine if self._armed else Qt.SolidLine))
        else:
            painter.setPen(_NODE_BORDER_HOVER if self._hovered else _NODE_BORDER)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self._rect.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        if option.levelOfDetailFromTransform(painter.worldTransform()) < _TEXT_LOD:
            return
        painter.setFont(_title_font())
        painter.setPen(_TITLE_TEXT)
        painter.drawText(self._title_at, self._title)
        if self._icon:
            icons.icon(self._icon, theme.MUTED).paint(painter, self._icon_rect)
        painter.setFont(_text_font())
        painter.setPen(_BODY_TEXT)
        for at, line in zip(self._lines_at, self._lines):
            painter.drawText(at, line)


def _border_point(rect: QRectF, center: QPointF, toward: QPointF) -> QPointF:
    """Il punto in cui la retta dal centro di un nodo verso `toward` esce dal suo rettangolo."""
    dx, dy = toward.x() - center.x(), toward.y() - center.y()
    if dx == 0 and dy == 0:
        return center
    scale = min(rect.width() / 2 / abs(dx) if dx else math.inf, rect.height() / 2 / abs(dy) if dy else math.inf)
    return QPointF(center.x() + dx * scale, center.y() + dy * scale)


def _arrow_head(origin: QPointF, tip: QPointF, size: float) -> QPolygonF:
    """Un triangolo con la punta in `tip`, rivolto nel verso che va da `origin` a `tip`."""
    angle = math.atan2(tip.y() - origin.y(), tip.x() - origin.x())
    left, right = angle + math.radians(155), angle - math.radians(155)
    return QPolygonF([tip, QPointF(tip.x() + size * math.cos(left), tip.y() + size * math.sin(left)),
                      QPointF(tip.x() + size * math.cos(right), tip.y() + size * math.sin(right))])


class EdgeItem(QGraphicsItem):
    """Un arco: una linea fra due estremi (nodi o altri archi), con l'etichetta a metà e, se ha una direzione, una punta di freccia su uno
    o su entrambi i capi. A sua volta è un possibile estremo: gli archi che ci finiscono arrivano alla sua etichetta (o a un puntino)."""

    def __init__(self, edge: GraphEdge, a: "NodeItem | EdgeItem", b: "NodeItem | EdgeItem"):
        super().__init__()
        self.edge_id = edge.id
        self.endpoint = Endpoint(KIND_EDGE, edge.id)
        self.a, self.b = a, b
        self.edges: list["EdgeItem"] = []            # gli archi che finiscono su questo arco
        self._label, self._direction = edge.label, edge.direction
        self._selected = self._hovered = self._armed = False
        self._line: tuple[QPointF, QPointF] | None = None
        self._pill = QRectF()
        self._middle = QPointF()                     # il punto a metà della linea: dove arrivano gli archi che finiscono qui
        self._dot = False
        self._body = QRectF()
        self._bounds = QRectF()
        self._shape: QPainterPath | None = None             # si calcola alla prima richiesta (serve solo per capire cosa c'è sotto il puntatore)
        self.setZValue(1)
        a.edges.append(self)
        b.edges.append(self)
        self.refresh()
        for end in (a, b):
            if isinstance(end, EdgeItem):
                end.refresh()           # ora ha un arco che ci finisce sopra: se non ha l'etichetta deve mostrare il puntino

    def set_edge(self, edge: GraphEdge) -> None:
        """Etichetta e direzione (le modifiche si vedono subito, prima di essere salvate)."""
        self._label, self._direction = edge.label, edge.direction
        self.refresh()

    def center(self) -> QPointF:
        return self._middle

    def body(self) -> QRectF:
        """Il rettangolo dell'etichetta (o del puntino), attorno al centro dell'arco; vuoto se non si vede nulla."""
        return self._body

    def on_body(self, scene_point: QPointF) -> bool:
        return self._body.translated(self._middle).contains(scene_point)

    def refresh(self) -> None:
        """Ricalcola la linea e l'etichetta (gli estremi si sono spostati o è cambiato il testo), poi gli archi che ci finiscono."""
        self.prepareGeometryChange()
        pa, pb = self.a.center(), self.b.center()
        start, end = _border_point(self.a.body(), pa, pb), _border_point(self.b.body(), pb, pa)
        # se gli estremi si sovrappongono la linea non avrebbe senso: i punti sarebbero incrociati
        crossed = (end.x() - start.x()) * (pb.x() - pa.x()) + (end.y() - start.y()) * (pb.y() - pa.y()) <= 0
        self._line = None if crossed else (start, end)
        self._middle = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2) if self._line else QPointF((pa.x() + pb.x()) / 2, (pa.y() + pb.y()) / 2)
        self._pill = self._body = QRectF()
        self._dot = self._line is not None and not self._label and bool(self.edges)
        if self._line is not None and self._label:
            metrics = QFontMetrics(_text_font())
            width, height = metrics.horizontalAdvance(self._label) + 18, metrics.height() + 6
            self._body = QRectF(-width / 2, -height / 2, width, height)
            self._pill = self._body.translated(self._middle)
        elif self._dot:
            self._body = QRectF(-_DOT, -_DOT, 2 * _DOT, 2 * _DOT)
        self._bounds = (QRectF(*self._line).normalized() if self._line is not None else QRectF()).united(self._pill)
        self._bounds.adjust(-_ARROW_ROOM, -_ARROW_ROOM, _ARROW_ROOM, _ARROW_ROOM)
        self._shape = None
        self.update()
        for edge in self.edges:
            edge.refresh()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setZValue(3 if selected else 1)
        self.update()

    def set_hovered(self, hovered: bool) -> None:
        self._hovered = hovered
        self.update()

    def set_armed(self, armed: bool) -> None:
        self._armed = armed
        self.update()

    def boundingRect(self) -> QRectF:
        return self._bounds

    def shape(self) -> QPainterPath:
        if self._shape is None:
            path = QPainterPath()
            if self._line is not None:
                path.moveTo(self._line[0])
                path.lineTo(self._line[1])
            stroker = QPainterPathStroker()
            stroker.setWidth(14)
            self._shape = stroker.createStroke(path)
            self._shape.addRoundedRect(self._pill, 9, 9)
            if self._dot:
                self._shape.addEllipse(self._middle, 2 * _DOT, 2 * _DOT)
        return self._shape

    def paint(self, painter: QPainter, option, widget=None) -> None:
        if self._line is None:
            return
        zoom = option.levelOfDetailFromTransform(painter.worldTransform()) or 1
        painter.setRenderHint(QPainter.Antialiasing)
        pen = _EDGE_LINE_SELECTED if self._selected or self._armed else _EDGE_LINE_HOVER if self._hovered else _EDGE_LINE
        painter.setPen(pen)
        painter.drawLine(*self._line)
        painter.setPen(Qt.NoPen)
        painter.setBrush(pen.color())
        size = _ARROW / zoom                                         # la punta ha sempre la stessa misura sullo schermo
        start, end = self._line
        if self._direction in (TO_B, BOTH):
            painter.drawPolygon(_arrow_head(start, end, size))
        if self._direction in (TO_A, BOTH):
            painter.drawPolygon(_arrow_head(end, start, size))
        if self._dot:
            painter.drawEllipse(self._middle, _DOT, _DOT)
        if not self._pill.isEmpty() and zoom >= _TEXT_LOD:
            painter.setPen(_PILL_BORDER_SELECTED if self._selected or self._armed else _PILL_BORDER)
            painter.setBrush(_BG)
            painter.drawRoundedRect(self._pill, 9, 9)
            painter.setFont(_text_font())
            painter.setPen(_TITLE_TEXT if self._selected else _BODY_TEXT)
            painter.drawText(self._pill, Qt.AlignCenter, self._label)


class GraphCanvas(ZoomView):
    node_clicked = Signal(int)
    edge_clicked = Signal(int)
    background_clicked = Signal()
    node_moved = Signal(int, float, float)          # ID, nuovo centro
    add_requested = Signal(float, float)            # clic sulla tela con lo strumento «Nodo»
    connect_requested = Signal(Endpoint, Endpoint)  # i due estremi (nodi o archi) scelti con lo strumento «Collega»
    tool_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-_SCENE, -_SCENE, 2 * _SCENE, 2 * _SCENE)
        self._scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setScene(self._scene)
        self._min_scale, self._max_scale = _MIN_SCALE, _MAX_SCALE
        self._nodes: dict[int, NodeItem] = {}
        self._edges: dict[int, EdgeItem] = {}
        self._selected_node: int | None = None
        self._selected_edge: int | None = None
        self._hovered: NodeItem | EdgeItem | None = None
        self._armed: NodeItem | EdgeItem | None = None
        self._rubber: QGraphicsLineItem | None = None
        self._tool = SELECT
        self._fitted = True                             # finché non si fa zoom o ci si sposta, il grafo resta inquadrato per intero
        self._press: QPoint | None = None
        self._press_item: NodeItem | EdgeItem | None = None
        self._grab = QPointF()                          # dove, rispetto al centro del nodo, lo si è afferrato
        self._last = QPoint()
        self._moved = False

        self._hint = HintPill("circle-plus", _COLOR)
        self._hint.setParent(self)
        self._tools = ToolBar(_TOOLS, (("plus", "Ingrandisci", lambda: self._user_zoom(1.25)), ("minus", "Riduci", lambda: self._user_zoom(0.8)),
                                       ("maximize", "Inquadra tutto", self.fit_all)), _COLOR)
        self._tools.setParent(self)
        self._tools.tool_chosen.connect(self._set_tool)
        self._empty = QLabel(_EMPTY, self)
        self._empty.setFont(theme.ui_font(14))
        self._empty.setStyleSheet(f"color: {theme.MUTED}; background: transparent;")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._update_overlays()

    # --- Contenuto ---------------------------------------------------------------------------------
    def set_graph(self, nodes: list[GraphNode], edges: list[GraphEdge], refit: bool = False) -> None:
        """Mostra questi nodi e archi al posto di quelli di prima (la selezione resta, se esiste ancora). Con `refit` il grafo si inquadra."""
        self._cancel_connection()
        self._scene.clear()
        self._nodes, self._edges, self._hovered = {}, {}, None
        for node in nodes:
            item = self._nodes[node.id] = NodeItem(node)
            self._scene.addItem(item)
        for edge in edges:          # in ordine di ID: un arco finisce soltanto su archi già creati
            item = self._edges[edge.id] = EdgeItem(edge, self._item(edge.a), self._item(edge.b))
            self._scene.addItem(item)
        self.set_selection(self._selected_node, self._selected_edge)
        if refit:
            self._fitted = True
            self.fit_all(user=False)
        self._update_overlays()

    def _item(self, end: Endpoint) -> NodeItem | EdgeItem:
        return (self._nodes if end.kind == KIND_NODE else self._edges)[end.id]

    def set_selection(self, node_id: int | None = None, edge_id: int | None = None) -> None:
        """Il nodo o l'arco scelto (uno solo dei due, o nessuno)."""
        self._selected_node = node_id if node_id in self._nodes else None
        self._selected_edge = edge_id if edge_id in self._edges and self._selected_node is None else None
        for item_id, item in self._nodes.items():
            item.set_selected(item_id == self._selected_node)
        for item_id, edge in self._edges.items():
            edge.set_selected(item_id == self._selected_edge)

    def preview_node(self, node: GraphNode) -> None:
        """Mostra subito le modifiche a un nodo (mentre si scrive, prima che siano salvate)."""
        self._nodes[node.id].set_node(node)

    def preview_edge(self, edge: GraphEdge) -> None:
        self._edges[edge.id].set_edge(edge)

    def reveal(self, node_id: int) -> None:
        """Se il nodo è fuori dalla parte visibile, porta la tela a centrarlo."""
        item = self._nodes.get(node_id)
        if item is not None and not self.viewport().rect().contains(self.mapFromScene(item.pos())):
            self.centerOn(item)
            self._fitted = False

    # --- Strumenti, zoom, inquadratura -------------------------------------------------------------------
    def set_tool(self, tool: str) -> None:
        self._tools.set_tool(tool)

    def _set_tool(self, tool: str) -> None:
        self._tool = tool
        self._cancel_connection()
        self.tool_changed.emit(tool)
        self._update_overlays()
        self.viewport().setCursor(Qt.CrossCursor if tool != SELECT else Qt.ArrowCursor)

    def _user_zoom(self, factor: float) -> None:
        self._fitted = False
        self._zoom_by(factor)

    def wheelEvent(self, event) -> None:
        self._fitted = False
        super().wheelEvent(event)

    def fit_all(self, user: bool = True) -> None:
        """Inquadra tutti i nodi (senza ingrandire oltre la misura vera), anche se per farlo serve rimpicciolire oltre lo zoom
        minimo di chi usa la rotella; con la tela vuota, ricentra."""
        if user:
            self._fitted = True
        view = self.viewport().size()
        if view.width() <= 0 or view.height() <= 0:
            return
        bounds = QRectF()
        for item in self._nodes.values():
            bounds = bounds.united(item.mapRectToScene(item.body()))
        scale = 1.0
        if not bounds.isNull():
            bounds = bounds.adjusted(-_FIT_MARGIN - _TOOLS_ROOM, -_FIT_MARGIN, _FIT_MARGIN, _FIT_MARGIN)
            scale = min(view.width() / bounds.width(), view.height() / bounds.height(), 1.0)
        self._min_scale = min(_MIN_SCALE, scale)        # da qui non si deve poter «ridurre» a un'inquadratura più larga di questa
        self.resetTransform()
        self.scale(scale, scale)
        self._scale = scale
        self.centerOn(bounds.center() if not bounds.isNull() else QPointF(0, 0))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fitted:
            self.fit_all(user=False)
        self._update_overlays()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._fitted:
            self.fit_all(user=False)

    def _update_overlays(self) -> None:
        hint = _HINT_SECOND if self._armed is not None else _HINTS.get(self._tool, "")
        self._hint.set_text(hint)
        self._hint.setVisible(bool(hint))
        self._empty.setVisible(not self._nodes)
        self._empty.setGeometry(self.rect())
        self._tools.adjustSize()
        self._tools.move(16, 16)
        self._hint.move((self.width() - self._hint.width()) // 2, self.height() - 16 - self._hint.height())
        for overlay in (self._tools, self._hint):
            overlay.raise_()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor(theme.BG))
        step = _GRID
        while step * self._scale < 14:                  # rimpicciolendo i puntini non devono diventare una nebbia
            step *= 2
        pen = QPen(QColor(theme.BORDER_STRONG), 2)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        first_x, first_y = math.floor(rect.left() / step) * step, math.floor(rect.top() / step) * step
        points = QPolygonF()
        for x in range(0, int(rect.width() // step) + 2):
            for y in range(0, int(rect.height() // step) + 2):
                points.append(QPointF(first_x + x * step, first_y + y * step))
        painter.drawPoints(points)

    # --- Collegare due estremi -----------------------------------------------------------------------------
    def _arm(self, item: NodeItem | EdgeItem) -> None:
        self._armed = item
        item.set_armed(True)
        self._rubber = QGraphicsLineItem()
        pen = QPen(QColor(theme.ACCENT), 1.6, Qt.DashLine)
        pen.setCosmetic(True)
        self._rubber.setPen(pen)
        self._rubber.setZValue(20)
        self._rubber.setLine(item.center().x(), item.center().y(), item.center().x(), item.center().y())
        self._scene.addItem(self._rubber)
        self._update_overlays()

    def _cancel_connection(self) -> None:
        if self._armed is not None:
            self._armed.set_armed(False)
        if self._rubber is not None and self._rubber.scene() is not None:
            self._scene.removeItem(self._rubber)
        self._armed = self._rubber = None
        self._update_overlays()

    # --- Mouse ---------------------------------------------------------------------------------------------
    def _item_at(self, point: QPoint) -> NodeItem | EdgeItem | None:
        """Il nodo o l'arco sotto il punto. Fra più archi sovrapposti vince quello la cui etichetta (o puntino) è proprio lì:
        così si può scegliere un arco anche se la linea di un altro gli arriva addosso."""
        hits = [item for item in self.items(point) if isinstance(item, (NodeItem, EdgeItem))]
        if not hits or isinstance(hits[0], NodeItem):
            return hits[0] if hits else None
        scene = self.mapToScene(point)
        return next((item for item in hits if isinstance(item, EdgeItem) and item.on_body(scene)), hits[0])

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._press = self._last = event.position().toPoint()
        self._press_item = self._item_at(self._press)
        if isinstance(self._press_item, NodeItem):
            self._grab = self._press_item.pos() - self.mapToScene(self._press)
        self._moved = False

    def mouseMoveEvent(self, event) -> None:
        point = event.position().toPoint()
        if self._press is None:
            self._hover(point)
            if self._rubber is not None:
                scene = self.mapToScene(point)
                self._rubber.setLine(self._armed.center().x(), self._armed.center().y(), scene.x(), scene.y())
            return super().mouseMoveEvent(event)
        self._moved = self._moved or (point - self._press).manhattanLength() > _DRAG_START
        if self._moved:
            if self._tool == SELECT and isinstance(self._press_item, NodeItem):
                self._press_item.setPos(self.mapToScene(point) + self._grab)
            else:
                self._fitted = False
                self._pan_by(point - self._last)
        self._last = point

    def mouseReleaseEvent(self, event) -> None:
        if self._press is None:
            return super().mouseReleaseEvent(event)
        item, moved, point = self._press_item, self._moved, self._press
        self._press = self._press_item = None
        self._moved = False
        if not moved:
            self._clicked(item, point)
        elif self._tool == SELECT and isinstance(item, NodeItem):
            self.node_moved.emit(item.node_id, item.pos().x(), item.pos().y())

    def _clicked(self, item: NodeItem | EdgeItem | None, point: QPoint) -> None:
        if self._tool == CONNECT:
            if item is not None and self._armed is None:
                self._arm(item)
            elif item is not None and item is not self._armed:
                first = self._armed.endpoint
                self._cancel_connection()
                self.connect_requested.emit(first, item.endpoint)
            else:
                self._cancel_connection()
        elif isinstance(item, NodeItem):
            self.node_clicked.emit(item.node_id)
        elif isinstance(item, EdgeItem):
            self.edge_clicked.emit(item.edge_id)
        elif self._tool == NODE:
            scene = self.mapToScene(point)
            self.add_requested.emit(scene.x(), scene.y())
        else:
            self.background_clicked.emit()

    def _hover(self, point: QPoint) -> None:
        item = self._item_at(point)
        if item is not self._hovered:
            if self._hovered is not None:
                self._hovered.set_hovered(False)
            if item is not None:
                item.set_hovered(True)
            self._hovered = item
            if self._tool == SELECT or item is not None:
                self.viewport().setCursor(Qt.PointingHandCursor if item is not None else Qt.ArrowCursor)
            else:
                self.viewport().setCursor(Qt.CrossCursor)
