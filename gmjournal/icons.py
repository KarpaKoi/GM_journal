"""Icone a tratto (SVG in assets/icons), colorate dal codice."""

from functools import lru_cache

from PySide6.QtCore import QByteArray, QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme


class _SvgIconEngine(QIconEngine):
    """Disegna l'SVG direttamente alla dimensione richiesta, quindi resta nitido a ogni scala."""

    def __init__(self, normal: QSvgRenderer, disabled: QSvgRenderer):
        super().__init__()
        self._renderers = (normal, disabled)

    def paint(self, painter, rect, mode, state):
        painter.setRenderHint(QPainter.Antialiasing)
        self._renderers[mode == QIcon.Mode.Disabled].render(painter, QRectF(rect))

    def pixmap(self, size, mode, state):
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(QPoint(0, 0), size), mode, state)
        painter.end()
        return pixmap

    def clone(self):
        return _SvgIconEngine(*self._renderers)


def _renderer(svg: str, color: str) -> QSvgRenderer:
    return QSvgRenderer(QByteArray(svg.replace("currentColor", color).encode()))


@lru_cache(maxsize=None)
def icon(name: str, color: str = theme.TEXT) -> QIcon:
    """Icona `assets/icons/<name>.svg` nel colore indicato (grigia se disattivata)."""
    svg = (theme.ASSETS_DIR / "icons" / f"{name}.svg").read_text(encoding="utf-8")
    return QIcon(_SvgIconEngine(_renderer(svg, color), _renderer(svg, theme.DISABLED)))
