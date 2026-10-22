"""Ciò che la mappa e il grafo hanno in comune: una vista con zoom e spostamento, e le barre che galleggiano sopra la tela."""

from typing import Callable

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGraphicsView, QHBoxLayout, QLabel, QToolButton, QVBoxLayout,
)

from ... import icons, theme
from .icon_label import IconLabel


class FloatingBar(QFrame):
    """Una barra sopra la tela: si riadatta da sola al suo contenuto; `resized` avvisa chi deve mettersi sotto o accanto."""

    resized = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("FloatingBar")

    def event(self, event) -> bool:
        handled = super().event(event)
        if event.type() == QEvent.LayoutRequest:
            self.adjustSize()
        return handled

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resized.emit()


def _bar_button(icon_name: str, label: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName("BarButton")
    button.setIconSize(QSize(18, 18))
    button.setFixedSize(36, 36)
    button.setToolTip(label)
    button.setAccessibleName(label)
    button.setCursor(Qt.PointingHandCursor)
    button.setFocusPolicy(Qt.NoFocus)
    button.setIcon(icons.icon(icon_name, theme.TEXT_SOFT))
    return button


class ToolBar(FloatingBar):
    """La barra verticale degli strumenti: prima quelli fra cui se ne sceglie uno solo, poi i pulsanti che fanno una cosa (zoom…)."""

    tool_chosen = Signal(str)

    def __init__(self, tools: tuple[tuple[str, str, str], ...], actions: tuple[tuple[str, str, Callable[[], None]], ...], color: str):
        """`tools`: (chiave, icona, nome); `actions`: (icona, nome, cosa fare); `color`: quello dello strumento scelto."""
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        group = QButtonGroup(self)
        self._buttons: dict[str, QToolButton] = {}
        for key, icon_name, label in tools:
            button = _bar_button(icon_name, label)
            button.setCheckable(True)
            button.toggled.connect(lambda checked, key=key, icon_name=icon_name, button=button: self._toggled(button, icon_name, key, checked, color))
            group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)
        next(iter(self._buttons.values())).setChecked(True)
        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        layout.addSpacing(3)
        layout.addWidget(divider)
        layout.addSpacing(3)
        for icon_name, label, action in actions:
            button = _bar_button(icon_name, label)
            button.clicked.connect(lambda _=False, action=action: action())
            layout.addWidget(button)

    def _toggled(self, button: QToolButton, icon_name: str, key: str, checked: bool, color: str) -> None:
        button.setIcon(icons.icon(icon_name, color if checked else theme.TEXT_SOFT))
        if checked:
            self.tool_chosen.emit(key)

    def set_tool(self, key: str) -> None:
        self._buttons[key].setChecked(True)


class HintPill(FloatingBar):
    """Il suggerimento in basso (per esempio «Clicca sulla mappa per aggiungere un pin»)."""

    def __init__(self, icon_name: str, color: str, text: str = ""):
        super().__init__()
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(IconLabel(icon_name, color, 14))
        self._text = QLabel()
        self._text.setFont(theme.ui_font(13))
        self._text.setStyleSheet(f"color: {theme.TEXT_SOFT}; background: transparent;")
        layout.addWidget(self._text)
        self.set_text(text)
        self.hide()

    def set_text(self, text: str) -> None:
        self._text.setText(text)
        self.adjustSize()


class ZoomView(QGraphicsView):
    """Una vista con zoom (rotella, verso il puntatore) e spostamento a mano, senza barre di scorrimento.

    Chi la usa decide fra quali valori si può ingrandire (`_min_scale`, `_max_scale`) e come reagire a ogni cambiamento (`_changed`)."""

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(QColor(theme.BG))
        self.setMouseTracking(True)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self._scale = self._min_scale = self._max_scale = 1.0
        self.horizontalScrollBar().valueChanged.connect(lambda _=0: self._changed())
        self.verticalScrollBar().valueChanged.connect(lambda _=0: self._changed())

    def _changed(self) -> None:
        """Zoom, spostamento o nuova misura: chi ha qualcosa agganciato alla tela lo riposiziona."""

    def _zoom_by(self, factor: float, under_mouse: bool = False) -> None:
        target = min(max(self._scale * factor, self._min_scale), self._max_scale)
        if target == self._scale:
            return
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse if under_mouse else QGraphicsView.AnchorViewCenter)
        self.scale(target / self._scale, target / self._scale)
        self._scale = target
        self._changed()

    def _pan_by(self, delta: QPoint) -> None:
        """Sposta la vista di `delta` pixel (la tela segue il puntatore)."""
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

    def wheelEvent(self, event) -> None:
        self._zoom_by(1.2 ** (event.angleDelta().y() / 120), under_mouse=True)
