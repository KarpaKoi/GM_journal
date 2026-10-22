"""Passo 11c, schermata iniziale di Scrittura e «Da fare»: elenco dei capitoli (parole, date, apri/chiudi, menu), pannello destro."""
from harness import *
app()
from datetime import datetime, timedelta
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from gmjournal.app import MainWindow
from gmjournal.data.models import PageNode
from gmjournal.formatting import short_date
from gmjournal.ui.widgets.todo_panel import TodoPanel, _DeleteButton, _TodoRow
from gmjournal.ui.widgets.writing_home import WritingHome

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

# --- Le date ------------------------------------------------------------------------------------------
now = datetime(2026, 10, 13, 15, 0).astimezone()
check("oggi, anche a un minuto dalla mezzanotte", short_date(now.replace(hour=0, minute=1), now) == "oggi")
check("ieri", short_date(now - timedelta(days=1), now) == "ieri")
check("più indietro: giorno e mese", short_date(now - timedelta(days=4), now) == "9 ott" and short_date(datetime(2026, 1, 3, 9, 0).astimezone(), now) == "3 gen")
check("un altro anno: si aggiunge l'anno", short_date(datetime(2025, 12, 31, 23, 0).astimezone(), now) == "31 dic 2025")

# --- L'elenco, da solo -----------------------------------------------------------------------------------
def node(pid, parent, title, words, days=0):
    return PageNode(pid, parent, 0, title, words, datetime.now().astimezone() - timedelta(days=days))

home = WritingHome(); home.resize(900, 700); home.show(); pump(50)
check("nessuna pagina: riepilogo a zero", home._summary.text() == "0 capitoli · 0 sottocapitoli · 0 parole")
rows = [(node(1, None, "La Locanda", 100, 5), "1"), (node(4, 1, "L'arrivo", 1200, 1), "1.1"), (node(5, 1, "La rissa", 40, 0), "1.2"),
        (node(2, None, "Le rovine", 2300, 3), "2"), (node(6, 2, "Il ponte", 0, 4), "2.1"), (node(3, None, "Epilogo", 1, 9), "3")]
home.set_pages(rows); pump(50)
table = home._table
check("una riga per pagina", len(table._lines) == 6)
check("riepilogo con i punti sulle migliaia e i plurali", home._summary.text() == "3 capitoli · 3 sottocapitoli · 3.641 parole")
chap = {line.node.id: line for line in table._lines}
check("un capitolo conta anche le parole dei sottocapitoli", chap[1].words == "1.340 parole" and chap[2].words == "2.300 parole")
check("…«1 parola» al singolare e «0 parole»", chap[3].words == "1 parola" and chap[6].words == "0 parole")
check("…e la data più recente dei suoi sottocapitoli", chap[1].when == "oggi" and chap[2].when == short_date(datetime.now().astimezone() - timedelta(days=3)))
check("capitolo senza sottocapitoli: nessuna scritta e nessuna freccia", chap[3].count == "" and not chap[3].foldable)
check("«1 sottocapitolo» al singolare", chap[2].count == "1 sottocapitolo" and chap[1].count == "2 sottocapitoli")
check("l'ordine è quello dell'albero (i sottocapitoli sotto il loro capitolo)", [line.number for line in table._lines] == ["1", "1.1", "1.2", "2", "2.1", "3"])

def click(index, x):
    QTest.mouseClick(table, Qt.LeftButton, pos=QPoint(x, table.top(index) + table.row_height(index) // 2)); pump(20)

chosen, menus = [], []
home.chosen.connect(chosen.append); home.menu_requested.connect(lambda pid, pt: menus.append(pid))
click(1, 300)
check("un clic su una riga apre la pagina", chosen == [4])
click(0, 20)
check("la freccia di un capitolo chiude i suoi sottocapitoli (e non apre la pagina)", chosen == [4] and [l.node.id for l in table._lines] == [1, 2, 6, 3])
home.set_pages(rows); pump(20)
check("riaggiornare l'elenco non riapre i capitoli chiusi", [l.node.id for l in table._lines] == [1, 2, 6, 3])
click(0, 20)
check("la freccia di nuovo: si riaprono", len(table._lines) == 6)
click(5, 20)
check("capitolo senza sottocapitoli: il clic sulla freccia apre la pagina", chosen[-1] == 3)
click(2, table.width() - 25)
check("«⋯» di una riga: chiede il menu di quella pagina (e non la apre)", menus == [5] and chosen[-1] == 3)
QTest.mouseMove(table, QPoint(table.width() - 25, table.top(0) + 20)); pump(20)
check("passando sopra «⋯» c'è il suggerimento «Altre azioni»", table.toolTip() == "Altre azioni")
QTest.mouseMove(table, QPoint(300, table.top(0) + 20)); pump(20)
check("…altrove no", table.toolTip() == "")
home.set_pages([row for row in rows if row[0].id not in (1, 4, 5)]); pump(20)
check("un capitolo che non c'è più sparisce dall'elenco", [l.node.id for l in table._lines] == [2, 6, 3])
home.set_pages(rows); pump(20)
check("…e se tornasse non è rimasto «chiuso»", len(table._lines) == 6)
long = [(node(1, None, "Titolo " + "molto lungo " * 30, 10), "1")]
home.set_pages(long); pump(50)
check("un titolo lunghissimo non allarga l'elenco", home.horizontalScrollBar().maximum() == 0)
home.set_pages([(node(i, None, f"Capitolo {i}", 10), str(i)) for i in range(1, 301)])
check("300 capitoli: l'elenco è un solo widget alto quanto serve", table.height() == 300 * 48 + 2)

# --- La schermata ------------------------------------------------------------------------------------------
repo = new_repo("Iniziale")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "scrittura"); pump(200)
s = w._screens["scrittura"]
check("campagna senza capitoli: schermata vuota con il suo invito", s._views.currentIndex() == 2 and s._empty.isVisible())
check("…e a destra «Da fare»", s._panel.currentIndex() == 2 and s._todo.isVisible())
check("…senza voci: la frase che spiega, senza conteggio", s._todo._empty.isVisible() and not s._todo._count.isVisible())

c1 = repo.create_page("La Locanda"); c2 = repo.create_page("Il Passo")
s1 = repo.create_page("L'arrivo", c1)
repo.save_content(s1, "<p>uno due tre quattro</p>")
s._reload_tree(); pump(50)
check("con i capitoli: si vede l'elenco, non una pagina", s._views.currentIndex() == 1 and s._page_id is None)
check("…e a destra «Da fare»", s._panel.currentIndex() == 2)
check("l'elenco conta le parole salvate", s._index._table._lines[0].words == "4 parole" and "4 parole" in s._index._summary.text())

s._open(s1); pump(100)
check("aprendo una pagina: l'editor e i collegamenti", s._views.currentIndex() == 0 and s._panel.currentIndex() == 0)
s._editor.setFocus(); QTest.keyClick(s._editor, Qt.Key_End, Qt.ControlModifier); QTest.keyClicks(s._editor, " cinque sei"); pump(100)
s._close_page(); pump(100)
check("tornando all'elenco: «Da fare» di nuovo", s._views.currentIndex() == 1 and s._panel.currentIndex() == 2)
check("…con le parole appena scritte (senza aspettare altro)", s._index._table._lines[1].words == "6 parole" and s._index._table._lines[0].words == "6 parole")
check("…e la data di oggi", s._index._table._lines[1].when == "oggi")
s._open(s1); pump(50)
w._topbar.back_clicked.emit(); pump(100)
check("«indietro» dalla pagina porta all'elenco", s._page_id is None and s._views.currentIndex() == 1 and s._panel.currentIndex() == 2)

# eliminare il capitolo aperto: si torna all'elenco
s._open(c2); pump(50)
s._delete(c2); pump(100)
check("eliminata la pagina aperta: torna l'elenco, con «Da fare»", s._page_id is None and s._views.currentIndex() == 1 and s._panel.currentIndex() == 2)
check("…e il capitolo non è più nell'elenco", [l.node.id for l in s._index._table._lines] == [c1, s1])

# un elemento mostra la sua anteprima nel pannello destro solo con una pagina aperta
s._open(s1); pump(50)
s._open_target("page", c1); pump(50)
check("da una pagina a un'altra: i collegamenti", s._panel.currentIndex() == 0)
s._close_page(); pump(50)

# menu «⋯» dell'elenco → stesse voci dell'albero
opened = []
import gmjournal.ui.screens.scrittura as scr
class FakeMenu:
    def __init__(self, parent): self.items = []; opened.append(self)
    def add_item(self, icon, text, fn, danger=False): self.items.append(text)
    def add_separator(self): pass
    def popup_at(self, point, align="right"): self.align = align
real_menu = scr.PopupMenu; scr.PopupMenu = FakeMenu
s._index.menu_requested.emit(c1, QPoint(500, 300)); pump(20)
scr.PopupMenu = real_menu
check("«⋯» di un capitolo: modifica, sottocapitolo, elimina — e si apre verso sinistra", opened[-1].items == ["Modifica…", "Nuovo sottocapitolo", "Elimina…"] and opened[-1].align == "right")

# --- «Da fare» -----------------------------------------------------------------------------------------------
todo = s._todo
def rows_():
    return [todo._items.itemAt(i).widget() for i in range(todo._items.count()) if isinstance(todo._items.itemAt(i).widget(), _TodoRow)]
def texts():
    return [r._todo.text for r in rows_()]
def add(text):
    todo._field._edit.setText(text); todo._field.submitted.emit(); pump(50)

check("all'inizio nessuna voce", repo.todos() == [] and texts() == [])
add("Stampare la pianta"); add("   Preparare  tre   trappole  "); pump(20)
check("Invio aggiunge la voce (spazi puliti) e svuota il campo", texts() == ["Preparare tre trappole", "Stampare la pianta"] and todo._field.text() == "")
add("   ")
check("…una riga di soli spazi non aggiunge nulla", len(repo.todos()) == 2)
todo._field.clear()
check("…il conteggio e la frase vuota", todo._count.text() == "2 da fare" and todo._count.isVisible() and not todo._empty.isVisible())
check("le voci sono nel database", [t.text for t in repo.todos()] == ["Preparare tre trappole", "Stampare la pianta"])

first = rows_()[1]
first._box.click(); pump(100)
check("la spunta sposta la voce fra le «Fatte»", [t.done for t in repo.todos()] == [False, True] and todo._count.text() == "1 da fare")
heads = [todo._items.itemAt(i).widget().text() for i in range(todo._items.count()) if todo._items.itemAt(i).widget().__class__.__name__ == "QLabel"]
check("…sotto il titoletto «FATTE · 1»", heads == ["FATTE · 1"])
rows_()[1]._box.click(); pump(100)
check("togliendo la spunta torna fra quelle da fare, in cima", [t.done for t in repo.todos()] == [False, False] and texts()[0] == "Stampare la pianta")

# modificare: clic sul testo
row = rows_()[0]
QTest.mouseClick(row, Qt.LeftButton, pos=row._text.geometry().center()); pump(50)
editor = row._editor
check("un clic sul testo lo rende modificabile, con il cursore in fondo", editor is not None and editor.toPlainText() == "Stampare la pianta"
      and not editor.textCursor().hasSelection() and editor.textCursor().atEnd())
one_line = editor.height()
editor.setPlainText("Una voce molto lunga che deve andare a capo su piu righe dentro il pannello stretto, senza essere tagliata in alto o in basso mentre la si modifica."); pump(100)
check("mentre si modifica il campo cresce con le righe (niente testo tagliato)", editor.height() >= 3 * one_line - 6 and editor.height() >= editor.document().size().height()
      and row.height() >= editor.height())
editor.setPlainText("Stampare la pianta"); editor.moveCursor(QTextCursor.End)
QTest.keyClicks(editor, " della locanda, a colori"); QTest.keyClick(editor, Qt.Key_Return); pump(100)
check("Invio conferma la modifica", texts()[0] == "Stampare la pianta della locanda, a colori" and repo.todos()[0].text == "Stampare la pianta della locanda, a colori")
row = rows_()[0]; row.edit(); pump(20)
row._editor.setPlainText("Cambio d'idea"); QTest.keyClick(row._editor, Qt.Key_Escape); pump(100)
check("Esc annulla", texts()[0] == "Stampare la pianta della locanda, a colori")
row = rows_()[0]; row.edit(); pump(20)
row._editor.setPlainText("   "); QTest.keyClick(row._editor, Qt.Key_Return); pump(100)
check("un testo svuotato non si salva: resta quello di prima", texts()[0] == "Stampare la pianta della locanda, a colori")
row = rows_()[0]; row.edit(); pump(20)
row._editor.setPlainText("Uscita dal campo"); todo._field._edit.setFocus(); pump(100)
check("uscire dal campo conferma", "Uscita dal campo" in texts())
row = rows_()[0]; row.edit(); pump(20)
QTest.keyClicks(row._editor, "x"); row._box.click(); pump(100)
check("spuntare mentre si modifica conferma prima il testo", any(t.text.endswith("x") and t.done for t in repo.todos()))

# eliminare: la «x» sulla voce, subito
n = len(repo.todos())
rows_()[0]._delete.click(); pump(100)
check("la «x» elimina la voce subito", len(repo.todos()) == n - 1)
check("la «x» non si vede finché il mouse non è sulla voce, ma il posto c'è", rows_()[0]._delete.width() == 22 and isinstance(rows_()[0]._delete, _DeleteButton))
for r in rows_():
    r._delete.click()
pump(100)
check("senza più voci: di nuovo la frase che spiega", repo.todos() == [] and todo._empty.isVisible() and not todo._count.isVisible())

# 300 caratteri al massimo
add("a" * 400); pump(50)
check("una voce lunghissima si taglia a 300 lettere", len(repo.todos()[0].text) == 300)

# le voci restano riaprendo la campagna
w._go(repo.folder, "personaggi"); pump(100)
w._go(repo.folder, "scrittura"); pump(150)
s = w._screens["scrittura"]
check("tornando a Scrittura le voci ci sono ancora", [r._todo.text for r in [s._todo._items.itemAt(i).widget() for i in range(s._todo._items.count())] if isinstance(r, _TodoRow)] == [repo.todos()[0].text])

# il pannello da solo: tanti elementi non rompono lo scorrimento
panel = TodoPanel(); panel.resize(300, 400); panel.show()
from gmjournal.data.models import Todo
panel.set_todos([Todo(i, f"Cosa numero {i} " * 3, i % 3 == 0) for i in range(1, 60)]); pump(100)
check("59 voci: il pannello scorre e non va in errore", panel._scroll.verticalScrollBar().maximum() > 0)
print(f"\n{sum(ok)}/{len(ok)}")
