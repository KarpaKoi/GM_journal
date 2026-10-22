"""Popup per creare o modificare una cartella della libreria immagini."""

from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox, QWidget

from ... import theme
from ...data import trees
from ...data.db import DatabaseError
from ...data.models import ImageFolder
from ...data.repository import NAME_MAX, Repository
from ..widgets.hold_button import HoldButton
from ..widgets.select_field import SelectField
from .base import DELETE, PopupDialog, labeled, note

_MAIN = "Immagini (cartella principale)"


class ImageFolderPopup(PopupDialog):
    """Senza `folder` ne crea una nuova dentro `parent_id`; con `folder` la rinomina, la sposta o la elimina."""

    def __init__(self, parent: QWidget, folders: list[ImageFolder], folder: ImageFolder | None = None, parent_id: int | None = None):
        edit = folder is not None
        super().__init__(
            parent,
            "Modifica cartella" if edit else "Nuova cartella",
            "Cambia il nome o sposta la cartella dentro un'altra." if edit else "Le cartelle servono a tenere in ordine le immagini.",
            "Salva modifiche" if edit else "Crea cartella",
            width=620,
        )
        self._name = QLineEdit(folder.name if edit else "")
        self._name.setFixedHeight(40)
        self._name.setMaxLength(NAME_MAX)
        self._name.setFont(theme.ui_font(15))
        self._name.setPlaceholderText("Es. Taverne")

        inside = trees.subtree(folders, folder.id) if edit else set()     # non si può finire dentro se stessa
        options = [(None, _MAIN)] + [(id_, path) for id_, path in trees.named_paths(folders) if id_ not in inside]
        self._container = SelectField()
        self._container.set_options(options, parent_id if parent_id in dict(options) else None)

        self.body.setSpacing(18)
        self.body.addLayout(labeled("Nome", self._name))
        self.body.addLayout(labeled("Dentro a", self._container))
        if edit:
            delete = HoldButton("Tieni premuto per eliminare la cartella")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)
            self.body.addWidget(note("Eliminando la cartella le immagini che contiene non si perdono: passano nella cartella che la conteneva."))

        self._name.textChanged.connect(lambda: self.set_primary_enabled(bool(self._name.text().strip())))
        self.set_primary_enabled(bool(self._name.text().strip()))
        self._name.setFocus()
        self._name.selectAll()

    def name(self) -> str:
        return self._name.text().strip()

    def parent_id(self) -> int | None:
        return self._container.value()


def create_image_folder(parent: QWidget, repo: Repository, parent_id: int | None) -> int | None:
    """Apre «Nuova cartella» e, se si conferma, la crea. Restituisce il suo ID (None se annullato o fallito)."""
    popup = ImageFolderPopup(parent, repo.image_folders(), parent_id=parent_id)
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_image_folder(popup.name(), popup.parent_id())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_image_folder(parent: QWidget, repo: Repository, folder: ImageFolder) -> int:
    """Apre «Modifica cartella» e fa ciò che si sceglie. Restituisce `DELETE`, `QDialog.Accepted` o `QDialog.Rejected`."""
    popup = ImageFolderPopup(parent, repo.image_folders(), folder, folder.parent_id)
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_image_folder(folder.id)
        elif result == QDialog.Accepted:
            repo.update_image_folder(folder.id, popup.name(), popup.parent_id())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
