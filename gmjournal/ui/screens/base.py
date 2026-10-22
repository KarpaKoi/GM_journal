"""Classe base di ogni schermata principale."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class Screen(QWidget):
    """Una schermata. Può offrire un pannello destro e una lista per la barra sinistra.

    La finestra chiama i primi due metodi una sola volta, quando crea la schermata.
    """

    navigated = Signal(object)   # l'utente ha scelto un altro elemento nella schermata (es. un'altra pagina)
    open_requested = Signal(str, object)   # (chiave della schermata, elemento): va aperto in un'altra schermata
    trail_changed = Signal()     # il percorso della schermata (vedi `trail`) è cambiato senza che l'utente abbia cambiato posto (es. una pagina rinominata)
    panel_requested = Signal()   # la schermata ha qualcosa da mostrare nel pannello destro: se è chiuso, la finestra lo apre

    def create_side_panel(self) -> QWidget | None:
        """Il pannello destro della schermata, o None se non ne ha."""
        return None

    def panel_visible(self) -> bool:
        """Se il pannello destro ha senso nello stato attuale della schermata (es. non quando si vede una scheda a tutta larghezza)."""
        return True

    def create_sidebar_list(self) -> QWidget | None:
        """La lista sotto le voci della barra sinistra (capitoli, mappe, grafi…), o None."""
        return None

    def current_target(self) -> object | None:
        """L'elemento mostrato (es. l'ID della pagina), per la cronologia; None se la schermata non ne ha."""
        return None

    def bookmark_target(self) -> tuple[str, int] | None:
        """(tipo, ID) di ciò che la schermata mostra, se si può segnare con un segnalibro (una pagina, un elemento, una mappa, un grafo
        o un incontro: i tipi di `data/links.py`); None se non c'è nulla da segnare."""
        return None

    def trail(self) -> list[tuple[str, object]]:
        """I tratti del percorso in alto dopo il nome della schermata, ognuno con il testo e l'elemento da mostrare se lo si preme
        (es. i capitoli che contengono la pagina aperta). L'ultimo è il posto attuale."""
        return []

    def show_target(self, target: object) -> None:
        """Mostra l'elemento `target` (tornando indietro o avanti nella cronologia). Se non esiste più, non fa nulla."""

    def flush(self) -> bool:
        """Salva subito ciò che è ancora in sospeso (la finestra lo chiama prima di chiudere la campagna).
        Restituisce False se non ci riesce."""
        return True
