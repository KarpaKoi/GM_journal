# Ricetta di PyInstaller, uguale per Windows e Linux: crea la cartella «GMJournal» (programma + Python + Qt + assets).
# Non si lancia a mano: lo fanno build_windows.bat e build_linux.sh.
import sys
from pathlib import Path

root = Path(SPECPATH).parent
windows = sys.platform == "win32"

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    datas=[(str(root / "assets"), "assets")],       # font, icone e icona del programma: theme.ASSETS_DIR li cerca accanto ai moduli
    excludes=["tkinter", "unittest", "pydoc"],
)
exe = EXE(
    PYZ(a.pure),
    a.scripts,
    exclude_binaries=True,
    name="GMJournal",
    console=False,                                  # niente finestra nera del terminale
    icon=str(root / "installer" / "gmjournal.ico") if windows else None,
)
COLLECT(exe, a.binaries, a.datas, name="GMJournal")
