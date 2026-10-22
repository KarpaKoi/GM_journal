"""Il pannello destro della schermata Immagini: anteprima, nome mostrato, cartella, dove è usata ed eliminazione."""

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import Image, LinkTarget
from ...data.repository import NAME_MAX
from ...thumbnails import Thumb
from .group_label import group_label
from .hold_button import HoldButton
from .links_panel import LinkSection

_COLOR = theme.SECTION_COLORS["immagini"]
_PREVIEW_HEIGHT = 200


class _PreviewBox(QWidget):
    """L'immagine intera in un riquadro arrotondato; se il file manca, un'icona."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(_PREVIEW_HEIGHT)
        self._thumb = Thumb(crop=False)

    def set_file(self, file: Path | None) -> None:
        self._thumb.set_file(file)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(self.rect()), 12, 12)
        painter.setClipPath(outline)
        painter.fillRect(self.rect(), theme.tint(_COLOR))
        pixmap = self._thumb.pixmap(self.width(), self.height(), self.devicePixelRatioF())
        if pixmap is not None:
            size = pixmap.deviceIndependentSize().toSize()
            painter.drawPixmap((self.width() - size.width()) // 2, (self.height() - size.height()) // 2, pixmap)
        else:
            icons.icon("image", _COLOR).paint(painter, QRect((self.width() - 56) // 2, (self.height() - 56) // 2, 56, 56))


class ImageDetails(QScrollArea):
    label_edited = Signal(str)
    enlarge_requested = Signal()
    move_requested = Signal(object)     # il pulsante «Sposta in…», sotto cui comparirà il menu
    use_chosen = Signal(object)         # LinkTarget della pagina o scheda scelta in «Usata in»
    delete_confirmed = Signal()

    def __init__(self, hint: str):
        super().__init__()
        self._saved_label = ""
        self._hint = QLabel(hint)
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)

        self._preview = _PreviewBox()
        enlarge = self._button("Apri anteprima grande", "external-link")
        enlarge.clicked.connect(self.enlarge_requested)
        self._label = QLineEdit()
        self._label.setFixedHeight(36)
        self._label.setMaxLength(NAME_MAX)
        self._label.editingFinished.connect(self._finish_label)
        self._folder = QLabel()
        self._folder.setWordWrap(True)
        self._folder.setStyleSheet(f"color: {theme.TEXT_SOFT};")
        move = self._button("Sposta in…", "folder")
        move.clicked.connect(lambda: self.move_requested.emit(move))
        self._used = LinkSection("Usata in", "Non è usata da nessuna parte.", self.use_chosen.emit)
        self._delete = HoldButton("Tieni premuto per eliminare l’immagine")
        self._delete.confirmed.connect(self.delete_confirmed)

        self._details = QWidget()
        layout = QVBoxLayout(self._details)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._preview)
        layout.addSpacing(12)
        layout.addWidget(enlarge)
        layout.addSpacing(20)
        layout.addWidget(group_label("Etichetta"))
        layout.addSpacing(6)
        layout.addWidget(self._label)
        layout.addSpacing(18)
        layout.addWidget(group_label("Cartella"))
        layout.addSpacing(6)
        layout.addWidget(self._folder)
        layout.addSpacing(8)
        layout.addWidget(move)
        layout.addSpacing(22)
        layout.addWidget(self._used)
        layout.addSpacing(22)
        layout.addWidget(self._delete)

        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addWidget(self._hint)
        outer.addWidget(self._details)
        outer.addStretch(1)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)
        content.setAutoFillBackground(False)
        self.show_image(None, Path(), "", [])

    @staticmethod
    def _button(text: str, icon_name: str) -> QPushButton:
        button = QPushButton(" " + text)
        button.setIcon(icons.icon(icon_name))
        button.setIconSize(QSize(16, 16))
        button.setFixedHeight(36)
        button.setCursor(Qt.PointingHandCursor)
        return button

    def show_image(self, image: Image | None, file: Path | None, folder_path: str, uses: list[LinkTarget]) -> None:
        """Mostra l'immagine scelta (con il percorso della sua cartella e dove è usata); `None` = nessuna scelta."""
        self._hint.setVisible(image is None)
        self._details.setVisible(image is not None)
        if image is None:
            return
        self._saved_label = image.label
        self._preview.set_file(file)
        self._label.setText(image.label)
        self._folder.setText(folder_path)
        self._used.set_targets(uses)

    def _finish_label(self) -> None:
        """Il nome mostrato non può restare vuoto: se lo si svuota torna quello salvato."""
        text = self._label.text().strip()
        if not text:
            self._label.setText(self._saved_label)
        elif text != self._saved_label:
            self._saved_label = text
            self.label_edited.emit(text)
