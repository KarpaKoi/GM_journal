"""Miniature delle immagini: ritagliate per riempire un riquadro (o intere, dentro un riquadro).

Ogni file si legge dal disco una sola volta, già ridotto a una misura «a scaglioni» (128, 256, 512… pixel sul lato lungo) che
resta in cache (quella di Qt, con un tetto di memoria). La miniatura esatta si ricava da quella copia in pochi millisecondi:
così ridimensionare la finestra, o far riadattare le tessere, non rilegge i file. Chi mostra una miniatura usa `Thumb`, che la
prepara solo quando il riquadro si disegna: una tessera fuori dalla vista non costa nulla.
"""

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QImageReader, QPixmap, QPixmapCache

_CACHE_KB = 160 * 1024     # memoria massima delle copie ridotte
_SMALLEST_STEP = 128       # lato lungo della copia più piccola, in pixel
QPixmapCache.setCacheLimit(_CACHE_KB)


def _step(side: int) -> int:
    """La più piccola misura a scaglioni (128, 256, 512…) che contiene `side` pixel."""
    step = _SMALLEST_STEP
    while step < side:
        step *= 2
    return step


def _reader(path: Path) -> QImageReader:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)       # le foto dal telefono arrivano ruotate: si raddrizzano
    return reader


def _decoded(path: Path, mtime_ns: int, step: int | None, size: QSize) -> QPixmap | None:
    """L'immagine letta dal disco con il lato lungo di `step` pixel (`None` = a misura piena); sta in cache.
    `mtime_ns` serve solo come chiave: se il file cambia, la copia si rifà."""
    key = f"{path}|{mtime_ns}|{step}"
    pixmap = QPixmapCache.find(key)
    if pixmap is None:
        reader = _reader(path)
        if step is not None:
            reader.setScaledSize(size.scaled(step, step, Qt.KeepAspectRatio))  # decodifica già ridotta
        image = reader.read()
        if image.isNull():
            return None
        pixmap = QPixmap.fromImage(image)
        QPixmapCache.insert(key, pixmap)
    return pixmap


def _scaled(path: Path, width: int, height: int, dpr: float, crop: bool) -> QPixmap | None:
    """L'immagine ritagliata a riempire width×height (`crop`) o intera dentro width×height; None se manca o non si legge."""
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return None
    size = _reader(path).size()
    if not size.isValid():
        return None
    target = QSize(round(width * dpr), round(height * dpr))
    final = size.scaled(target, Qt.KeepAspectRatioByExpanding if crop else Qt.KeepAspectRatio)
    step = _step(max(final.width(), final.height()))
    if step >= max(size.width(), size.height()):
        step = None     # l'immagine è già più piccola di così: si legge com'è
    base = _decoded(path, mtime_ns, step, size)
    if base is None:
        return None
    pixmap = base.scaled(final, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    if crop:
        pixmap = pixmap.copy(QRect((final.width() - target.width()) // 2, (final.height() - target.height()) // 2,
                                   target.width(), target.height()))
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


class Thumb:
    """La miniatura di un file per un riquadro. Si prepara alla prima richiesta (cioè quando il riquadro si disegna) e si
    rifà solo se cambiano file, misura o scala dello schermo; un file mancante o illeggibile dà `None` senza riprovare."""

    def __init__(self, crop: bool = True):
        self._crop = crop
        self._file: Path | None = None
        self._key: tuple | None = None
        self._pixmap: QPixmap | None = None

    def set_file(self, file: Path | None) -> None:
        self._file, self._key, self._pixmap = file, None, None

    def pixmap(self, width: int, height: int, dpr: float) -> QPixmap | None:
        if self._file is None or width <= 0 or height <= 0:
            return None
        key = (width, height, dpr)
        if key != self._key:
            self._key, self._pixmap = key, _scaled(self._file, width, height, dpr, self._crop)
        return self._pixmap
