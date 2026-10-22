"""Impostazioni: le liste che si personalizzano (categorie di personaggi, luoghi e organizzazioni; tipi di pin delle mappe).

A sinistra si sceglie la lista, al centro si vedono le sue voci: si aggiungono, si modificano (nome, colore, icona), si riordinano e si eliminano.
La schermata non tocca il database: legge e scrive solo tramite il `Repository`.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.db import DatabaseError
from ...data.repository import Repository
from ...settings import BY_KEY, GROUPS, Entry, Group
from ..popups.base import DELETE
from ..popups.entry import create_category, edit_category
from ..popups.pin_type import create_pin_type, edit_pin_type
from ..widgets.entry_row import EntryRow
from ..widgets.group_label import group_label
from ..widgets.icon_label import IconLabel
from ..widgets.list_row import ListRow
from .base import Screen

_COLUMN_WIDTH = 720


class SettingsScreen(Screen):
    def __init__(self, repo: Repository):
        super().__init__()
        self._repo = repo
        self._group: Group = GROUPS[0]
        self._entries: list[Entry] = []
        self._rows: dict[str, ListRow] = {}

        self._icon = IconLabel("sliders", theme.MUTED, 32)
        self._title = QLabel()
        self._title.setFont(theme.serif_font(36, 500, -0.01))
        self._intro = QLabel()
        self._intro.setObjectName("Muted")
        self._intro.setWordWrap(True)
        self._intro.setFont(theme.ui_font(14))
        self._add = QPushButton()
        self._add.setIconSize(QSize(18, 18))
        self._add.setFixedHeight(38)
        self._add.setCursor(Qt.PointingHandCursor)
        self._add.clicked.connect(lambda _=False: self._create())
        self._list = QVBoxLayout()
        self._list.setSpacing(8)
        self._sidebar_list = self._make_sidebar_list()
        self._build_center()
        self.reload()

    # --- Costruzione -------------------------------------------------------------------------------
    def _make_sidebar_list(self) -> QWidget:
        heading = group_label("LISTE")
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(heading)
        layout.addSpacing(4)
        for group in GROUPS:
            row = ListRow(group.color, group.icon, group.title, "")
            row.clicked.connect(lambda _=False, key=group.key: self._select(key))
            layout.addWidget(row)
            self._rows[group.key] = row
        layout.addStretch()
        return holder

    def _build_center(self) -> None:
        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        title_row.addWidget(self._icon, alignment=Qt.AlignVCenter)
        title_row.addWidget(self._title, 1)
        title_row.addWidget(self._add, alignment=Qt.AlignVCenter)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addLayout(title_row)
        column.addSpacing(8)
        column.addWidget(self._intro)
        column.addSpacing(24)
        column.addLayout(self._list)
        column.addStretch(1)
        holder = QWidget()
        holder.setFixedWidth(_COLUMN_WIDTH)
        holder.setLayout(column)

        page = QWidget()
        centered = QHBoxLayout(page)
        centered.setContentsMargins(32, 28, 32, 28)
        centered.addWidget(holder, alignment=Qt.AlignTop | Qt.AlignHCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def create_sidebar_list(self) -> QWidget:
        return self._sidebar_list

    # --- Posizione e cronologia ------------------------------------------------------------------
    def current_target(self) -> str:
        return self._group.key

    def show_target(self, target: object) -> None:
        """Mostra la lista `target` (la chiave della sua schermata: «personaggi», «mappe»…)."""
        if target in BY_KEY:
            self._select(target, record=False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload()          # le voci possono essere cambiate mentre si era altrove (es. un tipo di pin creato dalle mappe)

    def _select(self, key: str, record: bool = True) -> None:
        if key == self._group.key:
            return
        self._group = BY_KEY[key]
        self.reload()
        if record:
            self.navigated.emit(key)

    # --- Contenuto ------------------------------------------------------------------------------------
    def _read(self, group: Group) -> list[Entry]:
        if group.kind is None:
            usage = self._repo.pin_type_usage()
            return [Entry(t.id, t.name, t.color, usage[t.id], t.icon) for t in self._repo.pin_types()]
        usage = self._repo.category_usage(group.kind)
        return [Entry(c.id, c.name, c.color, usage[c.id]) for c in self._repo.categories(group.kind)]

    def reload(self) -> None:
        """Rilegge le voci della lista scelta e ridisegna ciò che si vede."""
        group = self._group
        self._entries = self._read(group)
        for other in GROUPS:
            number = len(self._entries) if other is group else len(self._read(other))
            self._rows[other.key].set_selected(other is group)
            self._rows[other.key].set_caption(f"{number} {other.subject if number == 1 else other.plural}")
        self._icon.set_icon(group.icon, group.color)
        self._title.setText(group.title)
        self._intro.setText(group.intro)
        self._add.setText(f" {group.new}")
        self._add.setIcon(icons.icon("plus", theme.BG))
        self._add.setStyleSheet(theme.solid_button_style(group.color))
        while self._list.count():
            item = self._list.takeAt(0)
            item.widget().deleteLater()
        for index, entry in enumerate(self._entries):
            row = EntryRow(entry, group.count_text(entry.count), index == 0, index == len(self._entries) - 1)
            row.edit_requested.connect(lambda entry=entry: self._edit(entry))
            row.move_requested.connect(lambda offset, entry=entry: self._move(entry, offset))
            self._list.addWidget(row)

    # --- Azioni -------------------------------------------------------------------------------------------
    def _create(self) -> None:
        group = self._group
        if (create_pin_type(self, self._repo) if group.kind is None else create_category(self, self._repo, group)) is not None:
            self.reload()

    def _edit(self, entry: Entry) -> None:
        others = [other for other in self._entries if other.id != entry.id]
        group = self._group
        result = (edit_pin_type(self, self._repo, entry, others) if group.kind is None
                  else edit_category(self, self._repo, group, entry, others))
        if result in (QDialog.Accepted, DELETE):
            self.reload()

    def _move(self, entry: Entry, offset: int) -> None:
        try:
            if self._group.kind is None:
                self._repo.move_pin_type(entry.id, offset)
            else:
                self._repo.move_category(entry.id, offset)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self.reload()
