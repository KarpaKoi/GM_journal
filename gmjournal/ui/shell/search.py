"""La ricerca globale: sotto il campo in alto compare l'elenco dei risultati; Invio o un clic ne apre uno."""

from typing import Callable

from PySide6.QtCore import QObject, QPoint, QRect, Signal
from PySide6.QtWidgets import QWidget

from ...data.models import LinkTarget
from ..editor.link_ui import TargetPopup
from .topbar import SearchBox

MAX_RESULTS = 8


class SearchController(QObject):
    """Collega il campo di ricerca all'elenco dei risultati. `source(testo, quanti)` dà i risultati; `host` è il widget
    della finestra su cui l'elenco compare (sopra a tutto il resto)."""

    chosen = Signal(object)   # LinkTarget: il risultato scelto

    def __init__(self, box: SearchBox, host: QWidget, source: Callable[[str, int], list[LinkTarget]]):
        super().__init__(box)
        self._box, self._host, self._source = box, host, source
        self._popup = TargetPopup(host, width=box.width())
        self._popup.chosen.connect(self._accept)
        box.edited.connect(self._refresh)
        box.stepped.connect(self._popup.move_selection)
        box.submitted.connect(self._submit)
        box.dismissed.connect(self._dismiss)
        box.focus_changed.connect(lambda gained: self._refresh() if gained else self._popup.hide())

    def _refresh(self) -> None:
        """Mostra i risultati per il testo scritto; senza testo l'elenco resta chiuso."""
        query = self._box.text()
        if not query:
            self._popup.hide()
            return
        anchor = QRect(self._box.mapTo(self._host, QPoint(0, 0)), self._box.size())
        self._popup.show_results(self._source(query, MAX_RESULTS), anchor)

    def _submit(self) -> None:
        target = self._popup.current_target() if self._popup.isVisible() else None
        if target is not None:
            self._accept(target)

    def _dismiss(self) -> None:
        self._box.clear()
        self._box.release_focus()

    def _accept(self, target: LinkTarget) -> None:
        self._dismiss()
        self.chosen.emit(target)
