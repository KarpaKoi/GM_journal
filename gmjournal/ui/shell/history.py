"""Cronologia delle schermate visitate (pulsanti indietro e avanti)."""


class History:
    """Lista di posizioni con un cursore, come la cronologia di un browser."""

    def __init__(self):
        self._entries: list = []
        self._pos = -1

    def push(self, entry) -> None:
        """Registra una nuova posizione; scarta il "futuro" se si era tornati indietro."""
        if self._pos >= 0 and self._entries[self._pos] == entry:
            return
        del self._entries[self._pos + 1:]
        self._entries.append(entry)
        self._pos += 1

    def reset(self, entry) -> None:
        """Dimentica tutto tranne la posizione attuale."""
        self._entries = [entry]
        self._pos = 0

    @property
    def can_back(self) -> bool:
        return self._pos > 0

    @property
    def can_forward(self) -> bool:
        return self._pos < len(self._entries) - 1

    def back(self):
        """Sposta il cursore indietro e restituisce la posizione (None se non si può)."""
        if not self.can_back:
            return None
        self._pos -= 1
        return self._entries[self._pos]

    def forward(self):
        """Sposta il cursore avanti e restituisce la posizione (None se non si può)."""
        if not self.can_forward:
            return None
        self._pos += 1
        return self._entries[self._pos]
