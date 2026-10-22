from harness import *
app()
import sqlite3
from gmjournal.data import db
from gmjournal.data.models import ElementInput
from gmjournal.data.repository import unique_folder
from gmjournal.app import MainWindow
from gmjournal.ui.screens.elements import ElementTarget

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

# --- 1. campagna vecchia (v3) aperta dal programma -----------------------------------------------
folder = unique_folder("VecchiaV3"); folder.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(folder / db.DB_FILENAME, isolation_level=None)
for version in range(1, 4):
    for statement in db.MIGRATIONS[version - 1]:
        conn.execute(statement)
conn.execute("PRAGMA user_version = 3")
conn.execute("INSERT INTO campaign (id, name, description, color, image, modified_at) VALUES (1, 'Vecchia', '', 'blue', NULL, '2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO element (kind, name, category_id, brief, role, modified_at) VALUES ('character', 'Vecchio PG', 1, 'breve', 'ruolo', '2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO page (parent_id, position, title, content, modified_at) VALUES (NULL, 0, 'Cap 1', '<p>ciao</p>', '2026-01-01T00:00:00+00:00')")
conn.close()
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(folder, "personaggi", ElementTarget(1, True)); pump(200)
check("la campagna v3 si apre e si aggiorna all’ultima versione", w._repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION)
check("copia di sicurezza creata", (folder / "campagna.v3.bak").exists())
check("dati vecchi intatti", [e.name for e in w._repo.elements("character")] == ["Vecchio PG"] and w._repo.pages()[0].title == "Cap 1" if hasattr(w._repo, "pages") else True)
sheet = w._screens["personaggi"]._sheet
check("la scheda di un elemento vecchio si apre vuota", w._screens["personaggi"]._sheet_open and sheet.element_id == 1 and w._repo.texts(1) == {})

# --- 2. «Citato in» apre la scheda dell'elemento -------------------------------------------------------
repo = new_repo("CitatoIn")
cats = {k: repo.categories(k) for k in ("character", "place")}
a = repo.create_element(ElementInput("character", "Alfa", cats["character"][0].id, None, "", ""))
b = repo.create_element(ElementInput("place", "Beta", cats["place"][0].id, None, "", ""))
repo.save_text(a, "notes", f'<p>vive a <a href="gmj://place/{b}">Beta</a></p>')
w._go(repo.folder, "luoghi", b); pump(150)
screen = w._screens["luoghi"]
cited = repo.cited_by("place", b)
check("Beta è citato da Alfa", [(t.kind, t.id) for t in cited] == [("character", a)])
screen._preview.cited_chosen.emit(cited[0]); pump(150)
check("«Citato in» apre la scheda del personaggio", w._location[1] == "personaggi" and w._screens["personaggi"]._sheet_open and w._screens["personaggi"]._sheet.element_id == a)
w._topbar.back_clicked.emit(); pump(150)
check("indietro: torna ai luoghi", w._location[1] == "luoghi")

# --- 3. eliminare un luogo citato: il link nel testo dell'elemento diventa testo semplice ---------------
repo.delete_element(b)
check("link rimosso dal testo del personaggio", "gmj://" not in repo.texts(a)["notes"] and "Beta" in repo.texts(a)["notes"])

print(f"\n{sum(ok)}/{len(ok)}")
