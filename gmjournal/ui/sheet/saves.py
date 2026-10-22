"""Il salvataggio automatico della scheda: ciò che si scrive si salva da solo poco dopo l'ultima modifica."""

from typing import Callable

from PySide6.QtCore import QObject, QTimer

from ...data.db import DatabaseError

AUTOSAVE_MS = 800      # pausa di scrittura dopo la quale si salva


class PendingSaves(QObject):
    """Le modifiche non ancora salvate. Ognuna ha una chiave (il campo, la relazione…) e una funzione che salva
    ciò che c'è scritto *in quel momento*: una nuova modifica della stessa chiave prende il posto della precedente."""

    def __init__(self, parent: QObject, warn: Callable[[str], None]):
        super().__init__(parent)
        self._warn = warn
        self._pending: dict[object, Callable[[], None]] = {}
        self._warned = False       # l'errore è già stato mostrato: non lo ripetiamo a ogni lettera
        self._timer = QTimer(self, singleShot=True, interval=AUTOSAVE_MS)
        self._timer.timeout.connect(self.flush)

    def add(self, key: object, save: Callable[[], None]) -> None:
        self._pending[key] = save
        self._timer.start()

    def flush(self) -> bool:
        """Salva tutto subito. Se non ci riesce lo dice una volta e lascia tutto in sospeso (False)."""
        self._timer.stop()
        try:
            while self._pending:
                key = next(iter(self._pending))
                self._pending[key]()
                del self._pending[key]
        except DatabaseError as error:
            if not self._warned:
                self._warned = True
                self._warn(str(error))
            return False
        self._warned = False
        return True
