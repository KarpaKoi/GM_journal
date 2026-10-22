"""Prove della schermata Mappe: elenco, mappa interattiva, pin (posare, modificare, spostare, eliminare), tipi, collegamenti
dalla scheda del luogo e dalla libreria immagini, cronologia."""
from harness import *
app()
import tempfile
from pathlib import Path
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget
from gmjournal.app import MainWindow
from gmjournal.data import links
from gmjournal.data.models import ElementInput, PinInput
from gmjournal.ui.map_target import MapTarget
from gmjournal.ui.popups.base import DELETE
from gmjournal.ui.popups.map import MapPopup
from gmjournal.ui.popups.pin_type import PinTypePopup
from gmjournal.ui.editor.link_ui import LinkPickerPopup
from gmjournal.ui.screens.elements import ElementTarget
from gmjournal.ui.widgets.map_canvas import ADD, GHOST, MOVE, SELECT
from gmjournal.ui.widgets.map_card import MapCard
from gmjournal.ui.widgets.menu import PopupMenu
from gmjournal.ui.widgets.pin_card import PinCard
from gmjournal.ui.widgets.pin_form import PinForm

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def drive(fn, delay=60):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))

def menu_buttons():
    menus = [m for m in QApplication.topLevelWidgets() if isinstance(m, PopupMenu) and m.isVisible()]
    return menus[-1].findChildren(QAbstractButton) if menus else []

def menu_items():
    return {b.text(): b for b in menu_buttons()}

def choose(text):
    """Sceglie una voce del menu aperto (la voce parte dopo la chiusura del menu: serve un giro di eventi)."""
    items = menu_items()
    if text not in items:
        return False
    items[text].click(); pump(60)
    return True

def viewport_point(canvas, x, y):
    return canvas.mapFromScene(canvas._to_scene(x, y))

def card_fits(canvas):
    """La finestrella aperta si vede davvero: ha un'altezza, sta dentro l'area della mappa e ogni suo pezzo sta nel riquadro."""
    card = canvas._card
    if card is None or not card.isVisible():
        return False
    pieces = [c for c in card.findChildren(QWidget) if c.parent() is card and c.isVisible()]
    return (card.height() > 120 and canvas.rect().contains(card.geometry().adjusted(8, 8, -8, -8))
            and all(card.rect().contains(c.geometry()) and c.height() > 0 for c in pieces))

def click_map(canvas, x, y):
    QTest.mouseClick(canvas.viewport(), Qt.LeftButton, pos=viewport_point(canvas, x, y)); pump(60)

tmp = Path(tempfile.mkdtemp())
def png(name, color, size=(800, 500)):
    img = QImage(*size, QImage.Format_RGB32); img.fill(QColor(color)); img.save(str(tmp / name)); return tmp / name

repo = new_repo("ProvaMappe")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "mappe"); pump(200)
s = w._screens["mappe"]
seen = []
s.navigated.connect(seen.append)

# --- nessuna mappa -----------------------------------------------------------------------------------
check("senza mappe: schermata di benvenuto", s._views.currentIndex() == 2)
check("senza mappe: niente pannello a destra", not s.panel_visible() and not w._right_panel.isVisible())

# --- creare una mappa ------------------------------------------------------------------------------------
img_regno = repo.import_image(png("regno.png", "#c9b88f"), None)
img_valle = repo.import_image(png("valle.png", "#b8c49a", (500, 800)), None)

def fill_map(name, image=None, container=None):
    def go(d):
        assert isinstance(d, MapPopup)
        d._name.setText(name)
        if image is not None:
            d._choice.set_image(image)
        d.accept()
    return go
drive(fill_map("Regno di Aldoria")); s._create_map(); pump(200)
regno = repo.maps()[0].id
check("creata e aperta: vista della mappa", s._map_id == regno and s._views.currentIndex() == 1)
check("mappa senza sfondo: invito a sceglierlo", not s._canvas.has_image() and s._canvas._empty.isVisible())
check("la nuova mappa è nell'albero della barra", s._tree.topLevelItemCount() == 1 and s._tree.currentItem().text(0) == "Regno di Aldoria")
check("la cronologia sa dov'è", w._location[1] == "mappe" and w._location[2] == MapTarget(regno, None))
check("il pannello destro compare", s.panel_visible() and w._right_panel.isVisible())

# lo sfondo si sceglie dal popup di modifica (si apre anche dall'invito)
opened = []
def edit_background(d):
    opened.append(type(d).__name__); d._choice.set_image(img_regno); d.accept()
drive(edit_background); s._canvas.image_requested.emit(); pump(200)
check("l'invito apre «Modifica mappa» e lo sfondo compare", opened == ["MapPopup"] and s._canvas.has_image() and repo.maps()[0].image == img_regno)

# --- un luogo e dei pin ------------------------------------------------------------------------------------
cat = repo.categories(links.PLACE)[0]
varen = repo.create_element(ElementInput(links.PLACE, "Varenhold", cat.id, None, "Città sul fiume.", ""))
types = repo.pin_types()
check("quattro tipi di pin di partenza", [t.name for t in types] == ["Luogo", "Persona", "Evento", "Missione"])

# --- posare un pin con un clic vero ---------------------------------------------------------------------
s._canvas.set_tool(ADD); pump(50)
check("strumento «Aggiungi pin»: compare l'invito in basso", s._canvas._tool == ADD and s._canvas._hint.isVisible())
click_map(s._canvas, 0.30, 0.40)
check("il clic posa un pin provvisorio e apre la finestrella", GHOST in s._canvas._pins and isinstance(s._form, PinForm) and (s._canvas._card is not None))
check("la finestrella del nuovo pin si vede (altezza vera, dentro la mappa, pulsanti compresi)", card_fits(s._canvas))
check("finché non c'è un nome «Aggiungi pin» è spento", not s._form._primary.isEnabled())
placed = s._ghost
click_map(s._canvas, 0.8, 0.8)
check("a finestrella aperta un altro clic sulla mappa non sposta né salva nulla", s._ghost == placed and len(repo.pins(regno)) == 0 and s._form is not None)
form = s._form
form._name.setText("Torre abbandonata"); form._brief.setPlainText("Una torre senza porte."); pump(30)
check("col nome «Aggiungi pin» si accende", form._primary.isEnabled())
form._primary.click(); pump(200)
pins = repo.pins(regno)
check("il pin è salvato con nome, testo e tipo di partenza", len(pins) == 1 and pins[0].name == "Torre abbandonata" and pins[0].brief == "Una torre senza porte." and pins[0].type_id == types[0].id)
check("posizione: dov'è stato cliccato", abs(pins[0].x - 0.30) < 0.01 and abs(pins[0].y - 0.40) < 0.01)
check("finito: via il provvisorio, lo strumento torna a «Seleziona»", GHOST not in s._canvas._pins and s._canvas._tool == SELECT)
check("il pin nuovo è scelto: finestrella di lettura, riga nel pannello", s._selected == pins[0].id and isinstance(s._canvas._card, PinCard) and len(s._panel.findChildren(QAbstractButton)) == 1)
check("la finestrella di lettura si vede", card_fits(s._canvas))
check("la cronologia ricorda il pin", w._location[2] == MapTarget(regno, pins[0].id))

# --- annullare ---------------------------------------------------------------------------------------------------
s._canvas.set_tool(ADD); click_map(s._canvas, 0.6, 0.3)
s._panel.chosen.emit(pins[0].id); pump(50)
check("a finestrella aperta la scelta dal pannello è ignorata", s._form is not None and s._selected is None)
w._go(repo.folder, "personaggi"); pump(100)
w._go(repo.folder, "mappe", MapTarget(regno)); pump(100)
check("lasciando la schermata a pin non finito, il pin provvisorio si perde", s._form is None and GHOST not in s._canvas._pins)
check("tornando, la mappa è com'era", s._map_id == regno and len(repo.pins(regno)) == 1)
s._canvas.set_tool(ADD); click_map(s._canvas, 0.6, 0.3)
s._form.cancelled.emit(); pump(50)
check("annullando non si salva nulla e il provvisorio sparisce", len(repo.pins(regno)) == 1 and GHOST not in s._canvas._pins and s._form is None and s._canvas._tool == SELECT)

# --- pin collegato a un luogo ----------------------------------------------------------------------------------
def pick_place(d):
    assert isinstance(d, LinkPickerPopup)
    d._search.setText("Varen"); pump(30)
    d._choose(d._targets("Varen", 5)[0])
s._canvas.set_tool(ADD); click_map(s._canvas, 0.55, 0.55)
drive(pick_place); s._form.link_requested.emit(); pump(100)
check("scelto il luogo la finestrella mostra «Collegato a»", s._form._link is not None and s._form._link.id == varen and not s._form._linked.isHidden())
check("collegato: «Aggiungi pin» è acceso senza scrivere il nome", s._form._primary.isEnabled())
s._form._primary.click(); pump(200)
linked = [p for p in repo.pins(regno) if p.link is not None][0]
check("il pin collegato prende nome e testo dal luogo", linked.name == "Varenhold" and linked.brief == "Città sul fiume." and linked.link.kind == links.PLACE)
check("la finestrella del pin collegato si vede", card_fits(s._canvas))
check("la finestrella di lettura ha «Apri pagina»", any(b.text().strip() == "Apri pagina" for b in s._canvas._card.findChildren(QAbstractButton)))
sent = []
s.open_requested.connect(lambda section, target: sent.append((section, target)))
next(b for b in s._canvas._card.findChildren(QAbstractButton) if b.text().strip() == "Apri pagina").click(); pump(100)
check("«Apri pagina» porta alla scheda del luogo", w._location[1] == "luoghi" and w._location[2] == ElementTarget(varen, True))
w._topbar.back_clicked.emit(); pump(200)
check("indietro: di nuovo sulla mappa con quel pin scelto", w._location[1] == "mappe" and s._map_id == regno and s._selected == linked.id and (s._canvas._card is not None))

# --- scegliere dal pannello e dalla mappa -----------------------------------------------------------------------
rows = [b for b in s._panel.findChildren(QAbstractButton)]
check("il pannello elenca i pin della mappa", len(rows) == 2)
rows[0].click(); pump(100)
check("clic su una riga: pin scelto e finestrella", s._selected == repo.pins(regno)[0].id and (s._canvas._card is not None))
click_map(s._canvas, 0.55, 0.55)
check("clic sul pin sulla mappa: lo sceglie", s._selected == linked.id)
click_map(s._canvas, 0.9, 0.1)
check("clic sullo sfondo: nessun pin scelto, finestrella chiusa", s._selected is None and not (s._canvas._card is not None))

# --- spostare con il trascinamento -----------------------------------------------------------------------------------
start, end = viewport_point(s._canvas, 0.30, 0.40), viewport_point(s._canvas, 0.45, 0.25)
QTest.mousePress(s._canvas.viewport(), Qt.LeftButton, pos=start)
for step in range(1, 6):
    QTest.mouseMove(s._canvas.viewport(), start + (end - start) * step / 5); pump(10)
QTest.mouseRelease(s._canvas.viewport(), Qt.LeftButton, pos=end); pump(100)
moved = repo.pins(regno)[0]
check("trascinato: la nuova posizione è salvata", abs(moved.x - 0.45) < 0.02 and abs(moved.y - 0.25) < 0.02)
check("dopo il trascinamento non cambia la scelta", s._selected is None)

# --- zoom e spostamento della mappa ----------------------------------------------------------------------------------------------------------------------------------------------------
from PySide6.QtWidgets import QToolButton
c = s._canvas
tools = {b.toolTip(): b for b in c._tools.findChildren(QToolButton)}
fit = c._scale
check("all'inizio la mappa è tutta inquadrata", c._fitted and abs(fit - c._min_scale) < 1e-9)
tools["Ingrandisci"].click(); pump(30)
check("«Ingrandisci» fa lo zoom", c._scale > fit * 1.2 and not c._fitted)
zoomed = c._scale
centre = c.viewport().rect().center()
c.wheelEvent(QWheelEvent(QPointF(centre), QPointF(c.viewport().mapToGlobal(centre)), QPoint(0, 0), QPoint(0, 120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
check("la rotella ingrandisce (verso l'alto) sotto il mouse", c._scale > zoomed)
for _ in range(30):
    tools["Riduci"].click()
check("riducendo non si scende sotto l'inquadratura intera", abs(c._scale - c._min_scale) < 1e-9 and c._fitted)
for _ in range(30):
    tools["Ingrandisci"].click()
check("ingrandendo c'è un limite", c._scale <= c._max_scale + 1e-9)
c.set_tool(MOVE)
h0, v0 = c.horizontalScrollBar().value(), c.verticalScrollBar().value()
before = [(p.x, p.y) for p in repo.pins(regno)]
start = QPoint(300, 300)
QTest.mousePress(c.viewport(), Qt.LeftButton, pos=start)
for step in range(1, 5):
    QTest.mouseMove(c.viewport(), start + QPoint(-40 * step, -30 * step)); pump(10)
QTest.mouseRelease(c.viewport(), Qt.LeftButton, pos=start + QPoint(-160, -120)); pump(50)
check("con «Sposta la mappa» il trascinamento scorre la mappa", (c.horizontalScrollBar().value(), c.verticalScrollBar().value()) != (h0, v0))
check("…e non sposta nessun pin", [(p.x, p.y) for p in repo.pins(regno)] == before)
c.set_tool(SELECT)
for _ in range(30):
    tools["Riduci"].click()
tools["Ingrandisci"].click(); tools["Ingrandisci"].click(); pump(30)
pin_id = repo.pins(regno)[0].id
c.reveal(pin_id); pump(30)
check("«reveal» porta in vista un pin fuori dalla parte visibile", c.viewport().rect().contains(c.mapFromScene(c._pins[pin_id].pos())))
s._select_pin(pin_id); pump(30)
card_before = c._card.pos()
tools["Ingrandisci"].click(); pump(30)
check("la finestrella segue il suo pin quando si fa zoom", c._card.pos() != card_before or not c.viewport().rect().contains(c.mapFromScene(c._pins[pin_id].pos())))
s._deselect()
for _ in range(30):
    tools["Riduci"].click()

# --- modificare ---------------------------------------------------------------------------------------------------------
s._select_pin(moved.id); pump(50)
next(b for b in s._canvas._card.findChildren(QAbstractButton) if b.toolTip() == "Modifica pin").click(); pump(100)
check("«Modifica pin» apre la finestrella con i dati attuali", isinstance(s._form, PinForm) and s._form._name.text() == "Torre abbandonata" and s._form_pin.id == moved.id)
check("la finestrella di modifica si vede (anche con «tieni premuto» e suggerimento)", card_fits(s._canvas))
s._form._name.setText("Torre dei venti"); s._form._choose_type(types[2]); pump(30)
s._form._primary.click(); pump(150)
edited = repo.pins(regno)[0]
check("salvate le modifiche: nome e tipo", edited.name == "Torre dei venti" and edited.type_id == types[2].id)
check("dopo il salvataggio torna la finestrella di lettura", isinstance(s._canvas._card, PinCard) and s._selected == edited.id)
s._edit_pin(s._pin(edited.id)); s._form.cancelled.emit(); pump(50)
check("annullando la modifica si torna alla lettura", isinstance(s._canvas._card, PinCard) and repo.pins(regno)[0].name == "Torre dei venti")

# --- nuovo tipo di pin -----------------------------------------------------------------------------------------------------
def make_type(d):
    assert isinstance(d, PinTypePopup)
    d._name.setText("Tesoro"); d._icons.button(2).setChecked(True); d._colors.set_value("teal"); d.accept()
s._canvas.set_tool(ADD); click_map(s._canvas, 0.7, 0.7)
drive(make_type); s._form.new_type_requested.emit(); pump(150)
treasure = next(t for t in repo.pin_types() if t.name == "Tesoro")
check("il tipo è salvato con icona e colore scelti", treasure.icon == "gem" and treasure.color == list(__import__("gmjournal").theme.CATEGORY_COLORS)[1])
check("il tipo nuovo è subito quello scelto nella finestrella e compare fra i filtri", s._form.data().type_id == treasure.id and treasure.id in s._canvas._chips)
check("il pin provvisorio prende lo stile del tipo", s._canvas._pins[GHOST]._icon == "gem")
s._form._name.setText("Forziere"); s._form._primary.click(); pump(150)
chest = [p for p in repo.pins(regno) if p.name == "Forziere"][0]
check("pin del tipo nuovo salvato", chest.type_id == treasure.id)

# --- filtri per tipo ----------------------------------------------------------------------------------------------------------
s._canvas._chips[treasure.id].setChecked(False); pump(30)
check("filtro spento: i pin di quel tipo spariscono dalla mappa", not s._canvas._pins[chest.id].isVisible() and s._canvas._pins[edited.id].isVisible())
s._canvas.set_tool(ADD); click_map(s._canvas, 0.2, 0.8)
s._form._choose_type(treasure); s._form._name.setText("Altro forziere"); s._form._primary.click(); pump(150)
check("posare un pin di un tipo nascosto riaccende il filtro", s._canvas._chips[treasure.id].isChecked() and all(i.isVisible() for i in s._canvas._pins.values()))

# --- mappe che si aprono dai pin -------------------------------------------------------------------------------------------------------
def make_valle(d):
    d._name.setText("Valle dei Corvi"); d._choice.set_image(img_valle); d.accept()
s._select_pin(edited.id); pump(50)
s._edit_pin(s._pin(edited.id)); pump(50)
check("pin senza mappa: c'è il pulsante «Scegli o crea una mappa…»", not s._form._map_button.isHidden() and s._form._map_row.isHidden())
s._choose_map(); pump(50)
items = menu_items()
check("il menu delle mappe offre solo «Crea una nuova mappa…» (quella aperta non si può scegliere)", list(items) == ["Crea una nuova mappa…"])
drive(make_valle); choose("Crea una nuova mappa…"); pump(200)
valle = next(m for m in repo.maps() if m.name == "Valle dei Corvi")
check("la mappa creata dal pin sta dentro quella aperta", valle.parent_id == regno)
check("e diventa quella che il pin apre (nella finestrella)", s._form.data().opens_map_id == valle.id and not s._form._map_row.isHidden())
s._form._primary.click(); pump(150)
check("salvato: il pin apre la mappa", repo.pins(regno)[0].opens_map_id == valle.id)
card_button = next(b for b in s._canvas._card.findChildren(QAbstractButton) if b.text().strip().startswith("Apre la mappa"))
check("la finestrella di lettura dice quale mappa apre", "Valle dei Corvi" in card_button.text())
card_button.click(); pump(200)
check("clic: si apre quella mappa", s._map_id == valle.id and s._tree.currentItem().text(0) == "Valle dei Corvi" and w._location[2] == MapTarget(valle.id, None))
check("l'albero mostra la sottomappa dentro la prima", s._tree.topLevelItemCount() == 1 and s._tree.topLevelItem(0).childCount() == 1)
check("il pannello dice dove sta la mappa", "Regno di Aldoria" in s._panel._path.text() and s._panel._title.text() == "Valle dei Corvi")
w._topbar.back_clicked.emit(); pump(200)
check("indietro: di nuovo il Regno", s._map_id == regno)

# --- il menu «Apre la mappa»: nessuna ------------------------------------------------------------------------------------------------------
s._select_pin(edited.id); s._edit_pin(s._pin(edited.id)); pump(50)
s._choose_map(); pump(50)
check("con una mappa già scelta il menu offre «Nessuna mappa»", "Nessuna mappa" in menu_items())
choose("Nessuna mappa")
check("«Nessuna mappa» toglie la scelta", s._form.data().opens_map_id is None)
s._form.cancelled.emit(); pump(50)

# --- eliminare un pin ------------------------------------------------------------------------------------------------------------------------
before = len(repo.pins(regno))
s._edit_pin(s._pin(chest.id)); s._form.delete_confirmed.emit(); pump(150)
check("«Tieni premuto per eliminare» toglie il pin e chiude la finestrella", len(repo.pins(regno)) == before - 1 and not (s._canvas._card is not None) and s._selected is None)

# --- elenco delle mappe ----------------------------------------------------------------------------------------------------------------------------
s.show_target(None); pump(150)
check("senza bersaglio: l'elenco delle mappe, senza pannello destro", s._views.currentIndex() == 0 and not w._right_panel.isVisible() or not s.panel_visible())
cards = s._grid.findChildren(MapCard)
check("una scheda per mappa", len(cards) == 2)
check("le schede dicono quanti pin e dove stanno", any("pin · dentro Regno di Aldoria" in c._meta for c in cards) and any(c._meta.startswith(f"{len(repo.pins(regno))} pin") for c in cards))
cards[0].clicked.emit(); pump(150)
check("clic su una scheda apre la mappa", s._map_id == repo.maps()[0].id and s._views.currentIndex() == 1)

# --- menu della barra sinistra: sottomappa, modifica, elimina -------------------------------------------------------------------------------------
def sub_map(d):
    d._name.setText("Porto"); d.accept()
s._show_map_menu(regno, QPoint(300, 300)); pump(50)
check("il menu di una mappa ha modifica, sottomappa ed elimina", {"Modifica…", "Nuova sottomappa", "Elimina…"} <= set(menu_items()))
drive(sub_map); choose("Nuova sottomappa"); pump(200)
harbor = next(m for m in repo.maps() if m.name == "Porto")
check("«Nuova sottomappa» crea dentro quella scelta e la apre", harbor.parent_id == regno and s._map_id == harbor.id)

def delete_map(d):
    d.done(DELETE)
drive(delete_map); s._edit_map(s._map(harbor.id)); pump(200)
check("eliminata la mappa aperta: si torna all'elenco e sparisce il pannello", s._map_id is None and not w._right_panel.isVisible() and harbor.id not in {m.id for m in repo.maps()})

# --- dalla scheda del luogo --------------------------------------------------------------------------------------------------------------------------------
repo.create_pin(regno, 0.4, 0.4, PinInput(types[0].id, "", "", (links.PLACE, varen), valle.id))
w._go(repo.folder, "luoghi", ElementTarget(varen, True)); pump(200)
sheet = w._screens["luoghi"]._sheet
check("la scheda del luogo ha la scheda «Mappe»", "maps" in sheet._order)
sheet._tabs.select("maps"); pump(100)
page = sheet._pages.widget(sheet._order.index("maps"))
from gmjournal.ui.sheet.maps import _PinRow
rows = page.findChildren(_PinRow)
check("«Compare nelle mappe»: le mappe dove sta il luogo (due pin: quello di prima e questo)", len(rows) == 2)
cards = page.findChildren(MapCard)
check("«Mappa di questo luogo»: la mappa che si apre da lui", len(cards) == 1 and cards[0]._name == "Valle dei Corvi")
cards[0].action_clicked.emit(); pump(200)
check("«Apri la mappa» apre quella mappa", w._location[1] == "mappe" and s._map_id == valle.id)
w._topbar.back_clicked.emit(); pump(200)
sheet = w._screens["luoghi"]._sheet
page = sheet._pages.widget(sheet._order.index("maps"))
page.findChildren(_PinRow)[0].clicked.emit(); pump(200)
target_pin = repo.pins_linked_to(links.PLACE, varen)[0]
check("clic su una riga apre la mappa con quel pin scelto", s._map_id == target_pin.map_id and s._selected == target_pin.id)
w._topbar.back_clicked.emit(); pump(200)

sheet._show_on_map(); pump(100)
check("«Vedi sulla mappa» con più pin offre la scelta", len(menu_buttons()) == 2)
menu_buttons()[0].click(); pump(200)
check("…e apre la mappa scelta con il suo pin", w._location[1] == "mappe" and s._selected is not None)
w._topbar.back_clicked.emit(); pump(200)

# metterlo su un'altra mappa: si apre quella mappa, pronta a posare il pin collegato
sheet = w._screens["luoghi"]._sheet
page = sheet._pages.widget(sheet._order.index("maps"))
page._show_put_menu(); pump(50)
check("il menu elenca le mappe e «Crea una nuova mappa…»", {"Regno di Aldoria", "Regno di Aldoria › Valle dei Corvi", "Crea una nuova mappa…"} <= set(menu_items()))
choose("Regno di Aldoria › Valle dei Corvi")
check("si apre la mappa con «Aggiungi pin» già scelto", w._location[1] == "mappe" and s._map_id == valle.id and s._canvas._tool == ADD and s._armed is not None)
click_map(s._canvas, 0.5, 0.5)
check("al clic la finestrella parte già collegata al luogo", s._form._link is not None and s._form._link.id == varen)
s._form._primary.click(); pump(200)
check("il pin collegato è sulla mappa scelta e lo strumento si è spento", any(p.map_id == valle.id for p in repo.pins_linked_to(links.PLACE, varen)) and s._armed is None and s._canvas._tool == SELECT)
s._canvas.set_tool(ADD); click_map(s._canvas, 0.3, 0.3)
check("il pin successivo non è più collegato", s._form._link is None)
s._form.cancelled.emit(); pump(50)
s.show_target(MapTarget(valle.id, None, repo.link_target(links.PLACE, varen)))
s._canvas.set_tool(SELECT)
check("cambiare strumento toglie il collegamento in attesa", s._armed is None)

# senza pin: «Vedi sulla mappa» porta alla scheda «Mappe»
solo = repo.create_element(ElementInput(links.PLACE, "Torre sola", cat.id, None, "", ""))
w._screens["luoghi"].reload()          # l'elemento è nato fuori dalla schermata
w._go(repo.folder, "luoghi", ElementTarget(solo, True)); pump(150)
sheet = w._screens["luoghi"]._sheet
sheet._show_on_map(); pump(50)
check("luogo senza pin: «Vedi sulla mappa» mostra la scheda «Mappe»", sheet._order[sheet._pages.currentIndex()] == "maps")

# --- sfondo che non si legge ---------------------------------------------------------------------------------------------------------------------------------------
(repo.folder / img_valle).unlink()
w._go(repo.folder, "mappe"); w._go(repo.folder, "mappe", MapTarget(valle.id)); pump(100)
check("se il file dello sfondo manca, compare l'invito a sceglierlo (senza errori)", not s._canvas.has_image() and s._canvas._empty.isVisible())

# --- dalla libreria immagini --------------------------------------------------------------------------------------------------------------------------------
w._go(repo.folder, "immagini"); pump(200)
imgs = w._screens["immagini"]
image = next(i for i in repo.images() if i.path == img_valle)
imgs._selected = image.id; imgs.reload(); pump(50)
use = next(u for u in repo.image_uses(img_valle) if u.kind == links.MAP)
check("fra gli usi dell'immagine c'è la mappa", use.name == "Valle dei Corvi")
imgs._open_use(use); pump(200)
check("clic sull'uso: si apre la mappa", w._location[1] == "mappe" and s._map_id == valle.id)

# --- cronologia e ritorno alla schermata -----------------------------------------------------------------------------------------------------------------------------
w._go(repo.folder, "mappe"); pump(150)
check("il clic sulla voce «Mappe» della barra mostra l'elenco", s._map_id is None and s._views.currentIndex() == 0)
s._tree.selected.emit(regno); pump(100)
check("scegliere una mappa nell'albero la apre", s._map_id == regno and w._location[2] == MapTarget(regno, None))

# --- tutti i modi per creare o modificare una mappa aprono lo stesso popup -----------------------------------------------------------------------------------------------
from PySide6.QtWidgets import QPushButton, QToolButton
from gmjournal.ui.widgets.cards import NewCard
def cancel_and_note(log):
    def go(d):
        log.append(type(d).__name__ + ":" + d.windowTitle() if d.windowTitle() else type(d).__name__); d.reject()
    return go
w._go(repo.folder, "mappe"); pump(100)
before_maps = len(repo.maps())
log = []
header_button = next(b for b in s.findChildren(QPushButton) if b.text().strip() == "Nuova mappa")
for opener in (header_button.click, s._grid.findChildren(NewCard)[0].clicked.emit,
               next(b for b in s._sidebar_list.findChildren(QToolButton) if b.toolTip() == "Nuova mappa").click):
    drive(cancel_and_note(log)); opener(); pump(100)
check("«Nuova mappa» (pulsante, scheda tratteggiata, «+» della barra) apre il popup; annullando non si crea nulla",
      log == ["MapPopup"] * 3 and len(repo.maps()) == before_maps)
log.clear()
card = s._grid.findChildren(MapCard)[0]
drive(cancel_and_note(log)); card.edit_clicked.emit(); pump(100)
check("la matita sulla scheda apre «Modifica mappa»", log == ["MapPopup"])

# --- albero: aprire e chiudere i rami, il «⋯» -----------------------------------------------------------------------------------------------------------------------------------------
from gmjournal.ui.widgets.name_tree import _arrow_rect, _dots_rect
tree = s._tree
parent_item = tree.topLevelItem(0)
row = tree.visualItemRect(parent_item).adjusted(0, 1, 0, -1)
check("un ramo con sottomappe parte aperto", parent_item.isExpanded() and parent_item.childCount() >= 1)
QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=_arrow_rect(row, 0).center()); pump(50)
check("clic sulla freccia: si chiude", not parent_item.isExpanded())
s.reload(); pump(50)
check("ricostruendo l'albero il ramo resta chiuso", not tree.topLevelItem(0).isExpanded())
QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=_arrow_rect(tree.visualItemRect(tree.topLevelItem(0)).adjusted(0, 1, 0, -1), 0).center()); pump(50)
check("clic di nuovo: si riapre", tree.topLevelItem(0).isExpanded())
asked = []
tree.menu_requested.connect(lambda map_id, point: asked.append(map_id))
row = tree.visualItemRect(tree.topLevelItem(0)).adjusted(0, 1, 0, -1)
QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=_dots_rect(row).center()); pump(50)
check("il «⋯» chiede il menu di quella mappa", asked == [tree.topLevelItem(0).data(0, Qt.UserRole)])
for menu in [m for m in QApplication.topLevelWidgets() if isinstance(m, PopupMenu) and m.isVisible()]:
    menu.close()

# --- finestra piccola e molti tipi di pin: niente esce dalla mappa -------------------------------------------------------------
from gmjournal.ui.widgets.anchored_card import ScrollBody
w.resize(960, 600); pump(200)           # la finestra più piccola possibile
for n in range(10):
    repo.create_pin_type(f"Tipo di prova con un nome lungo {n + 1}", "map-pin", "blue")
w._go(repo.folder, "mappe", MapTarget(regno, None)); pump(300)
canvas, bar = s._canvas, s._canvas._filters
check("con molti tipi la barra dei filtri resta dentro la mappa (e scorre di lato)",
      bar.isVisible() and bar.geometry().left() >= 0 and bar.geometry().right() <= canvas.width() and len(canvas._chips) >= 14)
check("gli strumenti stanno sotto la barra dei filtri", canvas._tools.geometry().top() >= bar.geometry().bottom())
canvas.set_tool(ADD); click_map(canvas, 0.5, 0.5); pump(300)
check("pin nuovo con tanti tipi: la finestrella sta tutta nella mappa, con intestazione e pulsanti",
      isinstance(s._form, PinForm) and card_fits(canvas) and s._form._primary.isVisible() and s._form.height() <= canvas.height())
body = s._form.findChild(ScrollBody)
check("il contenuto che non ci sta scorre", body.verticalScrollBar().maximum() > 0)
small_height = s._form.height()
s._form.cancelled.emit(); pump(100)
w.resize(1440, 900); pump(200)
canvas.set_tool(ADD); click_map(canvas, 0.5, 0.5); pump(300)
check("a finestra grande la finestrella usa l'altezza che c'è e si vede intera", card_fits(canvas) and s._form.height() > small_height)
s._form.cancelled.emit(); pump(100)

# --- mappa che sparisce mentre si è altrove -----------------------------------------------------------------------------------------------------------------------------
repo.delete_map(regno)
w._go(repo.folder, "personaggi"); pump(100)
w._go(repo.folder, "mappe", MapTarget(regno, None)); pump(150)
check("un bersaglio che non esiste più mostra l'elenco, senza errori", s._map_id is None and s._views.currentIndex() in (0, 2))

print(f"{sum(ok)}/{len(ok)}")
