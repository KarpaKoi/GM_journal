"""Versioni del database: uno più nuovo del programma si rifiuta con un messaggio chiaro; uno vecchio si aggiorna dopo una copia di sicurezza."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from conftest import make_zip

from gmjournal.data import db
from gmjournal.data.backup import restore_backup
from gmjournal.data.db import MIGRATIONS, SCHEMA_VERSION, DatabaseError
from gmjournal.data.repository import Repository


def old_database(path: Path, version: int) -> None:
    """Un database come lo avrebbe lasciato la versione `version` del programma: solo le migrazioni fino a lì, con una campagna e, dalla 2, una pagina."""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for number in range(1, version + 1):
        conn.execute("BEGIN")
        for step in MIGRATIONS[number - 1]:
            step(conn) if callable(step) else conn.execute(step)
        conn.execute(f"PRAGMA user_version = {number}")
        conn.execute("COMMIT")
        if number == 1:
            conn.execute("INSERT INTO campaign (id, name, description, color, modified_at) VALUES (1, 'Vecchia', 'di una volta', 'teal', ?)",
                         (datetime.now(timezone.utc).isoformat(),))
    if version >= 2:
        conn.execute("INSERT INTO page (parent_id, position, title, content, modified_at) VALUES (NULL, 0, 'Capitolo', '<p>testo</p>', ?)",
                     (datetime.now(timezone.utc).isoformat(),))
    conn.close()


def version_of(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


@pytest.mark.parametrize("newer", [SCHEMA_VERSION + 1, SCHEMA_VERSION + 50])
def test_un_database_piu_nuovo_del_programma_e_rifiutato(tmp_path, newer):
    folder = tmp_path / "Futura"
    folder.mkdir()
    old_database(folder / db.DB_FILENAME, SCHEMA_VERSION)
    conn = sqlite3.connect(folder / db.DB_FILENAME)
    conn.execute(f"PRAGMA user_version = {newer}")
    conn.close()
    with pytest.raises(DatabaseError) as error:
        Repository.open(folder)
    assert "versione più recente" in str(error.value) and "Aggiorna il programma" in str(error.value)
    assert version_of(folder / db.DB_FILENAME) == newer                  # e non si tocca
    assert [path.name for path in folder.iterdir()] == [db.DB_FILENAME]  # niente copie di sicurezza di un database che non si apre


def test_un_backup_piu_nuovo_del_programma_e_rifiutato_con_lo_stesso_messaggio(root, tmp_path):
    old_database(tmp_path / "nuovo.db", SCHEMA_VERSION)
    conn = sqlite3.connect(tmp_path / "nuovo.db")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()
    source = make_zip(tmp_path / "nuovo.gmj", {db.DB_FILENAME: (tmp_path / "nuovo.db").read_bytes()})
    with pytest.raises(DatabaseError, match="versione più recente"):
        restore_backup(source)
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("old", [1, 2, 5, 10, SCHEMA_VERSION - 1])
def test_un_database_vecchio_si_aggiorna_dopo_una_copia_di_sicurezza(tmp_path, old):
    assert 1 <= old < SCHEMA_VERSION
    folder = tmp_path / "Vecchia"
    folder.mkdir()
    old_database(folder / db.DB_FILENAME, old)
    with Repository.open(folder) as repo:
        assert repo.campaign().name == "Vecchia"
        if old >= 2:
            assert [page.title for page in repo.pages()] == ["Capitolo"]            # i dati sopravvivono
    assert version_of(folder / db.DB_FILENAME) == SCHEMA_VERSION
    backup = folder / f"campagna.v{old}.bak"
    assert backup.is_file() and version_of(backup) == old                         # la copia è alla versione di prima
    conn = sqlite3.connect(backup)
    assert conn.execute("SELECT name FROM campaign").fetchone()[0] == "Vecchia"      # …e completa
    conn.close()


def test_un_database_aggiornato_non_rifa_la_copia(tmp_path):
    folder = tmp_path / "Vecchia"
    folder.mkdir()
    old_database(folder / db.DB_FILENAME, 3)
    Repository.open(folder).close()
    (folder / "campagna.v3.bak").unlink()
    Repository.open(folder).close()                                                 # già all'ultima versione: nessuna nuova copia
    assert not list(folder.glob("*.bak"))


def test_un_backup_vecchio_si_ripristina_aggiornato(root, tmp_path):
    old_database(tmp_path / "vecchio.db", 4)
    source = make_zip(tmp_path / "vecchio.gmj", {db.DB_FILENAME: (tmp_path / "vecchio.db").read_bytes()})
    restored = restore_backup(source)
    assert version_of(restored.folder / db.DB_FILENAME) == SCHEMA_VERSION
    assert not list(restored.folder.glob("*.bak"))      # la copia di sicurezza è rimasta nella cartella temporanea del ripristino
