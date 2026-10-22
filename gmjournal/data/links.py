"""Collegamenti interni al testo: come sono scritti nel testo salvato e come si leggono.

Un collegamento è sempre `<a href="gmj://tipo/ID">testo</a>`: punta a un elemento tramite il suo ID,
mai tramite il nome, così rinominare non rompe nulla.
"""

import re

PAGE = "page"                   # bersaglio «pagina di Scrittura»
CHARACTER = "character"         # bersagli «elemento»: personaggio, luogo, organizzazione, cultura
PLACE = "place"
ORGANIZATION = "organization"
CULTURE = "culture"             # popoli, religioni, razze, lingue
ELEMENT_KINDS = (CHARACTER, PLACE, ORGANIZATION, CULTURE)
MAP = "map"                     # bersagli «schermata»: una mappa o un grafo (si cercano e si citano nei testi, non si collegano a pin e nodi)
GRAPH = "graph"
VIEW_KINDS = (MAP, GRAPH)
ENCOUNTER = "encounter"         # un incontro: non si cita con «@», ma il box «Incontro» del testo lo apre con la stessa via dei collegamenti
CAMPAIGN = "campaign"           # non è un bersaglio di collegamenti: compare solo fra i posti dove è usata un'immagine
CREATE = "create:"              # prefisso del finto bersaglio «crea un nuovo elemento» (es. «create:character»): mai salvato

_SCHEME = "gmj://"
_HREF = re.compile(r"gmj://([a-z_]+)/(\d+)")
_ANCHOR = re.compile(r'<a href="(gmj://[a-z_]+/\d+)">(.*?)</a>', re.DOTALL)


def make_href(kind: str, target_id: int) -> str:
    return f"{_SCHEME}{kind}/{target_id}"


def parse_href(href: str) -> tuple[str, int] | None:
    """(tipo, ID) di un collegamento interno; None se non lo è."""
    match = _HREF.fullmatch(href)
    return (match.group(1), int(match.group(2))) if match else None


def extract_targets(content: str) -> list[tuple[str, int]]:
    """I bersagli citati nel testo, nell'ordine in cui compaiono e senza ripetizioni."""
    found: dict[tuple[str, int], None] = {}
    for href, _ in _ANCHOR.findall(content):
        target = parse_href(href)
        if target:
            found[target] = None
    return list(found)


def unlink(content: str, kind: str, target_id: int) -> str:
    """Toglie i collegamenti verso un bersaglio che non esiste più: il testo resta, senza link."""
    href = make_href(kind, target_id)
    return _ANCHOR.sub(lambda m: m.group(2) if m.group(1) == href else m.group(0), content)
