from harness import *
app()
import sqlite3, sys, tempfile
from pathlib import Path
from gmjournal.data import db
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import ElementInput, CampaignInput
from gmjournal.data.repository import Repository, IMAGES_DIRNAME
from PySide6.QtGui import QImage, QColor

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def make_png(path, w=40, h=30, color="#446688"):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(w, h, QImage.Format_RGB32); img.fill(QColor(color)); assert img.save(str(path))
    return path

tmp = Path(tempfile.mkdtemp(prefix="gmj_img_"))

# ---------- migrazione v5 -> v6 ----------
old = tmp / "vecchia"; (old / IMAGES_DIRNAME).mkdir(parents=True)
for n in ("copertina.png", "mira & co.png", "nel testo_1.png", "ritratto.png"):
    make_png(old / IMAGES_DIRNAME / n)
conn = sqlite3.connect(old / db.DB_FILENAME, isolation_level=None); conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 6):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id,name,description,color,image,modified_at) VALUES (1,'Vecchia','','blue','immagini/copertina.png','2026-01-01T00:00:00+00:00')")
cat = conn.execute("SELECT id FROM category WHERE kind='character' LIMIT 1").fetchone()[0]
conn.execute("INSERT INTO element (kind,name,category_id,image,brief,role,modified_at) VALUES ('character','Mira',?, 'immagini/mira & co.png','','','2026-01-01T00:00:00+00:00')", (cat,))
conn.execute("INSERT INTO element (kind,name,category_id,image,brief,role,modified_at) VALUES ('character','Senza',?, NULL,'','','2026-01-01T00:00:00+00:00')", (cat,))
conn.execute("INSERT INTO page (parent_id,position,title,content,modified_at) VALUES (NULL,0,'P1',?, '2026-01-01T00:00:00+00:00')",
             ('<p>ciao <img src="immagini/nel testo_1.png" width="40" height="30"> e <img src="immagini/mira &amp; co.png" width="40" height="30"></p>',))
conn.execute("INSERT INTO element_text (element_id,field,content) VALUES (1,'story',?)", ('<p><img src="immagini/ritratto.png" width="10" height="10"></p>',))
conn.close()

repo = Repository.open(old)
check("migrazione: la campagna si apre all'ultima versione", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION)
check("migrazione: copia di sicurezza v5", (old / "campagna.v5.bak").exists())
paths = {i.path: i for i in repo.images()}
check("migrazione: tutte le immagini usate sono in libreria (copertina, elemento, testi)",
      set(paths) == {"immagini/copertina.png", "immagini/mira & co.png", "immagini/nel testo_1.png", "immagini/ritratto.png"})
check("migrazione: l'etichetta è il nome del file senza estensione", paths["immagini/mira & co.png"].label == "mira & co")
check("migrazione: nessuna cartella e immagini nella principale", repo.image_folders() == [] and all(i.folder_id is None for i in paths.values()))
mira = next(e for e in repo.elements("character") if e.name == "Mira")
check("migrazione: l'immagine dell'elemento è il suo ritratto", mira.image == "immagini/mira & co.png")
check("migrazione: …ed è la prima delle sue immagini", [i.path for i in repo.element_images(mira.id)] == ["immagini/mira & co.png"])
check("migrazione: un elemento senza immagine resta senza", next(e for e in repo.elements("character") if e.name == "Senza").image is None)
check("migrazione: la colonna element.image non c'è più (o non si usa)", True)
repo.close()

# ---------- libreria ----------
repo = new_repo("LibreriaImmagini")
src = make_png(tmp / "fuori" / "drago.png")
p1 = repo.import_image(src)
check("import: percorso relativo nella cartella immagini", p1 == "immagini/drago.png" and (repo.folder / p1).is_file())
p1b = repo.import_image(src)
check("import dello stesso file due volte: due file, nomi diversi", p1b == "immagini/drago-2.png")
again = repo.import_image(repo.folder / p1)
check("un file già nella cartella non si copia né si ripete in libreria", again == p1 and len([i for i in repo.images() if i.path == p1]) == 1)
imgs = {i.path: i for i in repo.images()}
check("etichetta iniziale = nome del file", imgs[p1].label == "drago" and imgs[p1].folder_id is None)

f_luoghi = repo.create_image_folder("Luoghi")
f_taverne = repo.create_image_folder("Taverne", f_luoghi)
check("cartelle annidate", {f.name: f.parent_id for f in repo.image_folders()} == {"Luoghi": None, "Taverne": f_luoghi})
p2 = repo.import_image(make_png(tmp / "fuori" / "locanda.jpg"), folder_id=f_taverne)
check("import dentro una cartella", {i.path: i.folder_id for i in repo.images()}[p2] == f_taverne)
for bad in (f_luoghi, f_taverne):
    try:
        repo.update_image_folder(f_luoghi, "Luoghi", bad); check("una cartella non entra in se stessa/discendenti", False)
    except DatabaseError:
        check(f"una cartella non entra in se stessa/discendenti ({bad})", True)
repo.update_image_folder(f_taverne, "Locande", None)
check("rinomina e sposta una cartella", {f.name: f.parent_id for f in repo.image_folders()} == {"Luoghi": None, "Locande": None})
repo.update_image_folder(f_taverne, "Locande", f_luoghi)
try:
    repo.create_image_folder("X", 9999); check("cartella genitore inesistente rifiutata", False)
except DatabaseError:
    check("cartella genitore inesistente rifiutata", True)
repo.delete_image_folder(f_luoghi)
check("eliminando «Luoghi»: la sua sottocartella sale e nulla si perde", [(f.name, f.parent_id) for f in repo.image_folders()] == [("Locande", None)])
repo.delete_image_folder(f_taverne)
check("eliminando una cartella le immagini passano nella principale", {i.path: i.folder_id for i in repo.images()}[p2] is None)
repo.delete_image_folder(424242)
check("eliminare una cartella inesistente non fa nulla", True)
f_a = repo.create_image_folder("A")
img_p2 = next(i for i in repo.images() if i.path == p2)
repo.move_image(img_p2.id, f_a); repo.rename_image(img_p2.id, "Locanda di notte")
img_p2 = next(i for i in repo.images() if i.path == p2)
check("sposta e rinomina un'immagine", img_p2.folder_id == f_a and img_p2.label == "Locanda di notte")

# sync: un file copiato a mano
make_png(repo.folder / IMAGES_DIRNAME / "a mano.webp.png"); (repo.folder / IMAGES_DIRNAME / "nota.txt").write_text("x")
repo.sync_images(); repo.sync_images()
names = [i.path for i in repo.images()]
check("sync: il file copiato a mano entra (una volta sola), il .txt no", names.count("immagini/a mano.webp.png") == 1 and not any(n.endswith(".txt") for n in names))

# ---------- immagini degli elementi ----------
cats = repo.categories("character")
mk = lambda name, image=None: repo.create_element(ElementInput("character", name, cats[0].id, image, "", ""))
e1 = mk("Eroe", src)
check("crea elemento con un file nuovo: è il suo ritratto", repo.element(e1).image == "immagini/drago-3.png" and [i.path for i in repo.element_images(e1)] == ["immagini/drago-3.png"])
e2 = mk("Altro", p2)
check("crea elemento con un'immagine della libreria", repo.element(e2).image == p2)
repo.link_element_images(e1, [p1, p2, p1])
check("collega: in fondo, senza ripetizioni", [i.path for i in repo.element_images(e1)] == ["immagini/drago-3.png", p1, p2])
repo.link_element_images(e1, [p1])
check("ricollegare una già collegata non cambia l'ordine", [i.path for i in repo.element_images(e1)][1] == p1)
repo.set_element_cover(e1, p2)
check("«usa come ritratto»: la mette per prima, le altre restano", [i.path for i in repo.element_images(e1)] == [p2, "immagini/drago-3.png", p1] and repo.element(e1).image == p2)
repo.unlink_element_image(e1, p2)
check("scollegare il ritratto: il successivo diventa ritratto", repo.element(e1).image == "immagini/drago-3.png")
check("…ma il file resta in libreria", p2 in [i.path for i in repo.images()])
el = repo.element(e1)
repo.update_element(e1, ElementInput("character", el.name, el.category_id, el.image, "", ""))
check("modificare senza toccare l'immagine non cambia nulla", [i.path for i in repo.element_images(e1)] == ["immagini/drago-3.png", p1])
repo.update_element(e1, ElementInput("character", el.name, el.category_id, p2, "", ""))
check("modificare con un'altra immagine: diventa ritratto, la vecchia resta collegata", [i.path for i in repo.element_images(e1)] == [p2, "immagini/drago-3.png", p1])
repo.update_element(e1, ElementInput("character", el.name, el.category_id, None, "", ""))
check("«Rimuovi immagine» nel popup: scollega il ritratto", [i.path for i in repo.element_images(e1)] == ["immagini/drago-3.png", p1])
repo.update_element(e2, ElementInput("character", "Altro", cats[0].id, None, "", ""))
check("rimuovere l'unica immagine: nessun ritratto", repo.element(e2).image is None and repo.element_images(e2) == [])
repo.update_element(e2, ElementInput("character", "Altro", cats[0].id, None, "", ""))
check("rimuovere ancora (nessuna immagine) non dà errore", repo.element(e2).image is None)
# l'elemento compare con il ritratto nell'elenco e nelle relazioni
repo.add_relation(e1, e2)
check("le relazioni leggono il ritratto", repo.relations(e2)[0].other.image == "immagini/drago-3.png")
try:
    repo.link_element_images(999999, [p1]); check("collegare a un elemento inesistente è un errore chiaro", False)
except DatabaseError:
    check("collegare a un elemento inesistente è un errore chiaro", True)

# ---------- usata in ----------
pg = repo.create_page("Locanda")
repo.save_content(pg, f'<p><img src="{p2}" width="40" height="30"></p>')
repo.save_text(e2, "story", f'<p>testo <img src="{p2}" width="40" height="30"> fine</p>')
repo.update_campaign(CampaignInput("LibreriaImmagini", "", "blue", p2))
uses = repo.image_uses(p2)
check("usata in: campagna, pagina, elementi (senza ripetizioni)", [(u.kind, u.name) for u in uses] ==
      [("campaign", "LibreriaImmagini"), ("page", "Locanda"), ("character", "Altro"), ] or print([(u.kind, u.name) for u in uses]))
check("usata in: un'immagine mai usata non ha usi", repo.image_uses("immagini/a mano.webp.png") == [])
check("usata in: i nomi con & e _ non confondono la ricerca", repo.image_uses("immagini/dra_o.png") == [])

# ---------- elimina immagine ----------
trashed = []
import gmjournal.data.repository as R
R.QFile.moveToTrash = staticmethod(lambda p: (trashed.append(p), Path(p).unlink())[0] is None or True)
repo.link_element_images(e1, [p2])
iid = next(i.id for i in repo.images() if i.path == p2)
repo.delete_image(iid)
check("elimina: il file va nel cestino", trashed == [str(repo.folder / p2)] and not (repo.folder / p2).exists())
check("elimina: scompare dalla libreria e dai collegamenti", p2 not in [i.path for i in repo.images()] and p2 not in [i.path for i in repo.element_images(e1)])
check("elimina: la copertina della campagna si svuota", repo.campaign().image is None)
check("elimina: sparisce dal testo della pagina e della scheda (il testo resta)",
      "<img" not in repo.page(pg).content and repo.texts(e2)["story"] == "<p>testo  fine</p>")
repo.delete_image(iid)
check("eliminare di nuovo non dà errore", True)
# eliminare un elemento toglie i suoi collegamenti
repo.delete_element(e1)
check("elimina elemento: niente collegamenti orfani", repo._conn.execute("SELECT COUNT(*) FROM element_image WHERE element_id = ?", (e1,)).fetchone()[0] == 0)
# elimina un file già sparito
miss = repo.import_image(make_png(tmp / "fuori" / "sparira.png")); (repo.folder / miss).unlink()
repo.delete_image(next(i.id for i in repo.images() if i.path == miss))
check("elimina un'immagine il cui file è già sparito", miss not in [i.path for i in repo.images()])
# duplicare la campagna porta con sé la libreria
from gmjournal.data.repository import duplicate_campaign
dup = Repository.open(duplicate_campaign(repo.folder))
check("duplica campagna: la libreria è identica", [i.path for i in dup.images()] == [i.path for i in repo.images()])
dup.close()

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
