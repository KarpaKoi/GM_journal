"""Le immagini scritte nei testi: come sono salvate e come si riconoscono (come `links.py` per i collegamenti).

Nel testo salvato un'immagine è `<img src="immagini/nome.png" width="…" height="…">`: punta al file con il suo percorso.
"""

import html
import re
from pathlib import Path, PurePosixPath

IMAGES_DIRNAME = "immagini"      # la cartella delle immagini dentro quella di ogni campagna
_IMG = re.compile(r'<img src="([^"]*)"[^>]*>')
# Per ripulire testi che arrivano da fuori si è più larghi: l'editor accetta ogni forma di `<img …>` (attributi in qualunque ordine, apici singoli).
_IMG_TAG = re.compile(r"""<img\b(?:[^>"']|"[^"]*"|'[^']*')*>""", re.I)
_SRC = re.compile(r"""(?<![\w-])src\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", re.I)


def safe_media_path(base: Path, relative: str | None) -> Path | None:
    """Il file `relative` (un percorso scritto nel database o in un testo, come «immagini/mappa.png») dentro la cartella `base`
    della campagna; None se il percorso non è fidato. Un file della campagna si apre solo passando da qui: i percorsi
    arrivano da dati che possono venire da altri (un backup, una campagna ricevuta) e non devono portare fuori dalla cartella.

    Si rifiuta tutto ciò che non è un percorso relativo semplice dentro `immagini/`: vuoto, assoluto, con unità (`C:`),
    di rete (UNC), con backslash o con componenti `..`; poi si controlla anche il risultato finale (`resolve`), così
    nemmeno un collegamento simbolico può far uscire dalla cartella."""
    if not relative or "\\" in relative or ":" in relative or "\0" in relative:
        return None
    path = PurePosixPath(relative)
    if path.is_absolute() or len(path.parts) < 2 or path.parts[0] != IMAGES_DIRNAME or ".." in path.parts:
        return None
    try:
        file = (base / path).resolve()
        return file if file.is_relative_to(base.resolve() / IMAGES_DIRNAME) else None
    except (OSError, ValueError):
        return None


def source_attr(path: str) -> str:
    """`src="…"` com'è scritto nel testo salvato per questo file."""
    return f'src="{html.escape(path, quote=True)}"'


def extract(content: str) -> list[str]:
    """I file usati nel testo, senza ripetizioni."""
    return list(dict.fromkeys(html.unescape(src) for src in _IMG.findall(content)))


def remove(content: str, path: str) -> str:
    """Il testo senza le immagini che puntano a questo file (che non esiste più)."""
    return _IMG.sub(lambda m: "" if html.unescape(m.group(1)) == path else m.group(0), content)


def drop_unsafe(content: str, base: Path) -> str:
    """Il testo senza le immagini il cui percorso non è valido per la campagna in `base` (vedi `safe_media_path`)."""
    def keep(match: re.Match) -> str:
        src = _SRC.search(match.group(0))
        if src is None or safe_media_path(base, html.unescape(next(group for group in src.groups() if group is not None))):
            return match.group(0)
        return ""
    return _IMG_TAG.sub(keep, content)
