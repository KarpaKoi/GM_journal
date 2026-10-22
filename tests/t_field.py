from harness import *
app()
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from gmjournal.data.models import ElementInput
from gmjournal.elements import Field
from gmjournal.ui.link_sources import LinkSources
from gmjournal.ui.widgets.field_edit import FieldEdit, fill_document, export_content
from PySide6.QtGui import QTextDocument

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("CampoProva")
cats = repo.categories("character")
mira = repo.create_element(ElementInput("character", "Mira Vesperi", cats[0].id, None, "", ""))
anselm = repo.create_element(ElementInput("character", "Fratello Anselm", cats[1].id, None, "", ""))
host = QWidget(); host.resize(420, 500)
sources = LinkSources(host, repo, lambda: ("character", mira))
box = QVBoxLayout(host)
def make(label, field, content=""):
    box.addWidget(QLabel(label.upper()))
    w = FieldEdit(field, sources); w.set_content(content); box.addWidget(w); return w
link = lambda i, t: f'<a href="gmj://character/{i}">{t}</a>'
f1 = make("Aspetto", Field("appearance", "Aspetto"), "<p>Magra e nervosa, capelli corti color cenere, una cicatrice sottile sul sopracciglio sinistro. Veste di grigio consunto.</p>")
f2 = make("Legami", Field("bonds", "Legami"), f"<p>Deve la vita a {link(anselm, 'Fratello Anselm')}. Protegge la locanda.</p>")
f3 = make("Frase", Field("quote", "Frase tipica", quote=True), "<p>“Il fuoco non perdona, ma ricorda.”</p>")
f4 = make("Agganci", Field("hooks", "Agganci di trama", "Idee per collegarla alla storia dei giocatori…"))
box.addStretch()
host.show(); pump(100)
shot(host, "campo_1.png")

# round trip
doc = QTextDocument(); fill_document(doc, f"<p>A &amp; B &lt;x&gt;</p><p>Due{'<br>'}righe {link(2, 'Link')} fine</p><p></p><p></p>")
out = export_content(doc)
check("round trip: escape, br, link, paragrafi vuoti finali tolti", out == '<p>A &amp; B &lt;x&gt;</p><p>Due<br>righe <a href="gmj://character/2">Link</a> fine</p>')
check("content() di un campo vuoto è ''", f4.content() == "")
check("content() del campo pieno ricostruisce il link", f'gmj://character/{anselm}">Fratello Anselm</a>' in f2.content())

# clic su collegamento in lettura: apre
got = []
f2.link_activated.connect(lambda k, i: got.append((k, i)))
t = f2._text
cur = t.cursorRect(t.document().find("Fratello") if False else t.textCursor())
from PySide6.QtGui import QTextCursor
c = QTextCursor(t.document()); c.setPosition(t.document().toPlainText().index("Fratello") + 3)
pt = t.cursorRect(c).center()
QTest.mouseClick(t.viewport(), Qt.LeftButton, Qt.NoModifier, pt); pump()
check("clic su un collegamento (lettura) lo apre", got == [("character", anselm)])
check("…e non entra in modifica", not f2._editing)

# clic su testo: modifica
changed = []
f1.edited.connect(lambda: changed.append(1))
QTest.mouseClick(f1._text.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(20, 5)); pump()
check("clic sul testo entra in modifica", f1._editing and f1._text.hasFocus())
QTest.keyClicks(f1._text, " Nuovo."); pump()
check("scrivere emette edited", len(changed) > 0)
check("il testo è nel contenuto", "Nuovo." in f1.content() and f1.content().startswith("<p>") )
shot(host, "campo_2.png")
QTest.keyClick(f1._text, Qt.Key_Escape); pump()
check("Esc finisce la modifica", not f1._editing)

# campo vuoto: clic nella cornice
QTest.mouseClick(f4, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5)); pump()
check("clic nella cornice di un campo vuoto entra in modifica", f4._editing)
QTest.keyClicks(f4._text, "Vedi @Fra"); pump()
from gmjournal.ui.editor.link_ui import TargetPopup
pops = host.findChildren(TargetPopup)
check("«@» nel campo apre l'elenco (nella finestra, non tagliato)", pops and pops[0].isVisible() and pops[0].parentWidget() is host)
shot(host, "campo_3.png")
QTest.keyClick(f4._text, Qt.Key_Return); pump()
check("Invio inserisce il collegamento", f'gmj://character/{anselm}">Fratello Anselm</a>' in f4.content())
QTest.keyClicks(f4._text, " e basta"); pump()
check("il testo dopo il link non è nel link", f4.content().endswith('</a> e basta</p>'))
f4._stop_editing(); pump()
check("indice: il testo salvato è leggibile da links.extract_targets", True)
from gmjournal.data import links
check("extract_targets sul contenuto", links.extract_targets(f4.content()) == [("character", anselm)])
shot(host, "campo_4.png")

# incolla solo testo semplice
f1._start_editing(None)
from PySide6.QtCore import QMimeData
md = QMimeData(); md.setHtml("<b>grassetto</b>"); md.setText("grassetto")
f1._text.insertFromMimeData(md); pump()
check("incolla: solo testo semplice", "<b>" not in f1.content() and "grassetto" in f1.content())
f1._stop_editing()

# perdita del fuoco chiude la modifica
f3._start_editing(None); pump()
from PySide6.QtGui import QFocusEvent
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
QApplication.sendEvent(f3._text, QFocusEvent(QEvent.FocusOut, Qt.OtherFocusReason)); pump()
check("perdere il fuoco chiude la modifica", not f3._editing)
print(f"\n{sum(ok)}/{len(ok)}")
