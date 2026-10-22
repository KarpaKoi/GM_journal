#!/usr/bin/env python3
"""Costruisce l'installer di GM Journal per Windows: installer/out/GMJournal-Setup-<versione>.exe.

Produce anche la versione portatile: installer/out/GMJournal-Portable-<versione>.zip (una cartella da scompattare dove si vuole,
anche su una chiavetta: campagne e backup restano dentro la cartella; fuori vanno solo i file temporanei in %TEMP% e il Cestino).

Non serve un PC Windows: si costruisce da Linux, assemblando
  - Python 3.13 «embeddable» ufficiale (cartella `runtime`, da scaricare da python.org e scompattare),
  - le librerie Windows di PySide6 (solo QtCore, QtGui, QtWidgets, QtSvg), shiboken6 e spylls, prese da PyPI,
  - il programma (`gmjournal`, `main.py`, `assets`) con i .pyc già pronti,
  - un piccolo lanciatore GMJournal.exe (launcher.c) compilato con MinGW,
e infine impacchettando tutto con NSIS (gmjournal.nsi).

Strumenti necessari (Debian/Ubuntu):  sudo apt install nsis gcc-mingw-w64-x86-64 python3-pip
Uso:  python3 installer/windows/build_package.py --runtime <cartella o .zip di Python embeddable 3.13 a 64 bit>
"""

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PORTABLE_NAME = "GMJournal-Portable"
PORTABLE_NOTE = """GM Journal - versione portatile

Questa cartella e' tutto il programma: non serve installare nulla e campagne e backup restano qui dentro.
Fuori da qui il programma scrive solo i file temporanei di backup, ripristino e incolla di immagini (in %TEMP%, si cancellano da soli);
cio' che elimini va nel Cestino di Windows (su una chiavetta, dove il Cestino non c'e', il programma chiede se eliminarlo per sempre).
Per usarla: scompatta lo zip dove vuoi (anche su una chiavetta) e fai doppio clic su GMJournal.exe.

  Campagne\\     le tue campagne (una cartella per ognuna, con i loro dati e le loro immagini)
  Backup\\       dove il programma propone di salvare i backup (.gmj)
  errore.log     compare se il programma ha un problema (anche uno che non lo ferma): mandalo a chi ti ha dato il programma

Per spostare il tutto su un altro computer copia l'intera cartella (le campagne vengono con lei).
Per aggiornare il programma: scompatta la nuova versione in una cartella nuova e copia dentro la vecchia cartella Campagne.
Una campagna dell'installazione normale (Documenti\\GM Journal) si porta qui copiando la sua cartella dentro Campagne.

Se Windows dice "Windows ha protetto il PC" (il programma non e' firmato): Maggiori informazioni, poi Esegui comunque.
Se lo zip e' stato scaricato da internet: tasto destro sullo zip, Proprieta', spunta "Annulla blocco" e OK, prima di scompattarlo.

IMPORTANTE: il file portable.txt (questo) deve restare accanto a GMJournal.exe: e' lui che dice al programma di lavorare in modalita' portatile.
Non mettere la cartella in un posto dove Windows non lascia scrivere (per esempio Programmi).
Richiede Windows 10 (versione 1903 o successiva) o Windows 11, a 64 bit.
"""

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "installer" / "out"
STAGE = OUT / "windows-stage"
CACHE = OUT / "windows-cache"

PYSIDE_VERSION = "6.12.0"            # la stessa con cui il programma è stato provato
PYTHON_TAG = "313"                   # python313.dll

# Cosa tenere delle librerie Qt per Python: il programma usa solo questi quattro moduli.
QT_MODULES = ("Core", "Gui", "Widgets", "Svg")
QT_PLUGINS = ("platforms/qwindows.dll", "styles/qmodernwindowsstyle.dll", "iconengines/qsvgicon.dll",
              "imageformats/qsvg.dll", "imageformats/qjpeg.dll", "imageformats/qgif.dll", "imageformats/qwebp.dll")
MSVC_DLLS = ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "vcruntime140.dll", "vcruntime140_1.dll")
# Parti di Python che il programma non usa (rete cifrata, asyncio, multiprocessing…).
RUNTIME_DROP = {"libcrypto-3.dll", "libssl-3.dll", "_ssl.pyd", "_hashlib.pyd", "_asyncio.pyd", "_overlapped.pyd",
                "_multiprocessing.pyd", "_wmi.pyd", "winsound.pyd", "python.cat", "pythonw.exe"}


def run(*cmd: object, cwd: Path | None = None) -> None:
    subprocess.run([str(c) for c in cmd], check=True, cwd=cwd)


def version() -> str:
    match = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "gmjournal" / "__init__.py").read_text(encoding="utf-8"))
    return match.group(1)


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def fetch_wheels() -> Path:
    """Scarica da PyPI le librerie per Windows a 64 bit (una volta sola: restano in cache)."""
    folder = CACHE / "wheels"
    if not list(folder.glob("pyside6_essentials-*.whl")):
        folder.mkdir(parents=True, exist_ok=True)
        run(sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:", "--dest", folder,
            "--platform", "win_amd64", "--python-version", "3.13", "--abi", f"cp{PYTHON_TAG}", "--abi", "abi3",
            "--abi", "none", f"PySide6_Essentials=={PYSIDE_VERSION}", f"shiboken6=={PYSIDE_VERSION}", "spylls")
    return folder


def unpack(archive: Path, target: Path) -> Path:
    """Scompatta uno zip (wheel o runtime) in `target`, rifiutando percorsi che uscirebbero dalla cartella."""
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit(f"File sospetto in {archive.name}: {name}")
        z.extractall(target)
    return target


def build_runtime(source: Path, dest: Path) -> None:
    if source.is_file():
        source = unpack(source, CACHE / "python-embed")
    if not (source / f"python{PYTHON_TAG}.dll").exists():
        raise SystemExit(f"{source}: non e' Python {PYTHON_TAG[0]}.{PYTHON_TAG[1:]} embeddable a 64 bit")
    for item in source.iterdir():
        if item.is_file() and item.name not in RUNTIME_DROP:
            copy(item, dest / item.name)
    # Dove cercare i moduli: libreria di Python, estensioni, librerie Qt e programma (percorsi relativi a questo file).
    (dest / f"python{PYTHON_TAG}._pth").write_text(
        f"python{PYTHON_TAG}.zip\n.\n..\\lib\n..\\app\n", encoding="ascii")


def build_libs(wheels: Path, dest: Path) -> None:
    work = CACHE / "unpacked"
    shutil.rmtree(work, ignore_errors=True)
    for wheel in wheels.glob("*.whl"):
        unpack(wheel, work)

    qt = work / "PySide6"
    keep = ["__init__.py", "_config.py", "_git_pyside_version.py", "pyside6.abi3.dll", *MSVC_DLLS]
    keep += [f"Qt{m}.pyd" for m in QT_MODULES] + [f"Qt6{m}.dll" for m in QT_MODULES]
    keep += [f"plugins/{p}" for p in QT_PLUGINS] + ["support/__init__.py", "support/deprecated.py"]
    for name in keep:
        copy(qt / name, dest / "PySide6" / name)

    sb = work / "shiboken6"
    for name in ["__init__.py", "_config.py", "_git_shiboken_module_version.py", "Shiboken.pyd",
                 "shiboken6.abi3.dll", *MSVC_DLLS]:
        copy(sb / name, dest / "shiboken6" / name)

    # spylls: il codice si tiene, i dizionari di esempio (inglese, russo, svedese) no.
    shutil.copytree(work / "spylls", dest / "spylls",
                    ignore=shutil.ignore_patterns("__pycache__", "en", "ru", "sv"))

    # Testi delle licenze (obbligatori per Qt/PySide6 e Python).
    licenses = dest.parent / "licenses"
    for folder, label in (("pyside6_essentials-*.dist-info/licenses", "PySide6-Qt"), ("shiboken6-*.dist-info/licenses", "shiboken6")):
        for path in work.glob(folder + "/*"):
            copy(path, licenses / label / path.name)
    copy(next(work.glob("spylls-*.dist-info/LICENSE")), licenses / "spylls" / "LICENSE")


def strip_svg_metadata(text: str) -> str:
    """Le icone portano un blocco `<metadata>` di ~8 KB (manifest C2PA aggiunto dal trasferimento dei file): inutile."""
    text = re.sub(r"<metadata>.*?</metadata>", "", text, flags=re.S)
    return re.sub(r'\s+xmlns:c2pa="[^"]*"', "", text)


def build_app(dest: Path) -> None:
    """Il programma: sorgenti (+ .pyc già compilati), assets e il bootstrap `run.py`."""
    shutil.copytree(ROOT / "gmjournal", dest / "gmjournal", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "assets", dest / "assets")
    copy(ROOT / "main.py", dest / "main.py")
    copy(HERE / "run.py", dest / "run.py")
    for svg in (dest / "assets" / "icons").glob("*.svg"):
        svg.write_text(strip_svg_metadata(svg.read_text(encoding="utf-8")), encoding="utf-8")

    # .pyc «checked-hash»: validi anche se la data dei file cambia nell'installazione. Devono avere lo stesso
    # numero magico di quelli di Python embeddable (la 3.13 compilata qui deve capirsi con la 3.13 del pacchetto).
    if sys.version_info[:2] != (3, int(PYTHON_TAG[1:])):
        raise SystemExit(f"Serve Python 3.{PYTHON_TAG[1:]} per compilare i .pyc (questo e' {sys.version.split()[0]}).")
    run(sys.executable, "-m", "compileall", "-q", "-j", "0", "--invalidation-mode", "checked-hash", dest)


def check_pyc_magic(runtime: Path, app: Path) -> None:
    with zipfile.ZipFile(runtime / f"python{PYTHON_TAG}.zip") as z:
        theirs = z.read(next(n for n in z.namelist() if n.endswith(".pyc")))[:4]
    ours = next(app.rglob("*.pyc")).read_bytes()[:4]
    if theirs != ours:
        raise SystemExit("I .pyc non sono compatibili con il Python del pacchetto.")


def build_launcher(dest: Path, ver: str) -> None:
    nums = ",".join((ver.split(".") + ["0"] * 4)[:4])
    res = CACHE / "launcher.res.o"
    CACHE.mkdir(parents=True, exist_ok=True)
    run("x86_64-w64-mingw32-windres", f"-DAPP_VERSION_NUMS={nums}", f'-DAPP_VERSION_TEXT=\\"{ver}\\"', "-I", HERE,
        "-I", ROOT / "installer", "-O", "coff", HERE / "launcher.rc", res)
    run("x86_64-w64-mingw32-gcc", "-Os", "-s", "-municode", "-mwindows", "-static", HERE / "launcher.c", res,
        "-o", dest / "GMJournal.exe")


def build_portable(stage: Path, ver: str) -> Path:
    """La stessa cartella dell'installer più `portable.txt` (la modalità portatile) e le cartelle dei dati, in uno zip."""
    folder = OUT / "windows-portable" / PORTABLE_NAME
    shutil.rmtree(folder.parent, ignore_errors=True)
    shutil.copytree(stage, folder)
    (folder / "portable.txt").write_text(PORTABLE_NOTE.replace("\n", "\r\n"), encoding="utf-8-sig")
    for name in ("Campagne", "Backup"):       # le cartelle dei dati esistono ma sono vuote: nessuna campagna entra nel pacchetto
        if (folder / name).exists():
            raise SystemExit(f"«{name}» non dovrebbe essere nella cartella preparata: il pacchetto portatile non deve contenere dati.")
        (folder / name).mkdir()
    archive = OUT / f"{PORTABLE_NAME}-{ver}.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(folder.rglob("*")):
            z.write(path, Path(PORTABLE_NAME) / path.relative_to(folder))
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runtime", required=True, type=Path, help="Python 3.13 embeddable a 64 bit (cartella o .zip)")
    args = parser.parse_args()
    ver = version()

    shutil.rmtree(STAGE, ignore_errors=True)
    STAGE.mkdir(parents=True)
    wheels = fetch_wheels()
    build_runtime(args.runtime.resolve(), STAGE / "runtime")
    build_libs(wheels, STAGE / "lib")
    build_app(STAGE / "app")
    check_pyc_magic(STAGE / "runtime", STAGE / "app")
    build_launcher(STAGE, ver)

    setup = OUT / f"GMJournal-Setup-{ver}.exe"
    nums = ".".join((ver.split(".") + ["0"] * 4)[:4])
    run("makensis", "-V2", f"-DVERSION={ver}", f"-DVERSION_NUMS={nums}", f"-DSTAGE={STAGE}",
        f"-DICON={ROOT / 'installer' / 'gmjournal.ico'}", f"-DOUTFILE={setup}", HERE / "gmjournal.nsi")
    portable = build_portable(STAGE, ver)
    print(f"\nFatto: {setup}  ({setup.stat().st_size / 1e6:.1f} MB)")
    print(f"Fatto: {portable}  ({portable.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
