"""La finestrella che compare passando il mouse su un collegamento del testo: chi è, due righe su di lui e quante volte è citato.
Non si clicca: il mouse ci passa attraverso. Si apre con Ctrl+clic sul collegamento."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ... import icons, theme
from ...thumbnails import Thumb
from .element_thumb import paint_thumb
from .elided_label import ElidedLabel

WIDTH = 344
_TILE = 46
_BRIEF_LINES = 3
_WRAP = Qt.TextWordWrap | Qt.TextWrapAnywhere      # come va a capo un QLabel: alle parole e, se una parola non sta, anche dentro


@dataclass(frozen=True)
class LinkPreviewData:
    """Ciò che la finestrella mostra. Un elemento ha iniziali (o immagine), categoria, ruolo e `cited` (in quante pagine compare);
    una pagina, una mappa o un grafo hanno un'`icon` e non hanno categoria né conteggio (`cited` None)."""
    name: str
    color: str
    hint: str                      # «Ctrl+clic per aprire la scheda»
    subtitle: str = ""             # elemento: il ruolo; altrimenti cos'è («Pagina 1.2»)
    brief: str = ""
    icon: str = ""
    initials: str = ""
    image: Path | None = None
    chip: str = ""                 # la categoria (solo elementi)
    cited: int | None = None


def clamp_lines(text: str, font, width: int, lines: int) -> str:
    """`text` accorciato con «…» perché occupi al massimo `lines` righe larghe `width`."""
    metrics = QFontMetrics(font)
    limit = metrics.boundingRect(QRect(0, 0, width, 100000), _WRAP, "\n".join("x" * lines)).height()    # l'altezza di `lines` righe

    def fits(candidate: str) -> bool:
        return metrics.boundingRect(QRect(0, 0, width, 100000), _WRAP, candidate).height() <= limit

    if fits(text):
        return text
    words = text.split()
    low, high = 0, len(words)
    while low < high:                      # più parole che stanno ancora, con i puntini in fondo
        middle = (low + high + 1) // 2
        if fits(" ".join(words[:middle]) + "…"):
            low = middle
        else:
            high = middle - 1
    return " ".join(words[:low]) + "…"


class _Tile(QWidget):
    """Il riquadro a sinistra del nome: l'immagine o le iniziali di un elemento, l'icona del tipo per il resto."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(_TILE, _TILE)
        self._data: LinkPreviewData | None = None
        self._thumb = Thumb()

    def set_data(self, data: LinkPreviewData) -> None:
        self._data = data
        self._thumb.set_file(data.image)
        self.update()

    def paintEvent(self, event) -> None:
        if self._data is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        data = self._data
        if data.icon:
            outline = QPainterPath()
            outline.addRoundedRect(self.rect(), 10, 10)
            painter.fillPath(outline, theme.tint(data.color, 0.16))
            icons.icon(data.icon, data.color).paint(painter, QRect((_TILE - 22) // 2, (_TILE - 22) // 2, 22, 22))
        else:
            paint_thumb(painter, self.rect(), 10, data.initials, data.color, self._thumb.pixmap(_TILE, _TILE, self.devicePixelRatioF()))


class LinkPreviewCard(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("LinkPreview")
        self.setFixedWidth(WIDTH)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 128))
        self.setGraphicsEffect(shadow)

        self._tile = _Tile()
        self._name = ElidedLabel(color=theme.TEXT_ACTIVE, font=theme.ui_font(15, 600))
        self._chip = QLabel()
        self._chip.setFixedHeight(20)
        self._subtitle = ElidedLabel(color=theme.MUTED, font=theme.ui_font(12))
        under = QHBoxLayout()
        under.setSpacing(8)
        under.addWidget(self._chip)
        under.addWidget(self._subtitle, 1)
        self._under = QWidget()
        self._under.setLayout(under)
        under.setContentsMargins(0, 0, 0, 0)
        names = QVBoxLayout()
        names.setSpacing(3)
        names.setAlignment(Qt.AlignVCenter)
        names.addWidget(self._name)
        names.addWidget(self._under)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._tile)
        top.addLayout(names, 1)

        self._brief = QLabel()
        self._brief.setWordWrap(True)
        self._brief.setFont(theme.ui_font(13))
        self._brief.setStyleSheet(f"color: {theme.TEXT_SOFT};")
        self._brief.setContentsMargins(0, 10, 0, 0)       # niente padding QSS: sposterebbe il testo di qualche pixel
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {theme.BORDER_STRONG};")
        self._cited = QLabel()
        self._hint = QLabel()
        for label in (self._cited, self._hint):
            label.setFont(theme.ui_font(11))
            label.setStyleSheet(f"color: {theme.MUTED};")
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(self._cited)
        footer.addStretch()
        footer.addWidget(self._hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(self._brief)
        layout.addSpacing(10)
        layout.addWidget(line)
        layout.addSpacing(9)
        layout.addLayout(footer)

    def show_data(self, data: LinkPreviewData) -> None:
        self._tile.set_data(data)
        self._name.setText(data.name)
        self._chip.setVisible(bool(data.chip))
        if data.chip:
            self._chip.setText(data.chip)
            self._chip.setStyleSheet(
                f"background: {theme.tint(data.color, 0.16).name(QColor.HexArgb)}; color: {data.color}; border-radius: 10px; "
                "padding: 0 8px; font-size: 12px; font-weight: 500;")
        self._subtitle.setText(data.subtitle)
        self._under.setVisible(bool(data.chip or data.subtitle))
        text_width = WIDTH - 32
        brief = clamp_lines(data.brief, self._brief.font(), text_width, _BRIEF_LINES) if data.brief else ""
        self._brief.setText(brief)
        self._brief.setVisible(bool(brief))
        self._cited.setText("" if data.cited is None else
                            "Non citato in nessuna pagina" if data.cited == 0 else
                            f"Citato in {data.cited} {'pagina' if data.cited == 1 else 'pagine'}")
        self._hint.setText(data.hint)
        self.layout().invalidate()
        height = self.layout().heightForWidth(WIDTH)
        self.setFixedHeight(height if height >= 0 else self.layout().sizeHint().height())     # -1: nessun testo a capo

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.BORDER_STRONG))
        painter.setBrush(QColor(theme.MENU_BG))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)
