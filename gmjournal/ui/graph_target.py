"""Dove si trova la schermata Grafi (serve alla cronologia e a chi vuole aprirla da un'altra schermata)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphTarget:
    graph_id: int | None = None         # il grafo aperto (None = l'elenco dei grafi)
    node_id: int | None = None          # il nodo scelto
    edge_id: int | None = None          # oppure l'arco scelto
