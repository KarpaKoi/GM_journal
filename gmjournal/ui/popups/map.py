"""Popup per creare o modificare una mappa: nome, dove sta nell'albero delle mappe, immagine di sfondo."""

from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox, QWidget

from ... import theme
from ...data import trees
from ...data.db import DatabaseError
from ...data.models import Map
from ...data.repository import NAME_MAX, Repository
from ..widgets.hold_button import HoldButton
from ..widgets.image_choice import ImageChoice
from ..widgets.select_field import SelectField
from .base import DELETE, PopupDialog, labeled, note
from .images import choose_image

_TOP = "Primo livello"


class MapPopup(PopupDialog):
    """Senza `node` ne crea una nuova dentro `parent_id`; con `node` la rinomina, la sposta, ne cambia lo sfondo o la elimina."""

    def __init__(self, parent: QWidget, repo: Repository, maps: list[Map], node: Map | None = None, parent_id: int | None = None,
                 name: str = ""):
        edit = node is not None
        super().__init__(
            parent,
            "Modifica mappa" if edit else "Nuova mappa",
            "Cambia il nome, lo sfondo o sposta la mappa dentro un'altra." if edit
            else "Scegli la mappa disegnata da usare come sfondo: i pin si posano sopra.",
            "Salva modifiche" if edit else "Crea mappa",
            width=620,
        )
        self._name = QLineEdit(node.name if edit else name)
        self._name.setFixedHeight(40)
        self._name.setMaxLength(NAME_MAX)
        self._name.setFont(theme.ui_font(15))
        self._name.setPlaceholderText("Es. Regno di Aldoria")

        inside = trees.subtree(maps, node.id) if edit else set()      # non si può finire dentro se stessa
        options = [(None, _TOP)] + [(id_, path) for id_, path in trees.named_paths(maps) if id_ not in inside]
        self._container = SelectField()
        self._container.set_options(options, parent_id if parent_id in dict(options) else None)
        self._choice = ImageChoice(name_width=300, picker=lambda widget, current: choose_image(widget, repo, current))
        self._choice.set_image(node.image if edit else None)

        self.body.setSpacing(18)
        self.body.addLayout(labeled("Nome", self._name))
        self.body.addLayout(labeled("Dentro a", self._container, "(facoltativo)"))
        self.body.addLayout(labeled("Immagine della mappa", self._choice, "(facoltativo)"))
        if edit:
            delete = HoldButton("Tieni premuto per eliminare la mappa")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)
            self.body.addWidget(note("Eliminando la mappa si eliminano i suoi pin. Le sue sottomappe non si perdono: salgono di un livello."))

        self._name.textChanged.connect(lambda: self.set_primary_enabled(bool(self._name.text().strip())))
        self.set_primary_enabled(bool(self._name.text().strip()))
        self._name.setFocus()
        self._name.selectAll()

    def name(self) -> str:
        return self._name.text().strip()

    def parent_id(self) -> int | None:
        return self._container.value()

    def image(self) -> str | None:
        return self._choice.image()


def create_map(parent: QWidget, repo: Repository, parent_id: int | None = None, name: str = "") -> int | None:
    """Apre «Nuova mappa» e, se si conferma, la crea. Restituisce il suo ID (None se annullato o fallito)."""
    popup = MapPopup(parent, repo, repo.maps(), parent_id=parent_id, name=name)
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_map(popup.name(), popup.parent_id(), popup.image())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_map(parent: QWidget, repo: Repository, node: Map) -> int:
    """Apre «Modifica mappa» e fa ciò che si sceglie. Restituisce `DELETE`, `QDialog.Accepted` o `QDialog.Rejected`."""
    popup = MapPopup(parent, repo, repo.maps(), node, node.parent_id)
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_map(node.id)
        elif result == QDialog.Accepted:
            repo.update_map(node.id, popup.name(), popup.parent_id(), popup.image())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
