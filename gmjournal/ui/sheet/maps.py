"""La scheda interna «Mappe» di un luogo: la mappa che si apre da lui e le mappe dove compare."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ... import icons, theme
from ...data import trees
from ...data.models import Map, Pin, PinType
from ...data.repository import Repository
from ...elements import ElementKind
from ..kinds import pin_caption
from ..popups.map import create_map, edit_map
from ..map_target import MapTarget
from ..widgets.group_label import group_label
from ..widgets.map_card import TEXT_HEIGHT, MapCard
from ..widgets.menu import PopupMenu

_COVER_HEIGHT = 270
_ROW_HEIGHT = 58
_ICON = 34


class _PinRow(QAbstractButton):
    """Una mappa dove compare il luogo: il tipo del pin (icona colorata), il nome della mappa e cos'è il pin."""

    def __init__(self, map_name: str, pin: Pin, pin_type: PinType):
        super().__init__()
        self._name, self._caption, self._type = map_name, pin_caption(pin, pin_type), pin_type
        self.setFixedHeight(_ROW_HEIGHT)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def sizeHint(self) -> QSize:
        return QSize(100, _ROW_HEIGHT)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.HOVER if self.underMouse() else theme.SURFACE))
        painter.drawRoundedRect(QRectF(self.rect()), 10, 10)
        color = theme.category_color(self._type.color)
        box = QRectF(14, (self.height() - _ICON) / 2, _ICON, _ICON)
        painter.setBrush(theme.tint(color))
        painter.drawRoundedRect(box, 9, 9)
        icons.icon(self._type.icon, color).paint(painter, box.adjusted(8.5, 8.5, -8.5, -8.5).toRect())
        room = self.width() - 14 - _ICON - 12 - 14
        for font, text_color, text, top in ((theme.ui_font(14, 600), theme.TEXT, self._name, 9), (theme.ui_font(12), theme.MUTED, self._caption, 30)):
            painter.setFont(font)
            painter.setPen(QColor(text_color))
            painter.drawText(QRectF(14 + _ICON + 12, top, room, 18), Qt.AlignVCenter | Qt.AlignLeft,
                             QFontMetrics(font).elidedText(text, Qt.ElideRight, room))


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    return label


class MapsPage(QWidget):
    map_requested = Signal(object)      # una `MapTarget` da aprire nella schermata Mappe

    def __init__(self, repo: Repository, kind: ElementKind, element_id: int):
        super().__init__()
        self._repo, self._kind, self._element_id = repo, kind, element_id
        self._maps: list[Map] = []
        self._inside = QVBoxLayout()        # la mappa (o le mappe) che si aprono da questo luogo
        self._inside.setSpacing(10)
        self._appears = QVBoxLayout()       # le mappe dove compare
        self._appears.setSpacing(8)

        self._put = QPushButton(" Metti questo luogo su un’altra mappa")
        self._put.setObjectName("DashedButton")
        self._put.setIcon(icons.icon("plus", kind.color))
        self._put.setIconSize(QSize(14, 14))
        self._put.setFixedHeight(38)
        self._put.setStyleSheet("border-radius: 10px;")
        self._put.setCursor(Qt.PointingHandCursor)
        self._put.setFocusPolicy(Qt.NoFocus)
        self._put.clicked.connect(self._show_put_menu)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(group_label("Mappa di questo luogo"))
        left.addLayout(self._inside)
        left.addWidget(_note("Ogni luogo può avere una sua mappa interna (una città, un dungeon…)."))
        left.addStretch()
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(group_label("Compare nelle mappe"))
        right.addLayout(self._appears)
        right.addWidget(self._put)
        right.addStretch()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.setSpacing(20)
        layout.addLayout(left, 11)
        layout.addLayout(right, 10)
        self.reload()

    def reload(self) -> None:
        self._maps = self._repo.maps()
        pins = self._repo.pins_linked_to(self._kind.key, self._element_id)
        types = {pin_type.id: pin_type for pin_type in self._repo.pin_types()}
        names = {node.id: node.name for node in self._maps}
        by_id = {node.id: node for node in self._maps}
        self._clear(self._inside)
        self._clear(self._appears)

        opened = {pin.opens_map_id: pin for pin in reversed(pins) if pin.opens_map_id is not None}      # a parità di mappa vale il primo pin
        for map_id, pin in sorted(opened.items(), key=lambda item: pins.index(item[1])):
            self._inside.addWidget(self._map_card(by_id[map_id], f"Si apre dal pin sulla mappa «{names[pin.map_id]}»."))
        if not opened:
            self._inside.addWidget(_note("Nessuna mappa. Su una mappa, collega un pin a questo luogo e scegli quale mappa deve aprire."))
        for pin in pins:
            row = _PinRow(names[pin.map_id], pin, types[pin.type_id])
            row.clicked.connect(lambda _=False, pin=pin: self.map_requested.emit(MapTarget(pin.map_id, pin.id)))
            self._appears.addWidget(row)
        if not pins:
            self._appears.addWidget(_note("Non compare ancora su nessuna mappa."))

    @staticmethod
    def _clear(layout: QVBoxLayout) -> None:
        while layout.count():
            widget = layout.takeAt(0).widget()
            widget.setParent(None)
            widget.deleteLater()

    def _map_card(self, node: Map, meta: str) -> MapCard:
        card = MapCard()
        card.setFixedHeight(_COVER_HEIGHT + TEXT_HEIGHT)
        card.add_action("Apri la mappa")
        card.set_map(node.name, meta, self._repo.media_file(node.image))
        card.clicked.connect(lambda: self.map_requested.emit(MapTarget(node.id)))
        card.action_clicked.connect(lambda: self.map_requested.emit(MapTarget(node.id)))
        card.edit_clicked.connect(lambda: self._edit(node))
        return card

    def _edit(self, node: Map) -> None:
        if edit_map(self, self._repo, node) != QDialog.Rejected:
            self.reload()

    # --- «Metti questo luogo su un'altra mappa» ------------------------------------------------------
    def _show_put_menu(self) -> None:
        """Sceglie la mappa dove posare il pin di questo luogo: si apre quella mappa, pronta a posarlo."""
        menu = PopupMenu(self, width=300)
        for map_id, path in trees.named_paths(self._maps):
            menu.add_item("map", path, lambda map_id=map_id: self._put_on(map_id))
        if self._maps:
            menu.add_separator()
        menu.add_item("plus", "Crea una nuova mappa…", self._put_on_new)
        menu.popup_below(self._put)

    def _put_on(self, map_id: int) -> None:
        place = self._repo.link_target(self._kind.key, self._element_id)
        if place is None:
            QMessageBox.warning(self, "GM Journal", "Il luogo non esiste più.")
            return
        self.map_requested.emit(MapTarget(map_id, place=place))

    def _put_on_new(self) -> None:
        new_id = create_map(self, self._repo)
        if new_id is not None:
            self._put_on(new_id)
