"""Pezzi che le schede interne hanno in comune: il titolo di un riquadro, il nome che si può cliccare, la riga di testo modificabile."""

from PySide6.QtCore import QSize, Qt, SignalInstance
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QWidget

from ... import theme
from ...data.repository import RELATION_TEXT_MAX, Repository
from ..widgets.icon_label import IconLabel
from .saves import PendingSaves


def card_title(icon: str, title: str, color: str, count: int | None = None) -> QWidget:
    """L'intestazione di un riquadro: icona, TITOLO in maiuscolo e, se serve, quanti elementi contiene."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(IconLabel(icon, color, 15))
    label = QLabel(title.upper())
    label.setFont(theme.ui_font(12, 600, 0.08))
    label.setStyleSheet(f"color: {color};")
    layout.addWidget(label)
    if count is not None:
        number = QLabel(str(count))
        number.setFont(theme.ui_font(12, 500))
        number.setStyleSheet(f"color: {theme.MUTED};")
        layout.addWidget(number)
    layout.addStretch()
    return row


class NameLink(QAbstractButton):
    """Il nome di un elemento, in grassetto e sottolineato: un clic ne apre la scheda."""

    def __init__(self, name: str, inset: int = 0):
        super().__init__()
        self._inset = inset       # spazio a sinistra del nome (per allinearlo a un testo modificabile accanto)
        self.setText(name)
        self.setToolTip(name)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def _font(self):
        font = theme.ui_font(14, 600)
        font.setUnderline(True)
        return font

    def sizeHint(self) -> QSize:
        return QSize(self._inset + QFontMetrics(self._font()).horizontalAdvance(self.text()) + 2, 22)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 22)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        font = self._font()
        painter.setFont(font)
        painter.setPen(QColor(theme.ACCENT if self.underMouse() else theme.TEXT_ACTIVE))
        painter.drawText(self.rect().adjusted(self._inset, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(font).elidedText(self.text(), Qt.ElideRight, self.width() - self._inset))


class InlineEdit(QLineEdit):
    """Una riga di testo che sembra testo semplice finché non ci si scrive (poi compare il bordo)."""

    TEXT_INSET = 11      # distanza fra il bordo sinistro e l'inizio del testo: 1 di bordo, 8 di spazio, 2 di margine di Qt

    def __init__(self, placeholder: str):
        super().__init__()
        self.setObjectName("InlineEdit")
        self.setPlaceholderText(placeholder)
        self.setMaxLength(RELATION_TEXT_MAX)
        self.setFixedHeight(28)

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setCursorPosition(0)       # Qt porta il cursore in fondo e un testo lungo scorrerebbe: il testo si legge sempre dall'inizio

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.setCursorPosition(0)       # finito di scrivere, un testo lungo torna a mostrare l'inizio, allineato al nome sopra


def bind_text(widget, repo: Repository, element_id: int, key: str, saves: PendingSaves, finished: SignalInstance) -> None:
    """Fa salvare da solo il testo di `widget` (un campo o un riquadro di testo) nel campo `key` dell'elemento:
    poco dopo l'ultima modifica e subito quando `finished` segnala che si è smesso di scrivere."""
    widget.edited.connect(lambda: saves.add(("text", key), lambda: repo.save_text(element_id, key, widget.content())))
    finished.connect(saves.flush)
