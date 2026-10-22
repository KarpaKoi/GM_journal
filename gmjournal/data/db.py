"""Database SQLite di una campagna: apertura, transazioni e aggiornamento dello schema.

Il numero di versione dello schema è salvato nel database stesso (PRAGMA user_version).
Per aggiungere campi o tabelle in futuro basta aggiungere una voce in fondo a MIGRATIONS:
all'apertura i database più vecchi vengono aggiornati da soli, senza perdere dati.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Callable

from . import image_refs, links, plain

DB_FILENAME = "campagna.db"


class DatabaseError(Exception):
    """Problema con il database; il messaggio è pensato per essere letto dall'utente."""


def _leader_text_into_notes(conn: sqlite3.Connection) -> None:
    """Versione 5: il leader di un'organizzazione si legge dai suoi membri, non si scrive più. Il testo che era stato
    scritto nel vecchio campo «Leader» non si perde: passa in fondo agli «Appunti liberi» dell'organizzazione."""
    rows = conn.execute(
        "SELECT t.element_id, t.content, n.content AS notes FROM element_text t "
        "JOIN element e ON e.id = t.element_id AND e.kind = 'organization' "
        "LEFT JOIN element_text n ON n.element_id = t.element_id AND n.field = 'notes' "
        "WHERE t.field = 'leader'").fetchall()
    for row in rows:
        notes = (row["notes"] or "") + "<p><b>Leader</b></p>" + row["content"]
        conn.execute("INSERT INTO element_text (element_id, field, content) VALUES (?, 'notes', ?) "
                     "ON CONFLICT (element_id, field) DO UPDATE SET content = excluded.content", (row["element_id"], notes))
        conn.execute("DELETE FROM element_text WHERE element_id = ? AND field = 'leader'", (row["element_id"],))
        # I collegamenti del testo spostato sono ora in «notes»: l'indice dei collegamenti dell'elemento si ricostruisce.
        conn.execute("DELETE FROM element_mention WHERE element_id = ?", (row["element_id"],))
        found = dict.fromkeys(target for (text,) in conn.execute(
            "SELECT content FROM element_text WHERE element_id = ?", (row["element_id"],))
            for target in links.extract_targets(text))
        conn.executemany("INSERT INTO element_mention (element_id, target_kind, target_id) VALUES (?, ?, ?)",
                         [(row["element_id"], *target) for target in found])


def _images_into_library(conn: sqlite3.Connection) -> None:
    """Versione 6: ogni immagine già usata (copertina della campagna, immagine di un elemento, immagini nei testi) entra nella
    libreria. L'immagine di un elemento diventa la prima delle sue immagini collegate."""
    texts = [row[0] for row in conn.execute("SELECT content FROM page")] + [row[0] for row in conn.execute("SELECT content FROM element_text")]
    paths = dict.fromkeys(
        [row[0] for row in conn.execute("SELECT image FROM campaign WHERE image IS NOT NULL")]
        + [row[0] for row in conn.execute("SELECT image FROM element WHERE image IS NOT NULL ORDER BY id")]
        + [path for content in texts for path in image_refs.extract(content)])
    conn.executemany("INSERT INTO image (path, label) VALUES (?, ?)", [(path, PurePosixPath(path).stem) for path in paths])
    conn.execute("INSERT INTO element_image (element_id, path, position) SELECT id, image, 0 FROM element WHERE image IS NOT NULL")
    try:
        conn.execute("ALTER TABLE element DROP COLUMN image")   # ormai si legge da element_image
    except sqlite3.OperationalError:
        pass                                                      # SQLite troppo vecchio: la colonna resta, ma nessuno la usa più


def _count_page_words(conn: sqlite3.Connection) -> None:
    """Versione 10: le parole di ogni pagina già scritta (da ora si contano al salvataggio)."""
    conn.executemany("UPDATE page SET words = ? WHERE id = ?",
                     [(plain.count_words(content), page_id) for page_id, content in conn.execute("SELECT id, content FROM page").fetchall()])


# MIGRATIONS[n] porta il database dalla versione n alla n+1. Non modificare le voci
# già rilasciate: per cambiare qualcosa si aggiunge una nuova voce. Una voce è un elenco di istruzioni SQL
# e, quando l'SQL non basta, di funzioni che ricevono la connessione.
MIGRATIONS: tuple[tuple[str | Callable[[sqlite3.Connection], None], ...], ...] = (
    (  # versione 1: i dati della campagna (una sola riga)
        """
        CREATE TABLE campaign (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            name        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            color       TEXT NOT NULL DEFAULT 'blue',
            image       TEXT,
            modified_at TEXT NOT NULL
        )
        """,
    ),
    (  # versione 2: pagine di Scrittura (capitoli e sottocapitoli) e i collegamenti che contengono
        """
        CREATE TABLE page (
            id          INTEGER PRIMARY KEY,
            parent_id   INTEGER REFERENCES page(id) ON DELETE CASCADE,
            position    INTEGER NOT NULL,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX page_parent ON page (parent_id, position)",
        # Indice dei collegamenti: si ricostruisce dal testo di ogni pagina a ogni salvataggio.
        """
        CREATE TABLE mention (
            page_id     INTEGER NOT NULL REFERENCES page(id) ON DELETE CASCADE,
            ordinal     INTEGER NOT NULL,
            target_kind TEXT NOT NULL,
            target_id   INTEGER NOT NULL,
            PRIMARY KEY (page_id, target_kind, target_id)
        )
        """,
        "CREATE INDEX mention_target ON mention (target_kind, target_id)",
    ),
    (  # versione 3: elementi (personaggi, luoghi, organizzazioni) e le loro categorie
        """
        CREATE TABLE category (
            id       INTEGER PRIMARY KEY,
            kind     TEXT NOT NULL,
            name     TEXT NOT NULL,
            color    TEXT NOT NULL,
            position INTEGER NOT NULL
        )
        """,
        "CREATE INDEX category_kind ON category (kind, position)",
        """
        CREATE TABLE element (
            id          INTEGER PRIMARY KEY,
            kind        TEXT NOT NULL,
            name        TEXT NOT NULL,
            category_id INTEGER NOT NULL REFERENCES category(id),
            image       TEXT,
            brief       TEXT NOT NULL DEFAULT '',
            role        TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX element_kind ON element (kind, category_id)",
        # Categorie di partenza (si cambiano da Impostazioni).
        """
        INSERT INTO category (kind, name, color, position) VALUES
            ('character', 'Protagonisti', 'blue', 0), ('character', 'Alleati', 'teal', 1),
            ('character', 'Antagonisti', 'pink', 2), ('character', 'Neutrali', 'gray', 3),
            ('place', 'Città', 'green', 0), ('place', 'Natura', 'green', 1),
            ('place', 'Dungeon', 'green', 2), ('place', 'Edifici', 'green', 3),
            ('organization', 'Ordini religiosi', 'amber', 0), ('organization', 'Gilde', 'amber', 1),
            ('organization', 'Fazioni ostili', 'amber', 2), ('organization', 'Governi', 'amber', 3)
        """,
    ),
    (  # versione 4: i testi delle schede, le relazioni fra elementi e i collegamenti scritti nelle schede
        # Un campo di testo della scheda (Aspetto, Storia, Appunti…): la riga esiste solo se il campo non è vuoto.
        """
        CREATE TABLE element_text (
            element_id INTEGER NOT NULL REFERENCES element(id) ON DELETE CASCADE,
            field      TEXT NOT NULL,
            content    TEXT NOT NULL,
            PRIMARY KEY (element_id, field)
        )
        """,
        # Una relazione fra due elementi, scritta una volta sola (a_id < b_id) e letta da entrambe le parti.
        # status, note e leader servono solo per personaggio–organizzazione (la scheda «Membri»).
        """
        CREATE TABLE relation (
            id     INTEGER PRIMARY KEY,
            a_id   INTEGER NOT NULL REFERENCES element(id) ON DELETE CASCADE,
            b_id   INTEGER NOT NULL REFERENCES element(id) ON DELETE CASCADE,
            label  TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            note   TEXT NOT NULL DEFAULT '',
            leader INTEGER NOT NULL DEFAULT 0,
            UNIQUE (a_id, b_id),
            CHECK (a_id < b_id)
        )
        """,
        "CREATE INDEX relation_b ON relation (b_id)",
        # Come `mention` per le pagine: indice dei collegamenti scritti nei testi di un elemento (si ricostruisce a ogni salvataggio).
        """
        CREATE TABLE element_mention (
            element_id  INTEGER NOT NULL REFERENCES element(id) ON DELETE CASCADE,
            target_kind TEXT NOT NULL,
            target_id   INTEGER NOT NULL,
            PRIMARY KEY (element_id, target_kind, target_id)
        )
        """,
        "CREATE INDEX element_mention_target ON element_mention (target_kind, target_id)",
    ),
    (  # versione 5: il leader di un'organizzazione è il membro segnato come leader (il vecchio campo di testo sparisce)
        _leader_text_into_notes,
    ),
    (  # versione 6: la libreria immagini (cartelle, immagini) e le immagini collegate a un elemento (la prima è il ritratto)
        """
        CREATE TABLE image_folder (
            id        INTEGER PRIMARY KEY,
            parent_id INTEGER REFERENCES image_folder(id),
            name      TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE image (
            id        INTEGER PRIMARY KEY,
            path      TEXT NOT NULL UNIQUE,
            label     TEXT NOT NULL,
            folder_id INTEGER REFERENCES image_folder(id)
        )
        """,
        "CREATE INDEX image_folder_id ON image (folder_id)",
        """
        CREATE TABLE element_image (
            element_id INTEGER NOT NULL REFERENCES element(id) ON DELETE CASCADE,
            path       TEXT NOT NULL REFERENCES image(path) ON DELETE CASCADE ON UPDATE CASCADE,
            position   INTEGER NOT NULL,
            PRIMARY KEY (element_id, path)
        )
        """,
        "CREATE INDEX element_image_path ON element_image (path)",
        _images_into_library,
    ),
    (  # versione 7: le mappe (in un albero, con l'immagine di sfondo scelta dalla libreria), i tipi di pin e i pin posati sulle mappe
        """
        CREATE TABLE map (
            id        INTEGER PRIMARY KEY,
            parent_id INTEGER REFERENCES map(id),
            name      TEXT NOT NULL,
            image     TEXT REFERENCES image(path) ON DELETE SET NULL ON UPDATE CASCADE
        )
        """,
        "CREATE INDEX map_parent ON map (parent_id)",
        "CREATE INDEX map_image ON map (image)",
        """
        CREATE TABLE pin_type (
            id       INTEGER PRIMARY KEY,
            name     TEXT NOT NULL,
            icon     TEXT NOT NULL,
            color    TEXT NOT NULL,
            position INTEGER NOT NULL
        )
        """,
        "INSERT INTO pin_type (name, icon, color, position) VALUES "
        "('Luogo', 'building', 'green', 0), ('Persona', 'user', 'blue', 1), ('Evento', 'star', 'pink', 2), ('Missione', 'flag', 'violet', 3)",
        """
        CREATE TABLE pin (
            id           INTEGER PRIMARY KEY,
            map_id       INTEGER NOT NULL REFERENCES map(id) ON DELETE CASCADE,
            type_id      INTEGER NOT NULL REFERENCES pin_type(id),
            x            REAL NOT NULL,
            y            REAL NOT NULL,
            name         TEXT NOT NULL DEFAULT '',
            brief        TEXT NOT NULL DEFAULT '',
            link_kind    TEXT,
            link_id      INTEGER,
            opens_map_id INTEGER REFERENCES map(id) ON DELETE SET NULL
        )
        """,
        "CREATE INDEX pin_map ON pin (map_id)",
        "CREATE INDEX pin_link ON pin (link_kind, link_id)",
        "CREATE INDEX pin_opens ON pin (opens_map_id)",
    ),
    (  # versione 8: i grafi (mappe mentali): nodi, collegabili a una pagina o a un elemento, e archi con etichetta
        """
        CREATE TABLE graph (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """,
        # Un nodo collegato prende il titolo da ciò a cui è collegato (title resta vuoto); la descrizione è sempre sua.
        """
        CREATE TABLE graph_node (
            id          INTEGER PRIMARY KEY,
            graph_id    INTEGER NOT NULL REFERENCES graph(id) ON DELETE CASCADE,
            x           REAL NOT NULL,
            y           REAL NOT NULL,
            title       TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            color       TEXT NOT NULL,
            link_kind   TEXT,
            link_id     INTEGER
        )
        """,
        "CREATE INDEX graph_node_graph ON graph_node (graph_id)",
        "CREATE INDEX graph_node_link ON graph_node (link_kind, link_id)",
        # Un arco collega due nodi dello stesso grafo (a_id < b_id): fra due nodi ce n'è al più uno.
        """
        CREATE TABLE graph_edge (
            id    INTEGER PRIMARY KEY,
            a_id  INTEGER NOT NULL REFERENCES graph_node(id) ON DELETE CASCADE,
            b_id  INTEGER NOT NULL REFERENCES graph_node(id) ON DELETE CASCADE,
            label TEXT NOT NULL DEFAULT '',
            UNIQUE (a_id, b_id),
            CHECK (a_id < b_id)
        )
        """,
        "CREATE INDEX graph_edge_b ON graph_edge (b_id)",
    ),
    (  # versione 9: la direzione degli archi (nessuna freccia, verso un nodo, verso l'altro, verso entrambi: vedi graphs.py)
        "ALTER TABLE graph_edge ADD COLUMN direction INTEGER NOT NULL DEFAULT 0",
    ),
    (  # versione 10: le parole di ogni pagina (contate al salvataggio, non a ogni apertura) e l'elenco «Da fare» della campagna
        "ALTER TABLE page ADD COLUMN words INTEGER NOT NULL DEFAULT 0",
        _count_page_words,
        """
        CREATE TABLE todo (
            id       INTEGER PRIMARY KEY,
            text     TEXT NOT NULL,
            done     INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL
        )
        """,
        "CREATE INDEX todo_order ON todo (done, position)",
    ),
    (  # versione 11: le schede tecniche (mostri e PNG di D&D 5e) con le loro capacità (tratti, azioni, reazioni, azioni leggendarie)
        """
        CREATE TABLE creature (
            id                   INTEGER PRIMARY KEY,
            name                 TEXT NOT NULL,
            size                 TEXT NOT NULL DEFAULT '',
            kind                 TEXT NOT NULL DEFAULT '',
            alignment            TEXT NOT NULL DEFAULT '',
            armor_class          TEXT NOT NULL DEFAULT '',
            hit_points           TEXT NOT NULL DEFAULT '',
            speed                TEXT NOT NULL DEFAULT '',
            ab_str               INTEGER NOT NULL DEFAULT 10,
            ab_dex               INTEGER NOT NULL DEFAULT 10,
            ab_con               INTEGER NOT NULL DEFAULT 10,
            ab_int               INTEGER NOT NULL DEFAULT 10,
            ab_wis               INTEGER NOT NULL DEFAULT 10,
            ab_cha               INTEGER NOT NULL DEFAULT 10,
            saves                TEXT NOT NULL DEFAULT '',
            skills               TEXT NOT NULL DEFAULT '',
            vulnerabilities      TEXT NOT NULL DEFAULT '',
            resistances          TEXT NOT NULL DEFAULT '',
            immunities           TEXT NOT NULL DEFAULT '',
            condition_immunities TEXT NOT NULL DEFAULT '',
            senses               TEXT NOT NULL DEFAULT '',
            passive              INTEGER,
            languages            TEXT NOT NULL DEFAULT '',
            challenge            TEXT NOT NULL DEFAULT '',
            environment          TEXT NOT NULL DEFAULT '',
            source               TEXT NOT NULL DEFAULT '',
            notes                TEXT NOT NULL DEFAULT ''
        )
        """,
        "CREATE INDEX creature_name ON creature (name COLLATE NOCASE)",
        """
        CREATE TABLE creature_feature (
            id          INTEGER PRIMARY KEY,
            creature_id INTEGER NOT NULL REFERENCES creature(id) ON DELETE CASCADE,
            section     TEXT NOT NULL,
            position    INTEGER NOT NULL,
            name        TEXT NOT NULL DEFAULT '',
            text        TEXT NOT NULL DEFAULT ''
        )
        """,
        "CREATE INDEX creature_feature_creature ON creature_feature (creature_id, position)",
    ),
    (  # versione 12: gli incontri (di combattimento o di interazione), i giocatori presenti e le schede tecniche che servono
        """
        CREATE TABLE encounter (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('combat', 'interaction'))
        )
        """,
        """
        CREATE TABLE encounter_party (
            id           INTEGER PRIMARY KEY,
            encounter_id INTEGER NOT NULL REFERENCES encounter(id) ON DELETE CASCADE,
            position     INTEGER NOT NULL,
            level        INTEGER NOT NULL,
            count        INTEGER NOT NULL
        )
        """,
        "CREATE INDEX encounter_party_encounter ON encounter_party (encounter_id, position)",
        """
        CREATE TABLE encounter_creature (
            id           INTEGER PRIMARY KEY,
            encounter_id INTEGER NOT NULL REFERENCES encounter(id) ON DELETE CASCADE,
            creature_id  INTEGER NOT NULL REFERENCES creature(id) ON DELETE CASCADE,
            position     INTEGER NOT NULL,
            quantity     INTEGER NOT NULL,
            UNIQUE (encounter_id, creature_id)
        )
        """,
        "CREATE INDEX encounter_creature_creature ON encounter_creature (creature_id)",
    ),
    (  # versione 13: i segnalibri, cioè pagine rapide (una pagina, un elemento, una mappa, un grafo o un incontro) nella barra sinistra
        # Il segnalibro punta per ID (`kind` come in data/links.py) e non ha nome suo: lo prende da ciò a cui punta. Sparisce insieme a lui.
        """
        CREATE TABLE bookmark (
            id        INTEGER PRIMARY KEY,
            kind      TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            position  INTEGER NOT NULL,
            UNIQUE (kind, target_id)
        )
        """,
    ),
    (  # versione 14: un arco può finire anche su un altro arco (cioè sulla sua etichetta), non solo su un nodo
        # Ogni estremo è un nodo o un arco (una sola delle due colonne è piena). Un arco finisce solo su archi già esistenti: niente giri.
        # Il grafo si scrive nell'arco (prima si ricavava dai nodi). Eliminando un nodo o un arco spariscono anche gli archi che ci finiscono.
        "DROP INDEX graph_edge_b",
        "ALTER TABLE graph_edge RENAME TO graph_edge_old",
        """
        CREATE TABLE graph_edge (
            id        INTEGER PRIMARY KEY,
            graph_id  INTEGER NOT NULL REFERENCES graph(id) ON DELETE CASCADE,
            a_node    INTEGER REFERENCES graph_node(id) ON DELETE CASCADE,
            a_edge    INTEGER REFERENCES graph_edge(id) ON DELETE CASCADE,
            b_node    INTEGER REFERENCES graph_node(id) ON DELETE CASCADE,
            b_edge    INTEGER REFERENCES graph_edge(id) ON DELETE CASCADE,
            label     TEXT NOT NULL DEFAULT '',
            direction INTEGER NOT NULL DEFAULT 0,
            CHECK ((a_node IS NULL) <> (a_edge IS NULL)),
            CHECK ((b_node IS NULL) <> (b_edge IS NULL))
        )
        """,
        """
        INSERT INTO graph_edge (id, graph_id, a_node, b_node, label, direction)
        SELECT e.id, n.graph_id, e.a_id, e.b_id, e.label, e.direction FROM graph_edge_old e JOIN graph_node n ON n.id = e.a_id
        """,
        "DROP TABLE graph_edge_old",
        "CREATE INDEX graph_edge_graph ON graph_edge (graph_id)",
        "CREATE INDEX graph_edge_a_node ON graph_edge (a_node)",
        "CREATE INDEX graph_edge_b_node ON graph_edge (b_node)",
        "CREATE INDEX graph_edge_a_edge ON graph_edge (a_edge)",
        "CREATE INDEX graph_edge_b_edge ON graph_edge (b_edge)",
    ),
    (  # versione 15: la sezione Culture (popoli, religioni, razze, lingue): le categorie di partenza (si cambiano da Impostazioni)
        """
        INSERT INTO category (kind, name, color, position) VALUES
            ('culture', 'Popoli', 'teal', 0), ('culture', 'Religioni', 'violet', 1),
            ('culture', 'Razze', 'amber', 2), ('culture', 'Lingue', 'blue', 3)
        """,
    ),
)
SCHEMA_VERSION = len(MIGRATIONS)


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Raggruppa più scritture: o vanno a buon fine tutte, o non ne resta nessuna."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    except sqlite3.Error as error:
        raise DatabaseError(f"Impossibile scrivere nel database: {error}") from error


def connect(path: Path) -> sqlite3.Connection:
    """Apre il database (lo crea se non esiste) e lo porta all'ultima versione dello schema."""
    try:
        # isolation_level=None: le transazioni le gestiamo noi, con transaction().
        conn = sqlite3.connect(path, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            _migrate(conn, path)
        except BaseException:
            conn.close()
            raise
    except sqlite3.Error as error:
        raise DatabaseError(f"Impossibile aprire il database «{path}». Dettaglio: {error}") from error
    return conn


def _migrate(conn: sqlite3.Connection, path: Path) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise DatabaseError(
            "Questa campagna è stata creata con una versione più recente di GM Journal. "
            "Aggiorna il programma per aprirla."
        )
    if current == 0 and path.stat().st_size > 0:
        raise DatabaseError(f"Il file «{path.name}» non è un database di GM Journal.")
    if current > 0 and current < SCHEMA_VERSION:
        _copy_before_migration(conn, path, current)
    for version in range(current + 1, SCHEMA_VERSION + 1):
        with transaction(conn):
            for step in MIGRATIONS[version - 1]:
                step(conn) if callable(step) else conn.execute(step)
            conn.execute(f"PRAGMA user_version = {version}")


def copy_database(conn: sqlite3.Connection, target: Path) -> None:
    """Copia coerente del database aperto in `conn` nel file `target` (anche se la campagna è in uso)."""
    try:
        copy = sqlite3.connect(target)
        try:
            conn.backup(copy)
        finally:
            copy.close()
    except sqlite3.Error as error:
        raise DatabaseError(f"Impossibile copiare il database: {error}") from error


def _copy_before_migration(conn: sqlite3.Connection, path: Path, version: int) -> None:
    """Copia di sicurezza (campagna.v1.bak, ...) prima di aggiornare uno schema esistente."""
    copy_database(conn, path.with_name(f"{path.stem}.v{version}.bak"))
