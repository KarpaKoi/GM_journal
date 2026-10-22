"""Il controllo ortografico: quali parole di un testo non sono nel dizionario italiano.

Il dizionario è quello italiano di LibreOffice (Hunspell, licenza GPL 3, in `assets/dictionaries/it_IT`), letto con la
libreria `spylls` (solo Python, licenza MIT). Si carica una volta sola per tutto il programma (circa 1 secondo e 85 MB),
quindi di solito in un altro thread (`load_dictionary`).

Sono sempre corrette, oltre alle parole del dizionario: i nomi della campagna (personaggi, luoghi, organizzazioni, pagine,
mappe, grafi) e quelle messe da parte con «Ignora questa volta» (finché il programma è aperto). Non si segnalano
i numeri, le lettere sole né le sigle in maiuscolo di una o due lettere. Qui non c'è nulla di grafico: le onde rosse e il
menu sono in `ui/editor/spell_ui.py`.
"""

import logging
import re
import threading
import time
from typing import Callable, Iterable, Sequence

from . import theme

DICTIONARY_FILE = theme.ASSETS_DIR / "dictionaries" / "it_IT" / "it_IT"       # senza estensione (.aff e .dic)
# Una parola: lettere con apostrofi in mezzo («dell'Ordine»), più un apostrofo in fondo («po'»). Cifre e trattini la dividono.
WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*['’]?")
# Gli articoli e le preposizioni che si elidono davanti a un nome: «dell'Aldric» è giusto se «Aldric» è un nome noto.
# «un'» non c'è: «un'Aldric» è giusto o sbagliato secondo il genere del nome, e il programma non lo sa.
ELISIONS = frozenset({"l", "d", "dell", "all", "dall", "nell", "sull"})
NAMES_TTL = 3.0              # ogni quanti secondi si rileggono i nomi della campagna


class _Dictionary:
    """Il dizionario di Hunspell, uno per tutto il programma (le campagne cambiano i nomi, non la lingua)."""
    lock = threading.Lock()
    hunspell = None                 # il `spylls.hunspell.Dictionary`, quando è pronto
    missing = False                 # la libreria o i file non ci sono: il controllo non si può fare
    ignored: set[str] = set()       # le parole messe da parte con «Ignora questa volta» (finché il programma è aperto)
    ignored_version = 0


def load_dictionary() -> bool:
    """Carica il dizionario se non lo è già (lento: circa 1 s). Dice se il controllo ortografico è disponibile."""
    with _Dictionary.lock:
        if _Dictionary.hunspell is None and not _Dictionary.missing:
            try:
                from spylls.hunspell import Dictionary
                _Dictionary.hunspell = Dictionary.from_files(str(DICTIONARY_FILE))
            except (ImportError, OSError):
                _Dictionary.missing = True
            except Exception:                  # dizionario danneggiato o libreria che si rompe: nessun controllo, ma il thread non muore in silenzio
                logging.exception("Impossibile caricare il dizionario italiano")
                _Dictionary.missing = True
        return _Dictionary.hunspell is not None


def is_loaded() -> bool:
    return _Dictionary.hunspell is not None


def is_missing() -> bool:
    return _Dictionary.missing


def _pieces(name: str) -> set[str]:
    """Le parole di un nome, in minuscolo; con un apostrofo anche le due metà («L'arrivo» → «l'arrivo», «l'», «arrivo»)."""
    found = set()
    for match in WORD.finditer(name):
        word = match.group().replace("’", "'").rstrip("'").casefold()
        found.add(word)
        found.update(piece for piece in word.split("'") if piece)
    return found


def unknown_part(token: str) -> str:
    """Ciò che si ignora di una parola sbagliata: con un'elisione davanti a un nome («dell'Aldric») solo il nome."""
    word = token.replace("’", "'").rstrip("'")
    head, apostrophe, tail = word.partition("'")
    return tail if apostrophe and tail and head.casefold() in ELISIONS else word


class Speller:
    """Il controllo dei testi di una campagna: `names` dà i nomi della campagna (sempre corretti)."""

    def __init__(self, names: Callable[[], Iterable[str]]):
        self._names = names
        self._extra = frozenset[str]()
        self._extra_time = float("-inf")
        self._ignored_seen = -1
        self._cache: dict[str, bool] = {}

    @property
    def ready(self) -> bool:
        return _Dictionary.hunspell is not None

    # --- Quali parole sono giuste -------------------------------------------------------------
    def _extra_words(self) -> frozenset[str]:
        """Le parole sempre corrette oltre al dizionario; si rileggono se si è ignorata una parola (o ogni `NAMES_TTL` secondi)."""
        now = time.monotonic()
        if now - self._extra_time > NAMES_TTL or self._ignored_seen != _Dictionary.ignored_version:
            extra = frozenset(set().union(*(_pieces(name) for name in self._names())) | _Dictionary.ignored)
            if extra != self._extra:
                self._extra = extra
                self._cache.clear()
            self._extra_time, self._ignored_seen = now, _Dictionary.ignored_version
        return self._extra

    def is_correct(self, token: str) -> bool:
        """La parola va bene? (Senza dizionario caricato va sempre bene.)"""
        if _Dictionary.hunspell is None:
            return True
        word = token.replace("’", "'")                    # il dizionario conosce solo l'apostrofo dritto
        self._extra_words()
        correct = self._cache.get(word)
        if correct is None:
            correct = self._cache[word] = self._check(word)
        return correct

    def _check(self, word: str) -> bool:
        if len(word) == 1 or (len(word) == 2 and word.isupper()):
            return True
        if word.casefold() in self._extra or _Dictionary.hunspell.lookup(word):
            return True
        if word.endswith("'"):                            # una parola fra apici: «'ciao'»
            return self._check(word[:-1])
        head, apostrophe, tail = word.partition("'")
        return bool(apostrophe) and head.casefold() in ELISIONS and tail.casefold() in self._extra

    def errors(self, text: str, links: Sequence[tuple[int, int]] = ()) -> list[tuple[int, int]]:
        """Gli intervalli (inizio, fine) delle parole di `text` che non vanno bene. Le parole che iniziano dentro un
        collegamento (`links` sono i suoi intervalli nel testo) non si controllano: sono nomi."""
        found = []
        for match in WORD.finditer(text):
            start, end = match.span()
            if end - start < 2 or any(a <= start < b for a, b in links) or self.is_correct(match.group()):
                continue
            found.append((start, end - 1 if text[end - 1] in "'’" else end))
        return found

    def ignore(self, token: str) -> None:
        """«Ignora questa volta»: la parola non si segnala più finché il programma è aperto (in tutti i testi)."""
        _Dictionary.ignored.add(unknown_part(token).casefold())
        _Dictionary.ignored_version += 1
