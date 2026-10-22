"""La finestra di sistema per scegliere immagini dal computer."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ..data.repository import IMAGE_SUFFIXES

_FILTER = f"Immagini ({' '.join(f'*{suffix}' for suffix in sorted(IMAGE_SUFFIXES))})"


def choose_image_files(parent: QWidget, multiple: bool = False) -> list[Path]:
    """Fa scegliere uno o più file immagine; i file che non si riescono a leggere si segnalano e non entrano nell'elenco."""
    start = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
    if multiple:
        names, _ = QFileDialog.getOpenFileNames(parent, "Scegli le immagini", start, _FILTER)
    else:
        name, _ = QFileDialog.getOpenFileName(parent, "Scegli un'immagine", start, _FILTER)
        names = [name] if name else []
    paths = [Path(name) for name in names]
    unreadable = [path.name for path in paths if not QImageReader(str(path)).canRead()]
    if unreadable:
        QMessageBox.warning(parent, "GM Journal", "Non riesco a leggere come immagine: " + ", ".join(f"«{name}»" for name in unreadable) + ".")
    return [path for path in paths if path.name not in unreadable]
