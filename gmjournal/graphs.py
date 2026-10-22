"""Costanti dei grafi: come parte un nodo nuovo, i limiti dei suoi testi, e gli estremi degli archi."""

from typing import NamedTuple

NEW_NODE_TITLE = "Nuovo nodo"
NEW_NODE_COLOR = "violet"       # chiave in theme.CATEGORY_COLORS (è il colore della sezione Grafi)
DESCRIPTION_MAX = 500           # lunghezza massima della descrizione di un nodo
LABEL_MAX = 80                  # lunghezza massima dell'etichetta di un arco
NO_ARROW, TO_B, TO_A, BOTH = 0, 1, 2, 3     # direzione di un arco: nessuna freccia, verso l'estremo `b`, verso `a`, verso entrambi
KIND_NODE, KIND_EDGE = "node", "edge"      # un arco può finire su un nodo o su un altro arco (la sua etichetta)


class Endpoint(NamedTuple):
    """Un estremo di un arco: un nodo o un altro arco del grafo, per ID."""
    kind: str
    id: int


def endpoint_points(nodes: dict[int, tuple[float, float]], edges: list) -> dict[Endpoint, tuple[float, float]]:
    """Dove sta ogni estremo possibile: i nodi dove sono, gli archi a metà fra i loro estremi (serve alle miniature).
    `edges` va in ordine di ID: un arco finisce soltanto su archi più vecchi."""
    points = {Endpoint(KIND_NODE, node_id): point for node_id, point in nodes.items()}
    for edge in edges:
        (ax, ay), (bx, by) = points[edge.a], points[edge.b]
        points[Endpoint(KIND_EDGE, edge.id)] = ((ax + bx) / 2, (ay + by) / 2)
    return points
