"""Passo 11b, editor: onde rosse sotto le parole sbagliate (solo grafiche), menu «Ignora questa volta», pulsante «Italiano»."""
from harness import *
app()
import time
from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent, QTextCharFormat, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QToolButton, QVBoxLayout, QWidget
from gmjournal import spelling, theme
from gmjournal.data.models import ElementInput
from gmjournal.ui.editor.editor import RichEditor
from gmjournal.ui.editor.note_editor import NoteEditor
from gmjournal.ui.editor.spell_ui import DictionaryLoader
from gmjournal.ui.editor.toolbar import FormatToolbar
from gmjournal.ui.link_sources import LinkSources
from gmjournal.ui.widgets.menu import PopupMenu

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

spelling.load_dictionary()
spelling.NAMES_TTL = 0.0
repo = new_repo("OrtografiaUI")
cats = repo.categories("character")
repo.create_element(ElementInput("character", "Aldric", cats[0].id, None, "", ""))
host = QWidget(); host.resize(1100, 700)
sources = LinkSources(host, repo, lambda: None)
ed = RichEditor(link_targets=sources.targets, create_target=sources.create, speller=repo.speller)
bar = FormatToolbar(ed)
column = QVBoxLayout(host); column.setContentsMargins(0, 0, 0, 0); column.setSpacing(0)
column.addWidget(bar); column.addWidget(ed)
host.show(); host.activateWindow(); pump(100)
edited = []
ed.edited.connect(lambda: edited.append(1))

def marks():
    return ed._overlays.get("spell", [])

def marked_words():
    doc = ed.document()
    words = []
    for mark in marks():
        c = mark.cursor
        words.append(doc.toPlainText()[c.selectionStart():c.selectionEnd()])
    return words

def load(content, focus=False):
    ed.set_content(content)
    if focus:
        ed.setFocus()
    pump(300)

def word_point(word, occurrence=0):
    """Il centro della parola `word` nel testo (coordinate dell'area di testo)."""
    text = ed.document().toPlainText()
    index = -1
    for _ in range(occurrence + 1):
        index = text.index(word, index + 1)
    start, end = QTextCursor(ed.document()), QTextCursor(ed.document())
    start.setPosition(index); end.setPosition(index + len(word))
    a, b = ed.cursorRect(start), ed.cursorRect(end)
    return QPoint((a.left() + b.left()) // 2, a.center().y())

def right_click(point):
    ed.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Mouse, point, ed.viewport().mapToGlobal(point))); pump(50)

def menu_texts():
    menus = [m for m in QApplication.topLevelWidgets() if isinstance(m, PopupMenu) and m.isVisible()]
    return [b.text() for b in menus[-1].findChildren(QAbstractButton)] if menus else []

def close_menus():
    for m in QApplication.topLevelWidgets():
        if isinstance(m, PopupMenu) and m.isVisible():
            m.close()
    pump(30)

# --- Le onde ----------------------------------------------------------------------------------------
HTML = ("<p>Mira non si fida, perchè ha già visto un’altro uomo. Aldric e <a href='gm://page/1'>Zorbax</a> parlano.</p>"
        "<p>Un <b>grassetto sbagliatoo</b> e <span class='hl hl-sabbia'>evidenziatoo</span> qui.</p>"
        "<table><tr><th>Voce</th></tr><tr><td>una cellaa sbagliata</td></tr></table><p>Fine.</p>")
plain_before = RichEditor()
plain_before.set_content(HTML)
reference_html = plain_before.content()
load(HTML)
check("le parole sbagliate hanno un'onda (anche in grassetto, evidenziate e nelle celle)",
      marked_words() == ["perchè", "un’altro", "sbagliatoo", "evidenziatoo", "cellaa"])
check("le parole giuste, il nome «Aldric» e il testo di un collegamento non hanno onde",
      "Aldric" not in marked_words() and "Zorbax" not in marked_words() and "Mira" not in marked_words())
fmt = marks()[0].format
check("è un'onda rossa (WaveUnderline, colore del tema)",
      fmt.underlineStyle() == QTextCharFormat.WaveUnderline and fmt.underlineColor().name() == theme.SPELL_ERROR)
check("il testo salvato è identico a quello senza controllo (nessuna onda salvata)", ed.content() == reference_html)
check("nessuna riga di stile con onde nel testo salvato", "wave" not in ed.content().lower() and theme.SPELL_ERROR not in ed.content())
check("il testo non risulta modificato e non c'è nulla da annullare", not ed.document().isModified() and not ed.document().isUndoAvailable())
check("disegnare le onde non segnala nessuna modifica (niente salvataggi inutili)", edited == [])
ed.grab().save("/tmp/claude-0/shots/spell_ui.png")

# --- Scorrere e ricontrollare non cambia il testo ---------------------------------------------------
ed.verticalScrollBar().setValue(5); pump(300)
ed.verticalScrollBar().setValue(0); pump(300)
ed.spell.refresh(); pump()
check("scorrere e ricontrollare non segnala modifiche", edited == [])

# --- Accendere e spegnere ---------------------------------------------------------------------------
ed.spell.set_enabled(False); pump(50)
check("spento: nessuna onda", marks() == [])
check("spento: il menu non propone nulla sulle parole", ed.spell.error_at(word_point("perchè")) is None)
ed.spell.set_enabled(True); pump(50)
check("riacceso: le onde tornano", len(marks()) == 5)

# --- Mentre si scrive -------------------------------------------------------------------------------
load("<p>Ciao </p>", focus=True)
c = ed.textCursor(); c.movePosition(QTextCursor.End); ed.setTextCursor(c)
QTest.keyClicks(ed, "qwxyz"); pump(400)
check("la parola che si sta scrivendo non è sottolineata", marked_words() == [])
QTest.keyClick(ed, Qt.Key_Space); pump(400)
check("finita la parola (spazio) compare l'onda", marked_words() == ["qwxyz"])
QTest.keyClick(ed, Qt.Key_Backspace); pump(400)
check("tornando dentro la parola l'onda sparisce di nuovo", marked_words() == [])
QTest.keyClicks(ed, " ");  pump(400)
ed.clearFocus(); pump(400)
check("senza cursore nel testo (focus altrove) la parola è sottolineata", marked_words() == ["qwxyz"])
ed.setFocus(); pump(50)
ed.document().undo(); ed.document().undo(); ed.document().undo(); pump(300)
check("l'annulla toglie ciò che si è scritto: le onde non entrano nei passaggi", ed.document().toPlainText().strip() == "Ciao" and marked_words() == [])

# --- Le onde seguono il testo -----------------------------------------------------------------------
load("<p>Ciao qwxyz fine</p>")
c = QTextCursor(ed.document()); c.setPosition(0); c.insertText("Prima di tutto ")      # il testo prima della parola si sposta
check("inserendo testo prima, l'onda resta sulla parola (si sposta con lei)", marked_words() == ["qwxyz"])
pump(300)
check("dopo il ricontrollo è ancora una sola onda, sulla parola giusta", marked_words() == ["qwxyz"])

# --- Menu: ignora -----------------------------------------------------------------------------------
load("<p>Questa è una frasee con parolaccia e basta. Rimane frasee finale.</p>")
check("due onde con la stessa parola sbagliata", marked_words() == ["frasee", "frasee"])
right_click(word_point("frasee"))
texts = menu_texts()
check("clic destro sulla parola sbagliata: «Ignora questa volta» in cima", texts[:1] == ["Ignora questa volta"])
check("niente suggerimenti e niente «Aggiungi al dizionario»",
      not any("Forse" in t or "dizionario" in t.lower() for t in texts))
check("le voci di prima restano (Seleziona tutto…)", "Seleziona tutto" in texts)
close_menus()
right_click(word_point("Questa"))
check("clic destro su una parola giusta: il menu non cambia", "Ignora questa volta" not in menu_texts())
close_menus()
right_click(QPoint(word_point("frasee").x(), word_point("frasee").y() + 200))
check("clic destro nel vuoto sotto il testo: nessuna voce di ortografia", "Ignora questa volta" not in menu_texts())
close_menus()
right_click(word_point("frasee"))
buttons = {b.text(): b for m in QApplication.topLevelWidgets() if isinstance(m, PopupMenu) and m.isVisible() for b in m.findChildren(QAbstractButton)}
QTest.mouseClick(buttons["Ignora questa volta"], Qt.LeftButton); pump(300)
check("«Ignora questa volta»: spariscono le onde di quella parola, in tutto il testo", "frasee" not in marked_words())
check("«Ignora» non tocca il testo salvato", "frasee" in ed.content())
check("«Ignora» è valido anche in un altro editor", not RichEditor(speller=repo.speller).spell.error_at(QPoint(0, 0)))
spelling._Dictionary.ignored.clear(); spelling._Dictionary.ignored_version += 1

# --- Pulsante «Italiano» ----------------------------------------------------------------------------
language = bar._language
check("c'è il pulsante «Italiano» con icona, acceso all'apertura",
      language is not None and language.text() == "Italiano" and not language.icon().isNull() and language.isChecked())
check("sta a destra, dopo il pulsante Box", language.mapTo(bar, QPoint(0, 0)).x() > bar._box.mapTo(bar, QPoint(0, 0)).x())
load("<p>Ciao qwxyz fine</p>", focus=True)
QTest.mouseClick(language, Qt.LeftButton); pump(100)
check("un clic lo spegne: pulsante spento e onde tolte", not language.isChecked() and marks() == [] and not ed.spell.enabled)
QTest.mouseClick(language, Qt.LeftButton); pump(100)
check("un secondo clic lo riaccende", language.isChecked() and marked_words() == ["qwxyz"])
check("il clic sul pulsante non toglie il cursore al testo", ed.hasFocus())

# --- Dizionario non disponibile / ancora in caricamento ---------------------------------------------
saved = spelling._Dictionary.hunspell
spelling._Dictionary.hunspell, spelling._Dictionary.missing = None, True
ed.spell.changed.emit(); ed.spell.schedule(delay=0); pump(100)
check("dizionario mancante: pulsante spento con spiegazione, nessuna onda",
      not language.isEnabled() and "non è disponibile" in language.toolTip() and marks() == [])
spelling._Dictionary.hunspell, spelling._Dictionary.missing = None, False
ed.spell.changed.emit(); ed.spell.schedule(delay=0); pump(100)
check("dizionario in caricamento: nessuna onda, pulsante ancora attivo", marks() == [] and language.isEnabled())
spelling._Dictionary.hunspell = saved
DictionaryLoader.instance().ready.emit(); pump(100)
check("a caricamento finito le onde compaiono da sole", marked_words() == ["qwxyz"])

# --- Anche negli appunti delle schede ---------------------------------------------------------------
note = NoteEditor(sources.targets, sources.create, lambda path: "", lambda parent: [], repo.folder, repo.speller)
note.set_content("<p>Parolaccia qwxyz</p>"); note.resize(700, 300); note.show(); pump(400)
check("i riquadri di testo delle schede hanno il controllo e il pulsante «Italiano»",
      note._editor.spell is not None and len(note._editor._overlays.get("spell", [])) >= 1
      and any(b.text() == "Italiano" for b in note.findChildren(QToolButton)))
check("ma non «Cerca nella pagina» (è solo di Scrittura)", note._editor.find is None)

# --- Pagina lunga -----------------------------------------------------------------------------------
sentence = ("<p>La sala della Locanda era più silenziosa del solito quando la porta si aprì, perchè un viandante entrò nell'ombra "
            "e nessuno parlava ad alta voce, <b>neanche</b> il vecchio Aldric che beveva sempre lo stesso bicchiere di vinoo.</p>")
big = sentence * 520
print(f"  (pagina di {len(big) // 1024} KB)")
plain = RichEditor(); plain.resize(900, 600); plain.show(); pump(50)
start = time.perf_counter(); plain.set_content(big); without = time.perf_counter() - start
ed.resize(900, 600)
start = time.perf_counter(); ed.set_content(big); with_check = time.perf_counter() - start
print(f"  (apertura senza controllo {without:.2f} s, con controllo {with_check:.2f} s)")
check("l'apertura di una pagina lunga non rallenta (differenza sotto 0,15 s)", with_check - without < 0.15)
pump(400)
check("dopo l'apertura le onde ci sono solo sul testo in vista, non su tutta la pagina", 0 < len(marks()) < 300)
start = time.perf_counter(); ed.spell.refresh(); one = time.perf_counter() - start
print(f"  (ricontrollo del testo in vista {one * 1000:.0f} ms, {len(marks())} onde)")
check("ricontrollare il testo in vista richiede meno di 50 ms", one < 0.05)
ed.verticalScrollBar().setValue(ed.verticalScrollBar().maximum() // 2); pump(400)
check("scorrendo a metà pagina compaiono le onde del nuovo testo", len(marks()) > 0)
QTest.keyClicks(ed, "x"); start = time.perf_counter()
for _ in range(30):
    QTest.keyClicks(ed, "a")
typing = (time.perf_counter() - start) / 30
print(f"  (scrivere una lettera in una pagina lunga: {typing * 1000:.1f} ms)")
check("scrivere in una pagina lunga resta fluido (meno di 30 ms a lettera)", typing < 0.03)

print(f"\n{sum(ok)}/{len(ok)}")
