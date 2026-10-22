"""La finestrella per posare un pin nuovo o modificarne uno: tipo, nome e testo (o la pagina a cui è collegato), mappa che apre."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data.models import LinkTarget, Map, PinInput, PinType
from ...data.repository import NAME_MAX
from ..kinds import kind_icon, target_caption
from ..popups.base import field_label
from .anchored_card import AnchoredCard, ScrollBody
from .filter_chip import FilterChip
from .hold_button import HoldButton
from .icon_label import IconLabel

_WIDTH = 380
_PADDING = 18
_GAP = 6                    # fra un tipo e l'altro
_ADD_SIZE = 30              # il «+» che crea un tipo


def _link_button(text: str, icon_name: str, color: str) -> QPushButton:
    button = QPushButton(" " + text)
    button.setObjectName("DashedButton")
    button.setIcon(icons.icon(icon_name, color))
    button.setIconSize(QSize(15, 15))
    button.setCursor(Qt.PointingHandCursor)
    button.setFocusPolicy(Qt.NoFocus)
    return button


def _change_button(on_click) -> QPushButton:
    button = QPushButton("Cambia")
    button.setObjectName("LinkButton")
    button.setCursor(Qt.PointingHandCursor)
    button.setFocusPolicy(Qt.NoFocus)
    button.clicked.connect(on_click)
    return button


class PinForm(AnchoredCard):
    submitted = Signal()
    cancelled = Signal()
    delete_confirmed = Signal()
    type_changed = Signal(int)          # un altro tipo scelto
    new_type_requested = Signal()       # il «+» accanto ai tipi
    link_requested = Signal()           # «Collega a una pagina…» e «Cambia»
    map_requested = Signal()            # «Scegli o crea una mappa…» e «Cambia»

    def __init__(self, edit: bool, name: str = "", brief: str = ""):
        super().__init__(_WIDTH, padding=_PADDING, scrolls=True)
        self._type_id = 0
        self._color = theme.ACCENT
        self._link: LinkTarget | None = None
        self._opens: Map | None = None
        self._group = QButtonGroup(self)

        title = QLabel("Modifica pin" if edit else "Nuovo pin")
        title.setFont(theme.serif_font(22, 500, -0.01))
        close = QToolButton()
        close.setObjectName("CloseButton")
        close.setIcon(icons.icon("x", theme.MUTED))
        close.setIconSize(QSize(16, 16))
        close.setFixedSize(28, 28)
        close.setToolTip("Chiudi")
        close.setCursor(Qt.PointingHandCursor)
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.cancelled)
        header = QHBoxLayout()
        header.addWidget(title, 1)
        header.addWidget(close)

        self._types = QVBoxLayout()         # una riga per volta: i tipi vanno a capo quando non c'è più posto
        self._types.setSpacing(_GAP)
        types = QWidget()
        types.setLayout(self._types)
        self._types.setContentsMargins(0, 0, 0, 0)

        self._linked = self._make_linked_section()
        self._free = self._make_free_section(name, brief)
        self._map = self._make_map_section()

        self._primary = QPushButton("Salva modifiche" if edit else "Aggiungi pin")
        self._primary.setObjectName("PrimaryButton")
        self._primary.setFixedHeight(38)
        self._primary.setCursor(Qt.PointingHandCursor)
        self._primary.clicked.connect(self.submitted)
        cancel = QPushButton("Annulla")
        cancel.setFixedHeight(38)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.cancelled)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addStretch()
        footer.addWidget(cancel)
        footer.addWidget(self._primary)

        body = QWidget()
        fields = QVBoxLayout(body)
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setSpacing(14)
        fields.addWidget(self._section("Tipo", types))
        fields.addWidget(self._linked)
        fields.addWidget(self._free)
        fields.addWidget(self._map)
        if edit:
            delete = HoldButton("Tieni premuto per eliminare il pin")
            delete.confirmed.connect(self.delete_confirmed)
            hint = QLabel("Trascina il pin sulla mappa per spostarlo.")
            hint.setObjectName("Muted")
            hint.setFont(theme.ui_font(12))
            fields.addWidget(delete)
            fields.addWidget(hint)
        self.column.setSpacing(14)
        self.column.addLayout(header)
        self.column.addWidget(ScrollBody(body, _WIDTH - 2 * _PADDING))      # in un'area bassa scorre: intestazione e pulsanti restano
        self.column.addLayout(footer)
        self._refresh()

    @staticmethod
    def _section(label: str, content: QWidget | QVBoxLayout, hint: str = "") -> QWidget:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(field_label(label, hint))
        layout.addWidget(content) if isinstance(content, QWidget) else layout.addLayout(content)
        return holder

    def _make_linked_section(self) -> QWidget:
        """Pin collegato: nome e testo vengono da ciò a cui è collegato."""
        self._link_icon = IconLabel("file", theme.TEXT_SOFT, 16)
        self._link_name, self._link_caption = QLabel(), QLabel()
        self._link_name.setFont(theme.ui_font(14, 500))
        self._link_caption.setObjectName("Muted")
        self._link_caption.setFont(theme.ui_font(12))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(self._link_name)
        texts.addWidget(self._link_caption)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._link_icon)
        row.addLayout(texts, 1)
        row.addWidget(_change_button(self.link_requested))
        self._link_brief = QLabel()
        self._link_brief.setFont(theme.ui_font(13))
        self._link_brief.setStyleSheet(f"color: {theme.TEXT_SOFT};")
        self._link_brief.setWordWrap(True)
        box = QFrame()
        box.setObjectName("InfoBox")
        inside = QVBoxLayout(box)
        inside.setContentsMargins(12, 10, 8, 10)
        inside.setSpacing(6)
        inside.addLayout(row)
        inside.addWidget(self._link_brief)
        note = QLabel("Nome e testo vengono dalla pagina: se la modifichi, cambiano anche qui.")
        note.setObjectName("Muted")
        note.setFont(theme.ui_font(12))
        note.setWordWrap(True)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(field_label("Collegato a"))
        layout.addWidget(box)
        layout.addWidget(note)
        return holder

    def _make_free_section(self, name: str, brief: str) -> QWidget:
        """Pin libero: nome e testo si scrivono qui."""
        self._name = QLineEdit(name)
        self._name.setFixedHeight(38)
        self._name.setMaxLength(NAME_MAX)
        self._name.setPlaceholderText("Es. Torre abbandonata")
        self._name.textChanged.connect(self._update_primary)
        self._brief = QPlainTextEdit(brief)
        self._brief.setFixedHeight(64)
        self._brief.setPlaceholderText("Una riga che comparirà quando clicchi il pin.")
        self._link_button = _link_button("Collega a una pagina…", "link", theme.ACCENT)
        self._link_button.clicked.connect(self.link_requested)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        for label, widget, hint in (("Nome", self._name, ""), ("In breve", self._brief, "(facoltativo)")):
            layout.addWidget(self._section(label, widget, hint))
        layout.addWidget(self._link_button, alignment=Qt.AlignLeft)
        return holder

    def _make_map_section(self) -> QWidget:
        """La mappa che si apre dal pin."""
        self._map_icon = IconLabel("map", theme.TEXT_SOFT, 15)
        self._map_name = QLabel()
        self._map_name.setFont(theme.ui_font(14, 500))
        row = QHBoxLayout()
        row.setContentsMargins(12, 4, 6, 4)
        row.setSpacing(8)
        row.addWidget(self._map_icon)
        row.addWidget(self._map_name, 1)
        row.addWidget(_change_button(self.map_requested))
        self._map_row = QFrame()
        self._map_row.setObjectName("InfoBox")
        self._map_row.setLayout(row)
        self._map_button = _link_button("Scegli o crea una mappa…", "plus", theme.ACCENT)
        self._map_button.clicked.connect(self.map_requested)
        content = QVBoxLayout()
        content.setSpacing(0)
        content.addWidget(self._map_row)
        content.addWidget(self._map_button, alignment=Qt.AlignLeft)
        return self._section("Apre la mappa", content, "(facoltativo)")

    # --- Dati -----------------------------------------------------------------------------------
    def set_types(self, types: list[PinType], selected: int) -> None:
        """I tipi fra cui scegliere (il primo `selected`) e il «+» per aggiungerne uno."""
        while self._types.count():
            row = self._types.takeAt(0).layout()
            while row.count():
                widget = row.takeAt(0).widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
        self._group = QButtonGroup(self)
        entries: list[tuple[QWidget, int]] = []
        for pin_type in types:
            chip = FilterChip(pin_type.name, theme.category_color(pin_type.color), height=30)
            chip.setChecked(pin_type.id == selected)
            chip.clicked.connect(lambda _=False, pin_type=pin_type: self._choose_type(pin_type))
            self._group.addButton(chip)
            entries.append((chip, chip.sizeHint().width()))
        add = QPushButton()
        add.setObjectName("DashedButton")
        add.setIcon(icons.icon("plus", theme.TEXT_ACTIVE))
        add.setIconSize(QSize(14, 14))
        add.setFixedSize(_ADD_SIZE, _ADD_SIZE)
        add.setStyleSheet("padding: 0; min-height: 30px; border-radius: 15px;")
        add.setToolTip("Nuovo tipo di pin")
        add.setAccessibleName("Nuovo tipo di pin")
        add.setCursor(Qt.PointingHandCursor)
        add.setFocusPolicy(Qt.NoFocus)
        add.clicked.connect(self.new_type_requested)
        entries.append((add, _ADD_SIZE))

        row, used = None, 0
        for widget, width in entries:
            if row is None or used + _GAP + width > _WIDTH - 2 * _PADDING:
                if row is not None:
                    row.addStretch()
                row, used = QHBoxLayout(), -_GAP
                row.setSpacing(_GAP)
                self._types.addLayout(row)
            row.addWidget(widget)
            used += _GAP + width
        row.addStretch()
        chosen = next((t for t in types if t.id == selected), types[0])
        self._type_id, self._color = chosen.id, theme.category_color(chosen.color)
        self._refresh()

    def _choose_type(self, pin_type: PinType) -> None:
        self._type_id, self._color = pin_type.id, theme.category_color(pin_type.color)
        self._refresh()
        self.type_changed.emit(pin_type.id)

    def set_link(self, target: LinkTarget | None, brief: str = "") -> None:
        """Collega il pin a una pagina o a un elemento (`brief` è il suo testo «in breve»); `None` lo rende libero."""
        self._link = target
        if target is not None:
            self._link_icon.set_icon(kind_icon(target.kind), theme.TEXT_SOFT)
            self._link_name.setText(QFontMetrics(self._link_name.font()).elidedText(target.name, Qt.ElideRight, 210))
            self._link_caption.setText(target_caption(target))
            self._link_brief.setText(brief)
            self._link_brief.setVisible(bool(brief))
        self._refresh()

    def set_opens(self, node: Map | None) -> None:
        self._opens = node
        if node is not None:
            self._map_name.setText(QFontMetrics(self._map_name.font()).elidedText(node.name, Qt.ElideRight, 200))
        self._refresh()

    def map_anchor(self) -> QWidget:
        """Ciò che si vede nella parte «Apre la mappa» (sotto cui compare l'elenco delle mappe)."""
        return self._map_row if self._opens is not None else self._map_button

    def data(self) -> PinInput:
        return PinInput(self._type_id, self._name.text().strip(), self._brief.toPlainText().strip(),
                        (self._link.kind, self._link.id) if self._link is not None else None,
                        self._opens.id if self._opens is not None else None)

    def _refresh(self) -> None:
        """Mostra le parti che servono: collegato o libero, con o senza mappa."""
        linked = self._link is not None
        self._linked.setVisible(linked)
        self._free.setVisible(not linked)
        self._link_button.setIcon(icons.icon("link", self._color))
        self._map_row.setVisible(self._opens is not None)
        self._map_button.setVisible(self._opens is None)
        self._map_button.setIcon(icons.icon("plus", self._color))
        self._update_primary()
        self.layout().activate()

    def _update_primary(self) -> None:
        self._primary.setEnabled(self._link is not None or bool(self._name.text().strip()))

    def focus_name(self) -> None:
        self._name.setFocus()
