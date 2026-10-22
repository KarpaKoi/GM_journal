from harness import *
app()
import os, tempfile
from pathlib import Path
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPixmapCache
from PySide6.QtWidgets import QScrollArea
import gmjournal.thumbnails as thumbs
from gmjournal.data.models import ElementInput
from gmjournal.sections import BY_KEY
from gmjournal.ui.screens import create_screen

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

tmp = Path(tempfile.mkdtemp(prefix="gmj_thumbs_"))

def make_png(name, w, h, color="#446688"):
    path = tmp / name
    img = QImage(w, h, QImage.Format_RGB32); img.fill(QColor(color)); assert img.save(str(path))
    return path

def make_halves(name, w, h):
    """Metà sinistra rossa, metà destra blu."""
    path = tmp / name
    img = QImage(w, h, QImage.Format_RGB32); img.fill(QColor("#ff0000"))
    painter = QPainter(img); painter.fillRect(w // 2, 0, w - w // 2, h, QColor("#0000ff")); painter.end()
    assert img.save(str(path)); return path

# Conta le letture vere dal disco e le miniature ricavate.
reads, scaled = [], []
class CountingReader(QImageReader):
    def read(self):
        reads.append(self.fileName()); return super().read()
_real_reader, _real_scaled = thumbs._reader, thumbs._scaled
def counting_reader(path):
    reader = CountingReader(str(path)); reader.setAutoTransform(True); return reader
thumbs._reader = counting_reader
def counting_scaled(*args):
    scaled.append(args); return _real_scaled(*args)
thumbs._scaled = counting_scaled

def fresh():
    QPixmapCache.clear(); reads.clear(); scaled.clear()

# ---------- le misure ----------
check("la cache delle miniature ha un tetto di memoria", QPixmapCache.cacheLimit() == 160 * 1024)
big = make_png("grande.png", 1600, 900)
fresh()
cover = thumbs._scaled(big, 300, 200, 1.0, True)
check("ritagliata: esattamente la misura del riquadro", (cover.width(), cover.height()) == (300, 200) and cover.devicePixelRatio() == 1.0)
cover = thumbs._scaled(big, 300, 200, 1.5, True)
check("a scala 150%: pixel in più, stessa misura logica", (cover.width(), cover.height()) == (450, 300) and cover.deviceIndependentSize().toSize().width() == 300)
fit = thumbs._scaled(big, 300, 300, 1.0, False)
check("intera: sta dentro il riquadro, con le proporzioni", (fit.width(), fit.height()) in ((300, 168), (300, 169)))
tall = make_png("alta.png", 600, 800)
fit = thumbs._scaled(tall, 300, 300, 1.0, False)
check("intera, immagine alta", (fit.width(), fit.height()) == (225, 300))
tiny = make_png("minuscola.png", 40, 30)
check("immagine più piccola del riquadro: lo riempie comunque", (lambda p: (p.width(), p.height()))(thumbs._scaled(tiny, 200, 200, 1.0, True)) == (200, 200))
halves = make_halves("meta.png", 400, 200)
square = thumbs._scaled(halves, 100, 100, 1.0, True).toImage()
check("il ritaglio è al centro (a sinistra rosso, a destra blu)", square.pixelColor(10, 50).red() > 200 and square.pixelColor(90, 50).blue() > 200)
check("un file che manca dà None", thumbs._scaled(tmp / "manca.png", 100, 100, 1.0, True) is None)
broken = tmp / "rotta.png"; broken.write_text("non sono un'immagine")
check("un file illeggibile dà None", thumbs._scaled(broken, 100, 100, 1.0, True) is None)
empty = tmp / "vuota.png"; empty.write_bytes(b"")
check("un file vuoto dà None", thumbs._scaled(empty, 100, 100, 1.0, True) is None)

# ---------- una lettura dal disco, tante misure ----------
fresh()
thumb = thumbs.Thumb()
thumb.set_file(big)
for width in range(300, 321):
    thumb.pixmap(width, round(width * 0.72), 1.0)
check("21 misure diverse (la finestra che si ridimensiona): il file si legge una volta sola", len(reads) == 1)
other = thumbs.Thumb(); other.set_file(big); other.pixmap(310, 250, 1.0)
check("un altro riquadro della stessa immagine non rilegge il file", len(reads) == 1)
other.pixmap(900, 600, 1.0)
check("una misura molto più grande ha la sua copia (seconda lettura)", len(reads) == 2)
other.pixmap(310, 250, 1.0)
check("…e quella piccola resta in cache", len(reads) == 2)
fresh()
thumbs.Thumb(crop=False).pixmap(1, 1, 1.0)
check("un Thumb senza file non legge nulla", not reads and not scaled)

# ---------- Thumb: si rifà solo quando serve ----------
fresh()
thumb = thumbs.Thumb(); thumb.set_file(big)
first = thumb.pixmap(300, 200, 1.0)
again = thumb.pixmap(300, 200, 1.0)
check("stessa misura: nessun nuovo lavoro", len(scaled) == 1 and again is first)
thumb.pixmap(300, 200, 1.5)
check("scala diversa: si rifà", len(scaled) == 2)
thumb.set_file(big)
thumb.pixmap(300, 200, 1.5)
check("nuovo file impostato: si rifà", len(scaled) == 3)
thumb.set_file(None)
check("senza file: None", thumb.pixmap(300, 200, 1.0) is None)
fresh()
ghost = thumbs.Thumb(); ghost.set_file(tmp / "manca.png")
for _ in range(5):
    ghost.pixmap(300, 200, 1.0)
check("file che manca: si prova una volta sola, non a ogni disegno", len(scaled) == 1)
check("misura nulla: None, senza lavoro", thumb.pixmap(0, 100, 1.0) is None and thumb.pixmap(100, 0, 1.0) is None)

# ---------- un file cambiato si rilegge ----------
changed = make_png("cambia.png", 400, 300, "#ff0000")
fresh()
thumb = thumbs.Thumb(); thumb.set_file(changed)
check("prima: rosso", thumb.pixmap(100, 75, 1.0).toImage().pixelColor(50, 30).red() > 200)
make_png("cambia.png", 400, 300, "#0000ff")
os.utime(changed, (changed.stat().st_atime, changed.stat().st_mtime + 5))
thumb.set_file(changed)
check("dopo la modifica del file: blu (la copia in cache non resta quella vecchia)", thumb.pixmap(100, 75, 1.0).toImage().pixelColor(50, 30).blue() > 200)

# ---------- nelle schermate: ciò che non si vede non si carica ----------
repo = new_repo("Miniature")
cat = repo.categories("character")[0].id
paths = [repo.import_image(make_png(f"pers{i}.png", 600, 400, "#336655")) for i in range(60)]
for i, path in enumerate(paths):
    repo.create_element(ElementInput("character", f"Personaggio {i + 1}", cat, path, "", ""))
fresh()
screen = create_screen(BY_KEY["personaggi"], repo)
screen.resize(1000, 700); screen.show(); pump(400)
visible = len(scaled)
check(f"60 tessere con immagine, solo quelle in vista si preparano ({visible})", 0 < visible < 30)
scroll = next(s for s in screen.findChildren(QScrollArea) if s.verticalScrollBar().maximum() > 0)   # l'elenco (non la fascia dei filtri)
scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum()); pump(400)
check("scorrendo in fondo si preparano le altre", len(scaled) > visible)
before = len(scaled)
screen.resize(1100, 700); pump(400)
check("ridimensionando la schermata i file non si rileggono (copie in cache)", len(reads) <= 60)
screen.close()
repo.close()

print(f"\n{sum(ok)}/{len(ok)}")
