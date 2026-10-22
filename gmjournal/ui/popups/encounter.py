"""Popup per creare o modificare un incontro (e, da qui, eliminarlo): nome, tipo, giocatori presenti (nei combattimenti) e schede tecniche."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.db import DatabaseError
from ...data.models import CreatureRow, Encounter, EncounterInput, PartyGroup, Slot
from ...data.repository import NAME_MAX, Repository
from ...dnd import LEVEL_MAX, LEVEL_MIN, PLAYERS_MAX, QUANTITY_MAX
from ...encounters import COMBAT, KIND_LABELS, KINDS
from ..creature_items import caption
from ..widgets.elided_label import ElidedLabel
from ..widgets.hold_button import HoldButton
from ..widgets.segment_switch import SegmentSwitch
from .base import DELETE, PopupDialog, field_label, labeled, line_edit, note, number_edit, remove_button
from .creature_picker import pick_creatures

_DEFAULT_PARTY = PartyGroup(1, 4)       # un gruppo di quattro giocatori di primo livello, se non c'è nulla di meglio
_NUMBER_WIDTH = 64


class _Row(QFrame):
    removed = Signal(object)

    def __init__(self):
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def _finish(self) -> None:
        remove = remove_button()
        remove.clicked.connect(lambda: self.removed.emit(self))
        self._layout.addWidget(remove)


def _number(value: int, high: int, low: int = 1):
    edit = number_edit(str(value), low, high)
    edit.setFixedWidth(_NUMBER_WIDTH)
    edit.setAlignment(Qt.AlignCenter)
    return edit


def _read(edit, low: int, high: int) -> int | None:
    """Il numero scritto in un campo, riportato nei limiti; None se il campo è vuoto."""
    return min(max(int(edit.text()), low), high) if edit.text() else None


class _PartyRow(_Row):
    """«[4] giocatori di livello [3]»."""

    def __init__(self, group: PartyGroup):
        super().__init__()
        self._count = _number(group.count, PLAYERS_MAX)
        self._level = _number(group.level, LEVEL_MAX, LEVEL_MIN)
        self._layout.addWidget(self._count)
        self._layout.addWidget(QLabel("giocatori di livello"))
        self._layout.addWidget(self._level)
        self._layout.addStretch()
        self._finish()

    def group(self) -> PartyGroup | None:
        count, level = _read(self._count, 1, PLAYERS_MAX), _read(self._level, LEVEL_MIN, LEVEL_MAX)
        return PartyGroup(level, count) if count and level else None


class _SlotRow(_Row):
    """Una scheda dell'incontro: il nome, le informazioni e quante copie."""

    def __init__(self, creature: CreatureRow, quantity: int):
        super().__init__()
        self.creature_id = creature.id
        self._quantity = _number(quantity, QUANTITY_MAX)
        title = ElidedLabel(creature.name, theme.TEXT, theme.ui_font(14, 500))
        detail = ElidedLabel(caption(creature), theme.MUTED, theme.ui_font(12))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(title)
        texts.addWidget(detail)
        multiply = QLabel("×")
        multiply.setObjectName("Muted")
        multiply.setFont(theme.ui_font(16))
        self._layout.addLayout(texts, 1)
        self._layout.addWidget(multiply)
        self._layout.addWidget(self._quantity)
        self._finish()

    def slot(self) -> Slot:
        return Slot(self.creature_id, _read(self._quantity, 1, QUANTITY_MAX) or 1)


class _Rows(QVBoxLayout):
    """Le righe di una sezione, con la «x» che le toglie."""

    def __init__(self):
        super().__init__()
        self.setSpacing(8)

    def add(self, row: _Row) -> None:
        row.removed.connect(self._remove)
        self.addWidget(row)

    def _remove(self, row: _Row) -> None:
        self.removeWidget(row)
        row.deleteLater()

    def rows(self) -> list:
        return [self.itemAt(number).widget() for number in range(self.count())]


def _section(title: str, rows: _Rows, add_label: str, on_add, hint: str) -> QWidget:
    """Un gruppo di righe con il suo titolo, il pulsante per aggiungerne e una frase di spiegazione."""
    button = QPushButton(f" {add_label}")
    button.setIcon(icons.icon("plus"))
    button.setIconSize(QSize(16, 16))
    button.setFixedHeight(38)
    button.setAutoDefault(False)
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(lambda _=False: on_add())
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(field_label(title))
    layout.addLayout(rows)
    layout.addWidget(button, alignment=Qt.AlignLeft)
    layout.addWidget(note(hint))
    return section


class EncounterPopup(PopupDialog):
    """Senza `encounter` ne crea uno nuovo (con `party` come gruppo di partenza); con `encounter` lo modifica o lo elimina."""

    def __init__(self, parent: QWidget, creatures: list[CreatureRow], encounter: Encounter | None = None,
                 party: tuple[PartyGroup, ...] = (_DEFAULT_PARTY,)):
        edit = encounter is not None
        super().__init__(parent, "Modifica incontro" if edit else "Nuovo incontro",
                         "Cambia l'incontro." if edit else "Dai un nome all'incontro e scegli le schede tecniche che servono.",
                         "Salva modifiche" if edit else "Crea incontro", width=760)
        self._creatures = creatures
        self._by_id = {row.id: row for row in creatures}
        self._kind = encounter.kind if edit else COMBAT
        self._name = line_edit(encounter.name if edit else "", "Es. Imboscata dei goblin", NAME_MAX)
        self._switch = SegmentSwitch([(kind, KIND_LABELS[kind], 13) for kind in KINDS], self._choose_kind, segment_width=150)
        self._party = _Rows()
        self._slots = _Rows()

        self._party_box = _section("Giocatori presenti", self._party, "Aggiungi gruppo", lambda: self._party.add(_PartyRow(_DEFAULT_PARTY)),
                                   "Quanti giocatori ci sono a ogni livello: la difficoltà si calcola con le regole del 2014 (Dungeon Master's Guide).")
        form = QVBoxLayout()
        form.setSpacing(16)
        form.addLayout(labeled("Nome", self._name))
        form.addLayout(labeled("Tipo", self._switch))
        form.addWidget(self._party_box)
        form.addWidget(_section("Schede tecniche", self._slots, "Aggiungi schede…", self._add_creatures, "L'incontro mostra solo queste schede."))
        form.addStretch()

        for group in (encounter.party if edit else party):
            self._party.add(_PartyRow(group))
        for slot in encounter.creatures if edit else ():
            self._slots.add(_SlotRow(self._by_id[slot.creature_id], slot.quantity))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.addLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(content)
        content.setAutoFillBackground(False)          # (dopo setWidget, che lo accenderebbe): dentro il popup resta del suo colore
        scroll.setFixedHeight(max(280, min(560, self._window.height() - 300)))
        self.body.addWidget(scroll)

        if edit:
            delete = HoldButton("Tieni premuto per eliminare l'incontro")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)
        self._choose_kind(self._kind)
        self._name.textChanged.connect(lambda: self.set_primary_enabled(bool(self._name.text().strip())))
        self.set_primary_enabled(bool(self._name.text().strip()))
        self._name.setFocus()
        self._name.selectAll()

    def _choose_kind(self, kind: str) -> None:
        self._kind = kind
        self._switch.set_value(kind)
        self._party_box.setVisible(kind == COMBAT)

    def _add_creatures(self) -> None:
        taken = {row.creature_id for row in self._slots.rows()}
        for creature_id in pick_creatures(self, self._creatures, taken):
            self._slots.add(_SlotRow(self._by_id[creature_id], 1))

    def data(self) -> EncounterInput:
        groups = (row.group() for row in self._party.rows())
        return EncounterInput(self._name.text(), self._kind, tuple(group for group in groups if group) if self._kind == COMBAT else (),
                              tuple(row.slot() for row in self._slots.rows()))


def create_encounter(parent: QWidget, repo: Repository) -> int | None:
    """Apre «Nuovo incontro» e, se si conferma, lo crea. Restituisce il suo ID (None se annullato o fallito).
    I giocatori di partenza sono quelli dell'ultimo combattimento creato: di solito sono sempre gli stessi."""
    last = [encounter.party for encounter in sorted(repo.encounters(), key=lambda encounter: encounter.id) if encounter.party]
    popup = EncounterPopup(parent, repo.creatures(), party=last[-1] if last else (_DEFAULT_PARTY,))
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_encounter(popup.data())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_encounter(parent: QWidget, repo: Repository, encounter: Encounter) -> int:
    """Apre «Modifica incontro» e fa ciò che si sceglie. Restituisce `DELETE`, `QDialog.Accepted` o `QDialog.Rejected`."""
    popup = EncounterPopup(parent, repo.creatures(), encounter)
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_encounter(encounter.id)
        elif result == QDialog.Accepted:
            repo.update_encounter(encounter.id, popup.data())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
