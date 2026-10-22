"""Il dettaglio di una scheda tecnica: la scheda vera e propria e, sotto, ciò che serve solo al master (ambiente, fonte, descrizione)."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import Creature
from .group_label import group_label
from .stat_block import BLOCK_WIDTH, StatBlock, paragraphs


class CreatureDetail(QScrollArea):
    edit_requested = Signal()

    def __init__(self, hint: str):
        super().__init__()
        self._shown: int | None = None      # la scheda mostrata: cambiandola si torna in cima
        self._hint = QLabel(hint)
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)
        edit = QPushButton(" Modifica")
        edit.setIcon(icons.icon("pencil"))
        edit.setIconSize(QSize(16, 16))
        edit.setFixedHeight(36)
        edit.setCursor(Qt.PointingHandCursor)
        edit.clicked.connect(self.edit_requested)
        self._block = StatBlock()
        self._block.setMaximumWidth(BLOCK_WIDTH)
        self._extras = QVBoxLayout()
        self._extras.setSpacing(4)

        self._details = QWidget()
        self._details.setMaximumWidth(BLOCK_WIDTH)
        layout = QVBoxLayout(self._details)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(edit, alignment=Qt.AlignRight)
        layout.addSpacing(12)
        layout.addWidget(self._block)
        layout.addSpacing(20)
        layout.addLayout(self._extras)

        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 14, 28)
        outer.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        outer.addWidget(self._hint)
        outer.addWidget(self._details)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)
        content.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
        self.show_creature(None)

    def show_creature(self, creature: Creature | None) -> None:
        """Mostra la scheda; con None, il suggerimento."""
        self._hint.setVisible(creature is None)
        self._details.setVisible(creature is not None)
        if creature is None:
            self._shown = None
            return
        if creature.id != self._shown:
            self._shown = creature.id
            self.verticalScrollBar().setValue(0)
        self._block.set_creature(creature)
        while self._extras.count():
            item = self._extras.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for title, text in (("Ambiente", creature.environment), ("Fonte", creature.source), ("Descrizione", creature.notes)):
            if text:
                body = QLabel(paragraphs(text))
                body.setTextFormat(Qt.RichText)
                body.setWordWrap(True)
                body.setFont(theme.ui_font(14))
                body.setStyleSheet(f"color: {theme.TEXT_SOFT};")
                body.setContentsMargins(0, 4, 0, 16)
                body.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self._extras.addWidget(group_label(title))
                self._extras.addWidget(body)
