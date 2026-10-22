"""Popup per creare o rinominare un grafo (e, da qui, eliminarlo)."""

from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox, QWidget

from ... import theme
from ...data.db import DatabaseError
from ...data.models import Graph
from ...data.repository import NAME_MAX, Repository
from ..widgets.hold_button import HoldButton
from .base import DELETE, PopupDialog, labeled, note


class GraphPopup(PopupDialog):
    """Senza `graph` ne crea uno nuovo; con `graph` lo rinomina o lo elimina."""

    def __init__(self, parent: QWidget, graph: Graph | None = None):
        edit = graph is not None
        super().__init__(
            parent,
            "Modifica grafo" if edit else "Nuovo grafo",
            "Cambia il nome del grafo." if edit else "Dai un nome alla mappa mentale: i nodi e gli archi li aggiungi dopo.",
            "Salva modifiche" if edit else "Crea grafo",
            width=560,
        )
        self._name = QLineEdit(graph.name if edit else "")
        self._name.setFixedHeight(40)
        self._name.setMaxLength(NAME_MAX)
        self._name.setFont(theme.ui_font(15))
        self._name.setPlaceholderText("Es. Il complotto di corte")
        self.body.setSpacing(18)
        self.body.addLayout(labeled("Nome", self._name))
        if edit:
            delete = HoldButton("Tieni premuto per eliminare il grafo")
            delete.confirmed.connect(lambda: self.done(DELETE))
            self.footer_left.addWidget(delete)
            self.body.addWidget(note("Eliminando il grafo si eliminano i suoi nodi e archi. Le pagine e gli elementi a cui i nodi sono collegati non cambiano."))
        self._name.textChanged.connect(lambda: self.set_primary_enabled(bool(self._name.text().strip())))
        self.set_primary_enabled(bool(self._name.text().strip()))
        self._name.setFocus()
        self._name.selectAll()

    def name(self) -> str:
        return self._name.text().strip()


def create_graph(parent: QWidget, repo: Repository) -> int | None:
    """Apre «Nuovo grafo» e, se si conferma, lo crea. Restituisce il suo ID (None se annullato o fallito)."""
    popup = GraphPopup(parent)
    if popup.exec() != QDialog.Accepted:
        return None
    try:
        return repo.create_graph(popup.name())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
        return None


def edit_graph(parent: QWidget, repo: Repository, graph: Graph) -> int:
    """Apre «Modifica grafo» e fa ciò che si sceglie. Restituisce `DELETE`, `QDialog.Accepted` o `QDialog.Rejected`."""
    popup = GraphPopup(parent, graph)
    result = popup.exec()
    try:
        if result == DELETE:
            repo.delete_graph(graph.id)
        elif result == QDialog.Accepted:
            repo.rename_graph(graph.id, popup.name())
    except DatabaseError as error:
        QMessageBox.warning(parent, "GM Journal", str(error))
    return result
