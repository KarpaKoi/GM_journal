from harness import *
app()
import sqlite3, sys, tempfile
from pathlib import Path
from gmjournal.data import db
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import ElementInput, PinInput
from gmjournal.data.repository import Repository, IMAGES_DIRNAME, NAME_MAX
from PySide6.QtGui import QImage, QColor

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def fails(fn):
    try:
        fn()
    except DatabaseError:
        return True
    return False

def make_png(path, color="#446688"):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(40, 30, QImage.Format_RGB32); img.fill(QColor(color)); assert img.save(str(path))
    return path

tmp = Path(tempfile.mkdtemp(prefix="gmj_maps_"))

# ---------- migrazione v6 -> v7 ----------
old = tmp / "vecchia"; (old / IMAGES_DIRNAME).mkdir(parents=True)
conn = sqlite3.connect(old / db.DB_FILENAME, isolation_level=None); conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 7):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id,name,description,color,image,modified_at) VALUES (1,'Vecchia','','blue',NULL,'2026-01-01T00:00:00+00:00')")
conn.close()
repo = Repository.open(old)
check("migrazione: la campagna si apre all'ultima versione", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION)
check("migrazione: copia di sicurezza v6", (old / "campagna.v6.bak").exists())
check("migrazione: nessuna mappa, quattro tipi di pin", repo.maps() == [] and [t.name for t in repo.pin_types()] == ["Luogo", "Persona", "Evento", "Missione"])
check("migrazione: icone e colori dei tipi", [(t.icon, t.color) for t in repo.pin_types()] ==
      [("building", "green"), ("user", "blue"), ("star", "pink"), ("flag", "violet")])
repo.close()

# ---------- albero delle mappe ----------
repo = new_repo("ProvaMappe")
png = repo.import_image(make_png(tmp / "fuori" / "regno.png"))
png2 = repo.import_image(make_png(tmp / "fuori" / "citta.png", "#884466"))
regno = repo.create_map("Regno di Aldoria", None, png)
valle = repo.create_map("Valle del Corvo", regno)
citta = repo.create_map("Varenhold", valle, png2)
quartieri = repo.create_map("Quartieri", citta)
tree = {m.name: (m.parent_id, m.image) for m in repo.maps()}
check("mappe annidate a più livelli", tree == {"Regno di Aldoria": (None, png), "Valle del Corvo": (regno, None), "Varenhold": (valle, png2), "Quartieri": (citta, None)})
check("in ordine alfabetico", [m.name for m in repo.maps()] == ["Quartieri", "Regno di Aldoria", "Valle del Corvo", "Varenhold"])
long_map = repo.create_map("x" * 200)
check("il nome si accorcia", repo._conn.execute("SELECT name FROM map WHERE id = ?", (long_map,)).fetchone()[0] == "x" * NAME_MAX)
check("genitore inesistente rifiutato", fails(lambda: repo.create_map("Sbagliata", 9999)))
for bad in (valle, citta, quartieri):
    check(f"una mappa non entra in una sua discendente ({bad})", fails(lambda bad=bad: repo.update_map(regno, "Regno di Aldoria", bad, png)))
check("…se non entra in se stessa", fails(lambda: repo.update_map(regno, "Regno", regno, png)))
check("modificare una mappa inesistente è un errore chiaro", fails(lambda: repo.update_map(9999, "x", None, None)))
repo.update_map(quartieri, "Quartieri alti", valle, png)
check("rinomina, sposta, cambia sfondo", {m.id: (m.name, m.parent_id, m.image) for m in repo.maps()}[quartieri] == ("Quartieri alti", valle, png))
repo.update_map(quartieri, "Quartieri alti", citta, None)
check("sfondo tolto", {m.id: m.image for m in repo.maps()}[quartieri] is None)
check("un'immagine che non è in libreria è rifiutata", fails(lambda: repo.update_map(quartieri, "Quartieri alti", citta, "immagini/non-esiste.png")))

# ---------- tipi di pin ----------
t_luoghi, t_persone, t_eventi, t_missioni = [t.id for t in repo.pin_types()]
tesoro = repo.create_pin_type("Tesoro", "gem", "amber")
check("nuovo tipo in fondo agli altri", [t.name for t in repo.pin_types()][-2:] == ["Missione", "Tesoro"] and repo.pin_types()[-1].id == tesoro)
long_type = repo.create_pin_type("y" * 200, "star", "blue")
check("il nome del tipo si accorcia", len(next(t for t in repo.pin_types() if t.id == long_type).name) == NAME_MAX)

# ---------- pin liberi ----------
free = repo.create_pin(valle, 0.25, 0.5, PinInput(t_luoghi, "Torre abbandonata", "Una torre in rovina.", None, None))
p = repo.pins(valle)[0]
check("pin libero: nome, testo, posizione", (p.name, p.brief, p.x, p.y, p.link, p.type_id, p.map_id) == ("Torre abbandonata", "Una torre in rovina.", 0.25, 0.5, None, t_luoghi, valle))
far = repo.create_pin(valle, 7, -3, PinInput(t_eventi, "Fuori", "", None, None))
check("la posizione resta dentro l'immagine", (lambda q: (q.x, q.y))(next(q for q in repo.pins(valle) if q.id == far)) == (1.0, 0.0))
check("i pin sono nell'ordine in cui sono stati posati", [q.id for q in repo.pins(valle)] == [free, far])
repo.move_pin(free, 0.4, 0.6)
check("sposta un pin", (repo.pins(valle)[0].x, repo.pins(valle)[0].y) == (0.4, 0.6))
check("tipo inesistente rifiutato", fails(lambda: repo.create_pin(valle, 0, 0, PinInput(9999, "x", "", None, None))))
check("mappa inesistente rifiutata", fails(lambda: repo.create_pin(9999, 0, 0, PinInput(t_luoghi, "x", "", None, None))))
check("un pin non può aprire la mappa su cui sta", fails(lambda: repo.create_pin(valle, 0, 0, PinInput(t_luoghi, "x", "", None, valle))))
check("…né una mappa che non esiste", fails(lambda: repo.create_pin(valle, 0, 0, PinInput(t_luoghi, "x", "", None, 9999))))
check("le scritture fallite non lasciano nulla", len(repo.pins(valle)) == 2)
repo.update_pin(free, PinInput(t_eventi, "Torre crollata", "Crollata.", None, citta))
q = next(q for q in repo.pins(valle) if q.id == free)
check("modifica un pin (tipo, testo, mappa che apre); la posizione non cambia", (q.type_id, q.name, q.brief, q.opens_map_id, q.x, q.y) == (t_eventi, "Torre crollata", "Crollata.", citta, 0.4, 0.6))
check("modificare un pin inesistente è un errore chiaro", fails(lambda: repo.update_pin(9999, PinInput(t_luoghi, "x", "", None, None))))
check("conteggio dei pin per mappa", repo.pin_counts() == {valle: 2})

# ---------- pin collegati ----------
place_cat = repo.categories("place")[0].id
char_cat = repo.categories("character")[0].id
varenhold = repo.create_element(ElementInput("place", "Varenhold", place_cat, None, "Città fortificata sul fiume.", ""))
mira = repo.create_element(ElementInput("character", "Mira", char_cat, None, "Una cartografa.", "Cartografa"))
capitolo = repo.create_page("Il viaggio")
sotto = repo.create_page("La locanda", capitolo)
link_pin = repo.create_pin(regno, 0.5, 0.5, PinInput(t_luoghi, "ignorato", "ignorato", ("place", varenhold), citta))
q = repo.pins(regno)[0]
check("pin collegato: nome e testo vengono dall'elemento", (q.name, q.brief, q.link.kind, q.link.id, q.link.detail) == ("Varenhold", "Città fortificata sul fiume.", "place", varenhold, repo.categories("place")[0].name))
check("…e nel database non ne conserva di suoi", repo._conn.execute("SELECT name, brief FROM pin WHERE id = ?", (link_pin,)).fetchone()[:] == ("", ""))
repo.update_element(varenhold, ElementInput("place", "Varenhold la Grande", place_cat, None, "Capitale.", ""))
q = repo.pins(regno)[0]
check("rinominare l'elemento cambia anche il pin", (q.name, q.brief) == ("Varenhold la Grande", "Capitale."))
page_pin = repo.create_pin(regno, 0.1, 0.1, PinInput(t_eventi, "", "", ("page", capitolo), None))
q = next(q for q in repo.pins(regno) if q.id == page_pin)
check("pin collegato a una pagina: il titolo, nessun testo", (q.name, q.brief, q.link.kind) == ("Il viaggio", "", "page"))
check("collegamento a qualcosa che non esiste rifiutato", fails(lambda: repo.create_pin(regno, 0, 0, PinInput(t_luoghi, "", "", ("place", 9999), None))))
check("…o con il tipo sbagliato (un personaggio come luogo)", fails(lambda: repo.create_pin(regno, 0, 0, PinInput(t_luoghi, "", "", ("place", mira), None))))
check("…o con un tipo di collegamento inventato", fails(lambda: repo.create_pin(regno, 0, 0, PinInput(t_luoghi, "", "", ("map", citta), None))))
repo.update_pin(link_pin, PinInput(t_persone, "", "", ("character", mira), None))
q = next(q for q in repo.pins(regno) if q.id == link_pin)
check("cambiare il collegamento", (q.name, q.link.kind, q.type_id, q.opens_map_id) == ("Mira", "character", t_persone, None))
repo.update_pin(link_pin, PinInput(t_persone, "Libero ora", "Testo", None, None))
q = next(q for q in repo.pins(regno) if q.id == link_pin)
check("da collegato a libero", (q.name, q.brief, q.link) == ("Libero ora", "Testo", None))
repo.update_pin(link_pin, PinInput(t_luoghi, "", "", ("place", varenhold), citta))
check("pins_linked_to: i pin di un elemento, su tutte le mappe", [(q.map_id, q.id) for q in repo.pins_linked_to("place", varenhold)] == [(regno, link_pin)])
other = repo.create_pin(valle, 0.3, 0.3, PinInput(t_luoghi, "", "", ("place", varenhold), None))
check("…in ordine di mappa", [q.id for q in repo.pins_linked_to("place", varenhold)] == sorted([link_pin, other], key=lambda i: (repo._conn.execute("SELECT map_id FROM pin WHERE id = ?", (i,)).fetchone()[0], i)))
check("pins_linked_to: nessun pin", repo.pins_linked_to("character", 9999) == [])

# ---------- cosa succede quando sparisce qualcosa ----------
repo.delete_element(varenhold)
qs = {q.id: q for q in repo.pins(regno) + repo.pins(valle)}
check("eliminando l'elemento il pin resta, libero, con nome e testo di quel momento",
      (qs[link_pin].link, qs[link_pin].name, qs[link_pin].brief, qs[other].name) == (None, "Varenhold la Grande", "Capitale.", "Varenhold la Grande"))
check("…e conserva il tipo e la mappa che apre", (qs[link_pin].type_id, qs[link_pin].opens_map_id) == (t_luoghi, citta))
repo.delete_page(capitolo)
q = next(q for q in repo.pins(regno) if q.id == page_pin)
check("eliminando la pagina il pin resta libero con il suo titolo", (q.link, q.name) == (None, "Il viaggio"))
sub_pin = repo.create_pin(regno, 0.9, 0.9, PinInput(t_eventi, "", "", ("page", repo.create_page("Altra")), None))
repo.delete_page(next(n.id for n in repo.pages() if n.title == "Altra"))
check("anche un'altra pagina eliminata", next(q for q in repo.pins(regno) if q.id == sub_pin).name == "Altra")

# ---------- sfondi e immagini ----------
uses = repo.image_uses(png2)
check("usata in: lo sfondo di una mappa", [(u.kind, u.id, u.name, u.detail) for u in uses] == [("map", citta, "Varenhold", "Sfondo della mappa")])
check("usata in: più mappe, in ordine alfabetico", [u.name for u in repo.image_uses(png)] == ["Regno di Aldoria"])
repo.update_map(valle, "Valle del Corvo", regno, png)
check("…con più mappe", [u.name for u in repo.image_uses(png)] == ["Regno di Aldoria", "Valle del Corvo"])
import gmjournal.data.repository as R
R.QFile.moveToTrash = staticmethod(lambda p: (Path(p).unlink(), True)[1])
repo.delete_image(next(i.id for i in repo.images() if i.path == png2))
check("eliminando l'immagine la mappa resta, senza sfondo", {m.id: m.image for m in repo.maps()}[citta] is None and repo.image_uses(png2) == [])

# ---------- eliminare una mappa ----------
repo.delete_map(valle)
tree = {m.name: m.parent_id for m in repo.maps()}
check("eliminando una mappa le sottomappe salgono di un livello", tree["Varenhold"] == regno and "Valle del Corvo" not in tree)
check("…e i suoi pin spariscono", repo._conn.execute("SELECT COUNT(*) FROM pin WHERE map_id = ?", (valle,)).fetchone()[0] == 0)
repo.delete_map(citta)
check("i pin di altre mappe che la aprivano restano, senza mappa", all(q.opens_map_id is None for q in repo.pins(regno)) and len(repo.pins(regno)) >= 3)
check("la sottomappa della sottomappa sale", {m.name: m.parent_id for m in repo.maps()}["Quartieri alti"] == regno)
repo.delete_map(9999)
check("eliminare una mappa inesistente non fa nulla", True)

# ---------- una campagna duplicata porta con sé mappe e pin ----------
from gmjournal.data.repository import duplicate_campaign
dup = Repository.open(duplicate_campaign(repo.folder))
check("duplica campagna: mappe, tipi e pin", [m.name for m in dup.maps()] == [m.name for m in repo.maps()]
      and len(dup.pin_types()) == len(repo.pin_types()) and len(dup.pins(regno)) == len(repo.pins(regno)))
dup.close()

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
