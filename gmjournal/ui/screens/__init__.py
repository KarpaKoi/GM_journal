"""Le schermate principali, una per file."""

from ...data.repository import Repository
from ...elements import BY_SECTION
from ...sections import Section
from .base import Screen
from .elements import ElementsScreen
from .encounters import EncountersScreen
from .graphs import GraphsScreen
from .images import ImagesScreen
from .maps import MapsScreen
from .scrittura import ScritturaScreen
from .settings import SettingsScreen


def create_screen(section: Section, repo: Repository) -> Screen:
    """Crea la schermata di una sezione della campagna aperta."""
    if section.key == "scrittura":
        return ScritturaScreen(repo)
    if section.key == "immagini":
        return ImagesScreen(repo)
    if section.key == "mappe":
        return MapsScreen(repo)
    if section.key == "grafi":
        return GraphsScreen(repo)
    if section.key == "incontri":
        return EncountersScreen(repo)
    if section.key == "impostazioni":
        return SettingsScreen(repo)
    return ElementsScreen(repo, BY_SECTION[section.key])
