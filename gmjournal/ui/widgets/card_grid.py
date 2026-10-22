"""Griglia che dispone le tessere su più colonne e le ridispone quando la finestra cambia."""

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QWidget


class CardGrid(QWidget):
    """Con più spazio aggiunge colonne (fino a `max_columns`) invece di allargare le tessere:
    la larghezza resta tra `min_card_width` e poco più, e l'altezza segue la larghezza (`card_height`)."""

    def __init__(self, max_columns: int, min_card_width: int, h_gap: int, v_gap: int,
                 card_height: Callable[[int], int]):
        super().__init__()
        self._max_columns = max_columns
        self._min_card_width = min_card_width
        self._h_gap = h_gap
        self._card_height = card_height
        self._cards: list[QWidget] = []
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(h_gap)
        self._grid.setVerticalSpacing(v_gap)
        self._grid.setAlignment(Qt.AlignTop)

    def set_cards(self, cards: list[QWidget]) -> None:
        """Sostituisce tutte le tessere (le vecchie vengono eliminate)."""
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = cards
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._columns != self._columns_for(self.width()):
            self._reflow()
        else:
            self._fit_heights()

    def _fit_heights(self) -> None:
        card_width = (self.width() - (self._columns - 1) * self._h_gap) // self._columns
        height = self._card_height(card_width)
        for card in self._cards:
            if card.height() != height:
                card.setFixedHeight(height)

    def _columns_for(self, width: int) -> int:
        fit = (width + self._h_gap) // (self._min_card_width + self._h_gap)
        return max(1, min(self._max_columns, fit))

    def _reflow(self) -> None:
        for column in range(self._max_columns):
            self._grid.setColumnStretch(column, 0)
        while self._grid.count():
            self._grid.takeAt(0)
        self._columns = self._columns_for(self.width())
        for column in range(self._columns):
            self._grid.setColumnStretch(column, 1)
        for index, card in enumerate(self._cards):
            self._grid.addWidget(card, index // self._columns, index % self._columns)
            card.show()
        self._fit_heights()
