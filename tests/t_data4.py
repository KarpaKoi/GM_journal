"""Prove del livello dati del passo 4b: migrazione v3→v4, testi, relazioni, collegamenti nelle schede."""
import sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from gmjournal.data import db
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import CampaignInput, ElementInput
from gmjournal.data.repository import Repository

tmp = Path(tempfile.mkdtemp(prefix="gmj_data4_"))
ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)
def raises(fn, *a, **k):
    try: fn(*a, **k)
    except (DatabaseError, ValueError): return True
    return False

# --- migrazione v3 -> v4 -------------------------------------------------------------
folder = tmp / "vecchia"; (folder / "images").mkdir(parents=True)
conn = sqlite3.connect(folder / "campagna.db", isolation_level=None)
for version in range(3):
    for stmt in db.MIGRATIONS[version]: conn.execute(stmt)
conn.execute("PRAGMA user_version = 3")
conn.execute("INSERT INTO campaign (id, name, modified_at) VALUES (1, 'Vecchia', '2026-01-01T00:00:00')")
conn.execute("INSERT INTO element (kind, name, category_id, modified_at) VALUES ('character', 'Aria', 1, '2026-01-01T00:00:00')")
conn.close()
repo = Repository.open(folder)
check("migrazione: ultima versione dello schema", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION)
check("migrazione: backup campagna.v3.bak", (folder / "campagna.v3.bak").is_file())
check("migrazione: dati conservati", [e.name for e in repo.elements("character")] == ["Aria"])
check("migrazione: tabelle nuove", {"element_text", "relation", "element_mention"} <= {r[0] for r in repo._conn.execute("SELECT name FROM sqlite_master")})
repo.close()

# --- testi e indice dei collegamenti ----------------------------------------------------
repo = Repository.create(tmp / "nuova", CampaignInput("Nuova", "", "blue", None))
def make(kind, name, category=None):
    category = category or repo.categories(kind)[0].id
    return repo.create_element(ElementInput(kind, name, category, None, "", ""))
aria, borin, cora = make("character", "Aria"), make("character", "Borin"), make("character", "Cora")
alba = make("place", "Alba"); gilda = make("organization", "Gilda dei Corvi")
page = repo.create_page("Capitolo uno")

link = lambda kind, i, text: f'<a href="gmj://{kind}/{i}">{text}</a>'
check("texts: vuoto all'inizio", repo.texts(aria) == {})
repo.save_text(aria, "history", f"Nata ad {link('place', alba, 'Alba')}, amica di {link('character', borin, 'Borin')}.")
repo.save_text(aria, "appearance", f"Alta. Serve la {link('organization', gilda, 'Gilda')} e {link('character', borin, 'Borin')}.")
check("texts: salvati", set(repo.texts(aria)) == {"history", "appearance"})
mention = lambda: sorted(tuple(r) for r in repo._conn.execute("SELECT * FROM element_mention WHERE element_id = ?", (aria,)))
check("indice: tutti i bersagli senza doppioni", mention() == sorted([(aria, "place", alba), (aria, "character", borin), (aria, "organization", gilda)]))
check("cited_by: borin citato da aria", [(t.kind, t.id) for t in repo.cited_by("character", borin)] == [("character", aria)])
repo.save_content(page, f"Parla {link('character', borin, 'Borin')}.")
check("cited_by: pagina prima, poi elementi", [(t.kind, t.id) for t in repo.cited_by("character", borin)] == [("page", page), ("character", aria)])
repo.save_text(aria, "appearance", "")
check("save_text vuoto: campo tolto", set(repo.texts(aria)) == {"history"})
check("indice: ricalcolato (gilda sparita)", (aria, "organization", gilda) not in mention())
check("save_text: elemento inesistente", raises(repo.save_text, 9999, "history", "x"))
check("save_text: nessuna riga orfana", repo._conn.execute("SELECT COUNT(*) FROM element_text WHERE element_id = 9999").fetchone()[0] == 0)

# --- relazioni ---------------------------------------------------------------------------
r1 = repo.add_relation(borin, aria)       # ordine inverso di proposito: a_id < b_id
rows = repo.relations(aria)
check("relazione: visibile da una parte", [(r.other.id, r.label) for r in repo.relations(aria)] == [(borin, "")])
check("relazione: visibile dall'altra", [(r.other.id) for r in repo.relations(borin)] == [aria])
check("relazione: salvata una volta", repo._conn.execute("SELECT COUNT(*) FROM relation").fetchone()[0] == 1)
check("relazione: duplicato (anche invertito) rifiutato", raises(repo.add_relation, aria, borin) and raises(repo.add_relation, borin, aria))
check("relazione: con se stesso rifiutata", raises(repo.add_relation, aria, aria))
check("relazione: con elemento inesistente rifiutata", raises(repo.add_relation, aria, 9999))
repo.update_relation(r1, label="Compagno d'armi")
check("update label", repo.relations(borin)[0].label == "Compagno d'armi")
check("update label lungo: tagliato a 200", (repo.update_relation(r1, label="x" * 500), len(repo.relations(aria)[0].label))[1] == 200)
check("update stato non valido", raises(repo.update_relation, r1, status="boh"))
check("update campo sconosciuto", raises(repo.update_relation, r1, color="red"))
check("update vuoto", raises(repo.update_relation, r1))
check("update relazione inesistente", raises(repo.update_relation, 9999, label="x"))
r2 = repo.add_relation(gilda, aria)
repo.update_relation(r2, status="deserter", note="Fuggita", leader=True)
rel = [r for r in repo.relations(gilda) if r.other.id == aria][0]
check("membro: stato/nota/capo", (rel.status, rel.note, rel.leader) == ("deserter", "Fuggita", True))
repo.update_relation(r2, leader=False)
check("leader spento", [r for r in repo.relations(aria) if r.other.id == gilda][0].leader is False)
check("ordine: per creazione", [r.other.id for r in repo.relations(aria)] == [borin, gilda])
repo.remove_relation(r1)
check("remove_relation", [r.other.id for r in repo.relations(aria)] == [gilda])
repo.remove_relation(9999)
check("remove_relation inesistente: nessun errore", True)

# --- eliminazioni -------------------------------------------------------------------------
repo.save_text(cora, "notes", f"Odia {link('place', alba, 'Alba')} e {link('character', aria, 'Aria')}.")
repo.save_content(page, f"Vedi {link('place', alba, 'Alba')} e {link('character', borin, 'Borin')}.")
repo.delete_element(alba)
check("elimina luogo: link tolto dalla scheda di Aria", "gmj://place" not in repo.texts(aria)["history"] and "Nata ad Alba" in repo.texts(aria)["history"])
check("elimina luogo: link tolto dalla scheda di Cora", repo.texts(cora)["notes"] == f"Odia Alba e {link('character', aria, 'Aria')}.")
check("elimina luogo: link tolto dalla pagina", "gmj://place" not in repo.page(page).content and "Vedi Alba" in repo.page(page).content)
check("elimina luogo: indici puliti", repo._conn.execute("SELECT COUNT(*) FROM element_mention WHERE target_kind = 'place'").fetchone()[0] == 0
      and repo._conn.execute("SELECT COUNT(*) FROM mention WHERE target_kind = 'place'").fetchone()[0] == 0)
repo.delete_element(aria)
check("elimina personaggio: testi, relazioni e indice spariti", all(repo._conn.execute(q).fetchone()[0] == 0 for q in (
    f"SELECT COUNT(*) FROM element_text WHERE element_id = {aria}", "SELECT COUNT(*) FROM relation",
    f"SELECT COUNT(*) FROM element_mention WHERE element_id = {aria}")))
check("elimina personaggio: link tolto dalla scheda di Cora", repo.texts(cora)["notes"] == "Odia Alba e Aria.")
check("cora non cita più nessuno", repo.cited_by("character", aria) == [])
repo.delete_page(page)
check("elimina pagina: nessun errore, indice pulito", repo._conn.execute("SELECT COUNT(*) FROM mention").fetchone()[0] == 0)
# eliminare un elemento senza citazioni non tocca gli altri
repo.save_text(borin, "history", "Niente link.")
before = repo._conn.execute("SELECT modified_at FROM element WHERE id = ?", (borin,)).fetchone()[0]
repo.delete_element(cora)
check("elimina senza citazioni: altri intatti", repo.texts(borin) == {"history": "Niente link."}
      and repo._conn.execute("SELECT modified_at FROM element WHERE id = ?", (borin,)).fetchone()[0] == before)
check("integrità chiavi esterne", repo._conn.execute("PRAGMA foreign_key_check").fetchall() == [])
repo.close()
print(f"\n{sum(ok)}/{len(ok)} prove superate")
sys.exit(0 if all(ok) else 1)
