from harness import *
app()
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QToolButton
from gmjournal.data.models import ElementInput
from gmjournal.app import MainWindow
from gmjournal.ui.screens import scrittura as scr
from gmjournal.ui.popups.base import DELETE
from gmjournal.ui.widgets.links_panel import _Row

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("AnteprimaScrittura")
cats = {k: repo.categories(k) for k in ("character", "place", "organization")}
mk = lambda kind, name, brief="", role="": repo.create_element(ElementInput(kind, name, cats[kind][0].id, None, brief, role))
mira = mk("character", "Mira Vesperi", "Ex-novizia dell’Ordine", "Cacciatrice di taglie")
varen = mk("place", "Varenhold", "Città sul fiume")
ordine = mk("organization", "Ordine della Fiamma", "Ordine religioso armato")
cap1 = repo.create_page("Capitolo 1")
cap2 = repo.create_page("Capitolo 2")
A = lambda kind, i, t: f'<a href="gmj://{kind}/{i}">{t}</a>'
repo.save_content(cap1, f"<p>Incontro con {A('character', mira, 'Mira Vesperi')} a {A('place', varen, 'Varenhold')}. Vedi {A('page', cap2, 'Capitolo 2')}.</p>")
repo.save_content(cap2, f"<p>Torna {A('character', mira, 'Mira Vesperi')}.</p>")
repo.save_text(ordine, "notes", f"<p>Ne fa parte {A('character', mira, 'Mira Vesperi')}</p>")

w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "scrittura", cap1); pump(200)
s = w._screens["scrittura"]
check("all'inizio il pannello mostra i collegamenti", s._panel.currentIndex() == 0 and s._previewed is None)

# pannello chiuso: il link lo riapre
w._toggle_panel(); pump(50)
check("pannello chiuso dall'utente", not w._right_panel.isVisible())
s._editor.link_activated.emit("character", mira); pump(150)
check("Ctrl+clic su un personaggio: resta in Scrittura", w._location[1] == "scrittura" and s._page_id == cap1)
check("…mostra la sua anteprima", s._panel.currentIndex() == 1 and s._previewed.id == mira)
check("…e riapre il pannello chiuso", w._right_panel.isVisible())
w.grab().save("prev_scrittura_100.png")

# «Apri scheda»
s._preview.sheet_requested.emit(); pump(200)
check("«Apri scheda» porta alla scheda completa", w._location[1] == "personaggi" and w._screens["personaggi"]._sheet_open and w._screens["personaggi"]._sheet.element_id == mira)
w._topbar.back_clicked.emit(); pump(200)
check("indietro: di nuovo Scrittura, con l'anteprima ancora lì", w._location[1] == "scrittura" and s._previewed is not None and s._previewed.id == mira)

# torna ai collegamenti
back = [b for b in s._panel.widget(1).findChildren(QToolButton) if b.text() == "Collegamenti"][0]
back.click(); pump(50)
check("«‹ Collegamenti» torna all'elenco", s._panel.currentIndex() == 0 and s._previewed is None)

# riga di un elemento nel pannello Collegamenti
rows = s._links.findChildren(_Row)
row = [r for r in rows if r._target.id == varen][0]
row.click(); pump(100)
check("un clic su una riga-elemento del pannello mostra la sua anteprima", s._previewed.id == varen)

# «Citato in» dall'anteprima: una pagina si apre, un elemento si anteprima
s._load_preview(mira); pump(50)
cited = repo.cited_by("character", mira)
page_target = [t for t in cited if t.kind == "page" and t.id == cap2][0]
elem_target = [t for t in cited if t.kind == "organization"][0]
s._preview.cited_chosen.emit(elem_target); pump(50)
check("«Citato in»: un elemento mostra la sua anteprima", s._previewed.id == ordine)
s._load_preview(mira)
s._preview.cited_chosen.emit(page_target); pump(100)
check("«Citato in»: una pagina si apre e il pannello torna ai collegamenti", s._page_id == cap2 and s._panel.currentIndex() == 0)
w._topbar.back_clicked.emit(); pump(100)

# cambiare pagina azzera l'anteprima
s._load_preview(mira)
s._open(cap2); pump(50)
check("aprendo un'altra pagina l'anteprima si chiude", s._previewed is None and s._panel.currentIndex() == 0)
s._open(cap1); pump(50)

# modifica dall'anteprima (popup simulato)
def fake_edit(parent, repo_, element):
    repo_.update_element(element.id, ElementInput(element.kind, "Mira Valdor", element.category_id, None, "Nuovo breve", element.role))
    return QDialog.Accepted
scr.edit_element = fake_edit
s._load_preview(mira); s._preview.edit_requested.emit(); pump(100)
check("«Modifica» ricarica l'anteprima con i dati nuovi", s._previewed.name == "Mira Valdor" and s._panel.currentIndex() == 1)
def fake_delete(parent, repo_, element):
    repo_.delete_element(element.id)
    return DELETE
scr.edit_element = fake_delete
s._editor.setFocus(); QTest.keyClicks(s._editor, " nota"); pump(50)     # testo non ancora salvato: va salvato prima
s._preview.edit_requested.emit(); pump(100)
check("eliminare l'elemento: il pannello torna ai collegamenti", s._previewed is None and s._panel.currentIndex() == 0)
check("…i collegamenti verso di lui nel testo diventano testo semplice", "gmj://character" not in s._editor.content() and "Mira Vesperi" in s._editor.content())
check("…e il testo appena scritto non si è perso", "nota" in s._editor.content() and "nota" in repo.page(cap1).content)

# elemento eliminato mentre si è altrove: tornando, si vedono i collegamenti
s._load_preview(varen); pump(50)
w._go(repo.folder, "luoghi"); pump(100)
repo.delete_element(varen)
w._go(repo.folder, "scrittura"); pump(150)
check("elemento eliminato altrove: al ritorno niente anteprima fantasma (senza pagina aperta: «Da fare»)", s._previewed is None and s._page_id is None and s._panel.currentIndex() == 2)
print(f"\n{sum(ok)}/{len(ok)}")
