"""Backup di una campagna: un unico file `.gmj` (uno zip con `campagna.db` e la cartella `immagini/`) e il suo ripristino.

Il ripristino non sovrascrive mai nulla: il backup torna sempre come campagna nuova.
"""

import os
import shutil
import sqlite3
import tempfile
import zipfile
import zlib
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Callable

from .db import DB_FILENAME, DatabaseError
from .models import CampaignEntry, CampaignInput
from .repository import IMAGES_DIRNAME, Repository, list_campaigns, safe_name, unique_folder

BACKUP_SUFFIX = ".gmj"
RESTORED_TAG = "ripristinata"
_COMPRESSED = {".png", ".jpg", ".jpeg", ".gif", ".webp"}   # già compressi: comprimerli ancora costa tempo e non fa guadagnare spazio
_INVALID = "Il file non è un backup di GM Journal valido, oppure è danneggiato."
MAX_UNPACKED = 8 * 1024**3        # un backup che decompresso occupa di più non si ripristina
MAX_RATIO = 200                   # …né uno compresso più di così (le immagini non si comprimono: un backup vero resta molto sotto)
_RATIO_FROM = 256 * 1024**2       # sotto questa misura il rapporto non si controlla: un database ben compresso lo può avere alto, ma non è un rischio
_SPARE_SPACE = 16 * 1024**2       # spazio libero in più che deve restare sul disco dopo il ripristino

Progress = Callable[[int, int], None]   # (byte già trattati, byte totali): chi esegue il backup la richiama dopo ogni file


def backup_filename(campaign_name: str) -> str:
    """Il nome proposto per il file di backup: «Nome della campagna 2026-10-12.gmj»."""
    return f"{safe_name(campaign_name)} {date.today():%Y-%m-%d}{BACKUP_SUFFIX}"


# --- Salvare --------------------------------------------------------------------
def save_backup(folder: Path, destination: Path, progress: Progress | None = None) -> None:
    """Salva tutta la campagna in `folder` (database e immagini) nel file `destination`.

    Il file si scrive prima con un nome provvisorio: se qualcosa va storto, un backup già presente non viene toccato.
    """
    if destination.resolve().is_relative_to(folder.resolve()):
        raise DatabaseError("Scegli una posizione fuori dalla cartella della campagna.")
    partial = destination.with_name(destination.name + ".parte")
    try:
        with tempfile.TemporaryDirectory() as scratch:
            snapshot = Path(scratch) / DB_FILENAME      # il database si copia a parte: è coerente anche se la campagna è in uso
            with Repository.open(folder) as repo:
                repo.save_copy(snapshot)
            images = sorted(path for path in (folder / IMAGES_DIRNAME).rglob("*") if path.is_file())
            files = [(snapshot, DB_FILENAME)] + [(path, path.relative_to(folder).as_posix()) for path in images]
            sizes = [path.stat().st_size for path, _ in files]
            total, done = sum(sizes), 0
            with zipfile.ZipFile(partial, "w", strict_timestamps=False) as archive:
                for (path, name), size in zip(files, sizes):
                    method = zipfile.ZIP_STORED if path.suffix.lower() in _COMPRESSED else zipfile.ZIP_DEFLATED
                    archive.write(path, name, compress_type=method)
                    done += size
                    if progress:
                        progress(done, total)
            os.replace(partial, destination)
    except OSError as error:
        raise DatabaseError(f"Impossibile salvare il backup: {error}") from error
    finally:
        partial.unlink(missing_ok=True)


# --- Ripristinare ---------------------------------------------------------------
def restore_backup(source: Path, progress: Progress | None = None) -> CampaignEntry:
    """Ripristina il backup `source` come campagna nuova e la restituisce.

    Se esiste già una campagna con lo stesso nome, la nuova si chiama «Nome (ripristinata)».
    """
    try:
        with zipfile.ZipFile(source) as archive:
            return _restore(archive, progress)
    except (zipfile.BadZipFile, zlib.error, EOFError, sqlite3.Error) as error:     # sqlite3.Error: un database con le tabelle sbagliate
        raise DatabaseError(_INVALID) from error
    except OSError as error:
        raise DatabaseError(f"Impossibile ripristinare il backup: {error}") from error


def _restore(archive: zipfile.ZipFile, progress: Progress | None) -> CampaignEntry:
    members = _members(archive)
    total = _check_size(members)
    with tempfile.TemporaryDirectory() as scratch:
        database = Path(scratch) / DB_FILENAME
        _extract(archive, members[DB_FILENAME], database)
        with Repository.open(Path(scratch)) as repo:    # controlla che sia una campagna valida (e non troppo nuova) e la aggiorna
            repo.drop_unsafe_images()                   # di un backup non ci si fida: via ogni immagine con un percorso che esce dalla campagna
            campaign = repo.campaign()
        name = _free_name(campaign.name)
        target = unique_folder(name)
        _check_room(target.parent, total)
        (target / IMAGES_DIRNAME).mkdir(parents=True)
        try:
            done = members[DB_FILENAME].file_size
            for member, info in members.items():
                if member != DB_FILENAME:
                    _extract(archive, info, target / member)
                    done += info.file_size
                    if progress:
                        progress(done, total)
            shutil.move(database, target / DB_FILENAME)    # il database per ultimo: finché manca, la cartella non è una campagna
            with Repository.open(target) as repo:
                repo.update_campaign(CampaignInput(name, campaign.description, campaign.color, campaign.image))
                return CampaignEntry(target, repo.campaign())
        except BaseException:
            shutil.rmtree(target, ignore_errors=True)   # non lascia in giro una campagna a metà
            raise


def _members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """I file del backup, per nome. Un backup contiene solo `campagna.db` e file dentro `immagini/`: qualunque altro nome,
    o un percorso che uscirebbe dalla cartella della campagna, lo rende non valido."""
    members: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        parts = PurePosixPath(info.filename).parts
        in_images = len(parts) > 1 and parts[0] == IMAGES_DIRNAME and all(
            part not in (".", "..") and ":" not in part and "\\" not in part for part in parts)
        if parts != (DB_FILENAME,) and not in_images:
            raise DatabaseError(_INVALID)
        members["/".join(parts)] = info
    if DB_FILENAME not in members:
        raise DatabaseError(_INVALID)
    return members


def _size_text(size: int) -> str:
    return f"{size / 1024**3:.1f} GB".replace(".", ",") if size >= 1024**3 else f"{max(size, 1) / 1024**2:.0f} MB"


def _check_size(members: dict[str, zipfile.ZipInfo]) -> int:
    """La dimensione del backup decompresso. Un file zip può dichiarare pochi KB e riempire il disco: si rifiuta uno troppo
    grande, o compresso in modo anomalo. (Le misure dichiarate valgono: se i dati sono di più, la lettura si ferma con un errore.)"""
    total = sum(info.file_size for info in members.values())
    if total > MAX_UNPACKED:
        raise DatabaseError(f"Il backup è troppo grande: decompresso occuperebbe {_size_text(total)} (il limite è {_size_text(MAX_UNPACKED)}).")
    packed = sum(info.compress_size for info in members.values())
    if total > _RATIO_FROM and total > MAX_RATIO * max(packed, 1):
        raise DatabaseError("Il backup è compresso in modo anomalo e potrebbe essere danneggiato o pericoloso: non lo ripristino.")
    return total


def _check_room(folder: Path, needed: int) -> None:
    """Sul disco che ospiterà la campagna ripristinata c'è posto per `needed` byte (più un po' di margine)?"""
    existing = next(path for path in (folder, *folder.parents) if path.exists())      # la cartella delle campagne può non esserci ancora
    free = shutil.disk_usage(existing).free
    if free < needed + _SPARE_SPACE:
        raise DatabaseError(f"Non c'è abbastanza spazio sul disco per ripristinare il backup: servono circa {_size_text(needed)}, "
                            f"ne restano {_size_text(free)}.")


def _extract(archive: zipfile.ZipFile, info: zipfile.ZipInfo, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(info) as source, open(destination, "wb") as target:
        shutil.copyfileobj(source, target)


def _free_name(name: str) -> str:
    """`name`, oppure «name (ripristinata)», «name (ripristinata 2)»… se esiste già una campagna con quel nome."""
    taken = {entry.campaign.name.casefold() for entry in list_campaigns()}
    candidate, number = name, 1
    while candidate.casefold() in taken:
        candidate = f"{name} ({RESTORED_TAG})" if number == 1 else f"{name} ({RESTORED_TAG} {number})"
        number += 1
    return candidate
