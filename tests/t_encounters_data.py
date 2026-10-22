"""Prove dei dati degli incontri: le regole di difficoltà 2014 (valori del manuale), migrazione v12, creare/leggere/modificare/eliminare,
pulizia dei dati, schede usate e schede eliminate, copia e backup della campagna."""
from harness import *
app()
import sqlite3, tempfile
from dataclasses import replace
from pathlib import Path
from gmjournal.data import db
from gmjournal.data.backup import restore_backup, save_backup
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import CreatureInput, EncounterInput, PartyGroup, Slot
from gmjournal.data.repository import NAME_MAX, Repository, duplicate_campaign
from gmjournal.dnd import DIFFICULTY_LABELS, QUANTITY_MAX, assess, challenge_xp, monster_multiplier
from gmjournal.encounters import COMBAT, INTERACTION

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def fails(fn):
    try:
        fn()
    except DatabaseError:
        return True
    return False

def creature(name, challenge="1/4"):
    return CreatureInput(name, "Small", "humanoid", "", "", "", "", (10,) * 6, "", "", "", "", "", "", "", None, "", challenge, "", "", "", ())

tmp = Path(tempfile.mkdtemp(prefix="gmj_encounters_"))

# ---------- regole: i valori del Dungeon Master's Guide ----------
check("moltiplicatori per numero di mostri (gruppo da 3 a 5)",
      [monster_multiplier(n, 4) for n in (1, 2, 3, 6, 7, 10, 11, 14, 15, 30)] == [1, 1.5, 2, 2, 2.5, 2.5, 3, 3, 4, 4])
check("meno di 3 giocatori: un gradino in più (fino a ×4)", [monster_multiplier(n, 2) for n in (1, 2, 3, 7, 11, 15)] == [1.5, 2, 2.5, 3, 4, 4])
check("più di 5 giocatori: un gradino in meno (un mostro solo = ×0,5)", [monster_multiplier(n, 6) for n in (1, 2, 3, 7, 11, 15)] == [0.5, 1, 1.5, 2, 2.5, 3])
check("punti esperienza dei gradi di sfida", (challenge_xp("0"), challenge_xp("1/8"), challenge_xp("1/2"), challenge_xp("5"), challenge_xp("30"),
                                              challenge_xp(" 2 "), challenge_xp(""), challenge_xp("1/3")) == (10, 25, 100, 1800, 155000, 450, None, None))
a = assess([(1, 4)], [("1/4", 1)])
check("soglie di un gruppo di 4 di livello 1", a.thresholds == (100, 200, 300, 400))
check("gruppo misto: le soglie si sommano", assess([(5, 3), (4, 1)], []).thresholds == (3 * 250 + 125, 3 * 500 + 250, 3 * 750 + 375, 3 * 1100 + 500))
check("livello 20", assess([(20, 1)], []).thresholds == (2800, 5700, 8500, 12700))
b = assess([(3, 4)], [("1", 3), ("1/2", 2)])      # 3×200 + 2×100 = 800 PE, 5 mostri → ×2 = 1600; soglie 300/600/900/1600
check("esempio completo: PE, moltiplicatore, PE modificati e difficoltà", (b.xp, b.monsters, b.multiplier, b.adjusted, b.difficulty) == (800, 5, 2, 1600, "deadly"))
check("senza mostri non c'è nessuna difficoltà", assess([(1, 4)], []).difficulty == "" and assess([(1, 4)], [("", 3)]).difficulty == "")
# 4 giocatori di livello 1: soglie 100 / 200 / 300 / 400
check("i confini: appena sotto «facile» è banale, una soglia raggiunta esattamente conta",
      [assess([(1, 4)], [(c, n)]).difficulty for c, n in (("1/4", 1), ("1/2", 1), ("1", 1), ("1/8", 6), ("1/4", 4), ("1/8", 8))] ==
      ["trivial", "easy", "medium", "hard", "deadly", "deadly"])      # 50; 100; 200; 6×25×2 = 300; 4×50×2 = 400; 8×25×2,5 = 500
check("creature senza grado di sfida: escluse e contate a parte", (lambda r: (r.monsters, r.unrated, r.xp))(assess([(3, 4)], [("1", 2), ("", 3)])) == (2, 3, 400))
check("nessun giocatore: niente difficoltà", assess([], [("1", 2)]).difficulty == "" and assess([], [("1", 2)]).players == 0)
check("tutte le difficoltà hanno un nome", set(DIFFICULTY_LABELS) == {"trivial", "easy", "medium", "hard", "deadly"})

# ---------- migrazione v11 -> v12 ----------
old = tmp / "vecchia"; old.mkdir()
conn = sqlite3.connect(old / db.DB_FILENAME, isolation_level=None); conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 12):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id,name,description,color,image,modified_at) VALUES (1,'Vecchia','','blue',NULL,'2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO creature (id, name) VALUES (1, 'Goblin')")
conn.close()
repo = Repository.open(old)
check("migrazione: la campagna si apre all'ultima versione", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION >= 12)
check("migrazione: copia di sicurezza v11", (old / "campagna.v11.bak").exists())
check("migrazione: le schede di prima restano e non ci sono incontri", [c.name for c in repo.creatures()] == ["Goblin"] and repo.encounters() == [])
repo.close()

# ---------- creare, leggere, modificare, eliminare ----------
repo = new_repo("ProvaIncontri")
goblin, wolf, ogre = (repo.create_creature(creature(n, c)) for n, c in (("Goblin", "1/4"), ("Wolf", "1/4"), ("Ogre", "2")))
party = (PartyGroup(3, 3), PartyGroup(4, 1))
eid = repo.create_encounter(EncounterInput("  Imboscata  ", COMBAT, party, (Slot(goblin, 4), Slot(wolf, 2))))
e = repo.encounter(eid)
check("l'incontro si legge com'è stato scritto", (e.name, e.kind, e.party, e.creatures) == ("Imboscata", COMBAT, party, (Slot(goblin, 4), Slot(wolf, 2))))
check("l'elenco ha l'incontro", [x.id for x in repo.encounters()] == [eid])
check("una campagna con incontri risulta modificata", repo.campaign().modified_at is not None)
tavern = repo.create_encounter(EncounterInput("a Taverna", INTERACTION, (PartyGroup(5, 4),), (Slot(ogre, 1),)))
t = repo.encounter(tavern)
check("un incontro di interazione non ha giocatori (anche se glieli si danno)", t.party == () and t.creatures == (Slot(ogre, 1),))
check("elenco in ordine alfabetico senza badare alle maiuscole", [x.name for x in repo.encounters()] == ["a Taverna", "Imboscata"])
repo.update_encounter(eid, EncounterInput("Imboscata II", COMBAT, (PartyGroup(5, 4),), (Slot(ogre, 1), Slot(goblin, 2))))
e = repo.encounter(eid)
check("modificato: nome, giocatori e schede cambiano, nell'ordine dato", (e.name, e.party, e.creatures) == ("Imboscata II", (PartyGroup(5, 4),), (Slot(ogre, 1), Slot(goblin, 2))))
repo.update_encounter(eid, replace(e, kind=INTERACTION))
check("passando a interazione i giocatori spariscono", repo.encounter(eid).party == ())
repo.update_encounter(eid, replace(e, kind=COMBAT, party=party))
check("e tornando a combattimento si possono rimettere", repo.encounter(eid).party == party)

# ---------- pulizia e regole dei dati ----------
check("ci vuole un nome", fails(lambda: repo.create_encounter(EncounterInput("  ", COMBAT, (), ()))))
check("il tipo dev'essere valido", fails(lambda: repo.create_encounter(EncounterInput("X", "party", (), ()))))
check("una scheda che non c'è: errore chiaro, nessun incontro in più", fails(lambda: repo.create_encounter(EncounterInput("X", COMBAT, (), (Slot(9999, 1),)))) and len(repo.encounters()) == 2)
check("modificare un incontro che non c'è: errore chiaro", fails(lambda: repo.update_encounter(9999, EncounterInput("X", COMBAT, (), ()))))
check("l'incontro che non c'è: errore chiaro", fails(lambda: repo.encounter(9999)))
messy = repo.create_encounter(EncounterInput("n" * 200, COMBAT, (PartyGroup(0, 0), PartyGroup(99, 500)), (Slot(goblin, 0), Slot(goblin, 3), Slot(wolf, 5000))))
m = repo.encounter(messy)
check("il nome si accorcia", len(m.name) == NAME_MAX)
check("livelli e numeri fuori dai limiti rientrano", m.party == (PartyGroup(1, 1), PartyGroup(20, 20)))
check("una scheda ripetuta diventa una riga sola con le copie sommate, nei limiti", m.creatures == (Slot(goblin, 3), Slot(wolf, QUANTITY_MAX)))
repo.delete_encounter(messy)

# ---------- schede usate, schede eliminate ----------
check("quali incontri usano una scheda", repo.encounters_using(goblin) == ["Imboscata II"] and repo.encounters_using(ogre) == ["a Taverna", "Imboscata II"])
check("una scheda non usata non è in nessun incontro", repo.encounters_using(repo.create_creature(creature("Orfano"))) == [])
repo.delete_creature(goblin)
check("eliminata una scheda, sparisce anche dagli incontri che la usavano", repo.encounter(eid).creatures == (Slot(ogre, 1),))
repo.delete_encounter(tavern)
check("eliminato un incontro, le sue schede restano", [x.id for x in repo.encounters()] == [eid] and ogre in [c.id for c in repo.creatures()])
check("eliminato un incontro, spariscono i suoi giocatori e le sue righe",
      repo._conn.execute("SELECT COUNT(*) FROM encounter_party WHERE encounter_id = ?", (tavern,)).fetchone()[0] == 0
      and repo._conn.execute("SELECT COUNT(*) FROM encounter_creature WHERE encounter_id = ?", (tavern,)).fetchone()[0] == 0)
repo.delete_encounter(9999)
check("eliminare un incontro che non c'è non è un errore", len(repo.encounters()) == 1)

# ---------- copia e backup della campagna ----------
folder = repo.folder
snapshot = [(x.name, x.kind, x.party, x.creatures) for x in repo.encounters()]
repo.close()
copy = duplicate_campaign(folder)
with Repository.open(copy) as r:
    check("duplicando la campagna gli incontri restano", [(x.name, x.kind, x.party, x.creatures) for x in r.encounters()] == snapshot)
backup = tmp / "copia.gmj"
save_backup(folder, backup)
restored = restore_backup(backup)
with Repository.open(restored.folder) as r:
    check("il backup riporta gli incontri, con giocatori e schede", [(x.name, x.kind, x.party, x.creatures) for x in r.encounters()] == snapshot)

print(f"{sum(ok)}/{len(ok)}")
