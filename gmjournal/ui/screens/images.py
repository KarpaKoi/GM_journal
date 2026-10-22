"""Immagini: la libreria della campagna. Cartelle (esistono solo nel programma) e griglia delle immagini,
con a destra i dettagli dell'immagine scelta.

La schermata non tocca il database: legge e scrive solo tramite il `Repository`.
"""

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data import links, trees
from ...data.db import DatabaseError
from ...data.models import Image, ImageFolder, LinkTarget
from ...data.repository import IMAGES_DIRNAME, Repository
from ..image_files import choose_image_files
from ..popups.image_folder import create_image_folder, edit_image_folder
from ..popups.image_viewer import ImageViewer
from ..widgets.card_grid import CardGrid
from ..widgets.elided_label import ElidedLabel
from ..widgets.empty_state import EmptyState
from ..widgets.group_label import group_label
from ..widgets.icon_label import IconLabel
from ..widgets.image_details import ImageDetails
from ..widgets.image_tile import FolderCard, ImageTile, image_tile_height
from ..widgets.menu import PopupMenu
from .base import Screen
from .elements import link_destination

_COLOR = theme.SECTION_COLORS["immagini"]
_TILE_RATIO = 0.84
_LIST_VIEW, _EMPTY_VIEW = 0, 1
_MAIN = "Immagini"
_CRUMB_MIN, _CRUMB_KEEP, _CRUMB_HERE_MIN = 32, 60, 120   # un tratto del percorso non scende sotto _CRUMB_MIN px (sotto _CRUMB_HERE_MIN
                                                          # quello aperto), e un nome già più corto di _CRUMB_KEEP px non si accorcia


@dataclass(frozen=True)
class ImageTarget:
    """Dove si trova la schermata: la cartella aperta (None = la principale) e l'immagine scelta. Serve alla cronologia."""
    folder_id: int | None = None
    image_id: int | None = None


class _Crumb(ElidedLabel):
    """Un tratto del percorso delle cartelle. Se manca posto si accorcia con «…» (quello della cartella aperta per ultimo);
    gli altri si cliccano per tornare a quella cartella."""
    clicked = Signal()

    def __init__(self, name: str, here: bool):
        super().__init__(name, theme.TEXT_ACTIVE if here else theme.MUTED, theme.ui_font(13, 500 if here else 400))
        self._here = here
        self.setToolTip(name)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if not here:
            self.setCursor(Qt.PointingHandCursor)

    def minimumSizeHint(self) -> QSize:
        natural = self.sizeHint().width()
        least = _CRUMB_HERE_MIN if self._here else natural if natural <= _CRUMB_KEEP else _CRUMB_MIN
        return QSize(min(natural, least), self.height())

    def enterEvent(self, event) -> None:
        if not self._here:
            self.setColor(theme.TEXT)

    def leaveEvent(self, event) -> None:
        if not self._here:
            self.setColor(theme.MUTED)

    def mouseReleaseEvent(self, event) -> None:
        if not self._here and event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()


class ImagesScreen(Screen):
    def __init__(self, repo: Repository):
        super().__init__()
        self._repo = repo
        self._images: list[Image] = []
        self._folders: list[ImageFolder] = []
        self._folder_id: int | None = None         # cartella aperta (None = la principale)
        self._selected: int | None = None          # ID dell'immagine scelta
        self._tiles: dict[int, ImageTile] = {}

        title = QLabel(_MAIN)
        title.setFont(theme.serif_font(36, 500, -0.01))
        self._crumbs = QHBoxLayout()
        self._crumbs.setContentsMargins(0, 0, 0, 0)
        self._crumbs.setSpacing(6)
        open_folder = QPushButton(" Apri in Esplora file")
        open_folder.setIcon(icons.icon("external-link"))
        open_folder.setIconSize(QSize(17, 17))
        open_folder.setFixedHeight(38)
        open_folder.setCursor(Qt.PointingHandCursor)
        open_folder.setToolTip("Apre la cartella «immagini» della campagna, dove stanno tutti i file")
        open_folder.clicked.connect(self._open_system_folder)
        new_folder = QPushButton(" Nuova cartella")
        new_folder.setIcon(icons.icon("folder-plus"))
        new_folder.setIconSize(QSize(17, 17))
        new_folder.setFixedHeight(38)
        new_folder.setCursor(Qt.PointingHandCursor)
        new_folder.clicked.connect(self._new_folder)
        import_button = QPushButton(" Importa immagini")
        import_button.setIcon(icons.icon("upload", theme.BG))
        import_button.setIconSize(QSize(17, 17))
        import_button.setFixedHeight(38)
        import_button.setStyleSheet(theme.solid_button_style(_COLOR))
        import_button.setCursor(Qt.PointingHandCursor)
        import_button.clicked.connect(self._import)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(open_folder, alignment=Qt.AlignTop)
        header.addWidget(new_folder, alignment=Qt.AlignTop)
        header.addWidget(import_button, alignment=Qt.AlignTop)

        self._folders_title = group_label("Cartelle")
        self._folder_grid = CardGrid(max_columns=4, min_card_width=200, h_gap=12, v_gap=12, card_height=lambda _width: 56)
        self._images_title = group_label("Immagini")
        self._image_grid = CardGrid(max_columns=8, min_card_width=130, h_gap=16, v_gap=18,
                                    card_height=lambda width: image_tile_height(width, _TILE_RATIO))
        self._no_images = QLabel("Nessuna immagine in questa cartella.")
        self._no_images.setObjectName("Muted")
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 20)
        column.setSpacing(8)
        column.setAlignment(Qt.AlignTop)
        for widget in (self._folders_title, self._folder_grid):
            column.addWidget(widget)
        column.addSpacing(20)
        for widget in (self._images_title, self._no_images, self._image_grid):
            column.addWidget(widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        listing = QWidget()
        layout = QVBoxLayout(listing)
        layout.setContentsMargins(32, 28, 32, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addSpacing(8)
        layout.addLayout(self._crumbs)          # sotto il titolo, ma largo quanto la schermata: i nomi lunghi non devono contendersi il posto con i pulsanti
        layout.addSpacing(26)
        layout.addWidget(scroll, 1)

        empty = EmptyState("image", _COLOR, "Nessuna immagine", "Importa le immagini della tua campagna: ritratti, ambientazioni, mappe.",
                           "Importa immagini")
        empty.clicked.connect(self._import)
        self._views = QStackedWidget()
        self._views.addWidget(listing)      # _LIST_VIEW
        self._views.addWidget(empty)        # _EMPTY_VIEW
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._views)

        self._details = ImageDetails("Scegli un’immagine per vederne i dettagli.")
        self._details.label_edited.connect(self._rename)
        self._details.enlarge_requested.connect(self._enlarge)
        self._details.move_requested.connect(self._show_move_menu)
        self._details.use_chosen.connect(self._open_use)
        self._details.delete_confirmed.connect(self._delete)
        self.reload()

    def create_side_panel(self) -> QWidget:
        return self._details

    # --- Posizione e cronologia --------------------------------------------------------------
    def current_target(self) -> ImageTarget:
        return ImageTarget(self._folder_id, self._selected)

    def show_target(self, target: object) -> None:
        """Mostra una cartella e un'immagine scelta (`ImageTarget`); con `None` la cartella principale, senza scelta."""
        target = target or ImageTarget()
        self._folder_id, self._selected = target.folder_id, target.image_id
        self.reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            self._repo.sync_images()       # un file può essere stato copiato a mano nella cartella immagini
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self.reload()

    # --- Contenuto ---------------------------------------------------------------------------
    def reload(self) -> None:
        """Rilegge dati e ridisegna percorso, cartelle, immagini e pannello."""
        self._images = self._repo.images()
        self._folders = self._repo.image_folders()
        if self._folder_id is not None and self._folder_id not in {folder.id for folder in self._folders}:
            self._folder_id = None
        shown = self._shown()
        if self._selected not in {image.id for image in shown}:
            self._selected = None
        self._views.setCurrentIndex(_LIST_VIEW if self._images or self._folders else _EMPTY_VIEW)
        self._build_crumbs()
        self._build_folders()
        self._no_images.setVisible(not shown)
        self._build_tiles(shown)
        self._refresh_details()

    def _shown(self) -> list[Image]:
        return [image for image in self._images if image.folder_id == self._folder_id]

    def _build_crumbs(self) -> None:
        while self._crumbs.count():
            item = self._crumbs.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._crumbs.addWidget(IconLabel("folder", theme.MUTED, 15))
        path = trees.chain(self._folders, self._folder_id)
        stops: list[tuple[str, int | None]] = [(_MAIN, None)] + [(folder.name, folder.id) for folder in path]
        for index, (name, folder_id) in enumerate(stops):
            if index:
                self._crumbs.addWidget(IconLabel("chevron-right", theme.MUTED, 12))
            crumb = _Crumb(name, here=index == len(stops) - 1)
            crumb.clicked.connect(lambda folder_id=folder_id: self._open_folder(folder_id))
            self._crumbs.addWidget(crumb)
        self._crumbs.addStretch()

    def _build_folders(self) -> None:
        inside = [folder for folder in self._folders if folder.parent_id == self._folder_id]
        self._folders_title.setVisible(bool(inside))
        self._folder_grid.setVisible(bool(inside))
        cards = []
        for folder in inside:
            count = sum(1 for image in self._images if image.folder_id in trees.subtree(self._folders, folder.id))
            card = FolderCard(folder.name, count)
            card.clicked.connect(lambda folder_id=folder.id: self._open_folder(folder_id))
            card.edit_clicked.connect(lambda _=False, folder=folder: self._edit_folder(folder))
            cards.append(card)
        self._folder_grid.set_cards(cards)

    def _build_tiles(self, shown: list[Image]) -> None:
        self._tiles.clear()
        tiles = []
        for image in shown:
            tile = ImageTile(_TILE_RATIO)
            tile.set_image(image.label, self._repo.media_file(image.path))
            tile.set_selected(image.id == self._selected)
            tile.clicked.connect(lambda image_id=image.id: self._select(image_id))
            tile.double_clicked.connect(self._enlarge)
            tiles.append(tile)
            self._tiles[image.id] = tile
        self._image_grid.set_cards(tiles)
        self._image_grid.setVisible(bool(tiles))

    def _selected_image(self) -> Image | None:
        return next((image for image in self._images if image.id == self._selected), None)

    def _refresh_details(self) -> None:
        image = self._selected_image()
        if image is None:
            self._details.show_image(None, self._repo.folder, "", [])
            return
        path = " / ".join([_MAIN, *(folder.name for folder in trees.chain(self._folders, image.folder_id))])
        self._details.show_image(image, self._repo.media_file(image.path), path, self._repo.image_uses(image.path))

    # --- Scelte dell'utente -----------------------------------------------------------------------
    def _open_folder(self, folder_id: int | None) -> None:
        self._folder_id, self._selected = folder_id, None
        self.reload()
        self.navigated.emit(self.current_target())

    def _select(self, image_id: int) -> None:
        """L'utente ha scelto una tessera: va nella cronologia."""
        if image_id == self._selected:
            return
        self._selected = image_id
        for tile_id, tile in self._tiles.items():
            tile.set_selected(tile_id == image_id)
        self._refresh_details()
        self.navigated.emit(self.current_target())
        self.panel_requested.emit()

    def _new_folder(self) -> None:
        if create_image_folder(self, self._repo, self._folder_id) is not None:
            self.reload()

    def _edit_folder(self, folder: ImageFolder) -> None:
        edit_image_folder(self, self._repo, folder)
        self.reload()

    def _import(self) -> None:
        """Copia nella libreria (nella cartella aperta) le immagini scelte dal computer e sceglie la prima."""
        failed, first = [], None
        for path in choose_image_files(self, multiple=True):
            try:
                imported = self._repo.import_image(path, self._folder_id)
            except (OSError, DatabaseError):
                failed.append(path.name)
                continue
            first = first or imported
        if failed:
            QMessageBox.warning(self, "GM Journal", "Non riesco a copiare nella campagna: " + ", ".join(f"«{name}»" for name in failed) + ".")
        if first is not None:
            self._images = self._repo.images()
            self._selected = next((image.id for image in self._images if image.path == first and image.folder_id == self._folder_id), None)
            self.reload()
            self.navigated.emit(self.current_target())

    # --- Pannello dei dettagli -----------------------------------------------------------------------
    def _guarded(self, action) -> None:
        try:
            action()
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self.reload()

    def _rename(self, label: str) -> None:
        self._guarded(lambda: self._repo.rename_image(self._selected, label))

    def _show_move_menu(self, anchor: QWidget) -> None:
        image = self._selected_image()
        menu = PopupMenu(self, width=260)
        for folder_id, name in [(None, _MAIN), *trees.named_paths(self._folders)]:
            menu.add_item("folder", name, lambda folder_id=folder_id: self._move(folder_id), checked=folder_id == image.folder_id)
        menu.popup_below(anchor)

    def _move(self, folder_id: int | None) -> None:
        """Sposta l'immagine e apre la cartella dove è finita, così resta sotto gli occhi."""
        try:
            self._repo.move_image(self._selected, folder_id)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self._folder_id = folder_id
        self.reload()
        self.navigated.emit(self.current_target())

    def _enlarge(self) -> None:
        image = self._selected_image()
        if image is not None:
            ImageViewer(self, image.label, self._repo.media_file(image.path)).exec()

    def _open_system_folder(self) -> None:
        folder = self._repo.folder / IMAGES_DIRNAME
        folder.mkdir(exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            QMessageBox.warning(self, "GM Journal", f"Non riesco ad aprire la cartella:\n{folder}")

    def _open_use(self, target: LinkTarget) -> None:
        if target.kind != links.CAMPAIGN:         # la copertina della campagna non ha una pagina in cui andare
            self.open_requested.emit(*link_destination(target.kind, target.id))

    def _delete(self) -> None:
        self._guarded(lambda: self._repo.delete_image(self._selected))
