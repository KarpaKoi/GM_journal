#!/usr/bin/env python3
"""Alleggerisce la cartella costruita da PyInstaller (installer/out/dist/GMJournal) togliendo ciò che il programma non usa.

Il programma usa solo QtCore, QtGui, QtWidgets e QtSvg. PyInstaller però raccoglie anche:
  - moduli, librerie e plugin di Qt mai usati (rete, OpenGL per Python, schede grafiche embedded, traduzioni, formati d'immagine rari);
  - librerie di sistema trascinate da quei plugin (GTK, glib, cairo, systemd, kerberos…) che nessuna libreria rimasta richiede più.
Dopo aver tolto i primi, le seconde si trovano da sole: una libreria resta solo se qualcuno, fra i file rimasti, la richiede
(direttamente o tramite un'altra libreria). Uso:  python3 prune.py <cartella GMJournal>
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

QT_MODULES_UNUSED = ("QtNetwork", "QtDBus")                       # moduli Python di PySide6 mai importati dal programma
QT_LIBS_UNUSED = ("Network", "EglFSDeviceIntegration", "EglFsKmsSupport")
QT_PLUGIN_DIRS_UNUSED = ("egldeviceintegrations", "generic", "networkinformation", "tls", "platforminputcontexts")
PLATFORMS_KEPT = {"libqxcb.so", "libqwayland.so", "libqoffscreen.so"}                       # X11, Wayland e la prova senza schermo
IMAGE_FORMATS_KEPT = {"libqjpeg.so", "libqgif.so", "libqsvg.so", "libqwebp.so"}              # il PNG è già nel nucleo di Qt
ALWAYS_KEPT = ("libpython",)                                                                  # la carica l'avviatore con dlopen: nessun file la «richiede»
THEMES_UNUSED = ("libqgtk3.so",)                                                              # tirerebbe dentro GTK e mezzo sistema


def remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def is_elf(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    with path.open("rb") as handle:
        return handle.read(4) == b"\x7fELF"


def needed(path: Path) -> set[str]:
    out = subprocess.run(["readelf", "-d", str(path)], capture_output=True, text=True).stdout
    return set(re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", out))


def prune_qt(qt: Path, python_dir: Path) -> None:
    for name in QT_MODULES_UNUSED:
        for file in python_dir.glob(f"{name}.*"):
            remove(file)
    for name in QT_LIBS_UNUSED:
        for file in (qt / "lib").glob(f"libQt6{name}.so*"):
            remove(file)
    remove(qt / "translations")
    plugins = qt / "plugins"
    for name in QT_PLUGIN_DIRS_UNUSED:
        remove(plugins / name)
    for folder, kept in (("platforms", PLATFORMS_KEPT), ("imageformats", IMAGE_FORMATS_KEPT)):
        for file in (plugins / folder).glob("*.so"):
            if file.name not in kept:
                remove(file)
    for name in THEMES_UNUSED:
        remove(plugins / "platformthemes" / name)


def prune_unreferenced_libs(internal: Path, qt: Path) -> int:
    """Toglie le librerie di cartella `_internal` e `Qt/lib` che nessun file rimasto richiede. Restituisce quante."""
    candidates = {file.name: file for folder in (internal, qt / "lib") for file in folder.glob("*.so*") if is_elf(file)}
    candidate_paths = set(candidates.values())
    roots = [file for file in internal.rglob("*") if file not in candidate_paths and is_elf(file)]
    wanted: set[str] = set()
    pending = [needed(file) for file in roots]
    while pending:
        for name in pending.pop():
            if name not in wanted:
                wanted.add(name)
                if name in candidates:
                    pending.append(needed(candidates[name]))
    removed = [file for name, file in candidates.items() if name not in wanted and not name.startswith(ALWAYS_KEPT)]
    for file in removed:
        remove(file)
    for link in internal.rglob("*"):                                   # i collegamenti rimasti senza più il file a cui puntavano
        if link.is_symlink() and not link.exists():
            link.unlink()
    return len(removed)


def main(folder: Path) -> None:
    internal = folder / "_internal"
    qt = internal / "PySide6" / "Qt"
    before = sum(file.stat().st_size for file in folder.rglob("*") if file.is_file())
    prune_qt(qt, internal / "PySide6")
    count = prune_unreferenced_libs(internal, qt)
    after = sum(file.stat().st_size for file in folder.rglob("*") if file.is_file())
    print(f"Alleggerito: {before / 1e6:.0f} MB -> {after / 1e6:.0f} MB ({count} librerie di sistema inutili tolte)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
