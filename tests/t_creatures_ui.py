"""Prove della schermata Incontri (schede tecniche): elenco e ricerca, scheda a destra, popup per compilare a mano, importazione da file XML
(con la conferma per i file grossi), modifica ed eliminazione, cronologia."""
from harness import *
app()
import tempfile
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel
from gmjournal.app import MainWindow
from gmjournal.data.models import Feature
from gmjournal.ui.popups.base import DELETE
from gmjournal.ui.popups.creature import CreaturePopup
from gmjournal.ui.encounter_target import CREATURES, EncounterTarget
from gmjournal.ui.widgets import creature_page

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def drive(fn, delay=80):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))

def texts(widget):
    return " | ".join(label.text() for label in widget.findChildren(QLabel))

def click_row(screen, number):
    view = screen._list
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.visualRect(view.model().index(number, 0)).center()); pump(80)

def press(box, label):
    next(b for b in box.buttons() if b.text() == label).click()

XML = """<?xml version="1.0"?><compendium>
<monster><name>Aboleth</name><size>L</size><type>aberration</type><alignment>Lawful Evil</alignment><ac>17 (natural armor)</ac><hp>135 (18d10+36)</hp>
<speed>walk 10 ft., swim 40 ft.</speed><str>21</str><dex>9</dex><con>15</con><int>18</int><wis>15</wis><cha>18</cha><save>Con +6</save><passive>20</passive>
<cr>10</cr><senses>darkvision 120 ft.</senses><trait><name>Amphibious</name><text>The aboleth can breathe air and water.</text></trait>
<action><name>Tail</name><text>Melee Weapon Attack: +9 to hit.</text></action><legendary><name>Detect</name><text>Wisdom check.</text></legendary>
<description>Lore &lt;b&gt;pericolosa&lt;/b&gt;.

Source: Monster Manual p. 13</description><environment>underdark</environment></monster>
<monster><name>Goblin</name><size>S</size><type>humanoid</type><cr>1/4</cr></monster>
<monster><name>Archmage</name><size>M</size><type>humanoid</type><cr>12</cr></monster></compendium>"""
xml_file = Path(tempfile.mkdtemp(prefix="gmj_cui_")) / "mostri.xml"
xml_file.write_text(XML, encoding="utf-8")

repo = new_repo("ProvaIncontri")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "incontri", EncounterTarget(CREATURES)); pump(200)
screen = w._screens["incontri"]
s = screen._pages[CREATURES]

# --- nessuna scheda ----------------------------------------------------------------------------------
check("la sezione Incontri si apre", "incontri" in w._screens and w._location[1] == "incontri")
check("senza schede: schermata di benvenuto, nessun pannello a destra", s._views.currentIndex() == 1 and not w._right_panel.isVisible())

# --- compilare a mano ----------------------------------------------------------------------------------
def fill(popup):
    assert isinstance(popup, CreaturePopup)
    check("nuova scheda: «Crea» è spento finché manca il nome", not popup._primary.isEnabled())
    popup._name.setText("Goblin Scout"); popup._size.set_options(popup._size._options, "Small")
    popup._kind.setText("humanoid"); popup._armor_class.setText("15"); popup._hit_points.setText("7 (2d6)")
    popup._abilities[1].setText("14"); popup._challenge.setText("1/4"); popup._passive.setText("9")
    popup._features[1]._add(Feature("action", "Scimitar", "Melee Weapon Attack."))
    popup._features[0]._add(Feature("trait", "Nimble Escape", "Hide as a bonus action."))
    check("nuova scheda: con il nome «Crea» si accende", popup._primary.isEnabled())
    check("nuova scheda: nessun pulsante per eliminare", not popup.footer_left.count())
    popup.accept()
drive(fill); s._create(); pump(200)
rows = repo.creatures()
check("creata: sta nell'elenco e nel database", [r.name for r in rows] == ["Goblin Scout"] and s._list.model().rowCount() == 1)
made = repo.creature(rows[0].id)
check("i dati del popup arrivano al database", (made.size, made.abilities[1], made.challenge, made.passive, [f.name for f in made.features]) == ("Small", 14, "1/4", 9, ["Nimble Escape", "Scimitar"]))
check("la scheda nuova è scelta e si vede a destra", s._selected == made.id and s._detail._details.isVisible() and "Goblin Scout" in texts(s._detail._block))
check("la cronologia ricorda la scheda", w._location[1] == "incontri" and w._location[2] == EncounterTarget(CREATURES, made.id))
block = texts(s._detail._block)
check("la scheda mostra difese, caratteristiche e capacità", all(x in block for x in ("Classe Armatura", "15", "14 (+2)", "Grado di sfida", "1/4 (50 PE)", "passive Perception 9", "Azioni", "Scimitar", "Nimble Escape")))
check("senza fonte né ambiente né descrizione non ci sono quei titoli", "FONTE" not in texts(s._detail) and "DESCRIZIONE" not in texts(s._detail))

# --- importare da file XML ---------------------------------------------------------------------------
creature_page.choose_compendium_files = lambda parent: [xml_file]
seen = []
def close_info(box):
    seen.append(box.text()); press(box, "OK")
drive(close_info, 150); s._import(); pump(200)
check("importate 3 schede", seen == ["Importate 3 schede"] and [r.name for r in repo.creatures()] == ["Aboleth", "Archmage", "Goblin", "Goblin Scout"])
check("l'elenco si aggiorna", s._list.model().rowCount() == 4)
seen.clear()
drive(close_info, 150); s._import(); pump(200)
check("riimportando: già tutte presenti", seen == ["Nessuna scheda nuova: erano già tutte presenti."] and len(repo.creatures()) == 4)

def warn_cancel(box):
    seen.append(box.text()); press(box, "Annulla")
creature_page.LARGE_FILE = 2
seen.clear()
repo.delete_creature(next(r.id for r in repo.creatures() if r.name == "Archmage")); pump(10)
drive(warn_cancel, 150); s._import(); pump(200)
check("file grosso: si chiede conferma, con il numero", len(seen) == 1 and "mostri.xml" in seen[0] and "3 schede" in seen[0] and "molto pesante" in seen[0])
check("annullando non si importa nulla", len(repo.creatures()) == 3)
def warn_go(box):
    press(box, "Importa comunque")
    QTimer.singleShot(150, lambda: close_info(QApplication.activeModalWidget()))
seen.clear()
drive(warn_go, 150); s._import(); pump(300)
check("confermando si importa (solo ciò che mancava)", seen == ["1 importata, 2 già presenti"] and len(repo.creatures()) == 4)
creature_page.LARGE_FILE = 300
creature_page.choose_compendium_files = lambda parent: [xml_file.with_name("manca.xml")]
errors = []
def close_error(box):
    errors.append(box.text()); press(box, "OK")
drive(close_error, 150); s._import(); pump(200)
check("file illeggibile: messaggio chiaro, nulla cambia", len(errors) == 1 and "manca.xml" in errors[0] and len(repo.creatures()) == 4)
creature_page.choose_compendium_files = lambda parent: []
s._import(); pump(50)
check("nessun file scelto: non succede nulla", len(repo.creatures()) == 4)

# --- elenco, ricerca, scelta ---------------------------------------------------------------------------
check("elenco in ordine alfabetico", [s._list.model().index(n, 0).data() for n in range(4)] == ["Aboleth", "Archmage", "Goblin", "Goblin Scout"])
click_row(s, 0)
check("clic su una riga: la scheda si vede a destra e la riga è evidenziata", "Aboleth" in texts(s._detail._block) and s._list.currentIndex().row() == 0)
check("la cronologia segue la scelta", w._location[2] == EncounterTarget(CREATURES, s._selected))
check("la scheda importata ha taglia, tipo e allineamento", "Large aberration, Lawful Evil" in texts(s._detail._block))
check("caratteristiche con i modificatori", "21 (+5)" in texts(s._detail._block) and "9 (−1)" in texts(s._detail._block))
check("il grado di sfida mostra i punti esperienza", "10 (5.900 PE)" in texts(s._detail._block))
check("i tratti non hanno titolo, azioni e azioni leggendarie sì", "Azioni leggendarie" in texts(s._detail._block) and "Tratti" not in texts(s._detail._block))
extra = texts(s._detail)
check("ambiente, fonte e descrizione stanno sotto la scheda", all(x in extra for x in ("AMBIENTE", "underdark", "FONTE", "Monster Manual p. 13", "DESCRIZIONE", "Lore")))
check("il testo non diventa mai codice", "&lt;b&gt;pericolosa&lt;/b&gt;" in texts(s._detail) and "<b>pericolosa" not in texts(s._detail))

s._search._edit.setText("gobl"); pump(50)
check("ricerca per nome", s._list.model().rowCount() == 2)
s._search._edit.setText("monster manual"); pump(50)
check("ricerca per fonte", s._list.model().rowCount() == 1)
s._search._edit.setText("large aberr"); pump(50)
check("ricerca per taglia e tipo", s._list.model().rowCount() == 1)
s._search._edit.setText("zzzz"); pump(50)
check("nessun risultato: lo dice", s._results.currentIndex() == 1)
s._search._edit.setText(""); pump(50)
check("ricerca svuotata: tornano tutte", s._list.model().rowCount() == 4 and s._results.currentIndex() == 0)

# --- modificare ed eliminare -----------------------------------------------------------------------------
def rename(popup):
    check("modifica: i campi sono quelli della scheda", popup._name.text() == "Aboleth" and popup._size.value() == "Large" and popup._abilities[0].text() == "21"
          and popup._passive.text() == "20")
    check("modifica: c'è il pulsante per eliminare", popup.footer_left.count() == 1)
    popup._name.setText("Aboleth Antico"); popup._features[1]._add(Feature("action", "Slam", "Hit."))
    popup.accept()
drive(rename); s._edit(); pump(200)
a = repo.creature(next(r.id for r in repo.creatures() if r.name == "Aboleth Antico"))
check("modificata: nuovo nome e capacità in più, ognuna nella sua sezione", [f.name for f in a.features] == ["Amphibious", "Tail", "Slam", "Detect"])
check("la scheda a destra segue il nome nuovo", "Aboleth Antico" in texts(s._detail._block))

def remove_feature(popup):
    row = popup._features[1]._rows.itemAt(0).widget()
    row.removed.emit(row)
    popup.accept()
drive(remove_feature); s._edit(); pump(200)
check("una capacità si toglie dal popup", "Tail" not in [f.name for f in repo.creature(a.id).features])

def erase(popup):
    popup.done(DELETE)
drive(erase); s._edit(); pump(200)
check("eliminata: sparisce dall'elenco e dalla scheda", "Aboleth Antico" not in [r.name for r in repo.creatures()] and s._selected is None and s._detail._hint.isVisible())
check("la cronologia sa che non c'è più nulla di scelto", w._location[2] == EncounterTarget(CREATURES, None))
click_row(s, 0)
drive(lambda popup: popup.reject()); s._edit(); pump(200)
check("annullando la modifica non cambia nulla", len(repo.creatures()) == 3)

# --- tornare indietro ------------------------------------------------------------------------------------------
click_row(s, 0); first = s._selected
click_row(s, 1); second = s._selected
w._topbar.back_clicked.emit(); pump(100)
check("«indietro» riporta alla scheda di prima", s._selected == first and s._list.currentIndex().row() == 0)
w._topbar.forward_clicked.emit(); pump(100)
check("«avanti» alla seguente", s._selected == second)

# --- aspetto ---------------------------------------------------------------------------------------------------------
w._go(repo.folder, "incontri", EncounterTarget(CREATURES, repo.creatures()[0].id)); pump(200)
shot(w, "incontri_100.png", (1440, 900))
check("lo screenshot è stato salvato", Path("incontri_100.png").exists())

print(f"{sum(ok)}/{len(ok)}")
