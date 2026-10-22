"""Il box «Incontro» in Scrittura: salvataggio e lettura, inserimento dal menu Box, scheda disegnata, clic che apre l'incontro,
incontro eliminato, copia e incolla, annulla, togliere il box."""
from harness import *
app()
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QImage, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from gmjournal.app import MainWindow
from gmjournal.data.models import CreatureInput, EncounterInput, PartyGroup, Slot
from gmjournal.ui.editor import markup, styles
from gmjournal.ui.editor.link_ui import LinkPickerPopup
from gmjournal.ui.editor.encounter_box import card_height
from gmjournal.data import plain
from gmjournal.ui.encounter_target import ENCOUNTERS, EncounterTarget

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def drive(fn, delay=80):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))

def creature(name, challenge):
    return CreatureInput(name, "Medium", "humanoid", "", "15", "7 (2d6)", "walk 30 ft.", (10,) * 6, "", "", "", "", "", "", "", 9, "", challenge, "", "", "", ())

repo = new_repo("ProvaBoxIncontro")
goblin = repo.create_creature(creature("Goblin", "1/4"))
ogre = repo.create_creature(creature("Ogre", "2"))
fight = repo.create_encounter(EncounterInput("Imboscata dei goblin", "combat", (PartyGroup(3, 4),), (Slot(goblin, 4), Slot(ogre, 1))))
talk = repo.create_encounter(EncounterInput("Trattativa", "interaction", (), ()))
page = repo.create_page("Capitolo 1")

w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "scrittura", page); pump(200)
s = w._screens["scrittura"]
ed = s._editor
doc = ed.document()

# --- il formato salvato ------------------------------------------------------------------------------------------
ed.set_content(f'<p>Prima</p><div class="encounter" data-id="{fight}"></div><p>Dopo</p>'); pump(100)
found = [styles.encounter_in(b) for b in (doc.findBlockByNumber(i) for i in range(doc.blockCount()))]
check("il box è un paragrafo suo, fra gli altri due", found == [None, fight, None])
check("si salva com'era", ed.content() == f'<p>Prima</p><div class="encounter" data-id="{fight}"></div><p>Dopo</p>')
check("un testo senza box non ne ha", "encounter" not in markup.export_html(markup.QTextDocument()) )
ed.set_content(f'<div class="encounter" data-id="{fight}"></div>'); pump(50)
check("il box da solo, in cima, si legge e si salva", ed.content() == f'<div class="encounter" data-id="{fight}"></div>')
ed.set_content(f'<div class="encounter" data-id="x"></div><div class="encounter"></div><p>Testo</p>'); pump(50)
check("un box senza ID valido si ignora", ed.content() == "<p>Testo</p>")
ed.set_content(f'<div class="box master"><p>Nota</p></div><div class="encounter" data-id="{talk}"></div><ul><li>Uno</li></ul>'); pump(50)
check("dopo un box e prima di un elenco il testo resta com'è", ed.content() == f'<div class="box master"><p>Nota</p></div><div class="encounter" data-id="{talk}"></div><ul><li>Uno</li></ul>')

# --- la scheda disegnata ------------------------------------------------------------------------------------------
ed.set_content(f'<p>Prima</p><div class="encounter" data-id="{fight}"></div><p>Dopo</p>'); pump(100)
card = ed._card(fight)
check("la scheda: nome, tipo, riepilogo e creature con le copie", card.name == "Imboscata dei goblin" and card.kind_icon == "swords"
      and card.summary == "Combattimento · 4 giocatori · liv. 3 · 5 creature" and card.creatures == (("Goblin", 4), ("Ogre", 1)))
check("la difficoltà dei combattimenti", card.difficulty in ("trivial", "easy", "medium", "hard", "deadly"))
talk_card = ed._card(talk)
check("un'interazione: niente difficoltà né giocatori", talk_card.difficulty is None and talk_card.summary == "Interazione · nessuna scheda" and talk_card.creatures == ())
block = doc.findBlockByNumber(1)
rect = doc.documentLayout().blockBoundingRect(block)
check("il box occupa tutta la larghezza e l'altezza della scheda", abs(rect.width() - doc.pageSize().width()) < 1 and rect.height() >= card_height(card))
image = ed.viewport().grab().toImage()
pixels = {image.pixelColor(x, int(rect.top()) + 40).name() for x in range(10, 300, 7)}
check("si vede disegnato (lo sfondo della scheda)", "#2b2326" in pixels)

# --- un clic apre l'incontro --------------------------------------------------------------------------------------
opened = []
ed.link_activated.connect(lambda kind, i: opened.append((kind, i)))
y = ed.cursorRect(QTextCursor(block)).top() + 20
QTest.mouseClick(ed.viewport(), Qt.LeftButton, pos=QPoint(100, y)); pump(50)
check("un clic sul box apre l'incontro", opened == [("encounter", fight)])
before = ed.textCursor().position()
check("…senza spostare il cursore né cambiare il testo", ed.textCursor().position() == before and ed.content().count("encounter") == 1)
QTest.mouseClick(ed.viewport(), Qt.LeftButton, pos=QPoint(100, 5)); pump(50)
check("un clic fuori dal box non apre nulla", len(opened) == 1)
s._open_target("encounter", fight); pump(200)
check("da Scrittura l'incontro si apre nella schermata Incontri", w._location[1] == "incontri" and w._location[2] == EncounterTarget(ENCOUNTERS, fight))
w._go(repo.folder, "scrittura", page); pump(200)
ed = s._editor; doc = ed.document()

# --- inserire dal menu Box ----------------------------------------------------------------------------------------
ed.set_content("<p>Inizio</p><p>Fine</p>"); pump(50)
cursor = QTextCursor(doc); cursor.setPosition(len("Inizio")); ed.setTextCursor(cursor)
check("il menu Box offre «Incontro…» (l'editor di Scrittura ha gli incontri)", ed.has_encounters)
def pick(popup):
    check("il popup elenca gli incontri per nome", isinstance(popup, LinkPickerPopup) and [t.name for t in popup._targets("", 50)] == ["Imboscata dei goblin", "Trattativa"])
    check("…e li cerca", [t.name for t in popup._targets("tratt", 50)] == ["Trattativa"] and popup._targets("zzz", 50) == [])
    check("…con il tipo come dettaglio", [t.detail for t in popup._targets("", 50)] == ["Combattimento", "Interazione"])
    popup._search.setText("trat"); pump(20)
    popup._list.setCurrentRow(0) if hasattr(popup._list, "setCurrentRow") else None
    popup.accept()
drive(pick); ed.choose_encounter(); pump(100)
check("a metà paragrafo: il testo si divide e il box sta in mezzo", ed.content() == f'<p>Inizio</p><div class="encounter" data-id="{talk}"></div><p></p><p>Fine</p>'
      or ed.content() == f'<p>Inizio</p><div class="encounter" data-id="{talk}"></div><p>Fine</p>')
doc.undo(); pump(50)
check("Annulla toglie l'inserimento in un solo passo", ed.content() == "<p>Inizio</p><p>Fine</p>")
doc.redo(); pump(50)
check("Ripeti lo rimette", f'data-id="{talk}"' in ed.content())

ed.set_content(""); pump(50)
drive(lambda popup: (popup._search.setText("imb"), popup.accept())); ed.choose_encounter(); pump(100)
check("in una pagina vuota il box è il solo contenuto", ed.content() == f'<div class="encounter" data-id="{fight}"></div>')
drive(lambda popup: popup.reject()); ed.choose_encounter(); pump(100)
check("annullando il popup non cambia nulla", ed.content() == f'<div class="encounter" data-id="{fight}"></div>')

ed.set_content('<div class="box voice"><p>Leggi</p><p>Ancora</p></div><p>Dopo</p>'); pump(50)
cursor = QTextCursor(doc); cursor.setPosition(3); ed.setTextCursor(cursor)
import gmjournal.ui.editor.commands as commands
commands.insert_encounter(ed, fight); pump(50)
check("da dentro un box, l'incontro va dopo il box (e il cursore è nel paragrafo vuoto che segue)",
      ed.content() == f'<div class="box voice"><p>Leggi</p><p>Ancora</p></div><div class="encounter" data-id="{fight}"></div><p></p><p>Dopo</p>'
      and ed.textCursor().block().length() == 1)

ed.set_content("<ul><li>Uno</li><li>Due</li><li>Tre</li></ul>"); pump(50)
cursor = QTextCursor(doc); cursor.setPosition(len("UnoDu") + 1); ed.setTextCursor(cursor)
commands.insert_encounter(ed, fight); pump(50)
check("da un elenco, il box esce dall'elenco e il resto continua", ed.content() == f'<ul><li>Uno</li><li>Du</li></ul><div class="encounter" data-id="{fight}"></div><ul><li>e</li><li>Tre</li></ul>')

ed.set_content("<h2>Titolo</h2>"); pump(50)
cursor = QTextCursor(doc); cursor.movePosition(QTextCursor.End); ed.setTextCursor(cursor)
commands.insert_encounter(ed, fight); pump(50)
check("dopo un titolo il box non è un titolo", ed.content() == f'<h2>Titolo</h2><div class="encounter" data-id="{fight}"></div>')

ed.set_content("<table><tr><th>A</th></tr><tr><td>b</td></tr></table>"); pump(50)
cursor = QTextCursor(doc); cursor.setPosition(doc.findBlockByNumber(1).position()); ed.setTextCursor(cursor)
commands.insert_encounter(ed, fight); pump(50)
check("in una tabella non si inseriscono incontri", "encounter" not in ed.content())

# --- copia e incolla ----------------------------------------------------------------------------------------------
ed.set_content(f'<p>Uno</p><div class="encounter" data-id="{fight}"></div><p>Due</p>'); pump(50)
ed.selectAll(); ed.copy(); pump(20)
ed.set_content("<p>Altro</p><p></p>"); pump(50)
cursor = QTextCursor(doc); cursor.movePosition(QTextCursor.End); ed.setTextCursor(cursor)
ed.paste(); pump(100)
check("copiato e incollato, il box c'è ancora", ed.content() == f'<p>Altro</p><p>Uno</p><div class="encounter" data-id="{fight}"></div><p>Due</p>')

# --- togliere il box ----------------------------------------------------------------------------------------------
ed.set_content(f'<p>Uno</p><div class="encounter" data-id="{fight}"></div><p>Due</p>'); pump(50)
commands.remove_encounter(ed, fight); pump(50)
check("«Togli il box dal testo» lo toglie con il suo paragrafo", ed.content() == "<p>Uno</p><p>Due</p>")
ed.set_content(f'<div class="encounter" data-id="{fight}"></div><p>Due</p>'); pump(50)
commands.remove_encounter(ed, fight); pump(50)
check("…anche se è il primo", ed.content() == "<p>Due</p>")
ed.set_content(f'<p>Uno</p><div class="encounter" data-id="{fight}"></div>'); pump(50)
commands.remove_encounter(ed, fight); pump(50)
check("…o l'ultimo", ed.content() == "<p>Uno</p>")
ed.set_content(f'<div class="encounter" data-id="{fight}"></div>'); pump(50)
cursor = QTextCursor(doc); cursor.setPosition(0); ed.setTextCursor(cursor)
QTest.keyClick(ed, Qt.Key_Delete); pump(50)
check("con la tastiera (Canc davanti al box) sparisce", "encounter" not in ed.content())

# --- testo scritto accanto al box ----------------------------------------------------------------------------------
ed.set_content(f'<div class="encounter" data-id="{fight}"></div>'); pump(50)
cursor = QTextCursor(doc); cursor.movePosition(QTextCursor.End); ed.setTextCursor(cursor)
QTest.keyClicks(ed, "ciao"); pump(50)
check("il testo scritto accanto al box diventa un paragrafo, dopo salvato", ed.content() == f'<div class="encounter" data-id="{fight}"></div><p>ciao</p>')

# --- incontro eliminato o rinominato -----------------------------------------------------------------------------
ed.set_content(f'<p>x</p><div class="encounter" data-id="{talk}"></div>'); pump(50)
repo.update_encounter(talk, EncounterInput("Trattativa lunga", "interaction", (), ()))
ed.set_content(ed.content()); pump(50)
check("rinominato: la scheda lo mostra aggiornato", ed._card(talk).name == "Trattativa lunga")
repo.delete_encounter(talk)
ed.set_content(ed.content()); pump(50)
check("eliminato: nessuna scheda, resta il segnaposto e il testo salvato non cambia", ed._card(talk) is None and f'data-id="{talk}"' in ed.content())
rect = doc.documentLayout().blockBoundingRect(doc.findBlockByNumber(1))
check("il segnaposto ha un'altezza sua", card_height(None) == 64 and rect.height() >= 64)
opened.clear()
y = ed.cursorRect(QTextCursor(doc.findBlockByNumber(1))).top() + 20
QTest.mouseClick(ed.viewport(), Qt.LeftButton, pos=QPoint(100, y)); pump(50)
check("un clic sul segnaposto non apre nulla", opened == [])

# --- una pagina salvata e riaperta ---------------------------------------------------------------------------------
ed.set_content(f'<p>Scena</p><div class="encounter" data-id="{fight}"></div>'); pump(50)
ed.edited.emit(); s.flush(); pump(100)
check("la pagina salvata contiene il box", f'data-id="{fight}"' in repo.page(page).content)
check("…e il testo semplice (conteggio parole, anteprime) non ne è disturbato", plain.count_words(repo.page(page).content) == 1)

# --- gli altri editor non hanno incontri ---------------------------------------------------------------------------
from gmjournal.ui.editor.editor import RichEditor
plain = RichEditor(); 
check("un editor senza sorgente non offre incontri", not plain.has_encounters)

print(f"{sum(ok)}/{len(ok)}")
