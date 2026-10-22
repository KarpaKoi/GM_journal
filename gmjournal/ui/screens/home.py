"""Home: elenco delle campagne, con creazione, modifica, duplica, backup (salva e ripristina) ed elimina."""

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.backup import restore_backup, save_backup
from ...data.db import DatabaseError
from ...data.image_refs import safe_media_path
from ...data.models import CampaignEntry
from ...data.repository import (
    Repository, TrashError, delete_campaign, delete_campaign_permanently, duplicate_campaign, list_campaigns, unique_folder,
)
from ...formatting import modified_label
from ..backup_files import ask_backup_destination, ask_backup_source
from ..popups.base import DELETE
from ..popups.campaign import CampaignPopup
from ..popups.progress import run_with_progress
from ..widgets.card_grid import CardGrid
from ..widgets.cards import CampaignCard, NewCard, campaign_card_height
from ..widgets.menu import PopupMenu
from .base import Screen


class HomeScreen(Screen):
    campaign_opened = Signal(object)    # cartella (Path) della campagna da aprire
    campaign_removing = Signal(object)  # la campagna in questa cartella sta per essere eliminata

    def __init__(self):
        super().__init__()
        title = QLabel("Le tue campagne")
        title.setFont(theme.serif_font(46, 500, -0.01))
        subtitle = QLabel("Scegli una campagna su cui lavorare o creane una nuova.")
        subtitle.setObjectName("Muted")
        subtitle.setFont(theme.ui_font(16))
        restore = QPushButton(" Ripristina da backup…")
        restore.setIcon(icons.icon("upload"))
        restore.setIconSize(QSize(17, 17))
        restore.setFixedHeight(38)
        restore.setCursor(Qt.PointingHandCursor)
        restore.setToolTip("Crea una campagna nuova da un file di backup (.gmj)")
        restore.clicked.connect(self._restore)
        self._grid = CardGrid(max_columns=8, min_card_width=240, h_gap=20, v_gap=20, card_height=campaign_card_height)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(title)
        titles.addSpacing(10)
        titles.addWidget(subtitle)
        header = QHBoxLayout()
        header.addLayout(titles, 1)
        header.addWidget(restore, alignment=Qt.AlignTop)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(0)
        self._content_layout.addLayout(header)
        self._content_layout.addSpacing(44)
        self._content_layout.addWidget(self._grid)
        self._content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        self._set_margins()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()  # ogni volta che si torna alla Home l'elenco è aggiornato

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._set_margins()

    def _set_margins(self) -> None:
        side = 120 if self.width() >= 1280 else 48
        self._content_layout.setContentsMargins(side, 72, side, 40)

    def refresh(self) -> None:
        new_card = NewCard("Nuova campagna")
        new_card.clicked.connect(self._create)
        cards: list[QWidget] = [new_card]
        for entry in list_campaigns():
            campaign = entry.campaign
            card = CampaignCard()
            card.set_campaign(campaign.name, modified_label(campaign.modified_at), campaign.color,
                              safe_media_path(entry.folder, campaign.image))
            card.clicked.connect(lambda entry=entry: self.campaign_opened.emit(entry.folder))
            card.menu_clicked.connect(lambda entry=entry, card=card: self._open_menu(entry, card))
            cards.append(card)
        self._grid.set_cards(cards)

    # --- Azioni ----------------------------------------------------------------
    def _guarded(self, action: Callable[[], object]) -> bool:
        """Esegue `action`; se fallisce mostra il motivo all'utente e restituisce False."""
        try:
            action()
        except (DatabaseError, OSError) as error:
            QMessageBox.warning(self, "GM Journal", str(error))
            return False
        return True

    def _open_menu(self, entry: CampaignEntry, card: CampaignCard) -> None:
        menu = PopupMenu(card)
        menu.add_item("file", "Apri campagna", lambda: self.campaign_opened.emit(entry.folder))
        menu.add_item("pencil", "Modifica…", lambda: self._edit(entry))
        menu.add_item("copy", "Duplica", lambda: self._duplicate(entry))
        menu.add_item("download", "Salva backup…", lambda: self._save_backup(entry))
        menu.add_separator()
        menu.add_item("trash", "Elimina…", lambda: self._edit(entry), danger=True)  # si elimina dal popup di modifica
        menu.popup_at(card.menu_anchor())

    def _create(self) -> None:
        popup = CampaignPopup(self)
        if popup.exec() == QDialog.Accepted:
            data = popup.data()
            self._guarded(lambda: Repository.create(unique_folder(data.name), data).close())
            self.refresh()

    def _edit(self, entry: CampaignEntry) -> None:
        popup = CampaignPopup(self, entry.campaign, entry.folder)
        result = popup.exec()
        if result == QDialog.Accepted:
            data = popup.data()

            def save() -> None:
                with Repository.open(entry.folder) as repo:
                    repo.update_campaign(data)
            self._guarded(save)
        elif result == DELETE:
            self._delete(entry)
        self.refresh()

    def _duplicate(self, entry: CampaignEntry) -> None:
        self._guarded(lambda: duplicate_campaign(entry.folder))
        self.refresh()

    def _save_backup(self, entry: CampaignEntry) -> None:
        destination = ask_backup_destination(self, entry.campaign.name)
        if destination is not None:
            self._guarded(lambda: self._write_backup(entry, destination))

    def _write_backup(self, entry: CampaignEntry, destination: Path) -> None:
        run_with_progress(self, "Salvo il backup", "Copio i dati e le immagini della campagna in un unico file…",
                          lambda progress: save_backup(entry.folder, destination, progress))
        QMessageBox.information(self, "GM Journal", f"Backup salvato in:\n{destination}")

    def _restore(self) -> None:
        source = ask_backup_source(self)
        if source is not None:
            self._guarded(lambda: self._read_backup(source))

    def _read_backup(self, source: Path) -> None:
        restored = run_with_progress(self, "Ripristino il backup", "Creo una campagna nuova con i dati e le immagini del backup…",
                                     lambda progress: restore_backup(source, progress))
        self.refresh()
        QMessageBox.information(self, "GM Journal", f"Backup ripristinato: la campagna «{restored.campaign.name}» è nell'elenco.")

    def _delete(self, entry: CampaignEntry) -> None:
        self.campaign_removing.emit(entry.folder)  # se è aperta, la finestra la chiude prima

        def remove() -> None:
            try:
                delete_campaign(entry.folder)
            except TrashError:                       # niente cestino (per esempio su una chiavetta USB), o un file aperto
                if self._confirm_permanent_delete(entry.campaign.name):
                    delete_campaign_permanently(entry.folder)
        self._guarded(remove)

    def _confirm_permanent_delete(self, name: str) -> bool:
        """Il cestino non accetta la campagna: chiede se eliminarla per sempre (di norma la risposta è «no»)."""
        box = QMessageBox(QMessageBox.Warning, "GM Journal", f"Non riesco a spostare la campagna «{name}» nel Cestino.", parent=self)
        box.setInformativeText(f"Succede, per esempio, su una chiavetta USB, dove il Cestino non c'è. Vuoi eliminare «{name}» "
                               "definitivamente? Pagine, schede, mappe e immagini andranno perse e non si potranno recuperare.")
        delete = box.addButton("Elimina definitivamente", QMessageBox.DestructiveRole)
        cancel = box.addButton("Annulla", QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() is delete
