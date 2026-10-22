"""La sezione Culture: categorie di partenza, scheda con testo libero e titoli suggeriti, relazioni con gli altri elementi."""
from harness import *
app()
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
from gmjournal import sections, theme
from gmjournal.app import MainWindow
from gmjournal.data import links
from gmjournal.data.models import ElementInput
from gmjournal.elements import KINDS
from gmjournal.ui.editor.note_editor import NoteEditor
from gmjournal.ui.screens.elements import ElementTarget

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

repo = new_repo("ProvaCulture")
check("la sezione Culture è nel gruppo Mondo, dopo Organizzazioni",
      [s.key for s in sections.SECTIONS if s.group == "Mondo"] == ["personaggi", "luoghi", "organizzazioni", "culture", "incontri"])
check("colore e icona della sezione", theme.SECTION_COLORS["culture"] == "#c8d98c" and sections.BY_KEY["culture"].icon == "globe")
cats = repo.categories(links.CULTURE)
check("categorie di partenza: Popoli, Religioni, Razze, Lingue", [c.name for c in cats] == ["Popoli", "Religioni", "Razze", "Lingue"])

valesi = repo.create_element(ElementInput(links.CULTURE, "Valesi del Delta", cats[0].id, None, "Barcaioli", ""))
culto = repo.create_element(ElementInput(links.CULTURE, "Culto della Fiamma Eterna", cats[1].id, None, "", ""))
mira = repo.create_element(ElementInput(links.CHARACTER, "Mira Vesperi", repo.categories(links.CHARACTER)[0].id, None, "", ""))
check("una cultura si trova tra i bersagli dei collegamenti", any(t.kind == links.CULTURE and t.name == "Valesi del Delta" for t in repo.link_targets("", None)))

w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "culture"); pump(100)
screen = w._screens["culture"]; sheet = screen._sheet
check("la schermata Culture elenca le due culture", len(screen._tiles) == 2)
w._go(repo.folder, "culture", ElementTarget(valesi, True)); pump(150)
check("la scheda si apre: Descrizione, Immagini, Relazioni", screen._sheet_open and [t.label for t in KINDS[links.CULTURE].tabs] == ["Descrizione", "Immagini", "Relazioni"])

page = sheet._pages.widget(0)
chips = [b for b in page.findChildren(QPushButton) if b.objectName() == "SuggestionChip"]
check("12 titoli suggeriti sopra il testo", len(chips) == 12 and chips[0].text() == "Origine")
editor = page.findChildren(NoteEditor)[0]
chips[0].click(); pump()
html = editor.content()
check("un clic scrive il titolo «Origine» nel testo", "Origine" in html and "<h2" in html)
QTest.keyClicks(editor._editor, "Venuti dal mare."); pump()
chips[8].click(); pump()                                   # «Usanze» va sotto il testo già scritto
text = editor._editor.toPlainText()
check("il secondo titolo sta sotto il testo, che resta", text.index("Origine") < text.index("Venuti dal mare.") < text.index("Usanze"))
QTest.keyClicks(editor._editor, "Acqua dolce agli ospiti."); pump()
after = editor._editor.toPlainText()
check("dopo il titolo si continua a scrivere sotto di esso", after.index("Usanze") < after.index("Acqua dolce agli ospiti."))
sheet.flush(); pump()
saved = repo.texts(valesi).get("description", "")
check("il testo è salvato nel campo «description»", "Origine" in saved and "Acqua dolce" in saved)

# relazioni: una cultura è collegabile a un personaggio e si legge da entrambe le parti
relation = repo.add_relation(valesi, mira)
repo.update_relation(relation, label="Capo-barca")
check("la relazione cultura–personaggio si legge dall'altra parte", [r.other.id for r in repo.relations(mira)] == [valesi])
repo.add_relation(valesi, culto)
w._go(repo.folder, "personaggi", ElementTarget(mira, True)); pump(150)
rel_tab = w._screens["personaggi"]._sheet
rel_tab._tabs.select("relations"); pump(100)
check("nella scheda del personaggio c'è il riquadro «Culture»", KINDS[links.CULTURE].key in KINDS[links.CHARACTER].related)

# eliminare una categoria sposta le sue culture in un'altra
repo.delete_category(cats[0].id, cats[1].id)
check("eliminando «Popoli» i Valesi passano a «Religioni»", repo.element(valesi).category_id == cats[1].id)
print(f"{sum(ok)}/{len(ok)}")
