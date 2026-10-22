"""Prove del backup nella Home: pulsante «Ripristina da backup…», voce «Salva backup…» del menu «⋯», popup di avanzamento,
finestre di scelta file (quelle di Qt, pilotate), errori. Le finestre di sistema vere di Windows non si provano qui."""
from harness import *
app()
import tempfile, zipfile
from pathlib import Path
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QFileDialog, QFrame, QLabel, QLineEdit, QMessageBox, QPushButton, QToolButton
import gmjournal.data.repository as repo_mod
import gmjournal.ui.popups.progress as progress_mod
import gmjournal.ui.screens.home as home_mod
from gmjournal.app import MainWindow
from gmjournal.data.backup import backup_filename
from gmjournal.data.models import CampaignInput
from gmjournal.data.repository import Repository, unique_folder
from gmjournal.ui import backup_files
from gmjournal.ui.popups.progress import ProgressPopup, run_with_progress
from gmjournal.ui.widgets.cards import CampaignCard
from gmjournal.ui.widgets.menu import PopupMenu

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

timers = []
def drive(fn):
    """Appena la finestra di scelta file è aperta, la pilota con `fn` (la prima volta Qt ci mette un po' a mostrarla)."""
    timer = QTimer(); timer.setInterval(40); timers.append(timer)
    def tick():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QFileDialog) and dialog.isVisible():
            timer.stop(); fn(dialog)
    timer.timeout.connect(tick); timer.start()

tmp = Path(tempfile.mkdtemp(prefix="gmj_backup_ui_"))
root = tmp / "campagne"
repo_mod.campaigns_root = lambda: root          # le campagne di queste prove stanno qui
out = tmp / "backup"; out.mkdir()
cover = tmp / "copertina.png"
img = QImage(300, 200, QImage.Format_RGB32); img.fill(QColor("#335577")); img.save(str(cover))

# I messaggi (informazioni ed errori) si raccolgono invece di aprire finestre che nessuno chiude.
messages = []
QMessageBox.information = staticmethod(lambda parent, title, text, *a: messages.append(("info", text)) or QMessageBox.Ok)
QMessageBox.warning = staticmethod(lambda parent, title, text, *a: messages.append(("warn", text)) or QMessageBox.Ok)

# Le finestre di sistema si sostituiscono con una risposta decisa dalla prova.
answers = {"destination": None, "source": None}
asked = []
def fake_destination(parent, name):
    asked.append(("destination", name)); return answers["destination"]
def fake_source(parent):
    asked.append(("source", None)); return answers["source"]
home_mod.ask_backup_destination = fake_destination
home_mod.ask_backup_source = fake_source

aurora = Repository.create(unique_folder("Aurora"), CampaignInput("Aurora", "Prima campagna", "violet", cover))
aurora.create_page("Capitolo uno")
aurora.close()
cenere = Repository.create(unique_folder("Cenere"), CampaignInput("Cenere", "", "green", None)); cenere.close()

w = MainWindow(); w.resize(1440, 900); w.show(); pump(150)
home = w._home

def cards():
    return {c._name: c for c in home._grid._cards if isinstance(c, CampaignCard)}

def restore_button():
    return next((b for b in home.findChildren(QPushButton) if "Ripristina da backup" in b.text()), None)

def menu_items():
    menus = [m for m in QApplication.topLevelWidgets() if isinstance(m, PopupMenu) and m.isVisible()]
    return {b.text(): b for b in menus[-1].findChildren(QAbstractButton)} if menus else {}

def open_card_menu(name):
    button = cards()[name].findChild(QToolButton, "CardMenuButton")
    QTest.mouseClick(button, Qt.LeftButton); pump(80)

def click(widget):
    QTest.mouseClick(widget, Qt.LeftButton); pump(200)

# ---------- il pulsante «Ripristina da backup…» ----------
button = restore_button()
grid = home._grid
check("c'è il pulsante «Ripristina da backup…», con icona e suggerimento", button is not None and button.isVisible() and not button.icon().isNull() and ".gmj" in button.toolTip())
check("sta in alto a destra: sopra le card e allineato al loro bordo destro",
      button.mapTo(home, QPoint(0, 0)).y() < grid.mapTo(home, QPoint(0, 0)).y()
      and abs(button.mapTo(home, QPoint(button.width(), 0)).x() - grid.mapTo(home, QPoint(grid.width(), 0)).x()) <= 2)
title = next(l for l in home.findChildren(QLabel) if l.text() == "Le tue campagne")
check("non copre il titolo", button.mapTo(home, QPoint(0, 0)).x() >= title.mapTo(home, QPoint(0, 0)).x() + title.sizeHint().width())

# ---------- il menu «⋯» di una card ----------
open_card_menu("Aurora")
check("il menu ha «Salva backup…» dopo «Duplica» e prima di «Elimina…»",
      list(menu_items()) == ["Apri campagna", "Modifica…", "Duplica", "Salva backup…", "Elimina…"])
click(menu_items()["Salva backup…"])      # la finestra di scelta è sostituita: risponde «annulla»
check("la finestra di scelta riceve il nome della campagna", asked[-1] == ("destination", "Aurora"))
check("annullando non succede nulla: niente file, niente messaggi", not list(out.iterdir()) and messages == [])

# ---------- salvare ----------
answers["destination"] = out / "Aurora.gmj"
open_card_menu("Aurora"); click(menu_items()["Salva backup…"])
check("il backup è salvato", (out / "Aurora.gmj").is_file() and zipfile.is_zipfile(out / "Aurora.gmj"))
check("un messaggio dice dove", len(messages) == 1 and messages[0][0] == "info" and str(out / "Aurora.gmj") in messages[0][1])
check("nessun popup di avanzamento rimasto aperto", not [p for p in w.findChildren(ProgressPopup) if p.isVisible()])
check("le campagne dell'elenco non sono cambiate", sorted(cards()) == ["Aurora", "Cenere"])

# ---------- errore: dentro la campagna ----------
messages.clear()
answers["destination"] = repo_mod.unique_folder("Aurora").with_name("Aurora") / "dentro.gmj"
open_card_menu("Aurora"); click(menu_items()["Salva backup…"])
check("salvare dentro la campagna: avviso chiaro, nessun file", len(messages) == 1 and messages[0][0] == "warn" and "fuori dalla cartella" in messages[0][1]
      and not (root / "Aurora" / "dentro.gmj").exists())

# ---------- ripristinare ----------
messages.clear()
before = set(cards())
click(button)                            # nessun file scelto: annulla
check("annullando il ripristino non succede nulla", asked[-1] == ("source", None) and set(cards()) == before and messages == [])
answers["source"] = out / "Aurora.gmj"
click(button)
check("ripristino: compare la card «Aurora (ripristinata)»", set(cards()) == before | {"Aurora (ripristinata)"})
check("…e il messaggio dice come si chiama", len(messages) == 1 and messages[0][0] == "info" and "Aurora (ripristinata)" in messages[0][1])
restored = repo_mod.list_campaigns()
check("la campagna ripristinata è una cartella nuova, con i suoi dati", len(restored) == 3 and any(
    e.campaign.name == "Aurora (ripristinata)" and e.folder.name == "Aurora (ripristinata)" and Repository.open(e.folder).pages()[0].title == "Capitolo uno" for e in restored))
answers["source"] = out / "Aurora.gmj"
click(button)
check("un secondo ripristino: «Aurora (ripristinata 2)»", "Aurora (ripristinata 2)" in cards())

# ---------- ripristinare un file sbagliato ----------
messages.clear()
(out / "falso.gmj").write_text("non sono un backup")
answers["source"] = out / "falso.gmj"
names = sorted(p.name for p in root.iterdir())
click(button)
check("un file non valido: avviso chiaro, nessuna campagna in più", len(messages) == 1 and messages[0][0] == "warn" and "non è un backup" in messages[0][1]
      and sorted(p.name for p in root.iterdir()) == names)

# ---------- il backup di una campagna aperta nella finestra ----------
w._go(root / "Cenere", "scrittura"); pump(200)
page = w._repo.create_page("Scritto adesso")
w._go(None, "home"); pump(200)
answers["destination"] = out / "Cenere.gmj"
open_card_menu("Cenere"); click(menu_items()["Salva backup…"])
answers["source"] = out / "Cenere.gmj"
click(button)
with Repository.open(root / "Cenere (ripristinata)") as r:
    check("il backup di una campagna aperta nella finestra contiene l'ultimo salvataggio", [p.title for p in r.pages()] == ["Scritto adesso"])
check("…e la campagna aperta continua a funzionare", [p.title for p in w._repo.pages()] == ["Scritto adesso"])

# ---------- il popup di avanzamento ----------
seen = []
def quick(progress):
    progress(1, 2); seen.append(any(p.isVisible() for p in w.findChildren(ProgressPopup))); progress(2, 2)
    return "fatto"
check("operazione breve: nessun popup (non lampeggia) e il risultato arriva", run_with_progress(w, "T", "S", quick) == "fatto" and seen == [False])
pump(50)
check("…e il popup non resta tra i figli", not w.findChildren(ProgressPopup))

progress_mod._DELAY = 0
state = {}
def slow(progress):
    flag = []
    QTimer.singleShot(0, lambda: flag.append(True))
    progress(25, 100)
    popup = next(p for p in w.findChildren(ProgressPopup) if p.isVisible())
    state["popup"], state["events"] = popup, bool(flag)
    state["bar"] = (popup._bar.minimum(), popup._bar.maximum(), popup._bar.value())
    state["modal"] = QApplication.activeModalWidget() is popup
    card = popup.findChild(QFrame, "PopupCard")
    state["inside"] = popup.geometry() == w.geometry() and card.height() > 60 and popup.rect().contains(card.geometry())
    QTest.keyClick(popup, Qt.Key_Escape)
    state["after_esc"] = popup.isVisible()
    progress(100, 100)
    state["final"] = popup._bar.value()
    return 7
check("operazione lunga: restituisce il risultato", run_with_progress(w, "Salvo il backup", "Un momento…", slow) == 7)
check("il popup compare, è modale e copre la finestra", state["modal"] and state["inside"])
check("la barra mostra l'avanzamento (25 su 100, poi 100)", state["bar"] == (0, 100, 25) and state["final"] == 100)
check("la finestra si ridisegna mentre lavora (gli eventi girano)", state["events"])
check("Esc non lo chiude", state["after_esc"])
pump(50)
check("a lavoro finito il popup sparisce (viene eliminato)", not w.findChildren(ProgressPopup))
def boom(progress):
    progress(1, 2)
    raise ValueError("errore nel lavoro")
try:
    run_with_progress(w, "T", "S", boom)
except ValueError:
    pass
pump(50)
check("se il lavoro fallisce il popup si chiude e l'errore arriva a chi ha chiamato", not w.findChildren(ProgressPopup))
progress_mod._DELAY = 0.5

# ---------- le finestre di scelta (quelle di Qt, pilotate) ----------
details = {}
def pick_destination(dialog):
    details["is_dialog"] = isinstance(dialog, QFileDialog)
    details["name"] = Path(dialog.selectedFiles()[0]).name if dialog.selectedFiles() else None
    details["suffix"], details["mode"] = dialog.defaultSuffix(), dialog.acceptMode()
    details["filter"] = dialog.nameFilters()
    dialog.findChild(QLineEdit, "fileNameEdit").setText(str(out / "scelto"))      # un nome senza estensione
    dialog.accept()
drive(pick_destination)
chosen = backup_files.ask_backup_destination(w, "Aurora")
check("scelta della destinazione: nome proposto con la data, estensione .gmj, finestra «salva»",
      details["is_dialog"] and details["name"] == backup_filename("Aurora") and details["suffix"] == "gmj" and details["mode"] == QFileDialog.AcceptSave
      and details["filter"] == ["Backup di GM Journal (*.gmj)"])
check("…se si scrive un nome senza estensione, vi si aggiunge .gmj", chosen == out / "scelto.gmj")
drive(lambda dialog: dialog.reject())
check("…annullando restituisce None", backup_files.ask_backup_destination(w, "Aurora") is None)
def pick_source(dialog):
    details["open_filter"] = dialog.nameFilters()
    dialog.findChild(QLineEdit, "fileNameEdit").setText(str(out / "Aurora.gmj")); dialog.accept()
drive(pick_source)
check("scelta del backup da ripristinare: solo file .gmj", backup_files.ask_backup_source(w) == out / "Aurora.gmj" and details["open_filter"] == ["Backup di GM Journal (*.gmj)"])
drive(lambda dialog: dialog.reject())
check("…annullando restituisce None", backup_files.ask_backup_source(w) is None)

# ---------- campagna con un nome pieno di caratteri strani ----------
odd = Repository.create(unique_folder("Città d'Ombra: l'Alba?"), CampaignInput("Città d'Ombra: l'Alba?", "", "amber", None)); odd.close()
home.refresh(); pump(100)
messages.clear()
answers["destination"] = out / "strana.gmj"
open_card_menu("Città d'Ombra: l'Alba?"); click(menu_items()["Salva backup…"])
answers["source"] = out / "strana.gmj"
click(button)
check("nome con accenti, apostrofi e simboli: salva e ripristina", "Città d'Ombra: l'Alba? (ripristinata)" in cards() and messages[-1][0] == "info")

w.close()
print(f"\n{sum(ok)}/{len(ok)}")
