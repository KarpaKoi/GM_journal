"""Dove si trova la schermata Mappe (serve alla cronologia e a chi vuole aprirla da un'altra schermata)."""

from dataclasses import dataclass

from ..data.models import LinkTarget


@dataclass(frozen=True)
class MapTarget:
    map_id: int | None = None           # la mappa aperta (None = l'elenco delle mappe)
    pin_id: int | None = None           # il pin scelto
    place: LinkTarget | None = None     # se c'è, la mappa si apre già pronta a posare un pin collegato a questo elemento
