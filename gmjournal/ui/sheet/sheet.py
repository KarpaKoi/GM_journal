"""La scheda di un elemento: l'intestazione (immagine, nome, categoria), le schede interne e ciò che contengono."""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from ... import icons, theme
from ...data.models import Element
from ...data.repository import Repository
from ...elements import DESCRIPTION, IMAGES, MAPS, MEMBERS, PROFILE, RELATIONS, STORY, ElementKind, Tab
from ...formatting import initials
from ..link_sources import LinkSources
from ..widgets.elided_label import ElidedLabel
from ..widgets.element_thumb import ElementThumb
from ..map_target import MapTarget
from ..widgets.filter_chip import FilterChip
from ..widgets.menu import PopupMenu
from .images import ImagesPage
from .maps import MapsPage
from .members import MembersPage
from .profile import ProfilePage, TextPage
from .relations import RelationsPage
from .saves import PendingSaves

_TAB_HEIGHT = 42


class _TabButton(QAbstractButton):
    def __init__(self, tab: Tab):
        super().__init__()
        self._tab = tab
        self.setText(tab.label)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover)
        self.setFixedHeight(_TAB_HEIGHT)

    def sizeHint(self) -> QSize:
        return QSize(14 + 16 + 8 + QFontMetrics(theme.ui_font(14, 600)).horizontalAdvance(self.text()) + 14, _TAB_HEIGHT)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        color = theme.TEXT_ACTIVE if on else theme.TEXT_SOFT if self.underMouse() else theme.MUTED
        icons.icon(self._tab.icon, color).paint(painter, QRect(14, (self.height() - 16) // 2, 16, 16))
        painter.setFont(theme.ui_font(14, 600 if on else 500))
        painter.setPen(QColor(color))
        painter.drawText(QRect(38, 0, self.width() - 38, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        if on:
            painter.fillRect(0, self.height() - 2, self.width(), 2, QColor(theme.ACCENT))


class _TabBar(QWidget):
    """Le schede interne: una riga di pulsanti con una linea sotto; quella scelta ha la linea colorata."""

    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(_TAB_HEIGHT)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._buttons: dict[str, _TabButton] = {}

    def set_tabs(self, tabs: tuple[Tab, ...], current: str) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._buttons.clear()
        for tab in tabs:
            button = _TabButton(tab)
            button.clicked.connect(lambda _=False, key=tab.key: self.select(key))
            self._layout.addWidget(button)
            self._buttons[tab.key] = button
        self._layout.addStretch()
        self.select(current, notify=False)

    def select(self, key: str, notify: bool = True) -> None:
        for tab_key, button in self._buttons.items():
            button.setChecked(tab_key == key)
        if notify:
            self.changed.emit(key)

    def paintEvent(self, event) -> None:
        QPainter(self).fillRect(0, self.height() - 1, self.width(), 1, QColor(theme.BORDER))


class ElementSheet(QWidget):
    back_requested = Signal()
    edit_requested = Signal()
    link_requested = Signal(str, int)     # si vuole aprire ciò che un collegamento indica (una pagina o un elemento): (tipo, ID)
    map_requested = Signal(object)        # si vuole aprire una mappa: una `MapTarget`

    def __init__(self, repo: Repository, kind: ElementKind):
        super().__init__()
        self._repo, self._kind = repo, kind
        self._element_id: int | None = None
        self._saves = PendingSaves(self, lambda message: QMessageBox.warning(self, "GM Journal", message))
        self._sources = LinkSources(self, repo, lambda: (kind.key, self._element_id))

        back = QToolButton()
        back.setObjectName("BackLink")
        back.setIcon(icons.icon("chevron-left", theme.MUTED))
        back.setIconSize(QSize(15, 15))
        back.setText(kind.title)
        back.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self.back_requested)

        self._thumb = ElementThumb(88, 14, 88)
        self._name = ElidedLabel(font=theme.serif_font(34, 500, -0.01), color=theme.TEXT_ACTIVE)
        self._name.setFixedHeight(40)
        self._chip_slot = QHBoxLayout()
        self._chip_slot.setContentsMargins(0, 0, 0, 0)
        self._role = QLabel()
        self._role.setStyleSheet(f"color: {theme.TEXT_SOFT};")
        self._dot = QLabel("·")
        self._dot.setStyleSheet(f"color: {theme.DISABLED};")
        self._brief = ElidedLabel(font=theme.ui_font(14), color=theme.MUTED)
        details = QHBoxLayout()
        details.setSpacing(12)
        details.addLayout(self._chip_slot)
        details.addWidget(self._role)
        details.addWidget(self._dot)
        details.addWidget(self._brief, 1)
        titles = QVBoxLayout()
        titles.setSpacing(8)
        titles.addWidget(self._name)
        titles.addLayout(details)
        edit = QPushButton(" Modifica")
        edit.setIcon(icons.icon("pencil"))
        edit.setIconSize(QSize(16, 16))
        edit.setFixedHeight(36)
        edit.setCursor(Qt.PointingHandCursor)
        edit.clicked.connect(self.edit_requested)

        header = QHBoxLayout()
        header.setSpacing(20)
        header.addWidget(self._thumb)
        header.addLayout(titles, 1)
        if any(tab.key == MAPS for tab in kind.tabs):        # solo ciò che può stare su una mappa (i luoghi)
            self._on_map = QPushButton(" Vedi sulla mappa")
            self._on_map.setIcon(icons.icon("map"))
            self._on_map.setIconSize(QSize(16, 16))
            self._on_map.setFixedHeight(36)
            self._on_map.setCursor(Qt.PointingHandCursor)
            self._on_map.clicked.connect(self._show_on_map)
            header.addWidget(self._on_map)
        header.addWidget(edit)

        self._tabs = _TabBar()
        self._tabs.changed.connect(self._show_page)
        self._pages = QStackedWidget()
        self._order: list[str] = []         # le chiavi delle schede interne, nell'ordine delle pagine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 22, 32, 0)
        layout.setSpacing(0)
        layout.addWidget(back, alignment=Qt.AlignLeft)
        layout.addSpacing(14)
        layout.addLayout(header)
        layout.addSpacing(20)
        layout.addWidget(self._tabs)
        layout.addSpacing(20)
        layout.addWidget(self._pages, 1)

    @property
    def element_id(self) -> int | None:
        return self._element_id

    def open(self, element_id: int) -> None:
        """Mostra la scheda di un elemento, dalla prima scheda interna."""
        self.flush()
        self._element_id = element_id
        self._fill(self._kind.tabs[0].key)

    def reload(self) -> None:
        """Rilegge tutto dal database (la scheda interna resta quella). Da usare quando i dati possono essere cambiati altrove."""
        if self._element_id is not None and self.flush():
            self._fill(self._order[self._pages.currentIndex()] if self._order else self._kind.tabs[0].key)

    def refresh_header(self) -> None:
        """Rilegge solo l'intestazione (dopo «Modifica»)."""
        element = self._repo.element(self._element_id)
        category = next(c for c in self._repo.categories(self._kind.key) if c.id == element.category_id)
        self._fill_header(element, theme.category_color(category.color), category.name)

    def flush(self) -> bool:
        return self._saves.flush()

    # --- Costruzione -----------------------------------------------------------------------
    def _fill(self, tab_key: str) -> None:
        self.refresh_header()
        texts = self._repo.texts(self._element_id)
        while self._pages.count():
            page = self._pages.widget(0)
            self._pages.removeWidget(page)
            page.deleteLater()
        self._order = [tab.key for tab in self._kind.tabs]
        for key in self._order:
            page = self._make_page(key, texts)
            if key == IMAGES:
                page.changed.connect(self.refresh_header)
            elif key == MAPS:
                page.map_requested.connect(self.map_requested)
            else:
                page.link_requested.connect(self.link_requested)
            if key == PROFILE:
                page.members_requested.connect(lambda: self._tabs.select(MEMBERS))
            self._pages.addWidget(page)
        self._tabs.set_tabs(self._kind.tabs, tab_key if tab_key in self._order else self._order[0])
        self._show_page(tab_key if tab_key in self._order else self._order[0])

    def _make_page(self, key: str, texts: dict[str, str]) -> QWidget:
        args = (self._repo, self._kind, self._element_id)
        if key == PROFILE:
            return ProfilePage(*args, texts, self._sources, self._saves)
        if key in (STORY, DESCRIPTION):
            return TextPage(self._repo, self._element_id, texts, self._sources, self._saves, key, self._kind.suggestions)
        if key == MEMBERS:
            return MembersPage(*args, self._sources, self._saves)
        if key == IMAGES:
            return ImagesPage(*args)
        if key == MAPS:
            return MapsPage(*args)
        assert key == RELATIONS
        return RelationsPage(*args, self._sources, self._saves)

    def _show_on_map(self) -> None:
        """«Vedi sulla mappa»: apre la mappa dove compare il luogo (se sono più d'una, si sceglie); se non compare da nessuna parte, mostra la scheda «Mappe»."""
        pins = self._repo.pins_linked_to(self._kind.key, self._element_id)
        if not pins:
            self._tabs.select(MAPS)
            return
        names = {node.id: node.name for node in self._repo.maps()}
        if len(pins) == 1:
            self.map_requested.emit(MapTarget(pins[0].map_id, pins[0].id))
            return
        menu = PopupMenu(self, width=300)
        for pin in pins:
            menu.add_item("map", names[pin.map_id], lambda pin=pin: self.map_requested.emit(MapTarget(pin.map_id, pin.id)))
        menu.popup_below(self._on_map)

    def _show_page(self, key: str) -> None:
        self._pages.setCurrentIndex(self._order.index(key))

    def _fill_header(self, element: Element, color: str, category: str) -> None:
        image = self._repo.media_file(element.image)
        self._thumb.set_element(initials(element.name), color, image)
        self._name.setText(element.name)
        while self._chip_slot.count():
            item = self._chip_slot.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        chip = FilterChip(category, color, height=26, font_px=12)
        chip.setChecked(True)
        chip.setAttribute(Qt.WA_TransparentForMouseEvents)
        chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)       # senza «in breve» la riga non deve allargarla
        self._chip_slot.addWidget(chip)
        self._role.setText(element.role)
        self._role.setVisible(bool(element.role))
        self._dot.setVisible(bool(element.role and element.brief))
        self._brief.setText(element.brief)
        self._brief.setVisible(bool(element.brief))
