"""Le cartelle della libreria immagini e le mappe viste come alberi: percorso di un nodo, nodi contenuti, nomi per esteso.

Vale per qualunque cosa con `id`, `parent_id` e `name` (`ImageFolder`, `Map`).
"""

from typing import Protocol, TypeVar

from .search import fold

PATH_SEPARATOR = " › "


class Node(Protocol):
    id: int
    parent_id: int | None
    name: str


N = TypeVar("N", bound=Node)


def chain(nodes: list[N], node_id: int | None) -> list[N]:
    """I nodi dal primo livello fino a `node_id` (vuoto per il primo livello)."""
    by_id = {node.id: node for node in nodes}
    result = []
    while node_id in by_id:
        result.append(by_id[node_id])
        node_id = by_id[node_id].parent_id
    return result[::-1]


def subtree(nodes: list[N], node_id: int) -> set[int]:
    """`node_id` e tutti i nodi che contiene, a qualunque livello."""
    found = {node_id}
    grew = True
    while grew:
        inside = {node.id for node in nodes if node.parent_id in found}
        grew = not inside <= found
        found |= inside
    return found


def named_paths(nodes: list[N]) -> list[tuple[int, str]]:
    """Ogni nodo con il suo nome per esteso («Luoghi › Taverne»), nell'ordine di un elenco."""
    names = {node.id: PATH_SEPARATOR.join(part.name for part in chain(nodes, node.id)) for node in nodes}
    return sorted(names.items(), key=lambda item: fold(item[1]))
