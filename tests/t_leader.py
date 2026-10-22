from harness import *
app()
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
from gmjournal.data import db
from gmjournal.data.models import ElementInput
from gmjournal.data.repository import Repository, unique_folder
from gmjournal.app import MainWindow
from gmjournal.ui.screens.elements import ElementTarget
from gmjournal.ui.sheet.profile import LeadersField
from gmjournal.ui.sheet.members import _MemberRow
from gmjournal.ui.sheet.parts import NameLink

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

# --- migrazione v4 -> v5 ---------------------------------------------------------------------------
folder = unique_folder("LeaderV4"); folder.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(folder / db.DB_FILENAME, isolation_level=None)
for version in range(1, 5):
    for statement in db.MIGRATIONS[version - 1]:
        conn.execute(statement)
conn.execute("PRAGMA user_version = 4")
NOW = "2026-01-01T00:00:00+00:00"
conn.execute("INSERT INTO campaign (id, name, description, color, image, modified_at) VALUES (1, 'V4', '', 'blue', NULL, ?)", (NOW,))
def el(kind, name, cat):
    return conn.execute("INSERT INTO element (kind, name, category_id, brief, role, modified_at) VALUES (?, ?, ?, '', '', ?)", (kind, name, cat, NOW)).lastrowid
org_cat = conn.execute("SELECT id FROM category WHERE kind='organization' LIMIT 1").fetchone()[0]
chr_cat = conn.execute("SELECT id FROM category WHERE kind='character' LIMIT 1").fetchone()[0]
ismene, anselm = el("character", "Lady Ismene", chr_cat), el("character", "Anselm", chr_cat)
org_a, org_b, org_c = el("organization", "Ordine", org_cat), el("organization", "Gilda", org_cat), el("organization", "Senza testo", org_cat)
def txt(e, f, c): conn.execute("INSERT INTO element_text (element_id, field, content) VALUES (?, ?, ?)", (e, f, c))
def men(e, k, i): conn.execute("INSERT INTO element_mention (element_id, target_kind, target_id) VALUES (?, ?, ?)", (e, k, i))
txt(org_a, "leader", f'<p>Lady <a href="gmj://character/{ismene}">Ismene</a></p>'); men(org_a, "character", ismene)
txt(org_a, "notes", f'<p>Fondato da <a href="gmj://character/{anselm}">Anselm</a>.</p>'); men(org_a, "character", anselm)
txt(org_a, "symbol", "<p>Una fiamma</p>")
txt(org_b, "leader", "<p>Il Console</p>")           # senza appunti
txt(org_c, "symbol", "<p>Una spada</p>")            # senza leader
txt(anselm, "leader", "<p>campo di un personaggio: non va toccato</p>")
conn.close()
repo = Repository.open(folder)
a = repo.texts(org_a)
check("copia di sicurezza v4", (folder / "campagna.v4.bak").exists())
check("ultima versione dello schema", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION)
check("il campo «leader» non c'è più", "leader" not in a and "leader" not in repo.texts(org_b))
check("appunti: vecchio testo + titoletto + testo del leader", a["notes"].startswith("<p>Fondato da") and "<p><b>Leader</b></p><p>Lady <a" in a["notes"])
check("senza appunti: nascono con il testo del leader", repo.texts(org_b)["notes"] == "<p><b>Leader</b></p><p>Il Console</p>")
check("gli altri campi restano", a["symbol"] == "<p>Una fiamma</p>" and repo.texts(org_c) == {"symbol": "<p>Una spada</p>"})
check("un campo «leader» di un personaggio non si tocca", "leader" in repo.texts(anselm))
check("indice dei collegamenti ricostruito (Ismene e Anselm citati dall'Ordine)",
      sorted(t.id for t in repo.cited_by("character", ismene)) == [org_a] and [t.id for t in repo.cited_by("character", anselm)] == [org_a])
repo.close()
repo = Repository.open(folder)   # riaprire non rifà nulla
check("riaprire è innocuo", repo.texts(org_a)["notes"].count("<p><b>Leader</b></p>") == 1)
repo.close()

# --- il campo nella scheda ---------------------------------------------------------------------------
repo = new_repo("LeaderUI")
cats = {k: repo.categories(k) for k in ("character", "organization")}
mira = repo.create_element(ElementInput("character", "Mira", cats["character"][0].id, None, "", ""))
ism = repo.create_element(ElementInput("character", "Lady Ismene", cats["character"][2].id, None, "", ""))
org = repo.create_element(ElementInput("organization", "Ordine della Fiamma", cats["organization"][0].id, None, "", ""))
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "organizzazioni", ElementTarget(org, True)); pump(200)
sheet = w._screens["organizzazioni"]._sheet
field = sheet._pages.widget(0).findChildren(LeadersField)[0]
check("nessun leader: c'è il pulsante per andare ai Membri", [b.text().strip() for b in field.findChildren(QPushButton)] == ["Segna un leader nei Membri"])
QTest.mouseClick(field.findChildren(QPushButton)[0], Qt.LeftButton); pump(100)
check("il pulsante apre la scheda Membri", sheet._pages.currentIndex() == sheet._order.index("members"))
r1, r2 = repo.add_relation(org, ism), repo.add_relation(org, mira)
sheet.reload(); pump(100)
sheet._tabs.select("members"); pump(100)
rows = sheet._pages.widget(1).findChildren(_MemberRow)
[r for r in rows if r.relation.other.id == ism][0].leader_toggled.emit(); pump(100)
sheet._tabs.select("profile"); pump(150)
field = sheet._pages.widget(0).findChildren(LeadersField)[0]
check("tornando al Profilo il leader c'è, come nome da cliccare", [n.text() for n in field.findChildren(NameLink)] == ["Lady Ismene"])
got = []
sheet.link_requested.connect(lambda k, i: got.append((k, i)))
field.findChildren(NameLink)[0].click(); pump(50)
check("il nome apre la scheda del leader", got == [("character", ism)] and w._location[1] == "personaggi" and w._screens["personaggi"]._sheet.element_id == ism)
w._topbar.back_clicked.emit(); pump(150)
check("indietro: di nuovo la scheda dell'organizzazione", w._location[1] == "organizzazioni" and sheet._pages.isVisible())
# due leader
sheet._tabs.select("members"); pump(100)
[r for r in sheet._pages.widget(1).findChildren(_MemberRow) if r.relation.other.id == mira][0].leader_toggled.emit(); pump(100)
sheet._tabs.select("profile"); pump(150)
field = sheet._pages.widget(0).findChildren(LeadersField)[0]
check("due leader: due nomi", sorted(n.text() for n in field.findChildren(NameLink)) == ["Lady Ismene", "Mira"])
# togliere il leader
sheet._tabs.select("members"); pump(100)
for name in ("Lady Ismene", "Mira"):
    [r for r in sheet._pages.widget(1).findChildren(_MemberRow) if r.relation.other.name == name][0].leader_toggled.emit(); pump(100)
sheet._tabs.select("profile"); pump(150)
field = sheet._pages.widget(0).findChildren(LeadersField)[0]
check("tolti i leader: torna il pulsante", [b.text().strip() for b in field.findChildren(QPushButton)] == ["Segna un leader nei Membri"])
# un link a una pagina scritto in un campo apre la pagina in Scrittura (errore corretto)
page = repo.create_page("Cap 1")
repo.save_text(org, "symbol", f'<p>vedi <a href="gmj://page/{page}">Cap 1</a></p>')
w._go(repo.folder, "personaggi"); pump(50); w._go(repo.folder, "organizzazioni", ElementTarget(org, True)); pump(200)
sheet = w._screens["organizzazioni"]._sheet
from gmjournal.ui.widgets.field_edit import FieldEdit
fe = [f for f in sheet._pages.widget(0).findChildren(FieldEdit) if "gmj://page" in f.content()][0]
fe._text.link_clicked.emit("page", page); pump(200)
check("link a pagina dentro una scheda: apre la pagina in Scrittura", w._location[1] == "scrittura" and w._screens["scrittura"]._page_id == page)
print(f"\n{sum(ok)}/{len(ok)}")
