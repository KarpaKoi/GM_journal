"""Prove della schermata Impostazioni: le cinque liste, nuova voce / modifica / eliminazione con spostamento (popup veri, clic veri),
riordino, cronologia e effetto sulle altre schermate (elementi, mappe)."""
from harness import *
app()
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QToolButton
from gmjournal.app import MainWindow
from gmjournal.data import links
from gmjournal.data.models import ElementInput, PinInput
from gmjournal.ui.popups.entry import CategoryPopup
from gmjournal.ui.popups.pin_type import PinTypePopup, _IconButton
from gmjournal.ui.screens.settings import SettingsScreen
from gmjournal.ui.widgets.color_swatch import ColorSwatch
from gmjournal.ui.widgets.entry_row import EntryRow
from gmjournal.ui.widgets.filter_chip import FilterChip
from gmjournal.ui.widgets.hold_button import HOLD_MS, HoldButton
from gmjournal.ui.widgets.list_row import ListRow

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def drive(fn, delay=60):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))

def click(widget):
    QTest.mouseClick(widget, Qt.LeftButton); pump(60)

def hold(button):
    QTest.mousePress(button, Qt.LeftButton); QTest.qWait(HOLD_MS + 250); QTest.mouseRelease(button, Qt.LeftButton); pump(100)

repo = new_repo("ProvaImpostazioni")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "impostazioni"); pump(200)
s = w._screens["impostazioni"]
rows = lambda: s.findChildren(EntryRow)
def said(widget):
    """Tutto il testo che i QLabel dentro `widget` mostrano."""
    return " ".join(label.text() for label in widget.findChildren(QLabel))

# --- la schermata ------------------------------------------------------------------------------------
check("la schermata è quella vera (non il segnaposto)", isinstance(s, SettingsScreen))
check("nessun pannello a destra", "impostazioni" not in w._side_panels and not w._right_panel.isVisible())
lists = s._sidebar_list.findChildren(ListRow)
check("la barra sinistra elenca le cinque liste", len(lists) == 5 and w._sidebar_lists["impostazioni"] is s._sidebar_list)
check("si parte dai personaggi: titolo e quattro categorie", s._title.text() == "Personaggi" and len(rows()) == 4 and s._add.text().strip() == "Nuova categoria")
check("la prima riga non ha «su», l'ultima non ha «giù»", not rows()[0].findChildren(QToolButton)[0].isEnabled() and not rows()[-1].findChildren(QToolButton)[1].isEnabled())

# --- cambiare lista con un clic vero ---------------------------------------------------------------------
click(lists[4])
check("clic su «Mappe»: i tipi di pin", s._title.text() == "Mappe" and len(rows()) == 4 and s._add.text().strip() == "Nuovo tipo di pin" and s.current_target() == "mappe")
check("la cronologia sa dove siamo", w._location[1] == "impostazioni" and w._location[2] == "mappe")
click(lists[1])
check("clic su «Luoghi»", s._title.text() == "Luoghi" and w._location[2] == "luoghi")
w._topbar.back_clicked.emit(); pump(100)
check("«indietro» torna alla lista precedente", s._title.text() == "Mappe" and s.current_target() == "mappe")
w._topbar.forward_clicked.emit(); pump(100)
check("«avanti» alla successiva", s._title.text() == "Luoghi")
s.show_target("sconosciuta")
check("una lista che non esiste: nessun effetto", s._title.text() == "Luoghi")
click(lists[0])

# --- nuova categoria ---------------------------------------------------------------------------------------
def new_category(name, color_index):
    def go(d):
        assert isinstance(d, CategoryPopup)
        check("«Nuova categoria»: «Crea» spento a nome vuoto", not d._primary.isEnabled())
        d._name.setText(name)
        QTest.mouseClick(d._colors.findChildren(ColorSwatch)[color_index], Qt.LeftButton)
        check("il colore cliccato è quello scelto", d.color() == ["blue", "teal", "green", "amber", "pink", "violet", "mauve", "gray"][color_index])
        check("senza altre voci non c'è «elimina»", not d.findChildren(HoldButton))
        d.accept()
    return go
drive(new_category("Eroi", 5)); click(s._add); pump(150)
cats = repo.categories(links.CHARACTER)
check("creata in fondo, con il suo colore", [c.name for c in cats][-1] == "Eroi" and cats[-1].color == "violet" and len(rows()) == 5)
check("la barra sinistra aggiorna il conteggio", "5 categorie" in s._rows["personaggi"]._caption)

# --- riordinare con i clic veri -----------------------------------------------------------------------------------
last = rows()[-1]
click(last.findChildren(QToolButton)[0])        # «su»
check("«su» sposta la categoria", [c.name for c in repo.categories(links.CHARACTER)][-2] == "Eroi" and [r for r in rows()][-2] is not last)
click(rows()[-2].findChildren(QToolButton)[1])  # «giù»
check("«giù» la riporta", repo.categories(links.CHARACTER)[-1].name == "Eroi")

# --- modificare ------------------------------------------------------------------------------------------------------
eroi = repo.categories(links.CHARACTER)[-1]
def rename(d):
    check("«Modifica»: nome e colore attuali", isinstance(d, CategoryPopup) and d._name.text() == "Eroi" and d.color() == "violet")
    d._name.setText("Eroi della valle"); QTest.mouseClick(d._colors.findChildren(ColorSwatch)[1], Qt.LeftButton); d.accept()
drive(rename); click(rows()[-1]); pump(150)
renamed = repo.categories(links.CHARACTER)[-1]
check("nome e colore cambiati e salvati", (renamed.id, renamed.name, renamed.color) == (eroi.id, "Eroi della valle", "teal"))
drive(lambda d: d.reject()); click(rows()[-1]); pump(100)
check("«Annulla» non cambia nulla", repo.categories(links.CHARACTER)[-1].name == "Eroi della valle")

# --- eliminare con spostamento ----------------------------------------------------------------------------------------
pg = repo.categories(links.CHARACTER)
mira = repo.create_element(ElementInput(links.CHARACTER, "Mira", eroi.id, None, "", ""))
dax = repo.create_element(ElementInput(links.CHARACTER, "Dax", eroi.id, None, "", ""))
s.reload(); pump(50)
def remove_and_move(d):
    chips = d.findChildren(FilterChip)
    check("categoria usata: si sceglie dove spostare gli elementi, la prima è già scelta", len(chips) == 4 and chips[0].isChecked() and "2 personaggi" in said(d))
    QTest.mouseClick(chips[2], Qt.LeftButton)
    check("il clic cambia la scelta", chips[2].isChecked() and not chips[0].isChecked() and d.destination() == pg[2].id)
    hold(d.findChildren(HoldButton)[0])
drive(remove_and_move, 80); click(rows()[-1]); pump(200)
check("eliminata: la categoria non c'è più, gli elementi sono dove si è scelto",
      eroi.id not in {c.id for c in repo.categories(links.CHARACTER)} and repo.element(mira).category_id == pg[2].id and repo.element(dax).category_id == pg[2].id)
check("l'elenco si aggiorna (di nuovo 4 righe)", len(rows()) == 4)
check("il conteggio d'uso della categoria di destinazione cresce", "2 personaggi" in said(rows()[2]))

# tenere premuto troppo poco non elimina
def too_short(d):
    button = d.findChildren(HoldButton)[0]
    QTest.mousePress(button, Qt.LeftButton); QTest.qWait(300); QTest.mouseRelease(button, Qt.LeftButton); pump(50); d.reject()
drive(too_short); click(rows()[0]); pump(100)
check("rilasciare presto il pulsante non elimina", len(repo.categories(links.CHARACTER)) == 4)

# ultima categoria
for category in repo.categories(links.PLACE)[:-1]:
    repo.delete_category(category.id, repo.categories(links.PLACE)[-1].id)
click(lists[1]); pump(100)
only = []
drive(lambda d: (only.append((len(d.findChildren(HoldButton)), len(d.findChildren(FilterChip)))), d.reject()))
click(rows()[0]); pump(100)
check("l'unica categoria di un tipo non si può eliminare: niente pulsante", only == [(0, 0)])

# --- tipi di pin -----------------------------------------------------------------------------------------------------------
click(lists[4]); pump(100)
def new_type(d):
    check("«Nuovo tipo di pin»: c'è la scelta dell'icona", isinstance(d, PinTypePopup) and len(d.findChildren(_IconButton)) == 18)
    d._name.setText("Tesoro")
    QTest.mouseClick(d.findChildren(_IconButton)[2], Qt.LeftButton)       # Gemma
    QTest.mouseClick(d._colors.findChildren(ColorSwatch)[3], Qt.LeftButton)
    d.accept()
drive(new_type); click(s._add); pump(150)
tesoro = repo.pin_types()[-1]
check("tipo creato con nome, icona e colore scelti", (tesoro.name, tesoro.icon, tesoro.color) == ("Tesoro", "gem", "amber") and len(rows()) == 5)

def change_type(d):
    check("«Modifica tipo»: l'icona attuale è scelta", d.icon() == "gem" and d._name.text() == "Tesoro")
    d.findChildren(_IconButton)[10].click(); d.accept()
drive(change_type); click(rows()[-1]); pump(150)
check("cambiata l'icona", repo.pin_types()[-1].icon == "crown")
def keep_default_icon(d):
    check("un tipo di partenza mostra la sua icona (l'edificio) scelta", d.icon() == "building"); d.reject()
drive(keep_default_icon); click(rows()[0]); pump(100)

mappa = repo.create_map("Regno", None, None)
first = repo.pin_types()[0].id
repo.create_pin(mappa, 0.1, 0.1, PinInput(first, "Torre", "", None, None))
s.reload(); pump(50)
check("la riga mostra quanti pin usano il tipo", "1 pin" in said(rows()[0]))
def remove_type(d):
    d.findChildren(FilterChip)[1].click()
    hold(d.findChildren(HoldButton)[0])
drive(remove_type, 80); click(rows()[0]); pump(200)
check("tipo eliminato: il pin passa al tipo scelto", first not in {t.id for t in repo.pin_types()} and repo.pins(mappa)[0].type_id == repo.pin_types()[1].id)

# --- le altre schermate vedono i cambiamenti ------------------------------------------------------------------------------
w._go(repo.folder, "mappe"); pump(200)
maps_screen = w._screens["mappe"]
check("le mappe leggono i tipi di pin aggiornati", [t.name for t in maps_screen._types] == [t.name for t in repo.pin_types()] and "Tesoro" in [t.name for t in maps_screen._types])
w._go(repo.folder, "personaggi"); pump(200)
chars = w._screens["personaggi"]
check("la schermata dei personaggi vede le categorie nuove e il conteggio spostato", [c.name for c in chars._categories.values()] == [c.name for c in repo.categories(links.CHARACTER)]
      and {e.category_id for e in chars._elements} == {pg[2].id})
w._go(repo.folder, "impostazioni"); pump(100)
check("tornando in Impostazioni si resta sulla stessa lista", s.current_target() == "mappe")

# --- creare un tipo di pin dalle mappe: l'elenco delle Impostazioni lo vede ---------------------------------------------------
before = len(repo.pin_types())
repo.create_pin_type("Rovina", "skull", "gray")
w._go(repo.folder, "mappe"); pump(100); w._go(repo.folder, "impostazioni"); pump(150)
check("un tipo creato altrove compare tornando in Impostazioni", len(rows()) == before + 1)

print(f"{sum(ok)}/{len(ok)}")
