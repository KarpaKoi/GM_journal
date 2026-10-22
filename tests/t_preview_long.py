"""Il pannello destro dei Personaggi con testi lunghi: ogni pezzo sta sotto il precedente (niente sovrapposizioni) e si arriva in fondo scorrendo."""
from harness import *
app()
from gmjournal.app import MainWindow
from gmjournal.data import links
from gmjournal.data.models import ElementInput

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("AnteprimaLunga")
cat = repo.categories(links.CHARACTER)[0]
element = repo.create_element(ElementInput(links.CHARACTER, "Aldric il Giusto di Valdoria Settentrionale", cat.id, None,
                                           "Capitano della guardia reale e consigliere. " * 6, "Un testo descrittivo molto lungo. " * 40))
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "personaggi", element); pump(300)
p = w._screens["personaggi"]._preview
parts = [p._thumb, p._name, p._badge, p._open_sheet, p._role_title, p._role, p._brief_title, p._brief, p._cited]
tops = [part.mapTo(p.widget(), part.rect().topLeft()).y() for part in parts]
bottoms = [part.mapTo(p.widget(), part.rect().bottomLeft()).y() for part in parts]
check("il pannello mostra il personaggio scelto", p._details.isVisible() and p._name.text().startswith("Aldric"))
check("ogni pezzo comincia dopo la fine del precedente", all(tops[i + 1] > bottoms[i] for i in range(len(parts) - 1)))
check("il nome ha tutta l'altezza che serve (va a capo, non è schiacciato)", p._name.height() >= p._name.heightForWidth(p._name.width()))
check("il testo «In breve» ha tutta l'altezza che serve", p._brief.height() >= p._brief.heightForWidth(p._brief.width()))
check("il contenuto è alto quanto serve: si scorre fino in fondo", p.widget().height() >= bottoms[-1])
print(f"\n{sum(ok)}/{len(ok)}")
