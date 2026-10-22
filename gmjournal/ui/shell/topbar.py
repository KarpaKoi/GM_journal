"""Barra superiore: riduci barra sinistra, indietro/avanti, home, percorso, ricerca, pannello destro."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from ... import icons, theme
from ..widgets.breadcrumb import Breadcrumb
from ..widgets.search_field import SearchField


class SearchBox(SearchField):
    """Il campo di ricerca globale. Non cerca da solo: segnala ciò che l'utente fa (vedi `SearchController`)."""

    _PLACEHOLDER = "Cerca personaggi, luoghi, pagine…"
    _UNAVAILABLE = "Apri una campagna per cercare"

    def __init__(self):
        hint = QLabel("Ctrl K")
        hint.setObjectName("SearchHint")
        super().__init__("SearchBox", self._PLACEHOLDER, hint)
        self._hint = hint
        self.setFixedWidth(320)

    def text(self) -> str:
        return super().text().strip()

    def set_available(self, available: bool) -> None:
        """Fuori da una campagna (nell'elenco campagne) non c'è nulla da cercare."""
        if not available:
            self._edit.clear()
        self._edit.setEnabled(available)
        self._hint.setVisible(available)
        self._edit.setPlaceholderText(self._PLACEHOLDER if available else self._UNAVAILABLE)


class TopBar(QFrame):
    sidebar_clicked = Signal()
    back_clicked = Signal()
    forward_clicked = Signal()
    home_clicked = Signal()
    panel_clicked = Signal()
    bookmark_clicked = Signal()
    crumb_clicked = Signal(int)         # un tratto del percorso: la sua posizione (0 = il primo)

    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")
        self.setFixedHeight(theme.TOPBAR_HEIGHT)

        self._sidebar_button = self._button("panel-left", "Mostra o nascondi la barra laterale", self.sidebar_clicked, True)
        self._back = self._button("arrow-left", "Indietro", self.back_clicked)
        self._forward = self._button("arrow-right", "Avanti", self.forward_clicked)
        home = self._button("home", "Elenco campagne", self.home_clicked)
        self._bookmark_button = self._button("bookmark", "Aggiungi ai segnalibri", self.bookmark_clicked)
        self._panel_button = self._button("panel-right", "Mostra o nascondi il pannello destro", self.panel_clicked, True)
        self.search = SearchBox()

        self._location = Breadcrumb()
        self._location.clicked.connect(self.crumb_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 14, 0)
        layout.setSpacing(4)
        for widget in (self._sidebar_button, self._back, self._forward, home):
            layout.addWidget(widget)
        layout.addSpacing(10)
        layout.addWidget(self._location, 1)
        layout.addWidget(self._bookmark_button)
        layout.addWidget(self.search)
        layout.addSpacing(2)
        layout.addWidget(self._panel_button)

    def _button(self, icon_name: str, tooltip: str, signal: Signal, toggle: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("BarButton")
        button.setIcon(icons.icon(icon_name))
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(36, 36)
        button.setToolTip(tooltip)
        button.setCheckable(toggle)
        button.setFocusPolicy(Qt.NoFocus)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(signal)
        return button

    def set_location(self, crumbs: list[tuple[str, bool]], in_campaign: bool) -> None:
        """Aggiorna il percorso (ogni tratto: testo e se si può premere); `in_campaign` False nell'elenco campagne."""
        self._location.set_crumbs(crumbs)
        self._sidebar_button.setVisible(in_campaign)
        self.search.set_available(in_campaign)

    def set_bookmark(self, state: bool | None) -> None:
        """Il pulsante del segnalibro: nascosto (`None`) se il posto in cui si è non si può segnare, pieno se lo è già."""
        self._bookmark_button.setVisible(state is not None)
        self._bookmark_button.setIcon(icons.icon("bookmark-filled" if state else "bookmark", theme.ACCENT if state else theme.TEXT))
        self._bookmark_button.setToolTip("Togli dai segnalibri" if state else "Aggiungi ai segnalibri")

    def set_sidebar_open(self, is_open: bool) -> None:
        self._sidebar_button.setChecked(is_open)

    def set_panel_button(self, visible: bool, is_open: bool) -> None:
        self._panel_button.setVisible(visible)
        self._panel_button.setChecked(is_open)

    def set_history_state(self, can_back: bool, can_forward: bool) -> None:
        self._back.setEnabled(can_back)
        self._forward.setEnabled(can_forward)

    def focus_search(self) -> None:
        self.search.focus()
