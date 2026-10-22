"""Popup base: finestra sopra la schermata con sfondo attenuato, titolo, corpo e pulsanti Annulla / conferma."""

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QColor, QIntValidator, QPainter
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...dnd import FIELD_MAX

DELETE = 2  # codice di chiusura: l'utente ha tenuto premuto «elimina»


def field_label(text: str, hint: str = "") -> QLabel:
    """Etichetta di un campo, con una nota facoltativa in grigio («(facoltativo)»)."""
    label = QLabel(f'{text} <span style="font-weight: 400; color: {theme.MUTED}">{hint}</span>' if hint else text)
    label.setObjectName("FieldLabel")
    return label


def labeled(text: str, widget: QWidget, hint: str = "") -> QVBoxLayout:
    """Un campo con la sua etichetta sopra."""
    layout = QVBoxLayout()
    layout.setSpacing(6)
    layout.addWidget(field_label(text, hint))
    layout.addWidget(widget)
    return layout


def note(text: str) -> QLabel:
    """Una frase di spiegazione in grigio, sotto i campi."""
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    label.setFont(theme.ui_font(13))
    return label


def line_edit(text: str = "", placeholder: str = "", limit: int = FIELD_MAX) -> QLineEdit:
    """Un campo di testo su una riga, della misura dei campi dei popup."""
    edit = QLineEdit(text)
    edit.setFixedHeight(40)
    edit.setMaxLength(limit)
    edit.setFont(theme.ui_font(14))
    edit.setPlaceholderText(placeholder)
    return edit


def number_edit(text: str, low: int, high: int) -> QLineEdit:
    """Un campo per un numero intero fra `low` e `high` (il testo può restare vuoto: chi legge decide che cosa vale)."""
    edit = line_edit(text, limit=len(str(high)))
    edit.setValidator(QIntValidator(low, high))
    return edit


def remove_button(tooltip: str = "Togli") -> QToolButton:
    """La piccola «x» per togliere una riga da un elenco di un popup."""
    button = QToolButton()
    button.setObjectName("CloseButton")
    button.setIcon(icons.icon("x", theme.MUTED))
    button.setIconSize(QSize(16, 16))
    button.setFixedSize(30, 30)
    button.setToolTip(tooltip)
    button.setCursor(Qt.PointingHandCursor)
    button.setFocusPolicy(Qt.NoFocus)
    return button


class PopupDialog(QDialog):
    """Le sottoclassi riempiscono `self.body` (e, accanto ai pulsanti, `self.footer_left` e `self.footer_right`).

    Il popup è modale e copre tutta la finestra: lo sfondo si attenua e nulla resta sopra lo strato scuro.
    Esc lo chiude. Cambiando titolo e testo del pulsante serve sia per creare sia per modificare.
    Con `buttons=False` restano solo titolo e corpo (per i popup di sola informazione, come l'avanzamento).
    """

    def __init__(self, parent: QWidget, title: str, subtitle: str, primary_label: str, width: int = 720, buttons: bool = True):
        self._window = parent.window()
        super().__init__(self._window, Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._window.installEventFilter(self)  # per restare sopra la finestra se cambia posizione o misura
        self.finished.connect(lambda: self._window.removeEventFilter(self))

        title_label = QLabel(title)
        title_label.setFont(theme.serif_font(28, 500, -0.01))
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("Muted")
        subtitle_label.setWordWrap(True)

        heading = QVBoxLayout()
        heading.setSpacing(4)
        heading.addWidget(title_label)
        heading.addWidget(subtitle_label)
        header = QHBoxLayout()
        header.setAlignment(Qt.AlignTop)
        header.addLayout(heading, 1)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.footer_left = QHBoxLayout()
        self.footer_right = QHBoxLayout()      # prima di «Annulla»

        card = QFrame()
        card.setObjectName("PopupCard")
        card.setFixedWidth(width)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(64)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(0, 0, 0, 153))
        card.setGraphicsEffect(shadow)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 28, 30, 26)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addSpacing(24)
        layout.addLayout(self.body)
        if buttons:
            header.addWidget(self._close_button(), alignment=Qt.AlignTop)
            layout.addSpacing(28)
            layout.addLayout(self._footer(primary_label))

        outer = QVBoxLayout(self)
        outer.addWidget(card, alignment=Qt.AlignCenter)

    def _close_button(self) -> QToolButton:
        close = QToolButton()
        close.setObjectName("CloseButton")
        close.setIcon(icons.icon("x", theme.MUTED))
        close.setIconSize(QSize(18, 18))
        close.setFixedSize(32, 32)
        close.setToolTip("Chiudi")
        close.setCursor(Qt.PointingHandCursor)
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.reject)
        return close

    def _footer(self, primary_label: str) -> QHBoxLayout:
        cancel = QPushButton("Annulla")
        cancel.setFixedHeight(40)
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        self._primary = QPushButton(primary_label)
        self._primary.setObjectName("PrimaryButton")
        self._primary.setFixedHeight(40)
        self._primary.setDefault(True)
        self._primary.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addLayout(self.footer_left)
        footer.addStretch()
        footer.addLayout(self.footer_right)
        footer.addWidget(cancel)
        footer.addWidget(self._primary)
        return footer

    def set_primary_enabled(self, enabled: bool) -> None:
        self._primary.setEnabled(enabled)

    def set_primary_text(self, text: str) -> None:
        self._primary.setText(text)

    def showEvent(self, event):
        self.setGeometry(self._window.geometry())
        super().showEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Move, QEvent.Resize):
            self.setGeometry(self._window.geometry())
        return False

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect(), QColor(theme.OVERLAY))
