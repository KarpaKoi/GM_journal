"""«Collega immagini» (scelta multipla) e «Scegli un'immagine» (singola): si sceglie fra le immagini della libreria."""

from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QWidget

from ... import icons, theme
from ...data import trees
from ...data.models import Image, ImageFolder
from ...data.repository import Repository
from ...data.search import fold
from ..image_files import choose_image_files
from ..widgets.card_grid import CardGrid
from ..widgets.filter_chip import FilterChip
from ..widgets.image_tile import ImageTile, image_tile_height
from ..widgets.strip import HorizontalStrip
from .base import PopupDialog, note

_RATIO = 0.76
_GRID_HEIGHT = 340


class ImagesPopup(PopupDialog):
    """`multiple`: si possono scegliere più immagini («Collega immagini»); altrimenti una sola.
    `linked` sono i file già collegati (si vedono attenuati e non si scelgono); `current` è la scelta di partenza (solo una);
    `verb` è ciò che si fa con le immagini scelte («Collega», «Inserisci»)."""

    def __init__(self, parent: QWidget, repo: Repository, multiple: bool, linked: frozenset[str] = frozenset(), current: str | None = None,
                 verb: str = "Collega"):
        super().__init__(
            parent,
            f"{verb} immagini" if multiple else "Scegli un’immagine",
            "Dalla cartella Immagini dell’app: puoi sceglierne più di una." if multiple else "Dalla cartella Immagini dell’app.",
            f"{verb} immagini" if multiple else "Usa questa immagine",
            width=880,
        )
        self._repo, self._multiple, self._linked, self._verb = repo, multiple, linked, verb
        self._images: list[Image] = []
        self._folders: list[ImageFolder] = []
        self._filter: int | None = None         # cartella scelta nei filtri (None = tutte)
        self._selected: list[str] = [current] if current else []
        self._tiles: dict[str, ImageTile] = {}

        self._search = QLineEdit()
        self._search.setPlaceholderText("Cerca per nome…")
        self._search.setFixedSize(220, 34)
        self._search.setStyleSheet("border-radius: 17px; padding: 0 12px 0 4px;")
        self._search.addAction(icons.icon("search", theme.MUTED), QLineEdit.LeadingPosition)
        self._chips = QHBoxLayout()
        self._chips.setContentsMargins(0, 2, 0, 2)
        self._chips.setSpacing(8)
        chip_row = QWidget()
        chip_row.setLayout(self._chips)
        strip = HorizontalStrip(chip_row)
        strip.setFixedHeight(40)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(self._search)
        filters.addWidget(strip, 1)

        self._grid = CardGrid(max_columns=5, min_card_width=140, h_gap=12, v_gap=14, card_height=lambda w: image_tile_height(w, _RATIO))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(self._grid)
        self._grid.setAutoFillBackground(False)      # dentro il popup la griglia resta del colore del popup
        self._empty = QLabel()
        self._empty.setObjectName("Muted")
        self._empty.setAlignment(Qt.AlignCenter)
        self._views = QStackedWidget()
        self._views.setFixedHeight(_GRID_HEIGHT)
        self._views.addWidget(scroll)
        self._views.addWidget(self._empty)

        self.body.setSpacing(14)
        self.body.addLayout(filters)
        self.body.addWidget(self._views)

        import_button = QPushButton(" Importa dal computer…")
        import_button.setIcon(icons.icon("upload"))
        import_button.setIconSize(QSize(16, 16))
        import_button.setFixedHeight(40)
        import_button.setAutoDefault(False)
        import_button.setCursor(Qt.PointingHandCursor)
        import_button.clicked.connect(self._import)
        hint = note("Si copia nella cartella Immagini dell’app.")
        hint.setFixedWidth(210)
        self.footer_left.setSpacing(12)
        self.footer_left.addWidget(import_button)
        self.footer_left.addWidget(hint)
        self._count = QLabel()
        self._count.setObjectName("Muted")
        self.footer_right.addWidget(self._count)

        self._search.textChanged.connect(self._rebuild_tiles)
        self._reload()
        self._search.setFocus()

    def paths(self) -> list[str]:
        """I file scelti, nell'ordine in cui sono stati scelti."""
        return list(self._selected)

    # --- Contenuto ---------------------------------------------------------------------------
    def _reload(self) -> None:
        self._images = self._repo.images()
        self._folders = self._repo.image_folders()
        if self._filter not in {folder.id for folder in self._folders}:
            self._filter = None
        self._build_chips()
        self._rebuild_tiles()

    def _build_chips(self) -> None:
        while self._chips.count():
            item = self._chips.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        top = [folder for folder in self._folders if folder.parent_id is None]
        options = [(None, "Tutte", theme.TEXT, len(self._images))] + [
            (folder.id, folder.name, theme.SECTION_COLORS["immagini"], len(self._in_folder(folder.id))) for folder in top]
        for folder_id, label, color, count in options:
            chip = FilterChip(label, color, count)
            chip.setChecked(folder_id == self._filter)
            chip.clicked.connect(lambda _=False, folder_id=folder_id: self._set_filter(folder_id))
            self._chips.addWidget(chip)
        self._chips.addStretch()

    def _in_folder(self, folder_id: int) -> list[Image]:
        inside = trees.subtree(self._folders, folder_id)
        return [image for image in self._images if image.folder_id in inside]

    def _set_filter(self, folder_id: int | None) -> None:
        self._filter = folder_id
        self._build_chips()
        self._rebuild_tiles()

    def _rebuild_tiles(self) -> None:
        shown = self._images if self._filter is None else self._in_folder(self._filter)
        query = fold(self._search.text().strip())
        shown = [image for image in shown if query in fold(image.label)]
        self._tiles.clear()
        tiles = []
        for image in shown:
            tile = ImageTile(_RATIO, check=True, quiet=True)
            tile.set_image(image.label, self._repo.media_file(image.path))
            tile.set_selected(image.path in self._selected)
            if image.path in self._linked:
                tile.set_badge("Già collegata")
                tile.set_dimmed(True)
            else:
                tile.clicked.connect(lambda path=image.path: self._toggle(path))
                tile.double_clicked.connect(lambda path=image.path: self._choose_now(path))
            tiles.append(tile)
            self._tiles[image.path] = tile
        self._grid.set_cards(tiles)
        self._empty.setText("Nessuna immagine corrisponde alla ricerca." if self._images else
                            "La libreria è vuota. Importa le immagini dal computer.")
        self._views.setCurrentIndex(0 if shown else 1)
        self._update_footer()

    def _toggle(self, path: str) -> None:
        if path in self._selected:
            self._selected.remove(path)
        elif self._multiple:
            self._selected.append(path)
        else:
            self._selected = [path]
        for tile_path, tile in self._tiles.items():
            tile.set_selected(tile_path in self._selected)
        self._update_footer()

    def _choose_now(self, path: str) -> None:
        """Doppio clic: nella scelta singola equivale a scegliere e confermare."""
        if not self._multiple:
            self._selected = [path]
            self.accept()

    def _update_footer(self) -> None:
        count = len(self._selected)
        if self._multiple:
            self._count.setText(f"{count} selezionat{'a' if count == 1 else 'e'}" if count else "Nessuna selezionata")
            self.set_primary_text(f"{self._verb} {count} immagin{'e' if count == 1 else 'i'}" if count else f"{self._verb} immagini")
        else:
            self._count.setText("1 selezionata" if count else "Nessuna selezionata")
        self.set_primary_enabled(bool(count))

    def _import(self) -> None:
        """Copia nella libreria (nella cartella scelta nel filtro, se c'è) le immagini scelte dal computer e le seleziona."""
        paths = choose_image_files(self, multiple=self._multiple)
        failed = []
        for path in paths:
            try:
                imported = self._repo.import_image(path, self._filter)
            except OSError:
                failed.append(path.name)
                continue
            if self._multiple or imported not in self._selected:
                self._selected = [*self._selected, imported] if self._multiple else [imported]
        if failed:
            QMessageBox.warning(self, "GM Journal", "Non riesco a copiare nella campagna: " + ", ".join(f"«{name}»" for name in failed) + ".")
        self._reload()


def choose_images(parent: QWidget, repo: Repository, linked: frozenset[str] = frozenset(), verb: str = "Collega") -> list[str]:
    """«Collega immagini» (o «Inserisci…»): i file scelti (vuoto se si annulla). Quelli in `linked` non si possono scegliere."""
    popup = ImagesPopup(parent, repo, multiple=True, linked=linked, verb=verb)
    return popup.paths() if popup.exec() else []


def text_image_picker(repo: Repository) -> Callable[[QWidget], list[str]]:
    """Ciò che l'editor di testo apre per inserire immagini: la libreria della campagna."""
    return lambda parent: choose_images(parent, repo, verb="Inserisci")


def choose_image(parent: QWidget, repo: Repository, current: str | None = None) -> str | None:
    """«Scegli un'immagine»: il file scelto (None se si annulla)."""
    popup = ImagesPopup(parent, repo, multiple=False, current=current)
    return popup.paths()[0] if popup.exec() and popup.paths() else None
