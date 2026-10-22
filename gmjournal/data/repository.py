"""Lettura e scrittura dei dati di una campagna: le schermate passano sempre da qui."""

import logging
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path

from PySide6.QtCore import QFile

from ..dnd import ABILITY_MAX, ABILITY_MIN, FEATURE_KEYS, FIELD_MAX, LEVEL_MAX, LEVEL_MIN, PLAYERS_MAX, QUANTITY_MAX, TEXT_MAX
from ..encounters import COMBAT, KIND_LABELS, KINDS
from ..graphs import BOTH, DESCRIPTION_MAX, KIND_EDGE, KIND_NODE, LABEL_MAX, NO_ARROW, TO_A, TO_B, Endpoint
from ..paths import campaigns_root
from . import db, image_refs, links, plain
from .db import DatabaseError
from .image_refs import IMAGES_DIRNAME, safe_media_path
from .models import (
    MEMBER_STATUSES, Campaign, CampaignEntry, CampaignInput, Category, Creature, CreatureInput, CreatureRow, Element, ElementInput,
    Encounter, EncounterInput, Feature, Graph, GraphEdge, GraphNode, Image, ImageFolder, ImportResult, LinkTarget, Map, NodeInput, Page,
    PageNode, PartyGroup, Pin, PinInput, PinType, Relation, Slot, Todo,
)
from .search import fold, rank
from ..spelling import Speller

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}   # i file che si riconoscono come immagini
TITLE_MAX = 120   # lunghezza massima del titolo di una pagina
NAME_MAX = 80     # lunghezza massima del nome di un elemento
TODO_MAX = 300    # lunghezza massima di una voce di «Da fare»
RELATION_TEXT_MAX = 200   # lunghezza massima del testo di una relazione e della nota di un membro
_RELATION_COLUMNS = ("label", "status", "note", "leader")   # ciò che di una relazione si può cambiare
# Le colonne di un elemento, nell'ordine di `Element` (la tabella `element` si chiama `e`): l'immagine è la prima delle sue immagini.
_ELEMENT_COLUMNS = ("e.id, e.kind, e.name, e.category_id, "
                    "(SELECT path FROM element_image WHERE element_id = e.id ORDER BY position LIMIT 1), e.brief, e.role")

# Le colonne di una scheda tecnica nell'ordine di `CreatureInput` (le sei caratteristiche sono sei colonne, un solo campo).
_CREATURE_COLUMNS = ("name", "size", "kind", "alignment", "armor_class", "hit_points", "speed",
                     "ab_str", "ab_dex", "ab_con", "ab_int", "ab_wis", "ab_cha",
                     "saves", "skills", "vulnerabilities", "resistances", "immunities", "condition_immunities", "senses", "passive",
                     "languages", "challenge", "environment", "source", "notes")


def _encounter_parts(data: EncounterInput) -> tuple[str, str, list[PartyGroup], list[Slot]]:
    """Nome, tipo, giocatori e schede di un incontro, ripuliti: livelli e quantità nei limiti, una sola riga per scheda (le copie si
    sommano). I giocatori ci sono solo nei combattimenti."""
    if data.kind not in KINDS:
        raise DatabaseError("Il tipo di incontro non è valido.")
    party = [PartyGroup(min(max(group.level, LEVEL_MIN), LEVEL_MAX), min(max(group.count, 1), PLAYERS_MAX))
             for group in data.party] if data.kind == COMBAT else []
    quantities: dict[int, int] = {}
    for slot in data.creatures:
        quantities[slot.creature_id] = quantities.get(slot.creature_id, 0) + slot.quantity
    slots = [Slot(creature_id, min(max(quantity, 1), QUANTITY_MAX)) for creature_id, quantity in quantities.items()]
    return _required_name(data.name), data.kind, party, slots

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')   # vietati nei nomi di cartella di Windows
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}


# --- Elenco delle campagne -----------------------------------------------------
def list_campaigns() -> list[CampaignEntry]:
    """Tutte le campagne trovate, dalla modificata più di recente."""
    root = campaigns_root()
    entries = []
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if not (folder / db.DB_FILENAME).is_file():
            continue
        try:
            with Repository.open(folder) as repo:
                entries.append(CampaignEntry(folder, repo.campaign()))
        except DatabaseError as error:
            logging.warning("Campagna ignorata: %s", error)
    return sorted(entries, key=lambda entry: entry.campaign.modified_at, reverse=True)


def safe_name(name: str) -> str:
    """`name` come nome valido di cartella o di file su Windows."""
    base = _INVALID_CHARS.sub("", name).strip()[:60].rstrip(". ")
    if not base or base.split(".")[0].upper() in _RESERVED_NAMES:
        base = f"Campagna {base}".strip()
    return base


def unique_folder(name: str) -> Path:
    """Una cartella nuova e valida su Windows per una campagna chiamata `name`."""
    base = safe_name(name)
    root = campaigns_root()
    candidate, number = root / base, 2
    while candidate.exists():
        candidate = root / f"{base} ({number})"
        number += 1
    return candidate


def duplicate_campaign(folder: Path) -> Path:
    """Copia l'intera campagna (dati e immagini) con il nome «… (copia)»."""
    with Repository.open(folder) as source:
        new_name = f"{source.campaign().name} (copia)"
    target = unique_folder(new_name)
    try:
        shutil.copytree(folder, target, ignore=shutil.ignore_patterns("*.bak"))
        with Repository.open(target) as copy:
            original = copy.campaign()
            copy.update_campaign(CampaignInput(new_name, original.description, original.color, original.image))
    except (OSError, DatabaseError) as error:
        shutil.rmtree(target, ignore_errors=True)
        raise DatabaseError(f"Impossibile duplicare la campagna: {error}") from error
    return target


class TrashError(DatabaseError):
    """Il cestino non accetta la cartella: succede con un file aperto, o su un disco senza cestino (una chiavetta USB)."""


def delete_campaign(folder: Path) -> None:
    """Sposta la campagna nel cestino (così un errore non fa perdere nulla). Se il cestino non la accetta solleva `TrashError`:
    chi chiama può proporre `delete_campaign_permanently`."""
    if not QFile.moveToTrash(str(folder)):
        raise TrashError(f"Non riesco a spostare «{folder.name}» nel cestino. Chiudi i file aperti e riprova.")


def delete_campaign_permanently(folder: Path) -> None:
    """Elimina la campagna per sempre (senza cestino). Solo una cartella che è davvero una campagna."""
    if not (folder / db.DB_FILENAME).is_file():
        raise DatabaseError(f"«{folder.name}» non è una campagna: non la elimino.")
    try:
        shutil.rmtree(folder)
    except OSError as error:
        raise DatabaseError(f"Non riesco a eliminare «{folder.name}»: {error}") from error


def numbered_pages(nodes: list[PageNode]) -> list[tuple[PageNode, str]]:
    """Le pagine nell'ordine dell'albero (capitolo, poi i suoi sottocapitoli) con la numerazione: «1», «1.1»…"""
    children: dict[int | None, list[PageNode]] = {}
    for node in sorted(nodes, key=lambda n: n.position):
        children.setdefault(node.parent_id, []).append(node)
    result = []
    for chapter_number, chapter in enumerate(children.get(None, []), start=1):
        result.append((chapter, str(chapter_number)))
        for sub_number, sub in enumerate(children.get(chapter.id, []), start=1):
            result.append((sub, f"{chapter_number}.{sub_number}"))
    return result


def _endpoint(node_id: int | None, edge_id: int | None) -> Endpoint:
    """L'estremo di un arco dalle sue due colonne (una sola è piena)."""
    return Endpoint(KIND_NODE, node_id) if node_id is not None else Endpoint(KIND_EDGE, edge_id)


def _columns(end: Endpoint) -> tuple[int | None, int | None]:
    """L'inverso di `_endpoint`: (nodo, arco)."""
    return (end.id, None) if end.kind == KIND_NODE else (None, end.id)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _required_name(name: str) -> str:
    """Il nome di una categoria o di un tipo di pin, senza spazi ai bordi e della lunghezza massima; non può essere vuoto."""
    name = name.strip()[:NAME_MAX]
    if not name:
        raise DatabaseError("Il nome non può essere vuoto.")
    return name


def _todo_text(text: str) -> str:
    text = " ".join(text.split())[:TODO_MAX]
    if not text:
        raise DatabaseError("Scrivi cosa c'è da fare.")
    return text


def _short(text: str) -> str:
    """Un campo breve di una scheda tecnica: su una riga sola, della lunghezza massima."""
    return " ".join(text.split())[:FIELD_MAX]


def _creature_parts(data: CreatureInput) -> tuple[tuple, list[Feature]]:
    """I valori da scrivere nelle colonne di `creature` e le capacità, ripuliti (le capacità vuote spariscono)."""
    abilities = tuple(min(max(score, ABILITY_MIN), ABILITY_MAX) for score in data.abilities)
    values = (_required_name(data.name), _short(data.size), _short(data.kind), _short(data.alignment), _short(data.armor_class),
              _short(data.hit_points), _short(data.speed), *abilities, _short(data.saves), _short(data.skills), _short(data.vulnerabilities),
              _short(data.resistances), _short(data.immunities), _short(data.condition_immunities), _short(data.senses), data.passive,
              _short(data.languages), _short(data.challenge), _short(data.environment), _short(data.source), data.notes.strip()[:TEXT_MAX])
    features = [Feature(feature.section, _short(feature.name), feature.text.strip()[:TEXT_MAX]) for feature in data.features
                if feature.section in FEATURE_KEYS and (feature.name.strip() or feature.text.strip())]
    return values, features


def _unit(value: float) -> float:
    """Una posizione sull'immagine di una mappa, tenuta fra 0 e 1."""
    return min(max(value, 0.0), 1.0)


def _free_path(path: Path) -> Path:
    """`path`, oppure «nome-2.ext», «nome-3.ext»… se esiste già."""
    candidate, number = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
        number += 1
    return candidate


def _unlinked(content: str, kind: str, ids: list[int]) -> str:
    """Il testo senza i collegamenti verso questi bersagli (che non esistono più)."""
    for target_id in ids:
        content = links.unlink(content, kind, target_id)
    return content


# --- Una campagna aperta ---------------------------------------------------------
class Repository:
    """Una campagna aperta: la sua cartella e il suo database."""

    def __init__(self, folder: Path, conn: sqlite3.Connection):
        self.folder = folder
        self._conn = conn

    def __enter__(self) -> "Repository":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    @classmethod
    def open(cls, folder: Path) -> "Repository":
        path = folder / db.DB_FILENAME
        if not path.is_file():
            raise DatabaseError(f"Nessuna campagna trovata in «{folder}».")
        return cls(folder, db.connect(path))

    @classmethod
    def create(cls, folder: Path, data: CampaignInput) -> "Repository":
        """Crea la cartella della campagna (con database e cartella immagini)."""
        path = folder / db.DB_FILENAME
        if path.exists():
            raise DatabaseError(f"In «{folder}» esiste già una campagna.")
        folder_existed = folder.exists()
        repo = None
        try:
            (folder / IMAGES_DIRNAME).mkdir(parents=True, exist_ok=True)
            repo = cls(folder, db.connect(path))
            image = repo._store_image(data.image)
            with db.transaction(repo._conn):
                repo._conn.execute(
                    "INSERT INTO campaign (id, name, description, color, image, modified_at) VALUES (1, ?, ?, ?, ?, ?)",
                    (data.name, data.description, data.color, image, _now()),
                )
        except BaseException as error:
            if repo is not None:
                repo.close()
            if folder_existed:  # non lascia in giro una campagna a metà
                path.unlink(missing_ok=True)
            else:
                shutil.rmtree(folder, ignore_errors=True)
            if isinstance(error, OSError):
                raise DatabaseError(f"Impossibile creare la campagna: {error}") from error
            raise
        return repo

    def close(self) -> None:
        self._conn.close()

    def save_copy(self, target: Path) -> None:
        """Salva in `target` una copia coerente del database (serve al backup)."""
        db.copy_database(self._conn, target)

    def campaign(self) -> Campaign:
        row = self._conn.execute("SELECT * FROM campaign WHERE id = 1").fetchone()
        if row is None:
            raise DatabaseError("La campagna non è valida o è danneggiata.")
        return Campaign(
            name=row["name"],
            description=row["description"],
            color=row["color"],
            image=row["image"],
            modified_at=datetime.fromisoformat(row["modified_at"]),
        )

    def media_file(self, path: str | None) -> Path | None:
        """Il file di un'immagine della campagna dal percorso salvato nel database o in un testo; None se non c'è o il percorso non è valido."""
        return safe_media_path(self.folder, path)

    def update_campaign(self, data: CampaignInput) -> None:
        try:
            image = self._store_image(data.image)
        except OSError as error:
            raise DatabaseError(f"Impossibile copiare l'immagine: {error}") from error
        with db.transaction(self._conn):
            self._conn.execute(
                "UPDATE campaign SET name = ?, description = ?, color = ?, image = ?, modified_at = ? WHERE id = 1",
                (data.name, data.description, data.color, image, _now()),
            )

    def _store_image(self, source: str | Path | None) -> str | None:
        """Una copertina già salvata resta com'è; un file nuovo viene copiato nella cartella immagini."""
        return self.import_image(source) if isinstance(source, Path) else source

    def import_image(self, source: Path, folder_id: int | None = None) -> str:
        """Copia un'immagine scelta dall'utente nella cartella immagini e la mette nella libreria (in `folder_id`).
        Restituisce il percorso relativo alla campagna. Un file già nella cartella immagini non si copia."""
        images = self.folder / IMAGES_DIRNAME
        images.mkdir(exist_ok=True)
        if source.resolve().parent == images.resolve():
            target = source
        else:
            target = _free_path(images / source.name)
            shutil.copy2(source, target)
        path = target.relative_to(self.folder).as_posix()
        with db.transaction(self._conn):
            self._conn.execute("INSERT OR IGNORE INTO image (path, label, folder_id) VALUES (?, ?, ?)", (path, target.stem, folder_id))
        return path

    # --- Pagine di Scrittura -----------------------------------------------------------
    def pages(self) -> list[PageNode]:
        """Tutte le pagine (senza il testo): prima i capitoli principali, poi i sottocapitoli."""
        rows = self._conn.execute(
            "SELECT id, parent_id, position, title, words, modified_at FROM page ORDER BY parent_id IS NOT NULL, parent_id, position"
        )
        return [PageNode(row["id"], row["parent_id"], row["position"], row["title"], row["words"], datetime.fromisoformat(row["modified_at"]))
                for row in rows]

    def page(self, page_id: int) -> Page:
        row = self._conn.execute("SELECT id, parent_id, title, content FROM page WHERE id = ?", (page_id,)).fetchone()
        if row is None:
            raise DatabaseError("La pagina non esiste più.")
        return Page(row["id"], row["parent_id"], row["title"], row["content"])

    def create_page(self, title: str, parent_id: int | None = None) -> int:
        """Aggiunge una pagina in fondo al suo gruppo (capitoli principali o sottocapitoli di `parent_id`)."""
        with db.transaction(self._conn):
            self._check_parent(None, parent_id)
            position = self._conn.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) FROM page WHERE parent_id IS ?", (parent_id,)
            ).fetchone()[0]
            cursor = self._conn.execute(
                "INSERT INTO page (parent_id, position, title, modified_at) VALUES (?, ?, ?, ?)",
                (parent_id, position, title[:TITLE_MAX], _now()),
            )
            self._touch()
        return cursor.lastrowid

    def rename_page(self, page_id: int, title: str) -> None:
        with db.transaction(self._conn):
            self._conn.execute(
                "UPDATE page SET title = ?, modified_at = ? WHERE id = ?", (title[:TITLE_MAX], _now(), page_id)
            )
            self._touch()

    def save_content(self, page_id: int, content: str) -> None:
        """Salva il testo di una pagina e aggiorna l'indice dei collegamenti che contiene."""
        with db.transaction(self._conn):
            self._store_content(page_id, content)
            self._touch()

    def move_page(self, page_id: int, parent_id: int | None, index: int) -> None:
        """Mette la pagina dentro `parent_id` (None = capitolo principale) nel posto `index` del gruppo."""
        with db.transaction(self._conn):
            row = self._conn.execute("SELECT parent_id FROM page WHERE id = ?", (page_id,)).fetchone()
            if row is None:
                raise DatabaseError("La pagina non esiste più.")
            self._check_parent(page_id, parent_id)
            group = [r[0] for r in self._conn.execute(
                "SELECT id FROM page WHERE parent_id IS ? AND id != ? ORDER BY position", (parent_id, page_id))]
            group.insert(max(0, min(index, len(group))), page_id)
            self._conn.execute("UPDATE page SET parent_id = ? WHERE id = ?", (parent_id, page_id))
            self._renumber(parent_id, group)
            if row["parent_id"] != parent_id:
                self._renumber(row["parent_id"])
            self._touch()

    def delete_page(self, page_id: int) -> None:
        """Elimina la pagina e i suoi sottocapitoli. Nelle altre pagine i collegamenti verso di loro restano come testo."""
        with db.transaction(self._conn):
            row = self._conn.execute("SELECT parent_id FROM page WHERE id = ?", (page_id,)).fetchone()
            if row is None:
                return
            doomed = [r[0] for r in self._conn.execute("SELECT id FROM page WHERE id = ? OR parent_id = ?", (page_id, page_id))]
            self._unlink(links.PAGE, doomed, skip_pages=doomed)
            self._conn.execute("DELETE FROM page WHERE id = ?", (page_id,))  # elimina anche sottocapitoli e indice
            self._renumber(row["parent_id"])
            self._touch()

    def _check_parent(self, page_id: int | None, parent_id: int | None) -> None:
        """Le pagine hanno al massimo due livelli: capitolo e sottocapitolo."""
        if parent_id is None:
            return
        parent = self._conn.execute("SELECT parent_id FROM page WHERE id = ?", (parent_id,)).fetchone()
        if parent is None:
            raise DatabaseError("Il capitolo scelto non esiste più.")
        if parent["parent_id"] is not None or parent_id == page_id:
            raise DatabaseError("Un sottocapitolo non può contenere altre pagine.")
        if page_id is not None and self._conn.execute("SELECT 1 FROM page WHERE parent_id = ?", (page_id,)).fetchone():
            raise DatabaseError("Un capitolo con dei sottocapitoli non può diventare un sottocapitolo.")

    def _renumber(self, parent_id: int | None, ordered_ids: list[int] | None = None) -> None:
        """Riassegna le posizioni 0, 1, 2… a un gruppo di pagine (in `ordered_ids`, o nell'ordine attuale)."""
        if ordered_ids is None:
            ordered_ids = [r[0] for r in self._conn.execute(
                "SELECT id FROM page WHERE parent_id IS ? ORDER BY position", (parent_id,))]
        self._conn.executemany("UPDATE page SET position = ? WHERE id = ?", list(enumerate(ordered_ids)))

    def _store_content(self, page_id: int, content: str) -> None:
        """Scrive il testo di una pagina con le sue parole, la data e l'indice dei collegamenti (dentro una transazione)."""
        self._conn.execute("UPDATE page SET content = ?, words = ?, modified_at = ? WHERE id = ?",
                           (content, plain.count_words(content), _now(), page_id))
        self._set_mentions(page_id, content)

    def _set_mentions(self, page_id: int, content: str) -> None:
        self._conn.execute("DELETE FROM mention WHERE page_id = ?", (page_id,))
        self._conn.executemany(
            "INSERT INTO mention (page_id, ordinal, target_kind, target_id) VALUES (?, ?, ?, ?)",
            [(page_id, ordinal, kind, target_id) for ordinal, (kind, target_id) in enumerate(links.extract_targets(content))],
        )

    def _unlink(self, kind: str, ids: list[int], skip_pages: list[int] = ()) -> None:
        """Prima che questi bersagli spariscano: nei testi che li citano (pagine tranne `skip_pages`, schede degli elementi) toglie
        i collegamenti, il testo resta; i pin e i nodi collegati a una pagina o a un elemento restano come pin e nodi liberi."""
        marks, skip_marks = ",".join("?" * len(ids)), ",".join("?" * len(skip_pages))
        self._conn.execute(f"DELETE FROM bookmark WHERE kind = ? AND target_id IN ({marks})", (kind, *ids))
        if kind not in links.VIEW_KINDS:        # mappe e grafi non sono collegamenti di pin e nodi
            table, name, brief = ("page", "title", "''") if kind == links.PAGE else ("element", "name", "brief")
            self._conn.execute(
                f"UPDATE graph_node SET title = (SELECT {name} FROM {table} WHERE id = graph_node.link_id), "
                f"link_kind = NULL, link_id = NULL WHERE link_kind = ? AND link_id IN ({marks})", (kind, *ids))
            self._conn.execute(
                f"UPDATE pin SET name = (SELECT {name} FROM {table} WHERE id = pin.link_id), brief = (SELECT {brief} FROM {table} WHERE id = pin.link_id), "
                f"link_kind = NULL, link_id = NULL WHERE link_kind = ? AND link_id IN ({marks})", (kind, *ids))
        citing_pages = [r[0] for r in self._conn.execute(
            f"SELECT DISTINCT page_id FROM mention WHERE target_kind = ? AND target_id IN ({marks}) "
            f"AND page_id NOT IN ({skip_marks})", (kind, *ids, *skip_pages))]
        for page_id in citing_pages:
            content = _unlinked(self._conn.execute("SELECT content FROM page WHERE id = ?", (page_id,)).fetchone()[0], kind, ids)
            self._store_content(page_id, content)
        citing_elements = [r[0] for r in self._conn.execute(
            f"SELECT DISTINCT element_id FROM element_mention WHERE target_kind = ? AND target_id IN ({marks})", (kind, *ids))]
        for element_id in citing_elements:
            for field, content in self._conn.execute(
                    "SELECT field, content FROM element_text WHERE element_id = ?", (element_id,)).fetchall():
                self._conn.execute("UPDATE element_text SET content = ? WHERE element_id = ? AND field = ?",
                                   (_unlinked(content, kind, ids), element_id, field))
            self._set_element_mentions(element_id)
            self._conn.execute("UPDATE element SET modified_at = ? WHERE id = ?", (_now(), element_id))

    def _touch(self) -> None:
        """Segna la campagna come modificata (la Home mostra «Modificata oggi…»)."""
        self._conn.execute("UPDATE campaign SET modified_at = ? WHERE id = 1", (_now(),))

    # --- Segnalibri ---------------------------------------------------------------------
    def bookmarks(self) -> list[LinkTarget]:
        """I segnalibri, nell'ordine in cui sono stati aggiunti, ognuno con il nome e il tipo di ciò a cui punta."""
        rows = self._conn.execute("SELECT kind, target_id FROM bookmark ORDER BY position").fetchall()
        return [target for kind, target_id in rows if (target := self._bookmark_target(kind, target_id)) is not None]

    def is_bookmarked(self, kind: str, target_id: int) -> bool:
        return self._conn.execute("SELECT 1 FROM bookmark WHERE kind = ? AND target_id = ?", (kind, target_id)).fetchone() is not None

    def add_bookmark(self, kind: str, target_id: int) -> None:
        """Mette un segnalibro in fondo all'elenco (se c'è già non cambia nulla)."""
        with db.transaction(self._conn):
            if self._bookmark_target(kind, target_id) is None:
                raise DatabaseError("Non si può mettere un segnalibro: la pagina non esiste più.")
            self._conn.execute(
                "INSERT OR IGNORE INTO bookmark (kind, target_id, position) VALUES (?, ?, (SELECT COALESCE(MAX(position), -1) + 1 FROM bookmark))",
                (kind, target_id))

    def remove_bookmark(self, kind: str, target_id: int) -> None:
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM bookmark WHERE kind = ? AND target_id = ?", (kind, target_id))

    def _bookmark_target(self, kind: str, target_id: int) -> LinkTarget | None:
        """Cosa c'è con questo tipo e ID (None se non esiste): il nome e, accanto, la categoria o il tipo. Una lettura sola, senza costruire
        l'elenco di tutti i bersagli."""
        if kind in links.ELEMENT_KINDS:
            row = self._conn.execute("SELECT e.name, c.name FROM element e JOIN category c ON c.id = e.category_id "
                                     "WHERE e.id = ? AND e.kind = ?", (target_id, kind)).fetchone()
        elif kind == links.ENCOUNTER:
            row = self._conn.execute("SELECT name, kind FROM encounter WHERE id = ?", (target_id,)).fetchone()
            row = (row[0], KIND_LABELS[row[1]]) if row else None
        else:
            table = {links.PAGE: ("page", "title", "Pagina"), links.MAP: ("map", "name", "Mappa"), links.GRAPH: ("graph", "name", "Grafo")}.get(kind)
            row = self._conn.execute(f"SELECT {table[1]}, ? FROM {table[0]} WHERE id = ?", (table[2], target_id)).fetchone() if table else None
        return LinkTarget(kind, target_id, row[0], row[1]) if row else None

    # --- «Da fare» ----------------------------------------------------------------------
    def todos(self) -> list[Todo]:
        """Le voci da fare e poi quelle fatte; in ogni gruppo prima la più recente (nuova, spuntata o rimessa tra le aperte)."""
        return [Todo(row["id"], row["text"], bool(row["done"]))
                for row in self._conn.execute("SELECT id, text, done FROM todo ORDER BY done, position")]

    def add_todo(self, text: str) -> int:
        with db.transaction(self._conn):
            cursor = self._conn.execute("INSERT INTO todo (text, done, position) VALUES (?, 0, ?)", (_todo_text(text), self._top_todo(False)))
            self._touch()
        return cursor.lastrowid

    def rename_todo(self, todo_id: int, text: str) -> None:
        with db.transaction(self._conn):
            self._require_todo(self._conn.execute("UPDATE todo SET text = ? WHERE id = ?", (_todo_text(text), todo_id)))
            self._touch()

    def set_todo_done(self, todo_id: int, done: bool) -> None:
        """Spunta (o toglie la spunta): la voce passa in cima all'altro gruppo."""
        with db.transaction(self._conn):
            self._require_todo(self._conn.execute("UPDATE todo SET done = ?, position = ? WHERE id = ?", (done, self._top_todo(done), todo_id)))
            self._touch()

    def delete_todo(self, todo_id: int) -> None:
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM todo WHERE id = ?", (todo_id,))
            self._touch()

    def _top_todo(self, done: bool) -> int:
        """Il posto sopra a tutte le voci del gruppo (fatte o da fare)."""
        return self._conn.execute("SELECT COALESCE(MIN(position) - 1, 0) FROM todo WHERE done = ?", (done,)).fetchone()[0]

    @staticmethod
    def _require_todo(cursor: sqlite3.Cursor) -> None:
        if cursor.rowcount == 0:
            raise DatabaseError("La voce non esiste più.")

    # --- Elementi: personaggi, luoghi, organizzazioni --------------------------------------
    def categories(self, kind: str) -> list[Category]:
        rows = self._conn.execute("SELECT id, kind, name, color FROM category WHERE kind = ? ORDER BY position", (kind,))
        return [Category(row["id"], row["kind"], row["name"], row["color"]) for row in rows]

    def category(self, category_id: int) -> Category:
        row = self._conn.execute("SELECT id, kind, name, color FROM category WHERE id = ?", (category_id,)).fetchone()
        if row is None:
            raise DatabaseError("La categoria non esiste più.")
        return Category(row["id"], row["kind"], row["name"], row["color"])

    def category_usage(self, kind: str) -> dict[int, int]:
        """Quanti elementi usano ciascuna categoria del tipo (anche 0)."""
        rows = self._conn.execute(
            "SELECT c.id, COUNT(e.id) FROM category c LEFT JOIN element e ON e.category_id = c.id WHERE c.kind = ? GROUP BY c.id", (kind,))
        return {row[0]: row[1] for row in rows}

    def create_category(self, kind: str, name: str, color: str) -> int:
        with db.transaction(self._conn):
            cursor = self._conn.execute(
                "INSERT INTO category (kind, name, color, position) VALUES (?, ?, ?, "
                "(SELECT COALESCE(MAX(position) + 1, 0) FROM category WHERE kind = ?))", (kind, _required_name(name), color, kind))
            self._touch()
        return cursor.lastrowid

    def update_category(self, category_id: int, name: str, color: str) -> None:
        with db.transaction(self._conn):
            self._category_kind(category_id)
            self._conn.execute("UPDATE category SET name = ?, color = ? WHERE id = ?", (_required_name(name), color, category_id))
            self._touch()

    def move_category(self, category_id: int, offset: int) -> None:
        """Sposta la categoria di `offset` posti (-1 = prima) fra quelle dello stesso tipo; ai bordi non fa nulla."""
        with db.transaction(self._conn):
            kind = self._category_kind(category_id)
            self._reorder("category", "kind = ?", (kind,), category_id, offset)
            self._touch()

    def delete_category(self, category_id: int, move_to: int | None = None) -> None:
        """Elimina la categoria. Gli elementi che la usano passano alla categoria `move_to` (dello stesso tipo): se ce ne sono,
        va indicata. Ne deve restare almeno una per tipo."""
        with db.transaction(self._conn):
            kind = self._category_kind(category_id)
            if len(self.categories(kind)) == 1:
                raise DatabaseError("Deve restare almeno una categoria.")
            if self.category_usage(kind)[category_id]:
                if move_to is None or move_to == category_id:
                    raise DatabaseError("Scegli la categoria in cui spostare gli elementi.")
                self._check_category(kind, move_to)
                self._conn.execute("UPDATE element SET category_id = ?, modified_at = ? WHERE category_id = ?", (move_to, _now(), category_id))
            self._conn.execute("DELETE FROM category WHERE id = ?", (category_id,))
            self._reorder("category", "kind = ?", (kind,))
            self._touch()

    def _category_kind(self, category_id: int) -> str:
        row = self._conn.execute("SELECT kind FROM category WHERE id = ?", (category_id,)).fetchone()
        if row is None:
            raise DatabaseError("La categoria non esiste più.")
        return row[0]

    def _reorder(self, table: str, scope: str, values: tuple, moved_id: int | None = None, offset: int = 0) -> None:
        """Rimette in fila (0, 1, 2…) la colonna `position` delle righe di `table` che rispettano `scope`;
        prima sposta la riga `moved_id` di `offset` posti (-1 = prima), restando entro i bordi."""
        ids = [row[0] for row in self._conn.execute(f"SELECT id FROM {table} WHERE {scope} ORDER BY position, id", values)]
        if moved_id is not None:
            ids.insert(max(0, min(len(ids) - 1, ids.index(moved_id) + offset)), ids.pop(ids.index(moved_id)))
        self._conn.executemany(f"UPDATE {table} SET position = ? WHERE id = ?", [(position, row_id) for position, row_id in enumerate(ids)])

    def elements(self, kind: str) -> list[Element]:
        """Gli elementi di un tipo in ordine alfabetico."""
        rows = self._conn.execute(f"SELECT {_ELEMENT_COLUMNS} FROM element e WHERE e.kind = ?", (kind,))
        return sorted((Element(*tuple(row)) for row in rows), key=lambda element: fold(element.name))

    def element(self, element_id: int) -> Element:
        row = self._conn.execute(f"SELECT {_ELEMENT_COLUMNS} FROM element e WHERE e.id = ?", (element_id,)).fetchone()
        if row is None:
            raise DatabaseError("L'elemento non esiste più.")
        return Element(*tuple(row))

    def create_element(self, data: ElementInput) -> int:
        image = self._store_element_image(data.image)
        with db.transaction(self._conn):
            self._check_category(data.kind, data.category_id)
            cursor = self._conn.execute(
                "INSERT INTO element (kind, name, category_id, brief, role, modified_at) VALUES (?, ?, ?, ?, ?, ?)",
                (data.kind, data.name[:NAME_MAX], data.category_id, data.brief, data.role, _now()))
            self._set_cover(cursor.lastrowid, image)
            self._touch()
        return cursor.lastrowid

    def update_element(self, element_id: int, data: ElementInput) -> None:
        image = self._store_element_image(data.image)
        with db.transaction(self._conn):
            kind = self._conn.execute("SELECT kind FROM element WHERE id = ?", (element_id,)).fetchone()
            if kind is None:
                raise DatabaseError("L'elemento non esiste più.")
            self._check_category(kind["kind"], data.category_id)
            self._conn.execute(
                "UPDATE element SET name = ?, category_id = ?, brief = ?, role = ?, modified_at = ? WHERE id = ?",
                (data.name[:NAME_MAX], data.category_id, data.brief, data.role, _now(), element_id))
            self._set_cover(element_id, image)
            self._touch()

    def delete_element(self, element_id: int) -> None:
        """Elimina l'elemento. Nelle pagine i collegamenti verso di lui restano come testo."""
        with db.transaction(self._conn):
            row = self._conn.execute("SELECT kind FROM element WHERE id = ?", (element_id,)).fetchone()
            if row is None:
                return
            self._unlink(row["kind"], [element_id])
            self._conn.execute("DELETE FROM element WHERE id = ?", (element_id,))
            self._touch()

    def _store_element_image(self, source: str | Path | None) -> str | None:
        try:
            return self._store_image(source)
        except OSError as error:
            raise DatabaseError(f"Impossibile copiare l'immagine: {error}") from error

    def _check_category(self, kind: str, category_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM category WHERE id = ? AND kind = ?", (category_id, kind)).fetchone() is None:
            raise DatabaseError("La categoria scelta non esiste più.")

    # --- Immagini: la libreria e le immagini degli elementi ---------------------------------------
    def image_folders(self) -> list[ImageFolder]:
        rows = self._conn.execute("SELECT id, parent_id, name FROM image_folder")
        return sorted((ImageFolder(*tuple(row)) for row in rows), key=lambda folder: fold(folder.name))

    def images(self) -> list[Image]:
        """Tutte le immagini della libreria, in ordine alfabetico."""
        rows = self._conn.execute("SELECT id, path, label, folder_id FROM image")
        return sorted((Image(*tuple(row)) for row in rows), key=lambda image: fold(image.label))

    def sync_images(self) -> None:
        """Mette nella libreria i file della cartella immagini che non ci sono ancora (per esempio copiati a mano)."""
        known = {row[0] for row in self._conn.execute("SELECT path FROM image")}
        folder = self.folder / IMAGES_DIRNAME
        new = [(f"{IMAGES_DIRNAME}/{file.name}", file.stem) for file in sorted(folder.iterdir()) if file.is_file()
               and file.suffix.lower() in IMAGE_SUFFIXES and f"{IMAGES_DIRNAME}/{file.name}" not in known] if folder.is_dir() else []
        if new:
            with db.transaction(self._conn):
                self._conn.executemany("INSERT INTO image (path, label) VALUES (?, ?)", new)

    def create_image_folder(self, name: str, parent_id: int | None = None) -> int:
        with db.transaction(self._conn):
            self._check_image_folder(parent_id)
            cursor = self._conn.execute("INSERT INTO image_folder (parent_id, name) VALUES (?, ?)", (parent_id, name[:NAME_MAX]))
            self._touch()
        return cursor.lastrowid

    def update_image_folder(self, folder_id: int, name: str, parent_id: int | None) -> None:
        """Rinomina una cartella e/o la sposta dentro un'altra (`None` = nella cartella principale)."""
        with db.transaction(self._conn):
            self._check_image_folder(folder_id)
            self._check_tree_parent("image_folder", folder_id, parent_id, "cartella")
            self._conn.execute("UPDATE image_folder SET name = ?, parent_id = ? WHERE id = ?", (name[:NAME_MAX], parent_id, folder_id))
            self._touch()

    def delete_image_folder(self, folder_id: int) -> None:
        """Elimina la cartella: immagini e sottocartelle passano in quella che la conteneva. Nessuna immagine si perde."""
        with db.transaction(self._conn):
            row = self._conn.execute("SELECT parent_id FROM image_folder WHERE id = ?", (folder_id,)).fetchone()
            if row is None:
                return
            self._conn.execute("UPDATE image SET folder_id = ? WHERE folder_id = ?", (row["parent_id"], folder_id))
            self._conn.execute("UPDATE image_folder SET parent_id = ? WHERE parent_id = ?", (row["parent_id"], folder_id))
            self._conn.execute("DELETE FROM image_folder WHERE id = ?", (folder_id,))
            self._touch()

    def _check_image_folder(self, folder_id: int | None) -> None:
        if folder_id is not None and self._conn.execute("SELECT 1 FROM image_folder WHERE id = ?", (folder_id,)).fetchone() is None:
            raise DatabaseError("La cartella non esiste più.")

    def _check_tree_parent(self, table: str, item_id: int | None, parent_id: int | None, noun: str) -> None:
        """`parent_id` deve esistere e non può essere `item_id` né un suo discendente: l'albero non si chiude su se stesso.
        `table` è `image_folder` o `map`; `noun` il loro nome nei messaggi."""
        ancestor = parent_id
        while ancestor is not None:
            row = self._conn.execute(f"SELECT parent_id FROM {table} WHERE id = ?", (ancestor,)).fetchone()
            if row is None:
                raise DatabaseError(f"La {noun} non esiste più.")
            if ancestor == item_id:
                raise DatabaseError(f"Una {noun} non può stare dentro se stessa.")
            ancestor = row[0]

    def rename_image(self, image_id: int, label: str) -> None:
        with db.transaction(self._conn):
            self._conn.execute("UPDATE image SET label = ? WHERE id = ?", (label[:NAME_MAX], image_id))
            self._touch()

    def move_image(self, image_id: int, folder_id: int | None) -> None:
        with db.transaction(self._conn):
            self._check_image_folder(folder_id)
            self._conn.execute("UPDATE image SET folder_id = ? WHERE id = ?", (folder_id, image_id))
            self._touch()

    def delete_image(self, image_id: int) -> None:
        """Elimina l'immagine: il file va nel cestino, scompare da ritratti, copertine e testi (che restano senza l'immagine)."""
        with db.transaction(self._conn):
            row = self._conn.execute("SELECT path FROM image WHERE id = ?", (image_id,)).fetchone()
            if row is None:
                return
            path, marker = row["path"], image_refs.source_attr(row["path"])
            file = self.media_file(path)       # un percorso non valido non porta a nessun file: si tolgono solo i riferimenti
            if file is not None and file.exists() and not QFile.moveToTrash(str(file)):
                raise DatabaseError(f"Non riesco a spostare «{file.name}» nel cestino. Chiudi i file aperti e riprova.")
            self._conn.execute("UPDATE campaign SET image = NULL WHERE image = ?", (path,))
            for page_id, content in self._conn.execute("SELECT id, content FROM page WHERE instr(content, ?) > 0", (marker,)).fetchall():
                self._conn.execute("UPDATE page SET content = ? WHERE id = ?", (image_refs.remove(content, path), page_id))
            for element_id, field, content in self._conn.execute(
                    "SELECT element_id, field, content FROM element_text WHERE instr(content, ?) > 0", (marker,)).fetchall():
                self._conn.execute("UPDATE element_text SET content = ? WHERE element_id = ? AND field = ?",
                                   (image_refs.remove(content, path), element_id, field))
            self._conn.execute("DELETE FROM image WHERE id = ?", (image_id,))   # toglie anche i collegamenti degli elementi
            self._touch()

    def drop_unsafe_images(self) -> None:
        """Toglie da una campagna arrivata da fuori (un backup) ogni riferimento a immagini con un percorso non valido
        (vedi `safe_media_path`): dalla libreria, dalle copertine, dagli sfondi delle mappe e dai testi."""
        def unsafe(path: str | None) -> bool:
            return path is not None and self.media_file(path) is None
        with db.transaction(self._conn):
            library = {row[0] for row in self._conn.execute("SELECT path FROM image UNION SELECT path FROM element_image")}
            for path in filter(unsafe, library):
                self._conn.execute("DELETE FROM element_image WHERE path = ?", (path,))
                self._conn.execute("DELETE FROM image WHERE path = ?", (path,))
            for (path,) in self._conn.execute("SELECT DISTINCT image FROM map WHERE image IS NOT NULL").fetchall():
                if unsafe(path):
                    self._conn.execute("UPDATE map SET image = NULL WHERE image = ?", (path,))
            if unsafe(self.campaign().image):
                self._conn.execute("UPDATE campaign SET image = NULL WHERE id = 1")
            for page_id, content in self._conn.execute("SELECT id, content FROM page WHERE instr(lower(content), '<img') > 0").fetchall():
                self._conn.execute("UPDATE page SET content = ? WHERE id = ?", (image_refs.drop_unsafe(content, self.folder), page_id))
            for element_id, field, content in self._conn.execute(
                    "SELECT element_id, field, content FROM element_text WHERE instr(lower(content), '<img') > 0").fetchall():
                self._conn.execute("UPDATE element_text SET content = ? WHERE element_id = ? AND field = ?",
                                   (image_refs.drop_unsafe(content, self.folder), element_id, field))

    def image_uses(self, path: str) -> list[LinkTarget]:
        """Dove è usata un'immagine: la campagna (copertina), poi pagine e schede (ritratto, immagini collegate, testi) e mappe (sfondo)."""
        marker = image_refs.source_attr(path)
        used = {(links.PAGE, row[0]) for row in self._conn.execute("SELECT id FROM page WHERE instr(content, ?) > 0", (marker,))}
        used |= {(row[0], row[1]) for row in self._conn.execute(
            "SELECT kind, id FROM element WHERE id IN (SELECT element_id FROM element_image WHERE path = ? "
            "UNION SELECT element_id FROM element_text WHERE instr(content, ?) > 0)", (path, marker))}
        uses = [target for key, target in self._all_targets().items() if key in used]
        uses += [LinkTarget(links.MAP, node.id, node.name, "Sfondo della mappa") for node in self.maps() if node.image == path]
        campaign = self.campaign()
        if campaign.image == path:
            uses.insert(0, LinkTarget(links.CAMPAIGN, 0, campaign.name, "Copertina della campagna"))
        return uses

    def element_images(self, element_id: int) -> list[Image]:
        """Le immagini collegate a un elemento; la prima è il ritratto (o la copertina)."""
        rows = self._conn.execute(
            "SELECT i.id, i.path, i.label, i.folder_id FROM element_image l JOIN image i ON i.path = l.path "
            "WHERE l.element_id = ? ORDER BY l.position", (element_id,))
        return [Image(*tuple(row)) for row in rows]

    def link_element_images(self, element_id: int, paths: list[str]) -> None:
        """Collega immagini della libreria a un elemento, in fondo; quelle già collegate restano dove sono."""
        with db.transaction(self._conn):
            current = self._element_image_paths(element_id)
            self._set_element_images(element_id, current + [path for path in dict.fromkeys(paths) if path not in current])

    def unlink_element_image(self, element_id: int, path: str) -> None:
        with db.transaction(self._conn):
            self._set_element_images(element_id, [p for p in self._element_image_paths(element_id) if p != path])

    def set_element_cover(self, element_id: int, path: str) -> None:
        """Fa dell'immagine il ritratto (o la copertina) dell'elemento: la collega, se non lo è, e la mette per prima."""
        with db.transaction(self._conn):
            self._set_cover(element_id, path)

    def _element_image_paths(self, element_id: int) -> list[str]:
        return [row[0] for row in self._conn.execute(
            "SELECT path FROM element_image WHERE element_id = ? ORDER BY position", (element_id,))]

    def _set_element_images(self, element_id: int, paths: list[str]) -> None:
        self._check_element(element_id)
        self._conn.execute("DELETE FROM element_image WHERE element_id = ?", (element_id,))
        self._conn.executemany("INSERT INTO element_image (element_id, path, position) VALUES (?, ?, ?)",
                               [(element_id, path, position) for position, path in enumerate(paths)])
        self._conn.execute("UPDATE element SET modified_at = ? WHERE id = ?", (_now(), element_id))
        self._touch()

    def _set_cover(self, element_id: int, path: str | None) -> None:
        """Il ritratto diventa `path` (le altre immagini restano collegate); con `None` il ritratto attuale si scollega."""
        current = self._element_image_paths(element_id)
        self._set_element_images(element_id, current[1:] if path is None else [path, *(p for p in current if p != path)])

    # --- Mappe: l'albero delle mappe, i tipi di pin, i pin ---------------------------------------------
    def maps(self) -> list[Map]:
        """Tutte le mappe, in ordine alfabetico."""
        rows = self._conn.execute("SELECT id, parent_id, name, image FROM map")
        return sorted((Map(*tuple(row)) for row in rows), key=lambda node: fold(node.name))

    def pin_counts(self) -> dict[int, int]:
        """Quanti pin ha ogni mappa (quelle senza pin non compaiono)."""
        return {row[0]: row[1] for row in self._conn.execute("SELECT map_id, COUNT(*) FROM pin GROUP BY map_id")}

    def create_map(self, name: str, parent_id: int | None = None, image: str | None = None) -> int:
        """`image` è un'immagine della libreria."""
        with db.transaction(self._conn):
            self._check_tree_parent("map", None, parent_id, "mappa")
            cursor = self._conn.execute("INSERT INTO map (parent_id, name, image) VALUES (?, ?, ?)", (parent_id, name[:NAME_MAX], image))
            self._touch()
        return cursor.lastrowid

    def update_map(self, map_id: int, name: str, parent_id: int | None, image: str | None) -> None:
        """Rinomina la mappa, la sposta dentro un'altra (`None` = al primo livello) e ne cambia lo sfondo. I pin restano dove sono."""
        with db.transaction(self._conn):
            self._check_map(map_id)
            self._check_tree_parent("map", map_id, parent_id, "mappa")
            self._conn.execute("UPDATE map SET name = ?, parent_id = ?, image = ? WHERE id = ?", (name[:NAME_MAX], parent_id, image, map_id))
            self._touch()

    def delete_map(self, map_id: int) -> None:
        """Elimina la mappa e i suoi pin; le sue sottomappe salgono di un livello. I pin di altre mappe che la aprivano restano, senza mappa.
        Nei testi che la citavano il collegamento resta come testo semplice."""
        with db.transaction(self._conn):
            row = self._conn.execute("SELECT parent_id FROM map WHERE id = ?", (map_id,)).fetchone()
            if row is None:
                return
            self._conn.execute("UPDATE map SET parent_id = ? WHERE parent_id = ?", (row["parent_id"], map_id))
            self._unlink(links.MAP, [map_id])
            self._conn.execute("DELETE FROM map WHERE id = ?", (map_id,))   # toglie anche i suoi pin
            self._touch()

    def _check_map(self, map_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM map WHERE id = ?", (map_id,)).fetchone() is None:
            raise DatabaseError("La mappa non esiste più.")

    def pin_types(self) -> list[PinType]:
        rows = self._conn.execute("SELECT id, name, icon, color FROM pin_type ORDER BY position")
        return [PinType(*tuple(row)) for row in rows]

    def pin_type_usage(self) -> dict[int, int]:
        """Quanti pin usano ciascun tipo (anche 0)."""
        rows = self._conn.execute("SELECT t.id, COUNT(p.id) FROM pin_type t LEFT JOIN pin p ON p.type_id = t.id GROUP BY t.id")
        return {row[0]: row[1] for row in rows}

    def create_pin_type(self, name: str, icon: str, color: str) -> int:
        with db.transaction(self._conn):
            cursor = self._conn.execute(
                "INSERT INTO pin_type (name, icon, color, position) VALUES (?, ?, ?, (SELECT COALESCE(MAX(position) + 1, 0) FROM pin_type))",
                (_required_name(name), icon, color))
            self._touch()
        return cursor.lastrowid

    def update_pin_type(self, type_id: int, name: str, icon: str, color: str) -> None:
        with db.transaction(self._conn):
            self._check_pin_type(type_id)
            self._conn.execute("UPDATE pin_type SET name = ?, icon = ?, color = ? WHERE id = ?", (_required_name(name), icon, color, type_id))
            self._touch()

    def move_pin_type(self, type_id: int, offset: int) -> None:
        """Sposta il tipo di `offset` posti (-1 = prima); ai bordi non fa nulla."""
        with db.transaction(self._conn):
            self._check_pin_type(type_id)
            self._reorder("pin_type", "1", (), type_id, offset)
            self._touch()

    def delete_pin_type(self, type_id: int, move_to: int | None = None) -> None:
        """Elimina il tipo. I pin che lo usano passano al tipo `move_to`: se ce ne sono, va indicato. Ne deve restare almeno uno."""
        with db.transaction(self._conn):
            self._check_pin_type(type_id)
            if len(self.pin_types()) == 1:
                raise DatabaseError("Deve restare almeno un tipo di pin.")
            if self.pin_type_usage()[type_id]:
                if move_to is None or move_to == type_id:
                    raise DatabaseError("Scegli il tipo in cui spostare i pin.")
                self._check_pin_type(move_to)
                self._conn.execute("UPDATE pin SET type_id = ? WHERE type_id = ?", (move_to, type_id))
            self._conn.execute("DELETE FROM pin_type WHERE id = ?", (type_id,))
            self._reorder("pin_type", "1", ())
            self._touch()

    def _check_pin_type(self, type_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM pin_type WHERE id = ?", (type_id,)).fetchone() is None:
            raise DatabaseError("Il tipo di pin non esiste più.")

    def pins(self, map_id: int) -> list[Pin]:
        """I pin di una mappa, nell'ordine in cui sono stati posati."""
        return self._pins("WHERE map_id = ? ORDER BY id", (map_id,))

    def pins_linked_to(self, kind: str, target_id: int) -> list[Pin]:
        """I pin collegati a una pagina o a un elemento, su tutte le mappe."""
        return self._pins("WHERE link_kind = ? AND link_id = ? ORDER BY map_id, id", (kind, target_id))

    def _pins(self, condition: str, values: tuple) -> list[Pin]:
        rows = self._conn.execute(
            "SELECT id, map_id, type_id, x, y, name, brief, link_kind, link_id, opens_map_id FROM pin " + condition, values).fetchall()
        targets = self._all_targets()
        briefs = {row[0]: row[1] for row in self._conn.execute("SELECT id, brief FROM element")}
        pins = []
        for row in rows:
            link = targets.get((row["link_kind"], row["link_id"]))
            if link is None:
                name, brief = row["name"], row["brief"]
            else:   # un pin collegato prende nome e testo da ciò a cui è collegato (una pagina non ha un testo «in breve»)
                name, brief = link.name, briefs[link.id] if link.kind in links.ELEMENT_KINDS else ""
            pins.append(Pin(row["id"], row["map_id"], row["type_id"], row["x"], row["y"], name, brief, link, row["opens_map_id"]))
        return pins

    def create_pin(self, map_id: int, x: float, y: float, data: PinInput) -> int:
        """Posa un pin; `x` e `y` sono la posizione sull'immagine (da 0 a 1)."""
        with db.transaction(self._conn):
            self._check_map(map_id)
            cursor = self._conn.execute(
                "INSERT INTO pin (map_id, x, y, type_id, name, brief, link_kind, link_id, opens_map_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (map_id, _unit(x), _unit(y), *self._pin_values(map_id, data)))
            self._touch()
        return cursor.lastrowid

    def update_pin(self, pin_id: int, data: PinInput) -> None:
        with db.transaction(self._conn):
            row = self._conn.execute("SELECT map_id FROM pin WHERE id = ?", (pin_id,)).fetchone()
            if row is None:
                raise DatabaseError("Il pin non esiste più.")
            self._conn.execute(
                "UPDATE pin SET type_id = ?, name = ?, brief = ?, link_kind = ?, link_id = ?, opens_map_id = ? WHERE id = ?",
                (*self._pin_values(row["map_id"], data), pin_id))
            self._touch()

    def move_pin(self, pin_id: int, x: float, y: float) -> None:
        with db.transaction(self._conn):
            self._conn.execute("UPDATE pin SET x = ?, y = ? WHERE id = ?", (_unit(x), _unit(y), pin_id))
            self._touch()

    def delete_pin(self, pin_id: int) -> None:
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM pin WHERE id = ?", (pin_id,))
            self._touch()

    def _pin_values(self, map_id: int, data: PinInput) -> tuple:
        """Controlla i dati di un pin messo su `map_id` e li dispone come le colonne (tipo, nome, testo, collegamento, mappa che apre).
        Un pin collegato non conserva un nome e un testo suoi: li prende da ciò a cui è collegato."""
        self._check_pin_type(data.type_id)
        if data.opens_map_id is not None:
            self._check_map(data.opens_map_id)
            if data.opens_map_id == map_id:
                raise DatabaseError("Un pin non può aprire la mappa su cui sta.")
        if data.link is None:
            return data.type_id, data.name[:NAME_MAX], data.brief, None, None, data.opens_map_id
        self._check_link(data.link, "il pin")
        return data.type_id, "", "", *data.link, data.opens_map_id

    def _check_link(self, link: tuple[str, int], owner: str) -> None:
        """La pagina o l'elemento `link` = (tipo, ID) a cui sta per essere collegato `owner` («il pin», «il nodo») deve esistere."""
        kind, target_id = link
        found = (self._conn.execute("SELECT 1 FROM page WHERE id = ?", (target_id,)) if kind == links.PAGE else
                 self._conn.execute("SELECT 1 FROM element WHERE id = ? AND kind = ?", (target_id, kind))).fetchone()
        if found is None:
            raise DatabaseError(f"Ciò a cui {owner} è collegato non esiste più.")

    # --- Schede tecniche: mostri e PNG ------------------------------------------------------------------
    def creatures(self) -> list[CreatureRow]:
        """Tutte le schede (solo ciò che serve all'elenco), in ordine alfabetico."""
        rows = self._conn.execute("SELECT id, name, size, kind, challenge, source FROM creature")
        return sorted((CreatureRow(*tuple(row)) for row in rows), key=lambda creature: fold(creature.name))

    def creature(self, creature_id: int) -> Creature:
        row = self._conn.execute(f"SELECT {', '.join(_CREATURE_COLUMNS)} FROM creature WHERE id = ?", (creature_id,)).fetchone()
        if row is None:
            raise DatabaseError("La scheda non esiste più.")
        fields = list(row)
        fields[7:13] = [tuple(fields[7:13])]
        features = tuple(Feature(*tuple(feature)) for feature in self._conn.execute(
            "SELECT section, name, text FROM creature_feature WHERE creature_id = ? ORDER BY position", (creature_id,)))
        return Creature(*fields, features, creature_id)

    def create_creature(self, data: CreatureInput) -> int:
        values, features = _creature_parts(data)
        with db.transaction(self._conn):
            creature_id = self._insert_creature(values, features)
            self._touch()
        return creature_id

    def update_creature(self, creature_id: int, data: CreatureInput) -> None:
        values, features = _creature_parts(data)
        with db.transaction(self._conn):
            self._check_creature(creature_id)
            assignments = ", ".join(f"{column} = ?" for column in _CREATURE_COLUMNS)
            self._conn.execute(f"UPDATE creature SET {assignments} WHERE id = ?", (*values, creature_id))
            self._conn.execute("DELETE FROM creature_feature WHERE creature_id = ?", (creature_id,))
            self._insert_features(creature_id, features)
            self._touch()

    def delete_creature(self, creature_id: int) -> None:
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM creature WHERE id = ?", (creature_id,))
            self._touch()

    def import_creatures(self, items: list[CreatureInput]) -> ImportResult:
        """Aggiunge le schede lette da un file. Una scheda identica a una già presente (stesso nome, stessi dati) non si aggiunge."""
        added = 0
        with db.transaction(self._conn):
            for data in items:
                values, features = _creature_parts(data)
                if not self._creature_exists(values, features):
                    self._insert_creature(values, features)
                    added += 1
            if added:
                self._touch()
        return ImportResult(added, len(items) - added)

    def _creature_exists(self, values: tuple, features: list[Feature]) -> bool:
        wanted = [(feature.section, feature.name, feature.text) for feature in features]
        for row in self._conn.execute(f"SELECT id, {', '.join(_CREATURE_COLUMNS)} FROM creature WHERE name = ? COLLATE NOCASE", (values[0],)):
            stored = [tuple(feature) for feature in self._conn.execute(
                "SELECT section, name, text FROM creature_feature WHERE creature_id = ? ORDER BY position", (row["id"],))]
            if tuple(row)[1:] == values and stored == wanted:
                return True
        return False

    def _insert_creature(self, values: tuple, features: list[Feature]) -> int:
        marks = ", ".join("?" * len(_CREATURE_COLUMNS))
        cursor = self._conn.execute(f"INSERT INTO creature ({', '.join(_CREATURE_COLUMNS)}) VALUES ({marks})", values)
        self._insert_features(cursor.lastrowid, features)
        return cursor.lastrowid

    def _insert_features(self, creature_id: int, features: list[Feature]) -> None:
        self._conn.executemany(
            "INSERT INTO creature_feature (creature_id, section, position, name, text) VALUES (?, ?, ?, ?, ?)",
            [(creature_id, feature.section, position, feature.name, feature.text) for position, feature in enumerate(features)])

    def _check_creature(self, creature_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM creature WHERE id = ?", (creature_id,)).fetchone() is None:
            raise DatabaseError("La scheda non esiste più.")

    # --- Incontri: giocatori presenti e schede tecniche che servono ------------------------------------------
    def encounters(self) -> list[Encounter]:
        """Tutti gli incontri, in ordine alfabetico."""
        return self._read_encounters()

    def encounter(self, encounter_id: int) -> Encounter:
        found = self._read_encounters(encounter_id)
        if not found:
            raise DatabaseError("L'incontro non esiste più.")
        return found[0]

    def encounters_using(self, creature_id: int) -> list[str]:
        """I nomi degli incontri che usano questa scheda (si perdono se la scheda viene eliminata)."""
        rows = self._conn.execute("SELECT e.name FROM encounter e JOIN encounter_creature c ON c.encounter_id = e.id WHERE c.creature_id = ?",
                                  (creature_id,))
        return sorted((row[0] for row in rows), key=fold)

    def create_encounter(self, data: EncounterInput) -> int:
        name, kind, party, slots = _encounter_parts(data)
        with db.transaction(self._conn):
            encounter_id = self._conn.execute("INSERT INTO encounter (name, kind) VALUES (?, ?)", (name, kind)).lastrowid
            self._store_encounter_lists(encounter_id, party, slots)
            self._touch()
        return encounter_id

    def update_encounter(self, encounter_id: int, data: EncounterInput) -> None:
        name, kind, party, slots = _encounter_parts(data)
        with db.transaction(self._conn):
            self._check_encounter(encounter_id)
            self._conn.execute("UPDATE encounter SET name = ?, kind = ? WHERE id = ?", (name, kind, encounter_id))
            self._conn.execute("DELETE FROM encounter_party WHERE encounter_id = ?", (encounter_id,))
            self._conn.execute("DELETE FROM encounter_creature WHERE encounter_id = ?", (encounter_id,))
            self._store_encounter_lists(encounter_id, party, slots)
            self._touch()

    def delete_encounter(self, encounter_id: int) -> None:
        """Elimina l'incontro: le schede tecniche che usava restano dove sono."""
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM bookmark WHERE kind = ? AND target_id = ?", (links.ENCOUNTER, encounter_id))
            self._conn.execute("DELETE FROM encounter WHERE id = ?", (encounter_id,))
            self._touch()

    def _read_encounters(self, only: int | None = None) -> list[Encounter]:
        where, args = ("WHERE encounter_id = ?", (only,)) if only is not None else ("", ())
        parties, slots = defaultdict(list), defaultdict(list)
        for row in self._conn.execute(f"SELECT encounter_id, level, count FROM encounter_party {where} ORDER BY position", args):
            parties[row[0]].append(PartyGroup(row[1], row[2]))
        for row in self._conn.execute(f"SELECT encounter_id, creature_id, quantity FROM encounter_creature {where} ORDER BY position", args):
            slots[row[0]].append(Slot(row[1], row[2]))
        rows = self._conn.execute("SELECT id, name, kind FROM encounter" + (" WHERE id = ?" if only is not None else ""), args[:1])
        found = [Encounter(row["name"], row["kind"], tuple(parties[row["id"]]), tuple(slots[row["id"]]), row["id"]) for row in rows]
        return sorted(found, key=lambda encounter: fold(encounter.name))

    def _store_encounter_lists(self, encounter_id: int, party: list[PartyGroup], slots: list[Slot]) -> None:
        for slot in slots:
            self._check_creature(slot.creature_id)
        self._conn.executemany("INSERT INTO encounter_party (encounter_id, position, level, count) VALUES (?, ?, ?, ?)",
                               [(encounter_id, position, group.level, group.count) for position, group in enumerate(party)])
        self._conn.executemany("INSERT INTO encounter_creature (encounter_id, creature_id, position, quantity) VALUES (?, ?, ?, ?)",
                               [(encounter_id, slot.creature_id, position, slot.quantity) for position, slot in enumerate(slots)])

    def _check_encounter(self, encounter_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM encounter WHERE id = ?", (encounter_id,)).fetchone() is None:
            raise DatabaseError("L'incontro non esiste più.")

    # --- Grafi: nodi collegati da archi --------------------------------------------------------------------
    def graphs(self) -> list[Graph]:
        """Tutti i grafi, in ordine alfabetico."""
        rows = self._conn.execute("SELECT id, name FROM graph")
        return sorted((Graph(*tuple(row)) for row in rows), key=lambda graph: fold(graph.name))

    def create_graph(self, name: str) -> int:
        with db.transaction(self._conn):
            cursor = self._conn.execute("INSERT INTO graph (name) VALUES (?)", (name[:NAME_MAX],))
            self._touch()
        return cursor.lastrowid

    def rename_graph(self, graph_id: int, name: str) -> None:
        with db.transaction(self._conn):
            self._check_graph(graph_id)
            self._conn.execute("UPDATE graph SET name = ? WHERE id = ?", (name[:NAME_MAX], graph_id))
            self._touch()

    def delete_graph(self, graph_id: int) -> None:
        """Elimina il grafo con i suoi nodi e archi. Le pagine e gli elementi a cui i nodi erano collegati non cambiano;
        nei testi che citavano il grafo il collegamento resta come testo semplice."""
        with db.transaction(self._conn):
            self._unlink(links.GRAPH, [graph_id])
            self._conn.execute("DELETE FROM graph WHERE id = ?", (graph_id,))
            self._touch()

    def _check_graph(self, graph_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM graph WHERE id = ?", (graph_id,)).fetchone() is None:
            raise DatabaseError("Il grafo non esiste più.")

    def graph_nodes(self, graph_id: int) -> list[GraphNode]:
        """I nodi di un grafo, nell'ordine in cui sono stati creati."""
        rows = self._conn.execute(
            "SELECT id, graph_id, x, y, title, description, color, link_kind, link_id FROM graph_node WHERE graph_id = ? ORDER BY id", (graph_id,))
        targets = self._all_targets()
        nodes = []
        for row in rows:
            link = targets.get((row["link_kind"], row["link_id"]))
            nodes.append(GraphNode(row["id"], row["graph_id"], row["x"], row["y"], link.name if link is not None else row["title"],
                                   row["description"], row["color"], link))
        return nodes

    def graph_edges(self, graph_id: int) -> list[GraphEdge]:
        """Gli archi di un grafo, nell'ordine in cui sono stati creati (un arco finisce solo su archi più vecchi)."""
        rows = self._conn.execute(
            "SELECT id, a_node, a_edge, b_node, b_edge, label, direction FROM graph_edge WHERE graph_id = ? ORDER BY id", (graph_id,))
        return [GraphEdge(row["id"], _endpoint(row["a_node"], row["a_edge"]), _endpoint(row["b_node"], row["b_edge"]), row["label"], row["direction"])
                for row in rows]

    def create_node(self, graph_id: int, x: float, y: float, data: NodeInput) -> int:
        with db.transaction(self._conn):
            self._check_graph(graph_id)
            cursor = self._conn.execute(
                "INSERT INTO graph_node (graph_id, x, y, title, description, color, link_kind, link_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (graph_id, x, y, *self._node_values(data)))
            self._touch()
        return cursor.lastrowid

    def update_node(self, node_id: int, data: NodeInput) -> None:
        with db.transaction(self._conn):
            self._check_node(node_id)
            self._conn.execute(
                "UPDATE graph_node SET title = ?, description = ?, color = ?, link_kind = ?, link_id = ? WHERE id = ?",
                (*self._node_values(data), node_id))
            self._touch()

    def move_node(self, node_id: int, x: float, y: float) -> None:
        with db.transaction(self._conn):
            self._conn.execute("UPDATE graph_node SET x = ?, y = ? WHERE id = ?", (x, y, node_id))
            self._touch()

    def delete_node(self, node_id: int) -> None:
        """Elimina il nodo e i suoi archi (e gli archi che finiscono su di loro)."""
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM graph_node WHERE id = ?", (node_id,))
            self._touch()

    def _check_node(self, node_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM graph_node WHERE id = ?", (node_id,)).fetchone() is None:
            raise DatabaseError("Il nodo non esiste più.")

    def _node_values(self, data: NodeInput) -> tuple:
        """Controlla i dati di un nodo e li dispone come le colonne (titolo, descrizione, colore, collegamento).
        Un nodo collegato non conserva un titolo suo: lo prende da ciò a cui è collegato; uno libero ha bisogno di un titolo."""
        description = data.description[:DESCRIPTION_MAX]
        if data.link is None:
            title = data.title.strip()[:NAME_MAX]
            if not title:
                raise DatabaseError("Il nodo ha bisogno di un titolo.")
            return title, description, data.color, None, None
        self._check_link(data.link, "il nodo")
        return "", description, data.color, *data.link

    def create_edge(self, first: Endpoint, second: Endpoint) -> int:
        """Collega due nodi, o un nodo e un arco, o due archi, dello stesso grafo (l'etichetta parte vuota, la freccia va da `first`
        a `second`). Restituisce l'ID dell'arco."""
        if first == second:
            raise DatabaseError("Non si può collegare un elemento a se stesso.")
        with db.transaction(self._conn):
            if self._endpoint_graph(first) != self._endpoint_graph(second):
                raise DatabaseError("I due elementi non sono nello stesso grafo.")
            ends = (*_columns(first), *_columns(second))
            if self._conn.execute("SELECT 1 FROM graph_edge WHERE (a_node IS ? AND a_edge IS ? AND b_node IS ? AND b_edge IS ?) "
                                  "OR (a_node IS ? AND a_edge IS ? AND b_node IS ? AND b_edge IS ?)", (*ends, *_columns(second), *_columns(first))).fetchone():
                raise DatabaseError("I due elementi sono già collegati.")
            cursor = self._conn.execute(
                "INSERT INTO graph_edge (graph_id, a_node, a_edge, b_node, b_edge, direction) VALUES (?, ?, ?, ?, ?, ?)",
                (self._endpoint_graph(first), *ends, TO_B))
            self._touch()
        return cursor.lastrowid

    def _endpoint_graph(self, end: Endpoint) -> int:
        """Il grafo a cui appartiene un nodo o un arco (errore se non esiste più)."""
        table, name = ("graph_node", "Il nodo") if end.kind == KIND_NODE else ("graph_edge", "L'arco")
        row = self._conn.execute(f"SELECT graph_id FROM {table} WHERE id = ?", (end.id,)).fetchone()
        if row is None:
            raise DatabaseError(f"{name} non esiste più.")
        return row[0]

    def update_edge(self, edge_id: int, label: str, direction: int) -> None:
        if direction not in (NO_ARROW, TO_B, TO_A, BOTH):
            raise DatabaseError("La direzione dell'arco non è valida.")
        with db.transaction(self._conn):
            cursor = self._conn.execute("UPDATE graph_edge SET label = ?, direction = ? WHERE id = ?", (label.strip()[:LABEL_MAX], direction, edge_id))
            if cursor.rowcount == 0:
                raise DatabaseError("L'arco non esiste più.")
            self._touch()

    def delete_edge(self, edge_id: int) -> None:
        """Elimina l'arco e gli archi che finiscono su di lui."""
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM graph_edge WHERE id = ?", (edge_id,))
            self._touch()

    # --- Schede degli elementi: testi e relazioni ----------------------------------------------
    def texts(self, element_id: int) -> dict[str, str]:
        """I testi della scheda di un elemento (campo -> testo nel formato dell'editor); i campi vuoti non ci sono."""
        rows = self._conn.execute("SELECT field, content FROM element_text WHERE element_id = ?", (element_id,))
        return {row["field"]: row["content"] for row in rows}

    def save_text(self, element_id: int, field: str, content: str) -> None:
        """Salva un testo della scheda (se è vuoto il campo si svuota) e aggiorna l'indice dei collegamenti che contiene."""
        with db.transaction(self._conn):
            self._check_element(element_id)
            if content:
                self._conn.execute(
                    "INSERT INTO element_text (element_id, field, content) VALUES (?, ?, ?) "
                    "ON CONFLICT (element_id, field) DO UPDATE SET content = excluded.content", (element_id, field, content))
            else:
                self._conn.execute("DELETE FROM element_text WHERE element_id = ? AND field = ?", (element_id, field))
            self._set_element_mentions(element_id)
            self._conn.execute("UPDATE element SET modified_at = ? WHERE id = ?", (_now(), element_id))
            self._touch()

    def _set_element_mentions(self, element_id: int) -> None:
        """Ricostruisce l'indice dei collegamenti dell'elemento: quelli di tutti i suoi testi insieme."""
        self._conn.execute("DELETE FROM element_mention WHERE element_id = ?", (element_id,))
        contents = [row[0] for row in self._conn.execute(
            "SELECT content FROM element_text WHERE element_id = ? ORDER BY field", (element_id,))]
        targets = dict.fromkeys(target for content in contents for target in links.extract_targets(content))
        self._conn.executemany("INSERT INTO element_mention (element_id, target_kind, target_id) VALUES (?, ?, ?)",
                               [(element_id, *target) for target in targets])

    def relations(self, element_id: int) -> list[Relation]:
        """Le relazioni dell'elemento, nell'ordine in cui sono state create."""
        rows = self._conn.execute(
            f"SELECT r.id, r.label, r.status, r.note, r.leader, {_ELEMENT_COLUMNS} "
            "FROM relation r JOIN element e ON e.id = CASE WHEN r.a_id = ?1 THEN r.b_id ELSE r.a_id END "
            "WHERE r.a_id = ?1 OR r.b_id = ?1 ORDER BY r.id", (element_id,))
        return [Relation(row[0], Element(*tuple(row)[5:]), row[1], row[2], row[3], bool(row[4])) for row in rows]

    def add_relation(self, element_id: int, other_id: int) -> int:
        """Collega due elementi (la relazione parte senza testo; compare in entrambe le schede). Restituisce il suo ID."""
        if element_id == other_id:
            raise DatabaseError("Un elemento non può essere collegato a se stesso.")
        a_id, b_id = sorted((element_id, other_id))
        with db.transaction(self._conn):
            self._check_element(a_id)
            self._check_element(b_id)
            if self._conn.execute("SELECT 1 FROM relation WHERE a_id = ? AND b_id = ?", (a_id, b_id)).fetchone():
                raise DatabaseError("I due elementi sono già collegati.")
            cursor = self._conn.execute("INSERT INTO relation (a_id, b_id) VALUES (?, ?)", (a_id, b_id))
            self._touch()
        return cursor.lastrowid

    def update_relation(self, relation_id: int, **changes: str | bool) -> None:
        """Cambia il testo della relazione (`label`) o i dati del membro (`status`, `note`, `leader`)."""
        if not changes or changes.keys() - set(_RELATION_COLUMNS) or changes.get("status", "active") not in MEMBER_STATUSES:
            raise ValueError(f"Modifica non valida: {changes}")
        values = {name: int(value) if name == "leader" else str(value)[:RELATION_TEXT_MAX] if name != "status" else value
                  for name, value in changes.items()}
        with db.transaction(self._conn):
            cursor = self._conn.execute(
                f"UPDATE relation SET {', '.join(f'{name} = ?' for name in values)} WHERE id = ?", (*values.values(), relation_id))
            if cursor.rowcount == 0:
                raise DatabaseError("La relazione non esiste più.")
            self._touch()

    def remove_relation(self, relation_id: int) -> None:
        with db.transaction(self._conn):
            self._conn.execute("DELETE FROM relation WHERE id = ?", (relation_id,))
            self._touch()

    def _check_element(self, element_id: int) -> None:
        if self._conn.execute("SELECT 1 FROM element WHERE id = ?", (element_id,)).fetchone() is None:
            raise DatabaseError("L'elemento non esiste più.")

    # --- Collegamenti --------------------------------------------------------------------
    def _all_targets(self) -> dict[tuple[str, int], LinkTarget]:
        """Tutto ciò a cui si può collegare un testo: prima le pagine (nell'ordine dell'albero), poi gli elementi per tipo e nome,
        poi le mappe e i grafi (in ordine alfabetico)."""
        targets = {
            (links.PAGE, node.id): LinkTarget(links.PAGE, node.id, node.title, f"Pagina {number}")
            for node, number in numbered_pages(self.pages())
        }
        names = {row["id"]: row["name"] for row in self._conn.execute("SELECT id, name FROM category")}
        for kind in links.ELEMENT_KINDS:
            for element in self.elements(kind):
                targets[(kind, element.id)] = LinkTarget(kind, element.id, element.name, names[element.category_id])
        for node in sorted(self.maps(), key=lambda node: fold(node.name)):
            targets[(links.MAP, node.id)] = LinkTarget(links.MAP, node.id, node.name, "Mappa")
        for graph in self.graphs():
            targets[(links.GRAPH, graph.id)] = LinkTarget(links.GRAPH, graph.id, graph.name, "Grafo")
        return targets

    @cached_property
    def speller(self) -> Speller:
        """Il controllo ortografico dei testi della campagna: i nomi di pagine, elementi, mappe e grafi sono sempre corretti."""
        return Speller(self._spelling_names)

    def _spelling_names(self) -> list[str]:
        queries = ("SELECT title FROM page", "SELECT name FROM element", "SELECT name FROM map", "SELECT name FROM graph")
        return [row[0] for query in queries for row in self._conn.execute(query)]

    def link_target(self, kind: str, target_id: int) -> LinkTarget | None:
        """Il bersaglio con questo tipo e ID (None se non esiste più)."""
        return self._all_targets().get((kind, target_id))

    def link_targets(self, query: str, exclude: tuple[str, int] | None = None, limit: int = 8, views: bool = True) -> list[LinkTarget]:
        """I bersagli il cui nome corrisponde a `query` (prima quelli che iniziano così). `exclude` = (tipo, ID) da saltare;
        con `views` False niente mappe e grafi (a un pin o a un nodo si collegano solo pagine ed elementi)."""
        found = []
        for order, (key, target) in enumerate(self._all_targets().items()):
            score = rank(query, target.name)
            if score is not None and key != exclude and (views or target.kind not in links.VIEW_KINDS):
                found.append((score, order, target))
        return [target for _, _, target in sorted(found, key=lambda item: item[:2])][:limit]

    def cited_in(self, page_id: int) -> list[LinkTarget]:
        """I bersagli citati nel testo della pagina, nell'ordine in cui compaiono."""
        keys = [(r["target_kind"], r["target_id"]) for r in self._conn.execute(
            "SELECT target_kind, target_id FROM mention WHERE page_id = ? ORDER BY ordinal", (page_id,))]
        targets = self._all_targets()
        return [targets[key] for key in keys if key in targets]

    def cited_by(self, kind: str, target_id: int) -> list[LinkTarget]:
        """Le pagine (nell'ordine dell'albero) e le schede degli elementi che citano questo bersaglio."""
        citing = {(links.PAGE, r[0]) for r in self._conn.execute(
            "SELECT DISTINCT page_id FROM mention WHERE target_kind = ? AND target_id = ?", (kind, target_id))}
        citing |= {(r["kind"], r["id"]) for r in self._conn.execute(
            "SELECT DISTINCT e.kind, e.id FROM element_mention m JOIN element e ON e.id = m.element_id "
            "WHERE m.target_kind = ? AND m.target_id = ?", (kind, target_id))}
        return [target for key, target in self._all_targets().items() if key in citing]
