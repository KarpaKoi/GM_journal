"""Popup per creare o modificare una voce di Impostazioni (e, da qui, eliminarla): nome e colore, e per i tipi di pin anche l'icona.

La parte comune è in `EntryPopup`; le sottoclassi aggiungono i campi propri.
"""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMessageBox, QWidget

from ... import theme
from ...data.db import DatabaseError
from ...data.repository import NAME_MAX, Repository
from ...settings import Entry, Group
from ..widgets.color_swatch import ColorPicker
from ..widgets.filter_chip import FilterChip
from ..widgets.hold_button import HoldButton
from .base import DELETE, PopupDialog, labeled, note


class EntryPopup(PopupDialog):
    """Senza `entry` ne crea una nuova; con `entry` la modifica o la elimina.

    `others` sono le altre voci della lista: servono a scegliere dove spostare ciò che usa la voce eliminata.
    """

    def __init__(self, parent: QWidget, group: Group, entry: Entry | None, others: list[Entry], placeholder: str, width: int = 640):
        edit = entry is not None
        super().__init__(
            parent,
            f"Modifica {group.subject}" if edit else group.new,
            "Le modifiche si vedono subito ovunque." if edit else group.intro,
            "Salva modifiche" if edit else f"Crea {group.subject}",
            width=width,
        )
        self._entry, self._others = entry, others
        self._name = QLineEdit(entry.name if edit else "")
        self._name.setFixedHeight(40)
        self._name.setMaxLength(NAME_MAX)
        self._name.setFont(theme.ui_font(15))
        self._name.setPlaceholderText(placeholder)
        self._colors = ColorPicker()
        if edit:
            self._colors.set_value(entry.color)
        self.body.setSpacing(18)
        self.body.addLayout(labeled("Nome", self._name))
        self.add_fields()
        self.body.addLayout(labeled("Colore", self._colors))

        self._destination = others[0].id if others else None      # dove vanno ciò che usa la voce eliminata
        if edit:
            self._add_delete(group, entry)
        self._name.textChanged.connect(lambda: self.set_primary_enabled(bool(self._name.text().strip())))
        self.set_primary_enabled(bool(self._name.text().strip()))
        self._name.setFocus()
        self._name.selectAll()

    def add_fields(self) -> None:
        """Dove le sottoclassi aggiungono i loro campi, fra il nome e il colore."""

    def _add_delete(self, group: Group, entry: Entry) -> None:
        if not self._others:
            self.body.addWidget(note(group.last_text))
            return
        if entry.count:
            self.body.addLayout(labeled(group.move_text, self._destination_chips(), f"({group.count_text(entry.count)})"))
        delete = HoldButton(f"Tieni premuto per eliminare {'la' if group.kind else 'il'} {group.subject}")
        delete.confirmed.connect(lambda: self.done(DELETE))
        self.footer_left.addWidget(delete)

    def _destination_chips(self) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._chips: dict[int, FilterChip] = {}
        for other in self._others:
            chip = FilterChip(other.name, theme.category_color(other.color), height=32)
            chip.clicked.connect(lambda _=False, other_id=other.id: self._choose_destination(other_id))
            row.addWidget(chip)
            self._chips[other.id] = chip
        row.addStretch()
        self._choose_destination(self._destination)
        return holder

    def _choose_destination(self, other_id: int) -> None:
        self._destination = other_id
        for chip_id, chip in self._chips.items():
            chip.setChecked(chip_id == other_id)

    def name(self) -> str:
        return self._name.text().strip()

    def color(self) -> str:
        return self._colors.value()

    def destination(self) -> int | None:
        """La voce a cui passa ciò che usava quella eliminata (None se non c'è altra voce)."""
        return self._destination


class CategoryPopup(EntryPopup):
    def __init__(self, parent: QWidget, group: Group, entry: Entry | None, others: list[Entry]):
        super().__init__(parent, group, entry, others, "Es. Alleati")


def create_category(parent: QWidget, repo: Repository, group: Group) -> int | None:
    """Apre «Nuova categoria» e, se si conferma, la crea. Restituisce il suo ID (None se annullato o fallito)."""
    popup = CategoryPopup(parent, group, None, [])
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_category(group.kind, popup.name(), popup.color())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_category(parent: QWidget, repo: Repository, group: Group, entry: Entry, others: list[Entry]) -> int:
    """Apre «Modifica categoria» e fa ciò che si sceglie. Restituisce `DELETE`, `QDialog.Accepted` o `QDialog.Rejected`."""
    popup = CategoryPopup(parent, group, entry, others)
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_category(entry.id, popup.destination())
        elif result == QDialog.Accepted:
            repo.update_category(entry.id, popup.name(), popup.color())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
