"""Prove dei dati di Impostazioni: categorie (crea, rinomina, colore, riordina, elimina con spostamento) e tipi di pin (anche l'icona)."""
from harness import *
app()
from gmjournal.data import db, links
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import ElementInput, PinInput
from gmjournal.data.repository import NAME_MAX, Repository

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def fails(fn):
    try:
        fn()
    except DatabaseError:
        return True
    return False

repo = new_repo("ProvaImpostazioni")
check("il database è all'ultima versione (il passo 8 non ha aggiunto migrazioni)", db.SCHEMA_VERSION >= 9)

# ---------- categorie ----------
names = lambda kind: [c.name for c in repo.categories(kind)]
check("categorie di partenza dei luoghi", names(links.PLACE) == ["Città", "Natura", "Dungeon", "Edifici"])
usage = repo.category_usage(links.PLACE)
check("l'uso di ogni categoria parte da zero", sorted(usage.values()) == [0, 0, 0, 0])

taverne = repo.create_category(links.PLACE, "  Taverne  ", "amber")
check("nuova categoria in fondo, senza spazi ai bordi", names(links.PLACE)[-1] == "Taverne" and repo.categories(links.PLACE)[-1].color == "amber")
check("le categorie degli altri tipi non cambiano", len(repo.categories(links.CHARACTER)) == 4 and len(repo.categories(links.ORGANIZATION)) == 4)
check("il nome non può essere vuoto", fails(lambda: repo.create_category(links.PLACE, "   ", "blue")))
long_id = repo.create_category(links.PLACE, "x" * 300, "gray")
check("un nome troppo lungo viene accorciato", len(repo.categories(links.PLACE)[-1].name) == NAME_MAX)
repo.delete_category(long_id)

repo.update_category(taverne, "Locande", "pink")
check("rinominare e cambiare colore", (lambda c: (c.name, c.color))(next(c for c in repo.categories(links.PLACE) if c.id == taverne)) == ("Locande", "pink"))
check("rinominare con nome vuoto è rifiutato", fails(lambda: repo.update_category(taverne, "", "pink")))
check("una categoria che non esiste: errore chiaro", fails(lambda: repo.update_category(99999, "A", "blue")) and fails(lambda: repo.move_category(99999, 1))
      and fails(lambda: repo.delete_category(99999)))

# ---------- riordinare ----------
ids = [c.id for c in repo.categories(links.PLACE)]
repo.move_category(taverne, -1)
check("sposta su di un posto", [c.id for c in repo.categories(links.PLACE)] == ids[:3] + [taverne, ids[3]])
repo.move_category(taverne, -3)
check("spostare di più posti arriva in cima", repo.categories(links.PLACE)[0].id == taverne)
repo.move_category(taverne, -1)
check("in cima, «su» non fa nulla", repo.categories(links.PLACE)[0].id == taverne)
repo.move_category(taverne, 99)
check("«giù» oltre il fondo si ferma in fondo", repo.categories(links.PLACE)[-1].id == taverne)
repo.move_category(taverne, 1)
check("in fondo, «giù» non fa nulla", repo.categories(links.PLACE)[-1].id == taverne)
check("lo spostamento non tocca gli altri tipi", names(links.CHARACTER) == ["Protagonisti", "Alleati", "Antagonisti", "Neutrali"])
positions = [r[0] for r in repo._conn.execute("SELECT position FROM category WHERE kind = ? ORDER BY position", (links.PLACE,))]
check("le posizioni restano in fila (0, 1, 2…)", positions == list(range(len(positions))))

# ---------- eliminare ----------
citta = next(c.id for c in repo.categories(links.PLACE) if c.name == "Città")
natura = next(c.id for c in repo.categories(links.PLACE) if c.name == "Natura")
varenhold = repo.create_element(ElementInput(links.PLACE, "Varenhold", citta, None, "", ""))
brumal = repo.create_element(ElementInput(links.PLACE, "Brumal", citta, None, "", ""))
check("conteggio d'uso", repo.category_usage(links.PLACE)[citta] == 2 and repo.category_usage(links.PLACE)[natura] == 0)
check("eliminare una categoria usata senza dire dove spostare è rifiutato", fails(lambda: repo.delete_category(citta)) and fails(lambda: repo.delete_category(citta, citta)))
check("…e nulla è cambiato", repo.element(varenhold).category_id == citta and citta in {c.id for c in repo.categories(links.PLACE)})
mondo = repo.categories(links.CHARACTER)[0].id
check("non si può spostare gli elementi in una categoria di un altro tipo", fails(lambda: repo.delete_category(citta, mondo)) and repo.category_usage(links.PLACE)[citta] == 2)
check("né in una che non esiste", fails(lambda: repo.delete_category(citta, 99999)))
before = repo.element(varenhold)
repo.delete_category(citta, natura)
check("eliminata: gli elementi passano alla categoria scelta", repo.element(varenhold).category_id == natura and repo.element(brumal).category_id == natura
      and citta not in {c.id for c in repo.categories(links.PLACE)})
check("…il resto dell'elemento è intatto", repo.element(varenhold).name == before.name)
check("una categoria non usata si elimina senza dire altro", repo.delete_category(taverne) is None and taverne not in {c.id for c in repo.categories(links.PLACE)})
positions = [r[0] for r in repo._conn.execute("SELECT position FROM category WHERE kind = ? ORDER BY position", (links.PLACE,))]
check("dopo l'eliminazione le posizioni sono di nuovo in fila", positions == list(range(len(positions))))
rest = [c.id for c in repo.categories(links.PLACE)]
for category_id in rest[:-1]:
    repo.delete_category(category_id, rest[-1])
check("l'ultima categoria di un tipo non si elimina", fails(lambda: repo.delete_category(rest[-1], rest[-1])) and len(repo.categories(links.PLACE)) == 1)
check("…e gli elementi sono tutti nell'ultima", {e.category_id for e in repo.elements(links.PLACE)} == {rest[-1]})
check("i collegamenti nel testo usano ID: spostare gli elementi non li rompe", repo.link_target(links.PLACE, varenhold).name == "Varenhold"
      and repo.link_target(links.PLACE, varenhold).detail == repo.categories(links.PLACE)[0].name)

# ---------- tipi di pin ----------
types = lambda: [t.name for t in repo.pin_types()]
check("tipi di pin di partenza", types() == ["Luogo", "Persona", "Evento", "Missione"])
tesoro = repo.create_pin_type("  Tesoro ", "gem", "amber")
check("nuovo tipo in fondo", types()[-1] == "Tesoro")
check("il nome del tipo non può essere vuoto", fails(lambda: repo.create_pin_type(" ", "gem", "amber")))
repo.update_pin_type(tesoro, "Bottino", "crown", "violet")
t = next(t for t in repo.pin_types() if t.id == tesoro)
check("rinomina, icona e colore del tipo", (t.name, t.icon, t.color) == ("Bottino", "crown", "violet"))
check("modifica di un tipo che non esiste: errore", fails(lambda: repo.update_pin_type(99999, "A", "gem", "blue")) and fails(lambda: repo.move_pin_type(99999, 1)))
repo.move_pin_type(tesoro, -4)
check("riordinare i tipi", types()[0] == "Bottino" and types()[1:] == ["Luogo", "Persona", "Evento", "Missione"])
repo.move_pin_type(tesoro, -1)
check("in cima, «su» non fa nulla", types()[0] == "Bottino")

mappa = repo.create_map("Regno", None, None)
luogo = repo.pin_types()[1].id
persona = repo.pin_types()[2].id
repo.create_pin(mappa, 0.1, 0.1, PinInput(luogo, "Torre", "", None, None))
repo.create_pin(mappa, 0.2, 0.2, PinInput(luogo, "Ponte", "", None, None))
repo.create_pin(mappa, 0.3, 0.3, PinInput(persona, "Oste", "", None, None))
usage = repo.pin_type_usage()
check("conteggio dei pin per tipo", usage[luogo] == 2 and usage[persona] == 1 and usage[tesoro] == 0)
check("eliminare un tipo usato senza dire dove spostare è rifiutato", fails(lambda: repo.delete_pin_type(luogo)) and fails(lambda: repo.delete_pin_type(luogo, luogo)))
check("…o con un tipo che non esiste", fails(lambda: repo.delete_pin_type(luogo, 99999)))
repo.delete_pin_type(luogo, persona)
check("eliminato: i pin passano all'altro tipo", repo.pin_type_usage()[persona] == 3 and luogo not in {t.id for t in repo.pin_types()}
      and {p.type_id for p in repo.pins(mappa)} == {persona})
check("…e i pin restano dove erano", sorted(p.name for p in repo.pins(mappa)) == ["Oste", "Ponte", "Torre"])
repo.delete_pin_type(tesoro)
positions = [r[0] for r in repo._conn.execute("SELECT position FROM pin_type ORDER BY position")]
check("tipo non usato: si elimina senza spostare; posizioni in fila", tesoro not in {t.id for t in repo.pin_types()} and positions == list(range(len(positions))))
rest = [t.id for t in repo.pin_types()]
for type_id in rest[:-1]:
    repo.delete_pin_type(type_id, rest[-1])
check("l'ultimo tipo di pin non si elimina", fails(lambda: repo.delete_pin_type(rest[-1], rest[-1])) and len(repo.pin_types()) == 1)
check("i pin esistono ancora tutti", len(repo.pins(mappa)) == 3 and {p.type_id for p in repo.pins(mappa)} == {rest[-1]})
check("un pin nuovo con un tipo eliminato è rifiutato", fails(lambda: repo.create_pin(mappa, 0.5, 0.5, PinInput(luogo, "X", "", None, None))))

# ---------- salvataggio ----------
folder = repo.folder
repo.close()
repo = Repository.open(folder)
check("le modifiche restano dopo la chiusura e la riapertura", len(repo.categories(links.PLACE)) == 1 and len(repo.pin_types()) == 1)
repo.close()

print(f"{sum(ok)}/{len(ok)}")
