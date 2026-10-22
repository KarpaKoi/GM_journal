"""Le finestre di sistema del backup: dove salvarlo e quale ripristinare."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from ..data.backup import BACKUP_SUFFIX, backup_filename
from ..paths import start_folder

_FILTER = f"Backup di GM Journal (*{BACKUP_SUFFIX})"


def ask_backup_destination(parent: QWidget, campaign_name: str) -> Path | None:
    """Fa scegliere dove salvare il backup della campagna `campaign_name`; None se si annulla.
    Il file ha sempre l'estensione .gmj (se manca la aggiunge la finestra, che chiede conferma se il file esiste già)."""
    dialog = QFileDialog(parent, "Salva backup", str(start_folder() / backup_filename(campaign_name)), _FILTER)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    dialog.setDefaultSuffix(BACKUP_SUFFIX.lstrip("."))
    return Path(dialog.selectedFiles()[0]) if dialog.exec() == QFileDialog.Accepted else None


def ask_backup_source(parent: QWidget) -> Path | None:
    """Fa scegliere il file di backup da ripristinare; None se si annulla."""
    name, _ = QFileDialog.getOpenFileName(parent, "Scegli il backup da ripristinare", str(start_folder()), _FILTER)
    return Path(name) if name else None
