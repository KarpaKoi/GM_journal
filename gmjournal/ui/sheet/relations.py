"""La scheda interna «Relazioni»: gli elementi collegati a questo, un riquadro per ogni tipo."""

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data.db import DatabaseError
from ...data.models import Relation
from ...data.repository import Repository
from ...elements import KINDS, ElementKind
from ...formatting import initials
from ..link_sources import LinkSources
from ..widgets.element_thumb import ElementThumb
from ..widgets.icon_label import IconLabel
from .parts import InlineEdit, NameLink, card_title
from .picking import choose_element
from .saves import PendingSaves

_ROW_PADDING = 10


class RemovableRow(QWidget):
    """Una riga con una linea sotto e, al passaggio del mouse, il pulsante per scollegare."""

    unlink_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_Hover)
        self._unlink = QToolButton()
        self._unlink.setObjectName("ChipButton")
        self._unlink.setIcon(icons.icon("x", theme.MUTED))
        self._unlink.setIconSize(QSize(14, 14))
        self._unlink.setFixedSize(24, 24)
        self._unlink.setToolTip("Scollega")
        self._unlink.setCursor(Qt.PointingHandCursor)
        self._unlink.clicked.connect(self.unlink_requested)
        self._fade = QGraphicsOpacityEffect(self._unlink)
        self._unlink.setGraphicsEffect(self._fade)
        self._fade.setOpacity(0)

    @property
    def unlink_button(self) -> QToolButton:
        return self._unlink

    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Enter, QEvent.HoverEnter):
            self._fade.setOpacity(1)
        elif event.type() in (QEvent.Leave, QEvent.HoverLeave):
            self._fade.setOpacity(0)
        return super().event(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(0, self.height() - 1, self.width(), 1, QColor("#262a33"))


class _RelationRow(RemovableRow):
    def __init__(self, relation: Relation, color: str, image: Path | None):
        super().__init__()
        self.relation = relation
        thumb = ElementThumb(36, 9, 36)
        thumb.set_element(initials(relation.other.name), color, image)
        self.name = NameLink(relation.other.name, inset=InlineEdit.TEXT_INSET)      # allineato al testo della riga sotto
        self.label = InlineEdit("Che relazione ha? Es. “Ci va a caccia”")
        self.label.setText(relation.label)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(self.name)
        column.addWidget(self.label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, _ROW_PADDING, 0, _ROW_PADDING)
        layout.setSpacing(3)
        layout.addWidget(thumb, alignment=Qt.AlignTop)
        layout.addLayout(column, 1)
        layout.addWidget(self.unlink_button, alignment=Qt.AlignTop)


class _Group(QFrame):
    """Il riquadro di un tipo di elemento: titolo, le righe, il pulsante «Collega un …»."""

    def __init__(self, kind: ElementKind, rows: list[_RelationRow]):
        super().__init__()
        self.setObjectName("SheetCard")
        self.add_button = QPushButton(" Collega " + kind.a)
        self.add_button.setObjectName("DashedButton")
        self.add_button.setIcon(icons.icon("plus", theme.ACCENT))
        self.add_button.setIconSize(QSize(14, 14))
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setAutoDefault(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(0)
        layout.addWidget(card_title(kind.icon, kind.title, kind.color, len(rows)))
        layout.addSpacing(8)
        for row in rows:
            layout.addWidget(row)
        layout.addSpacing(10)
        layout.addWidget(self.add_button)
        layout.addStretch()


class RelationsPage(QScrollArea):
    link_requested = Signal(str, int)     # un nome è stato cliccato: (tipo, ID)

    def __init__(self, repo: Repository, kind: ElementKind, element_id: int, sources: LinkSources, saves: PendingSaves):
        super().__init__()
        self._repo, self._kind, self._element_id, self._sources, self._saves = repo, kind, element_id, sources, saves
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reload()

    def reload(self, focus_relation: int | None = None) -> None:
        """Ridisegna i riquadri; il testo della relazione `focus_relation` è pronto per essere scritto."""
        relations = self._repo.relations(self._element_id)
        linked = {relation.other.id for relation in relations}
        groups = QHBoxLayout()
        groups.setSpacing(16)
        focus: InlineEdit | None = None
        for related in self._kind.related:
            kind = KINDS[related]
            rows = []
            for relation in (r for r in relations if r.other.kind == related):
                image = self._repo.media_file(relation.other.image)
                row = _RelationRow(relation, kind.color, image)
                row.name.clicked.connect(lambda _=False, other=relation.other: self.link_requested.emit(other.kind, other.id))
                row.label.textEdited.connect(lambda _text, row=row: self._saves.add(
                    ("relation", row.relation.id),
                    lambda: self._repo.update_relation(row.relation.id, label=row.label.text())))
                row.label.editingFinished.connect(self._saves.flush)
                row.unlink_requested.connect(lambda relation_id=relation.id: self._unlink(relation_id))
                if relation.id == focus_relation:
                    focus = row.label
                rows.append(row)
            group = _Group(kind, rows)
            group.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            group.add_button.clicked.connect(lambda _=False, kind=kind, button=group.add_button: choose_element(
                self, self._repo, self._sources, kind, linked, self._element_id, button, self._link))
            groups.addWidget(group, 1)

        note = QHBoxLayout()
        note.setSpacing(8)
        note.addWidget(IconLabel("info", theme.MUTED, 15))
        text = QLabel("Queste relazioni compaiono anche nei Grafi e nella scheda dell’altro elemento.")
        text.setStyleSheet(f"color: {theme.MUTED};")
        note.addWidget(text)
        note.addStretch()
        content = QWidget()
        content.setFocusPolicy(Qt.ClickFocus)       # un clic nel vuoto toglie il cursore dal testo
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.addLayout(groups)
        layout.addSpacing(16)
        layout.addLayout(note)
        layout.addStretch()
        self.setWidget(content)         # sostituisce il contenuto precedente (e lo elimina)
        if focus is not None:
            QTimer.singleShot(0, focus.setFocus)

    def _link(self, other_id: int) -> None:
        if not self._saves.flush():
            return
        relation_id = None
        try:
            relation_id = self._repo.add_relation(self._element_id, other_id)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self.reload(relation_id)

    def _unlink(self, relation_id: int) -> None:
        if not self._saves.flush():
            return
        try:
            self._repo.remove_relation(relation_id)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self.reload()
