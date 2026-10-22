from harness import *
app()
import sys
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from gmjournal.data.models import ElementInput
from gmjournal.app import MainWindow
from gmjournal.ui.editor.link_ui import TargetPopup

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("RicercaGlobale")
cats = {k: repo.categories(k) for k in ("character", "place", "organization")}
mk = lambda kind, name: repo.create_element(ElementInput(kind, name, cats[kind][0].id, None, "", ""))
mira = mk("character", "Mira Vesperi")
miriel = mk("character", "Miriel dell'Alba")
varen = mk("place", "Varenhold")
cit = mk("place", "Città di Miravale")
ordine = mk("organization", "Ordine della Fiamma")
cap1 = repo.create_page("Capitolo 1")
cap2 = repo.create_page("Il ritorno di Mira")

w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
box = w._topbar.search
edit = box._edit
popup = [p for p in w.centralWidget().findChildren(TargetPopup)][0]
names = lambda: [popup._list.item(i).data(Qt.UserRole).name for i in range(popup._list.count())]

check("nell'elenco campagne il campo è spento", not edit.isEnabled() and "campagna" in edit.placeholderText())
w._topbar.focus_search(); QTest.keyClicks(edit, "mira"); pump(50)
check("…e non apre nulla", not popup.isVisible())

w._go(repo.folder, "scrittura", cap1); pump(200)
check("in una campagna il campo è acceso", edit.isEnabled() and edit.placeholderText().startswith("Cerca"))

# Ctrl+K porta il cursore nel campo
w.setFocus(); pump(30)
QTest.keyClick(w, Qt.Key_K, Qt.ControlModifier); pump(50)
check("Ctrl K mette il cursore nel campo", edit.hasFocus())
check("senza testo l'elenco è chiuso", not popup.isVisible())

QTest.keyClicks(edit, "mira"); pump(80)
check("scrivendo compare l'elenco", popup.isVisible())
check("prima ciò che inizia così, poi ciò che lo contiene (pagine prima degli elementi)",
      names() == ["Mira Vesperi", "Il ritorno di Mira", "Città di Miravale"])
check("«Miriel» non c'entra con «mira»", "Miriel dell'Alba" not in names())
check("la prima riga è già evidenziata", popup._list.currentRow() == 0)
w.grab().save("search_100.png")

edit.clear(); QTest.keyClicks(edit, "citta"); pump(50)
check("«citta» trova «Città di Miravale» (accenti ignorati)", names() == ["Città di Miravale"])
edit.clear(); QTest.keyClicks(edit, "zzzz"); pump(50)
check("nessun risultato: l'elenco resta aperto con «Nessun risultato»", popup.isVisible() and popup._empty.isVisible())
QTest.keyClick(edit, Qt.Key_Return); pump(50)
check("Invio senza risultati non fa nulla", w._location[1] == "scrittura" and edit.text() == "zzzz")

# frecce + Invio su un elemento
edit.clear(); QTest.keyClicks(edit, "var"); pump(50)
check("«var» trova Varenhold", names() == ["Varenhold"])
QTest.keyClick(edit, Qt.Key_Down); pump(20)
check("le frecce non escono dall'elenco (una riga: resta lì)", popup._list.currentRow() == 0)
QTest.keyClick(edit, Qt.Key_Return); pump(250)
check("Invio apre la scheda del luogo", w._location[1] == "luoghi" and w._screens["luoghi"]._sheet_open and w._screens["luoghi"]._sheet.element_id == varen)
check("il campo si svuota, l'elenco si chiude, il cursore esce", edit.text() == "" and not popup.isVisible() and not edit.hasFocus())

# cronologia: indietro riporta a Scrittura
w._topbar.back_clicked.emit(); pump(200)
check("indietro: di nuovo Scrittura", w._location[1] == "scrittura")

# clic con il mouse su una pagina (seconda riga)
edit.setFocus(); QTest.keyClicks(edit, "mira"); pump(80)
rows = names()
i = rows.index("Il ritorno di Mira")
item = popup._list.item(i)
QTest.mouseClick(popup._list.viewport(), Qt.LeftButton, Qt.NoModifier, popup._list.visualItemRect(item).center()); pump(250)
check("un clic su una pagina la apre in Scrittura", w._location[1] == "scrittura" and w._screens["scrittura"]._page_id == cap2)
check("…e chiude l'elenco", not popup.isVisible() and edit.text() == "")

# frecce su/giù con più risultati e Invio
edit.setFocus(); QTest.keyClicks(edit, "mira"); pump(80)
QTest.keyClick(edit, Qt.Key_Down); pump(20)
cur = popup.current_target()
check("freccia giù passa alla riga dopo", popup._list.currentRow() == 1)
QTest.keyClick(edit, Qt.Key_Up); QTest.keyClick(edit, Qt.Key_Up); pump(20)
check("freccia su dalla prima va all'ultima", popup._list.currentRow() == popup._list.count() - 1)
QTest.keyClick(edit, Qt.Key_Down); pump(20)  # dall'ultima si ricomincia dalla prima
tgt = popup.current_target()
QTest.keyClick(edit, Qt.Key_Return); pump(250)
check("Invio apre la riga evidenziata", tgt.kind == "character" and w._location[1] == "personaggi" and w._screens["personaggi"]._sheet.element_id == tgt.id)

# Esc: svuota e chiude
w._go(repo.folder, "scrittura", cap1); pump(150)
edit.setFocus(); QTest.keyClicks(edit, "ordine"); pump(60)
check("«ordine» trova l'Ordine della Fiamma", names() == ["Ordine della Fiamma"] and popup.isVisible())
QTest.keyClick(edit, Qt.Key_Escape); pump(50)
check("Esc chiude, svuota e toglie il cursore", not popup.isVisible() and edit.text() == "" and not edit.hasFocus())
check("Esc non cambia schermata", w._location[1] == "scrittura")

# perdere il cursore chiude l'elenco; riaverlo lo riapre
edit.setFocus(); QTest.keyClicks(edit, "mira"); pump(60)
w.centralWidget().setFocus(); pump(50)
check("togliere il cursore chiude l'elenco ma lascia il testo", not popup.isVisible() and edit.text() == "mira")
w._topbar.focus_search(); pump(60)
check("Ctrl K lo riapre con lo stesso testo", popup.isVisible() and edit.text() == "mira" and edit.selectedText() == "mira")
edit.clear(); pump(20)

# elemento cancellato mentre l'elenco è aperto: la ricerca lo rilegge a ogni lettera
edit.setFocus(); QTest.keyClicks(edit, "ordine"); pump(50)
repo.delete_element(ordine)
QTest.keyClick(edit, Qt.Key_Backspace); QTest.keyClicks(edit, "e"); pump(50)
check("un elemento eliminato non compare più", "Ordine della Fiamma" not in names())
edit.clear(); box.release_focus(); pump(30)

# tornare alla Home spegne e svuota
edit.setFocus(); QTest.keyClicks(edit, "mira"); pump(50)
w._topbar.home_clicked.emit(); pump(150)
check("Home: campo spento, testo svuotato, elenco chiuso", not edit.isEnabled() and edit.text() == "" and not popup.isVisible())
w.grab().save("search_home_100.png")

# campagna vuota
empty = new_repo("RicercaVuota")
w._go(empty.folder, "scrittura"); pump(200)
edit.setFocus(); QTest.keyClicks(edit, "a"); pump(50)
check("campagna vuota: «Nessun risultato», nessun errore", popup.isVisible() and popup._empty.isVisible())

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
