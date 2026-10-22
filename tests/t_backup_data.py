from harness import *
app()
import os, shutil, sqlite3, tempfile, time, zipfile
from datetime import date
from pathlib import Path
from PySide6.QtGui import QColor, QImage
import gmjournal.data.repository as repo_mod
from gmjournal.data import db
from gmjournal.data.backup import BACKUP_SUFFIX, backup_filename, restore_backup, save_backup
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import CampaignInput, ElementInput, NodeInput, PinInput
from gmjournal.data.repository import IMAGES_DIRNAME, Repository, list_campaigns
from gmjournal.graphs import Endpoint

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def fails(fn, *words):
    """True se `fn` dà un DatabaseError (il cui messaggio contiene tutte le `words`)."""
    try:
        fn()
    except DatabaseError as error:
        return all(word in str(error) for word in words)
    return False

def make_png(path, color="#446688"):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(40, 30, QImage.Format_RGB32); img.fill(QColor(color)); assert img.save(str(path))
    return path

def make_zip(path, entries):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return path

def fingerprint(folder):
    """Tutto ciò che di una campagna deve sopravvivere al backup: le tabelle (tranne nome e data della campagna) e i file."""
    conn = sqlite3.connect(folder / db.DB_FILENAME)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    rows = {t: conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in tables if t != "campaign"}
    head = conn.execute("SELECT description, color, image FROM campaign").fetchone()
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    files = {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted((folder / IMAGES_DIRNAME).rglob("*")) if p.is_file()}
    return rows, head, version, files

def folders(root):
    return sorted(p.name for p in root.iterdir()) if root.exists() else []

tmp = Path(tempfile.mkdtemp(prefix="gmj_backup_"))
root = tmp / "campagne"                      # le campagne di queste prove stanno qui, non nei Documenti
repo_mod.campaigns_root = lambda: root
out = tmp / "backup"; out.mkdir()

# ---------- una campagna ricca ----------
repo = new_repo("Città d'Ombra: l'Alba?")
png = repo.import_image(make_png(tmp / "src" / "Città è.png"))
png2 = repo.import_image(make_png(tmp / "src" / "mappa.png", "#884466"))
bmp = tmp / "src" / "vecchia.bmp"
img = QImage(60, 40, QImage.Format_RGB32); img.fill(QColor("#336655")); assert img.save(str(bmp))
bmp_path = repo.import_image(bmp)
sub = repo.folder / IMAGES_DIRNAME / "sotto"; sub.mkdir()
(sub / "annidata.jpg").write_bytes(os.urandom(5000))        # un file in una sottocartella di immagini/
old = repo.folder / IMAGES_DIRNAME / "antica.png"; make_png(old, "#aa5522")
os.utime(old, (0, 0))                                        # data del 1970: lo zip non la accetta in modo rigido
(repo.folder / "campagna.v3.bak").write_bytes(b"vecchia copia di sicurezza")
repo.update_campaign(CampaignInput("Città d'Ombra: l'Alba?", "Una campagna di prova", "violet", png))
cat = repo.categories("character")[0].id
mira = repo.create_element(ElementInput("character", "Mira", cat, png, "Una cartografa", "Guida"))
varen = repo.create_element(ElementInput("place", "Varenhold", repo.categories("place")[0].id, None, "Città sul fiume", ""))
repo.add_relation(mira, varen)
page = repo.create_page("Il viaggio")
repo.save_content(page, f'<p>vai a <a href="gmj://place/{varen}">Varenhold</a><img src="{png2}"></p>')
repo.save_text(mira, "notes", f'<p>vive a <a href="gmj://place/{varen}">Varenhold</a></p>')
the_map = repo.create_map("Regno", None, png2)
repo.create_pin(the_map, 0.3, 0.6, PinInput(repo.pin_types()[0].id, "Torre", "In rovina", None, None))
graph = repo.create_graph("Intrighi")
n1 = repo.create_node(graph, 10, 20, NodeInput("Re", "Il sovrano", "blue", None))
n2 = repo.create_node(graph, 80, 20, NodeInput("", "Il maestro", "pink", ("character", mira)))
repo.create_edge(Endpoint("node", n1), Endpoint("node", n2))
folder = repo.folder
original_name = repo.campaign().name

# ---------- il nome del file proposto ----------
suggested = backup_filename("Con:trol/Name?")
check("nome proposto: senza caratteri vietati e con data e estensione", suggested == f"ControlName {date.today():%Y-%m-%d}{BACKUP_SUFFIX}" and BACKUP_SUFFIX == ".gmj")
check("nome proposto: nomi riservati di Windows evitati", backup_filename("CON").startswith("Campagna CON "))
check("nome proposto: accenti e spazi restano", backup_filename("Città d'Ombra").startswith("Città d'Ombra "))

# ---------- salvare ----------
file = out / "prova.gmj"
calls = []
save_backup(folder, file, lambda done, total: calls.append((done, total)))
check("il file di backup esiste e non resta il file provvisorio", file.is_file() and not (out / "prova.gmj.parte").exists())
with zipfile.ZipFile(file) as z:
    names = sorted(z.namelist())
    kinds = {i.filename: i.compress_type for i in z.infolist()}
    check("lo zip è integro", z.testzip() is None)
check("contenuto: database e immagini, niente copie di sicurezza",
      names == sorted(["campagna.db", "immagini/Città è.png", "immagini/mappa.png", "immagini/vecchia.bmp", "immagini/sotto/annidata.jpg", "immagini/antica.png"]))
check("le immagini già compresse non si ricomprimono, il resto sì",
      kinds["immagini/mappa.png"] == zipfile.ZIP_STORED and kinds["immagini/sotto/annidata.jpg"] == zipfile.ZIP_STORED
      and kinds["immagini/vecchia.bmp"] == zipfile.ZIP_DEFLATED and kinds["campagna.db"] == zipfile.ZIP_DEFLATED)
check("avanzamento: una chiamata per file, crescente, finisce al totale",
      len(calls) == 6 and [c[0] for c in calls] == sorted(c[0] for c in calls) and calls[-1][0] == calls[-1][1] and len({c[1] for c in calls}) == 1)
check("un file con la data del 1970 non blocca il backup", "immagini/antica.png" in names)
with zipfile.ZipFile(file) as z:
    z.extract("campagna.db", tmp / "estratto")
check("il database nel backup è all'ultima versione e leggibile",
      sqlite3.connect(tmp / "estratto" / "campagna.db").execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION)
check("la campagna originale non è cambiata", fingerprint(folder)[3]["immagini/mappa.png"] == (folder / IMAGES_DIRNAME / "mappa.png").read_bytes())

# ---------- ripristinare: il nome esiste già ----------
before = fingerprint(folder)
t0 = time.time()
entry = restore_backup(file)
check("ripristino: campagna nuova «… (ripristinata)»", entry.campaign.name == original_name + " (ripristinata)" and entry.folder != folder and entry.folder.parent == root)
check("la cartella ripristinata ha un nome valido e unico", entry.folder.name.endswith("(ripristinata)") and "?" not in entry.folder.name and ":" not in entry.folder.name)
after = fingerprint(entry.folder)
check("dati identici (tutte le tabelle)", after[0] == before[0] and after[2] == before[2])
check("descrizione, colore e copertina identici", after[1] == before[1])
check("immagini identiche byte per byte, anche nelle sottocartelle", after[3] == before[3])
check("la campagna originale è intatta", fingerprint(folder) == before and repo.campaign().name == original_name)
check("nessuna copia di sicurezza nella campagna ripristinata", not list(entry.folder.glob("*.bak")) and not list(entry.folder.glob("*.parte")))
listed = {e.folder: e.campaign for e in list_campaigns()}
check("la campagna ripristinata compare nell'elenco con la data di oggi (le date sono al secondo)",
      entry.folder in listed and listed[entry.folder].modified_at.timestamp() >= t0 - 1 and listed[entry.folder].modified_at >= listed[folder].modified_at)
with Repository.open(entry.folder) as r2:
    check("si apre e legge i dati: elementi, mappa, grafo", [e.name for e in r2.elements("character")] == ["Mira"] and len(r2.maps()) == 1 and len(r2.graphs()) == 1)
second = restore_backup(file)
third = restore_backup(file)
check("ripristini ripetuti: (ripristinata 2), (ripristinata 3)", (second.campaign.name, third.campaign.name) == (original_name + " (ripristinata 2)", original_name + " (ripristinata 3)"))
check("…in cartelle diverse", len({entry.folder, second.folder, third.folder}) == 3)

# ---------- ripristinare: il nome non esiste ----------
away = tmp / "spostata"; shutil.move(folder, away)
for e in (entry, second, third):
    shutil.move(e.folder, tmp / f"via_{e.folder.name}")
check("senza campagne in giro, l'elenco è vuoto", list_campaigns() == [])
fresh = restore_backup(file)
check("nessun conflitto: il nome resta quello originale", fresh.campaign.name == original_name)
shutil.rmtree(fresh.folder); shutil.move(away, folder)

# ---------- maiuscole e minuscole ----------
repo.update_campaign(CampaignInput("CITTÀ D'OMBRA: L'ALBA?", "", "blue", None))
case = restore_backup(file)
check("il confronto dei nomi ignora maiuscole e minuscole", case.campaign.name == original_name + " (ripristinata)")
shutil.rmtree(case.folder)
repo.update_campaign(CampaignInput(original_name, "Una campagna di prova", "violet", png))

# ---------- sovrascrivere un backup ----------
file2 = out / "da_sovrascrivere.gmj"
file2.write_bytes(b"vecchio backup")
def broken_progress(done, total):
    raise KeyError("errore a metà")
try:
    save_backup(folder, file2, broken_progress)
except KeyError:
    pass
check("un backup interrotto non tocca quello vecchio né lascia file provvisori", file2.read_bytes() == b"vecchio backup" and not (out / "da_sovrascrivere.gmj.parte").exists())
save_backup(folder, file2)
check("un backup riuscito sostituisce il vecchio", zipfile.is_zipfile(file2))

# ---------- destinazioni sbagliate ----------
check("non si salva dentro la campagna stessa", fails(lambda: save_backup(folder, folder / "dentro.gmj"), "fuori dalla cartella") and not (folder / "dentro.gmj").exists())
check("…nemmeno dentro immagini/", fails(lambda: save_backup(folder, folder / IMAGES_DIRNAME / "dentro.gmj"), "fuori dalla cartella"))
check("cartella di destinazione inesistente: errore leggibile", fails(lambda: save_backup(folder, out / "non_esiste" / "x.gmj"), "Impossibile salvare il backup"))
check("una cartella che non è una campagna: errore leggibile", fails(lambda: save_backup(tmp / "src", out / "x.gmj"), "Nessuna campagna"))
check("…e non crea il file", not (out / "x.gmj").exists())

# ---------- backup mentre la campagna è aperta e in uso ----------
live = new_repo("Aperta")
live.create_page("Capitolo uno")
live.create_page("Capitolo due")
save_backup(live.folder, out / "aperta.gmj")           # `live` resta aperta, come quando si è nell'app
back = restore_backup(out / "aperta.gmj")
with Repository.open(back.folder) as r:
    check("il backup di una campagna aperta contiene tutto ciò che era salvato", [p.title for p in r.pages()] == ["Capitolo uno", "Capitolo due"])
live.create_page("Capitolo tre")
check("…e la campagna aperta continua a funzionare", len(live.pages()) == 3)
live.close()

# ---------- campagna senza immagini / senza cartella immagini ----------
empty = new_repo("Vuota")
empty.close()
save_backup(empty.folder, out / "vuota.gmj")
back_empty = restore_backup(out / "vuota.gmj")
check("campagna vuota: ripristinata con la cartella immagini", (back_empty.folder / IMAGES_DIRNAME).is_dir() and (back_empty.folder / db.DB_FILENAME).is_file())
shutil.rmtree(empty.folder / IMAGES_DIRNAME)
save_backup(empty.folder, out / "senza_cartella.gmj")
check("manca la cartella immagini: il backup riesce", zipfile.ZipFile(out / "senza_cartella.gmj").namelist() == ["campagna.db"])
check("…e si ripristina con la cartella immagini", (restore_backup(out / "senza_cartella.gmj").folder / IMAGES_DIRNAME).is_dir())

# ---------- avanzamento del ripristino ----------
steps = []
restore_backup(file, lambda done, total: steps.append((done, total)))
check("ripristino: avanzamento crescente, finisce al totale", len(steps) == 5 and [s[0] for s in steps] == sorted(s[0] for s in steps) and steps[-1][0] == steps[-1][1])

# ---------- un backup di una versione più vecchia ----------
old_root = tmp / "vecchio"; (old_root / IMAGES_DIRNAME).mkdir(parents=True)
conn = sqlite3.connect(old_root / db.DB_FILENAME, isolation_level=None)
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 8):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id, name, description, color, image, modified_at) VALUES (1, 'Antica', 'd', 'green', NULL, '2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO map (name) VALUES ('Vecchia mappa')")
conn.close()
old_file = out / "antica.gmj"
make_zip(old_file, {"campagna.db": (old_root / db.DB_FILENAME).read_bytes()})
before_names = folders(root)
upgraded = restore_backup(old_file)
check("un backup di una versione vecchia si ripristina all'ultima versione", fingerprint(upgraded.folder)[2] == db.SCHEMA_VERSION)
with Repository.open(upgraded.folder) as r:
    check("…senza perdere dati", [m.name for m in r.maps()] == ["Vecchia mappa"] and r.campaign().description == "d")
check("…e senza lasciare copie di sicurezza nella campagna", not list(upgraded.folder.glob("*.bak")))

# ---------- file che non sono backup validi (nessuna cartella resta in giro) ----------
good_db = zipfile.ZipFile(file).read("campagna.db")
newer = tmp / "piu_nuovo.db"; newer.write_bytes(good_db)
c = sqlite3.connect(newer); c.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}"); c.commit(); c.close()
garbage = tmp / "spazzatura.db"; garbage.write_bytes(b"questo non e' un database sqlite " * 40)
bad = {
    "un file di testo": (out / "testo.gmj", lambda p: p.write_text("ciao")),
    "un file vuoto": (out / "vuoto.gmj", lambda p: p.write_bytes(b"")),
    "uno zip senza database": (out / "senza_db.gmj", lambda p: make_zip(p, {"immagini/a.png": b"x"})),
    "un file di troppo": (out / "troppo.gmj", lambda p: make_zip(p, {"campagna.db": good_db, "segreto.txt": b"x"})),
    "un percorso che esce dalla cartella": (out / "esce.gmj", lambda p: make_zip(p, {"campagna.db": good_db, "immagini/../../evil.txt": b"x"})),
    "un percorso assoluto": (out / "assoluto.gmj", lambda p: make_zip(p, {"campagna.db": good_db, "/evil.txt": b"x"})),
    "un'unità di Windows": (out / "unita.gmj", lambda p: make_zip(p, {"campagna.db": good_db, "immagini/C:/evil.txt": b"x"})),
    "un database che non lo è": (out / "falso_db.gmj", lambda p: make_zip(p, {"campagna.db": garbage.read_bytes()})),
}
for what, (path, build) in bad.items():
    build(path)
    names_before = folders(root)
    check(f"{what}: rifiutato con un messaggio leggibile, nulla di nuovo in giro", fails(lambda: restore_backup(path)) and folders(root) == names_before)
check("nessun file «evil.txt» scritto fuori posto", not list(tmp.rglob("evil.txt")) and not list(Path("/").glob("evil.txt")))
make_zip(out / "nuovo.gmj", {"campagna.db": newer.read_bytes()})
check("un backup di una versione più recente è rifiutato (aggiorna il programma)", fails(lambda: restore_backup(out / "nuovo.gmj"), "versione più recente") and folders(root) == names_before)
trunc = out / "troncato.gmj"; trunc.write_bytes(file.read_bytes()[:-300])
check("un file troncato è rifiutato", fails(lambda: restore_backup(trunc)) and folders(root) == names_before)
check("un file che non esiste: errore leggibile", fails(lambda: restore_backup(out / "mancante.gmj"), "Impossibile ripristinare"))
raw = bytearray(file.read_bytes())
pos = raw.index(b"\x89PNG", raw.index(b"mappa.png"))       # i byte dell'immagine (non compressa) di mappa.png
raw[pos + 20] ^= 0xFF
corrupt = out / "corrotto.gmj"; corrupt.write_bytes(raw)
check("un'immagine danneggiata dentro il backup è rifiutata, senza lasciare una campagna a metà", fails(lambda: restore_backup(corrupt)) and folders(root) == names_before)

# ---------- una prova di dimensione ----------
big = new_repo("Grande")
for i in range(40):
    (big.folder / IMAGES_DIRNAME / f"img{i}.png").write_bytes(os.urandom(250_000))
big.close()
t0 = time.time(); save_backup(big.folder, out / "grande.gmj"); t_save = time.time() - t0
t0 = time.time(); big_back = restore_backup(out / "grande.gmj"); t_restore = time.time() - t0
check(f"40 immagini da 250 KB: salvataggio {t_save:.1f}s e ripristino {t_restore:.1f}s", t_save < 5 and t_restore < 5)
check("…e tornano tutte identiche", fingerprint(big_back.folder)[3] == fingerprint(big.folder)[3])

print(f"\n{sum(ok)}/{len(ok)}")
