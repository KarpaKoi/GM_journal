"""Popup per creare o modificare una scheda tecnica (e, da qui, eliminarla): i dati di base e le capacità, divise per sezione."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ... import icons
from ...data.db import DatabaseError
from ...data.models import Creature, CreatureInput, Feature
from ...data.repository import NAME_MAX, Repository
from ...dnd import ABILITY_DEFAULT, ABILITY_LABELS, ABILITY_MAX, ABILITY_MIN, FEATURE_SECTIONS, SIZES
from ..widgets.hold_button import HoldButton
from ..widgets.select_field import SelectField
from .base import DELETE, PopupDialog, field_label, labeled, line_edit, note, number_edit, remove_button


_MIN_LINES, _MAX_LINES = 3, 9


def _columns(*columns: QVBoxLayout) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(14)
    for column in columns:
        row.addLayout(column, 1)
    return row


class _FeatureRow(QFrame):
    """Una voce: il nome, il testo e il pulsante per toglierla."""

    removed = Signal(object)

    def __init__(self, feature: Feature):
        super().__init__()
        self._name = line_edit(feature.name, "Nome")
        self._text = QPlainTextEdit(feature.text)
        self._text.setPlaceholderText("Testo")
        self._text.document().documentLayout().documentSizeChanged.connect(self._fit_text)
        self._fit_text()
        remove = remove_button()
        remove.clicked.connect(lambda: self.removed.emit(self))
        fields = QVBoxLayout()
        fields.setSpacing(6)
        fields.addWidget(self._name)
        fields.addWidget(self._text)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(fields, 1)
        layout.addWidget(remove, alignment=Qt.AlignTop)

    def _fit_text(self) -> None:
        """Il campo del testo cresce con ciò che c'è scritto (da 3 a 9 righe): le capacità lunghe si leggono senza scorrere."""
        lines = max(self._text.document().size().height(), 1)
        self._text.setFixedHeight(int(min(max(lines, _MIN_LINES), _MAX_LINES) * self._text.fontMetrics().lineSpacing()) + 22)

    def feature(self, section: str) -> Feature:
        return Feature(section, self._name.text(), self._text.toPlainText())


class _FeatureEditor(QWidget):
    """Le voci di una sezione (tratti, azioni…) e un pulsante per aggiungerne altre."""

    def __init__(self, key: str, title: str, features: list[Feature]):
        super().__init__()
        self._key = key
        self._rows = QVBoxLayout()
        self._rows.setSpacing(10)
        add = QPushButton(" Aggiungi")
        add.setIcon(icons.icon("plus"))
        add.setIconSize(QSize(16, 16))
        add.setFixedHeight(38)
        add.setAutoDefault(False)
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda _=False: self._add(Feature(key, "", "")))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(field_label(title))
        layout.addLayout(self._rows)
        layout.addWidget(add, alignment=Qt.AlignLeft)
        for feature in features:
            self._add(feature)

    def _add(self, feature: Feature) -> None:
        row = _FeatureRow(feature)
        row.removed.connect(self._remove)
        self._rows.addWidget(row)

    def _remove(self, row: _FeatureRow) -> None:
        self._rows.removeWidget(row)
        row.deleteLater()

    def features(self) -> list[Feature]:
        return [self._rows.itemAt(number).widget().feature(self._key) for number in range(self._rows.count())]


class CreaturePopup(PopupDialog):
    """Senza `creature` ne crea una nuova; con `creature` la modifica o la elimina."""

    def __init__(self, parent: QWidget, creature: Creature | None = None, used_in: list[str] | None = None):
        edit = creature is not None
        super().__init__(parent, "Modifica scheda" if edit else "Nuova scheda",
                         "Cambia i dati della scheda." if edit else "Compila ciò che ti serve: solo il nome è obbligatorio.",
                         "Salva modifiche" if edit else "Crea scheda", width=860)
        c = creature
        self._name = line_edit(c.name if edit else "", "Es. Goblin", NAME_MAX)
        self._size = SelectField()
        sizes = [("", "—"), *((size, size) for size in SIZES)]
        if edit and c.size and c.size not in SIZES:
            sizes.append((c.size, c.size))
        self._size.set_options(sizes, c.size if edit else "")
        self._kind = line_edit(c.kind if edit else "", "Es. humanoid (goblinoid)")
        self._alignment = line_edit(c.alignment if edit else "", "Es. neutral evil")
        self._armor_class = line_edit(c.armor_class if edit else "", "Es. 15 (leather armor, shield)")
        self._hit_points = line_edit(c.hit_points if edit else "", "Es. 7 (2d6)")
        self._speed = line_edit(c.speed if edit else "", "Es. walk 30 ft.")
        self._abilities = [number_edit(str(score) if edit else str(ABILITY_DEFAULT), ABILITY_MIN, ABILITY_MAX)
                           for score in (c.abilities if edit else [ABILITY_DEFAULT] * len(ABILITY_LABELS))]
        self._saves = line_edit(c.saves if edit else "", "Es. Dex +4, Wis +2")
        self._skills = line_edit(c.skills if edit else "", "Es. Stealth +6")
        self._vulnerabilities = line_edit(c.vulnerabilities if edit else "")
        self._resistances = line_edit(c.resistances if edit else "")
        self._immunities = line_edit(c.immunities if edit else "")
        self._condition_immunities = line_edit(c.condition_immunities if edit else "")
        self._senses = line_edit(c.senses if edit else "", "Es. darkvision 60 ft.")
        self._passive = number_edit("" if not edit or c.passive is None else str(c.passive), 0, 99)
        self._languages = line_edit(c.languages if edit else "", "Es. Common, Goblin")
        self._challenge = line_edit(c.challenge if edit else "", "Es. 1/4 o 10")
        self._environment = line_edit(c.environment if edit else "")
        self._source = line_edit(c.source if edit else "", "Es. Monster Manual p. 166")
        self._notes = QPlainTextEdit(c.notes if edit else "")
        self._notes.setFixedHeight(96)
        self._notes.setPlaceholderText("Descrizione, note per il master…")
        self._features = [_FeatureEditor(key, title, [f for f in c.features if f.section == key] if edit else [])
                          for key, title in FEATURE_SECTIONS]

        form = QVBoxLayout()
        form.setSpacing(16)
        form.addLayout(labeled("Nome", self._name))
        form.addLayout(_columns(labeled("Taglia", self._size), labeled("Tipo", self._kind), labeled("Allineamento", self._alignment)))
        form.addLayout(_columns(labeled("Classe Armatura", self._armor_class), labeled("Punti ferita", self._hit_points),
                                labeled("Velocità", self._speed)))
        form.addLayout(_columns(*(labeled(label, edit_) for label, edit_ in zip(ABILITY_LABELS, self._abilities))))
        form.addLayout(_columns(labeled("Tiri salvezza", self._saves), labeled("Abilità", self._skills)))
        form.addLayout(_columns(labeled("Vulnerabilità ai danni", self._vulnerabilities), labeled("Resistenze ai danni", self._resistances)))
        form.addLayout(_columns(labeled("Immunità ai danni", self._immunities), labeled("Immunità alle condizioni", self._condition_immunities)))
        form.addLayout(_columns(labeled("Sensi", self._senses), labeled("Percezione passiva", self._passive), labeled("Linguaggi", self._languages)))
        form.addLayout(_columns(labeled("Grado di sfida", self._challenge), labeled("Ambiente", self._environment, "(facoltativo)"),
                                labeled("Fonte", self._source, "(facoltativo)")))
        for editor in self._features:
            form.addWidget(editor)
        form.addLayout(labeled("Descrizione", self._notes, "(facoltativa)"))

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
        scroll.setFixedHeight(max(280, min(620, self._window.height() - 300)))
        self.body.addWidget(scroll)

        if used_in:
            self.body.addSpacing(10)
            self.body.addWidget(note(f"Questa scheda è usata in {len(used_in)} incontr{'o' if len(used_in) == 1 else 'i'} ({', '.join(used_in)}): "
                                     "eliminandola sparisce anche da lì."))
        if edit:
            delete = HoldButton("Tieni premuto per eliminare la scheda")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)
        self._name.textChanged.connect(lambda: self.set_primary_enabled(bool(self._name.text().strip())))
        self.set_primary_enabled(bool(self._name.text().strip()))
        self._name.setFocus()
        self._name.selectAll()

    def data(self) -> CreatureInput:
        return CreatureInput(
            name=self._name.text(), size=self._size.value(), kind=self._kind.text(), alignment=self._alignment.text(),
            armor_class=self._armor_class.text(), hit_points=self._hit_points.text(), speed=self._speed.text(),
            abilities=tuple(int(edit.text()) if edit.text() else ABILITY_DEFAULT for edit in self._abilities),
            saves=self._saves.text(), skills=self._skills.text(), vulnerabilities=self._vulnerabilities.text(),
            resistances=self._resistances.text(), immunities=self._immunities.text(), condition_immunities=self._condition_immunities.text(),
            senses=self._senses.text(), passive=int(self._passive.text()) if self._passive.text() else None, languages=self._languages.text(),
            challenge=self._challenge.text(), environment=self._environment.text(), source=self._source.text(),
            notes=self._notes.toPlainText(), features=tuple(feature for editor in self._features for feature in editor.features()))


def create_creature(parent: QWidget, repo: Repository) -> int | None:
    """Apre «Nuova scheda» e, se si conferma, la crea. Restituisce il suo ID (None se annullato o fallito)."""
    popup = CreaturePopup(parent)
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_creature(popup.data())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_creature(parent: QWidget, repo: Repository, creature: Creature) -> int:
    """Apre «Modifica scheda» e fa ciò che si sceglie. Restituisce `DELETE`, `QDialog.Accepted` o `QDialog.Rejected`."""
    popup = CreaturePopup(parent, creature, repo.encounters_using(creature.id))
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_creature(creature.id)
        elif result == QDialog.Accepted:
            repo.update_creature(creature.id, popup.data())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
