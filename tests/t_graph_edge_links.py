"""Prove dei collegamenti con le etichette dei grafi: un arco può finire su un nodo o su un altro arco (dati, tela, pannello)."""
from harness import *
app()
import sqlite3
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton
from gmjournal.app import MainWindow
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import NodeInput
from gmjournal.graphs import KIND_EDGE, KIND_NODE, TO_B, Endpoint, endpoint_points
from gmjournal.ui.graph_target import GraphTarget
from gmjournal.ui.widgets.graph_canvas import CONNECT, SELECT

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def N(node_id):
    return Endpoint(KIND_NODE, node_id)

def E(edge_id):
    return Endpoint(KIND_EDGE, edge_id)

def fails(fn):
    try:
        fn()
    except DatabaseError:
        return True
    return False

def node(repo, graph, title, x, y):
    return repo.create_node(graph, x, y, NodeInput(title, "", "blue", None))

# ---------- dati ----------
repo = new_repo("ProvaEtichette")
g = repo.create_graph("Intrighi")
other_graph = repo.create_graph("Altro")
a, b, c = node(repo, g, "A", -300, 0), node(repo, g, "B", 300, 0), node(repo, g, "C", 0, 300)
stranger = node(repo, other_graph, "Estraneo", 0, 0)
e1 = repo.create_edge(N(a), N(b))
repo.update_edge(e1, "alleati", TO_B)
on_edge = repo.create_edge(E(e1), N(c))
edge = next(e for e in repo.graph_edges(g) if e.id == on_edge)
check("un arco può finire su un altro arco e su un nodo", (edge.a, edge.b, edge.direction) == (E(e1), N(c), TO_B))
check("l'arco appartiene al grafo dei suoi estremi", repo._conn.execute("SELECT graph_id FROM graph_edge WHERE id = ?", (on_edge,)).fetchone()[0] == g)
check("gli archi sono letti in ordine di creazione", [x.id for x in repo.graph_edges(g)] == [e1, on_edge])
check("la stessa coppia (arco, nodo) non si ripete, in nessun verso", fails(lambda: repo.create_edge(E(e1), N(c))) and fails(lambda: repo.create_edge(N(c), E(e1))))
check("un arco non si collega a se stesso", fails(lambda: repo.create_edge(E(e1), E(e1))))
check("un arco di un altro grafo non si collega", fails(lambda: repo.create_edge(E(e1), N(stranger))))
check("un arco che non esiste: errore chiaro", fails(lambda: repo.create_edge(E(9999), N(c))))
e2 = repo.create_edge(N(b), N(c))
both = repo.create_edge(E(e1), E(e2))
check("anche due archi si collegano fra loro", [x for x in repo.graph_edges(g) if x.id == both][0].a == E(e1))
points = endpoint_points({a: (-300, 0), b: (300, 0), c: (0, 300)}, repo.graph_edges(g))
check("miniatura: un arco sta a metà fra i suoi estremi, anche se uno è un arco", points[E(e1)] == (0, 0) and points[E(on_edge)] == (0, 150)
      and points[E(e2)] == (150, 150) and points[E(both)] == (75, 75))
repo.delete_edge(e1)
check("eliminando un arco spariscono anche quelli che ci finiscono, a catena", [x.id for x in repo.graph_edges(g)] == [e2])
check("…ma non i nodi", len(repo.graph_nodes(g)) == 3)
e3 = repo.create_edge(N(a), N(c))
dep = repo.create_edge(E(e3), E(e2))
repo.delete_node(a)
check("eliminando un nodo spariscono i suoi archi e quelli che finiscono su di loro", [x.id for x in repo.graph_edges(g)] == [e2])
dep2 = repo.create_edge(E(e2), N(c))
repo.delete_graph(g)
check("eliminando il grafo non resta nessun arco", repo._conn.execute("SELECT COUNT(*) FROM graph_edge WHERE id IN (?, ?)", (dep2, e2)).fetchone()[0] == 0)
check("…e la violazione dei vincoli non c'è", repo._conn.execute("PRAGMA foreign_key_check").fetchall() == [])
try:
    repo._conn.execute("INSERT INTO graph_edge (graph_id, a_node, a_edge, b_node) VALUES (1, 1, 1, 1)")
    two_ends = False
except sqlite3.IntegrityError:
    two_ends = True
check("il database rifiuta un lato con due estremi", two_ends)
repo.close()

# ---------- la tela e il pannello ----------
repo = new_repo("ProvaEtichetteUI")
g = repo.create_graph("Intrighi")
a, b, c = node(repo, g, "Aldric", -300, 0), node(repo, g, "Berta", 300, 0), node(repo, g, "Corvo", 0, 320)
e1 = repo.create_edge(N(a), N(b))
repo.update_edge(e1, "alleati", TO_B)
w = MainWindow(); w.resize(1440, 900); w.show(); pump(100)
w._go(repo.folder, "grafi", GraphTarget(g)); pump(250)
s = w._screens["grafi"]
cv = s._canvas
cv.set_tool(SELECT)

def at(x, y):
    return cv.mapFromScene(QPointF(x, y))

def click(x, y):
    QTest.mouseClick(cv.viewport(), Qt.LeftButton, pos=at(x, y)); pump(60)

pill = cv._edges[e1]
check("l'etichetta è un possibile estremo: ha un centro e un riquadro", pill.center() == QPointF(0, 0) and not pill.body().isEmpty())
cv.set_tool(CONNECT); pump(30)
click(*(lambda p: (p.x(), p.y()))(cv._nodes[c].pos()))
check("primo clic su un nodo: l'invito parla di nodo o arco", cv._armed is not None and "arco" in cv._hint._text.text())
click(pill.center().x(), pill.center().y())
edges = repo.graph_edges(g)
check("secondo clic sull'etichetta: nasce un arco dal nodo all'arco", len(edges) == 2 and (edges[1].a, edges[1].b) == (N(c), E(e1)))
e2 = edges[1].id
check("l'arco nuovo è scelto, pronto per l'etichetta", s._edge_id == e2 and cv._tool == SELECT and s._panel._stack.currentIndex() == 2)
dep = cv._edges[e2]
check("la sua linea arriva al bordo dell'etichetta, non al centro", dep._line is not None
      and abs(dep._line[1].y() - pill.center().y()) <= pill.body().height() / 2 + 1 and dep._line[1].y() > pill.center().y() + pill.body().height() / 2 - 2)
check("nel pannello i due estremi sono il nodo e l'arco", [s._panel._from_row.itemAt(0).widget()._name, s._panel._to_row.itemAt(0).widget()._name] == ["Corvo", "alleati"])
s._panel._from_row.itemAt(0).widget().click(); pump(60)
check("premendo il nodo dell'arco si passa al nodo", s._node_id == c)
s.show_target(GraphTarget(g, None, e1)); pump(80)
rows = [r for r in s._panel._stack.currentWidget().findChildren(QAbstractButton) if r.__class__.__name__ == "ListRow"]
check("la pagina dell'arco con l'etichetta mostra i suoi estremi e l'arco che ci finisce sopra", len(rows) == 3 and "1" in s._panel._edge_arcs_label.text())
rows[-1].click(); pump(60)
check("premendo quell'arco si passa a lui", s._edge_id == e2)

# spostare un nodo muove tutta la catena (la tela si è ricostruita: gli elementi vanno riletti)
pill, dep = cv._edges[e1], cv._edges[e2]
before = dep._line[1]
moved_to = cv._nodes[a].pos() + QPointF(0, -200)
cv._nodes[a].setPos(moved_to); pump(30)
check("spostando un nodo si muovono l'arco, la sua etichetta e l'arco che ci finisce", pill.center().y() < 0 and dep._line[1] != before)
cv._nodes[a].setPos(-300, 0); pump(30)

# arco su arco senza etichetta: compare un puntino
cv.set_tool(CONNECT)
click(*(lambda p: (p.x(), p.y()))(cv._nodes[b].pos()))
mid = (dep._line[0] + dep._line[1]) / 2
click(mid.x(), mid.y())
edges = repo.graph_edges(g)
check("si collega anche a un arco senza etichetta (cliccando la sua linea)", len(edges) == 3 and (edges[2].a, edges[2].b) == (N(b), E(e2)))
pill, dep = cv._edges[e1], cv._edges[e2]
check("l'arco senza etichetta che ora ha un arco sopra mostra un puntino", dep._dot and not dep.body().isEmpty() and not pill._dot)
cv.set_tool(CONNECT)
click(*(lambda p: (p.x(), p.y()))(cv._nodes[b].pos()))
click(mid.x(), mid.y())
check("collegare di nuovo la stessa coppia sceglie l'arco che c'è", len(repo.graph_edges(g)) == 3 and s._edge_id == edges[2].id)

# eliminare l'arco con l'etichetta porta via anche quelli sopra di lui
s._saves.flush()
s._repo.delete_edge(e1); s._refresh_graph(); pump(60)
check("la tela non mostra più gli archi che finivano sull'etichetta eliminata", not cv._edges and len(cv._nodes) == 3)

# miniatura nell'elenco dei grafi
first = repo.create_edge(N(a), N(b)); repo.create_edge(E(first), N(c))
s.reload(); s._open_graph(None); pump(100)
check("l'elenco dei grafi si disegna anche con archi su archi", not s._grid.grab().isNull() and s._views.currentIndex() == 0)
print(f"{sum(ok)}/{len(ok)}")
