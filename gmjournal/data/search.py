"""Confronto di testi per le ricerche: ignora maiuscole e accenti («Citta» trova «Città»)."""

import unicodedata


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def rank(query: str, text: str) -> int | None:
    """0 se `text` inizia con `query`, 1 se la contiene, None se non c'entra."""
    needle, haystack = fold(query.strip()), fold(text)
    if haystack.startswith(needle):
        return 0
    return 1 if needle in haystack else None
