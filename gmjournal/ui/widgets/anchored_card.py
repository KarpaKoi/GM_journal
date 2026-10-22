"""Un riquadro con una freccetta che punta a un punto (il pin sulla mappa): la base delle finestrelle dei pin."""

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QScrollArea, QVBoxLayout, QWidget

from ... import theme

ARROW = 8           # altezza della freccetta (e margine attorno al riquadro che la contiene)
_RADIUS = 12
_GAP = 22           # distanza fra il centro del pin e la punta della freccetta
_EDGE = 8           # distanza minima dal bordo dell'area


class ScrollBody(QScrollArea):
    """La parte centrale di una finestrella (`scrolls=True`): alta quanto il suo contenuto, ma se alla finestrella manca posto si
    accorcia e il contenuto scorre, mentre intestazione e pulsanti restano visibili. `width` è la larghezza che il contenuto avrà."""

    _MIN_HEIGHT = 96

    def __init__(self, content: QWidget, width: int):
        super().__init__()
        self._width = width
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumHeight(self._MIN_HEIGHT)
        self.viewport().setAutoFillBackground(False)
        self.setWidget(content)
        content.setAutoFillBackground(False)        # `setWidget` lo riattiva: la finestrella ha il suo sfondo

    def sizeHint(self) -> QSize:
        layout = self.widget().layout()
        height = layout.totalHeightForWidth(self._width)
        return QSize(self._width, height if height >= 0 else layout.sizeHint().height())

    def eventFilter(self, watched, event) -> bool:
        if watched is self.widget() and event.type() == QEvent.LayoutRequest:      # il contenuto è cambiato: la finestrella si riadatta
            self.updateGeometry()
        return super().eventFilter(watched, event)


class AnchoredCard(QFrame):
    """Le sottoclassi mettono i loro widget in `self.column`. `place` lo posiziona accanto al punto indicato.
    L'altezza segue da sola il contenuto (anche il testo che va a capo); quando cambia, `resized` avvisa chi deve riposizionarlo.
    Con `scrolls=True` la finestrella non supera mai l'altezza dell'area: ci deve essere un `ScrollBody` che assorbe la differenza."""

    resized = Signal()

    def __init__(self, body_width: int, padding: int = 16, scrolls: bool = False):
        super().__init__()
        self._scrolls = scrolls
        self._room = 0              # altezza massima concessa dall'area, se `scrolls` (0 = ancora nessun limite)
        self.setFixedWidth(body_width + 2 * ARROW)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 16)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(ARROW + padding, ARROW + padding, ARROW + padding, ARROW + padding)
        self.column.setSpacing(0)
        self._side = "bottom"       # da che lato del riquadro esce la freccetta
        self._offset = 0            # dove, lungo quel lato (dal bordo sinistro o da quello alto del riquadro)

    def event(self, event) -> bool:
        handled = super().event(event)
        if event.type() == QEvent.LayoutRequest:        # il contenuto è cambiato
            self._fit()
        return handled

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resized.emit()

    def _fit(self) -> None:
        layout = self.layout()
        height = layout.totalHeightForWidth(self.width())
        if height < 0:          # senza testi che vanno a capo l'altezza non dipende dalla larghezza (Qt risponde -1)
            height = layout.sizeHint().height()
        if self._room:
            height = min(height, self._room + 2 * ARROW)
        if height != self.height():
            self.resize(self.width(), height)

    def place(self, anchor: QPoint, bounds: QRect, prefer: str) -> None:
        """Mette il riquadro sopra (`prefer="above"`) o a destra (`"right"`) di `anchor`, dentro `bounds`; se non c'è posto, dall'altra parte."""
        if self._scrolls:
            self._room = bounds.height() - 2 * _EDGE
        self._fit()
        width, height = self.width() - 2 * ARROW, self.height() - 2 * ARROW
        if prefer == "above":
            x = max(bounds.left() + _EDGE, min(anchor.x() - width // 2, bounds.right() - _EDGE - width))
            y, self._side = anchor.y() - _GAP - height, "bottom"
            if y < bounds.top() + _EDGE:
                y, self._side = anchor.y() + _GAP, "top"
            self._offset = max(24, min(anchor.x() - x, width - 24))
        else:
            y = max(bounds.top() + _EDGE, min(anchor.y() - height // 2, bounds.bottom() - _EDGE - height))
            x, self._side = anchor.x() + _GAP, "left"
            if x + width > bounds.right() - _EDGE:
                x, self._side = anchor.x() - _GAP - width, "right"
            x = max(bounds.left() + _EDGE, x)       # un'area stretta: il riquadro copre il pin, ma resta tutto visibile
            self._offset = max(24, min(anchor.y() - y, height - 24))
        self.move(x - ARROW, y - ARROW)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        body = QRectF(self.rect()).adjusted(ARROW, ARROW, -ARROW, -ARROW)
        tip, first, second = self._arrow(body)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.POPUP_BG))
        painter.drawRoundedRect(body, _RADIUS, _RADIUS)
        painter.drawPolygon(QPolygonF([first, tip, second]))
        border = QPen(QColor(theme.BORDER_STRONG), 1)
        path = QPainterPath()
        path.addRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS, _RADIUS)
        painter.setPen(border)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setPen(QPen(QColor(theme.POPUP_BG), 2))              # il bordo del riquadro sparisce sotto la base della freccetta
        painter.drawLine(first, second)
        painter.setPen(border)
        painter.drawPolyline(QPolygonF([first, tip, second]))

    def _arrow(self, body: QRectF) -> tuple[QPointF, QPointF, QPointF]:
        """(punta, un estremo della base, l'altro estremo) della freccetta."""
        o = self._offset
        if self._side == "bottom":
            return (QPointF(body.left() + o, body.bottom() + ARROW), QPointF(body.left() + o - ARROW, body.bottom() - 0.5),
                    QPointF(body.left() + o + ARROW, body.bottom() - 0.5))
        if self._side == "top":
            return (QPointF(body.left() + o, body.top() - ARROW), QPointF(body.left() + o - ARROW, body.top() + 0.5),
                    QPointF(body.left() + o + ARROW, body.top() + 0.5))
        if self._side == "left":
            return (QPointF(body.left() - ARROW, body.top() + o), QPointF(body.left() + 0.5, body.top() + o - ARROW),
                    QPointF(body.left() + 0.5, body.top() + o + ARROW))
        return (QPointF(body.right() + ARROW, body.top() + o), QPointF(body.right() - 0.5, body.top() + o - ARROW),
                QPointF(body.right() - 0.5, body.top() + o + ARROW))
