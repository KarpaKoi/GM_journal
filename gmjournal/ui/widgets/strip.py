"""Una riga di widget che, se non c'è spazio, scorre di lato con la rotella invece di sovrapporsi."""

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget


class HorizontalStrip(QScrollArea):
    """Contiene la riga dei pulsanti: se lo spazio non basta la riga scorre di lato (con la rotella) invece di sovrapporsi."""

    def __init__(self, row: QWidget):
        super().__init__()
        self.setFocusPolicy(Qt.NoFocus)         # un clic sulla riga (anche su un pulsante spento) non toglie il cursore al testo
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)
        self.setWidget(row)
        row.setAutoFillBackground(False)        # `setWidget` lo riattiva: dentro un popup la riga deve restare trasparente

    def sizeHint(self) -> QSize:
        return self.widget().sizeHint()         # la riga intera (Qt di suo la taglierebbe a una misura fissa)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.sizeHint().height())       # può stringersi quanto serve, ma resta alta quanto la riga

    def eventFilter(self, watched, event) -> bool:
        if watched is self.widget() and event.type() == QEvent.LayoutRequest:       # la riga è cambiata: chi contiene la barra si riadatta
            self.updateGeometry()
        return super().eventFilter(watched, event)

    def wheelEvent(self, event) -> None:
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - (event.angleDelta().y() or event.angleDelta().x()))
