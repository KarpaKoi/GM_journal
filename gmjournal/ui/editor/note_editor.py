"""Un riquadro di testo libero dentro una scheda (Storia, Appunti liberi): la barra di formattazione e l'editor."""

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from ... import theme
from ...spelling import Speller
from . import commands
from .editor import COMPACT_FRAME, CreateTarget, LinkSource, RichEditor
from .preview_ui import PreviewSource
from .toolbar import FormatToolbar

_RADIUS = 12


class _Outline(QWidget):
    """Il bordo arrotondato, disegnato sopra il contenuto (che altrimenti ne coprirebbe gli angoli)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS, _RADIUS)


class NoteEditor(QFrame):
    """`body_height` è l'altezza del testo (senza barra); senza, il riquadro si allunga quanto può."""

    edited = Signal()
    focus_lost = Signal()
    link_activated = Signal(str, int)     # Ctrl+clic su un collegamento: (tipo, ID)

    def __init__(self, link_targets: LinkSource, create_target: CreateTarget, import_image: Callable[[Path], str],
                 pick_images: Callable[[QWidget], list[str]], media_dir: Path, speller: Speller, body_height: int | None = None,
                 link_preview: PreviewSource | None = None):
        super().__init__()
        self.setObjectName("NoteEditor")
        self._editor = RichEditor(link_targets, create_target, import_image, media_dir, frame=COMPACT_FRAME, pick_images=pick_images,
                                  speller=speller, link_preview=link_preview)
        self._editor.edited.connect(self.edited)
        self._editor.focus_lost.connect(self.focus_lost)
        self._editor.link_activated.connect(self.link_activated)
        toolbar = FormatToolbar(self._editor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(self._editor, 1)
        if body_height is not None:
            self._editor.setFixedHeight(body_height)
        self._outline = _Outline(self)

    def content(self) -> str:
        return self._editor.content()

    def set_content(self, content: str, keep_view: bool = False) -> None:
        self._editor.set_content(content, keep_view)

    def insert_title(self, text: str) -> None:
        """Aggiunge un titolo nel punto del cursore e si resta a scrivere sotto."""
        commands.insert_title(self._editor, text)
        self._editor.setFocus()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._outline.setGeometry(self.rect())
        self._outline.raise_()
