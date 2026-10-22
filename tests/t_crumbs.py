"""Il percorso in alto («Campagna › Sezione › …») è cliccabile."""
from harness import *
app()
from PySide6.QtTest import QTest
from gmjournal.app import MainWindow
from gmjournal.ui.widgets.breadcrumb import _Crumb

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("Percorso")
cap = repo.create_page("La Locanda")
sub = repo.create_page("Lo straniero", cap)
other = repo.create_page("Il bosco")

w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
crumbs = lambda: w._topbar._location.findChildren(_Crumb)
texts = lambda: [c.text() for c in crumbs()]
enabled = lambda: [c.isEnabled() for c in crumbs()]
press = lambda index: crumbs()[index].click()

check("nell'elenco campagne c'è solo il titolo, non cliccabile", texts() == ["Le tue campagne"] and enabled() == [False])

w._go(repo.folder, "scrittura"); pump(200)
check("Scrittura senza pagina: «Campagna › Scrittura», la campagna si preme, la sezione no", texts() == ["Percorso", "Scrittura"] and enabled() == [True, False])

w._go(repo.folder, "scrittura", cap); pump(200)
check("pagina aperta: si aggiunge il capitolo", texts() == ["Percorso", "Scrittura", "1. La Locanda"])
check("…la sezione ora si preme, il posto attuale no", enabled() == [True, True, False])

w._go(repo.folder, "scrittura", sub); pump(200)
check("sottocapitolo: capitolo e sottocapitolo, con la numerazione", texts() == ["Percorso", "Scrittura", "1. La Locanda", "1.1 Lo straniero"])
check("…il capitolo si preme", enabled() == [True, True, True, False])

press(2); pump(100)
check("premere il capitolo apre la sua pagina", w._screens["scrittura"]._page_id == cap and texts()[-1] == "1. La Locanda")
check("…ed entra nella cronologia", w._history.can_back)
press(1); pump(100)
check("premere «Scrittura» riporta alla schermata iniziale", w._screens["scrittura"]._page_id is None and texts() == ["Percorso", "Scrittura"])
w._travel(w._history.back()); pump(100)
check("«indietro» torna alla pagina", w._screens["scrittura"]._page_id == cap)
press(0); pump(100)
check("premere la campagna porta all'elenco campagne", w._location[0] is None and texts() == ["Le tue campagne"])

# titolo rinominato mentre la pagina è aperta: il percorso lo segue
w._go(repo.folder, "scrittura", other); pump(200)
s = w._screens["scrittura"]
s._title.setText("Il bosco nero"); s._title.textEdited.emit("Il bosco nero"); s._save(); pump(100)
check("rinominare la pagina aggiorna il percorso", texts()[-1] == "2. Il bosco nero")

# nome lunghissimo: nessun tratto supera la misura massima e la barra non si allarga
repo.rename_page(other, "Un titolo lunghissimo " * 12)
w._go(repo.folder, "scrittura", other); pump(200); s._reload_tree(); pump(100)
check("un titolo lunghissimo si accorcia", all(c.width() <= 260 for c in crumbs()) and w.width() == 1440)

# mappe annidate
a = repo.create_map("Mondo", None, None)
b = repo.create_map("Regno", a, None)
c = repo.create_map("Città", b, None)
w._go(repo.folder, "mappe"); pump(200)
from gmjournal.ui.map_target import MapTarget
check("elenco mappe: «Campagna › Mappe»", texts() == ["Percorso", "Mappe"] and enabled()[1] is False)
w._go(repo.folder, "mappe", MapTarget(c)); pump(200)
check("mappa annidata: la catena delle mappe", texts() == ["Percorso", "Mappe", "Mondo", "Regno", "Città"])
press(3); pump(100)
check("premere «Regno» apre quella mappa", w._screens["mappe"]._map_id == b and texts()[-1] == "Regno")
press(1); pump(100)
check("premere «Mappe» torna all'elenco", w._screens["mappe"]._map_id is None)
print(f"\n{sum(ok)}/{len(ok)}")
