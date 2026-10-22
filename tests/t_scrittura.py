from harness import *
app()
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from gmjournal.data.models import ElementInput
from gmjournal.app import MainWindow

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("Scrittura")
cats = repo.categories("character")
mira = repo.create_element(ElementInput("character", "Mira Vesperi", cats[0].id, None, "", ""))
page = repo.create_page("Capitolo 1")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "scrittura", page); pump(200)
s = w._screens["scrittura"]
check("la pagina si apre", s._page_id == page)
ed = s._editor
ed.setFocus(); QTest.keyClicks(ed, "Incontro con @Mira"); pump(100)
QTest.keyClick(ed, Qt.Key_Return); pump(100)
s.flush(); pump(100)
content = repo.page(page).content
check("il collegamento con @ è salvato nella pagina", f"gmj://character/{mira}" in content)
check("la pagina cita Mira (indice)", [t.id for t in repo.cited_by("character", mira)] == [page])
# clic su un collegamento della pagina → scheda del personaggio
s._open_target("character", mira); pump(200)
check("da Scrittura, un collegamento a un personaggio resta in Scrittura e mostra l'anteprima", w._location[1] == "scrittura" and s._previewed.id == mira and s._page_id == page)
# «Citato in» di Mira elenca la pagina e la apre in Scrittura
w._go(repo.folder, "personaggi", mira); pump(200)
cited = repo.cited_by("character", mira)
w._screens["personaggi"]._preview.cited_chosen.emit(cited[0]); pump(200)
check("«Citato in» → pagina in Scrittura", w._location[1] == "scrittura" and s._page_id == page)
print(f"\n{sum(ok)}/{len(ok)}")
