from harness import *
app()
import tempfile
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication, QPushButton, QWidget
from gmjournal.app import MainWindow
from gmjournal.ui.editor.editor import RichEditor
from gmjournal.ui.popups.images import text_image_picker
from gmjournal.ui.popups.campaign import CampaignPopup
import gmjournal.ui.popups.campaign as camp_mod
import gmjournal.ui.widgets.image_choice as choice_mod
import gmjournal.ui.screens.images as scr_mod

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)
def drive(fn, delay=60):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))
tmp = Path(tempfile.mkdtemp())
def png(name, color):
    p = tmp / name; img = QImage(120, 90, QImage.Format_RGB32); img.fill(QColor(color)); img.save(str(p)); return p

repo = new_repo("PiuImmagini")
a = repo.import_image(png("uno.png", "#446688")); b = repo.import_image(png("due.png", "#668844"))
parent = QWidget(); parent.show()

# --- editor: inserire dalla libreria ---------------------------------------------------------------
ed = RichEditor(media_dir=repo.folder, pick_images=lambda p: [a, b])
ed.choose_image(); pump(50)
check("l'editor inserisce le immagini scelte dalla libreria", ed.content().count("<img") == 2 and f'src="{a}"' in ed.content() and f'src="{b}"' in ed.content())
check("nessuna copia nuova: la libreria resta di 2 file", len(repo.images()) == 2 and len(list((repo.folder / "immagini").iterdir())) == 2)
ed2 = RichEditor(media_dir=repo.folder); ed2.choose_image()
check("senza libreria collegata il pulsante non fa nulla", "<img" not in ed2.content())
ed3 = RichEditor(media_dir=repo.folder, pick_images=lambda p: [])
ed3.choose_image(); check("annullando non si inserisce nulla", "<img" not in ed3.content())

def popup_texts(d):
    check("popup dell'editor: «Inserisci immagini»", d._primary.text() == "Inserisci immagini" and not d._primary.isEnabled())
    d._toggle(a); pump(20)
    check("…con il conteggio nel pulsante", d._primary.text() == "Inserisci 1 immagine")
    d.accept()
drive(popup_texts)
check("text_image_picker restituisce la scelta", text_image_picker(repo)(parent) == [a])

# --- copertina della campagna dalla libreria ---------------------------------------------------------
picked = []
camp_mod.choose_image = lambda widget, r, current=None: (picked.append((type(r).__name__, current)), b)[1]
entry_campaign = repo.campaign()
popup = CampaignPopup(parent, entry_campaign, repo.folder)
popup._choice._pick(); pump(20)
check("modifica: la copertina si sceglie dalla libreria della campagna", picked == [("Repository", None)] and popup.data().image == b)
check("…l'anteprima usa il file della libreria", popup._image_path() == repo.folder / b)
popup._choice._pick(); check("…la scelta attuale è passata al selettore", picked[-1][1] == b)
repo.update_campaign(popup.data())
check("salvata come copertina senza copiare file", repo.campaign().image == b and len(list((repo.folder / "immagini").iterdir())) == 2)
check("«Usata in» mostra la copertina della campagna", [u.kind for u in repo.image_uses(b)][:1] == ["campaign"])
popup._pick_color("red"); check("un colore toglie l'immagine", popup.data().image is None)

used = []
choice_mod.choose_image_files = lambda parent, multiple=False: used.append(1) or [png("nuova.png", "#aa5500")]
new_popup = CampaignPopup(parent)
new_popup._choice._pick(); pump(20)
check("nuova campagna: la copertina si sceglie dal computer (non c'è ancora una libreria)", used and isinstance(new_popup.data().image, Path))

# --- Apri in Esplora file ------------------------------------------------------------------------
opened = []
class FakeServices:
    @staticmethod
    def openUrl(url): opened.append(url.toLocalFile()); return True
real = scr_mod.QDesktopServices; scr_mod.QDesktopServices = FakeServices
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "immagini"); pump(200)
s = w._screens["immagini"]
btn = [x for x in s.findChildren(QPushButton) if "Apri in Esplora file" in x.text()]
check("c'è il pulsante «Apri in Esplora file» in intestazione", len(btn) == 1)
btn[0].click(); pump(20)
check("apre la cartella immagini della campagna, senza dover scegliere un'immagine", s._selected is None and opened == [str(repo.folder / "immagini")])
(repo.folder / "immagini").rmdir() if not list((repo.folder / "immagini").iterdir()) else None
check("il pannello dei dettagli non ha più il pulsante doppio", not [x for x in s._details.findChildren(QPushButton) if "Apri la cartella" in x.text()])
scr_mod.QDesktopServices = real
print(f"\n{sum(ok)}/{len(ok)}")
