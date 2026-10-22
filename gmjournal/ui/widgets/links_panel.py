"""Pannello «Collegamenti»: cosa cita la pagina aperta e da chi è citata. Un clic su una riga apre l'elemento."""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import LinkTarget
from ..kinds import kind_icon
from .group_label import group_label

_ROW_HEIGHT = 54


class _Row(QAbstractButton):
    def __init__(self, target: LinkTarget):
        super().__init__()
        self._target = target
        self.setFixedHeight(_ROW_HEIGHT)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def sizeHint(self) -> QSize:
        return QSize(100, _ROW_HEIGHT)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER_SOFT))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        icons.icon(kind_icon(self._target.kind), theme.TEXT_SOFT).paint(painter, QRect(12, (_ROW_HEIGHT - 16) // 2, 16, 16))
        room = self.width() - 44 - 12
        for font, color, text, top in ((theme.ui_font(14, 500), theme.TEXT_ACTIVE, self._target.name, 8),
                                       (theme.ui_font(12), theme.MUTED, self._target.detail, 28)):
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(QRect(44, top, room, 20), Qt.AlignVCenter | Qt.AlignLeft,
                             QFontMetrics(font).elidedText(text, Qt.ElideRight, room))


class LinkSection(QWidget):
    """Un titoletto con l'elenco di ciò che c'è (righe cliccabili) o, se è vuoto, una frase che lo spiega."""

    def __init__(self, heading: str, empty_text: str, on_chosen):
        super().__init__()
        self._heading = heading
        self._on_chosen = on_chosen
        self._title = group_label()
        self._rows = QVBoxLayout()
        self._rows.setSpacing(2)
        self._empty = QLabel(empty_text)
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._title)
        layout.addLayout(self._rows)
        layout.addWidget(self._empty)

    def set_targets(self, targets: list[LinkTarget]) -> None:
        while self._rows.count():
            self._rows.takeAt(0).widget().deleteLater()
        for target in targets:
            row = _Row(target)
            row.clicked.connect(lambda _=False, target=target: self._on_chosen(target))
            self._rows.addWidget(row)
        self._title.setText(f"{self._heading.upper()}  ·  {len(targets)}" if targets else self._heading.upper())
        self._empty.setVisible(not targets)


class LinksPanel(QFrame):
    chosen = Signal(object)    # LinkTarget da aprire

    def __init__(self):
        super().__init__()
        title = QLabel("Collegamenti")
        title.setFont(theme.serif_font(24, 500))
        self._cited = LinkSection("Citati in questa pagina", "Nessun collegamento. Scrivi @ nel testo per collegare una pagina.", self.chosen.emit)
        self._citing = LinkSection("Citata da", "Nessun'altra pagina cita questa.", self.chosen.emit)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(24)
        layout.addWidget(title)
        layout.addWidget(self._cited)
        layout.addWidget(self._citing)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        content.setAutoFillBackground(False)     # la scheda sotto è già del colore del pannello
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def set_links(self, cited: list[LinkTarget], citing: list[LinkTarget]) -> None:
        self._cited.set_targets(cited)
        self._citing.set_targets(citing)
