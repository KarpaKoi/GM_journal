"""Popup per creare o modificare un capitolo (o sottocapitolo) di Scrittura."""

from PySide6.QtWidgets import QLineEdit, QWidget

from ... import theme
from ...data.models import PageNode
from ...data.repository import TITLE_MAX
from ..widgets.hold_button import HoldButton
from ..widgets.select_field import SelectField
from .base import DELETE, PopupDialog, labeled, note


class PagePopup(PopupDialog):
    """Senza `page` crea un capitolo; con `page` lo modifica.

    `chapters` sono i capitoli principali dove si può mettere la pagina, come (ID, «1 · Titolo»).
    `parent_id` è il capitolo scelto in partenza; `subchapters` quanti sottocapitoli ha la pagina che si modifica.
    """

    def __init__(self, parent: QWidget, chapters: list[tuple[int, str]], page: PageNode | None = None,
                 parent_id: int | None = None, subchapters: int = 0):
        edit = page is not None
        super().__init__(
            parent,
            "Modifica capitolo" if edit else "Nuovo capitolo",
            "Cambia il titolo o sposta la pagina in un altro capitolo." if edit
            else "Dai un titolo alla pagina. Se la metti dentro un capitolo diventa un sottocapitolo.",
            "Salva modifiche" if edit else "Crea capitolo",
            width=620,
        )
        self._title = QLineEdit(page.title if edit else "")
        self._title.setFixedHeight(40)
        self._title.setMaxLength(TITLE_MAX)
        self._title.setFont(theme.ui_font(15))
        self._title.setPlaceholderText("Titolo del capitolo")

        self._container = SelectField()
        options = [(None, "Nessuno (capitolo principale)")] + [c for c in chapters if not edit or c[0] != page.id]
        self._container.set_options(options, parent_id if parent_id in dict(options) else None)
        self._container.setEnabled(not subchapters)

        self.body.setSpacing(18)
        self.body.addLayout(labeled("Titolo", self._title))
        self.body.addLayout(labeled("Dentro a", self._container))
        if subchapters:
            self.body.addWidget(note("Un capitolo che contiene sottocapitoli non può stare dentro un altro capitolo."))

        if edit:
            delete = HoldButton("Tieni premuto per eliminare il capitolo")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)
            warning = "Nelle altre pagine i collegamenti verso questa restano come semplice testo."
            if subchapters:
                warning = f"Eliminandolo si eliminano anche i suoi {subchapters} sottocapitoli. " + warning
            self.body.addWidget(note(warning))

        self._title.textChanged.connect(lambda: self.set_primary_enabled(bool(self._title.text().strip())))
        self.set_primary_enabled(bool(self._title.text().strip()))
        self._title.setFocus()
        self._title.selectAll()

    def title(self) -> str:
        return self._title.text().strip()

    def parent_id(self) -> int | None:
        return self._container.value()
