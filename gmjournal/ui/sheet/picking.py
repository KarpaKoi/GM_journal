"""Scegliere un elemento da collegare: il selettore sotto un pulsante, con la possibilità di crearne uno nuovo."""

from typing import Callable

from PySide6.QtWidgets import QWidget

from ...data import links
from ...data.models import LinkTarget
from ...data.repository import Repository
from ...elements import ElementKind
from ..link_sources import LinkSources
from ..widgets.element_picker import ElementPicker, PickerRow


def picker_rows(repo: Repository, kind: ElementKind, linked: set[int], skip: int | None) -> list[PickerRow]:
    """Gli elementi di un tipo da proporre nel selettore (tranne `skip`); quelli in `linked` compaiono come «Già collegato»."""
    categories = {category.id: category.name for category in repo.categories(kind.key)}
    return [PickerRow(e.id, e.name, categories[e.category_id], e.id in linked)
            for e in repo.elements(kind.key) if e.id != skip]


def choose_element(owner: QWidget, repo: Repository, sources: LinkSources, kind: ElementKind, linked: set[int],
                   skip: int | None, anchor: QWidget, on_chosen: Callable[[int], None]) -> None:
    """Apre il selettore sotto `anchor`; l'elemento scelto (anche uno nuovo, se si preme «Crea…») va a `on_chosen(ID)`."""
    def create(name: str) -> None:
        target = sources.create(LinkTarget(links.CREATE + kind.key, 0, name, ""))
        if target is not None:
            on_chosen(target.id)

    picker = ElementPicker(owner, kind, picker_rows(repo, kind, linked, skip), width=max(340, anchor.width()))
    picker.chosen.connect(on_chosen)
    picker.create_requested.connect(create)
    picker.popup_below(anchor)
