"""Backup e ripristino: il giro completo conserva i dati, e un backup ostile non scrive fuori dalla campagna né lascia cartelle a metà."""

import collections
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest
from conftest import PNG, make_zip

from gmjournal.data import backup, db
from gmjournal.data.backup import restore_backup, save_backup
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import CampaignInput
from gmjournal.data.repository import Repository, list_campaigns


def listing(folder: Path) -> list[str]:
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def database_bytes(tmp_path: Path, edit=None) -> bytes:
    """Il file `campagna.db` di una campagna valida, dopo `edit(connessione)` se c'è."""
    folder = tmp_path / "db_fatto"
    shutil.rmtree(folder, ignore_errors=True)
    Repository.create(folder, CampaignInput("Da backup", "", "blue", None)).close()
    if edit:
        conn = sqlite3.connect(folder / db.DB_FILENAME)
        edit(conn)
        conn.commit()
        conn.close()
    return (folder / db.DB_FILENAME).read_bytes()


# --- Il giro completo -------------------------------------------------------------------------------------------
def snapshot(folder: Path) -> dict:
    """Ciò che di una campagna deve sopravvivere: testi, immagini (con il loro contenuto) e collegamenti."""
    with Repository.open(folder) as repo:
        pages = {page.title: repo.page(page.id).content for page in repo.pages()}
        element = repo.element(1)
        return {
            "campagna": (repo.campaign().description, repo.campaign().color, repo.campaign().image),
            "pagine": pages,
            "testi": repo.texts(element.id),
            "elemento": (element.name, element.image),
            "mappe": [(node.name, node.image) for node in repo.maps()],
            "immagini": sorted(image.path for image in repo.images()),
            "file": {path.relative_to(folder).as_posix(): path.read_bytes() for path in (folder / "immagini").rglob("*") if path.is_file()},
        }


def test_il_giro_completo_conserva_testi_e_immagini(campaign, tmp_path):
    folder, *_ = campaign
    file = tmp_path / "prova.gmj"
    save_backup(folder, file)
    before = snapshot(folder)
    restored = restore_backup(file)
    assert restored.folder != folder
    assert snapshot(restored.folder) == before
    assert "immagini/a.png" in before["pagine"]["Il viaggio"] and "immagini/b.png" in before["testi"]["notes"]
    assert before["file"]["immagini/a.png"] == PNG                       # il contenuto dei file torna identico


def test_i_nomi_uguali_diventano_ripristinata_e_ripristinata_2(campaign, tmp_path, root):
    folder, *_ = campaign
    file = tmp_path / "prova.gmj"
    save_backup(folder, file)
    first, second, third = (restore_backup(file) for _ in range(3))
    assert [first.campaign.name, second.campaign.name, third.campaign.name] == [
        "Aurora (ripristinata)", "Aurora (ripristinata 2)", "Aurora (ripristinata 3)"]
    assert sorted(entry.campaign.name for entry in list_campaigns()) == [
        "Aurora", "Aurora (ripristinata 2)", "Aurora (ripristinata 3)", "Aurora (ripristinata)"]
    assert len({first.folder, second.folder, third.folder, folder}) == 4          # cartelle diverse: non si sovrascrive nulla


def test_un_backup_di_una_campagna_con_nome_libero_mantiene_il_nome(campaign, tmp_path, root):
    folder, *_ = campaign
    file = tmp_path / "prova.gmj"
    save_backup(folder, file)
    shutil.rmtree(folder)
    assert restore_backup(file).campaign.name == "Aurora"


# --- Backup ostili ---------------------------------------------------------------------------------------------
def hostile_cases(tmp_path: Path) -> dict[str, dict[str, bytes]]:
    good = database_bytes(tmp_path)
    no_row = database_bytes(tmp_path, lambda conn: conn.execute("DELETE FROM campaign"))
    return {
        "percorso con ..": {db.DB_FILENAME: good, "../evil.txt": b"x"},
        "percorso con .. dentro immagini": {db.DB_FILENAME: good, "immagini/../../evil.png": PNG},
        "percorso assoluto": {db.DB_FILENAME: good, "/evil.png": PNG},
        "percorso assoluto dentro immagini": {db.DB_FILENAME: good, "immagini//evil.png": PNG, "/immagini/evil2.png": PNG},
        "unità di Windows": {db.DB_FILENAME: good, "C:/evil.png": PNG},
        "unità dentro immagini": {db.DB_FILENAME: good, "immagini/C:/evil.png": PNG},
        "backslash": {db.DB_FILENAME: good, "immagini\\..\\evil.png": PNG},
        "backslash senza immagini": {db.DB_FILENAME: good, "..\\evil.txt": b"x"},
        "rete (UNC)": {db.DB_FILENAME: good, "\\\\srv\\sh\\evil.png": PNG},
        "file estraneo": {db.DB_FILENAME: good, "evil.txt": b"x"},
        "file estraneo in una cartella": {db.DB_FILENAME: good, "documenti/evil.txt": b"x"},
        "un secondo database": {db.DB_FILENAME: good, "altro/campagna.db": good},
        "senza campagna.db": {"immagini/a.png": PNG},
        "database non valido": {db.DB_FILENAME: b"questo non e' un database" * 50},
        "database vuoto": {db.DB_FILENAME: b""},
        "database senza la riga della campagna": {db.DB_FILENAME: no_row},
        "database senza tabelle ma con la versione giusta": {db.DB_FILENAME: _versioned_empty(tmp_path)},
    }


def _versioned_empty(tmp_path: Path) -> bytes:
    path = tmp_path / "vuoto.db"
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE altro (x)")
    conn.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION}")
    conn.commit()
    conn.close()
    return path.read_bytes()


HOSTILE = ["percorso con ..", "percorso con .. dentro immagini", "percorso assoluto", "percorso assoluto dentro immagini", "unità di Windows",
           "unità dentro immagini", "backslash", "backslash senza immagini", "rete (UNC)", "file estraneo", "file estraneo in una cartella",
           "un secondo database", "senza campagna.db", "database non valido", "database vuoto", "database senza la riga della campagna",
           "database senza tabelle ma con la versione giusta"]


@pytest.mark.parametrize("name", HOSTILE)
def test_un_backup_ostile_e_rifiutato_senza_lasciare_tracce(root, tmp_path, name):
    source = make_zip(tmp_path / "ostile.gmj", hostile_cases(tmp_path)[name])
    before = listing(tmp_path)
    with pytest.raises(DatabaseError) as error:
        restore_backup(source)
    assert str(error.value)                                  # un messaggio leggibile
    assert listing(tmp_path) == before                       # niente fuori dalla cartella delle campagne (evil.* compresi)…
    assert list(root.iterdir()) == []                        # …e nessuna campagna a metà dentro


def test_uno_zip_corrotto_e_rifiutato(root, tmp_path, campaign):
    folder, *_ = campaign
    good = tmp_path / "buono.gmj"
    save_backup(folder, good)
    data = good.read_bytes()
    flipped = bytearray(data)
    flipped[len(flipped) // 3] ^= 0xFF                          # un byte cambiato nei dati
    cases = {"non è uno zip": b"PK\x03\x04 ma tutto il resto no", "troncato": data[: len(data) // 2], "un byte cambiato": bytes(flipped)}
    before = listing(tmp_path)
    for label, content in cases.items():
        broken = tmp_path / "rotto.gmj"
        broken.write_bytes(content)
        with pytest.raises(DatabaseError):
            restore_backup(broken)
        broken.unlink()
        assert listing(tmp_path) == before, label
    assert [entry.campaign.name for entry in list_campaigns()] == ["Aurora"]       # solo la campagna di partenza


def test_un_file_che_non_esiste_da_un_errore_leggibile(root, tmp_path):
    with pytest.raises(DatabaseError):
        restore_backup(tmp_path / "manca.gmj")


# --- Limiti di dimensione e spazio ----------------------------------------------------------------------------
def test_un_backup_troppo_grande_una_volta_decompresso_e_rifiutato(root, tmp_path, monkeypatch):
    source = make_zip(tmp_path / "grande.gmj", {db.DB_FILENAME: database_bytes(tmp_path), "immagini/a.png": PNG * 100})
    monkeypatch.setattr(backup, "MAX_UNPACKED", 1000)
    with pytest.raises(DatabaseError, match="troppo grande"):
        restore_backup(source)
    assert list(root.iterdir()) == []


def test_il_limite_predefinito_e_otto_gigabyte():
    assert backup.MAX_UNPACKED == 8 * 1024**3


def test_un_rapporto_di_compressione_anomalo_e_rifiutato(root, tmp_path, monkeypatch):
    with zipfile.ZipFile(tmp_path / "bomba.gmj", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(db.DB_FILENAME, database_bytes(tmp_path))
        archive.writestr("immagini/zeri.png", bytes(3_000_000))           # 3 MB di zeri: si comprimono quasi a nulla
    monkeypatch.setattr(backup, "_RATIO_FROM", 1_000_000)                  # il controllo parte da 1 MB (di norma da 256 MB)
    with pytest.raises(DatabaseError, match="anomalo"):
        restore_backup(tmp_path / "bomba.gmj")
    assert list(root.iterdir()) == []


def test_sotto_la_soglia_il_rapporto_non_blocca_un_backup_vero(root, tmp_path):
    with zipfile.ZipFile(tmp_path / "zeri.gmj", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(db.DB_FILENAME, database_bytes(tmp_path))
        archive.writestr("immagini/zeri.png", bytes(3_000_000))
    assert restore_backup(tmp_path / "zeri.gmj").campaign.name == "Da backup"


def test_senza_spazio_sul_disco_il_ripristino_e_rifiutato_prima_di_estrarre(root, tmp_path, monkeypatch):
    source = make_zip(tmp_path / "prova.gmj", {db.DB_FILENAME: database_bytes(tmp_path), "immagini/a.png": PNG})
    Usage = collections.namedtuple("Usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: Usage(10**9, 10**9 - 1024, 1024))
    with pytest.raises(DatabaseError, match="spazio"):
        restore_backup(source)
    assert list(root.iterdir()) == []


def test_lo_spazio_si_controlla_anche_se_la_cartella_delle_campagne_non_esiste_ancora(tmp_path, monkeypatch):
    import gmjournal.data.repository as repository
    missing = tmp_path / "non" / "ancora" / "Campagne"
    monkeypatch.setattr(repository, "campaigns_root", lambda: missing)
    source = make_zip(tmp_path / "prova.gmj", {db.DB_FILENAME: database_bytes(tmp_path), "immagini/a.png": PNG})
    assert restore_backup(source).folder.parent == missing


# --- Immagini ostili dentro un backup ------------------------------------------------------------------------------
def poison(conn: sqlite3.Connection) -> None:
    """Scrive nel database percorsi che escono dalla campagna, dappertutto dove ce ne possono stare."""
    element = conn.execute("SELECT id FROM element").fetchone()[0]
    conn.execute("UPDATE campaign SET image = '../../cover.png'")
    conn.execute("UPDATE page SET content = ?", ('<p>ok<img src="immagini/a.png" width="9" height="9">'
                                                 '<img src="../../x.png" width="9" height="9"><img src="C:\\y.png"><IMG alt="a" src=\'\\\\srv\\sh\\z.png\'></p>',))
    conn.execute("UPDATE element_text SET content = ?", ('<p>note<img src="/etc/passwd" width="9" height="9"><img src="immagini/b.png"></p>',))
    conn.executemany("INSERT INTO image (path, label) VALUES (?, ?)", [("../evil.png", "e1"), ("C:\\evil.png", "e2")])
    conn.execute("INSERT INTO element_image (element_id, path, position) VALUES (?, '../evil.png', 5)", (element,))
    conn.execute("UPDATE map SET image = '/abs/map.png'")


def test_le_immagini_fuori_dalla_campagna_di_un_backup_sono_neutralizzate(campaign, tmp_path):
    folder, page, element, (a, b) = campaign
    conn = sqlite3.connect(folder / db.DB_FILENAME)
    poison(conn)
    conn.commit()
    conn.close()
    file = tmp_path / "avvelenato.gmj"
    save_backup(folder, file)

    restored = restore_backup(file)
    with Repository.open(restored.folder) as repo:
        content = repo.page(page).content
        notes = repo.texts(element)["notes"]
        assert repo.campaign().image is None                                    # la copertina fuori posto è sparita
        assert [image.path for image in repo.images()] == [a, b]                # la libreria ha solo le immagini vere
        assert [image.path for image in repo.element_images(element)] == [a]
        assert [node.image for node in repo.maps()] == [None]
    assert content == f'<p>ok<img src="{a}" width="9" height="9"></p>'          # restano solo i tag giusti
    assert notes == f'<p>note<img src="{b}"></p>'
    for text in (content, notes):
        assert "x.png" not in text and "passwd" not in text and "srv" not in text and "C:" not in text
    assert not list(tmp_path.rglob("evil.png")) and not list(tmp_path.rglob("cover.png"))


def test_un_backup_pulito_non_perde_nessuna_immagine_valida(campaign, tmp_path):
    folder, page, element, (a, b) = campaign
    file = tmp_path / "pulito.gmj"
    save_backup(folder, file)
    with Repository.open(restore_backup(file).folder) as repo:
        assert repo.campaign().image == a
        assert [image.path for image in repo.images()] == [a, b]
        assert [node.image for node in repo.maps()] == [b]
