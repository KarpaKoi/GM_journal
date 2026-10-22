"""Passo 11c, dati: migrazione v10 (parole delle pagine, elenco «Da fare»), conteggio delle parole al salvataggio, voci «Da fare»."""
from harness import *
app()
import sqlite3, tempfile
from datetime import datetime
from pathlib import Path
from gmjournal.data import db, plain
from gmjournal.data.db import DatabaseError
from gmjournal.data.models import ElementInput
from gmjournal.data.repository import TODO_MAX, Repository

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def fails(fn):
    try:
        fn()
    except DatabaseError:
        return True
    return False

# ---------- il testo semplice ----------
check("plain_text: paragrafi, a capo e celle sono separati da uno spazio",
      plain.plain_text("<p>uno</p><p>due<br>tre</p><table><tr><th>a</th><td>b</td></tr></table>") == "uno due tre a b")
check("plain_text: i tag in riga non spezzano le parole, le entità si leggono",
      plain.plain_text('<p>Cor<b>vo</b> &amp; <a href="gmj://page/1">Locanda</a></p>') == "Corvo & Locanda")
check("count_words: «dell'Ordine» è una parola sola, i simboli non contano",
      plain.count_words("<p>La <b>Locanda</b> del Corvo, dell'Ordine &amp; dell’Alba - 3 volte</p>") == 8)
check("count_words: testo vuoto, solo tag, solo immagine", plain.count_words("") == 0 and plain.count_words("<p></p>") == 0 and plain.count_words('<p><img src="immagini/x.png"></p>') == 0)

# ---------- migrazione v9 -> v10 ----------
tmp = Path(tempfile.mkdtemp(prefix="gmj_writing_"))
old = tmp / "vecchia"; old.mkdir()
conn = sqlite3.connect(old / db.DB_FILENAME, isolation_level=None); conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
for version in range(1, 10):
    for step in db.MIGRATIONS[version - 1]:
        step(conn) if callable(step) else conn.execute(step)
    conn.execute(f"PRAGMA user_version = {version}")
conn.execute("INSERT INTO campaign (id,name,description,color,image,modified_at) VALUES (1,'Vecchia','','blue',NULL,'2026-01-01T00:00:00+00:00')")
conn.execute("INSERT INTO page (id, parent_id, position, title, content, modified_at) VALUES "
             "(1, NULL, 0, 'La Locanda', '<p>La sala era silenziosa.</p><p>Poi la porta si aprì.</p>', '2026-03-04T10:00:00+00:00'),"
             "(2, 1, 0, 'L''arrivo', '', '2026-03-05T10:00:00+00:00')")
conn.close()
repo = Repository.open(old)
check("migrazione: si apre all'ultima versione", repo._conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION >= 10)
check("migrazione: copia di sicurezza v9", (old / "campagna.v9.bak").exists())
pages = {p.id: p for p in repo.pages()}
check("migrazione: le parole delle pagine già scritte sono contate", pages[1].words == 9 and pages[2].words == 0)
check("migrazione: la data di modifica resta quella di prima", pages[1].modified_at == datetime.fromisoformat("2026-03-04T10:00:00+00:00"))
check("migrazione: l'elenco «Da fare» c'è ed è vuoto", repo.todos() == [])
repo.close()

# ---------- parole e date delle pagine ----------
repo = new_repo("ProvaScrittura")
chapter = repo.create_page("Capitolo")
check("una pagina nuova ha zero parole e una data", repo.pages()[0].words == 0 and isinstance(repo.pages()[0].modified_at, datetime))
repo.save_content(chapter, "<p>Una due tre</p><p>quattro</p>")
check("al salvataggio le parole si contano", repo.pages()[0].words == 4)
repo.save_content(chapter, "<p>Una</p>")
check("e si riconteggiano quando il testo cambia", repo.pages()[0].words == 1)
repo.rename_page(chapter, "Un titolo molto lungo di più parole")
check("rinominare non cambia le parole (il titolo non conta)", repo.pages()[0].words == 1)
mira = repo.create_element(ElementInput("character", "Mira", repo.categories("character")[0].id, None, "", ""))
repo.save_content(chapter, f'<p>Ciao <a href="gmj://character/{mira}">Mira</a> amica</p>')
check("un collegamento conta come le sue parole", repo.pages()[0].words == 3)
repo.delete_element(mira)
check("eliminato l'elemento citato il collegamento diventa testo: stesse parole", repo.pages()[0].words == 3 and "gmj://" not in repo.page(chapter).content)
sub = repo.create_page("Sotto", chapter)
repo.save_content(sub, "<p>cinque parole in un sottocapitolo</p>")
check("le parole di un sottocapitolo sono sue", {p.id: p.words for p in repo.pages()} == {chapter: 3, sub: 5})

# ---------- «Da fare» ----------
check("all'inizio nessuna voce", repo.todos() == [])
a = repo.add_todo("  Stampare   la pianta  ")
b = repo.add_todo("Disegnare la mappa")
c = repo.add_todo("Preparare le trappole")
check("la voce nuova va in cima; gli spazi si ripuliscono", [t.text for t in repo.todos()] == ["Preparare le trappole", "Disegnare la mappa", "Stampare la pianta"])
check("nessuna è fatta", not any(t.done for t in repo.todos()))
repo.set_todo_done(b, True)
check("spuntata: passa tra le fatte, in fondo alla lista", [(t.text, t.done) for t in repo.todos()] ==
      [("Preparare le trappole", False), ("Stampare la pianta", False), ("Disegnare la mappa", True)])
repo.set_todo_done(a, True)
check("l'ultima spuntata è la prima delle fatte", [t.id for t in repo.todos() if t.done] == [a, b])
repo.set_todo_done(a, False)
check("tolta la spunta: torna in cima alle aperte", [t.id for t in repo.todos()] == [a, c, b] and [t.done for t in repo.todos()] == [False, False, True])
repo.rename_todo(c, "Preparare tre trappole")
check("si rinomina", repo.todos()[1].text == "Preparare tre trappole" and repo.todos()[1].id == c)
check("testo vuoto rifiutato (all'aggiunta e alla modifica)", fails(lambda: repo.add_todo("   ")) and fails(lambda: repo.rename_todo(c, "")))
check("il testo rifiutato non cambia nulla", len(repo.todos()) == 3 and repo.todos()[1].text == "Preparare tre trappole")
long_id = repo.add_todo("x" * (TODO_MAX + 50))
check("il testo si accorcia", next(t for t in repo.todos() if t.id == long_id).text == "x" * TODO_MAX)
repo.delete_todo(long_id)
check("si elimina", long_id not in [t.id for t in repo.todos()])
repo.delete_todo(9999)
check("eliminare una voce che non c'è non è un errore", len(repo.todos()) == 3)
check("rinominare o spuntare una voce che non c'è dà un errore chiaro", fails(lambda: repo.rename_todo(9999, "x")) and fails(lambda: repo.set_todo_done(9999, True)))
check("le scritture aggiornano «Modificata…»", repo.campaign().modified_at >= datetime.fromisoformat("2026-01-01T00:00:00+00:00").replace(tzinfo=None).astimezone())

# ---------- le voci stanno nel backup ----------
from gmjournal.data import backup
target = tmp / "prova.gmj"
backup.save_backup(repo.folder, target)
restored = Repository.open(backup.restore_backup(target).folder)
check("un backup riporta anche l'elenco «Da fare» e le parole", [(t.text, t.done) for t in restored.todos()] == [(t.text, t.done) for t in repo.todos()]
      and [p.words for p in restored.pages()] == [p.words for p in repo.pages()])
print(f"\n{sum(ok)}/{len(ok)}")
