"""Da dove un testo prende ciò a cui collegarsi: i bersagli che si possono citare e la creazione di un elemento nuovo."""

from typing import Callable

from PySide6.QtWidgets import QWidget

from .. import theme
from ..data import links, plain
from ..data.db import DatabaseError
from ..data.models import LinkTarget
from ..data.repository import Repository, numbered_pages
from ..data.search import rank
from ..elements import KINDS
from ..encounters import COMBAT, KIND_ICONS, KIND_LABELS
from ..formatting import initials
from .kinds import kind_icon
from .editor.encounter_box import EncounterCard, EncounterSource
from .popups.element import create_element
from .widgets.difficulty_panel import assessment_of
from .widgets.encounter_page import creatures_text, players_text
from .widgets.link_preview import LinkPreviewData

_NOT_ELEMENTS = {links.PAGE: ("scrittura", "la pagina"), links.MAP: ("mappe", "la mappa"), links.GRAPH: ("grafi", "il grafo")}   # (sezione, «aprire …»)


class LinkSources:
    """Le funzioni che un editor o un campo di testo chiede per collegare: `targets`, `create` e `preview`.

    `current` dà ciò che il testo non deve citare (la pagina o la scheda in cui si sta scrivendo) come (tipo, ID), o None.
    `parent` è la finestra su cui si apre il popup «Nuovo …».
    """

    def __init__(self, parent: QWidget, repo: Repository, current: Callable[[], tuple[str, int] | None]):
        self._parent, self._repo, self._current = parent, repo, current

    def targets(self, query: str, limit: int) -> list[LinkTarget]:
        """Ciò a cui si può collegare (tutto tranne il testo stesso), poi le righe «Crea…» per ogni tipo."""
        found = self._repo.link_targets(query, self._current(), limit)
        if query.strip():
            found += [LinkTarget(links.CREATE + kind, 0, query.strip(), "") for kind in links.ELEMENT_KINDS]
        return found

    def preview(self, kind: str, target_id: int) -> LinkPreviewData | None:
        """Cosa mostra la finestrella su un collegamento: l'elemento (categoria, ruolo, in breve, in quante pagine compare), o la
        pagina (le prime righe), la mappa o il grafo (cosa sono). None se il bersaglio non esiste più."""
        target = self._repo.link_target(kind, target_id)
        if target is None:
            return None
        if kind not in KINDS:
            section, open_what = _NOT_ELEMENTS[kind]
            subtitle, brief = target.detail, ""
            if kind == links.PAGE:
                subtitle, brief = self._page_path(target_id), plain.plain_text(self._repo.page(target_id).content)
            return LinkPreviewData(target.name, theme.SECTION_COLORS[section], f"Ctrl+clic per aprire {open_what}", subtitle, brief,
                                   icon=kind_icon(kind))
        try:
            element = self._repo.element(target_id)
            category = self._repo.category(element.category_id)
        except DatabaseError:
            return None
        pages = sum(1 for cited in self._repo.cited_by(kind, target_id) if cited.kind == links.PAGE)
        return LinkPreviewData(element.name, theme.category_color(category.color), "Ctrl+clic per aprire la scheda", element.role, element.brief,
                               initials=initials(element.name), image=self._repo.media_file(element.image),
                               chip=category.name, cited=pages)

    def encounters(self) -> EncounterSource:
        """Ciò che serve al box «Incontro» di un testo: la ricerca per nome e la scheda di ogni incontro."""
        return EncounterSource(self._encounter_targets, self._encounter_card)

    def _encounter_targets(self, query: str, limit: int) -> list[LinkTarget]:
        found = [(rank(query, row.name), row) for row in self._repo.encounters()]
        found = sorted(((score, row) for score, row in found if score is not None), key=lambda item: item[0])
        return [LinkTarget(links.ENCOUNTER, row.id, row.name, KIND_LABELS[row.kind]) for _, row in found][:limit]

    def _encounter_card(self, encounter_id: int) -> EncounterCard | None:
        """La scheda di un incontro per il testo: tipo, riepilogo, difficoltà ed elenco delle creature. None se non esiste più."""
        try:
            row = self._repo.encounter(encounter_id)
        except DatabaseError:
            return None
        creatures = {creature.id: creature for creature in self._repo.creatures()}
        difficulty = assessment_of(row, {creature.id: creature.challenge for creature in creatures.values()}).difficulty if row.kind == COMBAT else ""
        summary = " · ".join(part for part in (KIND_LABELS[row.kind], players_text(row) if row.kind == COMBAT else "", creatures_text(row)) if part)
        return EncounterCard(row.name, KIND_ICONS[row.kind], summary, difficulty or None,
                             tuple((creatures[slot.creature_id].name, slot.quantity) for slot in row.creatures if slot.creature_id in creatures))

    def _page_path(self, page_id: int) -> str:
        """Dove sta una pagina nell'indice: «1. La Locanda» per un capitolo, «1. La Locanda › 1.2 Lo straniero» per un sottocapitolo."""
        numbered = {node.id: (node, number) for node, number in numbered_pages(self._repo.pages())}
        node, number = numbered[page_id]
        if node.parent_id is None:
            return f"{number}. {node.title}"
        chapter, chapter_number = numbered[node.parent_id]
        return f"{chapter_number}. {chapter.title} › {number} {node.title}"

    def create(self, request: LinkTarget) -> LinkTarget | None:
        """Una riga «Crea…» è stata scelta: apre il popup del nuovo elemento (con il nome già scritto) e restituisce il bersaglio creato."""
        kind = KINDS[request.kind.removeprefix(links.CREATE)]
        element_id = create_element(self._parent, self._repo, kind, request.name)
        if element_id is None:
            return None
        element = self._repo.element(element_id)
        category = next(c.name for c in self._repo.categories(kind.key) if c.id == element.category_id)
        return LinkTarget(kind.key, element_id, element.name, category)
