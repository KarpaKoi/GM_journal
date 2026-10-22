"""Scelta di un'immagine: il pulsante «Scegli un'immagine…» oppure, a immagine scelta, il suo nome con «Cambia»."""

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QWidget

from ... import icons, theme
from ..image_files import choose_image_files
from .icon_label import IconLabel

Picker = Callable[[QWidget, "str | Path | None"], "str | Path | None"]   # (questo widget, scelta attuale) -> la nuova scelta, None se si annulla


def pick_from_computer(parent: QWidget, current: str | Path | None) -> Path | None:
    """Il modo di scegliere di una campagna che ancora non ha una libreria (nuova o da modificare dalla Home): un file del computer."""
    chosen = choose_image_files(parent)
    return chosen[0] if chosen else None


class ImageChoice(QWidget):
    """`image()` è un percorso già salvato nella campagna (str), un file nuovo da importare (Path) o None.
    `picker` è ciò che si apre per scegliere: di norma un file del computer, nelle schede la libreria della campagna."""

    changed = Signal()

    def __init__(self, name_width: int = 150, picker: Picker = pick_from_computer):
        super().__init__()
        self._image: str | Path | None = None
        self._name_width = name_width
        self._picker = picker

        self._choose = QPushButton(" Scegli un’immagine…")
        self._choose.setObjectName("DashedButton")
        self._choose.setIcon(icons.icon("image"))
        self._choose.setIconSize(QSize(16, 16))
        self._choose.setCursor(Qt.PointingHandCursor)
        self._choose.setAutoDefault(False)
        self._choose.clicked.connect(self._pick)

        self._file_name = QLabel()
        remove = QToolButton()
        remove.setObjectName("ChipButton")
        remove.setIcon(icons.icon("x", theme.MUTED))
        remove.setIconSize(QSize(13, 13))
        remove.setFixedSize(22, 22)
        remove.setToolTip("Rimuovi immagine")
        remove.setCursor(Qt.PointingHandCursor)
        remove.clicked.connect(lambda: self.set_image(None, notify=True))
        chip_layout = QHBoxLayout()
        chip_layout.setContentsMargins(10, 0, 6, 0)
        chip_layout.setSpacing(8)
        chip_layout.addWidget(IconLabel("image", theme.MUTED, 15))
        chip_layout.addWidget(self._file_name)
        chip_layout.addWidget(remove)
        chip = QFrame()
        chip.setObjectName("Chip")
        chip.setFixedHeight(32)
        chip.setLayout(chip_layout)
        change = QPushButton("Cambia")
        change.setObjectName("LinkButton")
        change.setCursor(Qt.PointingHandCursor)
        change.setAutoDefault(False)
        change.clicked.connect(self._pick)
        self._chip = QWidget()
        chip_row = QHBoxLayout(self._chip)
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(6)
        chip_row.addWidget(chip)
        chip_row.addWidget(change)
        chip_row.addStretch()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._choose)
        layout.addWidget(self._chip)
        self.set_image(None)

    def image(self) -> str | Path | None:
        return self._image

    def set_image(self, image: str | Path | None, notify: bool = False) -> None:
        self._image = image
        self._choose.setVisible(image is None)
        self._chip.setVisible(image is not None)
        if image is not None:
            metrics = QFontMetrics(self._file_name.font())
            shown = metrics.elidedText(Path(image).name, Qt.ElideMiddle, self._name_width)
            self._file_name.setText(shown)
            self._file_name.setFixedWidth(metrics.horizontalAdvance(shown) + 2)
        if notify:
            self.changed.emit()

    def _pick(self) -> None:
        chosen = self._picker(self, self._image)
        if chosen is not None:
            self.set_image(chosen, notify=True)
