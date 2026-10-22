"""Finestra principale e navigazione tra le schermate."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from .data.db import DatabaseError
from .data.models import LinkTarget
from .data.repository import Repository
from .sections import BY_KEY, SECTIONS
from .ui.screens import Screen, create_screen
from .ui.screens.elements import link_destination
from .ui.screens.home import HomeScreen
from .ui.shell.history import History
from .ui.shell.rightpanel import RightPanel
from .ui.shell.search import SearchController
from .ui.shell.sidebar import Sidebar
from .ui.shell.topbar import TopBar

HOME = "home"                    # chiave della Home (le altre sono in sections.py)
HOME_TITLE = "Le tue campagne"

Location = tuple[Path | None, str, object | None]   # (cartella della campagna o None, chiave schermata, elemento mostrato)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GM Journal")
        self.setMinimumSize(960, 600)
        available = self.screen().availableGeometry()
        self.resize(min(1440, int(available.width() * 0.9)), min(900, int(available.height() * 0.9)))

        self._history = History()              # voci: (cartella della campagna o None, chiave schermata, elemento mostrato)
        self._location: Location = (None, HOME, None)
        self._repo: Repository | None = None   # campagna aperta; resta aperta anche tornando alla Home
        self._panel_open = True
        self._screens: dict[str, Screen] = {}  # schermate della campagna aperta, create al primo uso
        self._side_panels: dict[str, QWidget] = {}
        self._sidebar_lists: dict[str, QWidget] = {}

        self._topbar = TopBar()
        self._sidebar = Sidebar()
        self._stack = QStackedWidget()
        self._right_panel = RightPanel()
        self._home = HomeScreen()
        self._stack.addWidget(self._home)

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._sidebar)
        body.addWidget(self._stack, 1)
        body.addWidget(self._right_panel)
        root = QWidget()
        root.setFocusPolicy(Qt.ClickFocus)  # un clic su un'area vuota toglie il cursore dalla ricerca
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._topbar)
        layout.addLayout(body, 1)
        self.setCentralWidget(root)
        root.setFocus()  # all'avvio il cursore non deve finire nella ricerca
        self._search = SearchController(self._topbar.search, root, self._find)

        self._topbar.sidebar_clicked.connect(self._toggle_sidebar)
        self._topbar.panel_clicked.connect(self._toggle_panel)
        self._topbar.back_clicked.connect(lambda: self._travel(self._history.back()))
        self._topbar.forward_clicked.connect(lambda: self._travel(self._history.forward()))
        self._topbar.home_clicked.connect(lambda: self._go(None, HOME))
        self._topbar.crumb_clicked.connect(self._open_crumb)
        self._topbar.bookmark_clicked.connect(self._toggle_bookmark)
        self._sidebar.bookmark_chosen.connect(lambda kind, target_id: self._go(self._repo.folder, *link_destination(kind, target_id)))
        self._sidebar.bookmark_removed.connect(lambda kind, target_id: self._change_bookmark(self._repo.remove_bookmark, kind, target_id))
        self._sidebar.section_selected.connect(lambda key: self._go(self._repo.folder, key))
        self._home.campaign_opened.connect(lambda folder: self._go(folder, SECTIONS[0].key))
        self._home.campaign_removing.connect(self._release_campaign)
        self._search.chosen.connect(lambda target: self._go(self._repo.folder, *link_destination(target.kind, target.id)))
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._topbar.focus_search)

        self._go(None, HOME)

    # --- Navigazione -----------------------------------------------------------
    def _go(self, folder: Path | None, key: str, target: object | None = None, record: bool = True) -> None:
        """Mostra la schermata `key` della campagna in `folder` (None = elenco campagne).

        `target` è l'elemento da mostrare nella schermata (es. una pagina); senza, la schermata mostra la sua vista generale.
        """
        if folder is not None:
            if not self._switch_campaign(folder):
                return
            self._screen(key).show_target(target)
        self._arrive(folder, key, record)

    def _arrive(self, folder: Path | None, key: str, record: bool = True) -> None:
        """La schermata `key` è quella visibile: registra dove si trova (anche l'elemento aperto) e aggiorna la finestra."""
        entry = (folder, key, self._screens[key].current_target() if folder is not None else None)
        if record:
            self._history.push(entry)
        self._location = entry
        self._refresh()

    def _travel(self, entry: Location | None) -> None:
        """Va a una voce della cronologia, senza registrarla di nuovo."""
        if entry is not None:
            self._go(*entry, record=False)

    def _toggle_sidebar(self) -> None:
        self._sidebar.toggle_collapsed()
        self._topbar.set_sidebar_open(not self._sidebar.collapsed)

    def _toggle_panel(self) -> None:
        self._panel_open = not self._panel_open
        self._refresh()

    def _open_panel(self) -> None:
        if not self._panel_open:
            self._toggle_panel()

    def _refresh(self) -> None:
        """Allinea barre, pannello e schermata alla posizione corrente."""
        folder, key, _ = self._location
        in_campaign = folder is not None
        screen = self._screen(key) if in_campaign else self._home
        self._stack.setCurrentWidget(screen)

        panel = self._side_panels.get(key) if in_campaign and screen.panel_visible() else None
        self._sidebar.setVisible(in_campaign)
        if in_campaign:
            self._sidebar.set_current(key)
            self._sidebar.set_context(self._sidebar_lists.get(key))
        if panel is not None:
            self._right_panel.show_content(panel)
        self._right_panel.setVisible(panel is not None and self._panel_open)

        self._topbar.set_location(self._crumbs(), in_campaign)
        current = screen.bookmark_target() if in_campaign else None
        self._topbar.set_bookmark(self._repo.is_bookmarked(*current) if current is not None else None)
        self._sidebar.set_bookmarks(self._repo.bookmarks() if in_campaign else [], current)
        self._topbar.set_sidebar_open(not self._sidebar.collapsed)
        self._topbar.set_panel_button(panel is not None, self._panel_open)
        self._topbar.set_history_state(self._history.can_back, self._history.can_forward)

    def _toggle_bookmark(self) -> None:
        """Il pulsante del segnalibro: segna o toglie il posto in cui si è."""
        current = self._screen(self._location[1]).bookmark_target() if self._repo is not None else None
        if current is not None:
            action = self._repo.remove_bookmark if self._repo.is_bookmarked(*current) else self._repo.add_bookmark
            self._change_bookmark(action, *current)

    def _change_bookmark(self, action, kind: str, target_id: int) -> None:
        try:
            action(kind, target_id)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self._refresh()

    def _crumbs(self) -> list[tuple[str, bool]]:
        """Il percorso in alto, ogni tratto con il testo e se si può premere: «Campagna › Sezione › …» (nell'elenco campagne, solo il titolo).
        Il tratto della sezione si preme se la schermata sta mostrando qualcosa di più della sua vista generale."""
        folder, key, _ = self._location
        if folder is None:
            return [(HOME_TITLE, False)]
        screen = self._screen(key)
        trail = screen.trail()
        return [(self._repo.campaign().name, True), (BY_KEY[key].label, bool(trail) or screen.current_target() is not None),
                *((text, True) for text, _target in trail)]

    def _open_crumb(self, index: int) -> None:
        """Un tratto del percorso è stato premuto: la campagna porta all'elenco campagne, la sezione alla sua vista generale,
        gli altri all'elemento che indicano."""
        folder, key, _ = self._location
        if folder is None:
            return
        if index == 0:
            self._go(None, HOME)
        else:
            trail = self._screen(key).trail()
            self._go(folder, key, trail[index - 2][1] if index >= 2 else None)

    def _find(self, query: str, limit: int) -> list[LinkTarget]:
        """I risultati della ricerca globale: pagine ed elementi della campagna aperta il cui nome corrisponde."""
        return self._repo.link_targets(query, limit=limit) if self._repo is not None else []

    # --- Campagna aperta -------------------------------------------------------
    def _switch_campaign(self, folder: Path) -> bool:
        """Apre la campagna in `folder` (chiudendo la precedente). False se non si riesce."""
        if self._repo is not None and self._repo.folder == folder:
            return True
        try:
            repo = Repository.open(folder)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
            return False
        if not self._close_campaign():
            repo.close()                        # l'utente resta dov'era: la nuova campagna non si apre
            return False
        self._repo = repo
        return True

    def _confirm_close_unsaved(self) -> bool:
        """Un salvataggio è fallito: chiede se chiudere comunque (perdendo l'ultima modifica) o restare."""
        box = QMessageBox(QMessageBox.Warning, "GM Journal", "Non sono riuscito a salvare l'ultima modifica. Chiudere comunque?", parent=self)
        close = box.addButton("Chiudi comunque", QMessageBox.DestructiveRole)
        stay = box.addButton("Resta", QMessageBox.RejectRole)
        box.setDefaultButton(stay)
        box.setEscapeButton(stay)
        box.exec()
        return box.clickedButton() is close

    def _close_campaign(self, ask: bool = True) -> bool:
        """Chiude la campagna aperta dopo aver salvato ciò che si stava scrivendo. Se un salvataggio non riesce (`ask`) chiede se
        chiudere comunque; False se l'utente sceglie di restare: in quel caso non si chiude nulla."""
        saved = [screen.flush() for screen in self._screens.values()]      # tutte, anche se una prima fallisce
        if ask and not all(saved) and not self._confirm_close_unsaved():
            return False
        for screen in self._screens.values():
            screen.blockSignals(True)           # da qui le schermate non dicono più nulla alla finestra (staccate si ridisegnerebbero, e la finestra le cercherebbe)
        for widget in (*self._screens.values(), *self._side_panels.values(), *self._sidebar_lists.values()):
            widget.setParent(None)
            widget.deleteLater()
        self._screens.clear()
        self._side_panels.clear()
        self._sidebar_lists.clear()
        if self._repo is not None:
            self._repo.close()
            self._repo = None
        return True

    def _release_campaign(self, folder: Path) -> None:
        """Prima che una campagna venga eliminata: chiude i suoi file e dimentica la cronologia che la cita."""
        if self._repo is not None and self._repo.folder == folder:
            self._close_campaign(ask=False)     # sta per essere eliminata: ciò che non si salva non conta
        self._history.reset((None, HOME, None))
        self._location = (None, HOME, None)

    def _screen(self, key: str) -> Screen:
        """La schermata `key` della campagna aperta; la crea al primo accesso."""
        if key not in self._screens:
            screen = create_screen(BY_KEY[key], self._repo)
            screen.navigated.connect(lambda _target, key=key: self._arrive(self._repo.folder, key))
            screen.open_requested.connect(lambda section, target: self._go(self._repo.folder, section, target))
            screen.panel_requested.connect(self._open_panel)
            screen.trail_changed.connect(self._refresh)
            self._screens[key] = screen
            self._stack.addWidget(screen)
            for store, widget in ((self._side_panels, screen.create_side_panel()),
                                  (self._sidebar_lists, screen.create_sidebar_list())):
                if widget is not None:
                    store[key] = widget
        return self._screens[key]

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._close_campaign():
            super().closeEvent(event)
        else:
            event.ignore()
