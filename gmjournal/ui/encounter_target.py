"""Dove si trova la schermata Incontri (serve alla cronologia): quale delle due pagine e quale voce è scelta."""

from dataclasses import dataclass

ENCOUNTERS, CREATURES = "encounters", "creatures"       # le due pagine: gli incontri e le schede tecniche


@dataclass(frozen=True)
class EncounterTarget:
    page: str = ENCOUNTERS
    item_id: int | None = None          # l'incontro o la scheda scelti (None = nessuno)
