"""Il dettaglio di un incontro: il nome e il tipo con accanto la difficoltà (nei combattimenti) e, sotto, le schede tecniche che servono per
portarlo avanti, tutte in una riga: ognuna alta quanto il suo testo (una scheda molto lunga è larga due colonne) e, se non ci stanno tutte,
la riga scorre di lato. Niente altro."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import Creature, Encounter, Slot
from ...dnd import challenge_xp
from ...encounters import COMBAT, KIND_ICONS, KIND_LABELS
from ...formatting import thousands
from .difficulty_panel import DifficultyPanel, assessment_of
from .group_label import group_label
from .icon_label import IconLabel
from .stat_block import COLUMN_WIDTH, StatBlock

_GAP = 16
_WIDE = 2 * COLUMN_WIDTH + _GAP      # una scheda molto lunga ha due colonne: larga come due schede normali
_COLOR = theme.SECTION_COLORS["incontri"]


class _Name(QLabel):
    """Il nome dell'incontro: sta su una riga finché c'è posto (accanto c'è la difficoltà), poi va a capo."""

    def __init__(self):
        super().__init__()
        self.setFont(theme.serif_font(30, 500, -0.01))
        self.setWordWrap(True)

    def sizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 2, self.fontMetrics().lineSpacing())


class _CardRow(QScrollArea):
    """La riga delle schede: la pagina scorre in verticale, la riga solo in orizzontale (con Maiusc+rotella, la barra o il gesto laterale)."""

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.NoFocus)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.viewport().setAutoFillBackground(False)
        row = QWidget()
        self._layout = QHBoxLayout(row)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(_GAP)
        self.setWidget(row)
        row.setAutoFillBackground(False)        # `setWidget` lo riattiva

    def set_cards(self, cards: list[QWidget]) -> None:
        """Mostra queste schede, una dopo l'altra, ognuna in alto e alta quanto serve."""
        while self._layout.count():
            card = self._layout.takeAt(0).widget()      # (l'ultimo elemento è lo spazio vuoto a destra: non ha un widget)
            if card is not None:
                card.setParent(None)
                card.deleteLater()
        for card in cards:
            self._layout.addWidget(card, 0, Qt.AlignTop)
        self._layout.addStretch()
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        """Alta quanto la scheda più alta (Qt di suo darebbe una misura fissa), più la barra di scorrimento."""
        cards = [self._layout.itemAt(number).widget() for number in range(self._layout.count() - 1)]
        height = max((card.heightForWidth(card.minimumWidth()) for card in cards), default=0)
        return QSize(self.widget().minimumSizeHint().width(), height + self.horizontalScrollBar().sizeHint().height())

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.sizeHint().height())

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta()
        if delta.x() or event.modifiers() & Qt.ShiftModifier:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - (delta.x() or delta.y()))
            event.accept()
        else:
            event.ignore()      # la rotella da sola scorre la pagina


def _card(creature: Creature, label: str | None) -> QWidget:
    """Una scheda con, sopra, `label` (quante copie e quanti PE) se c'è."""
    block = StatBlock()
    block.set_creature(creature)
    card = QWidget()
    card.setFixedWidth(_WIDE if block.long else COLUMN_WIDTH)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    if label is not None:
        layout.addWidget(group_label(label))
    layout.addWidget(block)
    return card


class EncounterDetail(QScrollArea):
    edit_requested = Signal()

    def __init__(self):
        super().__init__()
        self._shown: int | None = None      # l'incontro mostrato: cambiandolo si torna in cima
        self._name = _Name()
        self._kind_icon = IconLabel("swords", _COLOR, 16)
        self._kind = QLabel()
        self._kind.setFont(theme.ui_font(14, 500))
        self._kind.setStyleSheet(f"color: {_COLOR};")
        edit = QPushButton(" Modifica")
        edit.setIcon(icons.icon("pencil"))
        edit.setIconSize(QSize(16, 16))
        edit.setFixedHeight(36)
        edit.setCursor(Qt.PointingHandCursor)
        edit.clicked.connect(self.edit_requested)
        self._difficulty = DifficultyPanel()
        self._empty = QLabel("Questo incontro non ha ancora schede tecniche: aggiungile da «Modifica».")
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        self._cards = _CardRow()

        kind = QHBoxLayout()
        kind.setSpacing(6)
        kind.addWidget(self._kind_icon)
        kind.addWidget(self._kind)
        kind.addStretch()
        title = QVBoxLayout()
        title.setSpacing(4)
        title.addWidget(self._name)
        title.addLayout(kind)
        header = QHBoxLayout()
        header.setSpacing(28)
        header.addLayout(title)
        header.addWidget(self._difficulty, alignment=Qt.AlignVCenter)
        header.addStretch()
        header.addWidget(edit, alignment=Qt.AlignVCenter)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 14, 28)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)
        layout.addLayout(header)
        layout.addSpacing(22)
        layout.addWidget(self._empty)
        layout.addWidget(self._cards)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)
        content.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)

    def forget(self) -> None:
        """L'incontro non si vede più: riaprendolo (anche lo stesso) si riparte dall'alto."""
        self._shown = None

    def show_encounter(self, encounter: Encounter, creatures: list[Creature]) -> None:
        """Mostra l'incontro con le sue schede (nell'ordine dell'incontro)."""
        if encounter.id != self._shown:
            self._shown = encounter.id
            self.verticalScrollBar().setValue(0)
            self._cards.horizontalScrollBar().setValue(0)
        combat = encounter.kind == COMBAT
        self._name.setText(encounter.name)
        self._kind.setText(KIND_LABELS[encounter.kind])
        self._kind_icon.set_icon(KIND_ICONS[encounter.kind], _COLOR)
        self._difficulty.setVisible(combat)
        if combat:
            self._difficulty.set_encounter(encounter, assessment_of(encounter, {c.id: c.challenge for c in creatures}))
        self._empty.setVisible(not creatures)
        labelled = combat or any(slot.quantity > 1 for slot in encounter.creatures)     # sopra le schede: quante copie (e quanti PE)
        self._cards.set_cards([_card(creature, self._label(slot, creature, combat) if labelled else None)
                               for slot, creature in zip(encounter.creatures, creatures)])

    @staticmethod
    def _label(slot: Slot, creature: Creature, combat: bool) -> str:
        xp = challenge_xp(creature.challenge)
        return f"×{slot.quantity}" + (f" · {thousands(xp)} PE ciascuno" if combat and xp is not None else "")
