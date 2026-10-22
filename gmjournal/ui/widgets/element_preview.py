"""Anteprima di un elemento (personaggio, luogo o organizzazione), con «Apri scheda» e «Modifica»: sta nel pannello destro
degli elenchi e di Scrittura."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import Category, Element, LinkTarget
from ...elements import KINDS
from ...formatting import initials
from .element_thumb import ElementThumb
from .filter_chip import FilterChip
from .group_label import group_label
from .links_panel import LinkSection


class ElementPreview(QScrollArea):
    edit_requested = Signal()
    sheet_requested = Signal()
    cited_chosen = Signal(object)     # LinkTarget della pagina o dell'elemento scelto in «Citato in»

    def __init__(self, hint: str = ""):
        """`hint`: la frase che si vede finché non c'è un elemento da mostrare."""
        super().__init__()
        self._hint = QLabel(hint)
        self._hint.setObjectName("Muted")
        self._hint.setWordWrap(True)

        self._thumb = ElementThumb(280, 12)
        self._name = QLabel()
        self._name.setFont(theme.serif_font(28, 500, -0.01))
        self._name.setWordWrap(True)
        self._badge_slot = QVBoxLayout()
        self._badge: FilterChip | None = None
        self._open_sheet = QPushButton(" Apri scheda")
        self._open_sheet.setIcon(icons.icon("book-open", theme.BG))
        self._open_sheet.setIconSize(QSize(16, 16))
        self._open_sheet.setCursor(Qt.PointingHandCursor)
        self._open_sheet.clicked.connect(self.sheet_requested)
        edit = QPushButton(" Modifica")
        edit.setIcon(icons.icon("pencil"))
        edit.setIconSize(QSize(16, 16))
        edit.setCursor(Qt.PointingHandCursor)
        edit.clicked.connect(self.edit_requested)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self._open_sheet, 1)
        buttons.addWidget(edit)
        self._role_title, self._role = group_label("Ruolo"), self._body()
        self._brief_title, self._brief = group_label("In breve"), self._body()
        self._cited = LinkSection("Citato in", "Nessuna pagina o scheda lo cita.", self.cited_chosen.emit)

        self._details = QWidget()
        layout = QVBoxLayout(self._details)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._thumb)
        layout.addSpacing(16)
        layout.addWidget(self._name)
        layout.addSpacing(8)
        layout.addLayout(self._badge_slot)
        layout.addSpacing(16)
        layout.addLayout(buttons)
        layout.addSpacing(20)
        for widget in (self._role_title, self._role, self._brief_title, self._brief):
            layout.addWidget(widget)
        layout.addSpacing(12)
        layout.addWidget(self._cited)

        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addWidget(self._hint)
        outer.addWidget(self._details)
        outer.addStretch(1)          # lo spazio che avanza va in fondo; con setAlignment un testo lungo non avrebbe l'altezza giusta e si sovrapporrebbe
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(content)
        content.setAutoFillBackground(False)     # lo sfondo è già quello del pannello
        self.show_element(None, None, None, [])

    @staticmethod
    def _body() -> QLabel:
        label = QLabel()
        label.setWordWrap(True)
        label.setFont(theme.ui_font(14))
        label.setStyleSheet(f"color: {theme.TEXT_SOFT};")
        label.setContentsMargins(0, 4, 0, 16)     # niente padding QSS: sposterebbe il testo di qualche pixel
        return label

    def clear(self) -> None:
        """Pannello vuoto: non c'è nessun elemento da scegliere, quindi neppure il suggerimento."""
        self._hint.hide()
        self._details.hide()

    def show_element(self, element: Element | None, category: Category | None, image: Path | None,
                     cited_in: list[LinkTarget]) -> None:
        """Mostra l'elemento (con la sua categoria, l'immagine e le pagine e schede che lo citano); None = nessuna scelta."""
        self._hint.setVisible(element is None)
        self._details.setVisible(element is not None)
        if element is None or category is None:
            return
        color = theme.category_color(category.color)
        self._open_sheet.setStyleSheet(theme.solid_button_style(KINDS[element.kind].color))
        self._thumb.set_element(initials(element.name), color, image)
        self._name.setText(element.name)
        if self._badge is not None:
            self._badge.deleteLater()
        self._badge = FilterChip(category.name, color, height=26, font_px=12)
        self._badge.setChecked(True)
        self._badge.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._badge_slot.addWidget(self._badge, alignment=Qt.AlignLeft)
        for title, label, text in ((self._role_title, self._role, element.role), (self._brief_title, self._brief, element.brief)):
            title.setVisible(bool(text))
            label.setVisible(bool(text))
            label.setText(text)
        self._cited.set_targets(cited_in)
