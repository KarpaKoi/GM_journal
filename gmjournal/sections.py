"""Elenco delle schermate di una campagna: l'unico posto dove definirle.

Barra sinistra, barra superiore e navigazione leggono tutte da qui, quindi
aggiungere o rinominare una schermata richiede di cambiare una sola riga.
"""

from dataclasses import dataclass

from . import theme


@dataclass(frozen=True)
class Section:
    key: str                # identificativo interno
    label: str              # nome mostrato
    icon: str               # nome del file in assets/icons
    group: str = ""         # titoletto di gruppo nella barra sinistra

    @property
    def color(self) -> str:
        return theme.SECTION_COLORS[self.key]


SECTIONS = (
    Section("scrittura", "Scrittura", "feather"),
    Section("personaggi", "Personaggi", "user", "Mondo"),
    Section("luoghi", "Luoghi", "map-pin", "Mondo"),
    Section("organizzazioni", "Organizzazioni", "flag", "Mondo"),
    Section("culture", "Culture", "globe", "Mondo"),
    Section("incontri", "Incontri", "swords", "Mondo"),
    Section("immagini", "Immagini", "image", "Visuale"),
    Section("mappe", "Mappe", "map", "Visuale"),
    Section("grafi", "Grafi", "graph", "Visuale"),
)

# Fuori dall'elenco: sta in fondo alla barra sinistra.
SETTINGS = Section("impostazioni", "Impostazioni", "sliders")

BY_KEY = {section.key: section for section in (*SECTIONS, SETTINGS)}
