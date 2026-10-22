"""I segnalibri nella barra sinistra: pagine rapide da raggiungere con un clic. Passando il mouse su una riga compare la «x» che toglie il segnalibro."""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import LinkTarget
from ..kinds import kind_color, kind_icon
from .group_label import group_label

_ROW = 32
_ICON = 16
_PADDING = 10
_X_SIZE = 22
_MAX_ROWS = 4           # oltre questo numero le righe scorrono


class _Row(QAbstractButton):
    opened = Signal()
    removed = Signal()

    def __init__(self, target: LinkTarget, current: bool):
        super().__init__()
        self._target, self._current = target, current
        self.setToolTip(f"{target.name} · {target.detail}")
        self.setAttribute(Qt.WA_Hover)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(_ROW)

    def sizeHint(self) -> QSize:
        return QSize(100, _ROW)

    def _x_rect(self) -> QRect:
        return QRect(self.width() - _X_SIZE - 4, (self.height() - _X_SIZE) // 2, _X_SIZE, _X_SIZE)

    def mousePressEvent(self, event) -> None:
        event.accept()          # il clic vero è al rilascio: senza questo il rilascio non arriva

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            (self.removed if self._x_rect().contains(event.position().toPoint()) else self.opened).emit()

    def mouseMoveEvent(self, event) -> None:
        self.update()
        super().mouseMoveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        hovered = self.underMouse()
        if self._current or hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER if self._current else theme.HOVER_SOFT))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        icons.icon(kind_icon(self._target.kind), kind_color(self._target.kind)).paint(
            painter, QRect(_PADDING, (self.height() - _ICON) // 2, _ICON, _ICON))
        text_left = _PADDING + _ICON + 8
        room = self.width() - text_left - (_X_SIZE + 6 if hovered else _PADDING)
        font = theme.ui_font(14, 500 if self._current else 400)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_ACTIVE if self._current else theme.TEXT_SOFT))
        painter.drawText(QRect(text_left, 0, room, self.height()), Qt.AlignVCenter | Qt.AlignLeft,
                         QFontMetrics(font).elidedText(self._target.name, Qt.ElideRight, room))
        if hovered:
            hot = self._x_rect().contains(self.mapFromGlobal(self.cursor().pos()))
            if hot:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(theme.HOVER))
                painter.drawRoundedRect(self._x_rect(), 6, 6)
            icons.icon("x", theme.TEXT if hot else theme.MUTED).paint(painter, self._x_rect().adjusted(4, 4, -4, -4))


class BookmarkList(QWidget):
    chosen = Signal(str, int)           # (tipo, ID) del segnalibro scelto
    removed = Signal(str, int)          # (tipo, ID) del segnalibro tolto

    def __init__(self):
        super().__init__()
        self._shown: tuple | None = None
        self._column = QVBoxLayout()
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(1)
        body = QWidget()
        body.setLayout(self._column)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidget(body)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")   # lo sfondo è quello della barra
        title = group_label("SEGNALIBRI")
        title.setContentsMargins(10, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addWidget(self._scroll)

    def set_bookmarks(self, targets: list[LinkTarget], current: tuple[str, int] | None = None) -> None:
        """Mostra questi segnalibri; quello che coincide con `current` (il posto in cui si è) è evidenziato."""
        state = (tuple(targets), current)
        if state == self._shown:
            return
        self._shown = state
        while self._column.count():
            widget = self._column.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)      # subito fuori dalla barra (le prove, e il layout, non devono più vederla)
                widget.deleteLater()
        for target in targets:
            row = _Row(target, (target.kind, target.id) == current)
            row.opened.connect(lambda target=target: self.chosen.emit(target.kind, target.id))
            row.removed.connect(lambda target=target: self.removed.emit(target.kind, target.id))
            self._column.addWidget(row)
        self._column.addStretch()
        self._scroll.setFixedHeight(min(len(targets), _MAX_ROWS) * (_ROW + 1))

    @property
    def has_bookmarks(self) -> bool:
        return bool(self._shown and self._shown[0])
