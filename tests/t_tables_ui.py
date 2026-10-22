"""Passo 11a, editor: inserire e modificare tabelle, evidenziatore, barra degli strumenti, barra sopra la tabella e «+»."""
from harness import *
app()
import random
import time
from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QColor, QTextCursor, QTextDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QFrame, QToolButton, QVBoxLayout, QWidget
from gmjournal.data.models import ElementInput
from gmjournal.ui.editor import commands, markup, styles
from gmjournal.ui.editor.editor import RichEditor
from gmjournal.ui.editor.note_editor import NoteEditor
from gmjournal.ui.editor.table_ui import TableSizePopup, table_grid
from gmjournal.ui.editor.toolbar import FormatToolbar
from gmjournal.ui.link_sources import LinkSources
from gmjournal.ui.widgets.color_swatch import ColorSwatch

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("TabelleUI")
cats = repo.categories("character")
mira = repo.create_element(ElementInput("character", "Mira Vesperi", cats[0].id, None, "", ""))
host = QWidget(); host.resize(1100, 760)
sources = LinkSources(host, repo, lambda: None)
ed = RichEditor(link_targets=sources.targets, create_target=sources.create)
bar = FormatToolbar(ed)
column = QVBoxLayout(host); column.setContentsMargins(0, 0, 0, 0); column.setSpacing(0)
column.addWidget(bar); column.addWidget(ed)
host.show(); host.activateWindow(); pump(100)

def load(content, at_end=True):
    ed.set_content(content); ed.setFocus()
    if at_end:
        c = ed.textCursor(); c.movePosition(QTextCursor.End); ed.setTextCursor(c)
    pump()

def tables():
    return [f for f in ed.document().rootFrame().childFrames()]

def cell_cursor(table, row, column, end=True):
    cell = table.cellAt(row, column)
    return cell.lastCursorPosition() if end else cell.firstCursorPosition()

def click_cell(table, row, column):
    point = ed.cursorRect(cell_cursor(table, row, column)).center()
    QTest.mouseClick(ed.viewport(), Qt.LeftButton, Qt.NoModifier, point); pump()

def popup():
    return QApplication.activePopupWidget()

# --- Inserire dalla griglia -------------------------------------------------------------------------
load("<p>Ciao</p>")
QTest.keyClick(ed, Qt.Key_Return); pump()
QTest.mouseClick(bar._table, Qt.LeftButton); pump(50)
grid_popup = popup()
check("il pulsante tabella apre la griglia", isinstance(grid_popup, TableSizePopup) and grid_popup.isVisible())
grid = grid_popup._grid
QTest.mouseMove(grid, QPoint(4 * 25 - 12, 2 * 25 - 12)); pump()
check("passando il mouse la misura cambia («4 colonne × 2 righe»)", grid_popup._label.text() == "4 colonne × 2 righe")
check("la griglia è 8 × 6 e sta dentro il riquadro", grid.width() == 8 * 25 - 3 and grid.height() == 6 * 25 - 3
      and grid_popup.rect().contains(grid.geometry()))
QTest.mouseClick(grid, Qt.LeftButton, Qt.NoModifier, QPoint(4 * 25 - 12, 2 * 25 - 12)); pump(50)
check("il clic inserisce la tabella e chiude la griglia", len(tables()) == 1 and tables()[0].rows() == 2
      and tables()[0].columns() == 4 and popup() is None)
check("la riga vuota diventa la tabella", ed.content() == "<p>Ciao</p><table><tr>" + "<th></th>" * 4 + "</tr><tr>" + "<td></td>" * 4 + "</tr></table>")
check("il cursore è nella prima cella", commands.current_cell(ed)[1:] == (0, 0))
check("nella tabella: tabella attiva, niente elenchi, dimensioni, immagini, box, tipo di paragrafo",
      bar._table.isChecked() and not bar._table.isEnabled() and not bar._bullets.isEnabled() and not bar._sizes.isEnabled()
      and not bar._image.isEnabled() and not bar._box.isEnabled() and not bar._block.isEnabled() and bar._bold.isEnabled())
ed.undo(); pump()
check("un solo «Annulla» toglie la tabella", ed.content() == "<p>Ciao</p>" and not tables())

load("<h2>Titolo</h2>", at_end=False)
c = ed.textCursor(); c.setPosition(3); ed.setTextCursor(c)
commands.insert_table(ed, 1, 2); pump()
check("in mezzo a un paragrafo lo divide: la seconda parte resta un titolo",
      ed.content() == "<h2>Tit</h2><table><tr><th></th><th></th></tr></table><h2>olo</h2>")
load('<div class="box voice"><p>Nel box</p></div>')
check("in un box il pulsante tabella è spento", not bar._table.isEnabled())
commands.insert_table(ed, 2, 2); pump()
check("…e il comando non fa nulla", not tables())
load("")
commands.insert_table(ed, 2, 2); pump()
check("tabella in una pagina vuota: si salva solo la tabella", ed.content() == "<table><tr><th></th><th></th></tr><tr><td></td><td></td></tr></table>")
commands.insert_table(ed, 2, 2); pump()
check("dentro una tabella non se ne inserisce un'altra", len(tables()) == 1)

# --- Scrivere: Tab, Maiusc+Tab, Invio ------------------------------------------------------------------
load("<p>Sopra</p>")
commands.insert_table(ed, 2, 2); pump()
for text in ("d6", "Voce", "1-2", "Mira"):
    QTest.keyClicks(ed, text); QTest.keyClick(ed, Qt.Key_Tab)
pump()
check("Tab porta alla cella successiva", ed.content().startswith("<p>Sopra</p><table><tr><th>d6</th><th>Voce</th></tr><tr><td>1-2</td><td>Mira</td></tr>"))
check("Tab dopo l'ultima cella aggiunge una riga (e ci porta il cursore)", tables()[0].rows() == 3 and commands.current_cell(ed)[1:] == (2, 0))
ed.undo(); pump()
check("…e un solo «Annulla» toglie la riga", tables()[0].rows() == 2 and "Mira" in ed.content())
click_cell(tables()[0], 1, 1)
QTest.keyClick(ed, Qt.Key_Backtab); pump()
check("Maiusc+Tab torna alla cella precedente", commands.current_cell(ed)[1:] == (1, 0))
QTest.keyClick(ed, Qt.Key_Return); QTest.keyClicks(ed, "seconda riga"); pump()
check("Invio in una cella va a capo nella stessa cella", "<td>1-2<br>seconda riga</td>" in ed.content() and tables()[0].rows() == 2)
QTest.keyClicks(ed, "- "); pump()
check("«- » in una cella non crea un elenco", "seconda riga- </td>" in ed.content())
for command, args in ((commands.set_heading, (2,)), (commands.toggle_list, ("ul",)), (commands.set_box, ("voice",))):
    command(ed, *args)
pump()
check("titolo, elenco e box non entrano nelle celle", "<h2>" not in ed.content() and "<ul>" not in ed.content() and "box" not in ed.content())
commands.insert_image(ed, "immagini/x.png", 100, 50); pump()
check("…e nemmeno le immagini", "<img" not in ed.content())

# --- Righe e colonne -------------------------------------------------------------------------------------
load("<p>A</p><table><tr><th>h1</th><th>h2</th></tr><tr><td>a</td><td>b</td></tr></table><h2>B</h2>")
table = tables()[0]
click_cell(table, 0, 0)
commands.add_row(ed, "above"); pump()
check("«Riga sopra» all'intestazione: la riga nuova è l'intestazione", ed.content().startswith("<p>A</p><table><tr><th></th><th></th></tr><tr><td>h1</td><td>h2</td></tr>"))
old_head = cell_cursor(tables()[0], 1, 0).block()
fmt = styles.fragments(old_head)[0][2]
check("…e la vecchia intestazione prende l'aspetto delle celle (senza diventare grassetto)", fmt.font().pixelSize() == 14
      and "<td>h1</td><td>h2</td>" in ed.content())
check("…il cursore è nella riga nuova", commands.current_cell(ed)[1:] == (0, 0))
commands.add_row(ed, "below"); commands.add_column(ed, "right"); pump()
check("«Riga sotto» e «Colonna a destra»", tables()[0].rows() == 4 and tables()[0].columns() == 3 and commands.current_cell(ed)[1:] == (1, 1))
ed.undo(); pump()
check("ogni operazione è un solo «Annulla»", tables()[0].rows() == 4 and tables()[0].columns() == 2)

# --- Barra sopra la tabella e «+» (clic veri) -----------------------------------------------------------
load("<p>" + "Testo prima. " * 40 + "</p><table><tr><th>h</th><th>k</th></tr><tr><td>a</td><td>b</td></tr></table><p>Dopo</p>")
click_cell(tables()[0], 1, 0); pump(50)
controls = ed._table_controls
grid_rect = table_grid(ed.document(), tables()[0]).rect()
offset = ed.viewport().geometry().topLeft()
table_rect = grid_rect.translated(offset.x(), offset.y() - ed.verticalScrollBar().value())
check("con il cursore nella tabella compaiono la barra e i due «+»",
      controls.bar.isVisible() and controls.add_column.isVisible() and controls.add_row.isVisible())
b = controls.bar.geometry()
check("la barra sta sopra la tabella, allineata a sinistra, dentro l'editor", b.height() > 20 and b.bottom() <= table_rect.top()
      and abs(b.left() - table_rect.left()) <= 1 and ed.rect().contains(b))
bar_buttons = controls.bar.findChildren(QToolButton)
check("la barra ha le sei voci (le tre di aggiunta, poi le tre di eliminazione), intere e dentro la barra",
      [w.text() for w in bar_buttons] == ["Riga sopra", "Riga sotto", "Colonna a destra", "Elimina riga", "Elimina colonna", "Elimina tabella"]
      and all(w.width() >= w.sizeHint().width() and controls.bar.rect().contains(w.geometry()) for w in bar_buttons))
pc, pr = controls.add_column.geometry(), controls.add_row.geometry()
check("«+» colonna a destra della tabella, «+» riga sotto", pc.left() > table_rect.right() and table_rect.top() <= pc.center().y() <= table_rect.bottom()
      and pr.top() > table_rect.bottom() and abs(pr.center().x() - table_rect.center().x()) <= 2 and ed.rect().contains(pc) and ed.rect().contains(pr))
QTest.mouseClick(controls.add_column, Qt.LeftButton); pump()
check("il «+» di destra aggiunge una colonna in fondo", tables()[0].columns() == 3 and commands.current_cell(ed)[1:] == (1, 2))
QTest.mouseClick(controls.add_row, Qt.LeftButton); pump()
check("il «+» in basso aggiunge una riga in fondo", tables()[0].rows() == 3 and commands.current_cell(ed)[1:] == (2, 0))
buttons = {w.text(): w for w in bar_buttons}
QTest.mouseClick(buttons["Riga sopra"], Qt.LeftButton); pump()
check("«Riga sopra» dalla barra", tables()[0].rows() == 4 and commands.current_cell(ed)[1:] == (2, 0) and ed.hasFocus())
QTest.mouseClick(buttons["Elimina riga"], Qt.LeftButton); pump()
check("«Elimina riga» dalla barra", tables()[0].rows() == 3 and commands.current_cell(ed)[1:] == (2, 0) and ed.hasFocus())
QTest.mouseClick(buttons["Elimina colonna"], Qt.LeftButton); pump()
check("«Elimina colonna» dalla barra", tables()[0].columns() == 2 and tables()[0].rows() == 3 and ed.hasFocus())
before = "<p>" + "Testo prima. " * 40 + "</p>"
QTest.mouseClick(buttons["Elimina tabella"], Qt.LeftButton); pump()
check("«Elimina tabella»: un clic, il testo prima e dopo resta separato", not tables() and ed.content() == before + "<p>Dopo</p>")
check("…e la barra sparisce", not controls.bar.isVisible() and not controls.add_column.isVisible())
ed.undo(); pump()
check("…Ctrl+Z la riporta com'era", len(tables()) == 1 and tables()[0].rows() == 3 and tables()[0].columns() == 2)
c = ed.textCursor(); c.movePosition(QTextCursor.End); ed.setTextCursor(c); pump()
check("uscendo dalla tabella barra e «+» spariscono", not controls.bar.isVisible() and not controls.add_row.isVisible())
load("<h3>Sopra</h3><table><tr><th>x</th></tr></table><h2>Sotto</h2>")
click_cell(tables()[0], 0, 0); commands.delete_table(ed); pump()
check("eliminando una tabella fra due titoli restano due titoli", ed.content() == "<h3>Sopra</h3><h2>Sotto</h2>")
load("<table><tr><th>x</th></tr></table><h2>Sotto</h2>")
click_cell(tables()[0], 0, 0); commands.delete_table(ed); pump()
check("tabella in cima: dopo l'eliminazione resta solo il titolo", ed.content() == "<h2>Sotto</h2>")

# --- Eliminare righe e colonne ---------------------------------------------------------------------------------
def head_look(table):
    """(grandezza, maiuscolo) del testo della prima cella: l'intestazione è 12 px maiuscolo, le celle 14 px."""
    fmt = styles.fragments(cell_cursor(table, 0, 0).block())[0][2]
    return fmt.font().pixelSize(), fmt.font().capitalization().name == "AllUppercase"

table3 = ("<table><tr><th>h1</th><th>h2</th><th>h3</th></tr><tr><td>a1</td><td>a2</td><td>a3</td></tr>"
          "<tr><td>b1</td><td>b2</td><td>b3</td></tr></table>")
load("<p>A</p>" + table3 + "<h2>B</h2>")
click_cell(tables()[0], 1, 1)
commands.delete_row(ed); pump()
check("«Elimina riga» toglie la riga del cursore, che passa alla riga che prende il suo posto",
      ed.content() == "<p>A</p><table><tr><th>h1</th><th>h2</th><th>h3</th></tr><tr><td>b1</td><td>b2</td><td>b3</td></tr></table><h2>B</h2>"
      and commands.current_cell(ed)[1:] == (1, 1))
ed.undo(); pump()
check("…un solo «Annulla» la riporta", ed.content() == "<p>A</p>" + table3 + "<h2>B</h2>")
click_cell(tables()[0], 2, 2)
commands.delete_row(ed); pump()
check("…eliminando l'ultima riga il cursore sale alla precedente", tables()[0].rows() == 2 and commands.current_cell(ed)[1:] == (1, 2)
      and "b1" not in ed.content())
commands.delete_column(ed); pump()
check("«Elimina colonna» toglie la colonna del cursore (qui l'ultima) e il cursore resta nella nuova ultima",
      ed.content() == "<p>A</p><table><tr><th>h1</th><th>h2</th></tr><tr><td>a1</td><td>a2</td></tr></table><h2>B</h2>"
      and commands.current_cell(ed)[1:] == (1, 1))
ed.undo(); pump()
check("…un solo «Annulla» la riporta", tables()[0].columns() == 3 and "<td>a3</td>" in ed.content())
click_cell(tables()[0], 0, 0)
commands.delete_column(ed); pump()
check("togliendo la prima colonna restano le altre, nell'ordine", ed.content() == "<p>A</p><table><tr><th>h2</th><th>h3</th></tr><tr><td>a2</td><td>a3</td></tr></table><h2>B</h2>"
      and commands.current_cell(ed)[1:] == (0, 0))
load("<p>A</p>" + table3)
click_cell(tables()[0], 0, 1)
commands.delete_row(ed); pump()
check("togliendo l'intestazione lo diventa la riga sotto (nel testo e nell'aspetto)",
      ed.content() == "<p>A</p><table><tr><th>a1</th><th>a2</th><th>a3</th></tr><tr><td>b1</td><td>b2</td><td>b3</td></tr></table>"
      and head_look(tables()[0]) == (12, True) and commands.current_cell(ed)[1:] == (0, 1))
load("<table><tr><th>x</th></tr><tr><td>y</td></tr><tr><td>z</td></tr></table>")
click_cell(tables()[0], 0, 0)
commands.delete_row(ed); pump()
check("…anche in una tabella di una sola colonna", ed.content() == "<table><tr><th>y</th></tr><tr><td>z</td></tr></table>" and head_look(tables()[0]) == (12, True))
load('<table><tr><th>x</th><th>y</th></tr><tr><td>1</td><td>2</td></tr></table>')
click_cell(tables()[0], 1, 1)
commands.delete_row(ed); commands.delete_row(ed); pump()
check("l'ultima riga non si toglie (resta l'intestazione, il cursore resta dov'era)",
      ed.content() == "<table><tr><th>x</th><th>y</th></tr></table>" and commands.current_cell(ed)[1:] == (0, 1))
check("…e «Elimina riga» è spento, «Elimina colonna» no", not buttons["Elimina riga"].isEnabled() and buttons["Elimina colonna"].isEnabled()
      and buttons["Riga sopra"].isEnabled())
QTest.mouseClick(buttons["Elimina riga"], Qt.LeftButton); pump()
check("…e un clic su un pulsante spento non fa nulla (il cursore resta nel testo, la barra resta)",
      tables()[0].rows() == 1 and ed.hasFocus() and controls.bar.isVisible())
divider = [w for w in controls.bar.findChildren(QFrame) if w.objectName() == "ToolbarDivider"][0]
QTest.mouseClick(divider, Qt.LeftButton); pump()
check("…e nemmeno un clic sul separatore", ed.hasFocus() and controls.bar.isVisible())
commands.delete_column(ed); commands.delete_column(ed); pump()
check("l'ultima colonna non si toglie; con una cella sola sono spenti «Elimina riga» ed «Elimina colonna»",
      ed.content() == "<table><tr><th>x</th></tr></table>" and not buttons["Elimina riga"].isEnabled() and not buttons["Elimina colonna"].isEnabled()
      and buttons["Elimina tabella"].isEnabled())
commands.add_row(ed, "end"); pump()
check("…aggiungendo una riga «Elimina riga» si riaccende", buttons["Elimina riga"].isEnabled() and not buttons["Elimina colonna"].isEnabled())
def brightest(button):
    image = button.grab().toImage()
    return max(max(QColor(image.pixel(x, y)).getRgb()[:3]) for x in range(image.width()) for y in range(image.height()))
check("un pulsante spento ha testo e icona grigi scuri (quello acceso è rosa chiaro)",
      brightest(buttons["Elimina colonna"]) < 130 and brightest(buttons["Elimina tabella"]) > 200)

# --- Collegamenti con @ nelle celle ------------------------------------------------------------------------
load("<table><tr><th>Chi</th></tr><tr><td></td></tr></table>")
click_cell(tables()[0], 1, 0)
QTest.keyClicks(ed, "@Mir"); pump(50)
check("«@» in una cella apre l'elenco dei collegamenti", ed._mention.active)
QTest.keyClick(ed, Qt.Key_Return); pump()
check("…e il link finisce nella cella", f'<td><a href="gmj://character/{mira}">Mira Vesperi</a></td>' in ed.content())

# --- Copia e incolla -------------------------------------------------------------------------------------
load("<p>A</p><table><tr><th>h1</th><th>h2</th></tr><tr><td><b>uno</b></td><td>due</td></tr></table><p>B</p>")
t = tables()[0]
c = QTextCursor(ed.document()); c.setPosition(t.cellAt(0, 0).firstPosition()); c.setPosition(t.cellAt(1, 1).lastPosition(), QTextCursor.KeepAnchor)
ed.setTextCursor(c)
data = ed.createMimeDataFromSelection()
copied = bytes(data.data("application/x-gmjournal-text")).decode()
check("copiare delle celle copia una tabella", copied.startswith("<table>") and "<b>uno</b>" in copied)
other = RichEditor(); other.set_content("<p>Testo</p>")
oc = other.textCursor(); oc.movePosition(QTextCursor.End); other.setTextCursor(oc)
other.insertFromMimeData(data)
check("incollata fuori da una tabella, la tabella arriva intera", "<table><tr><th>h1</th><th>h2</th></tr><tr><td><b>uno</b></td><td>due</td></tr></table>" in other.content())
c = QTextCursor(ed.document()); c.setPosition(tables()[0].cellAt(1, 1).lastPosition()); ed.setTextCursor(c)
ed.insertFromMimeData(data); pump()
check("incollata in una cella: niente tabella nella tabella, il testo va a capo nella cella",
      len(tables()) == 1 and not tables()[0].cellAt(1, 1).firstCursorPosition().currentFrame().childFrames()
      and "<td>dueh1<br>h2<br><b>uno</b><br>due</td>" in ed.content())
plain = QMimeData(); plain.setText("riga 1\nriga 2")
ed.insertFromMimeData(plain); pump()
check("testo semplice con «a capo» incollato in una cella resta nella cella", "<br>due</td>" not in ed.content() and "riga 1<br>riga 2</td>" in ed.content())
heading = QMimeData()
heading.setData("application/x-gmjournal-text", "<h1>Titolo</h1><ul><li>voce</li></ul>".encode())
ed.insertFromMimeData(heading); pump()
check("titoli ed elenchi incollati in una cella diventano testo", "<h1>" not in ed.content() and "Titolo<br>voce</td>" in ed.content())

# --- Evidenziatore -----------------------------------------------------------------------------------------
load("<p>La sala era silenziosa.</p>", at_end=False)
c = ed.textCursor(); c.setPosition(3); c.setPosition(7, QTextCursor.KeepAnchor); ed.setTextCursor(c)
commands.toggle_highlight(ed, "verde"); pump()
check("evidenziare la selezione", ed.content() == '<p>La <span class="hl hl-verde">sala</span> era silenziosa.</p>')
commands.toggle_highlight(ed, "verde"); pump()
check("lo stesso colore sul testo evidenziato lo toglie", ed.content() == "<p>La sala era silenziosa.</p>")
commands.toggle_highlight(ed, "verde"); commands.toggle_highlight(ed, "rosa"); pump()
check("un altro colore lo sostituisce", ed.content() == '<p>La <span class="hl hl-rosa">sala</span> era silenziosa.</p>')
commands.toggle_style(ed, "bold"); pump()
check("convive col grassetto", ed.content() == '<p>La <span class="hl hl-rosa"><b>sala</b></span> era silenziosa.</p>')
ed.set_content(ed.content()); pump()
check("…e sopravvive al salvataggio", ed.content() == '<p>La <span class="hl hl-rosa"><b>sala</b></span> era silenziosa.</p>')
c = ed.textCursor(); c.setPosition(5); ed.setTextCursor(c); pump()
check("con il cursore nel testo evidenziato il pulsante è acceso", bar._highlight.isChecked())
c = ed.textCursor(); c.setPosition(3); c.setPosition(7, QTextCursor.KeepAnchor); ed.setTextCursor(c)
commands.insert_link(ed, f"gmj://character/{mira}", "sala"); pump()
check("…e col link", ed.content() == f'<p>La <span class="hl hl-rosa"><a href="gmj://character/{mira}">sala</a></span> era silenziosa.</p>')

load("<p>Uno due tre</p>", at_end=False)
c = ed.textCursor(); c.setPosition(0); c.setPosition(3, QTextCursor.KeepAnchor); ed.setTextCursor(c)
FormatToolbar._last_highlight = "sabbia"
QTest.mouseClick(bar._highlight, Qt.LeftButton); pump()
check("il pulsante principale usa l'ultimo colore (sabbia)", ed.content() == '<p><span class="hl hl-sabbia">Uno</span> due tre</p>')
c = ed.textCursor(); c.setPosition(4); c.setPosition(7, QTextCursor.KeepAnchor); ed.setTextCursor(c)
QTest.mouseClick(bar._highlight_menu, Qt.LeftButton); pump(50)
menu = popup()
swatches = menu.findChildren(ColorSwatch)
check("la freccia apre i 6 colori, con quello in uso segnato", len(swatches) == 6 and swatches[0].isChecked()
      and [s.toolTip() for s in swatches] == ["Sabbia", "Verde", "Azzurro", "Rosa", "Viola", "Ambra"])
check("…e i pulsanti restano evidenziati mentre è aperto", bar._highlight_menu.isChecked())
QTest.mouseClick(swatches[4], Qt.LeftButton); pump(50)
check("scegliere «Viola» evidenzia e lo ricorda come ultimo colore", popup() is None and FormatToolbar._last_highlight == "viola"
      and ed.content() == '<p><span class="hl hl-sabbia">Uno</span> <span class="hl hl-viola">due</span> tre</p>')
other_bar = FormatToolbar(RichEditor())
check("l'ultimo colore vale anche per gli altri editor (finché il programma è aperto)", other_bar._highlight._color() == "viola")
c = ed.textCursor(); c.setPosition(0); c.setPosition(11, QTextCursor.KeepAnchor); ed.setTextCursor(c)
QTest.mouseClick(bar._highlight_menu, Qt.LeftButton); pump(50)
remove = [w for w in popup().findChildren(QAbstractButton) if w.text() == "Togli l'evidenziatore"]
QTest.mouseClick(remove[0], Qt.LeftButton); pump(50)
check("«Togli l'evidenziatore» toglie tutti i colori della selezione", ed.content() == "<p>Uno due tre</p>")
check("…e la freccia torna normale", not bar._highlight_menu.isChecked())
load("<p>Prima </p>")
commands.toggle_highlight(ed, "azzurro"); QTest.keyClicks(ed, "nuovo"); pump()
check("senza selezione: si scrive evidenziato", ed.content() == '<p>Prima <span class="hl hl-azzurro">nuovo</span></p>')
load("<table><tr><th>h</th></tr><tr><td>cella</td></tr></table>")
c = ed.textCursor(); c.setPosition(tables()[0].cellAt(1, 0).firstPosition()); c.setPosition(tables()[0].cellAt(1, 0).lastPosition(), QTextCursor.KeepAnchor); ed.setTextCursor(c)
commands.toggle_highlight(ed, "ambra"); pump()
check("evidenziatore nelle celle", '<td><span class="hl hl-ambra">cella</span></td>' in ed.content())

# --- Riquadro di una scheda (Storia, Appunti): stessi strumenti, «+» dentro il riquadro --------------------
note = NoteEditor(sources.targets, sources.create, lambda path: "", lambda parent: [], repo.folder, repo.speller)
note.resize(520, 360); note.show(); note.activateWindow(); pump(50)
note.set_content("<p>Storia</p><table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>")
inner = note._editor
inner.setFocus(); inner.setTextCursor(inner.document().rootFrame().childFrames()[0].cellAt(1, 0).lastCursorPosition()); pump(50)
nc = inner._table_controls
check("in un riquadro stretto barra e «+» restano dentro (la barra si accorcia e scorre di lato)", nc.bar.isVisible()
      and inner.rect().contains(nc.bar.geometry()) and nc.bar.width() < nc.bar.sizeHint().width() and inner.rect().contains(nc.add_column.geometry()))
note.hide()

# --- Prestazioni: pagina da 215 KB con 20 tabelle ------------------------------------------------------------
paragraph = "<p>" + "La sala della locanda era più silenziosa del solito quando la porta si aprì. " * 6 + "</p>"
table = "<table><tr><th>d6</th><th>Voce</th><th>Vera?</th></tr>" + "<tr><td>1–2</td><td>Mira nasconde una lettera sotto il bancone, e nessuno lo sa.</td><td>Sì</td></tr>" * 8 + "</table>"
plain_page = paragraph * (215_000 // len(paragraph))
tables_page = (paragraph * 20 + table) * 20
tables_page += paragraph * max(0, (215_000 - len(tables_page)) // len(paragraph))
def open_time(content):
    best = 9.0
    for _ in range(3):
        start = time.perf_counter(); ed.set_content(content); pump(); best = min(best, time.perf_counter() - start)
    return best
t_plain, t_tables = open_time(plain_page), open_time(tables_page)
print(f"  apertura: pagina da {len(plain_page) // 1000} KB {t_plain:.2f} s · con 20 tabelle ({len(tables_page) // 1000} KB) {t_tables:.2f} s")
check("una pagina da 215 KB con 20 tabelle si apre in tempi simili", t_tables < max(0.6, 1.6 * t_plain))
check("…e si risalva identica", ed.content() == tables_page)

# --- Sequenze casuali di operazioni: nessun errore, testo sempre coerente -----------------------------------
rng = random.Random(7)
def coherent():
    doc = ed.document()
    for frame in doc.rootFrame().childFrames():
        if frame.childFrames():
            return False
    block = doc.firstBlock()
    while block.isValid():
        if styles.table_of(block) is not None and (block.textList() is not None or styles.heading_of(block) or styles.box_of(block)[0]):
            return False
        block = block.next()
    saved = ed.content()
    scratch = QTextDocument(); markup.fill_document(scratch, saved)
    return markup.export_html(scratch) == saved

def random_cursor(select):
    size = ed.document().characterCount() - 1
    c = ed.textCursor(); c.setPosition(rng.randint(0, size))
    if select:
        c.setPosition(rng.randint(0, size), QTextCursor.KeepAnchor)
    ed.setTextCursor(c)

operations = [
    lambda: QTest.keyClicks(ed, rng.choice(["ab", "Mira ", "x"])),
    lambda: QTest.keyClick(ed, Qt.Key_Tab), lambda: QTest.keyClick(ed, Qt.Key_Backtab),
    lambda: QTest.keyClick(ed, Qt.Key_Return), lambda: QTest.keyClick(ed, Qt.Key_Backspace), lambda: QTest.keyClick(ed, Qt.Key_Delete),
    lambda: commands.insert_table(ed, rng.randint(1, 3), rng.randint(1, 3)),
    lambda: commands.add_row(ed, rng.choice(["above", "below", "end"])), lambda: commands.add_column(ed, rng.choice(["right", "end"])),
    lambda: commands.delete_table(ed), lambda: commands.delete_row(ed), lambda: commands.delete_column(ed),
    lambda: commands.toggle_highlight(ed, rng.choice(styles.HIGHLIGHTS + ("",))),
    lambda: commands.toggle_style(ed, "bold"), lambda: commands.set_heading(ed, rng.randint(0, 2)),
    lambda: commands.toggle_list(ed, "ul"), lambda: commands.set_box(ed, "voice"),
    lambda: ed._history(ed.undo), lambda: ed._history(ed.redo),
    lambda: random_cursor(False), lambda: random_cursor(True),
    lambda: (random_cursor(True), ed.insertFromMimeData(ed.createMimeDataFromSelection()) if ed.textCursor().hasSelection() else None),
]
bad = 0
start = time.perf_counter()
for sequence in range(400):
    ed.set_content(rng.choice(["", "<p>Uno</p><table><tr><th>a</th><th>b</th></tr><tr><td>c</td><td>d</td></tr></table><p>Due</p>",
                               '<h2>T</h2><ul><li>v</li></ul><div class="box master"><p>m</p></div>']))
    ed.setFocus()
    for step in range(30):
        rng.choice(operations)()
    pump()
    if not coherent():
        bad += 1
        if bad == 1:
            print("  primo testo incoerente:", ed.content()[:300])
print(f"  (400 sequenze da 30 operazioni in {time.perf_counter() - start:.1f} s)")
check("400 sequenze casuali (tabelle, celle, evidenziatore, annulla, incolla): testo sempre coerente", bad == 0)

print(f"\n{sum(ok)}/{len(ok)}")
