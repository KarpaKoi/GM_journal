"""Versione portatile: con `portable.txt` accanto al programma campagne e backup stanno dentro la sua cartella; senza, in Documenti."""
from harness import *
app()
import tempfile
from pathlib import Path
from gmjournal import paths
from gmjournal.data import repository as repo_mod
from gmjournal.data.repository import Repository
from gmjournal.data.models import CampaignInput

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

check("dai sorgenti (nessun portable.txt) il programma non è portatile", paths.portable_root() is None)
check("…e le campagne stanno in Documenti\\GM Journal", paths.campaigns_root().name == "GM Journal")

package = Path(tempfile.mkdtemp(prefix="gmj_portable_")) / "GMJournal-Portable"
(package / "app").mkdir(parents=True)
saved = paths._PACKAGE_ROOT
paths._PACKAGE_ROOT = package
check("il solo portable.txt non basta: serve anche app\\run.py (cioè il pacchetto vero)", (package / "portable.txt").write_text("x") and paths.portable_root() is None)
(package / "app" / "run.py").write_text("")
check("con portable.txt e il pacchetto il programma è portatile", paths.portable_root() == package)
check("le campagne stanno in Campagne, accanto al programma", paths.campaigns_root() == package / "Campagne")
check("le finestre dei file partono da Backup", paths.start_folder() == package / "Backup")

repo_mod.campaigns_root = paths.campaigns_root
folder = repo_mod.unique_folder("Aurora")
check("una campagna nuova prende posto in Campagne", folder == package / "Campagne" / "Aurora")
Repository.create(folder, CampaignInput("Aurora", "", "blue", None)).close()
check("l'elenco delle campagne legge Campagne", [entry.folder for entry in repo_mod.list_campaigns()] == [folder])
check("una seconda campagna con lo stesso nome prende «(2)»", repo_mod.unique_folder("Aurora") == package / "Campagne" / "Aurora (2)")

paths._PACKAGE_ROOT = saved
print(f"\n{sum(ok)}/{len(ok)}")
