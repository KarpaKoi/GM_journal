"""Dove il programma tiene le campagne e da dove parte nelle finestre di scelta dei file.

Normalmente le campagne stanno in Documenti\\GM Journal. Nella versione portatile (la cartella «GMJournal-Portable», con il file
`portable.txt` accanto a `GMJournal.exe`) tutto resta dentro la cartella del programma: campagne in `Campagne`, backup in `Backup`.
Così la cartella si copia su una chiavetta o su un altro computer, con le campagne dentro. Fuori restano solo i file temporanei
(backup, ripristino, immagini incollate), che passano da %TEMP%, e il Cestino di Windows per ciò che si elimina.
"""

from pathlib import Path

from PySide6.QtCore import QStandardPaths

PORTABLE_MARKER = "portable.txt"
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]      # nel pacchetto per Windows: la cartella con GMJournal.exe (e app\run.py a fianco)


def portable_root() -> Path | None:
    """La cartella del programma portatile, o None se il programma gira normalmente (installato o dai sorgenti)."""
    if (_PACKAGE_ROOT / PORTABLE_MARKER).is_file() and (_PACKAGE_ROOT / "app" / "run.py").is_file():
        return _PACKAGE_ROOT
    return None


def campaigns_root() -> Path:
    """La cartella che contiene tutte le campagne."""
    root = portable_root()
    if root is not None:
        return root / "Campagne"
    return Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)) / "GM Journal"


def start_folder() -> Path:
    """La cartella da cui partono le finestre «Salva backup», «Ripristina» e «Importa schede»."""
    root = portable_root()
    if root is not None:
        return root / "Backup"
    return Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))
