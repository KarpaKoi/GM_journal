"""La scheda interna «Immagini»: le immagini della libreria collegate all'elemento; la prima è il ritratto (o la copertina)."""

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.db import DatabaseError
from ...data.models import Image
from ...data.repository import Repository
from ...elements import ElementKind
from ..popups.image_viewer import ImageViewer
from ..popups.images import choose_images
from ..widgets.card_grid import CardGrid
from ..widgets.image_tile import ImageTile, image_tile_height
from ..widgets.menu import PopupMenu

_RATIO = 0.9


class ImagesPage(QWidget):
    changed = Signal()      # le immagini collegate sono cambiate (può essere cambiato il ritratto: l'intestazione va riletta)

    def __init__(self, repo: Repository, kind: ElementKind, element_id: int):
        super().__init__()
        self._repo, self._kind, self._element_id = repo, kind, element_id
        self._images: list[Image] = []

        self._count = QLabel()
        self._count.setObjectName("Muted")
        add = QPushButton(" Collega immagini")
        add.setIcon(icons.icon("link", theme.BG))
        add.setIconSize(QSize(16, 16))
        add.setFixedHeight(36)
        add.setStyleSheet(theme.solid_button_style(kind.color))
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(self._link)
        header = QHBoxLayout()
        header.addWidget(self._count)
        header.addStretch()
        header.addWidget(add)

        self._grid = CardGrid(max_columns=6, min_card_width=150, h_gap=16, v_gap=16, card_height=lambda w: image_tile_height(w, _RATIO))
        self._empty = QLabel(f"Nessuna immagine collegata. La prima che colleghi sarà usata come {kind.portrait.lower()}.")
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 20)
        column.setAlignment(Qt.AlignTop)
        column.addWidget(self._empty)
        column.addWidget(self._grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(scroll, 1)
        self.reload()

    def reload(self) -> None:
        self._images = self._repo.element_images(self._element_id)
        count = len(self._images)
        self._count.setText(f"Immagini collegate dalla libreria · {count}")
        self._empty.setVisible(not count)
        self._grid.setVisible(bool(count))
        tiles = []
        for index, image in enumerate(self._images):
            tile = ImageTile(_RATIO, quiet=True)
            tile.set_image(image.label, self._repo.media_file(image.path))
            tile.set_badge(self._kind.portrait if index == 0 else "")
            tile.clicked.connect(lambda tile=tile, image=image, index=index: self._show_menu(tile, image, index))
            tiles.append(tile)
        self._grid.set_cards(tiles)

    def _show_menu(self, tile: ImageTile, image: Image, index: int) -> None:
        menu = PopupMenu(self, width=240)
        menu.add_item("external-link", "Apri anteprima grande", lambda: ImageViewer(self, image.label, self._repo.media_file(image.path)).exec())
        if index:
            menu.add_item("image", f"Usa come {self._kind.portrait.lower()}", lambda: self._write(self._repo.set_element_cover, image.path))
        menu.add_item("unlink", "Scollega dalla scheda", lambda: self._write(self._repo.unlink_element_image, image.path))
        menu.popup_at(tile.mapToGlobal(QPoint(12, tile.height() - 30)), align="left")

    def _link(self) -> None:
        paths = choose_images(self, self._repo, frozenset(image.path for image in self._images))
        if paths:
            self._write(self._repo.link_element_images, paths)

    def _write(self, action, argument) -> None:
        try:
            action(self._element_id, argument)
        except DatabaseError as error:
            QMessageBox.warning(self, "GM Journal", str(error))
        self.reload()
        self.changed.emit()
