"""La finestrella di un pin selezionato: tipo, nome, testo, la mappa che apre e i pulsanti per aprire la pagina o modificarlo."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QWidget

from ... import icons, theme
from ...data.models import Map, Pin, PinType
from ..kinds import pin_caption
from .anchored_card import AnchoredCard
from .icon_label import IconLabel

_WIDTH = 288


class PinCard(AnchoredCard):
    close_requested = Signal()
    page_requested = Signal()         # «Apri pagina»
    map_requested = Signal()          # «Apre la mappa: …»
    edit_requested = Signal()

    def __init__(self, pin: Pin, pin_type: PinType, opens: Map | None):
        super().__init__(_WIDTH)
        color = theme.category_color(pin_type.color)

        kind = QLabel(pin_caption(pin, pin_type).upper())
        kind.setFont(theme.ui_font(11, 600, 0.08))
        kind.setStyleSheet(f"color: {color};")
        close = QToolButton()
        close.setObjectName("CloseButton")
        close.setIcon(icons.icon("x", theme.MUTED))
        close.setIconSize(QSize(14, 14))
        close.setFixedSize(24, 24)
        close.setToolTip("Chiudi")
        close.setCursor(Qt.PointingHandCursor)
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close_requested)
        header = QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(IconLabel(pin_type.icon, color, 14))
        header.addWidget(kind, 1)
        header.addWidget(close)
        self.column.addLayout(header)
        self.column.addSpacing(6)

        name = QLabel(pin.name)
        name.setFont(theme.serif_font(24, 500, -0.01))
        name.setWordWrap(True)
        self.column.addWidget(name)
        if pin.brief:
            brief = QLabel(pin.brief)
            brief.setFont(theme.ui_font(13))
            brief.setStyleSheet(f"color: {theme.TEXT_SOFT};")
            brief.setWordWrap(True)
            self.column.addSpacing(6)
            self.column.addWidget(brief)
        if opens is not None:
            font = theme.ui_font(13, 600)
            text = QFontMetrics(font).elidedText(f"Apre la mappa: {opens.name}", Qt.ElideRight, _WIDTH - 32 - 30)
            link = QPushButton(" " + text)
            link.setObjectName("LinkButton")
            link.setIcon(icons.icon("map", theme.MUTED))
            link.setIconSize(QSize(15, 15))
            link.setStyleSheet("text-align: left; padding: 0; min-height: 24px;")
            link.setCursor(Qt.PointingHandCursor)
            link.clicked.connect(self.map_requested)
            self.column.addSpacing(10)
            self.column.addWidget(link)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        if pin.link is not None:
            page = QPushButton(" Apri pagina")
            page.setIcon(icons.icon("file", theme.BG))
            page.setIconSize(QSize(15, 15))
            page.setFixedHeight(34)
            page.setStyleSheet(theme.solid_button_style(color))
            page.setCursor(Qt.PointingHandCursor)
            page.clicked.connect(self.page_requested)
            buttons.addWidget(page, 1)
        else:
            buttons.addStretch()
        edit = QToolButton()
        edit.setIcon(icons.icon("pencil", theme.TEXT))
        edit.setIconSize(QSize(15, 15))
        edit.setFixedSize(34, 34)
        edit.setToolTip("Modifica pin")
        edit.setAccessibleName("Modifica pin")
        edit.setCursor(Qt.PointingHandCursor)
        edit.setFocusPolicy(Qt.NoFocus)
        edit.setStyleSheet(f"QToolButton {{ border: 1px solid {theme.BORDER_STRONG}; border-radius: 8px; background: transparent; }}"
                           f"QToolButton:hover {{ background: {theme.HOVER}; }}")
        edit.clicked.connect(self.edit_requested)
        buttons.addWidget(edit)
        holder = QWidget()
        holder.setLayout(buttons)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.column.addSpacing(14)
        self.column.addWidget(holder)
