"""La scheda tecnica di una creatura come si legge al tavolo: nome, caratteristiche, difese e poi tratti, azioni, reazioni e azioni leggendarie.
Ha l'aspetto delle schede dei manuali ufficiali: carta beige, nome, titoli e filetti rossi, bordi arancio sopra e sotto.

Mostra solo ciò che serve a usare la creatura (non la descrizione né la fonte): così com'è sta anche dentro gli incontri.
Una scheda molto lunga, se c'è posto, si divide in due colonne come sui manuali: il testo scorre dalla prima alla seconda.
"""

from dataclasses import dataclass
from html import escape

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QWidget

from ... import theme
from ...data.models import Creature, Feature
from ...dnd import ABILITY_LABELS, FEATURE_SECTIONS, TRAIT, ability_text, xp_label

BLOCK_WIDTH = 720          # larghezza di una scheda nella sua pagina (due colonne, se è molto lunga)
COLUMN_WIDTH = 400          # larghezza di una scheda a una colonna: serve anche a decidere se è «molto lunga»
TWO_COLUMN_MIN = 680        # sotto questa larghezza una scheda, anche se lunga, resta in una colonna
COLUMN_GAP = 28
LONG_HEIGHT = 1400          # una scheda alta più di così (larga COLUMN_WIDTH) è «molto lunga»
_MARGIN_X, _MARGIN_Y = 22, 20
_SPACING = 6                # fra una parte e la successiva
_SECTION_GAP = 14           # sopra il titolo di una sezione


def paragraphs(text: str, lead: str = "") -> str:
    """Un testo su più righe come paragrafi HTML; `lead` (già HTML) apre il primo. Il testo è sempre protetto: niente di ciò che
    c'è scritto diventa codice."""
    lines = [escape(line) for line in text.splitlines() if line.strip()] or [""]
    lines[0] = lead + lines[0]
    return "".join(f'<p style="margin: 0 0 6px 0">{line}</p>' for line in lines)


def _label(html: str, size: int = 14) -> QLabel:
    label = QLabel(html)
    label.setTextFormat(Qt.RichText)
    label.setWordWrap(True)
    label.setFont(theme.ui_font(size))
    label.setStyleSheet(f"color: {theme.STAT_INK};")
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


def _property(name: str, value: str) -> QLabel:
    return _label(f'<b style="color: {theme.STAT_RED}">{escape(name)}</b> {escape(value)}')


class _Rule(QWidget):
    """Un filetto rosso: a punta (largo a sinistra, sottile a destra) fra i gruppi di dati, dritto sotto i titoli."""

    def __init__(self, tapered: bool = True):
        super().__init__()
        self._tapered = tapered
        self.setFixedHeight(5 if tapered else 2)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.STAT_RED))
        width, height = self.width(), self.height()
        if self._tapered:
            painter.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(width, height / 2), QPointF(0, height)]))
        else:
            painter.drawRect(0, 0, width, height)


@dataclass
class _Part:
    """Un pezzo della scheda (un titolo, un filetto, un dato, una voce…) con lo spazio che vuole sopra."""
    widget: QWidget
    gap: int = _SPACING
    keep: bool = False      # deve restare sopra al pezzo successivo (un titolo non resta solo in fondo a una colonna)


@dataclass(frozen=True)
class _Plan:
    split: int      # quanti pezzi stanno nella prima colonna (tutti, se la scheda ha una colonna sola)
    column: int     # larghezza di una colonna
    height: int     # altezza della scheda


def _height(widget: QWidget, width: int) -> int:
    """L'altezza che prende un pezzo largo `width`."""
    return widget.heightForWidth(width) if widget.hasHeightForWidth() else max(widget.sizeHint().height(), widget.minimumHeight())


class StatBlock(QFrame):
    def __init__(self):
        super().__init__()
        self._parts: list[_Part] = []
        self._plans: dict[int, _Plan] = {}      # la disposizione per ogni larghezza già vista (misurare i testi costa: si fa una volta)
        self.long = False       # se è molto lunga: con abbastanza larghezza va in due colonne
        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    # --- Misure ----------------------------------------------------------------------------------
    def sizeHint(self) -> QSize:
        return QSize(BLOCK_WIDTH, self.heightForWidth(BLOCK_WIDTH))

    def minimumSizeHint(self) -> QSize:
        return QSize(260, 0)

    def heightForWidth(self, width: int) -> int:
        """(Chi sta in un layout se lo sente chiedere con la larghezza di tutto lo spazio libero, anche se la scheda non può diventare così larga.)"""
        return self._plan(min(width, self.maximumWidth())).height

    def _stack(self, heights: list[int], start: int, stop: int) -> int:
        """L'altezza dei pezzi da `start` a `stop` (escluso), uno sotto l'altro: il primo non ha spazio sopra."""
        return sum(heights[start:stop]) + sum(part.gap for part in self._parts[start + 1:stop])

    def _heights(self, width: int) -> list[int]:
        return [_height(part.widget, width) for part in self._parts]

    def _plan(self, width: int) -> _Plan:
        if width not in self._plans:
            self._plans[width] = self._measure(width)
        return self._plans[width]

    def _measure(self, width: int) -> _Plan:
        """Come disporre i pezzi in una scheda larga `width`: in una colonna, oppure in due se è lunga e c'è posto.
        La seconda colonna comincia dove le due colonne risultano più pari (mai subito dopo un titolo)."""
        inner, count = width - 2 * _MARGIN_X, len(self._parts)
        if self.long and width >= TWO_COLUMN_MIN:
            column = (inner - COLUMN_GAP) // 2
            heights = self._heights(column)
            splits = [split for split in range(1, count) if not self._parts[split - 1].keep]
            if splits:
                best = min(splits, key=lambda split: max(self._stack(heights, 0, split), self._stack(heights, split, count)))
                return _Plan(best, column, max(self._stack(heights, 0, best), self._stack(heights, best, count)) + 2 * _MARGIN_Y)
        return _Plan(count, inner, self._stack(self._heights(inner), 0, count) + 2 * _MARGIN_Y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place()

    def _place(self) -> None:
        plan = self._plan(self.width())
        left, top = _MARGIN_X, _MARGIN_Y
        for index, part in enumerate(self._parts):
            if index == plan.split:
                left, top = left + plan.column + COLUMN_GAP, _MARGIN_Y
            elif index:
                top += part.gap
            height = _height(part.widget, plan.column)
            part.widget.setGeometry(left, top, plan.column, height)
            top += height

    # --- Disegno -----------------------------------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.STAT_PAPER))
        painter.fillRect(0, 0, self.width(), 3, QColor(theme.STAT_EDGE))
        painter.fillRect(0, self.height() - 3, self.width(), 3, QColor(theme.STAT_EDGE))
        plan = self._plan(self.width())
        if plan.split < len(self._parts):       # in due colonne, un filetto sottile le separa
            line = QColor(theme.STAT_RED)
            line.setAlpha(70)
            painter.fillRect(_MARGIN_X + plan.column + COLUMN_GAP // 2, _MARGIN_Y, 1, self.height() - 2 * _MARGIN_Y, line)

    # --- Contenuto -----------------------------------------------------------------------------------
    def _add(self, widget: QWidget, gap: int = _SPACING, keep: bool = False) -> None:
        widget.setParent(self)
        widget.show()
        self._parts.append(_Part(widget, gap, keep))

    def set_creature(self, creature: Creature) -> None:
        for part in self._parts:
            part.widget.setParent(None)
            part.widget.deleteLater()
        self._parts.clear()
        self._plans.clear()
        name = QLabel(creature.name)
        name.setFont(theme.serif_font(30, 500, -0.01))
        name.setStyleSheet(f"color: {theme.STAT_RED};")
        name.setWordWrap(True)
        kind = ", ".join(part for part in (" ".join(part for part in (creature.size, creature.kind) if part), creature.alignment) if part)
        self._add(name)
        if kind:
            self._add(_label(f"<i>{escape(kind)}</i>"))
        self._add(_Rule())
        for title, value in (("Classe Armatura", creature.armor_class), ("Punti ferita", creature.hit_points), ("Velocità", creature.speed)):
            if value:
                self._add(_property(title, value))
        self._add(_Rule())
        self._add(self._abilities(creature.abilities))
        self._add(_Rule())
        for title, value in self._details(creature):
            if value:
                self._add(_property(title, value))
        if creature.features:
            self._add(_Rule(), keep=True)
        for key, title in FEATURE_SECTIONS:
            features = [feature for feature in creature.features if feature.section == key]
            if features:
                self._add_section(None if key == TRAIT else title, features)
        heights = self._heights(COLUMN_WIDTH - 2 * _MARGIN_X)
        self.long = self._stack(heights, 0, len(self._parts)) + 2 * _MARGIN_Y > LONG_HEIGHT
        self._plans.clear()     # (se qualcuno ha misurato la scheda a metà, la misura valeva per una scheda non ancora «lunga»)
        self.updateGeometry()
        self._place()
        self.update()

    @staticmethod
    def _details(creature: Creature) -> list[tuple[str, str]]:
        passive = f"passive Perception {creature.passive}" if creature.passive is not None and "passive" not in creature.senses.lower() else ""
        challenge = f"{creature.challenge} ({xp_label(creature.challenge)})" if xp_label(creature.challenge) else creature.challenge
        return [("Tiri salvezza", creature.saves), ("Abilità", creature.skills), ("Vulnerabilità ai danni", creature.vulnerabilities),
                ("Resistenze ai danni", creature.resistances), ("Immunità ai danni", creature.immunities),
                ("Immunità alle condizioni", creature.condition_immunities), ("Sensi", ", ".join(part for part in (creature.senses, passive) if part)),
                ("Linguaggi", creature.languages), ("Grado di sfida", challenge)]

    @staticmethod
    def _abilities(scores: tuple[int, ...]) -> QWidget:
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)
        for column, (label, score) in enumerate(zip(ABILITY_LABELS, scores)):
            title = QLabel(label)
            title.setFont(theme.ui_font(12, 600, 0.04))
            title.setStyleSheet(f"color: {theme.STAT_RED};")
            title.setAlignment(Qt.AlignCenter)
            value = QLabel(ability_text(score))
            value.setFont(theme.ui_font(13))
            value.setStyleSheet(f"color: {theme.STAT_INK};")
            value.setAlignment(Qt.AlignCenter)
            grid.addWidget(title, 0, column)
            grid.addWidget(value, 1, column)
            grid.setColumnStretch(column, 1)
        return holder

    def _add_section(self, title: str | None, features: list[Feature]) -> None:
        if title:
            heading = QLabel(title)
            heading.setFont(theme.serif_font(21, 500))
            heading.setStyleSheet(f"color: {theme.STAT_RED};")
            self._add(heading, _SECTION_GAP, keep=True)
            self._add(_Rule(False), keep=True)
        for feature in features:
            lead = f'<b><i>{escape(feature.name)}.</i></b> ' if feature.name else ""
            self._add(_label(paragraphs(feature.text, lead)))
