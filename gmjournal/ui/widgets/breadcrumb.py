"""Il percorso della barra in alto («Campagna › Sezione › Pagina»): ogni tratto è un pulsante, tranne l'ultimo, che dice dove si è."""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QWidget

from ... import theme
from .icon_label import IconLabel

_PAD = 6                # spazio ai due lati del testo
_MAX_WIDTH = 260        # un tratto con un nome lunghissimo non occupa più di così
_MIN_WIDTH = 90         # se non c'è posto per tutti, un tratto si accorcia solo oltre questa misura: i nomi brevi restano interi


class _Crumb(QAbstractButton):
    def __init__(self, text: str, clickable: bool, current: bool):
        super().__init__()
        self._current = current
        self.setText(text)
        self.setToolTip(text)
        self.setEnabled(clickable)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setFixedHeight(28)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)

    def _font(self):
        font = theme.ui_font(14, 600 if self._current else 400)
        font.setUnderline(self.isEnabled() and self.underMouse())
        return font

    def _text_width(self) -> int:
        return QFontMetrics(self._font()).horizontalAdvance(self.text()) + 2 * _PAD + 2

    def sizeHint(self) -> QSize:
        return QSize(min(self._text_width(), _MAX_WIDTH), 28)

    def minimumSizeHint(self) -> QSize:
        return QSize(min(self._text_width(), _MIN_WIDTH), 28)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        font = self._font()
        painter.setFont(font)
        color = theme.TEXT_ACTIVE if self._current or self.underMouse() else theme.MUTED
        painter.setPen(QColor(color))
        text = QFontMetrics(font).elidedText(self.text(), Qt.ElideRight, self.width() - 2 * _PAD)
        painter.drawText(QRect(_PAD, 0, self.width() - 2 * _PAD, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)


class Breadcrumb(QWidget):
    clicked = Signal(int)       # la posizione del tratto premuto (0 = il primo)

    def __init__(self):
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setMinimumWidth(0)           # con nomi molto lunghi i tratti si accorciano invece di allargare la finestra

    def set_crumbs(self, crumbs: list[tuple[str, bool]]) -> None:
        """I tratti, ognuno con il testo e se si può premere. L'ultimo è il posto attuale e non si preme mai."""
        while self._layout.count():
            widget = self._layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        for index, (text, clickable) in enumerate(crumbs):
            last = index == len(crumbs) - 1
            if index:
                self._layout.addWidget(IconLabel("chevron-right", theme.MUTED, 14))
            crumb = _Crumb(text, clickable and not last, last)
            crumb.clicked.connect(lambda _=False, index=index: self.clicked.emit(index))
            self._layout.addWidget(crumb)
        self._layout.addStretch(1)          # i tratti restano a sinistra, grandi quanto il loro testo
