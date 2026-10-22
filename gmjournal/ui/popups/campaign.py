"""Popup per creare o modificare una campagna."""

from pathlib import Path

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QMessageBox, QPlainTextEdit, QVBoxLayout, QWidget

from ... import theme
from ...data.db import DatabaseError
from ...data.image_refs import safe_media_path
from ...data.models import Campaign, CampaignInput
from ...data.repository import Repository
from ..widgets.cards import CampaignCard
from ..widgets.color_swatch import ColorSwatch
from ..widgets.hold_button import HoldButton
from ..widgets.image_choice import ImageChoice, pick_from_computer
from .base import DELETE, PopupDialog, field_label, labeled, note
from .images import choose_image

_NAME_MAX = 60


class CampaignPopup(PopupDialog):
    """Senza `campaign` crea una nuova campagna; con `campaign` (e la sua cartella) la modifica."""

    def __init__(self, parent: QWidget, campaign: Campaign | None = None, folder: Path | None = None):
        edit = campaign is not None
        super().__init__(
            parent,
            "Modifica campagna" if edit else "Nuova campagna",
            "Cambia nome, descrizione e copertina della campagna." if edit
            else "Dai un nome alla tua avventura: il resto si può cambiare in seguito.",
            "Salva modifiche" if edit else "Crea campagna",
        )
        self._folder = folder
        self._edit = edit
        self._color = campaign.color if edit else "blue"
        self._choice = ImageChoice(picker=self._pick_cover if edit and folder else pick_from_computer)
        self._choice.set_image(campaign.image if edit else None)
        self._choice.changed.connect(self._update)

        self._name = QLineEdit(campaign.name if edit else "")
        self._name.setFixedHeight(40)
        self._name.setMaxLength(_NAME_MAX)
        self._name.setFont(theme.ui_font(15))
        self._description = QPlainTextEdit(campaign.description if edit else "")
        self._description.setFixedHeight(84)
        self._preview = CampaignCard(compact=True)
        self._preview.setFixedWidth(220)

        fields = QVBoxLayout()
        fields.setSpacing(18)
        fields.addLayout(labeled("Nome della campagna", self._name))
        fields.addLayout(labeled("Descrizione", self._description, "(facoltativa)"))
        fields.addLayout(self._cover_section())
        fields.addStretch()

        preview = QVBoxLayout()
        preview.setSpacing(6)
        preview.addWidget(field_label("Anteprima"))
        preview.addWidget(self._preview)
        preview.addStretch()

        content = QHBoxLayout()
        content.setSpacing(28)
        content.addLayout(fields, 1)
        content.addLayout(preview)
        self.body.addLayout(content)

        if edit:
            delete = HoldButton("Tieni premuto per eliminare la campagna")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)

        self._name.textChanged.connect(self._update)
        self._update()
        self._name.setFocus()
        self._name.selectAll()

    # --- Costruzione -----------------------------------------------------------
    def _cover_section(self) -> QVBoxLayout:
        self._swatches: dict[str, ColorSwatch] = {}
        swatches = QHBoxLayout()
        swatches.setSpacing(4)
        for key, (name, color, _) in theme.CAMPAIGN_COLORS.items():
            swatch = ColorSwatch(color, name)
            swatch.clicked.connect(lambda _=False, key=key: self._pick_color(key))
            swatches.addWidget(swatch)
            self._swatches[key] = swatch

        divider = QFrame()
        divider.setFixedSize(1, 22)
        divider.setObjectName("Divider")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addLayout(swatches)
        row.addWidget(divider)
        row.addWidget(self._choice)
        row.addStretch()

        section = QVBoxLayout()
        section.setSpacing(8)
        section.addWidget(field_label("Copertina"))
        section.addLayout(row)
        section.addWidget(note("Scegli un colore, oppure un'immagine " + ("della libreria della campagna." if self._edit else "dal computer.")))
        return section

    # --- Azioni ----------------------------------------------------------------
    def _pick_color(self, key: str) -> None:
        self._color = key
        self._choice.set_image(None)  # un colore sostituisce l'immagine
        self._update()

    def _pick_cover(self, widget: QWidget, current: str | Path | None) -> str | None:
        """Una campagna esistente sceglie la copertina fra le immagini della sua libreria (che si apre solo per questo)."""
        try:
            with Repository.open(self._folder) as repo:
                repo.sync_images()
                return choose_image(widget, repo, current if isinstance(current, str) else None)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
            return None

    def _image_path(self) -> Path | None:
        image = self._choice.image()
        if isinstance(image, Path):
            return image
        return safe_media_path(self._folder, image) if self._folder else None

    def _update(self) -> None:
        """Allinea pulsanti, selezione del colore e anteprima ai dati inseriti."""
        has_image = self._choice.image() is not None
        for key, swatch in self._swatches.items():
            swatch.setChecked(not has_image and key == self._color)
        name = self._name.text().strip()
        self.set_primary_enabled(bool(name))
        self._preview.set_campaign(name or "Nuova campagna", "Modificata oggi" if self._edit else "Appena creata",
                                   self._color, self._image_path())

    def data(self) -> CampaignInput:
        return CampaignInput(self._name.text().strip(), self._description.toPlainText().strip(), self._color, self._choice.image())
