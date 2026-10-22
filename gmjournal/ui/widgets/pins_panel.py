"""Il pannello destro di una mappa aperta: il suo nome, dove sta nell'albero e l'elenco dei suoi pin."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ... import theme
from ...data.models import Pin, PinType
from ..kinds import pin_caption
from .group_label import group_label
from .list_row import ListRow


class PinsPanel(QFrame):
    chosen = Signal(int)        # ID del pin scelto nell'elenco

    def __init__(self):
        super().__init__()
        self._title = QLabel()
        self._title.setFont(theme.serif_font(24, 500, -0.01))
        self._title.setWordWrap(True)
        self._path = QLabel()
        self._path.setObjectName("Muted")
        self._path.setWordWrap(True)
        self._count = group_label()
        self._rows = QVBoxLayout()
        self._rows.setSpacing(1)
        self._empty = QLabel()
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(0)
        layout.addWidget(self._title)
        layout.addWidget(self._path)
        layout.addSpacing(18)
        layout.addWidget(self._count)
        layout.addSpacing(6)
        layout.addLayout(self._rows)
        layout.addWidget(self._empty)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        content.setAutoFillBackground(False)     # lo sfondo è quello del pannello
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def show_pins(self, name: str, path: str, pins: list[tuple[Pin, PinType]], selected: int | None, empty: str) -> None:
        """`path` è dove sta la mappa («Regno › Valle»); vuoto se è al primo livello. `empty` è ciò che si legge se non ci sono pin."""
        self._title.setText(name)
        self._path.setText(path)
        self._path.setVisible(bool(path))
        while self._rows.count():
            self._rows.takeAt(0).widget().deleteLater()
        for pin, pin_type in pins:
            row = ListRow(theme.category_color(pin_type.color), pin_type.icon, pin.name, pin_caption(pin, pin_type), pin.id == selected)
            row.clicked.connect(lambda _=False, pin_id=pin.id: self.chosen.emit(pin_id))
            self._rows.addWidget(row)
        self._count.setText(f"PIN SULLA MAPPA  ·  {len(pins)}")
        self._empty.setText(empty)
        self._empty.setVisible(not pins)
