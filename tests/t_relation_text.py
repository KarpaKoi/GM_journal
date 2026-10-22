"""Un testo lungo in una riga di relazione (o in un membro) si legge dall'inizio, allineato al nome sopra."""
from harness import *
app()
from PySide6.QtTest import QTest
from gmjournal.data.models import ElementInput
from gmjournal.app import MainWindow
from gmjournal.ui.sheet.parts import InlineEdit

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("RelazioniLunghe")
cats = {k: repo.categories(k) for k in ("character", "organization")}
mk = lambda kind, name: repo.create_element(ElementInput(kind, name, cats[kind][0].id, None, "", ""))
aldric, mira, ordine = mk("character", "Aldric"), mk("character", "Mira"), mk("organization", "Ordine")
long_text = "Sua nipote, la protegge da sempre e non la perde mai di vista " * 3
rid = repo.add_relation(aldric, mira); repo.update_relation(rid, label=long_text)
repo.add_relation(aldric, ordine)

w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "personaggi", aldric); pump(200)
screen = w._screens["personaggi"]; screen._open_sheet(aldric); pump(200)
screen._sheet._tabs.select("relations"); pump(300)

fields = [f for f in screen._sheet.findChildren(InlineEdit) if f.text() == long_text]
check("la riga con il testo lungo c'è", len(fields) == 1)
field = fields[0]
check("a riposo il cursore è all'inizio (il testo non scorre)", field.cursorPosition() == 0)

field.setFocus(); QTest.keyClick(field, Qt.Key_End); pump(50)
check("scrivendo, il testo scorre come deve", field.cursorPosition() == len(long_text))
field.clearFocus(); pump(50)
check("finito di scrivere torna a mostrare l'inizio", field.cursorPosition() == 0)
check("il testo non è cambiato", field.text() == long_text and repo.relations(aldric)[0].label == long_text)
print(f"\n{sum(ok)}/{len(ok)}")
