from harness import *
app()
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from gmjournal.app import MainWindow
from gmjournal.data.models import ElementInput
from gmjournal.ui.screens.images import ImageTarget
from gmjournal.ui.screens.elements import ElementTarget
from gmjournal.ui.popups.images import choose_image, choose_images
from gmjournal.ui.popups.base import DELETE
from gmjournal.ui.sheet.images import ImagesPage
from gmjournal.ui.widgets.image_tile import ImageTile, FolderCard
import gmjournal.ui.screens.images as scr_mod
import gmjournal.ui.popups.images as pop_mod

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def drive(fn, delay=60):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))

def png(path, color):
    img = QImage(120, 90, QImage.Format_RGB32); img.fill(QColor(color)); img.save(str(path)); return path

tmp = Path(tempfile.mkdtemp())
files = [png(tmp / f"{n}.png", c) for n, c in (("alfa", "#446688"), ("beta", "#668844"), ("gamma", "#884466"))]

repo = new_repo("ProvaImmagini")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "immagini"); pump(200)
s = w._screens["immagini"]

# --- vuota ---------------------------------------------------------------------------------------
check("libreria vuota: schermata di benvenuto", s._views.currentIndex() == 1)

# --- importare -----------------------------------------------------------------------------------
scr_mod.choose_image_files = lambda parent, multiple=False: files[:2]
s._import(); pump(100)
check("importate 2 immagini nella principale", [i.label for i in s._shown()] == ["alfa", "beta"] and s._views.currentIndex() == 0)
check("la prima importata è scelta", s._selected == s._shown()[0].id)
check("tessere in griglia", len(s._tiles) == 2 and all(isinstance(t, ImageTile) for t in s._tiles.values()))
check("file copiato in immagini/", (repo.folder / "immagini" / "alfa.png").exists())

# --- cartelle --------------------------------------------------------------------------------------
def fill_folder(name, container=None):
    def go(d):
        d._name.setText(name)
        if container is not None:
            d._container.set_options(d._container._options if hasattr(d._container, "_options") else [], container)
        d.accept()
    return go
drive(fill_folder("Luoghi")); s._new_folder(); pump(100)
check("cartella creata e visibile come scheda", [f.name for f in repo.image_folders()] == ["Luoghi"] and len(s._folder_grid.findChildren(FolderCard)) == 1)
luoghi = repo.image_folders()[0].id
drive(lambda d: (d._name.setText(""), check("nome vuoto: «Crea» disattivato", not d._primary.isEnabled()), d.reject()))
s._new_folder(); pump(50)
check("annullare non crea nulla", len(repo.image_folders()) == 1)

# apro la cartella, ci importo la terza
s._open_folder(luoghi); pump(100)
check("cartella aperta: nessuna immagine", s._folder_id == luoghi and s._shown() == [] and not s._no_images.isHidden())
scr_mod.choose_image_files = lambda parent, multiple=False: files[2:]
s._import(); pump(100)
check("l'immagine va nella cartella aperta", [i.label for i in s._shown()] == ["gamma"] and repo.images()[-1].folder_id == luoghi)
# percorso del breadcrumb
s._open_folder(None); pump(100)
check("tornando alla principale: 2 immagini, la cartella conta 1", len(s._shown()) == 2)
card = s._folder_grid.findChildren(FolderCard)[0]
check("scheda cartella", card is not None)

# il percorso con nomi lunghi, a finestra stretta: ogni tratto si accorcia con «…», quello aperto resta leggibile
from gmjournal.ui.screens.images import _Crumb
deep, made = luoghi, []
for n in range(3):
    deep = repo.create_image_folder(f"Una cartella dal nome piuttosto lungo, livello {n + 1}", deep)
    made.append(deep)
s._open_folder(deep); pump(100)
crumbs = s.findChildren(_Crumb)
check("il percorso ha un tratto per ogni cartella, dalla principale a quella aperta", [c._text for c in crumbs][:2] == ["Immagini", "Luoghi"] and len(crumbs) == 5)
w.resize(960, 600); pump(200)      # la finestra più piccola possibile
here = crumbs[-1]
check("a finestra piccola tutto il percorso sta nella schermata: la cartella aperta resta leggibile, i nomi corti restano interi",
      here.width() >= 80 and max(c.mapTo(s, c.rect().topRight()).x() for c in crumbs) <= s.width()
      and all(c.width() == c.sizeHint().width() for c in crumbs[:2]) and all(0 < c.width() < c.sizeHint().width() for c in crumbs[2:]))
check("il nome intero resta nel suggerimento", here.toolTip() == here._text)
QTest.mouseClick(crumbs[1], Qt.LeftButton, pos=crumbs[1].rect().center()); pump(100)
check("un clic su un tratto apre quella cartella", s._folder_id == luoghi)
w.resize(1440, 900); pump(150)
s._open_folder(None); pump(100)
for folder_id in made:
    repo.delete_image_folder(folder_id)

# --- scelta, rinomina, sposta -------------------------------------------------------------------------
alfa = next(i for i in repo.images() if i.label == "alfa")
s._select(alfa.id); pump(50)
check("scegliere mostra i dettagli", s._selected == alfa.id and not s._details._details.isHidden())
s._details._label.setText("Alfa rinominata"); s._details._label.editingFinished.emit(); pump(50)
check("rinomina salvata", next(i for i in repo.images() if i.id == alfa.id).label == "Alfa rinominata")
s._details._label.setText("   "); s._details._label.editingFinished.emit(); pump(50)
check("nome vuoto torna a quello salvato", s._details._label.text() == "Alfa rinominata")
s._move(luoghi); pump(50)
check("sposta: la cartella di destinazione si apre", s._folder_id == luoghi and next(i for i in repo.images() if i.id == alfa.id).folder_id == luoghi)
s._select(alfa.id); pump(50)
check("percorso mostrato nei dettagli", "Luoghi" in s._details._folder.text())
s._move(None); pump(50)

# --- usata in -----------------------------------------------------------------------------------------
loc = repo.create_element(ElementInput("place", "Locanda", repo.categories("place")[0].id, alfa.path, "", ""))
pg = repo.create_page("Capitolo"); repo.save_content(pg, f'<p>Testo <img src="{alfa.path}" width="10" height="10"></p>')
s.reload(); s._select(alfa.id) if s._selected != alfa.id else None; s.reload(); pump(50)
uses = repo.image_uses(alfa.path)
check("usata in: scheda e pagina", {u.kind for u in uses} == {"place", "page"})
got = []
s.open_requested.connect(lambda *a: got.append(a))
place_use = next(u for u in uses if u.kind == "place")
s._details.use_chosen.emit(place_use); pump(50)
check("«Usata in» apre la scheda del luogo", got and got[-1][0] == "luoghi" and got[-1][1] == ElementTarget(loc, True))
n = len(got)
from gmjournal.data.models import LinkTarget
s._details.use_chosen.emit(LinkTarget("campaign", 0, "x", "Copertina")); pump(20)
check("la copertina della campagna non apre nulla", len(got) == n)

# --- cronologia ----------------------------------------------------------------------------------------
t = s.current_target()
s.show_target(ImageTarget(luoghi, None)); pump(50)
check("show_target apre la cartella", s._folder_id == luoghi and s._selected is None)
s.show_target(t); pump(50)
check("show_target ripristina cartella e scelta", s.current_target() == t)
s.show_target(ImageTarget(9999, 9999)); pump(50)
check("cartella inesistente: si torna alla principale", s._folder_id is None and s._selected is None)

# --- modifica / eliminazione cartella ------------------------------------------------------------------------
folder = repo.image_folders()[0]
drive(lambda d: (d._name.setText("Ambienti"), d.accept()))
s._edit_folder(folder); pump(50)
check("cartella rinominata", repo.image_folders()[0].name == "Ambienti")
sub = repo.create_image_folder("Dentro", folder.id)
folder = repo.image_folders()[0]
d_opts = {}
def probe(d):
    d_opts["ids"] = [v for v, _ in d._container._options] if hasattr(d._container, "_options") else None
    d.reject()
drive(probe); s._edit_folder(folder); pump(50)
drive(lambda d: d.done(DELETE)); s._edit_folder(folder); pump(100)
check("eliminata: la sottocartella passa in principale e le immagini non si perdono",
      [f.name for f in repo.image_folders()] == ["Dentro"] and repo.image_folders()[0].parent_id is None and len(repo.images()) == 3)

# --- ingrandire ---------------------------------------------------------------------------------------------
shown = []
drive(lambda d: (shown.append(type(d).__name__), d.reject()))
s._select(alfa.id); s._enlarge(); pump(50)
check("anteprima grande si apre", shown == ["ImageViewer"])

# --- eliminare immagine ---------------------------------------------------------------------------------------
warned = []
drive(lambda d: (warned.append(d.text()), d.close()), 300)
s._select(alfa.id); s._details.delete_confirmed.emit(); pump(400)
check("cestino non disponibile: avviso e nulla è perso", len(warned) == 1 and any(i.id == alfa.id for i in repo.images()) and (repo.folder / alfa.path).exists())
import os, gmjournal.data.repository as repo_mod
class FakeFile:
    @staticmethod
    def moveToTrash(path): os.remove(path); return True
real_qfile = repo_mod.QFile; repo_mod.QFile = FakeFile
s._select(alfa.id); s._details.delete_confirmed.emit(); pump(200)
repo_mod.QFile = real_qfile
check("immagine eliminata dal DB", all(i.id != alfa.id for i in repo.images()))
check("…file non più nella cartella", not (repo.folder / alfa.path).exists())
check("…tolta dal luogo", repo.element_images(loc) == [])
check("…e dal testo della pagina", "<img" not in repo.page(pg).content)

# ========== ImagesPopup ==========================================================================================
repo2 = new_repo("ProvaPopup")
f1 = repo2.create_image_folder("Uno"); f2 = repo2.create_image_folder("Due")
pa = repo2.import_image(files[0], f1); pb = repo2.import_image(files[1], f2); pc = repo2.import_image(files[2])
parent = QPushButton(); parent.show()

def multi(d):
    check("popup multiplo: 3 tessere", len(d._tiles) == 3)
    check("nessuna scelta: pulsante disattivato", not d._primary.isEnabled())
    d._toggle(pa); d._toggle(pb); pump(20)
    check("2 scelte: testo del pulsante", d._primary.text() == "Collega 2 immagini" and d._primary.isEnabled())
    d._toggle(pa); pump(20)
    check("deselezionare funziona", d.paths() == [pb])
    d._toggle(pa)
    d.accept()
drive(multi)
res = choose_images(parent, repo2)
check("choose_images restituisce nell'ordine di scelta", res == [pb, pa])

def linked(d):
    check("già collegata: attenuata, non selezionabile", len(d._tiles) == 3)
    d._tiles[pa].clicked.emit(); pump(20)
    check("clic su una già collegata non seleziona", pa not in d.paths())
    d.reject()
drive(linked); res = choose_images(parent, repo2, frozenset({pa}))
check("annullare restituisce lista vuota", res == [])

def filt(d):
    d._set_filter(f1); pump(20)
    check("filtro per cartella", list(d._tiles) == [pa])
    d._set_filter(None); d._search.setText("gam"); pump(30)
    check("ricerca per nome", list(d._tiles) == [pc])
    d._search.setText("zzz"); pump(30)
    check("nessun risultato: messaggio", d._views.currentIndex() == 1)
    d.reject()
drive(filt); choose_images(parent, repo2)

def single(d):
    check("scelta singola: parte da quella attuale", d.paths() == [pb])
    d._toggle(pc)
    check("scegliere un'altra sostituisce", d.paths() == [pc])
    d.accept()
drive(single)
check("choose_image singola", choose_image(parent, repo2, current=pb) == pc)
drive(lambda d: d._tiles[pa].double_clicked.emit())
check("doppio clic nella scelta singola conferma", choose_image(parent, repo2) == pa)
drive(lambda d: d.reject())
check("annullando la singola: None", choose_image(parent, repo2) is None)

# importare dal popup
pop_mod.choose_image_files = lambda parent, multiple=False: [png(tmp / "delta.png", "#aa5500")]
def imp(d):
    d._set_filter(f2)
    d._import(); pump(50)
    check("importa nel filtro attivo e seleziona", len(d.paths()) == 1 and d.paths()[0].endswith("delta.png"))
    check("…finisce nella cartella del filtro", next(i for i in repo2.images() if i.path == d.paths()[0]).folder_id == f2)
    d.reject()
drive(imp); choose_images(parent, repo2)

# ========== scheda Immagini ======================================================================================
repo3 = new_repo("ProvaScheda")
q1 = repo3.import_image(files[0]); q2 = repo3.import_image(files[1]); q3 = repo3.import_image(files[2])
ch = repo3.create_element(ElementInput("character", "Mira", repo3.categories("character")[0].id, None, "", ""))
w2 = MainWindow(); w2.resize(1440, 900); w2.show(); pump(100)
w2._go(repo3.folder, "personaggi", ElementTarget(ch, True)); pump(150)
sheet = w2._screens["personaggi"]._sheet
sheet._tabs.select("images"); pump(100)
page = sheet._pages.widget(sheet._order.index("images"))
check("pagina Immagini è ImagesPage", isinstance(page, ImagesPage))
check("senza immagini: messaggio con «ritratto»", not page._empty.isHidden() and "ritratto" in page._empty.text())
drive(lambda d: (d._toggle(q1), d._toggle(q2), d.accept())); page._link(); pump(100)
check("collegate 2 immagini", [i.path for i in repo3.element_images(ch)] == [q1, q2])
check("la prima è il ritratto dell'elemento", repo3.element(ch).image == q1 if hasattr(repo3, "element") else [e for e in repo3.elements("character") if e.id == ch][0].image == q1)
check("conteggio nell'intestazione", "2" in page._count.text())
seen = []
page.changed.connect(lambda: seen.append(1))
page._write(repo3.set_element_cover, q2); pump(50)
check("«Usa come ritratto» mette l'immagine per prima", [i.path for i in repo3.element_images(ch)] == [q2, q1] and seen)
page._write(repo3.unlink_element_image, q2); pump(50)
check("«Scollega» toglie l'immagine, la seconda diventa ritratto", [e for e in repo3.elements("character") if e.id == ch][0].image == q1)
check("…ma resta nella libreria", len(repo3.images()) == 3)
def only_new(d):
    check("popup di collegamento: la già collegata è attenuata", q1 in d._linked)
    d.reject()
drive(only_new); page._link(); pump(50)
# elemento popup con libreria
from gmjournal.ui.popups.element import ElementPopup
from gmjournal.elements import KINDS
def ep(d):
    check("popup elemento si apre con la libreria", isinstance(d, ElementPopup))
    d.reject()
drive(ep); ElementPopup(w2, KINDS["character"], repo3).exec()

print(f"\n{sum(ok)}/{len(ok)}")
