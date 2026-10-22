"""Strutture dati dell'app: semplici contenitori, senza logica."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..graphs import Endpoint


@dataclass(frozen=True)
class Campaign:
    name: str
    description: str
    color: str                 # chiave del colore di copertina (es. "blue")
    image: str | None          # copertina: percorso relativo alla cartella della campagna
    modified_at: datetime


@dataclass(frozen=True)
class CampaignEntry:
    """Una campagna dell'elenco: dove si trova e i suoi dati."""
    folder: Path
    campaign: Campaign


@dataclass(frozen=True)
class CampaignInput:
    """I dati inseriti nel popup della campagna."""
    name: str
    description: str
    color: str
    image: str | Path | None   # str = copertina già presente; Path = file nuovo da importare


@dataclass(frozen=True)
class PageNode:
    """Una pagina di Scrittura vista dall'albero dei capitoli (senza il testo)."""
    id: int
    parent_id: int | None      # None = capitolo principale; altrimenti sottocapitolo
    position: int              # posto tra le pagine con lo stesso genitore, da 0
    title: str
    words: int                 # le parole del testo (non del titolo)
    modified_at: datetime


@dataclass(frozen=True)
class Page:
    id: int
    parent_id: int | None
    title: str
    content: str               # testo nel formato dell'editor (vedi ui/editor/markup.py)


@dataclass(frozen=True)
class Todo:
    """Una voce dell'elenco «Da fare» della campagna."""
    id: int
    text: str
    done: bool


@dataclass(frozen=True)
class LinkTarget:
    """Qualcosa a cui si può collegare un testo: una pagina, un personaggio, un luogo, un'organizzazione."""
    kind: str                  # tipo (vedi data/links.py)
    id: int
    name: str
    detail: str                # descrizione accanto al nome: «Pagina 1.2», la categoria…


@dataclass(frozen=True)
class Category:
    id: int
    kind: str                  # tipo di elemento a cui appartiene (vedi data/links.py)
    name: str
    color: str                 # chiave del colore (vedi theme.CATEGORY_COLORS)


@dataclass(frozen=True)
class ImageFolder:
    """Una cartella della libreria immagini (esiste solo nel programma: i file stanno tutti nella cartella immagini)."""
    id: int
    parent_id: int | None      # None = dentro «Immagini», la cartella principale
    name: str


@dataclass(frozen=True)
class Image:
    """Un'immagine della libreria: il file (percorso relativo alla cartella della campagna), il nome mostrato e dove sta."""
    id: int
    path: str
    label: str
    folder_id: int | None      # None = nella cartella principale


@dataclass(frozen=True)
class Element:
    """Un personaggio, un luogo o un'organizzazione."""
    id: int
    kind: str
    name: str
    category_id: int
    image: str | None          # ritratto o copertina: la prima delle sue immagini (percorso relativo alla cartella della campagna)
    brief: str                 # «in breve»
    role: str                  # solo per i personaggi


@dataclass(frozen=True)
class ElementInput:
    """I dati inseriti nel popup di un elemento."""
    kind: str
    name: str
    category_id: int
    image: str | Path | None   # str = immagine già presente; Path = file nuovo da importare
    brief: str
    role: str


@dataclass(frozen=True)
class Map:
    """Una mappa: dove sta nell'albero delle mappe e la sua immagine di sfondo (della libreria; può mancare)."""
    id: int
    parent_id: int | None      # None = al primo livello
    name: str
    image: str | None          # percorso relativo alla cartella della campagna


@dataclass(frozen=True)
class PinType:
    """Un tipo di pin (Luoghi, Persone…): il nome nei filtri, l'icona (vedi pins.py) e il colore."""
    id: int
    name: str
    icon: str
    color: str                 # chiave del colore (vedi theme.CATEGORY_COLORS)


@dataclass(frozen=True)
class PinInput:
    """I dati inseriti nel popup di un pin. Un pin è collegato (`link`) oppure libero: nome e testo si scrivono solo se è libero."""
    type_id: int
    name: str
    brief: str
    link: tuple[str, int] | None        # (tipo, ID) di una pagina o di un elemento
    opens_map_id: int | None            # la mappa che si apre dal pin


@dataclass(frozen=True)
class Pin:
    """Un pin posato su una mappa. Nome e testo sono quelli del collegamento, se c'è; altrimenti quelli scritti nel pin."""
    id: int
    map_id: int
    type_id: int
    x: float                   # posizione sull'immagine: 0 = bordo sinistro/alto, 1 = bordo destro/basso
    y: float
    name: str
    brief: str
    link: LinkTarget | None
    opens_map_id: int | None


@dataclass(frozen=True)
class Graph:
    """Un grafo (una mappa mentale): solo il nome, nodi e archi si leggono a parte."""
    id: int
    name: str


@dataclass(frozen=True)
class NodeInput:
    """I dati di un nodo. Un nodo è collegato (`link`) oppure libero: il titolo si scrive solo se è libero."""
    title: str
    description: str
    color: str                          # chiave del colore (vedi theme.CATEGORY_COLORS)
    link: tuple[str, int] | None        # (tipo, ID) di una pagina o di un elemento


@dataclass(frozen=True)
class GraphNode:
    """Un nodo di un grafo. Il titolo è quello del collegamento, se c'è; la descrizione è sempre del nodo."""
    id: int
    graph_id: int
    x: float                   # posizione sulla tela del grafo
    y: float
    title: str
    description: str
    color: str
    link: LinkTarget | None


@dataclass(frozen=True)
class GraphEdge:
    """Un arco del grafo: unisce due estremi, ognuno un nodo o un altro arco (la sua etichetta). La direzione è in graphs.py."""
    id: int
    a: Endpoint
    b: Endpoint
    label: str
    direction: int


@dataclass(frozen=True)
class Feature:
    """Una voce di una scheda tecnica: un tratto, un'azione, una reazione o un'azione leggendaria (`section`, vedi dnd.py)."""
    section: str
    name: str
    text: str


@dataclass(frozen=True)
class CreatureInput:
    """I dati di una scheda tecnica (mostro o PNG). I testi restano come li scrive chi compila o come sono nel file importato."""
    name: str
    size: str
    kind: str                       # il tipo: «aberration», «humanoid (any race)»…
    alignment: str
    armor_class: str                # «17 (natural armor)»
    hit_points: str                 # «135 (18d10+36)»
    speed: str
    abilities: tuple[int, ...]      # nell'ordine di dnd.ABILITIES
    saves: str
    skills: str
    vulnerabilities: str
    resistances: str
    immunities: str
    condition_immunities: str
    senses: str
    passive: int | None             # Percezione passiva
    languages: str
    challenge: str                  # grado di sfida come testo: «1/8», «10»; vuoto se non noto
    environment: str
    source: str                     # da dove viene la scheda (libro, avventura…)
    notes: str                      # descrizione e note
    features: tuple[Feature, ...]   # nell'ordine in cui vanno lette


@dataclass(frozen=True)
class Creature(CreatureInput):
    id: int


@dataclass(frozen=True)
class CreatureRow:
    """Ciò che serve all'elenco delle schede: la scheda completa si legge a parte."""
    id: int
    name: str
    size: str
    kind: str
    challenge: str
    source: str


@dataclass(frozen=True)
class PartyGroup:
    """Un gruppo di giocatori presenti allo stesso livello («3 giocatori di livello 5»)."""
    level: int
    count: int


@dataclass(frozen=True)
class Slot:
    """Una scheda tecnica usata in un incontro, con quante copie (vedi `creature_id` in `CreatureRow`)."""
    creature_id: int
    quantity: int


@dataclass(frozen=True)
class EncounterInput:
    """Un incontro: di combattimento (con i giocatori presenti) o di interazione (senza)."""
    name: str
    kind: str                       # vedi encounters.py
    party: tuple[PartyGroup, ...]   # solo per i combattimenti
    creatures: tuple[Slot, ...]     # nell'ordine in cui si mostrano


@dataclass(frozen=True)
class Encounter(EncounterInput):
    id: int


@dataclass(frozen=True)
class ImportResult:
    added: int
    skipped: int                    # già presenti, identiche


MEMBER_STATUSES = ("active", "deserter", "deceased")   # stato di un membro di un'organizzazione (testi in elements.py)


@dataclass(frozen=True)
class Relation:
    """Una relazione vista da un elemento: l'altro elemento e ciò che le riguarda.

    `status`, `note` e `leader` hanno senso solo fra un personaggio e un'organizzazione (la scheda «Membri»).
    """
    id: int
    other: Element
    label: str                 # com'è scritta la relazione: la stessa da entrambe le parti
    status: str                # uno di MEMBER_STATUSES
    note: str
    leader: bool
