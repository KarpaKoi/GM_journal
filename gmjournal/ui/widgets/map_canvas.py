"""La mappa interattiva: lo sfondo, i pin, gli strumenti, i filtri per tipo e, ancorata a un pin, una finestrella.

Il widget mostra e raccoglie i gesti; non tocca i dati: dice cosa è successo con dei segnali e la schermata decide.
Le posizioni dei pin sono frazioni dell'immagine (da 0 a 1), così non dipendono dallo zoom né dalla misura dello sfondo.
"""

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImageReader, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsScene, QHBoxLayout, QPushButton, QWidget

from ... import icons, theme
from ...data.models import Pin, PinType
from .anchored_card import AnchoredCard
from .canvas_base import FloatingBar, HintPill, ToolBar, ZoomView
from .empty_state import EmptyState
from .filter_chip import FilterChip
from .strip import HorizontalStrip

SELECT, ADD, MOVE = "select", "add", "move"      # gli strumenti
GHOST = 0                                         # «ID» del pin appena posato, non ancora salvato
MAX_SIDE = 4096                                   # uno sfondo più grande di così (in pixel) viene ridotto
_COLOR = theme.SECTION_COLORS["mappe"]
_PIN_RADIUS = 16
_DRAG_START = 4                                   # pixel di spostamento oltre i quali un clic diventa un trascinamento
_TOOLS = ((SELECT, "pointer", "Seleziona"), (ADD, "map-pin-plus", "Aggiungi pin"), (MOVE, "move", "Sposta la mappa"))


class PinItem(QGraphicsItem):
    """Un pin: un cerchio con l'icona del suo tipo. Resta della stessa misura a qualunque zoom."""

    def __init__(self, pin_id: int, type_id: int, name: str, icon: str, color: str):
        super().__init__()
        self.pin_id, self.type_id = pin_id, type_id
        self._icon, self._color = icon, color
        self._selected = self._hovered = False
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.setToolTip(name)
        self.setZValue(5)

    def set_style(self, icon: str, color: str) -> None:
        self._icon, self._color = icon, color
        self.update()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setZValue(15 if selected else 5)
        self.update()

    def set_hovered(self, hovered: bool) -> None:
        self._hovered = hovered
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-24, -24, 48, 48)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), _PIN_RADIUS + 2, _PIN_RADIUS + 2)
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(self._color)
        painter.setPen(Qt.NoPen)
        if self._selected or self._hovered:
            ring = QColor(color)
            ring.setAlphaF(0.4 if self._selected else 0.25)
            painter.setBrush(ring)
            painter.drawEllipse(QPointF(0, 0), _PIN_RADIUS + 4, _PIN_RADIUS + 4)
        else:
            painter.setBrush(QColor(0, 0, 0, 80))
            painter.drawEllipse(QPointF(0, 2), _PIN_RADIUS + 1, _PIN_RADIUS + 1)
        painter.setBrush(QColor(theme.BG))
        painter.drawEllipse(QPointF(0, 0), _PIN_RADIUS, _PIN_RADIUS)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(0, 0), _PIN_RADIUS - 2, _PIN_RADIUS - 2)
        icons.icon(self._icon, theme.BG).paint(painter, QRect(-8, -8, 16, 16))


class MapCanvas(ZoomView):
    pin_clicked = Signal(int)
    pin_moved = Signal(int, float, float)      # ID (o GHOST), nuova posizione
    background_clicked = Signal()
    add_requested = Signal(float, float)       # clic sulla mappa con lo strumento «Aggiungi pin»
    type_requested = Signal()                  # il «+» fra i filtri
    image_requested = Signal()                 # «Scegli un'immagine» quando la mappa non ha sfondo
    tool_changed = Signal(str)                 # un altro strumento (SELECT, ADD o MOVE)

    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._image: QGraphicsPixmapItem | None = None
        self._pins: dict[int, PinItem] = {}
        self._types: dict[int, PinType] = {}
        self._hidden: set[int] = set()             # i tipi di pin nascosti dai filtri
        self._chips: dict[int, FilterChip] = {}
        self._selected: int | None = None
        self._hovered: PinItem | None = None
        self._tool = SELECT
        self._fitted = True
        self._press: QPoint | None = None          # dove è stato premuto il mouse
        self._press_pin: PinItem | None = None
        self._last = QPoint()
        self._moved = False
        self._card: AnchoredCard | None = None
        self._card_pin: int | None = None
        self._card_prefer = "above"
        self._locked = False                       # finestrella aperta che chiede di essere finita: la mappa non reagisce ai clic

        self._filters = self._make_filters()
        self._hint = HintPill("map-pin-plus", _COLOR, "Clicca sulla mappa per aggiungere un pin")
        self._hint.setParent(self)
        self._tools = ToolBar(_TOOLS, (("plus", "Ingrandisci", lambda: self._zoom_by(1.25)), ("minus", "Riduci", lambda: self._zoom_by(0.8))), _COLOR)
        self._tools.setParent(self)
        self._tools.tool_chosen.connect(self._set_tool)
        self._empty = EmptyState("map", _COLOR, "Questa mappa non ha uno sfondo",
                                 "Scegli dalla libreria l'immagine della mappa disegnata: i pin si posano sopra.", "Scegli un'immagine")
        self._empty.setParent(self)
        self._empty.setAutoFillBackground(True)
        self._empty.clicked.connect(self.image_requested)
        self._update_overlays()
        self._filters.resized.connect(self._update_overlays)     # se la barra cambia altezza, gli strumenti sotto la seguono

    # --- Costruzione delle barre ----------------------------------------------------------------
    def _make_filters(self) -> FloatingBar:
        bar = FloatingBar()
        bar.setParent(self)
        row = QWidget()
        self._filter_row = QHBoxLayout(row)
        self._filter_row.setContentsMargins(4, 4, 4, 4)
        self._filter_row.setSpacing(4)
        inside = QHBoxLayout(bar)
        inside.setContentsMargins(0, 0, 0, 0)
        inside.addWidget(HorizontalStrip(row))      # con molti tipi la barra non esce dalla mappa: i filtri scorrono di lato
        return bar

    # --- Sfondo e pin ---------------------------------------------------------------------------------
    def set_image(self, file: Path | None) -> None:
        """Mostra lo sfondo (rimuovendo i pin: vanno rimessi con `set_pins`). Senza file, o se non si legge, compare l'invito a sceglierlo."""
        self.close_card()
        self._scene.clear()
        self._pins.clear()
        self._image = self._hovered = None
        self._selected = None
        pixmap = self._load(file) if file is not None else None
        if pixmap is not None:
            self._image = self._scene.addPixmap(pixmap)
            self._image.setTransformationMode(Qt.SmoothTransformation)
            self._scene.setSceneRect(self._image.boundingRect())
            self._fitted = True
            self._fit()
        self._update_overlays()
        self._changed()

    @staticmethod
    def _load(file: Path) -> QPixmap | None:
        reader = QImageReader(str(file))
        reader.setAutoTransform(True)
        size = reader.size()
        if not size.isValid():
            return None
        if max(size.width(), size.height()) > MAX_SIDE:
            reader.setScaledSize(size.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio))
        image = reader.read()
        return None if image.isNull() else QPixmap.fromImage(image)

    def has_image(self) -> bool:
        return self._image is not None

    def set_types(self, types: list[PinType]) -> None:
        """I tipi di pin: ricostruisce i filtri. Un tipo nuovo è visibile; quelli nascosti restano nascosti."""
        self._types = {t.id: t for t in types}
        self._hidden &= set(self._types)
        while self._filter_row.count():
            old = self._filter_row.takeAt(0).widget()
            old.setParent(None)
            old.deleteLater()
        self._chips = {}
        for pin_type in types:
            chip = FilterChip(pin_type.name, theme.category_color(pin_type.color), height=30)
            chip.setChecked(pin_type.id not in self._hidden)
            chip.toggled.connect(lambda checked, type_id=pin_type.id: self._show_type(type_id, checked))
            self._filter_row.addWidget(chip)
            self._chips[pin_type.id] = chip
        add = QPushButton()
        add.setObjectName("DashedButton")
        add.setIcon(icons.icon("plus", theme.TEXT_ACTIVE))
        add.setIconSize(QSize(15, 15))
        add.setFixedSize(30, 30)
        add.setStyleSheet("padding: 0; min-height: 30px; border-radius: 15px;")
        add.setToolTip("Nuovo tipo di pin")
        add.setAccessibleName("Nuovo tipo di pin")
        add.setCursor(Qt.PointingHandCursor)
        add.setFocusPolicy(Qt.NoFocus)
        add.clicked.connect(self.type_requested)
        self._filter_row.addWidget(add)

    def reveal_type(self, type_id: int) -> None:
        """Rende visibile un tipo nascosto (per esempio perché ci si è appena posato un pin)."""
        if type_id in self._chips:
            self._chips[type_id].setChecked(True)

    def _show_type(self, type_id: int, shown: bool) -> None:
        (self._hidden.discard if shown else self._hidden.add)(type_id)
        for item in self._pins.values():
            item.setVisible(item.type_id not in self._hidden)

    def set_pins(self, pins: list[Pin]) -> None:
        for item in self._pins.values():
            self._scene.removeItem(item)
        self._pins.clear()
        self._hovered = None
        if self._image is None:
            return
        for pin in pins:
            pin_type = self._types[pin.type_id]
            item = PinItem(pin.id, pin.type_id, pin.name, pin_type.icon, theme.category_color(pin_type.color))
            item.setPos(self._to_scene(pin.x, pin.y))
            item.setVisible(pin.type_id not in self._hidden)
            item.set_selected(pin.id == self._selected)
            self._scene.addItem(item)
            self._pins[pin.id] = item
        self._changed()

    def set_selected(self, pin_id: int | None) -> None:
        self._selected = pin_id
        for item_id, item in self._pins.items():
            item.set_selected(item_id == pin_id)

    def show_ghost(self, x: float, y: float, pin_type: PinType) -> None:
        """Il pin appena posato (non ancora salvato), nello stile di `pin_type`."""
        item = self._pins.get(GHOST)
        if item is None:
            item = self._pins[GHOST] = PinItem(GHOST, pin_type.id, "", pin_type.icon, theme.category_color(pin_type.color))
            item.set_selected(True)
            self._scene.addItem(item)
        item.type_id = pin_type.id
        item.set_style(pin_type.icon, theme.category_color(pin_type.color))
        item.setPos(self._to_scene(x, y))
        self._changed()

    def clear_ghost(self) -> None:
        item = self._pins.pop(GHOST, None)
        if item is not None:
            self._scene.removeItem(item)

    def reveal(self, pin_id: int) -> None:
        """Se il pin è fuori dalla parte visibile, porta la mappa a centrarlo."""
        item = self._pins.get(pin_id)
        if item is not None and not self.viewport().rect().adjusted(40, 40, -40, -40).contains(self.mapFromScene(item.pos())):
            self.centerOn(item)

    def _to_scene(self, x: float, y: float) -> QPointF:
        rect = self._image.boundingRect()
        return QPointF(x * rect.width(), y * rect.height())

    def _fraction(self, point: QPointF) -> tuple[float, float]:
        rect = self._image.boundingRect()
        return min(max(point.x() / rect.width(), 0.0), 1.0), min(max(point.y() / rect.height(), 0.0), 1.0)

    # --- Strumenti, zoom, cornici ---------------------------------------------------------------
    def set_tool(self, tool: str) -> None:
        self._tools.set_tool(tool)

    def _set_tool(self, tool: str) -> None:
        self._tool = tool
        self.tool_changed.emit(tool)
        self._hint.setVisible(self._image is not None and tool == ADD)
        self.viewport().setCursor({SELECT: Qt.ArrowCursor, ADD: Qt.CrossCursor, MOVE: Qt.OpenHandCursor}[tool])

    def _zoom_by(self, factor: float, under_mouse: bool = False) -> None:
        if self._image is not None:
            super()._zoom_by(factor, under_mouse)
            self._fitted = self._scale <= self._min_scale * 1.001

    def _fit(self) -> None:
        """Calcola quanto ingrandire per vedere tutta l'immagine; se non è stato fatto zoom, la inquadra."""
        view, size = self.viewport().size(), self._image.boundingRect().size()
        if view.width() <= 0 or view.height() <= 0:
            return
        self._min_scale = min(view.width() / size.width(), view.height() / size.height())
        self._max_scale = max(self._min_scale * 8, 4.0)
        if self._fitted or self._scale < self._min_scale:
            self.resetTransform()
            self.scale(self._min_scale, self._min_scale)
            self._scale, self._fitted = self._min_scale, True
            self.centerOn(self._image)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._image is not None:
            self._fit()
        self._update_overlays()
        self._changed()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._image is not None:
            self._fit()
            self._changed()

    def _update_overlays(self) -> None:
        """Barre e invito nelle loro posizioni; senza sfondo c'è solo l'invito a sceglierlo."""
        has_image = self._image is not None
        self._empty.setGeometry(self.rect())
        self._empty.setVisible(not has_image)
        self._filters.setVisible(has_image)
        self._tools.setVisible(has_image)
        self._hint.setVisible(has_image and self._tool == ADD)
        self._filters.setMaximumWidth(max(0, self.width() - 32))
        self._filters.adjustSize()
        self._tools.adjustSize()
        self._filters.move(16, 16)
        self._tools.move(16, 16 + self._filters.height() + 10)
        self._hint.move((self.width() - self._hint.width()) // 2, self.height() - 16 - self._hint.height())
        for overlay in (self._filters, self._tools, self._hint):
            overlay.raise_()
        if self._card is not None:
            self._card.raise_()

    def _changed(self) -> None:
        """Zoom, spostamento o nuova misura: la finestrella deve seguire il suo pin."""
        self._place_card()

    # --- Finestrella ancorata a un pin -------------------------------------------------------------
    def show_card(self, card: AnchoredCard, pin_id: int, prefer: str, locked: bool = False) -> None:
        """Mostra `card` accanto al pin (`prefer`: «above» o «right»), al posto di quella che c'era.
        Con `locked` la mappa ignora i clic (si può solo trascinare quel pin) finché la finestrella non si chiude."""
        self.close_card()
        card.setParent(self)
        card.resized.connect(self._place_card)
        self._card, self._card_pin, self._card_prefer, self._locked = card, pin_id, prefer, locked
        card.show()
        self._place_card()
        card.raise_()

    def close_card(self) -> None:
        if self._card is not None:
            self._card.hide()
            self._card.deleteLater()
        self._card = self._card_pin = None
        self._locked = False

    def _place_card(self) -> None:
        item = self._pins.get(self._card_pin) if self._card is not None else None
        if item is not None:
            self._card.place(self.viewport().mapTo(self, self.mapFromScene(item.pos())), self.rect(), self._card_prefer)

    # --- Mouse ---------------------------------------------------------------------------------------
    def _pin_at(self, point: QPoint) -> PinItem | None:
        return next((item for item in self.items(point) if isinstance(item, PinItem) and item.isVisible()), None)

    def _draggable(self, item: PinItem | None) -> bool:
        """Mentre si compila una finestrella si può trascinare solo il suo pin."""
        return item is not None and (not self._locked or item.pin_id == self._card_pin)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or self._image is None:
            return super().mousePressEvent(event)
        self._press = self._last = event.position().toPoint()
        self._press_pin = self._pin_at(self._press) if self._tool == SELECT else None
        self._moved = False
        if self._tool == MOVE:
            self.viewport().setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        point = event.position().toPoint()
        if self._press is None:
            self._hover(point)
            return super().mouseMoveEvent(event)
        self._moved = self._moved or (point - self._press).manhattanLength() > _DRAG_START
        if self._moved:
            if self._draggable(self._press_pin):
                rect = self._image.boundingRect()
                scene = self.mapToScene(point)
                self._press_pin.setPos(min(max(scene.x(), 0), rect.width()), min(max(scene.y(), 0), rect.height()))
                self._changed()
            else:
                self._pan_by(point - self._last)
        self._last = point

    def mouseReleaseEvent(self, event) -> None:
        if self._press is None:
            return super().mouseReleaseEvent(event)
        item, moved, point = self._press_pin, self._moved, self._press
        self._press = self._press_pin = None
        self._moved = False
        if self._tool == MOVE:
            self.viewport().setCursor(Qt.OpenHandCursor)
        if moved:
            if self._draggable(item):
                self.pin_moved.emit(item.pin_id, *self._fraction(item.pos()))
        elif not self._locked:
            self._clicked(item, point)

    def _clicked(self, item: PinItem | None, point: QPoint) -> None:
        if self._tool == ADD:
            scene = self.mapToScene(point)
            if self._image.boundingRect().contains(scene):
                self.add_requested.emit(*self._fraction(scene))
        elif item is not None and item.pin_id != GHOST:
            self.pin_clicked.emit(item.pin_id)
        elif item is None and self._tool == SELECT:
            self.background_clicked.emit()

    def _hover(self, point: QPoint) -> None:
        item = self._pin_at(point) if self._tool == SELECT else None
        if item is not self._hovered:
            if self._hovered is not None:
                self._hovered.set_hovered(False)
            if item is not None:
                item.set_hovered(True)
            self._hovered = item
            self.viewport().setCursor(Qt.PointingHandCursor if item is not None else Qt.ArrowCursor)
