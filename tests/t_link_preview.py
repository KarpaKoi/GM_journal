"""Passo 11c, anteprima dei collegamenti: cosa mostra (elemento, pagina, mappa, grafo), quando compare e sparisce, dove si mette."""
from harness import *
app()
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QFontMetrics, QMouseEvent, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from gmjournal import theme
from gmjournal.app import MainWindow
from gmjournal.data import links
from gmjournal.data.models import ElementInput
from gmjournal.ui.editor.editor import RichEditor
from gmjournal.ui.editor.note_editor import NoteEditor
from gmjournal.ui.link_sources import LinkSources
from gmjournal.ui.widgets.link_preview import WIDTH, LinkPreviewCard, LinkPreviewData, clamp_lines

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

# --- Accorciare il testo -------------------------------------------------------------------------------------
font = theme.ui_font(13); metrics = QFontMetrics(font)
def lines_of(text, width=312):
    wrap = Qt.TextWordWrap | Qt.TextWrapAnywhere
    one = metrics.boundingRect(QRect(0, 0, width, 100000), wrap, "x").height()
    return metrics.boundingRect(QRect(0, 0, width, 100000), wrap, text).height() // one
check("un testo breve resta com'è", clamp_lines("Una ladra.", font, 312, 3) == "Una ladra.")
check("un testo vuoto resta vuoto", clamp_lines("", font, 312, 3) == "")
long = " ".join(f"parola{i}" for i in range(200))
cut = clamp_lines(long, font, 312, 3)
check("un testo lungo sta in tre righe e finisce con «…»", lines_of(cut) == 3 and cut.endswith("…") and long.startswith(cut[:-1]))
check("…ma ne usa tre intere, non due", lines_of(clamp_lines(long, font, 312, 3)) == 3 and lines_of(clamp_lines(long, font, 312, 2)) == 2)
check("una sola parola lunghissima non manda in errore", clamp_lines("x" * 500, font, 312, 3) == "…")

# --- La finestrella da sola ------------------------------------------------------------------------------------
host = QWidget(); host.resize(800, 600); host.show()
card = LinkPreviewCard(host)
base = dict(name="Mira Vesperi", color="#8cb8e8", hint="Ctrl+clic per aprire la scheda")
card.show_data(LinkPreviewData(**base, subtitle="Locandiera", brief="Gestisce la locanda.", initials="MV", chip="Protagonisti", cited=6)); pump(20)
check("elemento: categoria, ruolo, in breve e conteggio",
      card._chip.text() == "Protagonisti" and card._subtitle._text == "Locandiera" and card._brief.text() == "Gestisce la locanda."
      and card._cited.text() == "Citato in 6 pagine" and card._hint.text() == "Ctrl+clic per aprire la scheda")
check("è larga come nel disegno e non ruba il mouse", card.width() == WIDTH == 344 and card.testAttribute(Qt.WA_TransparentForMouseEvents))
tall = card.height()
card.show_data(LinkPreviewData(**base, initials="MV", chip="Protagonisti", cited=1)); pump(20)
check("senza «in breve» la finestrella è più bassa", card.height() < tall and not card._brief.isVisible() and card._cited.text() == "Citato in 1 pagina")
card.show_data(LinkPreviewData(**base, initials="MV", chip="Protagonisti", cited=0)); pump(20)
check("mai citato: lo dice", card._cited.text() == "Non citato in nessuna pagina")
card.show_data(LinkPreviewData(name="La Locanda", color=theme.SECTION_COLORS["scrittura"], hint="Ctrl+clic per aprire la pagina", subtitle="Pagina 1",
                               brief=long, icon="file")); pump(20)
check("pagina: niente categoria né conteggio, ma il tipo e le prime righe",
      not card._chip.isVisible() and card._cited.text() == "" and card._subtitle._text == "Pagina 1" and lines_of(card._brief.text()) <= 3)
check("…alta quanto serve per tre righe", card.height() < 200)
card.show_data(LinkPreviewData(name="Mappa", color="#7fcfc8", hint="x", icon="map")); pump(20)
check("solo il nome: nessuna riga sotto e nessun «in breve»", not card._under.isVisible() and not card._brief.isVisible())
card.show_data(LinkPreviewData(name="N" * 300, color="#7fcfc8", hint="x", initials="NN")); pump(20)
check("un nome lunghissimo non allarga la finestrella", card.width() == WIDTH)
host.close()          # una finestra rimasta aperta intercetterebbe i movimenti del mouse delle prove sotto

# --- Cosa dà l'applicazione ------------------------------------------------------------------------------
repo = new_repo("Anteprima")
chars = repo.categories("character")
mira = repo.create_element(ElementInput("character", "Mira Vesperi", chars[0].id, None, "Gestisce la Locanda del Corvo.", "Locandiera di Varenhold"))
orgs = repo.categories("organization")
ordine = repo.create_element(ElementInput("organization", "Ordine della Fiamma", orgs[0].id, None, "", ""))
p1 = repo.create_page("La Locanda"); p2 = repo.create_page("Lo straniero", p1)
repo.save_content(p1, "<h2>Titolo</h2><p>La sala  era <b>silenziosa</b>.</p><ul><li>uno</li><li>due</li></ul>")
def href(kind, i): return f'<a href="{links.make_href(kind, i)}">'
repo.save_content(p2, f"<p>Entra {href('character', mira)}Mira Vesperi</a>, vede {href('organization', ordine)}Ordine della Fiamma</a> e {href('page', p1)}La Locanda</a>.</p>")
sources = LinkSources(QWidget(), repo, lambda: (links.PAGE, p2))

data = sources.preview("character", mira)
check("elemento: nome, categoria, ruolo, in breve", data.name == "Mira Vesperi" and data.chip == chars[0].name and data.subtitle == "Locandiera di Varenhold"
      and data.brief == "Gestisce la Locanda del Corvo." and data.initials == "MV" and data.image is None)
check("…compare in una pagina", data.cited == 1 and data.hint == "Ctrl+clic per aprire la scheda")
check("…nel colore della sua categoria", data.color == theme.category_color(chars[0].color))
aldric = repo.create_element(ElementInput("character", "Aldric", chars[0].id, None, "", ""))
check("un elemento mai citato: zero pagine", sources.preview("character", aldric).cited == 0 and sources.preview("organization", ordine).cited == 1)
data = sources.preview("page", p1)
check("pagina: titolo, posto nell'indice, prime righe del testo senza tag", data.name == "La Locanda" and data.subtitle == "1. La Locanda" and data.brief == "Titolo La sala era silenziosa. uno due"
      and data.icon == "file" and data.cited is None and data.hint == "Ctrl+clic per aprire la pagina")
check("sottocapitolo: il percorso «capitolo › sottocapitolo»", sources.preview("page", p2).subtitle == "1. La Locanda › 1.1 Lo straniero")
check("un bersaglio che non esiste più: niente", sources.preview("character", 9999) is None and sources.preview("page", 9999) is None)
repo.delete_element(mira)
check("un elemento eliminato: niente", sources.preview("character", mira) is None)
mira = repo.create_element(ElementInput("character", "Mira Vesperi", chars[0].id, None, "Gestisce la Locanda del Corvo.", "Locandiera di Varenhold"))
repo.save_content(p2, f"<p>Entra {href('character', mira)}Mira Vesperi</a>, vede {href('organization', ordine)}Ordine della Fiamma</a> e {href('page', p1)}La Locanda</a>."
                      + "".join("<p>Riga di riempimento per scendere nella pagina.</p>" for _ in range(60))
                      + f"<p>Metà pagina: {href('character', mira)}Mira Vesperi</a>.</p>"
                      + "".join("<p>Riga di riempimento per scendere nella pagina.</p>" for _ in range(20))
                      + f"<p>Di nuovo {href('character', mira)}Mira Vesperi</a> in fondo.</p>")

# --- Nell'editor di Scrittura -------------------------------------------------------------------------------
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "scrittura"); pump(150)
s = w._screens["scrittura"]; s._reload_tree(); s._open(p2); pump(300)
ed = s._editor; viewport = ed.viewport(); prev = ed._preview
check("l'editor di Scrittura ha l'anteprima, al posto del suggerimento", prev is not None)

def point_of(text, nth=0):
    txt = ed.document().toPlainText(); idx = -1
    for _ in range(nth + 1):
        idx = txt.index(text, idx + 1)
    cursor = QTextCursor(ed.document()); cursor.setPosition(idx + 2)
    rect = ed.cursorRect(cursor)
    return QPoint(rect.center().x() + 4, rect.center().y())

def reset():
    QTest.mouseMove(viewport, QPoint(2, ed.height() - 30)); pump(30)
    prev.leave(); pump(20)

ed.verticalScrollBar().setValue(0); reset()
QTest.mouseMove(viewport, point_of("Mira Vesperi")); pump(150)
check("a 150 ms non c'è ancora", not prev.visible)
pump(500)
check("dopo mezzo secondo compare", prev.visible)
card = prev._card
check("…è una finestrella della finestra intera, sopra tutto", card.parent() is w and card.width() == WIDTH)
mapped = viewport.mapTo(w, point_of("Mira Vesperi"))
check("…sotto la riga del link", card.y() > mapped.y() and card.y() - mapped.y() < 60)
check("…con il suo nome", card._name._text == "Mira Vesperi" and card._chip.text() == chars[0].name)
check("…e niente suggerimento «Ctrl + clic» (c'è già nella finestrella)", viewport.toolTip() == "")
QTest.mouseMove(viewport, point_of("Mira Vesperi") + QPoint(3, 0)); pump(700)
check("muovendosi sullo stesso link resta lì", prev.visible)
QTest.mouseMove(viewport, point_of("Ordine della Fiamma")); pump(100)
check("passando a un altro link sparisce subito…", not prev.visible)
pump(600)
check("…e dopo mezzo secondo compare quella del nuovo link", prev.visible and card._name._text == "Ordine della Fiamma")
QTest.mouseMove(viewport, QPoint(700, 600)); pump(50)
check("mouse fuori dai link: sparisce", not prev.visible)
QTest.mouseMove(viewport, point_of("La Locanda")); pump(700)
check("link a una pagina: titolo e posto nell'indice", prev.visible and card._name._text == "La Locanda" and card._subtitle._text == "1. La Locanda")
QTest.mouseMove(viewport, QPoint(700, 600)); pump(50)

QTest.mouseMove(viewport, point_of("Mira Vesperi")); pump(700)
QTest.keyClick(ed, Qt.Key_Shift); pump(20)
check("scrivere (un tasto qualsiasi) la toglie", not prev.visible)
QTest.mouseMove(viewport, point_of("Mira Vesperi") + QPoint(2, 0)); pump(800)
check("…e non ricompare finché il mouse resta sul link", not prev.visible)
QTest.mouseMove(viewport, QPoint(700, 600)); pump(50)
QTest.mouseMove(viewport, point_of("Mira Vesperi")); pump(700)
check("…ma tornando sul link sì", prev.visible)
ed.verticalScrollBar().setValue(60); pump(30)
check("scorrere la toglie", not prev.visible)
reset(); ed.verticalScrollBar().setValue(0); pump(30)
QTest.mouseMove(viewport, point_of("Mira Vesperi")); pump(700)
QTest.mouseClick(viewport, Qt.LeftButton, pos=QPoint(700, 600)); pump(30)
check("un clic la toglie", not prev.visible)
reset()
QTest.mouseMove(viewport, point_of("Mira Vesperi")); pump(700)
ed.set_content("<p>altro</p>"); pump(30)
check("cambiare il testo (un'altra pagina) la toglie", not prev.visible)
ed.set_content(repo.page(p2).content); pump(50); reset()
QTest.mouseMove(viewport, point_of("Mira Vesperi")); pump(700)
w._go(repo.folder, "personaggi"); pump(100)
check("cambiando schermata non resta a mezz'aria", not prev.visible and not card.isVisible())
w._go(repo.folder, "scrittura", p2); pump(300)
reset()

# Ctrl+clic apre ancora
opened = []
ed.link_activated.connect(lambda kind, i: opened.append((kind, i)))
QTest.mouseClick(viewport, Qt.LeftButton, Qt.ControlModifier, pos=point_of("Ordine della Fiamma")); pump(50)
check("Ctrl+clic su un collegamento lo apre, come prima", opened == [("organization", ordine)])

# trascinando per selezionare (tasto premuto) l'anteprima non compare, nemmeno passando su un link
reset()
start = point_of("Mira Vesperi")
drag = QMouseEvent(QEvent.MouseMove, QPointF(start), QPointF(viewport.mapToGlobal(start)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(viewport, drag); pump(800)
check("trascinando sopra un link, niente anteprima", not prev.visible)
QTest.mouseMove(viewport, QPoint(700, 600)); pump(50)
QTest.mouseMove(viewport, start); pump(700)
check("…a tasto rilasciato sì", prev.visible)
reset()

# lontano dal bordo basso: sotto la riga; con la riga vicina al bordo basso: sopra, sempre dentro la finestra
ed.verticalScrollBar().setValue(ed.verticalScrollBar().maximum()); pump(50); reset()
spot = point_of("Mira Vesperi", 2)
QTest.mouseMove(viewport, spot); pump(700)
mapped = viewport.mapTo(w, spot)
check("con posto sotto, sta sotto la riga", prev.visible and card.y() > mapped.y())
bar = ed.verticalScrollBar()
bar.setValue(0); pump(30)
spot = point_of("Mira Vesperi", 1)
bar.setValue(spot.y() - (viewport.height() - 50)); pump(50); reset()
spot = point_of("Mira Vesperi", 1)
QTest.mouseMove(viewport, spot); pump(700)
mapped = viewport.mapTo(w, spot)
check("senza posto sotto, sta sopra la riga e dentro la finestra", prev.visible and card.y() + card.height() <= mapped.y() and card.y() >= 0
      and card.y() + card.height() <= w.height())
ed.verticalScrollBar().setValue(0); reset()
w.hide()          # le prove che seguono usano finestre proprie: due finestre sovrapposte si contenderebbero il mouse

# a destra: dentro la finestra
narrow = QWidget(); narrow.resize(520, 300)
note = NoteEditor(sources.targets, sources.create, repo.import_image, lambda parent: [], repo.folder, repo.speller, 200, sources.preview)
column = QVBoxLayout(narrow); column.addWidget(note)
narrow.show(); note.set_content(f"<p>{'Parole in fila ' * 3}{href('character', mira)}Mira Vesperi</a> e il resto del testo.</p>"); pump(100)
inner = note._editor
txt = inner.document().toPlainText(); cursor = QTextCursor(inner.document()); cursor.setPosition(txt.index("Mira") + 2)
rect = inner.cursorRect(cursor)
QTest.mouseMove(inner.viewport(), QPoint(rect.center().x() + 4, rect.center().y())); pump(700)
check("nel riquadro di una scheda l'anteprima compare, sotto il link", inner._preview.visible)
shown = inner._preview._card
check("…e non esce dalla finestra stretta", shown.x() >= 0 and shown.x() + shown.width() <= narrow.width() and shown.y() + shown.height() <= narrow.height())
narrow.close()

# gli editor senza anteprima restano come prima
plain = RichEditor(link_targets=sources.targets); plain.resize(400, 200); plain.show()
plain.set_content(f"<p>{href('character', mira)}Mira Vesperi</a></p>"); pump(50)
check("senza anteprima: il suggerimento «Ctrl + clic per aprire» c'è ancora", plain._preview is None)
cursor = QTextCursor(plain.document()); cursor.setPosition(3)
QTest.mouseMove(plain.viewport(), QPoint(plain.cursorRect(cursor).center().x() + 4, plain.cursorRect(cursor).center().y())); pump(100)
check("…compare passando sul link", plain.viewport().toolTip() == "Ctrl + clic per aprire")
print(f"\n{sum(ok)}/{len(ok)}")
