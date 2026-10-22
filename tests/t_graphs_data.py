"""Prove dei dati dei grafi: migrazioni v8 e v9, grafi, nodi (liberi e collegati), archi e direzioni, pulizia quando spariscono pagine ed elementi,
mappe e grafi come bersagli di collegamento (ricerca, «@»)."""
from harness import *
app()
import sqlite3, tempfile
from pathlib import Path
from gmjournal.data import db, links
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import ElementInput, NodeInput, PinInput
from gmjournal.data.repository import NAME_MAX, Repository
from gmjournal.graphs import BOTH, DESCRIPTION_MAX, KIND_EDGE, KIND_NODE, LABEL_MAX, NEW_NODE_COLOR, NO_ARROW, TO_A, TO_B, Endpoint

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

tmp = Path(tempfile.mkdtemp(prefix="gmj_graphs_"))

# ---------- migrazione v8 -> v9 ----------
old = tmp / "vecchia"; old.mkdir()
conn = sqlite3.connect(old / db.DB_FILENAME, isolation_level=None); conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 9):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id,name,description,color,image,modified_at) VALUES (1,'Vecchia','','blue',NULL,'2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO graph (id, name) VALUES (1, 'Vecchio grafo')")
conn.execute("INSERT INTO graph_node (id, graph_id, x, y, title, color) VALUES (1, 1, 0, 0, 'A', 'blue'), (2, 1, 9, 9, 'B', 'blue')")
conn.execute("INSERT INTO graph_edge (a_id, b_id, label) VALUES (1, 2, 'vecchio arco')")
conn.close()
repo = Repository.open(old)
check("migrazione: la campagna si apre all'ultima versione", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION >= 9)
check("migrazione: copia di sicurezza v8", (old / "campagna.v8.bak").exists())
check("migrazione: gli archi di prima restano, fra gli stessi nodi e senza frecce", [(e.a, e.b, e.label, e.direction) for e in repo.graph_edges(1)] == [(N(1), N(2), "vecchio arco", NO_ARROW)])
repo.close()

# ---------- grafi ----------
repo = new_repo("ProvaGrafi")
trama = repo.create_graph("Trama principale")
corte = repo.create_graph("alleanze di corte")
zeta = repo.create_graph("Zeta")
check("elenco in ordine alfabetico, senza badare alle maiuscole", [g.name for g in repo.graphs()] == ["alleanze di corte", "Trama principale", "Zeta"])
repo.rename_graph(zeta, "Betrayals")
check("rinomina (e l'ordine si aggiorna)", [g.name for g in repo.graphs()] == ["alleanze di corte", "Betrayals", "Trama principale"])
check("rinomina di un grafo che non c'è: errore chiaro", fails(lambda: repo.rename_graph(9999, "x")))
long_graph = repo.create_graph("x" * 200)
check("il nome si accorcia", next(g for g in repo.graphs() if g.id == long_graph).name == "x" * NAME_MAX)
repo.delete_graph(long_graph)
check("un grafo eliminato sparisce", long_graph not in [g.id for g in repo.graphs()])
repo.delete_graph(9999)    # non è un errore: non c'è più

# ---------- nodi liberi ----------
cat = repo.categories(links.CHARACTER)[0]
aldric = repo.create_element(ElementInput(links.CHARACTER, "Re Aldric", cat.id, None, "Il vecchio re.", ""))
page = repo.create_page("Il tradimento")
sub = repo.create_page("Capitolo due", page)

free = repo.create_node(trama, 10.5, -20.0, NodeInput("  Un segreto  ", "Nessuno lo sa.", "amber", None))
node = repo.graph_nodes(trama)[0]
check("nodo libero: titolo ripulito, descrizione, colore, posizione", (node.title, node.description, node.color, node.x, node.y, node.link) ==
      ("Un segreto", "Nessuno lo sa.", "amber", 10.5, -20.0, None))
check("un nodo libero ha bisogno di un titolo", fails(lambda: repo.create_node(trama, 0, 0, NodeInput("   ", "", "blue", None))))
check("…anche quando lo si modifica", fails(lambda: repo.update_node(free, NodeInput("", "x", "blue", None))))
check("un nodo in un grafo che non c'è è rifiutato", fails(lambda: repo.create_node(9999, 0, 0, NodeInput("A", "", "blue", None))))
big = repo.create_node(trama, 0, 0, NodeInput("y" * 200, "z" * 2000, NEW_NODE_COLOR, None))
big_node = next(n for n in repo.graph_nodes(trama) if n.id == big)
check("titolo e descrizione hanno un massimo", len(big_node.title) == NAME_MAX and len(big_node.description) == DESCRIPTION_MAX)
repo.delete_node(big)

repo.move_node(free, 100.0, 200.0)
node = repo.graph_nodes(trama)[0]
check("spostare un nodo", (node.x, node.y) == (100.0, 200.0))
check("nei grafi non c'è il limite 0–1 delle mappe", repo.graph_nodes(trama)[0].x == 100.0)

# ---------- nodi collegati ----------
linked = repo.create_node(trama, 0, 0, NodeInput("ignorato", "Ruolo nel complotto.", "pink", (links.CHARACTER, aldric)))
node = next(n for n in repo.graph_nodes(trama) if n.id == linked)
check("collegato: il titolo viene dall'elemento, la descrizione è del nodo", node.title == "Re Aldric" and node.description == "Ruolo nel complotto." and node.link.id == aldric)
check("collegato: nel database il titolo proprio resta vuoto", repo._conn.execute("SELECT title FROM graph_node WHERE id = ?", (linked,)).fetchone()[0] == "")
check("collegato a una pagina", repo.create_node(trama, 0, 0, NodeInput("", "", "blue", (links.PAGE, page))) > 0)
check("collegamento verso qualcosa che non esiste: rifiutato", fails(lambda: repo.create_node(trama, 0, 0, NodeInput("", "", "blue", (links.CHARACTER, 9999)))))
check("collegamento con il tipo sbagliato: rifiutato", fails(lambda: repo.create_node(trama, 0, 0, NodeInput("", "", "blue", (links.PLACE, aldric)))))
repo.update_element(aldric, ElementInput(links.CHARACTER, "Aldric il Giusto", cat.id, None, "Il vecchio re.", ""))
node = next(n for n in repo.graph_nodes(trama) if n.id == linked)
check("rinominando l'elemento cambia il titolo del nodo, la descrizione resta", node.title == "Aldric il Giusto" and node.description == "Ruolo nel complotto.")

repo.update_node(linked, NodeInput("Aldric il Giusto", "Ruolo nel complotto.", "pink", None))
node = next(n for n in repo.graph_nodes(trama) if n.id == linked)
check("scollegando, il nodo diventa libero e tiene il titolo di prima", node.link is None and node.title == "Aldric il Giusto")
repo.update_node(linked, NodeInput("", "Ora di nuovo.", "pink", (links.CHARACTER, aldric)))
node = next(n for n in repo.graph_nodes(trama) if n.id == linked)
check("ricollegando, il titolo torna quello dell'elemento", node.link is not None and node.title == "Aldric il Giusto" and node.description == "Ora di nuovo.")
check("modificare un nodo che non c'è: errore chiaro", fails(lambda: repo.update_node(9999, NodeInput("A", "", "blue", None))))

# ---------- eliminare pagine ed elementi collegati ----------
on_page = [n for n in repo.graph_nodes(trama) if n.link is not None and n.link.kind == links.PAGE][0]
sub_node = repo.create_node(trama, 5, 5, NodeInput("", "Nota sul sottocapitolo.", "teal", (links.PAGE, sub)))
pin_map = repo.create_map("Mappa")
pin = repo.create_pin(pin_map, 0.5, 0.5, PinInput(repo.pin_types()[0].id, "", "", (links.CHARACTER, aldric), None))
repo.delete_element(aldric)
node = next(n for n in repo.graph_nodes(trama) if n.id == linked)
check("eliminando l'elemento il nodo resta, libero, con l'ultimo titolo e la sua descrizione", node.link is None and node.title == "Aldric il Giusto" and node.description == "Ora di nuovo.")
check("…e il pin collegato allo stesso elemento fa lo stesso", repo.pins(pin_map)[0].link is None and repo.pins(pin_map)[0].name == "Aldric il Giusto")
repo.delete_page(page)       # elimina anche il sottocapitolo
nodes = {n.id: n for n in repo.graph_nodes(trama)}
check("eliminando una pagina i nodi collegati restano liberi col titolo della pagina", nodes[on_page.id].link is None and nodes[on_page.id].title == "Il tradimento")
check("…anche quelli collegati ai suoi sottocapitoli", nodes[sub_node].link is None and nodes[sub_node].title == "Capitolo due" and nodes[sub_node].description == "Nota sul sottocapitolo.")

# ---------- archi ----------
a = repo.create_node(corte, 0, 0, NodeInput("A", "", "blue", None))
b = repo.create_node(corte, 50, 0, NodeInput("B", "", "blue", None))
c = repo.create_node(corte, 100, 0, NodeInput("C", "", "blue", None))
other = repo.create_node(trama, 0, 0, NodeInput("Altrove", "", "blue", None))
e1 = repo.create_edge(N(b), N(a))
edge = repo.graph_edges(corte)[0]
check("arco: i due estremi nell'ordine scelto, etichetta vuota", (edge.id, edge.a, edge.b, edge.label) == (e1, N(b), N(a), ""))
check("la freccia va dal primo estremo scelto al secondo", edge.direction == TO_B)
check("fra due nodi un solo arco, in qualunque verso", fails(lambda: repo.create_edge(N(a), N(b))) and fails(lambda: repo.create_edge(N(b), N(a))))
check("un nodo non si collega a se stesso", fails(lambda: repo.create_edge(N(a), N(a))))
check("nodi di grafi diversi non si collegano", fails(lambda: repo.create_edge(N(a), N(other))))
check("nodo che non esiste: errore chiaro", fails(lambda: repo.create_edge(N(a), N(9999))))
e2 = repo.create_edge(N(b), N(c))
check("…anche per gli altri archi", repo.graph_edges(corte)[1].direction == TO_B)
repo.update_edge(e1, "  alleato di  ", TO_A)
check("etichetta ripulita", [e.label for e in repo.graph_edges(corte)] == ["alleato di", ""])
repo.update_edge(e1, "q" * 300, TO_A)
check("l'etichetta ha un massimo", len(repo.graph_edges(corte)[0].label) == LABEL_MAX)
repo.update_edge(e1, "", TO_A)
check("l'etichetta può essere vuota", repo.graph_edges(corte)[0].label == "")
for direction in (NO_ARROW, BOTH, TO_B, TO_A):
    repo.update_edge(e1, "x", direction)
    check(f"la direzione {direction} si salva", repo.graph_edges(corte)[0].direction == direction)
check("una direzione che non esiste è rifiutata", fails(lambda: repo.update_edge(e1, "x", 7)) and repo.graph_edges(corte)[0].direction == TO_A)
repo.update_edge(e1, "", TO_A)
check("modificare un arco che non c'è: errore chiaro", fails(lambda: repo.update_edge(9999, "x", NO_ARROW)))
check("gli archi sono quelli del grafo chiesto", repo.graph_edges(trama) == [] and len(repo.graph_edges(corte)) == 2)
check("nodi e archi di un grafo non finiscono in un altro", len(repo.graph_nodes(trama)) == 5 and len(repo.graph_nodes(corte)) == 3)
repo.delete_edge(e2)
check("eliminare un arco non tocca i nodi", [e.id for e in repo.graph_edges(corte)] == [e1] and len(repo.graph_nodes(corte)) == 3)
repo.delete_edge(9999)
e3 = repo.create_edge(N(a), N(c))
repo.delete_node(a)
check("eliminando un nodo spariscono i suoi archi, non gli altri", [e.id for e in repo.graph_edges(corte)] == [] and len(repo.graph_nodes(corte)) == 2)
e4 = repo.create_edge(N(b), N(c))
repo.delete_graph(corte)
check("eliminando un grafo spariscono nodi e archi", repo._conn.execute("SELECT COUNT(*) FROM graph_node WHERE graph_id = ?", (corte,)).fetchone()[0] == 0
      and repo._conn.execute("SELECT COUNT(*) FROM graph_edge WHERE id = ?", (e4,)).fetchone()[0] == 0)
check("…ma non i nodi degli altri grafi", len(repo.graph_nodes(trama)) > 0)

# ---------- la campagna risulta modificata ----------
trama_node = repo.graph_nodes(trama)[0].id
edge_last = repo.create_edge(*[N(n.id) for n in repo.graph_nodes(trama)[:2]])
repo._conn.execute("UPDATE campaign SET modified_at = '2000-01-01T00:00:00+00:00' WHERE id = 1")
check("(prova preparata) la data di modifica è vecchia", repo.campaign().modified_at.year == 2000)
repo.create_graph("Nuovo")
check("scrivere nei grafi aggiorna «Modificata…»", repo.campaign().modified_at.year >= 2026)
for write in (lambda: repo.move_node(trama_node, 1, 1), lambda: repo.update_edge(edge_last, "x", BOTH), lambda: repo.delete_node(trama_node)):
    repo._conn.execute("UPDATE campaign SET modified_at = '2000-01-01T00:00:00+00:00' WHERE id = 1")
    write()
    check("anche spostare, rinominare un arco, eliminare un nodo", repo.campaign().modified_at.year >= 2026)

# ---------- mappe e grafi come bersagli di collegamento ----------
repo = new_repo("ProvaBersagli")
regno = repo.create_map("Regno di Aldoria", None, None)
valle = repo.create_map("Valle dei Corvi", regno, None)
complotto = repo.create_graph("Il complotto")
cat = repo.categories(links.CHARACTER)[0]
repo.create_element(ElementInput(links.CHARACTER, "Aldo il Corvo", cat.id, None, "", ""))
found = {(t.kind, t.id): t for t in repo.link_targets("")}
check("la ricerca trova mappe e grafi, con il loro tipo", found[(links.MAP, regno)].detail == "Mappa" and found[(links.GRAPH, complotto)].detail == "Grafo")
check("per nome: «cor» trova la valle, il grafo no, l'elemento sì", {(t.kind, t.id) for t in repo.link_targets("cor")} ==
      {(links.MAP, valle), (links.CHARACTER, next(t.id for t in repo.link_targets("aldo") if t.kind == links.CHARACTER))})
check("prima le pagine e gli elementi, poi mappe e grafi", [t.kind for t in repo.link_targets("")] == [links.CHARACTER, links.MAP, links.MAP, links.GRAPH])
check("senza «views» (pin e nodi) mappe e grafi non ci sono", {t.kind for t in repo.link_targets("", views=False)} == {links.CHARACTER})
check("link_target ritrova una mappa e un grafo", repo.link_target(links.MAP, valle).name == "Valle dei Corvi" and repo.link_target(links.GRAPH, complotto).name == "Il complotto")
page = repo.create_page("Prologo")
repo.save_content(page, f'<p>Vai nella <a href="gmj://map/{valle}">valle</a> e leggi <a href="gmj://graph/{complotto}">il complotto</a>.</p>')
check("una pagina può citare una mappa e un grafo (indice dei collegamenti)", {(t.kind, t.id) for t in repo.cited_in(page)} == {(links.MAP, valle), (links.GRAPH, complotto)})
check("«citata da» vale anche per mappe e grafi", [t.id for t in repo.cited_by(links.MAP, valle)] == [page])
repo.delete_graph(complotto)
check("eliminato il grafo il collegamento nel testo resta come testo semplice", "gmj://graph" not in repo.page(page).content and "il complotto" in repo.page(page).content
      and (links.GRAPH, complotto) not in {(t.kind, t.id) for t in repo.cited_in(page)})
repo.delete_map(valle)
check("…e lo stesso per la mappa", "gmj://map" not in repo.page(page).content and "valle" in repo.page(page).content and repo.cited_in(page) == [])
check("i nodi collegati ai bersagli non sono toccati (nessun errore, la mappa regno c'è ancora)", repo.link_target(links.MAP, regno) is not None)

print(f"{sum(ok)}/{len(ok)}")
