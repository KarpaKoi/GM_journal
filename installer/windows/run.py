"""Avvio di GM Journal dal programma installato (lo lancia GMJournal.exe).

Senza finestra del terminale un errore all'avvio non si vedrebbe: qui lo si intercetta, lo si scrive in
«errore.log» (cartella %LOCALAPPDATA%\\GM Journal; nella versione portatile accanto a GMJournal.exe) e lo si mostra in una
finestra di messaggio. Anche un arresto improvviso di Qt lascia la sua traccia nello stesso file. A programma chiuso senza
problemi il file non resta.

Gli errori che il programma non intercetta (in uno slot di Qt, in un thread) non lo fermano ma, senza terminale, sparirebbero:
`sys.excepthook` e `threading.excepthook` li scrivono nello stesso file e avvisano con una finestra, una sola per sessione.
"""

import faulthandler
import logging
import os
import runpy
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import TextIO

APP_DIR = Path(__file__).resolve().parent
LOG_MAX = 200_000      # oltre questa misura il vecchio file si butta

_log: TextIO | None = None     # errore.log aperto (None se non si è potuto aprire, o a programma chiuso)
_log_file: Path | None = None
_warned = False                # la finestra di avviso per gli errori non fatali si mostra una volta sola per sessione


def _log_path() -> Path:
    if (APP_DIR.parent / "portable.txt").is_file():     # versione portatile: niente fuori dalla sua cartella
        return APP_DIR.parent / "errore.log"
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "GM Journal" / "errore.log"


def _message(text: str, icon: int = 0x10) -> None:
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, text, "GM Journal", icon)    # 0x10 = icona di errore, 0x30 = di avviso


def _report(exc_type, exc, tb) -> None:
    """Un errore che il programma non ha intercettato: lo scrive in errore.log e, la prima volta, avvisa. Non ferma il programma.
    Qualunque problema qui dentro (log non scrivibile, finestra non mostrabile) si ignora: segnalare un errore non ne deve creare un altro."""
    global _warned
    try:
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        saved = False
        if _log is not None:
            try:
                _log.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Errore non gestito\n{details}")
                _log.flush()
                saved = True
            except (OSError, ValueError):            # disco pieno o file chiuso: l'avviso si mostra lo stesso
                pass
        if not _warned:
            _warned = True                           # prima della finestra: gli errori che nascono mentre è aperta non ne aprono un'altra
            where = f"I dettagli sono in:\n{_log_file}" if saved else "Non sono riuscito a salvare i dettagli."
            _message("GM Journal ha avuto un problema, ma resta aperto.\n\n" + details.strip().splitlines()[-1]
                     + "\n\nSe qualcosa non funziona, salva il lavoro e riavvia il programma. Questo avviso compare una sola volta.\n\n"
                     + where, 0x30)
    except Exception:
        pass


def _excepthook(exc_type, exc, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
    else:
        _report(exc_type, exc, tb)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is not SystemExit:          # come Python: uscire da un thread non è un errore
        _report(args.exc_type, args.exc_value, args.exc_traceback)


def main() -> None:
    for name in ("stdout", "stderr"):                  # senza terminale Python li lascia vuoti
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))

    global _log, _log_file
    path = _log_path()
    log = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > LOG_MAX:
            path.unlink()
        log = open(path, "a", encoding="utf-8")
        faulthandler.enable(log)
        _log, _log_file = log, path
        logging.basicConfig(stream=log, level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")   # anche logging.warning/exception
    except OSError:
        pass                                           # niente log: il programma parte lo stesso
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook

    try:
        runpy.run_path(str(APP_DIR / "main.py"), run_name="__main__")
    except SystemExit:
        raise
    except BaseException:
        details = traceback.format_exc()
        if log:
            log.write(details)
            log.flush()
        _message("GM Journal si è fermato per un errore.\n\n"
                 + details.strip().splitlines()[-1] + f"\n\nI dettagli sono in:\n{path}")
        sys.exit(1)
    finally:
        if log:
            _log = None
            faulthandler.disable()
            log.close()
            if path.stat().st_size == 0:
                path.unlink()


if __name__ == "__main__":
    main()
