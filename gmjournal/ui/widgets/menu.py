"""Menu a comparsa (come quello «⋯» delle card): voci con icona, una voce può essere «pericolosa»."""

from typing import Callable

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget

from ... import icons, theme

_WIDTH = 208
_SHADOW = 24  # spazio attorno al pannello per l'ombra


class _MenuItem(QAbstractButton):
    def __init__(self, icon_name: str | None, text: str, danger: bool, width: int, checked: bool):
        super().__init__()
        self.setText(text)
        self._icon = icons.icon(icon_name, theme.DANGER_TEXT if danger else theme.TEXT) if icon_name else None
        self._color = theme.DANGER_TEXT if danger else theme.TEXT
        self._width = width
        self._checked = checked
        self.setFixedHeight(36)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def sizeHint(self) -> QSize:
        return QSize(self._width - 12, 36)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        hovered = self.underMouse()
        if hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.MENU_HOVER))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        if self._icon is not None:
            self._icon.paint(painter, QRect(10, 10, 16, 16))
        left = 38 if self._icon is not None else 14
        painter.setFont(theme.ui_font(14))
        painter.setPen(QColor(theme.TEXT_ACTIVE if hovered and self._color == theme.TEXT else self._color))
        room = self.width() - left - (32 if self._checked else 10)
        text = QFontMetrics(painter.font()).elidedText(self.text(), Qt.ElideRight, room)
        painter.drawText(QRect(left, 0, room, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
        if self._checked:     # la voce attualmente scelta
            icons.icon("check", theme.ACCENT).paint(painter, QRect(self.width() - 30, 10, 16, 16))


class PopupMenu(QWidget):
    """Si chiude da solo con un clic fuori, con Esc o dopo aver scelto una voce."""

    def __init__(self, parent: QWidget, width: int = _WIDTH):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._width = width
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        panel = QFrame()
        panel.setObjectName("MenuPanel")
        panel.setFixedWidth(width)
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 128))
        panel.setGraphicsEffect(shadow)
        self._items = QVBoxLayout(panel)
        self._items.setContentsMargins(6, 6, 6, 6)
        self._items.setSpacing(0)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(_SHADOW, _SHADOW, _SHADOW, _SHADOW)
        outer.addWidget(panel)

    def add_item(self, icon_name: str | None, text: str, callback: Callable[[], None], danger: bool = False,
                 checked: bool = False) -> None:
        item = _MenuItem(icon_name, text, danger, self._width, checked)
        # La voce parte dopo la chiusura del menu, così può aprire finestre senza problemi.
        item.clicked.connect(lambda: (self.close(), QTimer.singleShot(0, callback)))
        self._items.addWidget(item)

    def add_separator(self) -> None:
        line = QFrame()
        line.setFixedHeight(1)
        line.setObjectName("Divider")
        holder = QWidget()
        holder.setFixedHeight(13)
        QVBoxLayout(holder).setContentsMargins(4, 6, 4, 6)
        holder.layout().addWidget(line)
        self._items.addWidget(holder)

    def popup_at(self, anchor: QPoint, align: str = "right") -> None:
        """Mostra il menu con l'angolo in alto a destra («right») o a sinistra («left») su `anchor` (coordinate globali)."""
        self.adjustSize()
        size = self.sizeHint()
        x = anchor.x() - size.width() + _SHADOW if align == "right" else anchor.x() - _SHADOW
        y = anchor.y() - _SHADOW
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = max(area.left(), min(x, area.right() - size.width()))
        y = max(area.top(), min(y, area.bottom() - size.height()))
        self.move(x, y)
        self.show()

    def popup_below(self, widget: QWidget) -> None:
        """Mostra il menu sotto `widget`, allineato al suo bordo sinistro."""
        self.popup_at(widget.mapToGlobal(QPoint(0, widget.height() + 4)), align="left")
