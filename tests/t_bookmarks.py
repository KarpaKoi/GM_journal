"""Segnalibri: pagine rapide nella barra sinistra (dati, migrazione v12 -> v13, pulsante in alto, elenco, pulizia quando qualcosa sparisce)."""
from harness import *
app()
import sqlite3
from PySide6.QtTest import QTest
from gmjournal.data import db, links
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import ElementInput, EncounterInput, PartyGroup
from gmjournal.data.repository import Repository
from gmjournal.encounters import COMBAT, INTERACTION
from gmjournal.app import MainWindow
from gmjournal.ui.map_target import MapTarget
from gmjournal.ui.widgets.bookmark_list import _Row

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def fails(fn):
    try:
        fn()
    except DatabaseError:
        return True
    return False

# ---------- migrazione v12 -> v13 ----------
tmp = Path(tempfile.mkdtemp(prefix="gmj_bookmarks_"))
old = tmp / "vecchia"; old.mkdir()
conn = sqlite3.connect(old / db.DB_FILENAME, isolation_level=None); conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 13):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id,name,description,color,image,modified_at) VALUES (1,'Vecchia','','blue',NULL,'2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO page (id, parent_id, position, title, content, modified_at) VALUES (1, NULL, 0, 'Capitolo', '', '2026-01-01T00:00:00+00:00')")
conn.close()
repo = Repository.open(old)
check("migrazione: la campagna si apre all'ultima versione", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION >= 13)
check("migrazione: copia di sicurezza v12", (old / "campagna.v12.bak").exists())
check("migrazione: i dati di prima restano e non ci sono segnalibri", [p.title for p in repo.pages()] == ["Capitolo"] and repo.bookmarks() == [])
repo.close()

# ---------- dati ----------
repo = new_repo("Segnalibri")
cats = {k: repo.categories(k) for k in ("character", "place", "organization")}
mk = lambda kind, name: repo.create_element(ElementInput(kind, name, cats[kind][0].id, None, "", ""))
mira, varen, ordine = mk("character", "Mira"), mk("place", "Varenhold"), mk("organization", "Ordine")
cap = repo.create_page("La Locanda")
mappa = repo.create_map("Mondo")
grafo = repo.create_graph("Corte")
incontro = repo.create_encounter(EncounterInput("Imboscata", COMBAT, (PartyGroup(3, 4),), ()))
pace = repo.create_encounter(EncounterInput("Trattativa", INTERACTION, (), ()))

check("all'inizio non ce ne sono", repo.bookmarks() == [] and not repo.is_bookmarked(links.PAGE, cap))
for kind, target_id in ((links.PAGE, cap), (links.CHARACTER, mira), (links.PLACE, varen), (links.ORGANIZATION, ordine),
                        (links.MAP, mappa), (links.GRAPH, grafo), (links.ENCOUNTER, incontro), (links.ENCOUNTER, pace)):
    repo.add_bookmark(kind, target_id)
marks = repo.bookmarks()
check("ogni tipo si può segnare, nell'ordine di aggiunta", [(m.kind, m.id) for m in marks] == [
    (links.PAGE, cap), (links.CHARACTER, mira), (links.PLACE, varen), (links.ORGANIZATION, ordine), (links.MAP, mappa),
    (links.GRAPH, grafo), (links.ENCOUNTER, incontro), (links.ENCOUNTER, pace)])
check("il nome è quello di ciò a cui punta, con il tipo accanto", [(m.name, m.detail) for m in marks] == [
    ("La Locanda", "Pagina"), ("Mira", cats["character"][0].name), ("Varenhold", cats["place"][0].name), ("Ordine", cats["organization"][0].name),
    ("Mondo", "Mappa"), ("Corte", "Grafo"), ("Imboscata", "Combattimento"), ("Trattativa", "Interazione")])
check("is_bookmarked", repo.is_bookmarked(links.PAGE, cap) and not repo.is_bookmarked(links.PAGE, 999))
repo.add_bookmark(links.PAGE, cap)
check("segnare due volte la stessa cosa non la duplica", len(repo.bookmarks()) == 8)
check("non si segna ciò che non esiste", fails(lambda: repo.add_bookmark(links.PAGE, 999)) and fails(lambda: repo.add_bookmark(links.CHARACTER, varen))
      and fails(lambda: repo.add_bookmark("strano", 1)) and len(repo.bookmarks()) == 8)
repo.rename_page(cap, "La Taverna")
check("rinominare cambia il nome del segnalibro (un solo dato, un solo posto)", repo.bookmarks()[0].name == "La Taverna")
repo.remove_bookmark(links.MAP, mappa)
check("togliere un segnalibro non tocca la mappa", not repo.is_bookmarked(links.MAP, mappa) and [m.id for m in repo.maps()] == [mappa])
repo.add_bookmark(links.MAP, mappa)
check("uno rimesso va in fondo", repo.bookmarks()[-1].kind == links.MAP)

repo.delete_page(cap)
check("eliminare una pagina toglie il suo segnalibro", not repo.is_bookmarked(links.PAGE, cap))
repo.delete_element(mira)
check("eliminare un elemento toglie il suo segnalibro", not repo.is_bookmarked(links.CHARACTER, mira))
repo.delete_map(mappa)
repo.delete_graph(grafo)
repo.delete_encounter(incontro)
check("lo stesso per mappe, grafi e incontri", [(m.kind, m.id) for m in repo.bookmarks()] == [(links.PLACE, varen), (links.ORGANIZATION, ordine), (links.ENCOUNTER, pace)])
check("…e nel database non ne resta nessuno orfano", repo._conn.execute("SELECT COUNT(*) FROM bookmark").fetchone()[0] == 3)
new_page = repo.create_page("Un'altra")
check("un nuovo elemento non eredita il segnalibro di uno eliminato", not repo.is_bookmarked(links.PAGE, new_page))

# ---------- interfaccia ----------
repo = new_repo("SegnalibriUI")
cats = {k: repo.categories(k) for k in ("character", "place", "organization")}
mira = repo.create_element(ElementInput("character", "Mira Vesperi", cats["character"][0].id, None, "", ""))
cap = repo.create_page("La Locanda")
sub = repo.create_page("Lo straniero con un titolo molto lungo che non ci sta", cap)
mappa = repo.create_map("Mondo")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
star = w._topbar._bookmark_button
rows = lambda: w._sidebar._bookmarks.findChildren(_Row)
names = lambda: [r._target.name for r in rows()]

check("nell'elenco campagne il pulsante non c'è", not star.isVisibleTo(w._topbar))
w._go(repo.folder, "scrittura"); pump(200)
check("nella schermata iniziale di Scrittura non c'è nulla da segnare", not star.isVisibleTo(w._topbar))
check("senza segnalibri l'elenco non si vede", not w._sidebar._bookmarks.isVisibleTo(w._sidebar))

w._go(repo.folder, "scrittura", cap); pump(200)
check("con una pagina aperta il pulsante c'è, vuoto", star.isVisibleTo(w._topbar) and star.toolTip() == "Aggiungi ai segnalibri")
star.click(); pump(100)
check("un clic mette il segnalibro", repo.is_bookmarked(links.PAGE, cap) and names() == ["La Locanda"])
check("…il pulsante diventa «Togli»", star.toolTip() == "Togli dai segnalibri")
check("…l'elenco si vede nella barra sinistra e la riga è quella del posto attuale", w._sidebar._bookmarks.isVisibleTo(w._sidebar) and rows()[0]._current)

w._go(repo.folder, "scrittura", sub); pump(200)
check("in un'altra pagina il pulsante è di nuovo vuoto e la riga non è più evidenziata", star.toolTip() == "Aggiungi ai segnalibri" and not rows()[0]._current)
star.click(); pump(100)
check("un secondo segnalibro", names() == ["La Locanda", "Lo straniero con un titolo molto lungo che non ci sta"])

w._go(repo.folder, "personaggi", mira); pump(200)
w._screens["personaggi"]._open_sheet(mira); pump(200)
star.click(); pump(100)
check("anche una scheda di personaggio", repo.is_bookmarked(links.CHARACTER, mira) and len(rows()) == 3)
w._go(repo.folder, "mappe", MapTarget(mappa)); pump(200)
star.click(); pump(100)
check("e una mappa", repo.is_bookmarked(links.MAP, mappa) and len(rows()) == 4)
w._go(repo.folder, "immagini"); pump(200)
check("nelle Immagini il pulsante non c'è ma i segnalibri restano", not star.isVisibleTo(w._topbar) and len(rows()) == 4)

# clic su una riga
rows()[0].opened.emit(); pump(200)
check("un clic su un segnalibro porta alla pagina", w._location[1] == "scrittura" and w._screens["scrittura"]._page_id == cap)
check("…e entra nella cronologia", w._history.can_back)
rows()[2].opened.emit(); pump(200)
check("un segnalibro di un personaggio apre la sua scheda", w._location[1] == "personaggi" and w._screens["personaggi"]._sheet_open)
rows()[3].opened.emit(); pump(200)
check("un segnalibro di una mappa apre la mappa", w._location[1] == "mappe" and w._screens["mappe"]._map_id == mappa)
# clic vero sulla riga (rilascio) e sulla «x»
w._go(repo.folder, "immagini"); pump(200)
row = rows()[1]
QTest.mouseMove(row, QPoint(30, 12)); pump(30)
QTest.mouseClick(row, Qt.LeftButton, Qt.NoModifier, QPoint(30, 12)); pump(200)
check("clic con il mouse su una riga: apre la pagina", w._screens["scrittura"]._page_id == sub)
row = rows()[1]
x_point = row._x_rect().center()
QTest.mouseMove(row, x_point); pump(30)
QTest.mouseClick(row, Qt.LeftButton, Qt.NoModifier, x_point); pump(200)
check("la «x» toglie il segnalibro senza aprirlo", not repo.is_bookmarked(links.PAGE, sub) and len(rows()) == 3 and w._location[1] == "scrittura")
check("…e senza eliminare la pagina", sub in [p.id for p in repo.pages()])

# elemento eliminato da fuori: il segnalibro sparisce al prossimo aggiornamento
repo.delete_element(mira); w._go(repo.folder, "scrittura", cap); pump(200)
check("un elemento eliminato non lascia il suo segnalibro", len(rows()) == 2 and "Mira Vesperi" not in names())
# tolto con il pulsante
w._go(repo.folder, "scrittura", cap); pump(100)
star.click(); pump(100)
check("il pulsante pieno toglie il segnalibro", not repo.is_bookmarked(links.PAGE, cap) and star.toolTip() == "Aggiungi ai segnalibri")
# tanti segnalibri: l'elenco scorre invece di crescere
for i in range(10):
    pid = repo.create_page(f"Pagina {i}"); repo.add_bookmark(links.PAGE, pid)
w._go(repo.folder, "scrittura", cap); pump(200)
check("con molti segnalibri l'elenco si ferma a 4 righe e scorre", w._sidebar._bookmarks._scroll.height() == 4 * 33 and len(rows()) >= 10)
# barra ridotta: niente segnalibri
w._sidebar.set_collapsed(True); pump(50)
check("a barra ridotta i segnalibri si nascondono", not w._sidebar._bookmarks.isVisibleTo(w._sidebar))
w._sidebar.set_collapsed(False); pump(50)
check("…e tornano", w._sidebar._bookmarks.isVisibleTo(w._sidebar))
# i segnalibri sono della campagna: un'altra campagna non li vede
other = new_repo("Altra")
w._go(other.folder, "scrittura"); pump(200)
check("un'altra campagna non ha i segnalibri della prima", rows() == [] or not w._sidebar._bookmarks.isVisibleTo(w._sidebar))
print(f"\n{sum(ok)}/{len(ok)}")
