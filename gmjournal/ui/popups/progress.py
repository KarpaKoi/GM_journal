"""Popup di avanzamento per le operazioni lunghe (backup, ripristino): compare solo se durano più di mezzo secondo."""

import time
from typing import Callable, TypeVar

from PySide6.QtWidgets import QApplication, QProgressBar, QWidget

from ...data.backup import Progress
from .base import PopupDialog

_DELAY = 0.5   # secondi: prima di questa soglia il popup non si mostra (le operazioni brevi non lampeggiano)
T = TypeVar("T")


class ProgressPopup(PopupDialog):
    """Titolo, frase e una barra che si riempie. Non si può chiudere: finisce da solo."""

    def __init__(self, parent: QWidget, title: str, subtitle: str):
        super().__init__(parent, title, subtitle, "", width=480, buttons=False)
        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self.body.addWidget(self._bar)

    def set_progress(self, done: int, total: int) -> None:
        self._bar.setRange(0, total)
        self._bar.setValue(done)

    def reject(self) -> None:
        """Esc non lo chiude: l'operazione non si interrompe a metà."""


def run_with_progress(parent: QWidget, title: str, subtitle: str, task: Callable[[Progress], T]) -> T:
    """Esegue `task(progress)` e ne restituisce il risultato. Se dura più di mezzo secondo compare un popup con la barra
    di avanzamento: la finestra si ridisegna ma non accetta clic finché l'operazione non è finita."""
    popup = ProgressPopup(parent, title, subtitle)
    started = time.monotonic()

    def progress(done: int, total: int) -> None:
        if not popup.isVisible() and time.monotonic() - started >= _DELAY:
            popup.setModal(True)
            popup.show()
        if popup.isVisible():
            popup.set_progress(done, total)
            QApplication.processEvents()

    try:
        return task(progress)
    finally:
        popup.done(0)
        popup.deleteLater()
