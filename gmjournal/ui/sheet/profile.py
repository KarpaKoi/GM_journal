"""Le schede interne fatte di testo: «Profilo» (riquadri di campi e appunti liberi) e le schede di solo testo libero («Storia», «Descrizione»)."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.repository import Repository
from ...elements import NOTES, ElementKind, Field, Group
from ..editor.note_editor import NoteEditor
from ..link_sources import LinkSources
from ..widgets.field_edit import FieldEdit
from ..widgets.flow_layout import FlowLayout
from ..widgets.group_label import group_label
from ..widgets.icon_label import IconLabel
from .parts import NameLink, bind_text, card_title
from ..popups.images import text_image_picker
from .saves import PendingSaves

_NOTES_HEIGHT = 130        # altezza del testo degli appunti liberi (la barra di formattazione è sopra)
_GM_COLOR = theme.BOX_COLORS["master"][1]


def make_note_editor(repo: Repository, sources: LinkSources, element_id: int, key: str, text: str, saves: PendingSaves,
                     body_height: int | None) -> NoteEditor:
    editor = NoteEditor(sources.targets, sources.create, repo.import_image, text_image_picker(repo), repo.folder, repo.speller, body_height,
                         sources.preview)
    editor.set_content(text)
    bind_text(editor, repo, element_id, key, saves, editor.focus_lost)
    return editor


class LeadersField(QWidget):
    """Il campo «Leader» di un'organizzazione: non si scrive, mostra i membri segnati come leader nella scheda «Membri»
    (così il leader è scritto in un posto solo)."""

    link_requested = Signal(str, int)     # il nome di un leader è stato cliccato: (tipo, ID)
    members_requested = Signal()          # nessun leader: si vuole andare alla scheda «Membri»

    def __init__(self, repo: Repository, element_id: int):
        super().__init__()
        self._repo, self._element_id = repo, element_id
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.refresh()

    def refresh(self) -> None:
        """Rilegge i leader (possono essere cambiati nella scheda «Membri»)."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        leaders = [relation.other for relation in self._repo.relations(self._element_id) if relation.leader]
        if not leaders:
            button = QPushButton(" Segna un leader nei Membri")
            button.setObjectName("DashedButton")
            button.setIcon(icons.icon("users", theme.ACCENT))
            button.setIconSize(QSize(14, 14))
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(self.members_requested)
            self._layout.addWidget(button)
            return
        for index, leader in enumerate(leaders):
            if index:
                separator = QLabel(", ")
                separator.setStyleSheet(f"color: {theme.FIELD_TEXT};")
                self._layout.addWidget(separator)
            name = NameLink(leader.name)
            name.clicked.connect(lambda _=False, leader=leader: self.link_requested.emit(leader.kind, leader.id))
            self._layout.addWidget(name)
        self._layout.addStretch()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()


class ProfilePage(QScrollArea):
    link_requested = Signal(str, int)     # un collegamento è stato cliccato: (tipo, ID)
    members_requested = Signal()          # si vuole andare alla scheda «Membri»

    def __init__(self, repo: Repository, kind: ElementKind, element_id: int, texts: dict[str, str],
                 sources: LinkSources, saves: PendingSaves):
        super().__init__()
        self._repo, self._element_id, self._texts, self._sources, self._saves = repo, element_id, texts, sources, saves
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        groups = QHBoxLayout()
        groups.setSpacing(16)
        for group in kind.groups:
            widget = self._build_group(group)
            widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            groups.addWidget(widget, group.weight)

        notes_title = QHBoxLayout()
        notes_title.setSpacing(8)
        notes_title.addWidget(IconLabel("pencil", theme.MUTED, 15))
        label = group_label("Appunti liberi")
        label.setFont(theme.ui_font(12, 600, 0.08))
        notes_title.addWidget(label)
        notes_title.addStretch()
        notes = make_note_editor(repo, sources, element_id, NOTES, texts.get(NOTES, ""), saves, _NOTES_HEIGHT)
        notes.link_activated.connect(self.link_requested)

        content = QWidget()
        content.setFocusPolicy(Qt.ClickFocus)       # un clic nel vuoto toglie il cursore dal testo
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(0)
        layout.addLayout(groups)
        layout.addSpacing(18)
        layout.addLayout(notes_title)
        layout.addSpacing(10)
        layout.addWidget(notes)
        layout.addStretch()
        self.setWidget(content)

    def _build_field(self, field: Field) -> QWidget:
        if field.leaders:
            leaders = LeadersField(self._repo, self._element_id)
            leaders.link_requested.connect(self.link_requested)
            leaders.members_requested.connect(self.members_requested)
            return leaders
        edit = FieldEdit(field, self._sources)
        edit.set_content(self._texts.get(field.key, ""))
        bind_text(edit, self._repo, self._element_id, field.key, self._saves, edit.stopped)
        edit.link_activated.connect(self.link_requested)
        return edit

    def _build_group(self, group: Group) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SheetCard")
        frame.setProperty("gm", group.gm)
        grid = QGridLayout()
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(14)
        for column in range(group.columns):
            grid.setColumnStretch(column, 1)
        row = column = 0
        for field in group.fields:
            if field.wide and column:
                row, column = row + 1, 0
            cell = QWidget()
            cell.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(3)
            cell_layout.addWidget(group_label(field.label))
            cell_layout.addWidget(self._build_field(field))
            span = group.columns if field.wide else 1
            grid.addWidget(cell, row, column, 1, span, Qt.AlignTop)
            column += span
            if column >= group.columns:
                row, column = row + 1, 0
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(18, 16, 18, 18)
        outer.setSpacing(14)
        outer.addWidget(card_title(group.icon, group.title, _GM_COLOR if group.gm else theme.TEXT_SOFT))
        outer.addLayout(grid)
        outer.addStretch()
        return frame


class TextPage(QWidget):
    """Una scheda di solo testo libero che occupa tutta la scheda («Storia», «Descrizione»). Con `suggestions` sopra il testo
    compaiono dei titoli proposti: un clic ne scrive uno nel testo, e si usano solo quelli che servono."""

    link_requested = Signal(str, int)

    def __init__(self, repo: Repository, element_id: int, texts: dict[str, str], sources: LinkSources, saves: PendingSaves,
                 key: str, suggestions: tuple[str, ...] = ()):
        super().__init__()
        editor = make_note_editor(repo, sources, element_id, key, texts.get(key, ""), saves, None)
        editor.link_activated.connect(self.link_requested)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(0)
        if suggestions:
            title = QHBoxLayout()
            title.setSpacing(10)
            label = group_label("Suggerimenti")
            label.setFont(theme.ui_font(11, 600, 0.08))
            hint = QLabel("Un clic scrive il titolo nel testo, dove sta il cursore. Usa solo quelli che ti servono.")
            hint.setStyleSheet(f"color: {theme.MUTED};")
            title.addWidget(label)
            title.addWidget(hint, 1)
            chips = FlowLayout(spacing=8)
            for text in suggestions:
                chip = QPushButton(text)
                chip.setObjectName("SuggestionChip")
                chip.setCursor(Qt.PointingHandCursor)
                chip.setFocusPolicy(Qt.NoFocus)         # il cursore del testo non si sposta cliccando
                chip.clicked.connect(lambda _=False, text=text: editor.insert_title(text))
                chips.addWidget(chip)
            layout.addLayout(title)
            layout.addSpacing(10)
            layout.addLayout(chips)
            layout.addSpacing(16)
        layout.addWidget(editor)
