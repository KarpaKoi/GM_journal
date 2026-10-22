"""Prove dei dati delle schede tecniche: migrazione v11, creare/leggere/modificare/eliminare, pulizia dei dati, lettura dei file XML
(anche sporchi), importazione senza doppioni, copia e backup della campagna."""
from harness import *
app()
import sqlite3, tempfile
from dataclasses import replace
from pathlib import Path
from gmjournal.data import db
from gmjournal.data.backup import restore_backup, save_backup
from gmjournal.data.compendium import LARGE_FILE, read_compendium
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import CreatureInput, Feature
from gmjournal.data.repository import NAME_MAX, Repository, duplicate_campaign
from gmjournal.dnd import ABILITY_MAX, ABILITY_MIN, FIELD_MAX, TEXT_MAX, ability_text, size_name, xp_label
from gmjournal.ui.creature_files import import_summary

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def fails(fn):
    try:
        fn()
    except DatabaseError:
        return True
    return False

def sheet(name="Goblin", **changes):
    base = CreatureInput(name, "Small", "humanoid (goblinoid)", "neutral evil", "15 (leather armor, shield)", "7 (2d6)", "walk 30 ft.",
                         (8, 14, 10, 10, 8, 8), "", "Stealth +6", "", "", "", "", "darkvision 60 ft.", 9, "Common, Goblin", "1/4", "forest",
                         "Monster Manual p. 166", "Piccolo e cattivo.",
                         (Feature("trait", "Nimble Escape", "Disengage or Hide as a bonus action."),
                          Feature("action", "Scimitar", "Melee Weapon Attack: +4 to hit.\nHit: 5 (1d6 + 2) slashing damage."),
                          Feature("action", "Shortbow", "Ranged Weapon Attack: +4 to hit."),
                          Feature("reaction", "Redirect Attack", "Swap places with an ally.")))
    return replace(base, **changes)

tmp = Path(tempfile.mkdtemp(prefix="gmj_creatures_"))

# ---------- regole ----------
check("modificatori delle caratteristiche", (ability_text(21), ability_text(8), ability_text(10), ability_text(1)) == ("21 (+5)", "8 (−1)", "10 (+0)", "1 (−5)"))
check("taglie: dal codice al nome", (size_name("L"), size_name("t"), size_name("Medium"), size_name("")) == ("Large", "Tiny", "Medium", ""))
check("punti esperienza", (xp_label("10"), xp_label("1/8"), xp_label("0"), xp_label(""), xp_label("1/3")) == ("5.900 PE", "25 PE", "0 o 10 PE", "", ""))
check("riepilogo dell'importazione", (import_summary(3, 0), import_summary(1, 0), import_summary(2, 1), import_summary(2, 5), import_summary(0, 4), import_summary(5538, 0), import_summary(1, 2)) ==
      ("Importate 3 schede", "Importata 1 scheda", "2 importate, 1 già presente", "2 importate, 5 già presenti",
       "Nessuna scheda nuova: erano già tutte presenti.", "Importate 5.538 schede", "1 importata, 2 già presenti"))

# ---------- migrazione v10 -> v11 ----------
old = tmp / "vecchia"; old.mkdir()
conn = sqlite3.connect(old / db.DB_FILENAME, isolation_level=None); conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 11):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id,name,description,color,image,modified_at) VALUES (1,'Vecchia','','blue',NULL,'2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO graph (id, name) VALUES (1, 'Vecchio grafo')")
conn.close()
repo = Repository.open(old)
check("migrazione: la campagna si apre all'ultima versione", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION >= 11)
check("migrazione: copia di sicurezza v10", (old / "campagna.v10.bak").exists())
check("migrazione: i dati di prima restano", [g.name for g in repo.graphs()] == ["Vecchio grafo"])
check("migrazione: nessuna scheda all'inizio", repo.creatures() == [])
repo.close()

# ---------- creare e leggere ----------
repo = new_repo("ProvaSchede")
goblin = repo.create_creature(sheet())
c = repo.creature(goblin)
check("la scheda si legge com'è stata scritta",
      (c.name, c.size, c.kind, c.alignment, c.armor_class, c.hit_points, c.speed, c.abilities, c.skills, c.senses, c.passive, c.languages, c.challenge,
       c.environment, c.source, c.notes) == ("Goblin", "Small", "humanoid (goblinoid)", "neutral evil", "15 (leather armor, shield)", "7 (2d6)", "walk 30 ft.",
                                           (8, 14, 10, 10, 8, 8), "Stealth +6", "darkvision 60 ft.", 9, "Common, Goblin", "1/4", "forest",
                                           "Monster Manual p. 166", "Piccolo e cattivo."))
check("le capacità restano nell'ordine, con sezione e testo a più righe",
      [(f.section, f.name) for f in c.features] == [("trait", "Nimble Escape"), ("action", "Scimitar"), ("action", "Shortbow"), ("reaction", "Redirect Attack")]
      and c.features[1].text == "Melee Weapon Attack: +4 to hit.\nHit: 5 (1d6 + 2) slashing damage.")
check("la scheda di un ID che non c'è: errore chiaro", fails(lambda: repo.creature(9999)))

# ---------- pulizia dei dati ----------
messy = repo.create_creature(sheet("  zombie  ", size="  Medium ", kind="undead\nthing", abilities=(0, 99, -3, 10, 10, 10), passive=None,
                                   features=(Feature("trait", "  ", "  "), Feature("action", "Slam", " Hit. "), Feature("boh", "Strana", "sezione sconosciuta"))))
m = repo.creature(messy)
check("il nome si ripulisce", m.name == "zombie")
check("i campi brevi stanno su una riga", (m.size, m.kind) == ("Medium", "undead thing"))
check("le caratteristiche restano fra 1 e 30", m.abilities == (ABILITY_MIN, ABILITY_MAX, ABILITY_MIN, 10, 10, 10))
check("le capacità vuote o di una sezione sconosciuta spariscono", [(f.section, f.name, f.text) for f in m.features] == [("action", "Slam", "Hit.")])
check("la Percezione passiva può mancare", m.passive is None)
check("ci vuole un nome", fails(lambda: repo.create_creature(sheet("   "))))
long = repo.create_creature(sheet("x" * 200, source="s" * 1000, notes="n" * (TEXT_MAX + 50)))
check("i testi lunghi si accorciano", (len(repo.creature(long).name), len(repo.creature(long).source), len(repo.creature(long).notes)) == (NAME_MAX, FIELD_MAX, TEXT_MAX))
repo.delete_creature(long)

# ---------- elenco ----------
repo.create_creature(sheet("aboleth", size="Large", kind="aberration", challenge="10"))
names = [row.name for row in repo.creatures()]
check("elenco in ordine alfabetico, senza badare alle maiuscole", names == ["aboleth", "Goblin", "zombie"])
row = next(r for r in repo.creatures() if r.name == "aboleth")
check("l'elenco porta solo il necessario", (row.size, row.kind, row.challenge, row.source) == ("Large", "aberration", "10", "Monster Manual p. 166"))

# ---------- modificare ed eliminare ----------
repo.update_creature(goblin, sheet("Goblin Boss", challenge="1", features=(Feature("action", "Multiattack", "Two attacks."),)))
c = repo.creature(goblin)
check("la modifica cambia i dati", (c.name, c.challenge) == ("Goblin Boss", "1"))
check("la modifica sostituisce le capacità", [(f.section, f.name) for f in c.features] == [("action", "Multiattack")])
check("modificare una scheda che non c'è: errore chiaro", fails(lambda: repo.update_creature(9999, sheet())))
before = repo._conn.execute("SELECT COUNT(*) FROM creature_feature").fetchone()[0]
repo.delete_creature(goblin)
after = repo._conn.execute("SELECT COUNT(*) FROM creature_feature").fetchone()[0]
check("eliminata, la scheda sparisce con le sue capacità", goblin not in [r.id for r in repo.creatures()] and after == before - 1)
repo.delete_creature(9999)      # non è un errore: non c'è più

# ---------- file XML ----------
def write(name, text):
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    return path

xml = write("mostri.xml", """<?xml version="1.0"?>
<compendium version="5">
  <item><name>Arrow</name><type>A</type></item>
  <monster>
    <name>Aboleth</name><size>L</size><type>aberration</type><alignment>Lawful Evil</alignment>
    <ac>17 (natural armor)</ac><hp>135 (18d10+36)</hp><speed>walk 10 ft., swim 40 ft.</speed>
    <str>21</str><dex>9</dex><con>15</con><int>18</int><wis>15</wis><cha>18</cha>
    <save>Con +6, Int +8</save><skill>History +12</skill><passive>20</passive><languages>Deep Speech</languages><cr>10</cr>
    <resist/><immune/><vulnerable/><conditionImmune/><senses>darkvision 120 ft.</senses>
    <trait><name>Amphibious</name><text>
The aboleth can breathe air and water.</text></trait>
    <action><name>Tentacle</name><text>Melee Weapon Attack: +9 to hit.</text><text>Hit: 12 damage.</text><attack>Tentacle|+9|2d6+5</attack></action>
    <legendary><name>Detect</name><text>Wisdom check.</text></legendary>
    <description>Lore dell'aboleth.

Altro paragrafo.

Source:	Monster Manual p. 13,
		Tomb of Annihilation</description>
    <environment>underdark</environment>
  </monster>
  <monster>
    <name>Strano</name><size>SM</size><type>beast</type><str>abc</str><dex>12</dex><cr></cr><conditionimmune>charmed</conditionimmune>
    <imune>fire</imune><sense>blindsight 10 ft.</sense><skills>Stealth +1</skills><name>Doppio</name>
  </monster>
  <monster><name></name><size>M</size></monster>
</compendium>""")
items = read_compendium(xml)
check("si leggono solo i mostri (non gli oggetti) e si scarta chi non ha nome", [i.name for i in items] == ["Aboleth", "Strano"])
a = items[0]
check("campi base letti", (a.size, a.kind, a.alignment, a.armor_class, a.hit_points, a.speed, a.abilities, a.saves, a.skills, a.passive, a.languages, a.challenge, a.senses, a.environment) ==
      ("Large", "aberration", "Lawful Evil", "17 (natural armor)", "135 (18d10+36)", "walk 10 ft., swim 40 ft.", (21, 9, 15, 18, 15, 18), "Con +6, Int +8",
       "History +12", 20, "Deep Speech", "10", "darkvision 120 ft.", "underdark"))
check("le capacità: sezione, nome, testo (anche con più <text>)", [(f.section, f.name, f.text) for f in a.features] == [
      ("trait", "Amphibious", "The aboleth can breathe air and water."),
      ("action", "Tentacle", "Melee Weapon Attack: +9 to hit.\nHit: 12 damage."), ("legendary", "Detect", "Wisdom check.")])
check("la fonte si separa dalla descrizione", (a.source, a.notes) == ("Monster Manual p. 13, Tomb of Annihilation", "Lore dell'aboleth.\n\nAltro paragrafo."))
s = items[1]
check("file sporco: errori di battitura, valori che mancano, campi doppi", (s.size, s.abilities, s.challenge, s.condition_immunities, s.immunities, s.senses, s.skills, s.name) ==
      ("SM", (10, 12, 10, 10, 10, 10), "", "charmed", "fire", "blindsight 10 ft.", "Stealth +1", "Strano"))
check("un file che non è XML: errore chiaro", fails(lambda: read_compendium(write("rotto.xml", "<compendium><monster>"))))
check("un file senza schede: errore chiaro", fails(lambda: read_compendium(write("vuoto.xml", "<compendium><item><name>x</name></item></compendium>"))))
check("un file che non esiste: errore chiaro", fails(lambda: read_compendium(tmp / "non-c-e.xml")))

# ---------- importare ----------
repo2 = new_repo("ProvaImport")
result = repo2.import_creatures(items)
check("importate 2 schede", (result.added, result.skipped) == (2, 0) and [r.name for r in repo2.creatures()] == ["Aboleth", "Strano"])
check("l'importata si legge con le sue capacità", [f.name for f in repo2.creature(next(r.id for r in repo2.creatures() if r.name == "Aboleth")).features] == ["Amphibious", "Tentacle", "Detect"])
again = repo2.import_creatures(items)
check("riimportando le stesse schede non si aggiunge nulla", (again.added, again.skipped) == (0, 2) and len(repo2.creatures()) == 2)
changed = repo2.import_creatures([replace(items[0], hit_points="200 (20d10+90)"), replace(items[0], source="Un altro libro"),
                                  replace(items[0], features=items[0].features[:1]), replace(items[1], name="strano")])
check("stesso nome ma contenuto diverso (dati, fonte, capacità, maiuscole del nome) è un'altra scheda", (changed.added, changed.skipped) == (4, 0))
mixed = repo2.import_creatures([items[0], replace(items[0], name="Nuova"), items[1]])
check("in un file misto: 1 nuova, 2 già presenti", (mixed.added, mixed.skipped) == (1, 2))
twice = repo2.import_creatures([replace(items[0], name="Gemella"), replace(items[0], name="Gemella")])
check("due schede identiche nello stesso file: ne entra una", (twice.added, twice.skipped) == (1, 1))
check("un file grosso si riconosce", 1 < LARGE_FILE < 5538)
repo2.close()

# ---------- copia e backup della campagna ----------
folder = repo.folder
repo.close()
copy = duplicate_campaign(folder)
with Repository.open(copy) as r:
    check("duplicando la campagna le schede restano", [x.name for x in r.creatures()] == ["aboleth", "zombie"])
backup = tmp / "copia.gmj"
save_backup(folder, backup)
restored = restore_backup(backup)
with Repository.open(restored.folder) as r:
    names = [x.name for x in r.creatures()]
    check("il backup riporta le schede, con le capacità", names == ["aboleth", "zombie"] and [f.name for f in r.creature(next(x.id for x in r.creatures() if x.name == "aboleth")).features] != [])

print(f"{sum(ok)}/{len(ok)}")
