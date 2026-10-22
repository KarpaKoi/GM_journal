"""Un elenco di righe disegnate a mano in un solo widget (niente un widget per riga: resta veloce con centinaia di righe).

Chi lo usa dice quante righe ci sono, quanto è alta ognuna e come si disegna (`row_height`, `paint_row`, eventualmente `paint_header`);
qui ci sono la cornice arrotondata, i filetti fra le righe, l'evidenziazione al passaggio del mouse e il clic."""

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ... import theme

_RADIUS = 12


class RowTable(QWidget):
    row_clicked = Signal(int, QPoint)       # la riga cliccata e il punto del clic (nelle coordinate del widget)

    def __init__(self, header_height: int = 0):
        super().__init__()
        self._count = 0
        self._header = header_height        # un'intestazione fissa sopra le righe, se serve (la disegna `paint_header`)
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self._fit()

    # --- Da definire -------------------------------------------------------------------------------
    def row_height(self, index: int) -> int:
        raise NotImplementedError

    def paint_row(self, painter: QPainter, index: int, row: QRect, hovered: bool) -> None:
        """Disegna il contenuto della riga dentro `row` (sfondo al passaggio del mouse e filetto sono già fatti)."""
        raise NotImplementedError

    def paint_header(self, painter: QPainter, header: QRect) -> None:
        """Disegna l'intestazione dentro `header`."""

    # --- Geometria ---------------------------------------------------------------------------------
    def set_count(self, count: int) -> None:
        self._count = count
        self._hover = -1
        self._fit()
        self.update()

    def _fit(self) -> None:
        self.setFixedHeight(self._header + sum(self.row_height(index) for index in range(self._count)) + 2)     # + il bordo

    def sizeHint(self) -> QSize:
        return QSize(100, self.height())

    def top(self, index: int) -> int:
        return 1 + self._header + sum(self.row_height(number) for number in range(index))

    def index_at(self, y: int) -> int:
        bottom = 1 + self._header
        for index in range(self._count):
            bottom += self.row_height(index)
            if y < bottom:
                return index if y >= 1 + self._header else -1
        return -1

    # --- Disegno -----------------------------------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(frame, _RADIUS, _RADIUS)
        painter.fillPath(clip, QColor(theme.SURFACE))
        painter.save()
        painter.setClipPath(clip)
        if self._header:
            self.paint_header(painter, QRect(1, 1, self.width() - 2, self._header))
        for index in range(self._count):
            top, hovered = self.top(index), index == self._hover
            row = QRect(1, top, self.width() - 2, self.row_height(index))
            if hovered:
                painter.fillRect(row, QColor(theme.HOVER_SOFT))
            if index or self._header:
                painter.fillRect(QRect(1, top, row.width(), 1), QColor(theme.BORDER))
            self.paint_row(painter, index, row, hovered)
        painter.restore()
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(frame, _RADIUS, _RADIUS)

    # --- Mouse -------------------------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        event.accept()          # il clic vero e proprio è al rilascio: senza questo il rilascio non arriva

    def mouseMoveEvent(self, event) -> None:
        index = self.index_at(int(event.position().y()))
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            index = self.index_at(int(event.position().y()))
            if index >= 0:
                self.row_clicked.emit(index, event.position().toPoint())
