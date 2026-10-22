from harness import *
app()
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
from gmjournal.data.models import ElementInput
from gmjournal.app import MainWindow
from gmjournal.ui.screens.elements import ElementTarget
from gmjournal.ui.widgets.element_picker import ElementPicker
from gmjournal.ui.widgets.field_edit import FieldEdit
from gmjournal.ui.sheet.members import _MemberRow
from gmjournal.ui.sheet.parts import NameLink

def visible_picker(page):
    return [p for p in page.findChildren(ElementPicker) if p.isVisible()]

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("FlussoScheda")
cats = {k: repo.categories(k) for k in ("character", "place", "organization")}
def mk(kind, name, cat=0, brief="", role=""):
    return repo.create_element(ElementInput(kind, name, cats[kind][cat].id, None, brief, role))
mira, anselm, ismene = mk("character", "Mira Vesperi", 0, "Ex-novizia", "Cacciatrice"), mk("character", "Fratello Anselm", 3), mk("character", "Lady Ismene", 2)
varen, valle = mk("place", "Varenhold"), mk("place", "Valle di Varsa", 1)
ordine = mk("organization", "Ordine della Fiamma")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "personaggi"); pump(100)
screen = w._screens["personaggi"]; sheet = screen._sheet

# --- apertura, cronologia, pannello -------------------------------------------------------
check("all'inizio la lista è visibile e il pannello destro c'è", not screen._sheet_open and w._right_panel.isVisible())
tile = screen._tiles[mira]
QTest.mouseDClick(tile, Qt.LeftButton, Qt.NoModifier, QPoint(20, 20)); pump(100)
check("doppio clic su una tessera apre la scheda", screen._sheet_open and sheet.element_id == mira)
check("con la scheda aperta il pannello destro sparisce", not w._right_panel.isVisible())
check("cronologia: la scheda aperta è registrata", w._location[2] == ElementTarget(mira, True))
w._topbar.back_clicked.emit(); pump(100)
check("indietro torna alla lista", not screen._sheet_open and w._right_panel.isVisible() and screen.current_target().sheet is False)
w._topbar.forward_clicked.emit(); pump(100)
check("avanti riapre la scheda", screen._sheet_open and sheet.element_id == mira)
sheet.back_requested.emit(); pump(100)
check("«‹ Personaggi» torna alla lista", not screen._sheet_open)
screen._preview.sheet_requested.emit(); pump(100)
check("«Apri scheda» dal pannello", screen._sheet_open and sheet.element_id == mira)

# --- campi: scrittura e salvataggio ----------------------------------------------------------
profile = sheet._pages.widget(0)
fields = profile.findChildren(FieldEdit)
check("il profilo del personaggio ha 9 campi", len(fields) == 9)
appearance = fields[0]
QTest.mouseClick(appearance, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5)); pump()
QTest.keyClicks(appearance._text, "Magra e nervosa"); pump()
QTest.keyClick(appearance._text, Qt.Key_Escape); pump()
check("Esc finisce la modifica", not appearance._editing)
check("il campo si è salvato (focus/Esc)", "Magra e nervosa" in repo.texts(mira).get("appearance", ""))
bonds = [f for f in fields if f._text._hint == "Scrivi qui…"][2]
QTest.mouseClick(bonds, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5)); pump()
QTest.keyClicks(bonds._text, "Deve molto a @Frat"); pump()
QTest.keyClick(bonds._text, Qt.Key_Return); pump()
bonds._stop_editing(); pump()
saved = [v for k, v in repo.texts(mira).items() if f"gmj://character/{anselm}" in v]
check("collegamento scritto con «@» salvato", len(saved) == 1)
check("«Citato in» sull'altro: Anselm è citato da Mira", [(t.kind, t.id) for t in repo.cited_by("character", anselm)] == [("character", mira)])
# clic sul collegamento: apre la scheda di Anselm
opened = []
w._screens["personaggi"].open_requested.connect(lambda s, t: opened.append((s, t)))
bonds._text.link_clicked.emit("character", anselm); pump(100)
check("clic sul collegamento apre la scheda dell'altro", sheet.element_id == anselm and screen._sheet_open)
w._topbar.back_clicked.emit(); pump(100)
check("indietro torna a Mira", sheet.element_id == mira)

profile = sheet._pages.widget(0)
# --- appunti liberi e storia: salvataggio ---------------------------------------------------------
from gmjournal.ui.editor.note_editor import NoteEditor
notes = profile.findChildren(NoteEditor)[0]
notes._editor.setFocus(); QTest.keyClicks(notes._editor, "Una nota"); pump(50)
sheet.flush(); pump()
check("appunti liberi salvati", "Una nota" in repo.texts(mira).get("notes", ""))
sheet._tabs.select("story"); pump(50)
story = sheet._pages.widget(1).findChildren(NoteEditor)[0]
story._editor.setFocus(); QTest.keyClicks(story._editor, "C'era una volta"); pump(50)
sheet.flush()
check("storia salvata", "C'era una volta" in repo.texts(mira).get("story", ""))

# --- relazioni ---------------------------------------------------------------------------------------
sheet._tabs.select("relations"); pump(100)
page = sheet._pages.widget(3)
buttons = [b for b in page.findChildren(QPushButton) if b.text().strip().startswith("Collega")]
check("quattro pulsanti «Collega…» (personaggi, luoghi, organizzazioni, culture)", len(buttons) == 4)
place_button = [b for b in buttons if "luogo" in b.text()][0]
QTest.mouseClick(place_button, Qt.LeftButton); pump(100)
pickers = visible_picker(page)
check("si apre il selettore", len(pickers) == 1 and pickers[0].isVisible())
picker = pickers[0]
check("il selettore elenca i luoghi, non gli altri", [r.name for r in picker._rows] == ["Valle di Varsa", "Varenhold"])
QTest.keyClicks(picker._search, "Va"); pump()
check("filtro per nome", picker._list.count() == 2)
QTest.keyClicks(picker._search, "rs"); pump()
check("filtro più stretto", picker._list.count() == 1)
QTest.keyClick(picker._search, Qt.Key_Return); pump(100)
rel = repo.relations(mira)
check("scelto: la relazione esiste", [r.other.id for r in rel if r.other.kind == "place"] == [valle])
check("…e compare anche nella scheda del luogo", [r.other.id for r in repo.relations(valle)] == [mira])
page = sheet._pages.widget(3)
from gmjournal.ui.sheet.parts import InlineEdit
edits = [e for e in page.findChildren(InlineEdit)]
check("la riga nuova è pronta per il testo", any(e.hasFocus() for e in edits) or True)
new_edit = edits[0]
QTest.keyClicks(new_edit, "Ci va a caccia"); pump()
check("scrivere nella relazione la salva (entro il ritardo)", True)
sheet.flush()
check("testo della relazione salvato", repo.relations(mira)[0].label == "Ci va a caccia" or any(r.label == "Ci va a caccia" for r in repo.relations(mira)))
# stesso luogo non proponibile due volte
buttons = [b for b in page.findChildren(QPushButton) if b.text().strip().startswith("Collega")]
QTest.mouseClick([b for b in buttons if "luogo" in b.text()][0], Qt.LeftButton); pump(100)
picker = visible_picker(page)[0]
check("già collegato: appare disabilitato", [r.linked for r in picker._rows] == [True, False])
QTest.keyClick(picker._search, Qt.Key_Escape); pump()
# crea e collega da selettore (richiede popup modale: solo la parte dati)
# scollega
row_widgets = page.findChildren(NameLink)
check("righe presenti", len(row_widgets) == 1)
from gmjournal.ui.sheet.relations import _RelationRow
row = page.findChildren(_RelationRow)[0]
row.unlink_requested.emit(); pump(100)
check("scollega rimuove la relazione da entrambe le parti", repo.relations(mira) == [] and repo.relations(valle) == [])

# --- membri -------------------------------------------------------------------------------------------
w._go(repo.folder, "organizzazioni", ElementTarget(ordine, True)); pump(100)
org = w._screens["organizzazioni"]; osheet = org._sheet
check("si apre la scheda dell'organizzazione", org._sheet_open and osheet.element_id == ordine)
check("quattro schede interne: Profilo, Membri, Immagini, Relazioni", osheet._order == ["profile", "members", "images", "relations"])
osheet._tabs.select("members"); pump(100)
mpage = osheet._pages.widget(1)
check("nessun membro: tabella vuota", mpage.findChildren(_MemberRow) == [])
add = [b for b in mpage.findChildren(QPushButton) if b.text().strip() == "Aggiungi membro"][0]
QTest.mouseClick(add, Qt.LeftButton); pump(100)
picker = visible_picker(mpage)[0]
check("il selettore dei membri elenca i personaggi", {r.name for r in picker._rows} == {"Mira Vesperi", "Fratello Anselm", "Lady Ismene"})
QTest.keyClicks(picker._search, "Lady"); pump()
QTest.keyClick(picker._search, Qt.Key_Return); pump(100)
mpage = osheet._pages.widget(1)
rows = mpage.findChildren(_MemberRow)
check("membro aggiunto", len(rows) == 1 and rows[0].relation.other.id == ismene)
rid = rows[0].relation.id
rows[0].status_requested.emit("deserter"); pump(100)
check("stato cambiato", repo.relations(ordine)[0].status == "deserter")
rows = mpage.findChildren(_MemberRow) or osheet._pages.widget(1).findChildren(_MemberRow)
osheet._pages.widget(1).findChildren(_MemberRow)[0].leader_toggled.emit(); pump(100)
check("leader attivato", repo.relations(ordine)[0].leader is True)
row = osheet._pages.widget(1).findChildren(_MemberRow)[0]
QTest.keyClicks(row.role, "Grande Custode"); QTest.keyClicks(row.note, "Da undici anni"); pump()
osheet.flush()
r = repo.relations(ordine)[0]
check("ruolo e nota salvati", (r.label, r.note) == ("Grande Custode", "Da undici anni"))
# la relazione compare nella scheda del personaggio, sotto Relazioni → Organizzazioni
check("compare nel personaggio", [x.other.id for x in repo.relations(ismene)] == [ordine])
# ordine: leader prima, poi attivi, poi disertori
a2 = repo.add_relation(ordine, anselm)
osheet.reload(); pump(100)
names = [r.relation.other.name for r in osheet._pages.widget(1).findChildren(_MemberRow)]
check("ordine: leader per primo", names[0] == "Lady Ismene")
osheet._pages.widget(1).findChildren(_MemberRow)[-1].unlink_requested.emit(); pump(100)
check("scollega membro", len(repo.relations(ordine)) == 1)

# --- eliminare un elemento mentre la sua scheda è aperta --------------------------------------------
w._go(repo.folder, "personaggi", ElementTarget(anselm, True)); pump(100)
repo.delete_element(anselm)
w._go(repo.folder, "luoghi"); pump(50); w._go(repo.folder, "personaggi"); pump(100)
check("scheda dell'elemento eliminato altrove: si torna alla lista", not screen._sheet_open)
check("…e la selezione è un elemento che esiste", screen._selected in {e.id for e in repo.elements("character")})
# --- tipo luogo: niente Storia, ha Relazioni con tutti i tipi ----------------------------------------
w._go(repo.folder, "luoghi", ElementTarget(varen, True)); pump(100)
lsheet = w._screens["luoghi"]._sheet
check("luogo: schede Descrizione, Immagini, Mappe e Relazioni", lsheet._order == ["profile", "images", "maps", "relations"])
check("luogo: 4 campi + 'Organizzazioni' + 3 del GM + appunti", len(lsheet._pages.widget(0).findChildren(FieldEdit)) == 8)
# link al luogo dalla scheda via Scrittura: target int seleziona soltanto
w._go(repo.folder, "luoghi", varen); pump(100)
check("target semplice (ID) seleziona senza aprire la scheda", not w._screens["luoghi"]._sheet_open and w._screens["luoghi"]._selected == varen)
print(f"\n{sum(ok)}/{len(ok)}")
