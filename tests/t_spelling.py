"""Passo 11b, motore dell'ortografia: quali parole sono sbagliate (dizionario italiano, apostrofi, nomi della campagna, «Ignora»)."""
from harness import *
app()
import time
from gmjournal import spelling
from gmjournal.data.models import ElementInput

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

def wrong(speller, text, links=()):
    return [text[a:b] for a, b in speller.errors(text, links)]

# --- Il dizionario ----------------------------------------------------------------------------------
start = time.perf_counter()
check("il dizionario italiano si carica", spelling.load_dictionary())
print(f"  (caricato in {time.perf_counter() - start:.2f} s)")
check("risulta caricato e non mancante", spelling.is_loaded() and not spelling.is_missing())
check("caricarlo di nuovo è immediato e non rifà il lavoro", (lambda t0: (spelling.load_dictionary(), time.perf_counter() - t0)[1] < 0.05)(time.perf_counter()))

repo = new_repo("Ortografia")
spelling.NAMES_TTL = 0.0                      # nelle prove i nomi nuovi si vedono subito
speller = repo.speller
check("la campagna ha un solo controllo (sempre lo stesso oggetto)", repo.speller is speller)
check("senza nomi: «Aldric» e «Zorbax» sono sbagliate", wrong(speller, "Aldric e Zorbax") == ["Aldric", "Zorbax"])

# --- Parole giuste e sbagliate ----------------------------------------------------------------------
check("parole italiane con accenti giuste", wrong(speller, "perché è già città più però così") == [])
check("accento sbagliato: «perchè»", wrong(speller, "perchè e perché") == ["perchè"])
check("«un'altra» e «l'arrivo» giusti", wrong(speller, "un'altra volta, l'arrivo, dell'ordine, all'alba") == [])
check("«un'altro» è sbagliato (apostrofo dritto)", wrong(speller, "un'altro uomo") == ["un'altro"])
check("«un’altro» è sbagliato (apostrofo tipografico): stessa cosa", wrong(speller, "un’altro uomo") == ["un’altro"])
check("«un’altra» e «l’arrivo» giusti (apostrofo tipografico)", wrong(speller, "un’altra volta, l’arrivo, dell’Ordine") == [])
check("«po'» giusto anche con l'apostrofo in fondo", wrong(speller, "un po' di pane, un po’ di vino") == [])
check("una parola fra apici è controllata senza gli apici", wrong(speller, "disse 'ciao' e 'qwxyz'") == ["qwxyz"])
check("l'intervallo non include l'apostrofo finale", wrong(speller, "qwxyz' fine") == ["qwxyz"])
check("numeri, lettere sole e sigle di 1–2 lettere non si controllano", wrong(speller, "12 a b XY GM 3d6 1500") == [])
check("una parola con cifre in mezzo: si controllano le parti di lettere", wrong(speller, "qwx123 perché") == ["qwx"])
check("maiuscolo iniziale e tutto maiuscolo ammessi per parole del dizionario", wrong(speller, "Città CITTÀ Perché") == [])
check("due lettere minuscole sconosciute sono sbagliate", wrong(speller, "zq") == ["zq"])
check("posizioni giuste in un testo con più errori", speller.errors("ciao qwxyz casa zzzzy", ()) == [(5, 10), (16, 21)])
check("andare a capo (U+2028) separa le parole", wrong(speller, "ciao qwxyz") == ["qwxyz"])

# --- Nomi della campagna ----------------------------------------------------------------------------
cats = repo.categories("character")
repo.create_element(ElementInput("character", "Aldric", cats[0].id, None, "", ""))
check("il nome di un personaggio è giusto", wrong(speller, "Aldric entra") == [])
check("anche scritto minuscolo o maiuscolo", wrong(speller, "aldric ALDRIC") == [])
check("con elisione: «dell'Aldric», «l’Aldric», «all'Aldric»", wrong(speller, "dell'Aldric, l’Aldric, all'Aldric") == [])
check("«un'Aldric» non si può giudicare: resta sbagliato", wrong(speller, "un'Aldric") == ["un'Aldric"])
check("«Zorbax» è ancora sbagliato", wrong(speller, "Zorbax") == ["Zorbax"])
repo.create_page("La Locanda dello Zorbax")
repo.create_map("Karthia")
repo.create_graph("Intrighi di Velmora")
check("un titolo di pagina, una mappa e un grafo sono giusti (parola per parola)",
      wrong(speller, "Zorbax Karthia Velmora Intrighi") == [])
repo.create_page("Dell'Ordine Fiammeo")
check("anche le parole di un titolo con apostrofo: «Fiammeo»", wrong(speller, "Fiammeo") == [])
repo.create_element(ElementInput("place", "L'Arrivo Lento", repo.categories("place")[0].id, None, "", ""))
check("un nome che inizia con l'elisione: «Arrivo» e «L'arrivo»", wrong(speller, "Lento l'Arrivo l’arrivo") == [])

# --- Collegamenti -----------------------------------------------------------------------------------
text = "vai da Qwxyzia con Zzzyx"
check("senza collegamenti entrambe sono sbagliate", wrong(speller, text) == ["Qwxyzia", "Zzzyx"])
check("una parola dentro un collegamento non si controlla", wrong(speller, text, [(7, 14)]) == ["Zzzyx"])
check("una parola che inizia dentro il collegamento non si controlla", wrong(speller, text, [(6, 10)]) == ["Zzzyx"])
check("una parola che finisce dove il collegamento comincia si controlla", wrong(speller, text, [(14, 19)]) == ["Qwxyzia", "Zzzyx"])

# --- Ignora questa volta ----------------------------------------------------------------------------
speller.ignore("Qwxyzia")
check("«Ignora questa volta»: la parola non è più sbagliata", wrong(speller, "Qwxyzia qwxyzia") == [])
other = new_repo("Ortografia2")
check("vale in tutti i testi, anche di un'altra campagna", wrong(other.speller, "Qwxyzia") == [])
speller.ignore("dell'Fakeword")
check("con elisione si ignora solo il nome", wrong(speller, "Fakeword dell'Fakeword") == [])
check("le altre parole restano sbagliate", wrong(speller, "Qwxyzia Zzzyx") == ["Zzzyx"])
spelling._Dictionary.ignored.clear(); spelling._Dictionary.ignored_version += 1
check("ripartendo (parole ignorate azzerate) tornano sbagliate", wrong(speller, "Qwxyzia") == ["Qwxyzia"])

# --- Senza dizionario -------------------------------------------------------------------------------
saved = spelling._Dictionary.hunspell
spelling._Dictionary.hunspell, spelling._Dictionary.missing = None, True
check("dizionario mancante: nessuna parola è sbagliata", wrong(speller, "Qwxyzia zzzyx") == [] and not speller.ready)
check("dizionario mancante: risulta mancante", spelling.is_missing() and not spelling.is_loaded())
spelling._Dictionary.hunspell, spelling._Dictionary.missing = saved, False
check("dizionario di nuovo presente", wrong(speller, "Qwxyzia") == ["Qwxyzia"] and speller.ready)

# --- Velocità ---------------------------------------------------------------------------------------
sentence = ("La sala della Locanda era più silenziosa del solito quando la porta si aprì e un viandante entrò lentamente "
            "nell'ombra, perché nessuno parlava ad alta voce. ")
words = sentence.split()
big = " ".join(words[i % len(words)] for i in range(36000))      # circa 215 KB
spelling.NAMES_TTL = 3.0                      # per misurare la velocità vera: i nomi si rileggono ogni 3 s, non a ogni parola
fresh = new_repo("Veloce").speller
start = time.perf_counter()
errors = fresh.errors(big)
first = time.perf_counter() - start
start = time.perf_counter()
fresh.errors(big)
second = time.perf_counter() - start
print(f"  ({len(big) // 1024} KB, {len(big.split())} parole: prima volta {first:.2f} s, poi {second:.2f} s)")
check("una pagina di 215 KB, prima volta, si controlla in meno di 3 s", first < 3)
check("la stessa pagina la seconda volta in meno di 1 s (parole già note)", second < 1)
visible = " ".join(words * 6)          # il testo che si vede in una finestra: circa 3 KB
start = time.perf_counter()
for _ in range(20):
    fresh.errors(visible)
check("il testo in vista (circa 3 KB) si ricontrolla in meno di 15 ms", (time.perf_counter() - start) / 20 < 0.015)

print(f"\n{sum(ok)}/{len(ok)}")
