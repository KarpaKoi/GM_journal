"""Passo 11b, «Cerca nella pagina»: le occorrenze nel testo (maiuscole, accenti, celle), la barra, successivo/precedente, coerenza."""
from harness import *
app()
import time
from PySide6.QtCore import QPoint
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget
from gmjournal import spelling
from gmjournal.app import MainWindow
from gmjournal.ui.editor import markup
from gmjournal.ui.editor.editor import RichEditor
from gmjournal.ui.editor.find_ui import find_matches, match_rects
from gmjournal.ui.editor.note_editor import NoteEditor
from gmjournal.ui.editor.toolbar import FormatToolbar

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def doc_of(html):
    doc = QTextDocument(); markup.fill_document(doc, html); return doc

def found(html, query):
    doc = doc_of(html); text = doc.toPlainText()
    return [text[a:b] for a, b in find_matches(doc, query)]

# --- Dove sono le occorrenze (nessuna finestra) -----------------------------------------------------
check("maiuscole ignorate", found("<p>Locanda LOCANDA locanda</p>", "locanda") == ["Locanda", "LOCANDA", "locanda"])
check("accenti ignorati, in tutti e due i versi", found("<p>Città citta CITTÀ</p>", "citta") == ["Città", "citta", "CITTÀ"]
      and found("<p>Città citta</p>", "città") == ["Città", "citta"])
check("apostrofo dritto e tipografico sono uguali", found("<p>l’arrivo e l'arrivo</p>", "l'arrivo") == ["l’arrivo", "l'arrivo"]
      and found("<p>l’arrivo e l'arrivo</p>", "l’arrivo") == ["l’arrivo", "l'arrivo"])
check("una frase con spazi", found("<p>la Locanda del Corvo, la locanda del corvo</p>", "locanda del corvo") == ["Locanda del Corvo", "locanda del corvo"])
check("occorrenze che non si sovrappongono", found("<p>aaaaa</p>", "aa") == ["aa", "aa"])
check("campo vuoto o di soli spazi: nessun risultato", found("<p>a b c</p>", "") == [] and found("<p>a b c</p>", "   ") == [])
check("nessuna occorrenza fra due paragrafi", found("<p>fine</p><p>inizio</p>", "fine inizio") == [] and found("<p>fine</p><p>inizio</p>", "ineinizio") == [])
check("un testo più corto della ricerca non c'entra", found("<p>ab</p>", "abc") == [])
check("nelle celle delle tabelle", found("<table><tr><th>Voce</th></tr><tr><td>nella locanda</td></tr></table><p>x</p>", "locanda") == ["locanda"])
check("nel testo di un collegamento, in grassetto, evidenziato",
      found("<p><a href='gm://page/1'>Locanda</a> <b>locanda</b> <span class='hl hl-sabbia'>locanda</span></p>", "locanda") == ["Locanda", "locanda", "locanda"])
doc = doc_of("<p>ﬁnale e finale</p>")        # la legatura «ﬁ» diventa «fi» (due lettere): la posizione resta quella del testo vero
check("lettere che cambiano lunghezza (legatura «ﬁ»): la posizione resta giusta",
      [doc.toPlainText()[a:b] for a, b in find_matches(doc, "fin")] == ["ﬁn", "fin"])
doc = doc_of("<p>uno</p><p>due locanda</p>")
a, b = find_matches(doc, "locanda")[0]
check("le posizioni sono quelle del documento (seconda riga)", doc.toPlainText()[a:b] == "locanda" and doc.findBlock(a).blockNumber() == 1)

# --- L'editor con la ricerca ------------------------------------------------------------------------
repo = new_repo("Trova")
HTML = ("<p>La sala della <a href='gm://page/1'>Locanda del Corvo</a> era silenziosa, perché la locanda era vuota. Un viandante.</p>"
        "<table><tr><th>d6</th><th>Voce</th></tr><tr><td>1</td><td>Nella locanda piove</td></tr></table>"
        "<p>Dopo la LOCANDA e la Locànda.</p>")
host = QWidget(); host.resize(1100, 640)
ed = RichEditor(speller=repo.speller, searchable=True)
bar = FormatToolbar(ed)
column = QVBoxLayout(host); column.setContentsMargins(0, 0, 0, 0); column.setSpacing(0)
column.addWidget(bar); column.addWidget(ed)
host.show(); host.activateWindow(); pump(100)
spelling.load_dictionary()
edited = []
ed.edited.connect(lambda: edited.append(1))
ed.set_content(HTML); ed.setFocus(); pump(200)
find = ed.find
field = find._bar._field._edit
counter = find._bar._count

def undo_state():
    return ed.document().isUndoAvailable()

def type_query(text):
    field.setFocus(); field.setText(text); pump(100)

cursor_before = ed.textCursor().position()
content_before = ed.content()
check("si apre solo dalla lente: all'inizio la barra non c'è", not find.is_open and find._bar.isHidden())
lens = bar._find
check("la lente è nella barra, a destra di «Italiano»", lens is not None and lens.mapTo(bar, QPoint(0, 0)).x() > bar._language.mapTo(bar, QPoint(0, 0)).x())
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
check("un clic sulla lente apre la barra e la lente resta evidenziata", find.is_open and lens.isChecked())
check("il cursore è nel campo di ricerca", field.hasFocus())
geometry = find._bar.geometry()
check("barra in alto a destra del testo: 368 px, 12 px dall'alto, 20 px dal bordo",
      geometry.width() == 368 and geometry.y() == 12 and abs((ed.width() - ed.verticalScrollBar().width() * ed.verticalScrollBar().isVisible()) - geometry.right() - 1 - 20) <= 1)
check("campo vuoto: nessun conteggio", counter.text() == "")

type_query("locanda")
check("conta le occorrenze: collegamento, testo, cella, maiuscolo, accento → «1 di 5»", counter.text() == "1 di 5" and len(find._matches) == 5)
check("la prima è quella corrente e ha il contorno", len(ed._outlines) >= 1)
marks = ed._overlays["find"]
check("tutte le occorrenze sono evidenziate", len(marks) == 5)
check("quella corrente è azzurra (157, 183, 232), le altre sabbia (224, 207, 160)",
      marks[0].format.background().color().getRgb()[:3] == (157, 183, 232) and marks[1].format.background().color().getRgb()[:3] == (224, 207, 160))
check("la ricerca non tocca testo, cursore, annulla, modifiche",
      ed.content() == content_before and ed.textCursor().position() == cursor_before and not undo_state()
      and not ed.document().isModified() and edited == [])

QTest.keyClick(field, Qt.Key_Return); pump(50)
check("Invio: successiva «2 di 5»", counter.text() == "2 di 5")
for _ in range(3):
    QTest.keyClick(field, Qt.Key_Return)
pump(50)
check("ancora tre Invio: l'ultima «5 di 5»", counter.text() == "5 di 5")
QTest.keyClick(field, Qt.Key_Return); pump(50)
check("dopo l'ultima si riparte dalla prima «1 di 5»", counter.text() == "1 di 5")
buttons = {b.toolTip(): b for b in find._bar.findChildren(QToolButton)}
QTest.mouseClick(buttons["Risultato precedente"], Qt.LeftButton); pump(50)
check("«precedente» dalla prima va all'ultima «5 di 5»", counter.text() == "5 di 5")
QTest.mouseClick(buttons["Risultato successivo"], Qt.LeftButton); pump(50)
check("«successivo» dall'ultima va alla prima", counter.text() == "1 di 5")
check("la corrente cambia colore con lei", ed._overlays["find"][0].format.background().color().red() == 157)

type_query("citta")
check("ricerca senza accenti: «Città» non c'è in questa pagina → nessun risultato", counter.text() == "Nessun risultato" and ed._overlays["find"] == [] and ed._outlines == [])
type_query("locànda")
check("ricerca con l'accento trova anche senza", counter.text() == "1 di 5")
type_query("corvo")
check("una frase dentro un collegamento: «1 di 1»", counter.text() == "1 di 1")
check("il testo salvato è identico dopo tante ricerche", ed.content() == content_before and edited == [] and not undo_state())

# --- Chiudere ---------------------------------------------------------------------------------------
QTest.keyClick(field, Qt.Key_Escape); pump(50)
check("Esc chiude la barra, toglie le evidenziature e il contorno", not find.is_open and ed._overlays["find"] == [] and ed._outlines == [])
check("il cursore torna nel testo e la lente si spegne", ed.hasFocus() and not lens.isChecked())
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
check("riaperta ricorda la ricerca di prima", find.is_open and counter.text() == "1 di 1" and field.text() == "corvo")
QTest.mouseClick(buttons["Chiudi la ricerca"], Qt.LeftButton); pump(50)
check("il pulsante ✕ chiude", not find.is_open and ed.hasFocus())
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
check("la lente apre e richiude (alterna)", not find.is_open)

# --- Il testo cambia mentre la ricerca è aperta -------------------------------------------------------
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
type_query("locanda")
check("riparte da «1 di 5»", counter.text() == "1 di 5")
ed.setFocus(); c = ed.textCursor(); c.movePosition(QTextCursor.End); ed.setTextCursor(c)
QTest.keyClicks(ed, " La locanda finale."); pump(400)
check("scrivendo una nuova occorrenza il conteggio si aggiorna da solo: «… di 6»", counter.text().endswith("di 6") and len(find._matches) == 6)
for _ in range(len(" La locanda finale.")):
    QTest.keyClick(ed, Qt.Key_Backspace)
pump(400)
check("cancellandola torna a 5", counter.text().endswith("di 5") and len(find._matches) == 5)
check("ogni occorrenza evidenziata è davvero «locanda» (le posizioni sono aggiornate)",
      all(ed.document().toPlainText()[m.cursor.selectionStart():m.cursor.selectionEnd()].lower().replace("à", "a").replace("ò", "o") in ("locanda", "locànda".replace("à", "a"))
          for m in ed._overlays["find"]))
text_now = ed.document().toPlainText()
check("e coincidono con le occorrenze trovate", [(m.cursor.selectionStart(), m.cursor.selectionEnd()) for m in ed._overlays["find"]] == find._matches)
undo_steps = 0
while ed.document().isUndoAvailable() and undo_steps < 80:
    ed.document().undo(); undo_steps += 1
pump(400)
check("l'annulla riporta il testo di prima e la ricerca resta coerente", ed.content() == content_before and len(find._matches) == 5)

# --- Cambiare pagina chiude la ricerca ----------------------------------------------------------------
ed.set_content("<p>Altra pagina con locanda</p>"); pump(100)
check("un'altra pagina: la ricerca si chiude e le evidenziature spariscono",
      not find.is_open and not lens.isChecked() and ed._overlays["find"] == [] and ed._outlines == [])
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
type_query("locanda")
ed.set_content("<p>Testo cambiato da fuori, locanda e locanda</p>", keep_view=True); pump(400)
check("un testo cambiato da fuori (stessa pagina) non chiude la ricerca e la aggiorna", find.is_open and counter.text().endswith("di 2"))
find.close(); pump(50)

# --- Il contorno sta sul testo -------------------------------------------------------------------------
ed.set_content("<p>Prima riga con la parola trovami nel mezzo e basta.</p>"); ed.resize(1100, 400); pump(100)
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
type_query("trovami")
rect = ed._outlines[0]
start = QTextCursor(ed.document()); start.setPosition(ed.document().toPlainText().index("trovami"))
finish = QTextCursor(ed.document()); finish.setPosition(ed.document().toPlainText().index("trovami") + 7)
a, b = ed.cursorRect(start), ed.cursorRect(finish)
check("il contorno parte dall'inizio della parola e finisce alla sua fine (±2 px)", abs(rect.left() - a.left()) <= 2 and abs(rect.right() - b.left()) <= 2)
check("e sta sulla riga della parola", rect.top() - ed.verticalScrollBar().value() <= a.center().y() <= rect.bottom() - ed.verticalScrollBar().value())
ed.grab().save("/tmp/claude-0/shots/find_ui.png")
find.close(); pump(50)

# --- Parola che va a capo: un contorno per riga -------------------------------------------------------
ed.set_content("<p>" + "parola " * 30 + "due parole divise da un a capo lungo lungo lungo lungo lungo lungo lungo lungo lungo lungo</p>")
ed.resize(520, 400); pump(150)
doc = ed.document(); text = doc.toPlainText()
line = doc.firstBlock().layout().lineAt(0)
break_at = line.textStart() + line.textLength()
rects = match_rects(doc, break_at - 5, break_at + 5)         # a cavallo del primo a capo
check("un'occorrenza su due righe ha due rettangoli, uno sotto l'altro", len(rects) == 2 and rects[1].top() > rects[0].top())
check("una su una riga sola ne ha uno", len(match_rects(doc, 0, 5)) == 1)

# --- Pagina lunga: si porta in vista e si evidenzia solo ciò che si vede --------------------------------
sentence = "<p>La sala della locanda era più silenziosa del solito quando la porta si aprì e un viandante entrò lentamente nell'ombra.</p>"
ed.resize(1000, 500)
ed.set_content(sentence * 600 + "<p>L'ultima riga ha una zebra solitaria.</p>"); pump(200)
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
start_time = time.perf_counter(); type_query("zebra"); elapsed = time.perf_counter() - start_time
scroll = ed.verticalScrollBar()
rect = ed._outlines[0]
check("«zebra» è l'unica occorrenza e la pagina scorre fino a lei", counter.text() == "1 di 1" and scroll.value() > 1000
      and scroll.value() <= rect.top() <= scroll.value() + ed.viewport().height())
type_query("a")
check("cercando una lettera su una pagina lunga si evidenzia solo il testo in vista (meno di 4000 segni)",
      len(find._matches) > 5000 and 0 < len(ed._overlays["find"]) < 4000)
start_time = time.perf_counter(); type_query("locanda"); slow = time.perf_counter() - start_time
print(f"  (ricerca di «locanda» in {len(ed.document().toPlainText()) // 1024} KB: {slow * 1000:.0f} ms compresa la pausa di 100 ms)")
check("cercare in una pagina lunga è rapido (meno di 0,6 s)", slow < 0.6)
before = ed._overlays["find"][0].cursor.selectionStart()
scroll.setValue(scroll.maximum() // 2); pump(100)
check("scorrendo cambiano le occorrenze evidenziate (quelle in vista)", ed._overlays["find"][0].cursor.selectionStart() != before)
find.close(); pump(50)

# --- La barra segue la finestra; stile ----------------------------------------------------------------------
ed.set_content(HTML); ed.resize(1100, 500); pump(100)
QTest.mouseClick(lens, Qt.LeftButton); pump(100)
x1 = find._bar.x()
ed.resize(900, 500); pump(100)
check("se l'editor si restringe la barra resta in alto a destra", find._bar.x() < x1 and find._bar.y() == 12)
check("sta sopra al testo", find._bar.isVisible() and find._bar.geometry().right() < ed.width())
find.close(); pump(50)

# --- Dentro Scrittura (finestra intera) ---------------------------------------------------------------------
repo2 = new_repo("TrovaScrittura")
first = repo2.create_page("Capitolo 1")
second = repo2.create_page("Capitolo 2")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo2.folder, "scrittura", first); pump(300)
s = w._screens["scrittura"]
check("in Scrittura il controllo e la ricerca ci sono", s._editor.spell is not None and s._editor.find is not None)
toolbar = s.findChildren(FormatToolbar)[0]
check("la barra di Scrittura ha «Italiano» e la lente", toolbar._language is not None and toolbar._find is not None)
toolbar._find.click(); pump(100)
check("la ricerca si apre in Scrittura", s._editor.find.is_open)
s._open(second); pump(300)
check("aprendo un'altra pagina la ricerca si chiude", not s._editor.find.is_open)
toolbar._find.click(); pump(100)
s._close_page(); pump(200)
check("tornando all'elenco dei capitoli la ricerca è chiusa", not s._editor.find.is_open)

# --- Negli appunti di una scheda non c'è ----------------------------------------------------------------------
note = NoteEditor(lambda q, n: [], lambda r: None, lambda p: "", lambda parent: [], repo.folder, repo.speller)
check("i riquadri delle schede non hanno la lente", note._editor.find is None and not any(b.toolTip() == "Cerca nella pagina" for b in note.findChildren(QToolButton)))

print(f"\n{sum(ok)}/{len(ok)}")
