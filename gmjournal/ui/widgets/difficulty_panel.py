"""Il blocco della difficoltà di un incontro di combattimento: com'è (banale… mortale), la barra con le soglie e, piccolo, il calcolo.
Sta accanto al titolo dell'incontro; le soglie con i nomi si leggono passando il mouse."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ... import theme
from ...data.models import Encounter
from ...dnd import DIFFICULTIES, DIFFICULTY_LABELS, Assessment, assess
from ...formatting import thousands

_WIDTH = 320
_TRACK = 8          # altezza della barra
_TICK = 16          # altezza dei segni delle soglie: sporgono sopra e sotto la barra
_TICK_WIDTH = 2


def assessment_of(encounter: Encounter, challenges: dict[int, str]) -> Assessment:
    """La difficoltà di un incontro; `challenges` = grado di sfida di ogni scheda (per ID)."""
    return assess([(group.level, group.count) for group in encounter.party],
                  [(challenges.get(slot.creature_id, ""), slot.quantity) for slot in encounter.creatures])


def party_text(encounter: Encounter) -> str:
    """«4 giocatori di livello 3» oppure «3 giocatori di livello 5 · 1 giocatore di livello 4»."""
    return " · ".join(f"{group.count} giocator{'e' if group.count == 1 else 'i'} di livello {group.level}" for group in encounter.party)


def multiplier_text(value: float) -> str:
    return "×" + (f"{value:g}".replace(".", ","))


class _Bar(QWidget):
    """La barra dei PE: riempita fino ai PE modificati, con un segno a ogni soglia."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(_TICK)
        self._assessment: Assessment | None = None

    def set_assessment(self, assessment: Assessment) -> None:
        self._assessment = assessment
        self.update()

    def paintEvent(self, event) -> None:
        a = self._assessment
        if a is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width, top = self.width(), (_TICK - _TRACK) / 2
        scale = width / max(a.thresholds[-1] * 1.25, a.adjusted * 1.05, 1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.BORDER))
        painter.drawRoundedRect(QRectF(0, top, width, _TRACK), _TRACK / 2, _TRACK / 2)
        painter.setBrush(QColor(theme.DIFFICULTY_COLORS[a.difficulty or "trivial"]))
        painter.drawRoundedRect(QRectF(0, top, max(min(a.adjusted * scale, width), _TRACK), _TRACK), _TRACK / 2, _TRACK / 2)
        painter.setBrush(QColor(theme.DISABLED))
        for threshold in a.thresholds:
            painter.drawRect(QRectF(min(round(threshold * scale), width - _TICK_WIDTH), 0, _TICK_WIDTH, _TICK))


class DifficultyPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(_WIDTH)
        self._verdict = QLabel()
        self._verdict.setFont(theme.ui_font(15, 600))
        self._total = QLabel()
        self._total.setObjectName("Muted")
        self._total.setFont(theme.ui_font(13))
        self._bar = _Bar()
        self._detail = QLabel()
        self._detail.setObjectName("Muted")
        self._detail.setWordWrap(True)
        self._detail.setFont(theme.ui_font(12))

        top = QHBoxLayout()
        top.addWidget(self._verdict)
        top.addStretch()
        top.addWidget(self._total)
        self._numbers = QWidget()
        numbers = QVBoxLayout(self._numbers)
        numbers.setContentsMargins(0, 0, 0, 0)
        numbers.setSpacing(4)
        numbers.addLayout(top)
        numbers.addWidget(self._bar)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._numbers)
        layout.addWidget(self._detail)

    def set_encounter(self, encounter: Encounter, assessment: Assessment) -> None:
        message = ("Scrivi i giocatori presenti (da «Modifica») per vedere la difficoltà." if not assessment.players else
                   "Aggiungi schede con un grado di sfida per vedere la difficoltà." if not assessment.monsters else "")
        self._numbers.setVisible(not message)
        if message:
            self._detail.setText(message)
            return
        self._verdict.setText(DIFFICULTY_LABELS[assessment.difficulty])
        self._verdict.setStyleSheet(f"color: {theme.DIFFICULTY_COLORS[assessment.difficulty]};")
        self._total.setText(f"{thousands(assessment.adjusted)} PE modificati")
        self._bar.set_assessment(assessment)
        self._numbers.setToolTip("<br>".join(f'<span style="color: {theme.DIFFICULTY_COLORS[key]}">●</span> {DIFFICULTY_LABELS[key]} '
                                             f"<b>{thousands(threshold)}</b> PE" for key, threshold in zip(DIFFICULTIES, assessment.thresholds)))
        steps = (f"{party_text(encounter)} · {thousands(assessment.xp)} PE dei mostri {multiplier_text(assessment.multiplier)} "
                 f"({assessment.monsters} {'mostro' if assessment.monsters == 1 else 'mostri'}"
                 f"{', gruppo piccolo' if assessment.players < 3 else ', gruppo grande' if assessment.players > 5 else ''})")
        if assessment.unrated:
            steps += (f". {assessment.unrated} {'creatura' if assessment.unrated == 1 else 'creature'} senza grado di sfida "
                      f"non {'conta' if assessment.unrated == 1 else 'contano'}.")
        self._detail.setText(steps)
