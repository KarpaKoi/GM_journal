"""La finestra di sistema per scegliere i file di schede tecniche (XML) e i messaggi dell'importazione."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ..formatting import thousands
from ..paths import start_folder


def choose_compendium_files(parent: QWidget) -> list[Path]:
    """Fa scegliere uno o più file XML di schede tecniche."""
    names, _ = QFileDialog.getOpenFileNames(parent, "Scegli i file di schede", str(start_folder()), "Schede tecniche (*.xml)")
    return [Path(name) for name in names]


def confirm_large_file(parent: QWidget, filename: str, count: int) -> bool:
    """Un file con tante schede appesantisce la campagna: si chiede se continuare. True = importa comunque."""
    box = QMessageBox(QMessageBox.Warning, "GM Journal",
                      f"Il file «{filename}» contiene {thousands(count)} schede: la campagna diventerebbe molto pesante. Continuare?",
                      QMessageBox.NoButton, parent)
    go = box.addButton("Importa comunque", QMessageBox.AcceptRole)
    box.addButton("Annulla", QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is go


def import_summary(added: int, skipped: int) -> str:
    """«Importate 3 schede», «2 importate, 1 già presente», «1 importata, 2 già presenti»."""
    if not added:
        return "Nessuna scheda nuova: erano già tutte presenti."
    if not skipped:
        return "Importata 1 scheda" if added == 1 else f"Importate {thousands(added)} schede"
    return f"{thousands(added)} {'importata' if added == 1 else 'importate'}, {thousands(skipped)} già {'presente' if skipped == 1 else 'presenti'}"
