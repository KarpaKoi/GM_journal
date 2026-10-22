"""La scheda interna «Membri» di un'organizzazione: i personaggi che ne fanno parte, con ruolo, stato e note."""

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data.db import DatabaseError
from ...data.models import MEMBER_STATUSES, Relation
from ...data.repository import Repository
from ...data.search import fold
from ...elements import KINDS, MEMBER_STATES, ElementKind
from ...formatting import initials
from ..link_sources import LinkSources
from ..widgets.element_thumb import ElementThumb
from ..widgets.group_label import group_label
from ..widgets.icon_label import IconLabel
from ..widgets.menu import PopupMenu
from .parts import InlineEdit, NameLink
from .picking import choose_element
from .saves import PendingSaves

_COLUMNS = (22, 16, 10, 24)         # larghezze relative di Nome, Ruolo, Stato, Note
_ACTIONS_WIDTH = 28
_PADDING_X, _GAP = 20, 16
_ROW_HEIGHT, _HEADER_HEIGHT = 54, 38
_ROW_LINE = "#262a33"


class _StateButton(QAbstractButton):
    """Il pallino colorato e il nome dello stato; un clic permette di cambiarlo."""

    def __init__(self, status: str):
        super().__init__()
        self._label, self._color = MEMBER_STATES[status]
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("Cambia lo stato")
        self.setFixedHeight(28)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(QRectF(0, (self.height() - 7) / 2, 7, 7))
        painter.setFont(theme.ui_font(14))
        painter.setPen(QColor(theme.TEXT_ACTIVE if self.underMouse() else theme.FIELD_TEXT))
        painter.drawText(self.rect().adjusted(14, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, self._label)


class _TableRow(QWidget):
    """Una riga della tabella: le celle stanno nelle colonne, tutte uguali per ogni riga (anche l'intestazione),
    e in fondo c'è lo spazio del pulsante «altre azioni». Chi la usa mette le celle con `set_cells`."""

    def __init__(self, height: int):
        super().__init__()
        self.setFixedHeight(height)
        self._cells: list[QWidget] = []
        self._actions: QWidget | None = None

    def set_cells(self, cells: list[QWidget], actions: QWidget | None = None) -> None:
        self._cells, self._actions = cells, actions
        for widget in (*cells, *([actions] if actions else [])):
            widget.setParent(self)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        room = self.width() - 2 * _PADDING_X - _ACTIONS_WIDTH - _GAP * len(_COLUMNS)
        x = _PADDING_X
        for cell, share in zip(self._cells, _COLUMNS):
            width = round(room * share / sum(_COLUMNS))
            cell.setGeometry(x, (self.height() - cell.height()) // 2, width, cell.height())
            x += width + _GAP
        if self._actions is not None:
            self._actions.move(self.width() - _PADDING_X - self._actions.width(), (self.height() - self._actions.height()) // 2)

    def paintEvent(self, event) -> None:
        QPainter(self).fillRect(0, self.height() - 1, self.width(), 1, QColor(_ROW_LINE))


class _MemberRow(_TableRow):
    leader_toggled = Signal()
    status_requested = Signal(str)
    unlink_requested = Signal()

    def __init__(self, relation: Relation, color: str, image):
        super().__init__(_ROW_HEIGHT)
        self.relation = relation
        self.setAttribute(Qt.WA_Hover)
        thumb = ElementThumb(34, 9, 34)
        thumb.set_element(initials(relation.other.name), color, image)
        self.name = NameLink(relation.other.name)
        who = QWidget()
        who.setFixedHeight(34)
        who_layout = QHBoxLayout(who)
        who_layout.setContentsMargins(0, 0, 0, 0)
        who_layout.setSpacing(12)
        who_layout.addWidget(thumb)
        who_layout.addWidget(self.name)
        if relation.leader:
            badge = QLabel("Leader")
            badge.setFixedHeight(20)
            badge.setFont(theme.ui_font(11, 600))
            badge.setStyleSheet(f"background: {theme.HOVER}; color: {KINDS['organization'].color}; border-radius: 10px; padding: 0 8px;")
            who_layout.addWidget(badge)
        who_layout.addStretch()

        self.role = InlineEdit("Ruolo")
        self.role.setText(relation.label)
        self.note = InlineEdit("Nota")
        self.note.setText(relation.note)
        state = _StateButton(relation.status)
        state.clicked.connect(lambda: self._open_state_menu(state))

        self._more = QToolButton()
        self._more.setObjectName("ChipButton")
        self._more.setIcon(icons.icon("more", theme.MUTED))
        self._more.setIconSize(QSize(16, 16))
        self._more.setFixedSize(_ACTIONS_WIDTH, 24)
        self._more.setToolTip("Altre azioni")
        self._more.setCursor(Qt.PointingHandCursor)
        self._more.clicked.connect(self._open_menu)
        self._fade = QGraphicsOpacityEffect(self._more)
        self._more.setGraphicsEffect(self._fade)
        self._fade.setOpacity(0)
        self.set_cells([who, self.role, state, self.note], self._more)

    def _open_state_menu(self, anchor: QWidget) -> None:
        menu = PopupMenu(self, width=190)
        for status, (label, _) in MEMBER_STATES.items():
            menu.add_item(None, label, lambda status=status: self.status_requested.emit(status), checked=status == self.relation.status)
        menu.popup_below(anchor)

    def _open_menu(self) -> None:
        menu = PopupMenu(self, width=250)
        menu.add_item("flag", "Togli il ruolo di leader" if self.relation.leader else "Segna come leader", self.leader_toggled.emit)
        menu.add_item("unlink", "Scollega dall’organizzazione", self.unlink_requested.emit)
        menu.popup_at(self._more.mapToGlobal(self._more.rect().bottomRight()), align="right")

    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Enter, QEvent.HoverEnter):
            self._fade.setOpacity(1)
        elif event.type() in (QEvent.Leave, QEvent.HoverLeave):
            self._fade.setOpacity(0)
        return super().event(event)


class _Header(_TableRow):
    """I titoli delle colonne."""

    def __init__(self):
        super().__init__(_HEADER_HEIGHT)
        titles = []
        for text in ("Nome", "Ruolo", "Stato", "Note"):
            label = group_label(text)
            label.setFixedHeight(16)
            titles.append(label)
        for label in (titles[1], titles[3]):
            label.setContentsMargins(InlineEdit.TEXT_INSET, 0, 0, 0)      # allineato al testo delle righe sotto
        self.set_cells(titles)

    def paintEvent(self, event) -> None:
        QPainter(self).fillRect(0, self.height() - 1, self.width(), 1, QColor(theme.BORDER))


class MembersPage(QScrollArea):
    link_requested = Signal(str, int)     # un nome è stato cliccato: (tipo, ID)

    def __init__(self, repo: Repository, kind: ElementKind, element_id: int, sources: LinkSources, saves: PendingSaves):
        super().__init__()
        self._repo, self._kind, self._element_id, self._sources, self._saves = repo, kind, element_id, sources, saves
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reload()

    def reload(self, focus_relation: int | None = None) -> None:
        """Ridisegna la tabella; il ruolo del membro `focus_relation` è pronto per essere scritto."""
        members = sorted((r for r in self._repo.relations(self._element_id) if r.other.kind == "character"),
                         key=lambda r: (not r.leader, MEMBER_STATUSES.index(r.status), fold(r.other.name)))
        character = KINDS["character"]
        categories = {c.id: theme.category_color(c.color) for c in self._repo.categories(character.key)}
        linked = {r.other.id for r in members}

        def add_member(anchor: QWidget) -> None:
            choose_element(self, self._repo, self._sources, character, linked, None, anchor, self._link)

        count = QLabel(f"Membri noti · {len(members)}")
        count.setStyleSheet(f"color: {theme.MUTED};")
        add_button = QPushButton(" Aggiungi membro")
        add_button.setIcon(icons.icon("plus", theme.BG))
        add_button.setIconSize(QSize(16, 16))
        add_button.setFixedHeight(36)
        add_button.setStyleSheet(theme.solid_button_style(self._kind.color))
        add_button.setCursor(Qt.PointingHandCursor)
        add_button.clicked.connect(lambda _=False: add_member(add_button))
        top = QHBoxLayout()
        top.addWidget(count)
        top.addStretch()
        top.addWidget(add_button)

        footer = QPushButton(" Collega un personaggio come membro")
        footer.setIcon(icons.icon("plus", self._kind.color))
        footer.setIconSize(QSize(14, 14))
        footer.setFixedHeight(44)
        footer.setCursor(Qt.PointingHandCursor)
        footer.setStyleSheet(f"QPushButton {{ border: none; border-radius: 0; background: transparent; color: {theme.MUTED}; font-weight: 400; }}"
                             f"QPushButton:hover {{ background: {theme.HOVER_SOFT}; }}")
        footer.clicked.connect(lambda _=False: add_member(footer))

        table = QFrame()
        table.setObjectName("SheetCard")
        column = QVBoxLayout(table)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(_Header())
        focus = None
        for relation in members:
            image = self._repo.media_file(relation.other.image)
            row = _MemberRow(relation, categories[relation.other.category_id], image)
            row.name.clicked.connect(lambda _=False, other=relation.other: self.link_requested.emit(other.kind, other.id))
            row.role.textEdited.connect(lambda _text, row=row: self._saves.add(
                ("member-role", row.relation.id), lambda: self._repo.update_relation(row.relation.id, label=row.role.text())))
            row.note.textEdited.connect(lambda _text, row=row: self._saves.add(
                ("member-note", row.relation.id), lambda: self._repo.update_relation(row.relation.id, note=row.note.text())))
            for edit in (row.role, row.note):
                edit.editingFinished.connect(self._saves.flush)
            row.status_requested.connect(lambda status, relation_id=relation.id: self._change(relation_id, status=status))
            row.leader_toggled.connect(lambda relation_id=relation.id, leader=relation.leader: self._change(relation_id, leader=not leader))
            row.unlink_requested.connect(lambda relation_id=relation.id: self._unlink(relation_id))
            if relation.id == focus_relation:
                focus = row.role
            column.addWidget(row)
        column.addWidget(footer)

        note = QHBoxLayout()
        note.setSpacing(8)
        note.addWidget(IconLabel("info", theme.MUTED, 15))
        text = QLabel("L’appartenenza compare anche nella scheda del personaggio, sotto Relazioni.")
        text.setStyleSheet(f"color: {theme.MUTED};")
        note.addWidget(text)
        note.addStretch()

        content = QWidget()
        content.setFocusPolicy(Qt.ClickFocus)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addSpacing(12)
        layout.addWidget(table)
        layout.addSpacing(14)
        layout.addLayout(note)
        layout.addStretch()
        self.setWidget(content)
        if focus is not None:
            QTimer.singleShot(0, focus.setFocus)

    def _write(self, action, *args, **changes) -> int | None:
        """Esegue una modifica dei dati dopo aver salvato ciò che si stava scrivendo; poi ridisegna. Restituisce il suo risultato."""
        result = None
        if self._saves.flush():
            try:
                result = action(*args, **changes)
            except DatabaseError as error:
                QMessageBox.warning(self, "GM Journal", str(error))
        return result

    def _change(self, relation_id: int, **changes) -> None:
        self._write(self._repo.update_relation, relation_id, **changes)
        self.reload()

    def _link(self, character_id: int) -> None:
        relation_id = self._write(self._repo.add_relation, self._element_id, character_id)
        self.reload(relation_id)

    def _unlink(self, relation_id: int) -> None:
        self._write(self._repo.remove_relation, relation_id)
        self.reload()
