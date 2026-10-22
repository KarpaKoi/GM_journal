"""Il testo semplice di una pagina salvata (senza i tag): serve a contare le parole e a mostrare le prime righe."""

import re
from html import unescape

# I tag che chiudono una riga o una cella: fra due paragrafi, voci o celle ci vuole uno spazio, altrimenti le parole si incollano.
_BREAKS = re.compile(r"</?(?:p|h[1-3]|li|ul|ol|div|table|tr|td|th)\b[^>]*>|<br\s*/?>", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]*>")
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")       # «dell'Ordine» è una parola sola


def plain_text(content: str) -> str:
    """Il testo di `content` su una riga sola, con le parole separate da un solo spazio."""
    return " ".join(unescape(_TAGS.sub("", _BREAKS.sub(" ", content))).split())


def count_words(content: str) -> int:
    return len(_WORD.findall(plain_text(content)))
