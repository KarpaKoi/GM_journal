"""Prove della schermata Incontri: le due pagine e il passaggio dall'una all'altra, creare un incontro dal popup (giocatori, schede, copie),
l'elenco nella barra sinistra, il dettaglio con la difficoltà e la riga delle sole schede che servono, il popup che sceglie le schede,
modifica, eliminazione, cronologia."""
from harness import *
app()
from PySide6.QtCore import QPoint, QPointF, QRect, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QToolButton
from gmjournal import theme
from gmjournal.app import MainWindow
from gmjournal.data.models import CreatureInput, EncounterInput, Feature, PartyGroup, Slot
from gmjournal.ui.encounter_target import CREATURES, ENCOUNTERS, EncounterTarget
from gmjournal.ui.popups.base import DELETE
from gmjournal.ui.popups.creature import CreaturePopup
from gmjournal.ui.popups.creature_picker import CreaturePickerPopup
from gmjournal.ui.popups.encounter import EncounterPopup
from gmjournal.ui.widgets.stat_block import StatBlock

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def drive(fn, delay=80):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))

def texts(widget):
    """Tutte le scritte che si vedono in un widget (quelle nascoste non contano)."""
    return " | ".join(label.text() for label in widget.findChildren(QLabel) if label.isVisibleTo(widget))

def caption_of(page, name):
    """La riga di descrizione che l'elenco mostra sotto il nome di una voce (con, in coda, la parola colorata se c'è)."""
    model = page._list.model()
    index = next(model.index(i, 0) for i in range(model.rowCount()) if model.index(i, 0).data() == name)
    return " · ".join(part for part in (index.data(Qt.UserRole + 1), index.data(Qt.UserRole + 3)) if part)

def tag_color_of(page, name):
    model = page._list.model()
    return next(model.index(i, 0).data(Qt.UserRole + 4) for i in range(model.rowCount()) if model.index(i, 0).data() == name)

def wheel(widget, dx=0, dy=0, shift=False):
    """Un giro di rotella (o un gesto laterale) sopra `widget`; dice se qualcuno l'ha usato."""
    point = QPointF(widget.viewport().rect().center())
    event = QWheelEvent(point, point, QPoint(0, 0), QPoint(dx, dy), Qt.NoButton, Qt.ShiftModifier if shift else Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(widget.viewport(), event)
    return event.isAccepted()

def click_item(view, name):
    """Un clic vero sulla voce di un elenco, trovata per nome."""
    model = view.model()
    row = next(i for i in range(model.rowCount()) if model.index(i, 0).data() == name)
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(model.index(row, 0)).center()); pump(50)

def click_row(page, number):
    view = page._list
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(view.model().index(number, 0)).center()); pump(80)

def click_switch(screen, number):
    QTest.mouseClick(screen._switch, Qt.LeftButton, pos=QPoint(2 + number * 130 + 65, 16)); pump(150)

def creature(name, challenge, size="Medium"):
    return CreatureInput(name, size, "humanoid", "", "15", "7 (2d6)", "walk 30 ft.", (10,) * 6, "", "", "", "", "", "", "", 9, "", challenge, "", "", "", ())

repo = new_repo("ProvaIncontriUI")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "incontri"); pump(200)
screen = w._screens["incontri"]
enc, cre = screen._pages[ENCOUNTERS], screen._pages[CREATURES]

# --- niente di niente ------------------------------------------------------------------------------------
check("la sezione si apre sulla pagina degli incontri", screen._page == ENCOUNTERS and screen._title.text() == "Incontri" and w._location[2] == EncounterTarget(ENCOUNTERS, None))
check("senza incontri: schermata di benvenuto", enc._views.currentIndex() == 1)
check("i pulsanti sono quelli degli incontri", enc.buttons.isVisibleTo(screen) and not cre.buttons.isVisibleTo(screen))
new_button = enc.buttons.findChildren(QPushButton)[0]
check("«Nuovo incontro» ha la sua misura (alto 38, largo quanto il testo, non quanto i due pulsanti delle schede)",
      new_button.height() == 38 and new_button.width() <= new_button.sizeHint().width() + 4 and new_button.width() < 200)

# --- passare alle schede e tornare -------------------------------------------------------------------------
click_switch(screen, 1)
check("«Schede tecniche»: cambiano pagina e pulsanti, il titolo resta «Incontri»", screen._page == CREATURES and screen._title.text() == "Incontri" and cre.buttons.isVisibleTo(screen) and not enc.buttons.isVisibleTo(screen))
check("il passaggio entra nella cronologia", w._location[2] == EncounterTarget(CREATURES, None))
goblin = repo.create_creature(creature("Goblin", "1/4", "Small"))
ogre = repo.create_creature(creature("Ogre", "2", "Large"))
wolf = repo.create_creature(creature("Wolf", "1/4"))
mage = repo.create_creature(creature("Archmage", "12"))
unknown = repo.create_creature(creature("Mistero", ""))
click_switch(screen, 0)
check("«Incontri»: si torna", screen._page == ENCOUNTERS and w._location[2] == EncounterTarget(ENCOUNTERS, None))
w._topbar.back_clicked.emit(); pump(100)
check("«indietro» riporta alle schede, «avanti» agli incontri", screen._page == CREATURES)
w._topbar.forward_clicked.emit(); pump(100)
check("…e «avanti» agli incontri", screen._page == ENCOUNTERS)

# --- creare un incontro di combattimento dal popup ------------------------------------------------------------
def build(popup):
    assert isinstance(popup, EncounterPopup)
    check("nuovo incontro: «Crea» è spento finché manca il nome", not popup._primary.isEnabled())
    check("nuovo incontro: parte come combattimento con un gruppo di giocatori", popup._kind == "combat" and popup._party_box.isVisibleTo(popup)
          and len(popup._party.rows()) == 1)
    popup._name.setText("Imboscata dei goblin")
    check("con il nome «Crea» si accende", popup._primary.isEnabled())
    row = popup._party.rows()[0]
    row._count.setText("4"); row._level.setText("3")

    def pick(picker):
        check("il popup delle schede mostra tutte le schede", picker._list.model().rowCount() == 5)
        picker._toggle(goblin); picker._toggle(ogre)
        check("scegliendo: il pulsante dice quante", picker._primary.text() == "Aggiungi 2 schede" and picker._primary.isEnabled())
        picker._toggle(ogre)
        check("togliendo una scelta il numero scende", picker._primary.text() == "Aggiungi 1 scheda")
        picker._toggle(ogre)
        picker.accept()
    QTimer.singleShot(150, lambda: pick(QApplication.activeModalWidget()))
    popup._add_creatures()
    check("le schede scelte compaiono nel popup, ognuna con una copia", [r.creature_id for r in popup._slots.rows()] == [goblin, ogre]
          and [r.slot().quantity for r in popup._slots.rows()] == [1, 1])
    popup._slots.rows()[0]._quantity.setText("4")
    popup.accept()
drive(build); enc.create(); pump(200)
found = repo.encounters()
check("creato: nel database con giocatori e schede", len(found) == 1 and (found[0].name, found[0].kind, found[0].party, found[0].creatures) ==
      ("Imboscata dei goblin", "combat", (PartyGroup(3, 4),), (Slot(goblin, 4), Slot(ogre, 1))))
eid = found[0].id
check("è scelto, in elenco e nella cronologia", enc._selected == eid and enc._list.model().rowCount() == 1
      and w._location[2] == EncounterTarget(ENCOUNTERS, eid))
detail = texts(enc._encounter)
check("il dettaglio ha nome e tipo", "Imboscata dei goblin" in detail and "Combattimento" in detail)
# 4 goblin (50) + 1 orco (450) = 650 PE, 5 mostri ×2 = 1.300; soglie di 4 giocatori di livello 3: 300 / 600 / 900 / 1.600 → difficile
check("difficoltà: Difficile, 1.300 PE modificati", "Difficile" in detail and "1.300 PE modificati" in detail)
tip = enc._encounter._difficulty._numbers.toolTip()
check("le soglie del gruppo si leggono passando il mouse sulla barra", all(x in tip for x in ("Facile", "300", "Medio", "600", "900", "Mortale", "1.600")))
check("il calcolo passo per passo, piccolo", "650 PE dei mostri ×2 (5 mostri)" in detail and "4 giocatori di livello 3" in detail)
blocks = enc._encounter.findChildren(StatBlock)
check("solo le schede dell'incontro, una per scheda, nell'ordine dell'incontro", len(blocks) == 2 and "Goblin" in texts(blocks[0]) and "Ogre" in texts(blocks[1]))
check("sopra ogni scheda: quante copie e quanti PE", "×4 · 50 PE ciascuno".upper() in detail.upper() and "×1 · 450 PE ciascuno".upper() in detail.upper())
check("la riga dell'elenco dice creature e difficoltà (colorata)", caption_of(enc, "Imboscata dei goblin") == "5 creature · Difficile"
      and tag_color_of(enc, "Imboscata dei goblin") == theme.DIFFICULTY_COLORS["hard"])

# --- modificare: più giocatori, un'altra scheda --------------------------------------------------------------
def more(popup):
    check("modifica: i campi sono quelli dell'incontro", popup._name.text() == "Imboscata dei goblin" and popup._party.rows()[0]._count.text() == "4"
          and [r._quantity.text() for r in popup._slots.rows()] == ["4", "1"] and popup.footer_left.count() == 1)
    popup._party.rows()[0]._count.setText("6")
    def pick(picker):
        click_item(picker._list, "Goblin")      # una scheda già nell'incontro non si sceglie
        check("una scheda già presente è attenuata e non si sceglie", picker._marked == [] and "già nell'incontro" in caption_of(picker, "Goblin"))
        picker._search._edit.setText("wolf"); pump(50)
        check("la ricerca nel popup delle schede", picker._list.model().rowCount() == 1)
        picker._toggle(wolf)
        picker._search._edit.setText(""); pump(50)
        check("la scelta resta cambiando la ricerca", picker._marked == [wolf] and picker._primary.text() == "Aggiungi 1 scheda")
        picker.accept()
    QTimer.singleShot(150, lambda: pick(QApplication.activeModalWidget()))
    popup._add_creatures()
    popup.accept()
drive(more); enc._edit(); pump(200)
e = repo.encounter(eid)
check("modificato: giocatori e schede nuovi", e.party == (PartyGroup(3, 6),) and e.creatures == (Slot(goblin, 4), Slot(ogre, 1), Slot(wolf, 1)))
detail = texts(enc._encounter)
# 650 + 50 = 700 PE, 6 mostri ×2 = 1.400; 6 giocatori: ×2 → ×1,5 = 1.050 → soglie 6×(75, 150, 225, 400) = 450 / 900 / 1.350 / 2.400 → difficile
check("6 giocatori: il moltiplicatore scende di un gradino e il calcolo segue", "700 PE dei mostri ×1,5 (6 mostri, gruppo grande)" in detail and "1.050 PE modificati" in detail
      and "Medio" in detail and len(enc._encounter.findChildren(StatBlock)) == 3)

# --- la riga delle schede: ognuna alta quanto serve, la riga scorre di lato ------------------------------------------------------------
cards = enc._encounter._cards
blocks = enc._encounter.findChildren(StatBlock)
check("le schede stanno una accanto all'altra, larghe uguali, a partire da sinistra", len({b.width() for b in blocks}) == 1 and blocks[0].width() == 400
      and blocks[0].mapTo(enc._encounter, QPoint(0, 0)).y() == blocks[1].mapTo(enc._encounter, QPoint(0, 0)).y()
      and blocks[0].mapTo(enc._encounter, QPoint(0, 0)).x() < blocks[1].mapTo(enc._encounter, QPoint(0, 0)).x() < blocks[2].mapTo(enc._encounter, QPoint(0, 0)).x())
check("tre schede da 400 non ci stanno nella finestra: la riga scorre di lato", cards.horizontalScrollBar().maximum() > 0 and cards.verticalScrollBar().maximum() == 0)
check("la riga è alta quanto la scheda più alta (e la barra), non una misura fissa", cards.height() >= max(b.height() for b in blocks))
before = cards.horizontalScrollBar().value()
check("Maiusc+rotella scorre le schede di lato", wheel(cards, dy=-120, shift=True) and cards.horizontalScrollBar().value() > before)
check("il gesto laterale (trackpad) pure", wheel(cards, dx=120) and cards.horizontalScrollBar().value() == before)
check("la rotella da sola non è della riga: scorre la pagina", not wheel(cards, dy=-120) and cards.horizontalScrollBar().value() == before)

# --- un incontro di interazione ---------------------------------------------------------------------------------------
def talk(popup):
    popup._name.setText("Il mercante")
    popup._choose_kind("interaction")
    check("interazione: i giocatori spariscono dal popup", not popup._party_box.isVisibleTo(popup))
    def pick(picker):
        picker._toggle(mage); picker.accept()
    QTimer.singleShot(150, lambda: pick(QApplication.activeModalWidget()))
    popup._add_creatures()
    popup.accept()
drive(talk); enc.create(); pump(200)
talk_e = next(x for x in repo.encounters() if x.name == "Il mercante")
check("interazione: nel database senza giocatori", talk_e.kind == "interaction" and talk_e.party == () and talk_e.creatures == (Slot(mage, 1),))
detail = texts(enc._encounter)
check("interazione: nessuna difficoltà, solo la scheda necessaria", "Interazione" in detail and not enc._encounter._difficulty.isVisibleTo(enc._encounter)
      and len(enc._encounter.findChildren(StatBlock)) == 1 and "×" not in detail)
check("la riga dell'elenco non parla di difficoltà", caption_of(enc, "Il mercante") == "Interazione · 1 creatura")
def peek(popup):
    check("…un nuovo incontro riparte dai giocatori dell'ultimo combattimento", [(r._count.text(), r._level.text()) for r in popup._party.rows()] == [("6", "3")])
    popup.reject()
drive(peek); enc.create(); pump(200)

# --- schede alte e basse insieme: ognuna alta quanto il suo testo ------------------------------------------------------------------------------
tall = repo.create_creature(CreatureInput("Drago", "Huge", "dragon", "", "19", "256", "walk 40 ft.", (10,) * 6, "", "", "", "", "", "", "", 9, "", "17", "", "", "",
                                          tuple(Feature("action", f"Attacco {n}", "Un attacco con gli artigli, la coda e le fauci, e poi un soffio terribile. " * 3) for n in range(4))))
mix = repo.create_encounter(EncounterInput("Alto e basso", "combat", (PartyGroup(5, 4),), (Slot(wolf, 1), Slot(tall, 1))))
enc.reload(); enc.show_id(mix); pump(150)
low, high = enc._encounter.findChildren(StatBlock)
check("ogni scheda è alta quanto il suo testo: la bassa non si allunga fino alla più alta", low.height() < high.height() and low.height() < 450
      and low.mapTo(enc._encounter, QPoint(0, 0)).y() == high.mapTo(enc._encounter, QPoint(0, 0)).y())
check("la riga è alta come la più alta e la scheda alta si vede per intero (si scorre la pagina, non la scheda)",
      enc._encounter._cards.height() >= high.height() and enc._encounter.verticalScrollBar().maximum() > 0
      and high.mapTo(enc._encounter._cards.widget(), QPoint(0, 0)).y() + high.height() <= enc._encounter._cards.widget().height())
enc.show_id(eid); pump(100)

# --- schede senza grado di sfida, nessun giocatore, nessuna scheda ---------------------------------------------------------
odd = repo.create_encounter(EncounterInput("Strano", "combat", (PartyGroup(2, 3),), (Slot(unknown, 2), Slot(goblin, 1))))
enc.reload(); enc.show_id(odd); pump(100)
detail = texts(enc._encounter)
check("creature senza grado di sfida: avvisa e non le conta", "50 PE dei mostri ×1 (1 mostro). 2 creature senza grado di sfida non contano." in detail
      and "50 PE modificati" in detail and "Banale" in detail)
nobody = repo.create_encounter(EncounterInput("Senza giocatori", "combat", (), (Slot(goblin, 1),)))
enc.reload(); enc.show_id(nobody); pump(100)
check("senza giocatori: lo dice e non calcola", "Scrivi i giocatori presenti" in texts(enc._encounter) and not enc._encounter._difficulty._numbers.isVisibleTo(enc._encounter))
check("…e nell'elenco non c'è nessuna difficoltà", caption_of(enc, "Senza giocatori") == "Combattimento · 1 creatura")
empty = repo.create_encounter(EncounterInput("Vuoto", "combat", (PartyGroup(2, 3),), ()))
enc.reload(); enc.show_id(empty); pump(100)
check("senza schede: lo dice, nessun blocco, nessuna difficoltà", "non ha ancora schede tecniche" in texts(enc._encounter) and not enc._encounter.findChildren(StatBlock)
      and "Aggiungi schede con un grado di sfida" in texts(enc._encounter))

# --- l'elenco nella barra sinistra -------------------------------------------------------------------------------------------------
side = w._sidebar_lists["incontri"]
check("l'elenco degli incontri sta nella barra sinistra, sotto le voci delle sezioni", w._sidebar.isAncestorOf(enc._list) and side.isVisibleTo(w)
      and not screen.isAncestorOf(enc._list) and "INCONTRI" in texts(side) and not enc._search.isVisibleTo(w))
check("in pagina non c'è più nessuna colonna a sinistra: il dettaglio prende tutto", enc._encounter.geometry().left() == 0)
check("nella barra ci sono tutti gli incontri", enc._list.model().rowCount() == len(repo.encounters()))
check("la schermata delle schede ha ancora il suo elenco con la ricerca in pagina", screen.isAncestorOf(cre._list) and cre._search.isVisibleTo(cre))
check("la riga di un combattimento senza giocatori non dice la difficoltà, quella di un'interazione sì il tipo",
      caption_of(enc, "Senza giocatori") == "Combattimento · 1 creatura" and tag_color_of(enc, "Senza giocatori") == "")

# --- scelta con il mouse e cronologia ------------------------------------------------------------------------------------------
click_row(enc, 0)
first = enc._selected
click_row(enc, 1)
second = enc._selected
check("clic su una riga: l'incontro compare a destra e va nella cronologia", first != second and w._location[2] == EncounterTarget(ENCOUNTERS, second))
w._topbar.back_clicked.emit(); pump(100)
check("«indietro» riporta all'incontro di prima", enc._selected == first)
w._topbar.forward_clicked.emit(); pump(100)
check("«avanti» al seguente", enc._selected == second)
w._go(repo.folder, "incontri", EncounterTarget(ENCOUNTERS, 99999)); pump(100)
check("una voce che non c'è più si ignora", enc._selected == second)

# --- la schermata iniziale: l'elenco di tutti gli incontri ---------------------------------------------------------------------------------------
home, table = enc._home, enc._home._table
def back_to_list():
    """Un clic vero sul titolo grande «Incontri»."""
    QTest.mouseClick(screen._title, Qt.LeftButton); pump(100)
def line_of(name):
    return next(x for x in table._lines if x.name == name)
def click_table(y):
    QTest.mouseClick(table, Qt.LeftButton, pos=QPoint(60, y)); pump(100)
w._sidebar._buttons["incontri"].click(); pump(150)       # la voce «Incontri» della barra riporta all'elenco
check("la voce «Incontri» della barra porta alla schermata iniziale, senza nulla di scelto (e va nella cronologia)",
      enc._content.currentWidget() is home and enc._selected is None and not enc._list.currentIndex().isValid() and w._location[2] == EncounterTarget(ENCOUNTERS, None))
check("l'elenco ha una riga per incontro, nello stesso ordine della barra", table._count == len(repo.encounters()) == enc._list.model().rowCount()
      and [x.name for x in table._lines] == [enc._list.model().index(i, 0).data() for i in range(enc._list.model().rowCount())])
check("combattimento: creature, giocatori e difficoltà", (line_of("Imboscata dei goblin").creatures, line_of("Imboscata dei goblin").players, line_of("Imboscata dei goblin").difficulty)
      == ("6 creature", "6 giocatori · liv. 3", "medium"))
check("interazione: nessun giocatore e nessuna difficoltà", (line_of("Il mercante").kind, line_of("Il mercante").players, line_of("Il mercante").difficulty) == ("interaction", "", None))
check("senza giocatori e senza schede lo dice a parole", line_of("Senza giocatori").players == "nessun giocatore" and line_of("Vuoto").creatures == "nessuna scheda")
check("la tabella è alta quanto le righe e sta nella larghezza della pagina", table.height() == 38 + 56 * table._count + 2 and table.width() <= home.viewport().width())
check("nell'intestazione e fuori dalle righe non c'è nessuna riga", table.index_at(5) == -1 and table.index_at(table.height() - 1) == -1
      and table.index_at(table.top(0) + 5) == 0 and table.index_at(table.top(2) + 5) == 2)
cells = table._cells(QRect(0, 0, table.width(), 56))
check("le cinque colonne non si sovrappongono e restano nella riga", len(cells) == 5 and all(a.right() < b.left() for a, b in zip(cells, cells[1:]))
      and cells[0].width() > 100 and cells[-1].right() <= table.width())
click_table(5)
check("un clic sull'intestazione non apre nulla", enc._content.currentWidget() is home and enc._selected is None)
click_table(table.top(1) + 20)
chosen = table._lines[1].id
check("un clic su una riga apre quell'incontro, lo evidenzia nella barra e va nella cronologia", enc._content.currentWidget() is enc._encounter and enc._selected == chosen
      and enc._list.currentIndex().data() == table._lines[1].name and w._location[2] == EncounterTarget(ENCOUNTERS, chosen))
check("il titolo «Incontri» è cliccabile (mano) e sopra l'incontro non c'è nessun altro pulsante per tornare", screen._title.cursor().shape() == Qt.PointingHandCursor
      and not enc._encounter.findChildren(QToolButton))
back_to_list()
check("un clic sul titolo riporta all'elenco, senza voce evidenziata, e va nella cronologia", enc._content.currentWidget() is home and enc._selected is None
      and not enc._list.currentIndex().isValid() and w._location[2] == EncounterTarget(ENCOUNTERS, None))
w._topbar.back_clicked.emit(); pump(100)
check("«indietro» riapre l'incontro", enc._content.currentWidget() is enc._encounter and enc._selected == chosen)
w._topbar.back_clicked.emit(); pump(100)
check("…e ancora «indietro» torna all'elenco", enc._content.currentWidget() is home and enc._selected is None)
w._topbar.forward_clicked.emit(); pump(100)
check("«avanti» riapre l'incontro", enc._content.currentWidget() is enc._encounter and enc._selected == chosen)
w._sidebar._buttons["incontri"].click(); pump(150)
check("dalla barra, con un incontro aperto, si torna all'elenco", enc._content.currentWidget() is home and enc._selected is None)
click_table(table.top(0) + 20)
click_item(enc._list, "Il mercante")
check("…un clic su un incontro della barra lo apre direttamente", enc._content.currentWidget() is enc._encounter and enc._selected == talk_e.id)
click_switch(screen, 1)
click_switch(screen, 0)
check("passando alle schede e tornando, la pagina degli incontri è dove l'avevi lasciata", enc._content.currentWidget() is enc._encounter and enc._selected == talk_e.id)
back_to_list()
before = table._count
drive(lambda popup: (popup._name.setText("Dall'elenco"), popup.accept()))
enc.create(); pump(250)
from_home = next(x for x in repo.encounters() if x.name == "Dall'elenco")
check("«Nuovo incontro» crea e apre l'incontro", enc._selected == from_home.id and enc._content.currentWidget() is enc._encounter)
back_to_list()
check("tornando all'elenco c'è anche il nuovo incontro", table._count == before + 1 and line_of("Dall'elenco").kind == "combat")

before_history = w._location
back_to_list()
check("sull'elenco un clic sul titolo non fa niente (nessuna voce in più nella cronologia)", w._location == before_history and enc._content.currentWidget() is home)
click_switch(screen, 1)
enc.show_id(second)
click_switch(screen, 1)
back_to_list()
check("dalle schede tecniche il titolo porta all'elenco degli incontri, e va nella cronologia", screen._page == ENCOUNTERS and enc._content.currentWidget() is home
      and enc._selected is None and w._location[2] == EncounterTarget(ENCOUNTERS, None))
w._topbar.back_clicked.emit(); pump(100)
check("«indietro» riporta alle schede tecniche", screen._page == CREATURES)
click_switch(screen, 0)

# --- gli incontri dalla barra, mentre si guardano le schede --------------------------------------------------------------------------------------
enc.show_id(second); pump(50)
click_switch(screen, 1); pump(100)
check("guardando le schede l'elenco degli incontri resta nella barra, senza voce evidenziata (e la scelta non si perde)",
      side.isVisibleTo(w) and not enc._list.currentIndex().isValid() and enc.current_id() == second and screen._page == CREATURES)
click_item(enc._list, "Il mercante")
check("un clic su un incontro porta alla pagina degli incontri con quell'incontro, e va nella cronologia",
      screen._page == ENCOUNTERS and screen._title.text() == "Incontri" and enc._selected == talk_e.id and w._location[2] == EncounterTarget(ENCOUNTERS, talk_e.id)
      and enc._list.currentIndex().isValid() and "Il mercante" in texts(enc._encounter))
click_switch(screen, 1)
click_item(enc._list, "Il mercante")
check("…anche se era già l'incontro scelto", screen._page == ENCOUNTERS and enc._selected == talk_e.id)
click_switch(screen, 1)
drive(lambda popup: (popup._name.setText("Dalla barra"), popup.accept()))
side.findChild(QToolButton).click(); pump(250)
bar_e = next(x for x in repo.encounters() if x.name == "Dalla barra")
check("il «+» della barra crea un incontro, lo sceglie e porta alla pagina degli incontri", screen._page == ENCOUNTERS and enc._selected == bar_e.id
      and w._location[2] == EncounterTarget(ENCOUNTERS, bar_e.id))

# --- le schede e gli incontri che le usano ---------------------------------------------------------------------------------------------
click_switch(screen, 1)
cre.show_id(goblin); pump(100)
seen = []
def note(popup):
    assert isinstance(popup, CreaturePopup)
    seen.append(texts(popup)); popup.reject()
drive(note); cre._edit(); pump(200)
check("modificando una scheda usata, il popup dice dove", len(seen) == 1 and "usata in 3 incontri" in seen[0] and "Imboscata dei goblin" in seen[0] and "eliminandola sparisce anche da lì" in seen[0])
cre.show_id(mage); pump(100)
def erase(popup):
    popup.done(DELETE)
seen.clear()
drive(erase); cre._edit(); pump(200)
check("una scheda non più usata: eliminata", mage not in [r.id for r in repo.creatures()])
cre.show_id(ogre); pump(100)
before = caption_of(enc, "Imboscata dei goblin")
drive(erase); cre._edit(); pump(200)
check("cambiando le schede si aggiorna anche l'elenco degli incontri nella barra (e resta senza voce evidenziata)",
      before.startswith("6 creature") and caption_of(enc, "Imboscata dei goblin").startswith("5 creature") and not enc._list.currentIndex().isValid())
click_switch(screen, 0)
enc.show_id(eid); pump(100)
check("eliminata una scheda, sparisce dall'incontro che la usava", repo.encounter(eid).creatures == (Slot(goblin, 4), Slot(wolf, 1)) and len(enc._encounter.findChildren(StatBlock)) == 2)
check("l'incontro di interazione, rimasto senza schede, lo dice", "non ha ancora schede tecniche" in (enc.show_id(talk_e.id), texts(enc._encounter))[1])

# --- eliminare un incontro ------------------------------------------------------------------------------------------------------------
enc.show_id(eid); pump(100)
drive(erase); enc._edit(); pump(200)
check("eliminato: sparisce dall'elenco e dal dettaglio, le schede restano", eid not in [x.id for x in repo.encounters()] and enc._selected is None
      and enc._content.currentWidget() is enc._home and goblin in [r.id for r in repo.creatures()])
check("la cronologia sa che non c'è più nulla di scelto", w._location[2] == EncounterTarget(ENCOUNTERS, None))
enc.show_id(talk_e.id)
drive(lambda popup: popup.reject()); enc._edit(); pump(200)
check("annullando la modifica non cambia nulla", talk_e.id in [x.id for x in repo.encounters()])

# --- popup: giocatori incompleti, nessuna scheda --------------------------------------------------------------------------------------------
def sloppy(popup):
    popup._name.setText("Disordine")
    popup._party.rows()[0]._count.setText("")
    popup._party.rows()[0]._level.setText("99")
    popup.accept()
drive(sloppy); enc.create(); pump(200)
sloppy_e = next(x for x in repo.encounters() if x.name == "Disordine")
check("un gruppo con un campo vuoto non conta", sloppy_e.party == ())
def levels(popup):
    popup._name.setText("Livelli"); popup._party.rows()[0]._count.setText("2"); popup._party.rows()[0]._level.setText("99")
    popup.accept()
drive(levels); enc.create(); pump(200)
check("un livello fuori dai limiti rientra", next(x for x in repo.encounters() if x.name == "Livelli").party == (PartyGroup(20, 2),))
def remove_group(popup):
    popup._name.setText("Senza gruppo")
    row = popup._party.rows()[0]
    row.removed.emit(row)
    check("togliere un gruppo (la «x»)", popup._party.rows() == [])
    popup.accept()
drive(remove_group); enc.create(); pump(200)
check("un combattimento senza gruppi si può creare", next(x for x in repo.encounters() if x.name == "Senza gruppo").party == ())

# --- con nessuna scheda il popup delle schede lo dice ----------------------------------------------------------------------------------------
repo2 = new_repo("ProvaIncontriVuota")
picker = CreaturePickerPopup(w, repo2.creatures(), set())
check("senza schede, il popup spiega cosa fare", "Non ci sono ancora schede tecniche" in texts(picker) and not picker._primary.isEnabled())
picker.reject()

print(f"{sum(ok)}/{len(ok)}")
