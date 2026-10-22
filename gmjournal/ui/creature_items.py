"""Come una scheda tecnica compare in un elenco (titolo e riga di descrizione) e come si cerca: usato dall'elenco delle schede e dal
popup che le sceglie per un incontro."""

from ..data.models import CreatureRow
from ..data.search import fold
from .widgets.item_list import ListItem


def caption(row: CreatureRow) -> str:
    """«Large aberration · GS 10»."""
    kind = " ".join(part for part in (row.size, row.kind) if part)
    return " · ".join(part for part in (kind, f"GS {row.challenge}" if row.challenge else "") if part)


def creature_item(row: CreatureRow, state: str = "", note: str = "") -> ListItem:
    """La voce dell'elenco per una scheda; `note` (se c'è) si aggiunge alla descrizione («già nell'incontro»)."""
    return ListItem(row.id, row.name, " · ".join(part for part in (caption(row), note) if part), state)


def matches(row: CreatureRow, query: str) -> bool:
    """Se la scheda risponde a una ricerca: per nome, taglia, tipo o fonte, senza badare a maiuscole e accenti."""
    return fold(query) in fold(f"{row.name} {row.size} {row.kind} {row.source}")
