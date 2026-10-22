"""Popup per creare o modificare un personaggio, un luogo o un'organizzazione (dati base: il resto è nella scheda)."""

from pathlib import Path

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QPlainTextEdit, QVBoxLayout, QWidget

from ... import theme
from ...data.db import DatabaseError
from ...data.image_refs import safe_media_path
from ...data.models import Element, ElementInput
from ...data.repository import NAME_MAX, Repository
from ...elements import KINDS, ElementKind
from ...formatting import initials
from ..widgets.element_thumb import ElementThumb
from ..widgets.filter_chip import FilterChip
from ..widgets.hold_button import HoldButton
from ..widgets.image_choice import ImageChoice
from .images import choose_image
from .base import DELETE, PopupDialog, labeled, note

_IMAGE_SIZE = 180


class ElementPopup(PopupDialog):
    """Senza `element` ne crea uno nuovo (con il nome già scritto, se `name` c'è); con `element` lo modifica.

    L'immagine si sceglie fra quelle della libreria della campagna `repo`.
    """

    def __init__(self, parent: QWidget, kind: ElementKind, repo: Repository, element: Element | None = None, name: str = ""):
        edit = element is not None
        super().__init__(
            parent,
            f"Modifica {kind.noun}" if edit else kind.new,
            f"Cambia i dati base di {element.name}." if edit
            else "Bastano i dati base: tutto il resto lo aggiungi poi nella scheda.",
            "Salva modifiche" if edit else f"Crea {kind.noun}",
            width=780,
        )
        self._kind, self._folder = kind, repo.folder
        self._categories = {category.id: category for category in repo.categories(kind.key)}
        self._category_id = element.category_id if edit else next(iter(self._categories))

        self._name = QLineEdit(element.name if edit else name)
        self._name.setFixedHeight(40)
        self._name.setMaxLength(NAME_MAX)
        self._name.setFont(theme.ui_font(15))
        self._name.setPlaceholderText(kind.name_hint)
        self._role = QLineEdit(element.role if edit else "")
        self._role.setFixedHeight(40)
        self._role.setPlaceholderText("Es. Cacciatrice di taglie")
        self._brief = QPlainTextEdit(element.brief if edit else "")
        self._brief.setFixedHeight(84)
        self._brief.setPlaceholderText(kind.brief_hint)
        self._choice = ImageChoice(name_width=100, picker=lambda widget, current: choose_image(widget, repo, current))
        self._choice.set_image(element.image if edit else None)
        self._thumb = ElementThumb(_IMAGE_SIZE, 14, _IMAGE_SIZE)

        image = QVBoxLayout()
        image.setSpacing(10)
        image.addWidget(self._thumb)
        image.addWidget(self._choice)
        self._no_image_hint = note("Senza immagine si usano le iniziali.")
        image.addWidget(self._no_image_hint)
        image.addStretch()

        fields = QVBoxLayout()
        fields.setSpacing(16)
        fields.addLayout(labeled("Nome", self._name))
        fields.addLayout(labeled("Categoria", self._category_chips()))
        if kind.has_role:
            fields.addLayout(labeled("Ruolo", self._role, "(facoltativo)"))
        fields.addLayout(labeled("In breve", self._brief, "(facoltativo)"))
        if edit:
            fields.addWidget(note(f"Nelle pagine di Scrittura i collegamenti verso {kind.the} restano come semplice testo."))

        content = QHBoxLayout()
        content.setSpacing(28)
        content.addLayout(image)
        content.addLayout(fields, 1)
        self.body.addLayout(content)

        if edit:
            delete = HoldButton(f"Tieni premuto per eliminare {kind.the}")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)

        self._name.textChanged.connect(self._update)
        self._choice.changed.connect(self._update)
        self._update()
        self._name.setFocus()
        self._name.selectAll()

    def _category_chips(self) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._chips: dict[int, FilterChip] = {}
        for category in self._categories.values():
            chip = FilterChip(category.name, theme.category_color(category.color), height=32)
            chip.clicked.connect(lambda _=False, category_id=category.id: self._pick_category(category_id))
            row.addWidget(chip)
            self._chips[category.id] = chip
        row.addStretch()
        return holder

    def _pick_category(self, category_id: int) -> None:
        self._category_id = category_id
        self._update()

    def _image_path(self) -> Path | None:
        image = self._choice.image()
        return image if isinstance(image, Path) else safe_media_path(self._folder, image)

    def _update(self) -> None:
        """Allinea chip, anteprima e pulsante ai dati inseriti."""
        for category_id, chip in self._chips.items():
            chip.setChecked(category_id == self._category_id)
        name = self._name.text().strip()
        color = theme.category_color(self._categories[self._category_id].color)
        self._thumb.set_element(initials(name), color, self._image_path())
        self._no_image_hint.setVisible(self._choice.image() is None)
        self.set_primary_enabled(bool(name))

    def data(self) -> ElementInput:
        return ElementInput(self._kind.key, self._name.text().strip(), self._category_id, self._choice.image(),
                            self._brief.toPlainText().strip(), self._role.text().strip() if self._kind.has_role else "")


def create_element(parent: QWidget, repo: Repository, kind: ElementKind, name: str = "") -> int | None:
    """Apre il popup «Nuovo …» e, se si conferma, crea l'elemento. Restituisce il suo ID (None se annullato o fallito)."""
    popup = ElementPopup(parent, kind, repo, name=name)
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_element(popup.data())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_element(parent: QWidget, repo: Repository, element: Element) -> int:
    """Apre il popup di modifica di un elemento e fa ciò che si sceglie: salvare, o eliminarlo (pulsante «tieni premuto»).
    Restituisce `DELETE`, `QDialog.Accepted` (modificato) o `QDialog.Rejected` (annullato)."""
    popup = ElementPopup(parent, KINDS[element.kind], repo, element=element)
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_element(element.id)
        elif result == QDialog.Accepted:
            repo.update_element(element.id, popup.data())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
