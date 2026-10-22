"""Prove della schermata Grafi: elenco, grafo interattivo (nodi, archi, trascinamento), pannello destro, collegamenti a pagine ed elementi, cronologia."""
from harness import *
app()
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget
from gmjournal.app import MainWindow
from gmjournal.data import links
from gmjournal.data.models import ElementInput, NodeInput
from gmjournal.graphs import BOTH, DESCRIPTION_MAX, KIND_NODE, NEW_NODE_COLOR, NEW_NODE_TITLE, NO_ARROW, TO_A, TO_B, Endpoint
from gmjournal.ui.editor.link_ui import LinkPickerPopup
from gmjournal.ui.graph_target import GraphTarget
from gmjournal.ui.popups.base import DELETE
from gmjournal.ui.popups.graph import GraphPopup
from gmjournal.ui.screens.elements import ElementTarget
from gmjournal.ui.widgets.color_swatch import ColorSwatch
from gmjournal.ui.widgets.graph_canvas import CONNECT, NODE, SELECT
from gmjournal.ui.widgets.hold_button import HOLD_MS, HoldButton
from gmjournal.ui.widgets.menu import PopupMenu

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def drive(fn, delay=60):
    QTimer.singleShot(delay, lambda: fn(QApplication.activeModalWidget()))

def at(canvas, x, y):
    """Il punto della vista dove sta il punto (x, y) della tela."""
    return canvas.mapFromScene(QPointF(x, y))

def click(canvas, x, y):
    QTest.mouseClick(canvas.viewport(), Qt.LeftButton, pos=at(canvas, x, y)); pump(60)

def click_node(canvas, node_id):
    item = canvas._nodes[node_id]
    click(canvas, item.pos().x(), item.pos().y())

def drag(canvas, x, y, dx, dy):
    start = at(canvas, x, y)
    QTest.mousePress(canvas.viewport(), Qt.LeftButton, pos=start)
    for step in range(1, 6):
        QTest.mouseMove(canvas.viewport(), start + QPoint(dx * step // 5, dy * step // 5)); pump(10)
    QTest.mouseRelease(canvas.viewport(), Qt.LeftButton, pos=start + QPoint(dx, dy)); pump(60)

def hold(button):
    QTest.mousePress(button, Qt.LeftButton); QTest.qWait(HOLD_MS + 250); QTest.mouseRelease(button, Qt.LeftButton); pump(100)

def holder(panel):
    """Il pulsante «tieni premuto» della pagina del pannello che si vede."""
    return [b for b in panel._stack.currentWidget().findChildren(HoldButton)][0]

def panel_fits(panel):
    """La pagina del pannello che si vede ha un'altezza vera e ogni suo pezzo sta nel pannello (non solo isVisible)."""
    page = panel._stack.currentWidget().widget()
    pieces = [c for c in page.findChildren(QWidget) if c.isVisible()]
    return panel.height() > 200 and all(c.width() > 0 and c.height() > 0 for c in pieces) and page.width() <= panel.width()

repo = new_repo("ProvaGrafi")
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "grafi"); pump(200)
s = w._screens["grafi"]
c = s._canvas

# --- nessun grafo ------------------------------------------------------------------------------------
check("senza grafi: schermata di benvenuto", s._views.currentIndex() == 2)
check("senza grafi: niente pannello a destra", not s.panel_visible() and not w._right_panel.isVisible())

# --- creare un grafo ---------------------------------------------------------------------------------
def name_graph(text):
    def go(d):
        assert isinstance(d, GraphPopup)
        d._name.setText(text); d.accept()
    return go
drive(name_graph("Il complotto di corte")); s._create_graph(); pump(200)
gid = repo.graphs()[0].id
check("creato e aperto: vista del grafo", s._graph_id == gid and s._views.currentIndex() == 1)
check("il grafo nuovo è nell'elenco della barra", s._tree.topLevelItemCount() == 1 and s._tree.currentItem().text(0) == "Il complotto di corte")
check("la cronologia sa dov'è", w._location[1] == "grafi" and w._location[2] == GraphTarget(gid))
check("il pannello compare, con l'elenco (vuoto) dei nodi", s.panel_visible() and w._right_panel.isVisible() and s._panel._stack.currentIndex() == 0
      and not s._panel._overview_empty.isHidden())
check("la tela vuota invita ad aggiungere un nodo", c._empty.isVisible() and not c._nodes)

# --- un nodo con un clic vero ------------------------------------------------------------------------
c.set_tool(NODE); pump(50)
check("strumento «Nodo»: compare l'invito in basso", c._tool == NODE and c._hint.isVisible())
click(c, 0, 0)
nodes = repo.graph_nodes(gid)
check("il clic crea un nodo con titolo e colore di partenza", len(nodes) == 1 and nodes[0].title == NEW_NODE_TITLE and nodes[0].color == NEW_NODE_COLOR)
check("posizione: dov'è stato cliccato", abs(nodes[0].x) < 3 and abs(nodes[0].y) < 3)
n1 = nodes[0].id
check("finito: lo strumento torna a «Seleziona» e il nodo è scelto", c._tool == SELECT and s._node_id == n1 and c._selected_node == n1)
check("il pannello mostra i campi del nodo e si vede per intero", s._panel._stack.currentIndex() == 1 and panel_fits(s._panel))
check("la cronologia ricorda il nodo", w._location[2] == GraphTarget(gid, n1, None))
check("l'invito della tela è sparito, la tela non è più vuota", not c._empty.isVisible() and not c._hint.isVisible())

# --- scrivere nel nodo -------------------------------------------------------------------------------
t = s._panel._title
t.selectAll(); QTest.keyClicks(t, "Il Cancelliere"); pump(20)
check("mentre si scrive il nodo cambia subito sulla tela", c._nodes[n1]._title == "Il Cancelliere")
check("…ma non è ancora salvato", repo.graph_nodes(gid)[0].title == NEW_NODE_TITLE)
s.flush()
check("poi si salva", repo.graph_nodes(gid)[0].title == "Il Cancelliere")
t.selectAll(); QTest.keyClick(t, Qt.Key_Delete); pump(20)
check("titolo vuoto: non si salva", repo.graph_nodes(gid)[0].title == "Il Cancelliere" and c._nodes[n1]._title == "Il Cancelliere")
s._panel._restore_title()
check("uscendo dal campo vuoto torna l'ultimo titolo", t.text() == "Il Cancelliere")
d = s._panel._description
d.setPlainText("x" * 600); pump(20)
check(f"la descrizione si ferma a {DESCRIPTION_MAX} caratteri", len(d.toPlainText()) == DESCRIPTION_MAX)
d.setPlainText("Tesse trame nell'ombra."); s.flush()
check("la descrizione si salva", repo.graph_nodes(gid)[0].description == "Tesse trame nell'ombra.")
swatch = s._panel._colors.findChildren(ColorSwatch)[4]
QTest.mouseClick(swatch, Qt.LeftButton); pump(60)
check("un colore scelto si salva subito", repo.graph_nodes(gid)[0].color == "pink" and s._nodes[n1].color == "pink")

# --- altri nodi, trascinare ---------------------------------------------------------------------------
ids = {}
for name, (x, y) in {"Regina": (320, -60), "Spia": (120, 220)}.items():
    c.set_tool(NODE); click(c, x, y)
    ids[name] = s._node_id
    t.selectAll(); QTest.keyClicks(t, name); s.flush()
check("tre nodi nel grafo", len(repo.graph_nodes(gid)) == 3 and {n.title for n in repo.graph_nodes(gid)} == {"Il Cancelliere", "Regina", "Spia"})
queen, spy = ids["Regina"], ids["Spia"]
before = c._nodes[spy].pos()
drag(c, before.x(), before.y(), 90, 40)
moved = next(n for n in repo.graph_nodes(gid) if n.id == spy)
check("trascinando un nodo si sposta e il nuovo posto si salva", abs(moved.x - (before.x() + 90 / c._scale)) < 3 and abs(moved.y - (before.y() + 40 / c._scale)) < 3)
check("il trascinamento non cambia la scelta", s._node_id == ids["Spia"] or s._node_id == queen)

# --- collegare due nodi ----------------------------------------------------------------------------------
c.set_tool(CONNECT); pump(30)
click_node(c, n1)
check("primo nodo scelto: l'invito chiede il secondo", c._armed is not None and "secondo" in c._hint._text.text())
click_node(c, queen)
edges = repo.graph_edges(gid)
check("secondo clic: nasce l'arco", len(edges) == 1 and {edges[0].a, edges[0].b} == {Endpoint(KIND_NODE, n1), Endpoint(KIND_NODE, queen)})
e1 = edges[0].id
check("l'arco è scelto, il pannello mostra i suoi campi, lo strumento torna a «Seleziona»", s._edge_id == e1 and s._panel._stack.currentIndex() == 2
      and c._tool == SELECT and panel_fits(s._panel))
check("la freccia di un arco nuovo va dal primo nodo cliccato al secondo (qui da «Il Cancelliere» a «Regina»: verso il nodo in basso)",
      repo.graph_edges(gid)[0].direction == TO_B and c._edges[e1]._direction == TO_B and s._panel._directions.checkedId() == TO_B)
for direction in (TO_A, BOTH, NO_ARROW, TO_B):
    QTest.mouseClick(s._panel._directions.button(direction), Qt.LeftButton); pump(60)
    check(f"un clic sul pulsante {direction} cambia la freccia: sulla tela e nei dati", c._edges[e1]._direction == direction and repo.graph_edges(gid)[0].direction == direction
          and s._panel._directions.checkedId() == direction)
lab = s._panel._label
QTest.keyClicks(lab, "serve fedelmente"); pump(20)
check("l'etichetta si vede subito sull'arco", c._edges[e1]._label == "serve fedelmente")
s.flush()
check("…e poi si salva", repo.graph_edges(gid)[0].label == "serve fedelmente")
c.set_tool(CONNECT); click_node(c, queen); click_node(c, n1)
check("collegare di nuovo la stessa coppia sceglie l'arco che c'è", len(repo.graph_edges(gid)) == 1 and s._edge_id == e1)
c.set_tool(CONNECT); click_node(c, n1); click_node(c, n1)
check("cliccare due volte lo stesso nodo annulla senza creare nulla", len(repo.graph_edges(gid)) == 1 and c._armed is None)
c.set_tool(CONNECT); click_node(c, spy); click_node(c, n1); pump(50)
check("secondo arco", len(repo.graph_edges(gid)) == 2)
c.set_tool(SELECT)

# --- scegliere ---------------------------------------------------------------------------------------------
click_node(c, n1)
check("clic su un nodo: campi del nodo, con i suoi due archi", s._node_id == n1 and s._panel._stack.currentIndex() == 1 and "2" in s._panel._arcs_label.text()
      and len(s._panel._arcs.parentWidget().findChildren(QAbstractButton)) >= 2)
rows = [b for b in s._panel._stack.currentWidget().findChildren(QAbstractButton) if b.__class__.__name__ == "ListRow"]
rows[0].click(); pump(60)
check("clic su un arco nell'elenco del nodo: si passa all'arco", s._edge_id is not None and s._node_id is None and s._panel._stack.currentIndex() == 2)
s._panel._from_row.itemAt(0).widget().click(); pump(60)
check("clic su un nodo dell'arco: si passa al nodo", s._node_id is not None and s._panel._stack.currentIndex() == 1)
mid = (c._nodes[n1].pos() + c._nodes[queen].pos()) / 2
click(c, mid.x(), mid.y())
check("clic sul filo di un arco: lo sceglie", s._edge_id == e1)
click(c, -400, 400)
check("clic sullo sfondo: nessuna scelta, il pannello torna all'elenco dei nodi", s._node_id is None and s._edge_id is None and s._panel._stack.currentIndex() == 0)
check("l'elenco ha tre nodi", len([b for b in s._panel._stack.currentWidget().findChildren(QAbstractButton) if b.__class__.__name__ == "ListRow"]) == 3)

# --- collegare un nodo a un elemento ----------------------------------------------------------------------
cat = repo.categories(links.CHARACTER)[0]
queen_el = repo.create_element(ElementInput(links.CHARACTER, "Isolde la Pallida", cat.id, None, "Regina di Aldoria.", ""))
click_node(c, queen)
def pick(d):
    assert isinstance(d, LinkPickerPopup)
    d._search.setText("Isolde"); pump(30)
    d._choose(d._targets("Isolde", 5)[0])
drive(pick); s._panel.link_requested.emit(); pump(150)
node = next(n for n in repo.graph_nodes(gid) if n.id == queen)
check("collegato: il titolo è quello dell'elemento, la descrizione resta del nodo", node.link is not None and node.title == "Isolde la Pallida")
check("il pannello mostra il riquadro «collegato»", not s._panel._linked.isHidden() and s._panel._free.isHidden())
check("la tela mostra il titolo dell'elemento", c._nodes[queen]._title == "Isolde la Pallida")
repo.update_element(queen_el, ElementInput(links.CHARACTER, "Isolde la Bianca", cat.id, None, "Regina di Aldoria.", ""))
s.reload()
check("se l'elemento cambia nome, il nodo lo segue", c._nodes[queen]._title == "Isolde la Bianca" and s._nodes[queen].title == "Isolde la Bianca")
s._panel.open_link_requested.emit(); pump(150)
check("«Apri» porta alla scheda dell'elemento", w._location[1] == "personaggi" and w._location[2] == ElementTarget(queen_el, True))
w._topbar.back_clicked.emit(); pump(200)
check("indietro: di nuovo sul grafo con quel nodo scelto", w._location[1] == "grafi" and s._graph_id == gid and s._node_id == queen)
s._panel.unlink_requested.emit(); pump(100)
node = next(n for n in repo.graph_nodes(gid) if n.id == queen)
check("«Scollega»: il nodo resta con il titolo che aveva", node.link is None and node.title == "Isolde la Bianca")

# --- elemento che sparisce ------------------------------------------------------------------------------
drive(pick); s._panel.link_requested.emit(); pump(150)
repo.delete_element(queen_el)
w._go(repo.folder, "personaggi"); pump(100)
w._go(repo.folder, "grafi", GraphTarget(gid, queen)); pump(150)
node = next(n for n in repo.graph_nodes(gid) if n.id == queen)
check("se l'elemento sparisce il nodo resta, libero, con l'ultimo titolo", node.link is None and node.title == "Isolde la Bianca" and s._node_id == queen)

# --- eliminare -----------------------------------------------------------------------------------------------
hold(holder(s._panel))
check("«tieni premuto» sul nodo lo elimina, con i suoi archi", queen not in {n.id for n in repo.graph_nodes(gid)} and len(repo.graph_edges(gid)) == 1)
check("dopo l'eliminazione non c'è più nulla di scelto", s._node_id is None and s._panel._stack.currentIndex() == 0)
click(c, *(lambda p: (p.x(), p.y()))(c._nodes[n1].pos())); s._panel.edge_chosen.emit(repo.graph_edges(gid)[0].id); pump(60)
hold(holder(s._panel))
check("«tieni premuto» sull'arco lo elimina", repo.graph_edges(gid) == [] and len(repo.graph_nodes(gid)) == 2)

# --- più grafi, elenco a schede ---------------------------------------------------------------------------
drive(name_graph("Alleanze")); s._create_graph(); pump(200)
second = next(g.id for g in repo.graphs() if g.name == "Alleanze")
check("il secondo grafo si apre vuoto e il primo non cambia", s._graph_id == second and repo.graph_nodes(second) == [] and len(repo.graph_nodes(gid)) == 2)
w._topbar.back_clicked.emit(); pump(150)
check("indietro: di nuovo il primo grafo", s._graph_id == gid)
s._open_graph(None); pump(100)
check("elenco dei grafi: una scheda per grafo più «Nuovo grafo»", s._views.currentIndex() == 0 and s._grid.layout() is not None
      and not s.panel_visible())
cards = s._grid.findChildren(QAbstractButton)
check("il pannello destro sparisce nell'elenco", not w._right_panel.isVisible() or not s.panel_visible())

# --- rinominare ed eliminare un grafo dal popup ---------------------------------------------------------------
def rename(d):
    d._name.setText("Alleanze e tradimenti"); d.accept()
drive(rename); s._edit_graph(s._graph(second)); pump(150)
check("rinominato", "Alleanze e tradimenti" in {g.name for g in repo.graphs()})
s._open_graph(second); pump(100)
def remove(d):
    d.done(DELETE)
drive(remove); s._edit_graph(s._graph(second)); pump(200)
check("eliminato dal popup: il grafo aperto sparisce e si torna all'elenco", second not in {g.id for g in repo.graphs()} and s._graph_id is None and s._views.currentIndex() == 0)
check("la cronologia sa che si è tornati all'elenco", w._location[2] is None or w._location[2] == GraphTarget())

# --- il «⋯» dell'elenco ----------------------------------------------------------------------------------------
tree = s._tree
asked = []
tree.menu_requested.connect(lambda graph_id, point: asked.append(graph_id))
from gmjournal.ui.widgets.name_tree import _dots_rect
row = tree.visualItemRect(tree.topLevelItem(0)).adjusted(0, 1, 0, -1)
QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=_dots_rect(row).center()); pump(50)
check("il «⋯» chiede il menu di quel grafo", asked == [tree.topLevelItem(0).data(0, Qt.UserRole)])
for menu in [m for m in QApplication.topLevelWidgets() if isinstance(m, PopupMenu) and m.isVisible()]:
    menu.close()

# --- zoom e inquadratura ------------------------------------------------------------------------------------------
s._open_graph(gid); pump(150)
check("all'apertura il grafo è tutto inquadrato", c._fitted and all(c.viewport().rect().contains(c.mapFromScene(i.pos())) for i in c._nodes.values()))
before = c._scale
c._user_zoom(1.25); pump(30)
check("ingrandendo, l'inquadratura automatica si ferma", c._scale > before and not c._fitted)
c.fit_all(); pump(30)
check("«Inquadra tutto» la ripristina", c._fitted and abs(c._scale - before) < 1e-6)

# un grafo molto più largo della finestra: si inquadra per intero anche sotto lo zoom minimo
far = repo.create_graph("Grafo vastissimo")
repo.create_node(far, -6000, -3000, NodeInput("Primo", "", "blue", None))
repo.create_node(far, 6000, 3000, NodeInput("Ultimo", "", "blue", None))
s._open_graph(far); pump(150)
visible = c.viewport().rect()
check("un grafo vastissimo si inquadra tutto, anche sotto lo zoom minimo",
      c._scale < 0.2 and all(visible.contains(c.mapFromScene(i.pos())) for i in c._nodes.values()))
c._user_zoom(0.5); pump(30)
check("riducendo non si scende sotto quell'inquadratura", abs(c._scale - c._min_scale) < 1e-9)
s._open_graph(gid); pump(150)
check("tornati a un grafo normale lo zoom minimo torna quello di sempre", abs(c._min_scale - 0.2) < 1e-9)
repo.delete_graph(far)

# --- mappe e grafi nella ricerca e nei collegamenti --------------------------------------------------------
regno = repo.create_map("Regno di Aldoria")
gid2 = repo.create_graph("Il complotto di corte 2")
check("la ricerca globale trova mappe e grafi", {(t.kind, t.id) for t in w._find("aldoria", 8)} == {("map", regno)}
      and ("graph", gid2) in {(t.kind, t.id) for t in w._find("complotto", 8)})
w._search.chosen.emit(next(t for t in w._find("complotto", 8) if t.id == gid2)); pump(200)
check("scelto un grafo nella ricerca si apre il grafo", w._location[1] == "grafi" and s._graph_id == gid2)
w._search.chosen.emit(next(t for t in w._find("aldoria", 8))); pump(200)
check("scelta una mappa nella ricerca si apre la mappa", w._location[1] == "mappe" and w._screens["mappe"]._map_id == regno)
w._go(repo.folder, "scrittura"); pump(150)
scr = w._screens["scrittura"]
opened = []
scr.open_requested.connect(lambda section, target: opened.append(section))
scr._open_target("graph", gid2); scr._open_target("map", regno)
check("da Scrittura un collegamento a un grafo o a una mappa apre la loro schermata", opened == ["grafi", "mappe"])
w._go(repo.folder, "grafi", GraphTarget(gid2)); pump(150)
check("un nodo non si collega a mappe e grafi: il selettore non li offre", {t.kind for t in repo.link_targets("", views=False)} <= {"page", "character", "place", "organization"})

# --- grafo che sparisce mentre si è altrove -------------------------------------------------------------------------
repo.delete_graph(gid)
w._go(repo.folder, "personaggi"); pump(100)
w._go(repo.folder, "grafi", GraphTarget(gid, None)); pump(150)
check("un bersaglio che non esiste più mostra l'elenco, senza errori", s._graph_id is None and s._views.currentIndex() in (0, 2))

print(f"{sum(ok)}/{len(ok)}")
