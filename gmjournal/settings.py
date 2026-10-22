"""Le quattro liste che si gestiscono da Impostazioni: le categorie di personaggi, luoghi e organizzazioni e i tipi di pin delle mappe.

La schermata e i popup leggono i testi da qui, così una lista si descrive in un posto solo.
"""

from dataclasses import dataclass

from . import sections
from .elements import KINDS


@dataclass(frozen=True)
class Entry:
    """Una voce di una lista: una categoria o un tipo di pin, con quante volte è usata."""
    id: int
    name: str
    color: str          # chiave del colore (vedi theme.CATEGORY_COLORS)
    count: int
    icon: str = ""      # solo i tipi di pin (vedi pins.py)


@dataclass(frozen=True)
class Group:
    key: str                    # chiave della schermata a cui appartiene (vedi sections.py)
    kind: str | None            # tipo di elemento delle categorie; None = i tipi di pin
    subject: str                # «categoria», «tipo di pin»
    plural: str                 # «categorie», «tipi di pin»
    new: str                    # «Nuova categoria»
    intro: str                  # spiegazione sotto il titolo
    unit_one: str               # ciò che si conta accanto a ogni voce: «personaggio»…
    unit_many: str
    move_text: str              # sopra la scelta di dove spostare ciò che usa la voce eliminata
    last_text: str              # perché l'ultima voce non si elimina

    @property
    def title(self) -> str:
        return sections.BY_KEY[self.key].label

    @property
    def icon(self) -> str:
        return sections.BY_KEY[self.key].icon

    @property
    def color(self) -> str:
        return sections.BY_KEY[self.key].color

    def count_text(self, number: int) -> str:
        return f"{number} {self.unit_one if number == 1 else self.unit_many}"


GROUPS = (
    *(Group(kind.section, kind.key, "categoria", "categorie", "Nuova categoria",
            f"Le categorie raggruppano {kind.title.lower()} nell'elenco e nei filtri. Il colore si vede sulle tessere e sulle pillole.",
            kind.noun, kind.title.lower(), "Gli elementi che usano questa categoria passeranno a:", "Deve restare almeno una categoria.")
      for kind in KINDS.values()),
    Group("mappe", None, "tipo di pin", "tipi di pin", "Nuovo tipo di pin",
          "I tipi di pin si scelgono quando si posa un pin sulla mappa e servono a filtrarli. Ognuno ha un'icona e un colore.",
          "pin", "pin", "I pin di questo tipo passeranno a:", "Deve restare almeno un tipo di pin."),
)
BY_KEY = {group.key: group for group in GROUPS}
