"""Scrittura: i capitoli a sinistra, al centro la schermata iniziale (l'elenco dei capitoli) o la pagina aperta con il suo editor,
a destra l'elenco «Da fare» oppure, con una pagina aperta, i collegamenti (o, dopo un clic su un personaggio, un luogo
o un'organizzazione, la sua anteprima).

La schermata non tocca il database: legge e scrive solo tramite il `Repository`. Ciò che si scrive
si salva da solo poco dopo l'ultima modifica, quando si cambia pagina e quando il cursore esce dal testo.
"""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLineEdit, QMessageBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data import links
from ...data.db import DatabaseError
from ...data.models import Element, PageNode
from ...data.repository import TITLE_MAX, Repository, numbered_pages
from ...elements import KINDS
from ..editor.editor import RichEditor
from ..editor.toolbar import FormatToolbar
from ..link_sources import LinkSources
from ..popups.base import DELETE
from ..popups.element import edit_element
from ..popups.images import text_image_picker
from ..popups.page import PagePopup
from ..widgets.element_preview import ElementPreview
from ..widgets.empty_state import EmptyState
from ..widgets.links_panel import LinksPanel
from ..widgets.menu import PopupMenu
from ..widgets.page_tree import PageTree
from ..widgets.sidebar_list import sidebar_list
from ..widgets.todo_panel import TodoPanel
from ..widgets.writing_home import WritingHome
from .base import Screen
from .elements import link_destination

AUTOSAVE_MS = 800      # pausa di scrittura dopo la quale la pagina si salva
TITLE_HEIGHT = 56
_EDITOR_VIEW, _INDEX_VIEW, _EMPTY_VIEW = 0, 1, 2
_LINKS_PANEL, _ELEMENT_PANEL, _TODO_PANEL = 0, 1, 2      # cosa mostra il pannello destro


class ScritturaScreen(Screen):
    def __init__(self, repo: Repository):
        super().__init__()
        self._repo = repo
        self._page_id: int | None = None       # la pagina aperta (None = si vede la schermata iniziale)
        self._pending: set[str] = set()        # cosa non è ancora salvato: "content" (testo), "title" (titolo)
        self._save_warned = False              # l'errore di salvataggio è già stato mostrato: non lo ripetiamo a ogni lettera
        self._previewed: Element | None = None     # l'elemento di cui il pannello destro mostra l'anteprima (None = i collegamenti)

        self._timer = QTimer(self, singleShot=True, interval=AUTOSAVE_MS)
        self._timer.timeout.connect(self._save)

        sources = LinkSources(self, repo, lambda: (links.PAGE, self._page_id))
        self._editor = RichEditor(link_targets=sources.targets, create_target=sources.create,
                                  import_image=repo.import_image, media_dir=repo.folder,
                                  pick_images=text_image_picker(repo), speller=repo.speller, searchable=True,
                                  link_preview=sources.preview, encounters=sources.encounters())
        self._title = self._make_title()
        self._editor.set_header(self._title)
        self._tree = PageTree()
        self._index = WritingHome()
        self._links = LinksPanel()
        self._todo = TodoPanel()
        self._preview = ElementPreview()
        self._panel = self._make_panel()
        self._empty = EmptyState(
            "feather", theme.SECTION_COLORS["scrittura"], "Il diario della campagna inizia qui",
            "Scrivi capitoli e sottocapitoli. Con la @ li colleghi a personaggi, luoghi e organizzazioni.", "Crea il primo capitolo")
        self._views = QStackedWidget()
        self._sidebar_list = sidebar_list("CAPITOLI", "Nuovo capitolo", self._create, self._tree)
        self._build_center()

        self._editor.edited.connect(lambda: self._changed("content"))
        self._editor.focus_lost.connect(self._save)
        self._editor.link_activated.connect(self._open_target)
        self._title.textEdited.connect(lambda: self._changed("title"))
        self._title.returnPressed.connect(self._editor.focus_start)
        self._title.editingFinished.connect(self._finish_title)
        self._index.chosen.connect(self._open)
        self._index.create_requested.connect(self._create)
        self._index.menu_requested.connect(lambda page_id, point: self._open_menu(page_id, point, "right"))
        self._tree.selected.connect(self._open, Qt.QueuedConnection)   # dopo il clic: la scelta può salvare e ridisegnare l'albero
        self._tree.menu_requested.connect(self._open_menu)
        self._tree.moved.connect(self._move, Qt.QueuedConnection)   # l'albero si ricostruisce a trascinamento concluso
        self._links.chosen.connect(lambda target: self._open_target(target.kind, target.id))
        self._preview.cited_chosen.connect(lambda target: self._open_target(target.kind, target.id))
        self._preview.sheet_requested.connect(lambda: self.open_requested.emit(*link_destination(self._previewed.kind, self._previewed.id)))
        self._preview.edit_requested.connect(self._edit_previewed)
        self._empty.clicked.connect(self._create)
        self._todo.added.connect(lambda text: self._change_todos(self._repo.add_todo, text))
        self._todo.toggled.connect(lambda todo_id, done: self._change_todos(self._repo.set_todo_done, todo_id, done))
        self._todo.renamed.connect(lambda todo_id, text: self._change_todos(self._repo.rename_todo, todo_id, text))
        self._todo.removed.connect(lambda todo_id: self._change_todos(self._repo.delete_todo, todo_id))

        self._reload_tree()
        self._todo.set_todos(self._repo.todos())
        self._update_panel()

    # --- Costruzione -------------------------------------------------------------------
    @staticmethod
    def _make_title() -> QLineEdit:
        title = QLineEdit()
        title.setObjectName("PageTitle")
        title.setFont(theme.serif_font(36, 500))
        title.setFixedHeight(TITLE_HEIGHT)
        title.setMaxLength(TITLE_MAX)
        title.setPlaceholderText("Titolo")
        return title

    def _make_panel(self) -> QStackedWidget:
        """Il pannello destro: «Da fare» (senza pagina aperta); con una pagina aperta i suoi collegamenti oppure, sotto
        «‹ Collegamenti», l'anteprima di un elemento."""
        back = QToolButton()
        back.setObjectName("BackLink")
        back.setIcon(icons.icon("chevron-left", theme.MUTED))
        back.setIconSize(QSize(15, 15))
        back.setText("Collegamenti")
        back.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self._show_links)
        header = QHBoxLayout()
        header.setContentsMargins(20, 0, 20, 0)
        header.addWidget(back)
        header.addStretch()
        element = QWidget()
        layout = QVBoxLayout(element)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self._preview, 1)
        panel = QStackedWidget()
        panel.addWidget(self._links)        # _LINKS_PANEL
        panel.addWidget(element)            # _ELEMENT_PANEL
        panel.addWidget(self._todo)         # _TODO_PANEL
        return panel

    def _build_center(self) -> None:
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(FormatToolbar(self._editor))
        column.addWidget(self._editor, 1)
        self._views.addWidget(page)            # _EDITOR_VIEW
        self._views.addWidget(self._index)     # _INDEX_VIEW
        self._views.addWidget(self._empty)     # _EMPTY_VIEW
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._views)

    def create_side_panel(self) -> QWidget:
        return self._panel

    def create_sidebar_list(self) -> QWidget:
        return self._sidebar_list

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._page_id is not None and self._save():
            self._reload_content()     # un elemento citato può essere stato rinominato o eliminato mentre si era altrove
        if self._previewed is not None:
            self._load_preview(self._previewed.id)

    # --- Posizione e cronologia ------------------------------------------------------------
    def current_target(self) -> int | None:
        return self._page_id

    def bookmark_target(self) -> tuple[str, int] | None:
        return (links.PAGE, self._page_id) if self._page_id is not None else None

    def trail(self) -> list[tuple[str, int]]:
        """I capitoli che portano alla pagina aperta, ognuno col suo numero («1. La Locanda › 1.2 Lo straniero»)."""
        rows = {node.id: (node, number) for node, number in self._rows()}
        if self._page_id not in rows:
            return []
        node, number = rows[self._page_id]
        parent = rows.get(node.parent_id)
        return [*([(f"{parent[1]}. {parent[0].title}", parent[0].id)] if parent else []),
                (f"{number}. {node.title}" if parent is None else f"{number} {node.title}", node.id)]

    def show_target(self, target: object) -> None:
        """Una pagina, oppure (`None`) la schermata iniziale."""
        if target is None:
            if self._page_id is not None:
                self._close_page(record=False)
        elif target in self._tree.page_ids():
            self._open(target, record=False)

    def flush(self) -> bool:
        return self._save()

    # --- Aprire una pagina -------------------------------------------------------------------
    def _open(self, page_id: int, record: bool = True) -> None:
        """Mostra la pagina `page_id` dopo aver salvato quella aperta. `record`: l'ha scelta l'utente (va nella cronologia)."""
        if page_id == self._page_id:
            return
        if not self._save():
            self._tree.select_page(self._page_id)      # salvataggio fallito: si resta qui, il testo non si perde
            return
        try:
            page = self._repo.page(page_id)
        except DatabaseError as error:
            self._warn(error)
            self._reload_tree()
            return
        self._page_id = page_id
        self._show_title(page.title)
        self._editor.set_content(page.content)
        self._tree.select_page(page_id)
        self._show_links()
        self._refresh_links()
        self._update_view()
        if record:
            self.navigated.emit(page_id)

    def _close_page(self, record: bool = True) -> None:
        """Torna alla schermata iniziale, dopo aver salvato la pagina aperta."""
        if not self._save():
            self._tree.select_page(self._page_id)
            return
        self._page_id = None
        self._editor.clearFocus()          # l'editor sta per sparire: senza questo il cursore passerebbe all'albero, che aprirebbe la prima pagina
        self._title.clearFocus()
        self._title.clear()
        self._editor.set_content("")
        self._show_links()
        self._reload_tree()            # le parole e le date dell'elenco sono quelle appena salvate
        if record:
            self.navigated.emit(None)

    def _open_target(self, kind: str, target_id: int) -> None:
        """Apre ciò che un collegamento indica: una pagina qui, un elemento con la sua anteprima nel pannello destro,
        una mappa o un grafo nella loro schermata."""
        if kind == links.PAGE:
            self._open(target_id)
        elif kind in KINDS:
            if self._load_preview(target_id):
                self.panel_requested.emit()
        else:
            self.open_requested.emit(*link_destination(kind, target_id))

    def _load_preview(self, element_id: int) -> bool:
        """Mostra nel pannello destro l'anteprima dell'elemento. Se non esiste più mostra i collegamenti (False)."""
        try:
            element = self._repo.element(element_id)
            category = self._repo.category(element.category_id)
        except DatabaseError:
            self._show_links()
            return False
        image = self._repo.media_file(element.image)
        self._preview.show_element(element, category, image, self._repo.cited_by(element.kind, element.id))
        self._previewed = element
        self._update_panel()
        return True

    def _show_links(self) -> None:
        self._previewed = None
        self._update_panel()

    def _update_panel(self) -> None:
        if self._page_id is None:
            panel = _TODO_PANEL
        else:
            panel = _ELEMENT_PANEL if self._previewed is not None else _LINKS_PANEL
        self._panel.setCurrentIndex(panel)

    def _change_todos(self, action, *args) -> None:
        """Una modifica all'elenco «Da fare»; poi lo si rimostra com'è nel database."""
        try:
            action(*args)
        except DatabaseError as error:
            self._warn(error)
        self._todo.set_todos(self._repo.todos())

    def _edit_previewed(self) -> None:
        """«Modifica» nell'anteprima. Prima si salva la pagina: se l'elemento viene eliminato, i suoi collegamenti nel testo si tolgono."""
        if self._previewed is None or not self._save():
            return
        result = edit_element(self, self._repo, self._previewed)
        if result == DELETE:
            self._show_links()
        elif result == QDialog.Accepted:
            self._load_preview(self._previewed.id)
        self._reload_content()

    # --- Salvataggio -----------------------------------------------------------------------------
    def _changed(self, what: str) -> None:
        self._pending.add(what)
        self._timer.start()

    def _save(self) -> bool:
        """Salva ciò che è in sospeso. Se non ci riesce lo dice una volta e lascia tutto in sospeso."""
        self._timer.stop()
        if self._page_id is None:
            return True
        try:
            if "content" in self._pending:
                self._repo.save_content(self._page_id, self._editor.content())
                self._pending.discard("content")
                self._refresh_links()
            if "title" in self._pending:
                title = self._title.text().strip()
                if title:                                  # un titolo vuoto non si salva: resta il precedente
                    self._repo.rename_page(self._page_id, title)
                    self._reload_tree()
                self._pending.discard("title")
        except DatabaseError as error:
            if not self._save_warned:
                self._save_warned = True
                self._warn(f"Non riesco a salvare la pagina. Il testo resta qui e riproverò alla prossima modifica.\n\n{error}")
            return False
        self._save_warned = False
        return True

    def _finish_title(self) -> None:
        """Il titolo non può restare vuoto: se lo si svuota torna quello salvato."""
        if not self._title.text().strip():
            self._pending.discard("title")
            self._sync_title()
        self._save()

    def _sync_title(self) -> None:
        """Rimette nel campo il titolo salvato della pagina aperta."""
        node = self._node(self._page_id)
        if node is not None:
            self._show_title(node.title)

    def _show_title(self, title: str) -> None:
        self._title.setText(title)
        self._title.setCursorPosition(0)       # un titolo lungo si mostra dall'inizio

    def _warn(self, message: object) -> None:
        QMessageBox.warning(self, "GM Journal", str(message))

    # --- Albero e collegamenti -----------------------------------------------------------------
    def _rows(self) -> list[tuple[PageNode, str]]:
        return numbered_pages(self._repo.pages())

    def _node(self, page_id: int | None) -> PageNode | None:
        return next((node for node, _ in self._rows() if node.id == page_id), None)

    def _reload_tree(self) -> None:
        rows = self._rows()
        self._tree.set_pages(rows, self._page_id)
        self._index.set_pages(rows)
        self._update_view()
        self.trail_changed.emit()          # i titoli e i numeri possono essere cambiati

    def _update_view(self) -> None:
        if not self._tree.page_ids():
            view = _EMPTY_VIEW
        else:
            view = _EDITOR_VIEW if self._page_id is not None else _INDEX_VIEW
        self._views.setCurrentIndex(view)

    def _refresh_links(self) -> None:
        if self._page_id is not None:
            self._links.set_links(self._repo.cited_in(self._page_id), self._repo.cited_by(links.PAGE, self._page_id))

    @staticmethod
    def _chapters(rows: list[tuple[PageNode, str]]) -> list[tuple[int, str]]:
        """I capitoli principali, come scelte per il popup («1 · Titolo»)."""
        return [(node.id, f"{number} · {node.title}") for node, number in rows if node.parent_id is None]

    # --- Creare, modificare, spostare, eliminare ----------------------------------------------
    def _create(self, parent_id: int | None = None) -> None:
        popup = PagePopup(self, self._chapters(self._rows()), parent_id=parent_id)
        if popup.exec() != QDialog.Accepted:
            return
        try:
            page_id = self._repo.create_page(popup.title(), popup.parent_id())
        except DatabaseError as error:
            self._warn(error)
            return
        self._reload_tree()
        self._open(page_id)
        if self._page_id == page_id:
            self._editor.focus_start()

    def _open_menu(self, page_id: int, point, align: str = "left") -> None:
        node = self._node(page_id)
        if node is None:
            return
        menu = PopupMenu(self)
        menu.add_item("pencil", "Modifica…", lambda: self._edit(page_id))
        if node.parent_id is None:
            menu.add_item("plus", "Nuovo sottocapitolo", lambda: self._create(page_id))
        menu.add_separator()
        menu.add_item("trash", "Elimina…", lambda: self._edit(page_id), danger=True)   # si elimina dal popup di modifica
        menu.popup_at(point, align=align)

    def _edit(self, page_id: int) -> None:
        if not self._save():
            return
        rows = self._rows()
        node = next((n for n, _ in rows if n.id == page_id), None)
        if node is None:
            return
        subchapters = sum(1 for n, _ in rows if n.parent_id == page_id)
        popup = PagePopup(self, self._chapters(rows), node, node.parent_id, subchapters)
        result = popup.exec()
        if result == DELETE:
            self._delete(page_id)
        elif result == QDialog.Accepted:
            self._apply_edit(node, popup.title(), popup.parent_id(), len(rows))

    def _apply_edit(self, node: PageNode, title: str, parent_id: int | None, end: int) -> None:
        try:
            if title != node.title:
                self._repo.rename_page(node.id, title)
            if parent_id != node.parent_id:
                self._repo.move_page(node.id, parent_id, end)          # in fondo al nuovo capitolo
        except DatabaseError as error:
            self._warn(error)
        self._reload_tree()
        self._sync_title()

    def _move(self, page_id: int, parent_id: int | None, index: int) -> None:
        """Una pagina è stata trascinata nell'albero."""
        try:
            self._repo.move_page(page_id, parent_id, index)
        except DatabaseError as error:
            self._warn(error)
        self._reload_tree()

    def _delete(self, page_id: int) -> None:
        try:
            self._repo.delete_page(page_id)
        except DatabaseError as error:
            self._warn(error)
            return
        remaining = {node.id for node, _ in self._rows()}
        if self._page_id is None or self._page_id in remaining:
            self._reload_tree()
            self._reload_content()
            return
        self._timer.stop()                   # la pagina aperta è sparita: niente da salvare, si torna all'elenco
        self._pending.clear()
        self._page_id = None
        self._reload_tree()
        self._close_page()

    def _reload_content(self) -> None:
        """Dopo un'eliminazione la pagina aperta può aver perso dei collegamenti: se il testo è cambiato lo ricarica."""
        if self._page_id is not None:
            stored = self._repo.page(self._page_id).content
            if stored != self._editor.content():
                self._editor.set_content(stored, keep_view=True)
        self._refresh_links()
