"""Come si riconosce, nell'interfaccia, ciò a cui si può collegare un testo."""

from .. import theme
from ..data import links
from ..data.models import LinkTarget, Pin, PinType
from ..elements import KINDS


def kind_icon(kind: str) -> str:
    """L'icona di un tipo di bersaglio: quella della sua schermata per gli elementi, una mappa per le mappe, un grafo per i grafi, un foglio per le pagine, un + per «crea»."""
    if kind.startswith(links.CREATE):
        return "plus"
    if kind == links.ENCOUNTER:
        return "swords"
    if kind in links.VIEW_KINDS:
        return "map" if kind == links.MAP else "graph"
    return KINDS[kind].icon if kind in KINDS else "file"


def kind_color(kind: str) -> str:
    """Il colore di un tipo di bersaglio: quello della sua sezione (Scrittura per le pagine, Mappe, Grafi, Incontri, o il tipo di elemento)."""
    if kind in KINDS:
        return KINDS[kind].color
    return theme.SECTION_COLORS[{links.MAP: "mappe", links.GRAPH: "grafi", links.ENCOUNTER: "incontri"}.get(kind, "scrittura")]


def target_caption(target: LinkTarget) -> str:
    """Cos'è un bersaglio, in breve: «Luogo · Città» per un elemento, «Pagina 1.2» per una pagina."""
    return f"{KINDS[target.kind].noun.capitalize()} · {target.detail}" if target.kind in KINDS else target.detail


def pin_caption(pin: Pin, pin_type: PinType) -> str:
    """Cos'è un pin, in breve: «Luogo · Città» (il suo tipo e, se è collegato a un elemento, la categoria di questo)."""
    return f"{pin_type.name} · {pin.link.detail}" if pin.link is not None and pin.link.kind in KINDS else pin_type.name
