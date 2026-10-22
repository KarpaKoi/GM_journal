"""Impostazioni comuni delle prove pytest (`python -m pytest tests`): Qt senza schermo e campagne in una cartella temporanea.

Le prove `test_*.py` sono quelle di sicurezza e stabilità; le altre (`t_*.py`) si lanciano con `python tests/run_all.py`.
Questa cartella non entra mai nei pacchetti (lo script di build copia solo `gmjournal`, `assets` e `main.py`).
"""

import os
import struct
import sys
import zipfile
import zlib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import pytest


def _png() -> bytes:
    """Un PNG valido di 1×1 pixel: basta per i file immagine delle prove."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


PNG = _png()


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    """La cartella delle campagne di una prova: vuota, e il programma la usa al posto dei Documenti."""
    folder = tmp_path / "Campagne"
    folder.mkdir()
    import gmjournal.data.repository as repository
    monkeypatch.setattr(repository, "campaigns_root", lambda: folder)
    return folder


@pytest.fixture(scope="session")
def qapp():
    """L'applicazione Qt senza schermo (serve solo alle prove che toccano finestre e widget)."""
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication
    QStandardPaths.setTestModeEnabled(True)       # eventuali file di Qt vanno in una cartella di prova
    app = QApplication.instance() or QApplication([])
    from gmjournal import theme
    theme.load_fonts()
    theme.apply(app)
    return app


@pytest.fixture
def campaign(root, tmp_path):
    """Una campagna con testi e immagini: (cartella, id della pagina, id dell'elemento, percorsi delle due immagini)."""
    from gmjournal.data.models import CampaignInput, ElementInput
    from gmjournal.data.repository import Repository, unique_folder
    source = tmp_path / "sorgenti"
    source.mkdir()
    (source / "a.png").write_bytes(PNG)
    (source / "b.png").write_bytes(PNG + b"\x00")
    with Repository.create(unique_folder("Aurora"), CampaignInput("Aurora", "Una campagna di prova", "violet", None)) as repo:
        a, b = repo.import_image(source / "a.png"), repo.import_image(source / "b.png")
        repo.update_campaign(CampaignInput("Aurora", "Una campagna di prova", "violet", a))
        page = repo.create_page("Il viaggio")
        repo.save_content(page, f'<p>Partenza<img src="{a}" width="10" height="10"></p>')
        element = repo.create_element(ElementInput("character", "Mira", repo.categories("character")[0].id, a, "Una cartografa", "Guida"))
        repo.save_text(element, "notes", f'<p>Appunti<img src="{b}" width="10" height="10"></p>')
        repo.create_map("Regno", None, b)
        folder = repo.folder
    return folder, page, element, (a, b)


def make_zip(path: Path, entries: dict[str, bytes | str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path
