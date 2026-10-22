"""La barra degli strumenti dell'editor: tipo di paragrafo, stili, evidenziatore, elenchi, dimensione, link, immagine,
tabella, box e, a destra, il controllo ortografico («Italiano») e «Cerca nella pagina».

Non contiene regole: ogni pulsante chiama un comando di `commands.py` e mostra lo stato del punto
in cui si trova il cursore.
"""

from typing import Callable

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from ... import icons, theme
from ..widgets.color_swatch import ColorPicker
from ..widgets.group_label import group_label
from ..widgets.menu import PopupMenu
from ..widgets.segment_switch import SegmentSwitch
from ..widgets.strip import HorizontalStrip
from . import commands, styles
from .editor import RichEditor
from .table_ui import TableSizePopup

_HEIGHT = 52
_BUTTON = 32
_HEADINGS = ((0, "Paragrafo", "pilcrow"), (1, "Titolo 1", "heading-1"), (2, "Titolo 2", "heading-2"), (3, "Titolo 3", "heading-3"))


class _IconButton(QToolButton):
    """Pulsante a icona; quando è attivo (grassetto acceso, elenco in uso…) si colora."""

    def __init__(self, icon_name: str, tooltip: str):
        super().__init__()
        self.setObjectName("FormatButton")
        self._normal = icons.icon(icon_name, theme.TEXT_SOFT)
        self._active = icons.icon(icon_name, theme.ACCENT)
        self.setIcon(self._normal)
        self.setIconSize(QSize(18, 18))
        self.setFixedSize(_BUTTON, _BUTTON)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)

    def show_active(self, active: bool) -> None:
        self.setChecked(active)
        self.setIcon(self._active if active else self._normal)


class _LanguageButton(QToolButton):
    """«Italiano»: accende e spegne il controllo ortografico (acceso è azzurro)."""

    def __init__(self, action: Callable[[], None]):
        super().__init__()
        self.setObjectName("LanguageButton")
        self._normal = icons.icon("spell-check", theme.TEXT_SOFT)
        self._active = icons.icon("spell-check", theme.ACCENT)
        self.setText("Italiano")
        self.setIcon(self._normal)
        self.setIconSize(QSize(17, 17))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setFont(theme.ui_font(13, 500))
        self.setFixedHeight(_BUTTON)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda _=False: action())

    def show_state(self, on: bool, available: bool) -> None:
        self.setEnabled(available)
        self.setChecked(on)
        self.setIcon(self._active if on else self._normal)
        self.setToolTip("Controllo ortografico: italiano" if available else "Il dizionario italiano non è disponibile")


class _Dropdown(QAbstractButton):
    """Pulsante con etichetta e freccia che apre un menu (tipo di paragrafo, box)."""

    def __init__(self, icon_name: str | None, text: str, width: int):
        super().__init__()
        self.setObjectName("Dropdown")
        self._icon = icons.icon(icon_name, theme.TEXT_SOFT) if icon_name else None
        self._chevron = icons.icon("chevron-down", theme.MUTED)
        self.setText(text)
        self.setFixedSize(width, _BUTTON)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.HOVER if self.underMouse() and self.isEnabled() else theme.CONTROL_BG))
        painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)
        left = 10
        if self._icon is not None:
            self._icon.paint(painter, QRect(left, 8, 16, 16))
            left += 24
        painter.setFont(theme.ui_font(13, 500))
        painter.setPen(QColor(theme.TEXT if self.isEnabled() else theme.DISABLED))
        room = self.width() - left - 28
        text = QFontMetrics(painter.font()).elidedText(self.text(), Qt.ElideRight, room)
        painter.drawText(QRect(left, 0, room, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
        self._chevron.paint(painter, QRect(self.width() - 24, 8, 16, 16))


class _HighlightButton(_IconButton):
    """Evidenzia con l'ultimo colore usato: la barretta sotto l'icona mostra quale."""

    def __init__(self, color: Callable[[], str]):
        super().__init__("highlighter", "Evidenzia con l'ultimo colore usato")
        self._color = color
        self.setIconSize(QSize(16, 16))
        self.setProperty("split", "left")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.HIGHLIGHT_COLORS[self._color()][1] if self.isEnabled() else theme.DISABLED))
        painter.drawRoundedRect(QRectF(8, self.height() - 7, self.width() - 16, 3), 1.5, 1.5)


class _HighlightPopup(PopupMenu):
    """I colori dell'evidenziatore (quello in uso è segnato) e «Togli l'evidenziatore»."""

    def __init__(self, parent: QWidget, current: str, on_choose: Callable[[str], None]):
        super().__init__(parent, width=252)
        title = group_label("Evidenzia con")
        title.setContentsMargins(2, 0, 0, 8)
        colors = ColorPicker(colors=theme.HIGHLIGHT_COLORS, fallback=styles.HIGHLIGHTS[0])
        colors.set_value(current)
        # Come le voci del menu: la scelta parte dopo la chiusura.
        colors.chosen.connect(lambda key: (self.close(), QTimer.singleShot(0, lambda: on_choose(key))))
        name = QLabel(theme.HIGHLIGHT_COLORS[current][0])
        name.setObjectName("Muted")
        name.setFont(theme.ui_font(13))
        name.setContentsMargins(2, 10, 0, 0)
        for widget in (title, colors, name):
            self._items.addWidget(widget)
        self._items.setContentsMargins(10, 10, 10, 6)
        self.add_separator()
        self.add_item("x", "Togli l'evidenziatore", lambda: on_choose(""))


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("ToolbarDivider")
    line.setFixedSize(1, 20)
    return line


class FormatToolbar(QFrame):
    _last_highlight = styles.HIGHLIGHTS[0]     # l'ultimo colore dell'evidenziatore: vale per tutti gli editor finché il programma è aperto

    def __init__(self, editor: RichEditor):
        super().__init__()
        self.setObjectName("FormatToolbar")
        self.setFixedHeight(_HEIGHT)
        self._editor = editor

        self._block = _Dropdown(None, "Paragrafo", 132)
        self._block.clicked.connect(self._open_block_menu)
        self._bold = self._style_button("bold", "Grassetto (Ctrl+B)", "bold")
        self._italic = self._style_button("italic", "Corsivo (Ctrl+I)", "italic")
        self._underline = self._style_button("underline", "Sottolineato (Ctrl+U)", "underline")
        self._highlight = _HighlightButton(lambda: FormatToolbar._last_highlight)
        self._highlight.clicked.connect(lambda: self._apply_highlight(FormatToolbar._last_highlight))
        self._highlight_menu = self._button("chevron-down", "Scegli il colore dell'evidenziatore", self._open_highlight_menu)
        self._highlight_menu.setFixedSize(20, _BUTTON)
        self._highlight_menu.setIconSize(QSize(12, 12))
        self._highlight_menu.setProperty("split", "right")
        highlighter = QWidget()
        pair = QHBoxLayout(highlighter)
        pair.setContentsMargins(2, 0, 0, 0)
        pair.setSpacing(0)
        pair.addWidget(self._highlight)
        pair.addWidget(self._highlight_menu)
        self._bullets = self._button("list", "Elenco puntato", lambda: self._run(commands.toggle_list, "ul"))
        self._numbers = self._button("list-ordered", "Elenco numerato", lambda: self._run(commands.toggle_list, "ol"))
        self._sizes = SegmentSwitch([(size, "A", px) for size, px in zip(styles.SIZES, (11, 14, 17))],
                                    lambda size: self._run(commands.set_size, size))
        self._sizes.setToolTip("Dimensione del testo: piccolo, medio, grande")
        self._link = self._button("link", "Collega a… (Ctrl+L)", editor.choose_link)
        self._image = self._button("image", "Inserisci un'immagine", editor.choose_image)
        self._table = self._button("table", "Inserisci una tabella", self._open_table_popup)
        self._box = _Dropdown("box", "Box", 92)
        self._box.setToolTip("Metti il testo in un box")
        self._box.clicked.connect(self._open_box_menu)
        spell, find = editor.spell, editor.find
        self._language = _LanguageButton(self._toggle_spelling) if spell is not None else None
        self._find = self._button("search", "Cerca nella pagina", find.toggle) if find is not None else None

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(6)
        layout.addStretch()
        for widget in (self._block, _divider(), self._bold, self._italic, self._underline, highlighter, _divider(),
                       self._bullets, self._numbers, _divider(), self._sizes, _divider(),
                       self._link, self._image, self._table, _divider(), self._box):
            layout.addWidget(widget)
            layout.setAlignment(widget, Qt.AlignVCenter)
        layout.addStretch()
        for widget in (self._language, self._find):
            if widget is not None:
                layout.addWidget(widget)
                layout.setAlignment(widget, Qt.AlignVCenter)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(HorizontalStrip(row))

        editor.state_changed.connect(self.refresh)
        if spell is not None:
            spell.changed.connect(self.refresh)
        if find is not None:
            find.toggled.connect(self.refresh)
        self.refresh()

    def _button(self, icon_name: str, tooltip: str, action: Callable[[], None]) -> _IconButton:
        button = _IconButton(icon_name, tooltip)
        button.clicked.connect(action)
        return button

    def _style_button(self, icon_name: str, tooltip: str, style: str) -> _IconButton:
        return self._button(icon_name, tooltip, lambda: self._run(commands.toggle_style, style))

    def _run(self, command: Callable, *args) -> None:
        command(self._editor, *args)
        self._editor.setFocus()

    def refresh(self) -> None:
        """Mostra la formattazione del punto in cui si trova il cursore."""
        state = commands.state_of(self._editor)
        in_box, in_table = bool(state.box), state.in_table
        label = next(name for level, name, _ in _HEADINGS if level == state.heading)
        self._block.setText(label)
        self._block.setEnabled(not in_box and not in_table)
        self._bold.show_active(state.bold)
        self._italic.show_active(state.italic)
        self._underline.show_active(state.underline)
        self._highlight.show_active(bool(state.highlight))
        self._highlight_menu.show_active(False)
        self._bullets.show_active(state.list_kind == "ul")
        self._numbers.show_active(state.list_kind == "ol")
        self._link.show_active(state.link)
        self._table.show_active(in_table)
        self._sizes.set_value(state.size)
        self._sizes.setEnabled(state.heading == 0 and not in_table)
        for widget in (self._bullets, self._numbers, self._image, self._box):     # nelle celle solo testo «in riga»
            widget.setEnabled(not in_table)
        self._table.setEnabled(not in_box and not in_table)
        if self._language is not None:
            spell = self._editor.spell
            self._language.show_state(spell.enabled and spell.available, spell.available)
        if self._find is not None:
            self._find.show_active(self._editor.find.is_open)
        for widget in (self._block, self._sizes, self._highlight):
            widget.update()

    def _toggle_spelling(self) -> None:
        self._editor.spell.set_enabled(not self._editor.spell.enabled)

    def _open_block_menu(self) -> None:
        current = commands.state_of(self._editor).heading
        menu = PopupMenu(self, width=190)
        for level, name, icon_name in _HEADINGS:
            menu.add_item(icon_name, name, lambda level=level: self._run(commands.set_heading, level), checked=level == current)
        menu.popup_below(self._block)

    def _apply_highlight(self, color: str) -> None:
        """Evidenzia con `color` (lo stesso colore già presente lo toglie); "" toglie l'evidenziatore."""
        if color:
            FormatToolbar._last_highlight = color
        self._run(commands.toggle_highlight, color)
        self.refresh()

    def _open_highlight_menu(self) -> None:
        menu = _HighlightPopup(self, FormatToolbar._last_highlight, self._apply_highlight)
        self._show_open(menu, self._highlight, self._highlight_menu)
        menu.popup_below(self._highlight)

    def _open_table_popup(self) -> None:
        popup = TableSizePopup(self, lambda rows, columns: self._run(commands.insert_table, rows, columns))
        self._show_open(popup, self._table)
        popup.popup_below(self._table)

    def _show_open(self, popup: QWidget, *buttons: _IconButton) -> None:
        """I pulsanti che hanno aperto il riquadro restano evidenziati finché è aperto."""
        for button in buttons:
            button.show_active(True)
        popup.destroyed.connect(self.refresh)

    def _open_box_menu(self) -> None:
        current = commands.state_of(self._editor).box
        menu = PopupMenu(self, width=230)
        for kind in styles.BOX_KINDS:
            menu.add_item(styles.BOX_ICONS[kind], styles.BOX_LABELS[kind],
                          lambda kind=kind: self._run(commands.set_box, kind), checked=kind == current)
        if current:
            menu.add_separator()
            menu.add_item("x", "Togli il box", lambda: self._run(commands.set_box, ""))
        if self._editor.has_encounters:
            menu.add_separator()
            menu.add_item("swords", "Incontro…", self._editor.choose_encounter)
        menu.popup_below(self._box)
