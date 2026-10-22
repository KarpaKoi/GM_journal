"""Pallino colorato selezionabile (scelta del colore di una copertina, di una categoria, dell'evidenziatore…)."""

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QHBoxLayout, QWidget

from ... import theme


class ColorSwatch(QAbstractButton):
    def __init__(self, color: str, name: str):
        super().__init__()
        self._color = color
        self.setCheckable(True)
        self.setToolTip(name)
        self.setAccessibleName(name)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(32, 32)

    def sizeHint(self) -> QSize:
        return QSize(32, 32)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        if self.isChecked():
            painter.setPen(QPen(QColor(theme.ACCENT), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, 15, 15)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(center, 11, 11)


class ColorPicker(QWidget):
    """Una riga con tutti i colori di `colors` (chiave -> (nome, colore); di base quelli delle categorie), uno solo scelto.
    Un colore sconosciuto diventa `fallback`."""

    chosen = Signal(str)        # la chiave del colore scelto dall'utente

    def __init__(self, spacing: int = 8, colors: dict[str, tuple[str, str]] = theme.CATEGORY_COLORS, fallback: str = "gray"):
        super().__init__()
        self._keys = list(colors)
        self._fallback = fallback
        self._group = QButtonGroup(self)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(spacing)
        for index, key in enumerate(self._keys):
            name, color = colors[key]
            swatch = ColorSwatch(color, name)
            self._group.addButton(swatch, index)
            row.addWidget(swatch)
        row.addStretch()
        self._group.idClicked.connect(lambda index: self.chosen.emit(self._keys[index]))
        self.set_value(self._keys[0])

    def value(self) -> str:
        return self._keys[self._group.checkedId()]

    def set_value(self, key: str) -> None:
        """Sceglie un colore (uno sconosciuto diventa `fallback`) senza emettere `chosen`."""
        self._group.button(self._keys.index(key if key in self._keys else self._fallback)).setChecked(True)
