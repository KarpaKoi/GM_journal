# GM Journal – guida dettagliata

Come è fatto il programma, cosa sa fare e le scorciatoie.

## Struttura del codice

```
main.py                    avvio dell'app
assets/                    font (Figtree, Newsreader), icone SVG e dizionario italiano (`dictionaries/it_IT`)
gmjournal/
  app.py                   finestra principale e navigazione
  theme.py                 colori, misure, caratteri, foglio di stile
  icons.py                 caricamento e colore delle icone
  thumbnails.py            miniature delle immagini (lette una volta sola, in cache; `Thumb` le prepara quando il riquadro si disegna)
  sections.py              elenco delle schermate (nome, icona, colore)
  elements.py              testi, schede interne e campi di Personaggi / Luoghi / Organizzazioni
  spelling.py              il controllo ortografico: quali parole non sono nel dizionario italiano (senza interfaccia)
  data/                    database SQLite, modelli, lettura/scrittura, backup (`backup.py`), testo semplice di una pagina per contare le parole (`plain.py`), lettura dei file XML di schede tecniche (`compendium.py`)
  ui/shell/                barra superiore, barra sinistra, pannello destro
  ui/screens/              una schermata per file (Home, Scrittura, elenchi degli elementi…)
  ui/sheet/                la scheda di un elemento: intestazione, Profilo, Storia, Immagini, Mappe, Relazioni, Membri
  ui/editor/               l'editor di testo: formato di salvataggio, comandi, barra degli strumenti, tabelle (`table_ui.py`), onde rosse dell'ortografia (`spell_ui.py`), «Cerca nella pagina» (`find_ui.py`), anteprima dei collegamenti (`preview_ui.py`), box «Incontro» (`encounter_box.py`)
  ui/popups/               finestre di dialogo (campagna, capitolo, personaggio/luogo/organizzazione, cartelle e scelta delle immagini, mappa, tipo di pin, grafo, scheda tecnica, incontro e scelta delle schede, voci di Impostazioni, avanzamento)
  ui/widgets/              componenti riutilizzabili (card, tele di mappe e grafi, finestrelle dei pin, `group_label` per i titoletti, `search_field` = campo con icona della barra in alto, di «Cerca nella pagina» e di «Da fare», `writing_home` = elenco dei capitoli di Scrittura, `todo_panel` = «Da fare», `link_preview` = finestrella sul collegamento, `list_page` / `item_list` = elenco e dettaglio delle pagine di Incontri (quello degli incontri sta nella barra sinistra), `row_table` = elenco di righe disegnate a mano (base dell'elenco dei capitoli di Scrittura e di quello degli incontri), `encounter_home` = la schermata iniziale degli Incontri, `sidebar_list` = titoletto con «+» e voci della barra sinistra (Scrittura, Mappe, Grafi, Incontri), `stat_block` = la scheda tecnica come sui manuali (molto lunga: in due colonne), `difficulty_panel` = il blocco compatto della difficoltà di un incontro, accanto al titolo…)
  ui/backup_files.py       le finestre di sistema del backup (dove salvarlo, quale ripristinare)
  ui/creature_files.py     la finestra di sistema per scegliere i file XML di schede tecniche e i messaggi dell'importazione
  ui/link_sources.py       da dove l'editor e i campi prendono i collegamenti (@) e come creano un elemento nuovo
  ui/map_target.py         «cosa mostrare» sulle Mappe (una mappa, un pin, un luogo da posare): lo usano le schede e la schermata
  ui/graph_target.py       «cosa mostrare» sui Grafi (un grafo, un nodo o un arco)
  ui/encounter_target.py   «cosa mostrare» in Incontri (la pagina degli incontri o delle schede, e la voce scelta)
  ui/creature_items.py     come una scheda tecnica compare negli elenchi e come si cerca
  encounters.py            i due tipi di incontro (combattimento, interazione): nomi e icone
  graphs.py                costanti dei grafi (titolo e colore di un nodo nuovo, limiti dei testi, direzioni degli archi)
  dnd.py                   le regole di D&D 5e che servono alle schede tecniche (caratteristiche, taglie, sezioni, punti esperienza e difficoltà di un incontro con le regole del 2014)
  settings.py              le quattro liste di Impostazioni (categorie di personaggi, luoghi, organizzazioni; tipi di pin): testi e voci
  pins.py                  le icone fra cui scegliere per un tipo di pin
installer/                 icona, ricetta PyInstaller e script per costruire installer e versione portatile di Windows, e installer Linux
tests/                     prove automatiche senza schermo: `python tests/run_all.py` (le vecchie, `t_*.py`) e `python -m pytest tests` (quelle di sicurezza, `test_*.py`; serve `pip install pytest`). Non entra mai nei pacchetti
riferimento_old/           vecchio prototipo, solo da consultare
```


## Funzioni

Fatti: fondamenta (tema, finestra, barre, navigazione, database), Home con le campagne,
Scrittura (editor di testo, capitoli, collegamenti fra pagine), Personaggi, Luoghi e
Organizzazioni (categorie colorate, filtri, finestra di creazione/modifica, anteprima, collegamenti
con il testo, scheda completa con profilo, storia, immagini, relazioni e membri), ricerca globale per nome,
libreria Immagini (cartelle, importazione, dettagli con «Usata in», collegamento alle schede; il testo e la copertina della campagna scelgono le immagini dalla libreria),
Mappe (elenco a schede, mappe dentro mappe, mappa interattiva con zoom e pin di vari tipi, pin collegati a pagine ed elementi o che aprono un'altra mappa, scheda «Mappe» dei luoghi).
Grafi (elenco a schede, mappe mentali interattive con nodi liberi o collegati a pagine ed elementi, archi con etichetta e frecce (un arco può unire anche due etichette, o un nodo e un'etichetta), pannello di modifica del nodo e dell'arco; mappe e grafi si trovano anche con la ricerca),
Impostazioni (categorie di personaggi, luoghi e organizzazioni e tipi di pin: aggiungere, rinominare, colore, icona, riordinare, eliminare spostando ciò che le usa).
Incontri, prima consegna (schede tecniche di mostri e PNG di D&D 5e: elenco con ricerca, scheda a destra con l'aspetto dei manuali (carta beige, titoli rossi), compilazione a mano da un popup, importazione di uno o più file XML nel formato dei compendi di Fight Club / Game Master 5e, senza aggiungere due volte la stessa scheda; il testo importato resta in inglese). Seconda consegna: la schermata Incontri con due pagine («Incontri» e «Schede tecniche»); un incontro è di combattimento o di interazione, mostra solo le schede che servono (con le copie) e, nei combattimenti, la difficoltà calcolata con le regole di D&D 5e del 2014. Poi la nuova veste: l'elenco degli incontri passa nella barra sinistra e le schede di un incontro si affiancano in una riga che scorre di lato, ognuna alta quanto il suo testo. Infine la schermata iniziale degli Incontri (l'elenco di tutti gli incontri in una tabella) e le schede tecniche molto lunghe divise in due colonne. In Scrittura, dal menu «Box» si inserisce il box «Incontro» (riepilogo ed elenco delle creature; un clic apre l'incontro).
Backup (dal menu «⋯» di una campagna «Salva backup…» crea un file `.gmj` con database e immagini; in Home «Ripristina da backup…» lo rimette come campagna nuova, senza sovrascrivere nulla).
Scrittura, passo 11a: tabelle nel testo (griglia per sceglierne la misura, barra sopra la tabella con aggiungi/elimina riga e colonna, «+» ai bordi) ed evidenziatore a 6 colori; valgono anche in Storia e Appunti delle schede.
Scrittura, passo 11b: ortografia italiana (onda rossa sotto le parole che non sono nel dizionario, pulsante «Italiano» per accenderla e spegnerla, «Ignora questa volta» col clic destro; i nomi della campagna sono sempre giusti; nessun suggerimento né dizionario personale) e «Cerca nella pagina» (lente a destra nella barra: barra di ricerca con «1 di N», occorrenze evidenziate, solo in Scrittura).
Scrittura, passo 11c: schermata iniziale di Scrittura (titolo con riepilogo, elenco dei capitoli e sottocapitoli con parole e data dell'ultima modifica, freccia per aprire e chiudere i sottocapitoli, menu «⋯» per riga), elenco «Da fare» della campagna nel pannello destro (spunte, modifica con un clic, «x» per eliminare) e anteprima di un collegamento fermando il mouse su di esso (elemento, pagina, mappa o grafo).
Rifinitura (provato con una campagna molto grande — 300 pagine, 315 elementi, 221 immagini, 28 mappe con fino a 450 pin, grafi fino a 500 nodi — a 100%, 125% e 150%: miniature in cache, grafi più veloci e sempre inquadrabili, percorso di Immagini a briciole, filtri e modulo dei pin che non escono dalla mappa, pulizia del codice).

Il programma è completo ed è disponibile anche come installer (Windows e Linux). Possibili sviluppi: ricerca dentro i testi, backup automatici.


## Scorciatoie

Ctrl+K cerca per nome pagine, personaggi, luoghi, organizzazioni, mappe e grafi (frecce e Invio, o un clic, aprono il risultato; Esc chiude) · Ctrl+L collega il testo a una pagina o a un elemento · `@` nel testo propone
pagine, personaggi, luoghi, organizzazioni, mappe e grafi (e permette di crearli al volo) · Ctrl+clic su un collegamento lo apre · Ctrl+B / I / U grassetto, corsivo, sottolineato ·
Ctrl+Maiusc+0…3 paragrafo e titoli · Tab / Maiusc+Tab sposta una voce d'elenco di livello.
Tabelle: Tab / Maiusc+Tab vanno alla cella successiva / precedente (dopo l'ultima cella si aggiunge una riga), Invio va a capo dentro la cella; la barra sopra la tabella aggiunge righe e colonne e toglie la riga, la colonna o tutta la tabella del cursore (un clic, si annulla con Ctrl+Z; con una riga o una colonna sola i relativi pulsanti sono spenti).
Ortografia: «Italiano» (a destra nella barra degli strumenti) accende e spegne l'onda rossa; il clic destro su una parola sbagliata offre «Ignora questa volta» (vale finché il programma è aperto). Il dizionario si carica in circa 1 secondo, una volta sola, mentre si apre il primo editor (~85 MB di memoria): finché non è pronto non c'è nessuna onda.
Cerca nella pagina: la lente (a destra, accanto a «Italiano») apre la barra in alto a destra del testo; Invio va al risultato successivo, Esc la chiude (nessuna scorciatoia nuova: si apre solo dalla lente). Maiuscole e accenti non contano; cercando in una pagina si evidenziano tutte le occorrenze, la corrente in azzurro.
Elenco dei capitoli (schermata iniziale di Scrittura): un clic su una riga apre la pagina, la freccia di un capitolo apre o chiude i suoi sottocapitoli (finché la campagna è aperta), «⋯» apre il menu della pagina; «Scrittura» nella barra o «indietro» dalla pagina riportano qui.
Da fare: a destra nella schermata iniziale (e quando non c'è nessuna pagina aperta); si scrive nel campo e si preme Invio, la casella spunta la voce (passa sotto «Fatte»), un clic sul testo lo modifica (Invio conferma, Esc annulla), la «x» che compare passando il mouse sulla voce la elimina subito. Le voci sono della campagna, non delle pagine, e entrano nel backup.
Anteprima di un collegamento: fermando il mouse per circa mezzo secondo su un collegamento del testo compare una finestrella con chi è (immagine o iniziali, categoria, ruolo, «in breve» e in quante pagine è citato; per una pagina il percorso e le prime righe); sparisce scrivendo, scorrendo, cliccando o spostando il mouse. Ctrl+clic apre come prima.
Evidenziatore: il pulsante usa l'ultimo colore scelto, la freccia accanto apre i colori e «Togli l'evidenziatore»; lo stesso colore su un testo già evidenziato lo toglie.
Immagini: un clic sull'immagine la seleziona e mostra la barra 300 / 500 / 700 px (le stesse misure sono nel menu del clic destro).
Schede degli elementi: doppio clic su una tessera (o «Apri scheda») per aprirla; un clic su un campo lo rende modificabile,
Esc o un clic fuori lo chiude (si salva da solo).
Mappe: rotella = zoom (verso il puntatore), trascinare lo sfondo = spostarsi; un clic su un pin ne mostra la finestrella, trascinarlo lo sposta. Nella barra in alto a sinistra della mappa:
«Seleziona», «Aggiungi pin» (un clic sulla mappa posa il pin), «Sposta la mappa» (si trascina anche sopra i pin), ingrandisci e riduci.
Grafi: rotella = zoom, trascinare lo sfondo = spostarsi, trascinare un nodo lo sposta; nella barra in alto a sinistra «Seleziona», «Nodo» (un clic sulla tela crea il nodo), «Collega» (un clic su un nodo (o su un arco, cioè sulla sua etichetta) e uno sul secondo creano l'arco: un arco può finire anche su un altro arco), ingrandisci, riduci, «Inquadra tutto». Un clic su un nodo o su un arco ne mostra i campi nel pannello destro (si salva da solo); per un arco si sceglie anche la direzione della freccia.

Segnalibri e percorso: la stella in alto (accanto alla ricerca) aggiunge la pagina, l'elemento, la mappa, il grafo o l'incontro che stai guardando ai segnalibri, che compaiono sotto l'elenco nella barra sinistra (un clic li apre, la x al passaggio del mouse li toglie). Il percorso in alto è cliccabile: ogni tratto porta alla pagina o alla mappa corrispondente.
Backup: «Salva backup…» nel menu «⋯» di una card della Home (propone «Nome 2026-10-12.gmj»; la posizione non può essere dentro la cartella della campagna); «Ripristina da backup…» in alto a destra nella Home crea sempre una campagna nuova («Nome (ripristinata)» se il nome esiste già). Il file `.gmj` è uno zip: dentro ci sono `campagna.db` e le immagini.
Schede tecniche (sezione Incontri): «Nuova scheda» apre il popup (dati di base, sei caratteristiche, difese e capacità divise in Tratti, Azioni, Reazioni e Azioni leggendarie con «Aggiungi»); «Importa schede…» apre la finestra di sistema (anche più file XML insieme) e alla fine dice «Importate 3 schede» o «2 importate, 1 già presente»; un file con 300 schede o più chiede conferma (la campagna diventa più pesante: 5.500 schede pesano circa 15 MB). La ricerca filtra per nome, taglia, tipo e fonte.
Box «Incontro» in Scrittura: dal menu **Box › Incontro…** si sceglie un incontro per nome e compare nel testo come una scheda (icona, nome, tipo, giocatori e creature, difficoltà nel suo colore, e sotto l'elenco delle creature con le copie «×4»). Un **clic sulla scheda apre l'incontro** nella sezione Incontri; il tasto destro offre «Apri l'incontro» e «Togli il box dal testo»; Canc/Backspace lo tolgono come un'immagine. La scheda è sempre aggiornata (si rilegge dalla campagna): se l'incontro viene rinominato cambia anche lì, se viene eliminato resta un segnaposto «Incontro eliminato». Nel testo salvato c'è solo `<div class="encounter" data-id="N"></div>`.
Incontri (sezione Incontri, pagina «Incontri»): la sezione si apre su una **schermata iniziale con l'elenco di tutti gli incontri** (nome, tipo, creature, giocatori e difficoltà nel suo colore); un clic su una riga apre l'incontro, un clic sul titolo grande «Incontri» (o la voce «Incontri» della barra sinistra, o «indietro») riporta all'elenco; il titolo resta «Incontri» anche guardando le schede tecniche. Una **scheda tecnica molto lunga** (un drago, per esempio) si legge **in due colonne** come sui manuali, quando c'è posto: nella pagina delle schede, e dentro un incontro dove prende il posto di due schede; in una finestra stretta resta a una colonna. «Nuovo incontro» apre il popup: nome, tipo (Combattimento o Interazione), nel combattimento i giocatori presenti (gruppi «4 giocatori di livello 3», scritti a mano, non legati a Personaggi) e le schede tecniche da «Aggiungi schede…» (se ne scelgono più d'una insieme; ognuna ha le sue copie, «× 4»). L'elenco degli incontri sta nella barra sinistra, sotto le voci delle sezioni (titoletto «INCONTRI» con il «+» per crearne uno; ogni riga dice la difficoltà nel suo colore, e se si guardano le schede tecniche un clic su un incontro porta alla sua pagina). Nella pagina l'incontro mostra solo le schede scelte, **una accanto all'altra in una riga che scorre di lato** (Maiusc+rotella, gesto laterale del trackpad o barra di scorrimento; la rotella da sola scorre la pagina), ognuna alta quanto il suo testo, con sopra «×4 · 50 PE ciascuno»; e, nei combattimenti, **accanto al titolo** il blocco della difficoltà: Banale, Facile, Medio, Difficile o Mortale sopra la barra colorata, con il calcolo passo per passo in piccolo (PE dei mostri × moltiplicatore per il numero di mostri; con meno di 3 giocatori si sale di un gradino, con più di 5 si scende) e le quattro soglie (Facile, Medio, Difficile, Mortale) che si leggono passando il mouse sulla barra. Un grado di sfida 0 vale 10 PE; le creature senza grado di sfida non contano e l'incontro lo dice. Un nuovo combattimento riparte dai giocatori dell'ultimo (altrimenti 4 di livello 1). Eliminando una scheda tecnica sparisce anche dagli incontri che la usano (il popup della scheda dice in quali). L'eliminazione di un incontro si fa tenendo premuto il pulsante.
Impostazioni: pulsante in fondo alla barra sinistra; a sinistra si sceglie la lista, al centro le voci (frecce su/giù per l'ordine, matita o clic sulla riga per modificare; eliminando una voce in uso si sceglie dove spostare ciò che la usa).
