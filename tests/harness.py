"""Supporto per le prove: app Qt senza schermo (`QT_QPA_PLATFORM=offscreen`), campagna di prova in una cartella temporanea."""
import os, sys, tempfile, shutil     # tempfile e shutil, come Qt e QPoint sotto, le prove li prendono da qui con `from harness import *`
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT = Path(__file__).resolve().parent.parent      # la cartella GM_Journal
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QStandardPaths, QCoreApplication, QPoint, Qt
from PySide6.QtWidgets import QApplication

_app = None

def app():
    global _app
    if _app is None:
        QStandardPaths.setTestModeEnabled(True)
        _app = QApplication.instance() or QApplication([])
        from gmjournal import theme
        theme.load_fonts(); theme.apply(_app)
    return _app

def pump(ms=0):
    app()
    from PySide6.QtTest import QTest
    QTest.qWait(ms) if ms else QCoreApplication.processEvents()
    QCoreApplication.processEvents()

def new_repo(name="Prova", seed=True):
    app()
    from gmjournal.data.repository import Repository, unique_folder
    from gmjournal.data.models import CampaignInput
    folder = unique_folder(name)
    repo = Repository.create(folder, CampaignInput(name, "", "blue", None))
    return repo

def shot(widget, path, size=None):
    app()
    if size:
        widget.resize(*size)
    widget.show()
    pump(250)
    widget.grab().save(str(path))
    return path
