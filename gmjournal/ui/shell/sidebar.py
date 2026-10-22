"""Barra sinistra: navigazione tra le schermate, riducibile a sole icone."""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QFrame, QLabel, QStackedWidget, QVBoxLayout, QWidget

from ... import icons, theme
from ...sections import SECTIONS, SETTINGS, Section
from ..widgets.bookmark_list import BookmarkList
from ..widgets.group_label import group_label

_BUTTON_HEIGHT = 40
_ICON_SIZE = 20
_PADDING = 12  # margine interno del pulsante e spazio tra icona e testo


class NavButton(QAbstractButton):
    """Voce della barra: icona colorata e nome; ridotta, resta solo l'icona al centro."""

    def __init__(self, section: Section):
        super().__init__()
        self._section = section
        self._icon = icons.icon(section.icon, section.color)
        self._collapsed = False
        self.setCheckable(True)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(_BUTTON_HEIGHT)
        self.setAccessibleName(section.label)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setToolTip(self._section.label if collapsed else "")
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(theme.SIDEBAR_WIDTH, _BUTTON_HEIGHT)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.isChecked() or self.underMouse():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER if self.isChecked() else theme.HOVER_SOFT))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)

        icon_x = (self.width() - _ICON_SIZE) // 2 if self._collapsed else _PADDING
        self._icon.paint(painter, QRect(icon_x, (self.height() - _ICON_SIZE) // 2, _ICON_SIZE, _ICON_SIZE))
        if self._collapsed:
            return

        font = theme.ui_font(14, 500)
        text_x = _PADDING + _ICON_SIZE + _PADDING
        text = QFontMetrics(font).elidedText(self._section.label, Qt.ElideRight, self.width() - text_x - _PADDING)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_ACTIVE if self.isChecked() else theme.TEXT_SOFT))
        painter.drawText(QRect(text_x, 0, self.width() - text_x, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)


class _Divider(QWidget):
    """Linea sottile orizzontale, con spazio sopra e sotto."""

    def __init__(self, inset: int, above: int, below: int):
        super().__init__()
        self._inset, self._above = inset, above
        self.setFixedHeight(above + 1 + below)

    def paintEvent(self, event):
        QPainter(self).fillRect(
            QRect(self._inset, self._above, self.width() - 2 * self._inset, 1), QColor(theme.BORDER)
        )


class Sidebar(QFrame):
    section_selected = Signal(str)  # chiave della schermata scelta
    bookmark_chosen = Signal(str, int)      # (tipo, ID) del segnalibro scelto
    bookmark_removed = Signal(str, int)     # (tipo, ID) del segnalibro tolto

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self._collapsed = False
        self._has_context = False
        self._buttons: dict[str, NavButton] = {}
        self._group_labels: list[QLabel] = []
        self._group_dividers: list[_Divider] = []
        self._button_group = QButtonGroup(self)  # esclusivo: una sola voce attiva

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(2)

        last_group = ""
        for section in SECTIONS:
            if section.group and section.group != last_group:
                self._add_group_header(layout, section.group)
            last_group = section.group
            layout.addWidget(self._make_button(section))

        # Zona contestuale (capitoli, mappe, grafi…): la riempie la schermata attiva.
        self._context_divider = _Divider(inset=4, above=12, below=10)
        self._context_stack = QStackedWidget()
        layout.addWidget(self._context_divider)
        layout.addWidget(self._context_stack, 1)

        # I segnalibri stanno sotto la lista della schermata (e restano quando questa cambia).
        self._bookmarks = BookmarkList()
        self._bookmarks.chosen.connect(self.bookmark_chosen)
        self._bookmarks.removed.connect(self.bookmark_removed)
        self._bookmarks_divider = _Divider(inset=4, above=10, below=8)
        layout.addWidget(self._bookmarks_divider)
        layout.addWidget(self._bookmarks)
        layout.addStretch()  # senza lista contestuale tiene Impostazioni in fondo

        layout.addWidget(self._make_button(SETTINGS))
        self.set_context(None)
        self._apply_collapsed()

    def _add_group_header(self, layout: QVBoxLayout, title: str) -> None:
        label = group_label(title)
        label.setContentsMargins(_PADDING, 14, _PADDING, 4)
        divider = _Divider(inset=8, above=10, below=10)  # al posto del titolo quando la barra è ridotta
        self._group_labels.append(label)
        self._group_dividers.append(divider)
        layout.addWidget(label)
        layout.addWidget(divider)

    def _make_button(self, section: Section) -> NavButton:
        button = NavButton(section)
        button.clicked.connect(lambda: self.section_selected.emit(section.key))
        self._button_group.addButton(button)
        self._buttons[section.key] = button
        return button

    def set_current(self, key: str) -> None:
        """Evidenzia la voce della schermata attiva (senza emettere segnali)."""
        self._buttons[key].setChecked(True)

    def set_context(self, widget: QWidget | None) -> None:
        """Mostra sotto le voci la lista della schermata attiva (None = nessuna lista)."""
        if widget is not None:
            if self._context_stack.indexOf(widget) < 0:
                self._context_stack.addWidget(widget)
            self._context_stack.setCurrentWidget(widget)
        self._has_context = widget is not None
        self._update_context_visibility()

    def set_bookmarks(self, targets, current: tuple[str, int] | None) -> None:
        """I segnalibri della campagna (`LinkTarget`) e, fra questi, quello del posto in cui si è."""
        self._bookmarks.set_bookmarks(targets, current)
        self._update_context_visibility()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._apply_collapsed()

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def _apply_collapsed(self) -> None:
        self.setFixedWidth(theme.SIDEBAR_WIDTH_COLLAPSED if self._collapsed else theme.SIDEBAR_WIDTH)
        for button in self._buttons.values():
            button.set_collapsed(self._collapsed)
        for label in self._group_labels:
            label.setVisible(not self._collapsed)
        for divider in self._group_dividers:
            divider.setVisible(self._collapsed)
        self._update_context_visibility()

    def _update_context_visibility(self) -> None:
        show = self._has_context and not self._collapsed
        self._context_divider.setVisible(show)
        self._context_stack.setVisible(show)
        marks = self._bookmarks.has_bookmarks and not self._collapsed
        self._bookmarks_divider.setVisible(marks)
        self._bookmarks.setVisible(marks)
