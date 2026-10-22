"""La scheda di un grafo nell'elenco: come quella di una mappa, ma al posto dello sfondo c'è una miniatura dei suoi nodi."""

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ... import icons, theme
from ...data.models import GraphEdge, GraphNode
from ...graphs import KIND_NODE, Endpoint, endpoint_points
from .map_card import MapCard

_COLOR = theme.SECTION_COLORS["grafi"]
_MARGIN = 28            # spazio fra la miniatura e il bordo della copertina
_NODE = (24, 14)        # misura di un nodo nella miniatura


class GraphCard(MapCard):
    def __init__(self):
        super().__init__()
        self._edit.setToolTip("Modifica il grafo")
        self._nodes: list[GraphNode] = []
        self._edges: list[GraphEdge] = []

    def set_graph(self, name: str, meta: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self._nodes, self._edges = nodes, edges
        self.set_map(name, meta, None)

    def _paint_cover(self, painter: QPainter, cover: QRect) -> None:
        painter.fillRect(cover, theme.tint(_COLOR))
        if not self._nodes:
            icons.icon("graph", _COLOR).paint(painter, QRect(cover.center().x() - 22, cover.center().y() - 22, 44, 44))
            return
        xs, ys = [node.x for node in self._nodes], [node.y for node in self._nodes]
        span_x, span_y = max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1)
        room = QRectF(cover).adjusted(_MARGIN, _MARGIN, -_MARGIN, -_MARGIN)
        scale = min(room.width() / span_x, room.height() / span_y)
        if len(self._nodes) == 1:
            scale = 0
        center = QPointF((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        points = endpoint_points({node.id: (room.center().x() + (node.x - center.x()) * scale, room.center().y() + (node.y - center.y()) * scale)
                                  for node in self._nodes}, self._edges)        # anche gli archi che finiscono su altri archi
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme.DISABLED), 1.4))
        for edge in self._edges:
            painter.drawLine(QPointF(*points[edge.a]), QPointF(*points[edge.b]))
        painter.setPen(Qt.NoPen)
        for node in self._nodes:
            painter.setBrush(QColor(theme.category_color(node.color)))
            x, y = points[Endpoint(KIND_NODE, node.id)]
            painter.drawRoundedRect(QRectF(x - _NODE[0] / 2, y - _NODE[1] / 2, *_NODE), 4, 4)
