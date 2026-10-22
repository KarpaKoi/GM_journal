"""Regressione: comportamento delle menzioni «@» dell'editor (deve restare identico dopo il refactor)."""
from harness import *
app()
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from gmjournal.data import links
from gmjournal.data.models import LinkTarget
from gmjournal.ui.editor.editor import RichEditor
from gmjournal.ui.editor.link_ui import TargetPopup

DB = [LinkTarget("character", 2, "Mira Vesperi", "Protagonisti"), LinkTarget("character", 3, "Mirko", "Alleati"),
      LinkTarget("place", 7, "Varenhold", "Città")]
calls = []
def source(query, limit):
    calls.append((query, limit))
    found = [t for t in DB if t.name.lower().startswith(query.lower())][:limit]
    return found + ([LinkTarget(links.CREATE + "place", 0, query, "")] if query else [])
created = []
def create(request):
    created.append(request)
    return LinkTarget("place", 99, request.name, "Città") if request.name != "Annulla" else None

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

editor = RichEditor(link_targets=source, create_target=create)
editor.resize(900, 500); editor.show(); editor.setFocus(); pump(50)
def popup():
    found = editor.viewport().findChildren(TargetPopup)
    return found[0] if found else None
def rows():
    p = popup()
    return p._list.count() if p is not None and p.isVisible() else None
def visible():
    p = popup(); return p is not None and p.isVisible()
def reset():
    editor.set_content(""); editor.setFocus(); pump()

check("popup assente all'inizio", not visible())
QTest.keyClicks(editor, "Ciao @Mi"); pump()
check("«@Mi» apre l'elenco", visible())
check("ricerca con 'Mi' e limite 8", calls[-1] == ("Mi", 8))
check("risultati: 2 elementi + riga Crea", rows() == 3)
check("popup dentro il viewport e con geometria sensata", popup().parentWidget() is editor.viewport() and popup().width() == 340 and popup().y() > 0)
QTest.keyClick(editor, Qt.Key_Down); pump()
check("freccia giù sposta la selezione", popup().current_target().id == 3)
QTest.keyClick(editor, Qt.Key_Return); pump()
check("Invio inserisce il link", '<a href="gmj://character/3">Mirko</a>' in editor.content())
check("popup chiuso dopo la scelta", not visible())
check("il testo '@Mi' è stato sostituito", "@Mi" not in editor.toPlainText() and editor.toPlainText().startswith("Ciao Mirko"))

reset()
QTest.keyClicks(editor, "@Va"); pump()
check("Tab accetta", visible())
QTest.keyClick(editor, Qt.Key_Tab); pump()
check("Tab inserisce Varenhold", 'gmj://place/7">Varenhold</a>' in editor.content() and not visible())

reset()
QTest.keyClicks(editor, "@Mi"); pump()
QTest.keyClick(editor, Qt.Key_Escape); pump()
check("Esc chiude e lascia il testo", not visible() and editor.toPlainText().startswith("@Mi"))
QTest.keyClicks(editor, "r"); pump()
check("dopo Esc, scrivere ancora non lo riapre", not visible())

reset()
QTest.keyClicks(editor, "parola@Mi"); pump()
check("«@» a metà parola non apre", not visible())

reset()
QTest.keyClicks(editor, "(@Mi"); pump()
check("«@» dopo '(' apre", visible())
QTest.keyClick(editor, Qt.Key_Home); pump()
check("spostare il cursore prima della «@» chiude", not visible())

reset()
QTest.keyClicks(editor, "@Xyz"); pump()
check("nessun risultato: resta la riga Crea", visible() and rows() == 1)
QTest.keyClicks(editor, " "); pump()
check("spazio: con la riga Crea l'elenco resta (nomi di più parole)", visible())
reset()
QTest.keyClicks(editor, "@Mir"); pump()
QTest.keyClicks(editor, " Ve"); pump()
check("più parole: la ricerca prosegue con lo spazio", visible() and calls[-1] == ("Mir Ve", 8))

bare = RichEditor(link_targets=lambda q, n: [t for t in DB if t.name.lower().startswith(q.lower())][:n])
bare.resize(600, 300); bare.show(); bare.setFocus(); pump(50)
QTest.keyClicks(bare, "@Xyz"); pump()
bpop = bare.viewport().findChildren(TargetPopup)[0]
check("senza risultati l'elenco dice «Nessun risultato»", bpop.isVisible() and bpop._list.count() == 0)
QTest.keyClicks(bare, " "); pump()
check("senza risultati, lo spazio chiude", not bpop.isVisible())
QTest.keyClicks(bare, "@Mi"); pump()
check("una nuova «@» riapre", bpop.isVisible())
QTest.keyClick(bare, Qt.Key_Return); pump()
check("Invio sul primo risultato", 'gmj://character/2">Mira Vesperi</a>' in bare.content())
reset_editor = None

reset()
QTest.keyClicks(editor, "@" + "a" * 31); pump()
check("oltre 30 caratteri non è più una ricerca", not visible())

reset()
QTest.keyClicks(editor, "@Nuovo"); pump()
QTest.keyClick(editor, Qt.Key_Return); pump()
check("Invio sulla riga «Crea» chiama create_target", created and created[-1].kind == links.CREATE + "place" and created[-1].name == "Nuovo")
check("…e inserisce il link al creato", 'gmj://place/99">Nuovo</a>' in editor.content())

reset(); created.clear()
QTest.keyClicks(editor, "@Annulla"); pump()
QTest.keyClick(editor, Qt.Key_Return); pump()
check("crea annullato: nessun link, testo '@Annulla' resta", "gmj://" not in editor.content() and editor.toPlainText().startswith("@Annulla"))

reset()
QTest.keyClicks(editor, "@Mi"); pump()
from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QApplication
QApplication.sendEvent(editor, QFocusEvent(QEvent.FocusOut, Qt.OtherFocusReason)); pump()
check("perdere il fuoco chiude", not visible())

editor.setFocus(); reset()
QTest.keyClicks(editor, "@Mi"); pump()
editor.set_content("altro"); pump()
check("set_content chiude", not visible())

# clic con il mouse su una riga
reset(); editor.setFocus()
QTest.keyClicks(editor, "@Mi"); pump()
lst = popup()._list
rect = lst.visualItemRect(lst.item(0))
QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center()); pump()
check("clic su una riga inserisce il link", 'gmj://character/2">Mira Vesperi</a>' in editor.content() and not visible())

# nessuna sorgente: nessun popup
plain = RichEditor(); plain.resize(500, 300); plain.show(); plain.setFocus(); pump(30)
QTest.keyClicks(plain, "@Mi"); pump()
check("senza sorgente: nessun elenco", not plain.viewport().findChildren(TargetPopup) or not plain.viewport().findChildren(TargetPopup)[0].isVisible())

print(f"\n{sum(ok)}/{len(ok)}")
raise SystemExit(0 if all(ok) else 1)
