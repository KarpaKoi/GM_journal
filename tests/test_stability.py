"""Stabilità: errori che non devono sparire, salvataggio alla chiusura, eliminazione senza cestino, immagini ostili nell'interfaccia."""

import importlib.util
import logging
import sqlite3
import sys
import threading
import types
import zipfile
from pathlib import Path

import pytest
from conftest import PNG, PROJECT

from gmjournal.data import db, repository
from gmjournal.data.db import DatabaseError
from gmjournal.data.repository import Repository, TrashError, delete_campaign, delete_campaign_permanently, list_campaigns


def load(path: Path, name: str) -> types.ModuleType:
    """Un modulo di `installer/windows` (non è un pacchetto) caricato senza eseguirlo come programma."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run(tmp_path):
    """`installer/windows/run.py` con il suo errore.log in una cartella di prova e la finestra di avviso sostituita da un registro."""
    module = load(PROJECT / "installer" / "windows" / "run.py", "gmj_run")
    module.messages = []
    module._message = lambda text, icon=0x10: module.messages.append((text, icon))
    module.log_path = tmp_path / "errore.log"
    module._log, module._log_file = open(module.log_path, "a", encoding="utf-8"), module.log_path
    yield module
    if module._log is not None and not module._log.closed:
        module._log.close()


def raised(error: BaseException):
    try:
        raise error
    except BaseException:
        return sys.exc_info()


# --- 2. sys.excepthook e threading.excepthook (installer/windows/run.py) ---------------------------------------------
def test_excepthook_scrive_il_traceback_nel_log_e_avvisa_una_sola_volta(run):
    run._excepthook(*raised(ValueError("primo errore")))
    run._excepthook(*raised(KeyError("secondo")))
    run._log.close()
    text = run.log_path.read_text(encoding="utf-8")
    assert "ValueError: primo errore" in text and "KeyError: 'secondo'" in text and "Traceback" in text
    assert len(run.messages) == 1                                              # una sola finestra per sessione…
    assert "ValueError: primo errore" in run.messages[0][0] and str(run.log_path) in run.messages[0][0]
    assert run.messages[0][1] == 0x30                                          # …di avviso: il programma non si chiude


def test_gli_errori_nati_mentre_la_finestra_e_aperta_non_ne_aprono_un_altra(run):
    def window(text, icon=0x10):
        run.messages.append(text)
        run._excepthook(*raised(RuntimeError("nato durante l'avviso")))          # gli eventi della finestra rientrano in Qt
    run._message = window
    run._excepthook(*raised(ValueError("primo")))
    run._log.close()
    assert len(run.messages) == 1
    assert "nato durante l'avviso" in run.log_path.read_text(encoding="utf-8")


def test_un_errore_in_un_thread_arriva_al_log(run, monkeypatch):
    monkeypatch.setattr(threading, "excepthook", run._thread_excepthook)

    def work():
        raise RuntimeError("nel thread")
    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    run._log.close()
    assert "RuntimeError: nel thread" in run.log_path.read_text(encoding="utf-8")
    assert len(run.messages) == 1


def test_uscire_da_un_thread_non_e_un_errore(run):
    run._thread_excepthook(types.SimpleNamespace(exc_type=SystemExit, exc_value=SystemExit(), exc_traceback=None, thread=None))
    assert run.messages == [] and run._log.tell() == 0


def test_se_il_log_non_si_scrive_lavviso_si_mostra_lo_stesso_e_nulla_si_rompe(run):
    run._log.close()                                                           # scrivere ora solleva ValueError
    run._excepthook(*raised(ValueError("con il log chiuso")))
    assert len(run.messages) == 1 and "Non sono riuscito a salvare i dettagli" in run.messages[0][0]


def test_senza_log_e_senza_finestra_non_solleva_nulla(run):
    def no_window(text, icon=0x10):
        raise OSError("nessuna finestra")
    run._log, run._message = None, no_window
    run._excepthook(*raised(ValueError("senza niente")))                       # non deve propagare: segnalare non crea errori


def test_main_installa_gli_hook_e_a_chiusura_pulita_il_log_non_resta(run, tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(run, "_log", None)
    monkeypatch.setattr(run, "_log_path", lambda: tmp_path / "nuovo" / "errore.log")
    monkeypatch.setattr(run, "faulthandler", types.SimpleNamespace(enable=lambda file: None, disable=lambda: None))
    monkeypatch.setattr(run.logging, "basicConfig", lambda **options: seen.update(logging=options))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)                    # ripristinati a fine prova
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)

    def program(*args, **kwargs):
        seen.update(hook=sys.excepthook, thread=threading.excepthook, log=run._log)
    monkeypatch.setattr(run.runpy, "run_path", program)
    run.main()
    assert seen["hook"] is run._excepthook and seen["thread"] is run._thread_excepthook
    assert seen["logging"]["stream"] is seen["log"] and seen["logging"]["level"] == logging.WARNING      # anche logging.warning/exception
    assert not (tmp_path / "nuovo" / "errore.log").exists()                   # nessun errore: il file non resta


def test_main_lascia_il_log_se_il_programma_ha_avuto_un_errore_non_fatale(run, tmp_path, monkeypatch):
    path = tmp_path / "nuovo" / "errore.log"
    monkeypatch.setattr(run, "_log", None)
    monkeypatch.setattr(run, "_log_path", lambda: path)
    monkeypatch.setattr(run, "faulthandler", types.SimpleNamespace(enable=lambda file: None, disable=lambda: None))
    monkeypatch.setattr(run.logging, "basicConfig", lambda **options: None)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(run.runpy, "run_path", lambda *a, **k: sys.excepthook(*raised(ValueError("non fatale"))))
    run.main()
    assert "ValueError: non fatale" in path.read_text(encoding="utf-8")


def test_un_errore_dentro_uno_slot_di_qt_arriva_a_sys_excepthook(qapp, monkeypatch):
    from PySide6.QtCore import QObject, Signal
    caught = []
    monkeypatch.setattr(sys, "excepthook", lambda *info: caught.append(info))

    class Source(QObject):
        fired = Signal()

    def slot():
        raise RuntimeError("nello slot")
    source = Source()
    source.fired.connect(slot)
    source.fired.emit()
    assert caught and caught[0][0] is RuntimeError and str(caught[0][1]) == "nello slot"


# --- 2. Repository.campaign() senza la riga della campagna ------------------------------------------------------------
def test_una_campagna_senza_la_riga_da_un_errore_leggibile_e_la_home_la_mostra(root, qapp, monkeypatch):
    folder = root / "Vuota"
    folder.mkdir()
    (folder / db.DB_FILENAME).write_bytes(b"")                                # un database vuoto: lo schema c'è, la campagna no
    with Repository.open(folder) as repo, pytest.raises(DatabaseError, match="La campagna non è valida o è danneggiata."):
        repo.campaign()
    assert list_campaigns() == []                                             # nell'elenco una campagna così si salta, senza arresti

    from PySide6.QtWidgets import QMessageBox
    from gmjournal.ui.screens.home import HomeScreen
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text, *a: shown.append(text))

    def open_it():
        with Repository.open(folder) as repo:
            repo.campaign()
    assert HomeScreen()._guarded(open_it) is False
    assert shown == ["La campagna non è valida o è danneggiata."]


# --- 2. spelling.load_dictionary ----------------------------------------------------------------------------------------
def break_dictionary(monkeypatch):
    from spylls.hunspell import Dictionary
    from gmjournal import spelling

    def broken(path):
        raise ValueError("dizionario rotto")
    monkeypatch.setattr(spelling._Dictionary, "hunspell", None)
    monkeypatch.setattr(spelling._Dictionary, "missing", False)
    monkeypatch.setattr(Dictionary, "from_files", staticmethod(broken))
    return spelling


def test_un_errore_imprevisto_nel_dizionario_lo_segna_mancante_e_lo_registra(monkeypatch, caplog):
    spelling = break_dictionary(monkeypatch)
    with caplog.at_level(logging.ERROR):
        assert spelling.load_dictionary() is False
    assert spelling.is_missing() and not spelling.is_loaded()
    assert "dizionario rotto" in caplog.text and "Traceback" in caplog.text            # logging.exception
    assert spelling.load_dictionary() is False                                         # non riprova a ogni richiesta


def test_il_thread_del_dizionario_non_muore_senza_dire_pronto(qapp, monkeypatch):
    from PySide6.QtTest import QTest
    from gmjournal.ui.editor.spell_ui import DictionaryLoader
    break_dictionary(monkeypatch)
    loader, ready = DictionaryLoader(), []
    loader.ready.connect(lambda: ready.append(True))
    loader.start()
    for _ in range(100):
        if ready:
            break
        QTest.qWait(30)
    assert ready


# --- 3. Chiusura della finestra e salvataggio ---------------------------------------------------------------------------
@pytest.fixture
def window(campaign, qapp, monkeypatch):
    """La finestra con la campagna aperta in Scrittura e del testo scritto ma non ancora salvato; il salvataggio, al comando, fallisce."""
    from PySide6.QtTest import QTest
    from gmjournal.app import MainWindow
    folder, page, *_ = campaign
    main = MainWindow()
    main.resize(1200, 800)
    main.show()
    main._go(folder, "scrittura", page)
    screen = main._screens["scrittura"]
    screen._editor.setFocus()
    QTest.keyClicks(screen._editor, "testo non salvato")
    assert "content" in screen._pending
    main.state = types.SimpleNamespace(page=page, screen=screen, asked=[], answers=[False], warnings=[], failing=True)
    real_save = main._repo.save_content

    def save(page_id, content):
        if main.state.failing:
            raise DatabaseError("disco pieno")
        real_save(page_id, content)
    monkeypatch.setattr(main._repo, "save_content", save)
    monkeypatch.setattr(screen, "_warn", lambda message: main.state.warnings.append(message))

    def ask() -> bool:
        main.state.asked.append(True)
        return main.state.answers.pop(0) if main.state.answers else False
    monkeypatch.setattr(main, "_confirm_close_unsaved", ask)
    yield main
    main.state.failing = False
    main._close_campaign(ask=False)
    main.close()


def test_se_il_salvataggio_fallisce_e_si_sceglie_resta_la_finestra_non_si_chiude(window):
    assert window.close() is False
    assert len(window.state.asked) == 1
    assert window._repo is not None and "scrittura" in window._screens               # nulla si è chiuso
    assert "content" in window.state.screen._pending                                  # e il testo non si è perso
    assert window.isVisible()


def test_la_richiesta_compare_anche_se_lavviso_di_salvataggio_era_gia_stato_mostrato(window):
    window.state.screen._save_warned = True
    window.close()
    assert window.state.warnings == []                                                # l'avviso non si ripete…
    assert len(window.state.asked) == 1                                               # …ma la richiesta di chiusura sì


def test_la_prima_volta_si_mostrano_sia_lavviso_sia_la_richiesta(window):
    window.close()
    assert len(window.state.warnings) == 1 and len(window.state.asked) == 1


def test_dopo_resta_il_testo_si_salva_al_tentativo_successivo(window, campaign):
    folder, page, *_ = campaign
    assert window.close() is False
    window.state.failing = False                                                       # il problema si risolve
    assert window.close() is True
    assert len(window.state.asked) == 1                                                # niente seconda richiesta: il salvataggio riesce
    with Repository.open(folder) as repo:
        assert "testo non salvato" in repo.page(page).content


def test_chiudi_comunque_chiude(window):
    window.state.answers = [True]
    assert window.close() is True
    assert window._repo is None and window._screens == {}


def test_con_il_salvataggio_riuscito_non_si_chiede_nulla(window):
    window.state.failing = False
    assert window.close() is True and window.state.asked == []


def test_cambiare_campagna_con_un_salvataggio_fallito_e_resta_lascia_tutto_com_e(window, root):
    other = repository.unique_folder("Altra")
    from gmjournal.data.models import CampaignInput
    Repository.create(other, CampaignInput("Altra", "", "blue", None)).close()
    before = window._repo.folder
    assert window._switch_campaign(other) is False
    assert window._repo.folder == before and len(window.state.asked) == 1


def test_eliminare_la_campagna_aperta_non_chiede_di_salvare(window):
    window._release_campaign(window._repo.folder)
    assert window.state.asked == [] and window._repo is None


# --- 4. Eliminare una campagna senza cestino -----------------------------------------------------------------------------
class NoTrash:
    """Al posto di QFile: il cestino non accetta nulla (una chiavetta USB)."""
    @staticmethod
    def moveToTrash(path):
        return False


def test_senza_cestino_delete_campaign_solleva_un_errore_che_si_riconosce(campaign, monkeypatch):
    folder, *_ = campaign
    monkeypatch.setattr(repository, "QFile", NoTrash)
    with pytest.raises(TrashError) as error:
        delete_campaign(folder)
    assert isinstance(error.value, DatabaseError) and folder.exists()


def test_l_eliminazione_definitiva_toglie_la_cartella_ma_solo_se_e_una_campagna(campaign, tmp_path):
    folder, *_ = campaign
    stranger = tmp_path / "documenti"
    stranger.mkdir()
    (stranger / "tesi.txt").write_text("importante")
    with pytest.raises(DatabaseError):
        delete_campaign_permanently(stranger)
    assert (stranger / "tesi.txt").exists()
    delete_campaign_permanently(folder)
    assert not folder.exists()


def make_home(monkeypatch, answer: bool):
    from PySide6.QtWidgets import QMessageBox
    from gmjournal.ui.screens.home import HomeScreen
    home, asked, warnings = HomeScreen(), [], []
    monkeypatch.setattr(home, "_confirm_permanent_delete", lambda name: asked.append(name) or answer)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    return home, asked, warnings


def test_la_home_senza_cestino_chiede_e_se_si_rifiuta_non_elimina_nulla(campaign, qapp, monkeypatch):
    folder, *_ = campaign
    monkeypatch.setattr(repository, "QFile", NoTrash)
    home, asked, warnings = make_home(monkeypatch, answer=False)
    removing = []
    home.campaign_removing.connect(removing.append)
    home._delete(list_campaigns()[0])
    assert asked == ["Aurora"] and folder.exists() and warnings == [] and removing == [folder]


def test_la_home_senza_cestino_elimina_per_sempre_se_si_conferma(campaign, qapp, monkeypatch):
    folder, *_ = campaign
    monkeypatch.setattr(repository, "QFile", NoTrash)
    home, asked, warnings = make_home(monkeypatch, answer=True)
    home._delete(list_campaigns()[0])
    assert asked == ["Aurora"] and not folder.exists() and warnings == []


def test_con_il_cestino_funzionante_non_si_chiede_nulla(campaign, qapp, monkeypatch):
    folder, *_ = campaign
    trashed = []
    monkeypatch.setattr(repository, "QFile", types.SimpleNamespace(moveToTrash=lambda path: trashed.append(path) or True))
    home, asked, _ = make_home(monkeypatch, answer=True)
    home._delete(list_campaigns()[0])
    assert asked == [] and trashed == [str(folder)]


def test_la_conferma_dice_il_nome_e_il_pulsante_di_default_e_annulla(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from gmjournal.ui.screens.home import HomeScreen
    seen = {}

    def fake_exec(box):
        seen.update(text=box.text(), more=box.informativeText(), buttons=[b.text() for b in box.buttons()], default=box.defaultButton().text())
        next(b for b in box.buttons() if b.text() == "Elimina definitivamente").click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    assert HomeScreen()._confirm_permanent_delete("Aurora") is True
    assert "Aurora" in seen["text"] and "Aurora" in seen["more"] and "definitivamente" in seen["more"]
    assert sorted(seen["buttons"]) == ["Annulla", "Elimina definitivamente"] and seen["default"] == "Annulla"


# --- 1. L'interfaccia con percorsi ostili -----------------------------------------------------------------------------
def test_l_editor_non_legge_file_fuori_dalla_campagna_e_mostra_il_segnaposto(qapp, tmp_path):
    from PySide6.QtCore import QSize
    from gmjournal.ui.editor.editor import RichEditor
    campaign = tmp_path / "camp"
    (campaign / "immagini").mkdir(parents=True)
    (campaign / "immagini" / "a.png").write_bytes(PNG)
    outside = tmp_path / "fuori.png"
    outside.write_bytes(PNG)
    editor = RichEditor(media_dir=campaign)
    assert editor._load_image("immagini/a.png").size() == QSize(1, 1)                  # un'immagine vera si legge
    for name in ("../fuori.png", "immagini/../../fuori.png", str(outside), "C:\\x.png", "\\\\srv\\sh\\x.png", "file:///etc/passwd", "campagna.db"):
        assert editor._load_image(name).size() == QSize(280, 150), name                  # il segnaposto «Immagine non trovata»


def test_il_testo_con_un_percorso_ostile_non_fa_eccezioni(qapp, tmp_path):
    from gmjournal.ui.editor.editor import RichEditor
    (tmp_path / "camp" / "immagini").mkdir(parents=True)
    editor = RichEditor(media_dir=tmp_path / "camp")
    editor.set_content('<p>a<img src="../../x.png" width="40" height="30">b<img src="\\\\srv\\sh\\x.png" width="40" height="30"></p>')
    editor.resize(400, 300)
    assert not editor.grab().isNull()


def test_media_file_della_campagna(campaign):
    folder, _, _, (a, b) = campaign
    with Repository.open(folder) as repo:
        assert repo.media_file(a) == (folder / a).resolve()
        assert repo.media_file(None) is None and repo.media_file("../../x.png") is None and repo.media_file("C:\\x.png") is None


def test_le_tessere_e_l_anteprima_senza_file_mostrano_il_segnaposto(qapp):
    from PySide6.QtWidgets import QWidget
    from gmjournal.ui.popups.image_viewer import ImageViewer
    from gmjournal.ui.widgets.image_tile import ImageTile
    tile = ImageTile(0.75)
    tile.resize(200, 180)
    tile.set_image("Fuori", None)
    assert not tile.grab().isNull() and tile._thumb.pixmap(200, 150, 1.0) is None
    parent = QWidget()
    parent.resize(900, 700)
    viewer = ImageViewer(parent, "Fuori", None)
    assert not viewer.grab().isNull()


@pytest.mark.parametrize("evil", ["../../vittima.txt", "campagna.db", "C:\\vittima.txt", "ABSOLUTE"])
def test_eliminare_un_immagine_con_percorso_ostile_non_tocca_nessun_file(campaign, tmp_path, evil):
    folder, *_ = campaign
    victim = tmp_path / "vittima.txt"
    victim.write_text("da non toccare")
    evil = str(victim) if evil == "ABSOLUTE" else evil
    conn = sqlite3.connect(folder / db.DB_FILENAME)
    conn.execute("INSERT INTO image (path, label) VALUES (?, 'ostile')", (evil,))
    conn.commit()
    conn.close()
    with Repository.open(folder) as repo:
        repo.delete_image(next(image.id for image in repo.images() if image.path == evil))
        assert evil not in [image.path for image in repo.images()]                    # il riferimento sparisce…
    assert victim.read_text() == "da non toccare" and (folder / db.DB_FILENAME).is_file()    # …i file no


# --- 4. Pacchetto portatile -------------------------------------------------------------------------------------------------
def test_il_pacchetto_portatile_gia_costruito_ha_le_cartelle_dei_dati_vuote():
    zips = sorted((PROJECT / "installer" / "out").glob("GMJournal-Portable-*.zip"))
    if not zips:
        pytest.skip("nessun pacchetto portatile costruito")
    with zipfile.ZipFile(zips[-1]) as archive:
        names = archive.namelist()
    for folder in ("Campagne", "Backup"):
        assert f"GMJournal-Portable/{folder}/" in names
        assert [n for n in names if n.startswith(f"GMJournal-Portable/{folder}/") and n != f"GMJournal-Portable/{folder}/"] == []
    assert not [n for n in names if "/tests/" in n or n.endswith("conftest.py") or "dfsdfvs" in n]


def test_lo_script_di_build_non_mette_dati_nel_pacchetto_e_la_nota_e_onesta(tmp_path, monkeypatch):
    build = load(PROJECT / "installer" / "windows" / "build_package.py", "gmj_build")
    monkeypatch.setattr(build, "OUT", tmp_path / "out")
    dirty = tmp_path / "sporca"
    (dirty / "Campagne" / "dfsdfvs").mkdir(parents=True)
    with pytest.raises(SystemExit):                                                    # una campagna nella cartella preparata ferma la costruzione
        build.build_portable(dirty, "0.0.0")
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "GMJournal.exe").write_bytes(b"MZ")
    with zipfile.ZipFile(build.build_portable(stage, "0.0.0")) as archive:
        names = archive.namelist()
        note = archive.read("GMJournal-Portable/portable.txt").decode("utf-8-sig")
    assert "GMJournal-Portable/Campagne/" in names and "GMJournal-Portable/Backup/" in names
    assert [n for n in names if n.startswith("GMJournal-Portable/Campagne/") and not n.endswith("/Campagne/")] == []
    assert "non riceve nulla" not in note and "%TEMP%" in note and "Cestino" in note
