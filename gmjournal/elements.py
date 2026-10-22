"""I quattro tipi di elemento (personaggio, luogo, organizzazione, cultura): i loro nomi, i testi e la scheda di ciascuno.

Le schermate, i popup e il selettore dei collegamenti leggono i testi da qui, così un tipo si descrive in un posto solo.
"""

from dataclasses import dataclass

from . import sections, theme
from .data import links

# Le schede interne (tab) di una scheda: chiave (la sceglie la schermata), nome e icona.
PROFILE, STORY, MEMBERS, IMAGES, RELATIONS, MAPS = "profile", "story", "members", "images", "relations", "maps"
DESCRIPTION = "description"     # la scheda di una cultura: un solo testo libero, con titoli suggeriti
NOTES = "notes"     # il testo «Appunti liberi» in fondo al profilo (c'è in tutte le schede)


@dataclass(frozen=True)
class Tab:
    key: str
    label: str
    icon: str


@dataclass(frozen=True)
class Field:
    """Un campo di testo del profilo."""
    key: str                  # nome del campo nel database (tabella element_text)
    label: str
    placeholder: str = "Scrivi qui…"
    quote: bool = False       # una frase da citare: carattere con le grazie, corsivo
    wide: bool = False        # occupa tutta la riga del suo gruppo
    leaders: bool = False     # non si scrive: elenca i membri segnati come leader nella scheda «Membri»


@dataclass(frozen=True)
class Group:
    """Un riquadro del profilo con il suo titolo e i suoi campi."""
    title: str
    icon: str
    fields: tuple[Field, ...]
    columns: int = 1          # quante colonne di campi ha il riquadro
    gm: bool = False          # «Per il GM»: sfondo e titolo viola
    weight: int = 1           # larghezza rispetto ai riquadri vicini (2 = il doppio di 1)


# Come si mostra lo stato di un membro di un'organizzazione: nome e colore. Le chiavi sono quelle di data/models.py.
MEMBER_STATES = {
    "active": ("Attivo", "#7fcfc8"),
    "deserter": ("Disertore", "#e3b878"),
    "deceased": ("Defunto", "#a3a8b5"),
}


@dataclass(frozen=True)
class ElementKind:
    key: str            # tipo nei dati e nei collegamenti (vedi data/links.py)
    section: str        # chiave della schermata (vedi sections.py)
    noun: str           # «personaggio»
    the: str            # «il personaggio»
    a: str              # «un personaggio»
    new: str            # «Nuovo personaggio»
    none: str           # «Nessun personaggio»
    first: str          # «Crea il primo personaggio»
    empty_text: str     # spiegazione sotto «Nessun personaggio»
    name_hint: str      # esempio nel campo del nome
    brief_hint: str     # suggerimento nel campo «In breve»
    tabs: tuple[Tab, ...] = ()        # le schede interne, nell'ordine in cui compaiono
    groups: tuple[Group, ...] = ()    # i riquadri del profilo
    related: tuple[str, ...] = ()     # i tipi di elemento elencati in «Relazioni»
    suggestions: tuple[str, ...] = ()   # titoli proposti sopra il testo libero (un clic li inserisce): solo schede con DESCRIPTION
    has_role: bool = False
    portrait: str = "Copertina"       # com'è chiamata la prima immagine collegata: «Ritratto» per i personaggi

    @property
    def color(self) -> str:
        return theme.SECTION_COLORS[self.section]

    @property
    def icon(self) -> str:
        return sections.BY_KEY[self.section].icon

    @property
    def title(self) -> str:
        """Il nome della schermata: «Personaggi»."""
        return sections.BY_KEY[self.section].label


_IMAGES_TAB = Tab(IMAGES, "Immagini", "image")
_RELATIONS_TAB = Tab(RELATIONS, "Relazioni", "share")

KINDS = {kind.key: kind for kind in (
    ElementKind(
        links.CHARACTER, "personaggi", "personaggio", "il personaggio", "un personaggio", "Nuovo personaggio", "Nessun personaggio",
        "Crea il primo personaggio", "Aggiungi i personaggi della tua campagna: alleati, nemici, comparse.", "Es. Mira Vesperi",
        "Due righe per ricordare chi è: compariranno nella scheda e nel popup sulle mappe.", has_role=True, portrait="Ritratto",
        tabs=(Tab(PROFILE, "Profilo", "user"), Tab(STORY, "Storia", "book-open"), _IMAGES_TAB, _RELATIONS_TAB),
        related=(links.CHARACTER, links.PLACE, links.ORGANIZATION, links.CULTURE),
        groups=(
            Group("Aspetto", "eye", (
                Field("appearance", "Aspetto"),
                Field("mannerisms", "Voci e manierismi"),
                Field("quote", "Frase tipica", quote=True))),
            Group("Personalità", "heart", (
                Field("character", "Carattere"),
                Field("ideals", "Ideali"),
                Field("bonds", "Legami"),
                Field("flaws", "Difetti"))),
            Group("Per il GM", "sticky-note", (
                Field("goals", "Obiettivi personali"),
                Field("hooks", "Agganci di trama", "Idee per collegarla alla storia dei giocatori…")), gm=True),
        )),
    ElementKind(
        links.PLACE, "luoghi", "luogo", "il luogo", "un luogo", "Nuovo luogo", "Nessun luogo",
        "Crea il primo luogo", "Aggiungi città, foreste, locande e dungeon della tua campagna.", "Es. Varenhold",
        "Due righe per ricordare com’è: compariranno nella scheda e nel popup sulle mappe.",
        tabs=(Tab(PROFILE, "Descrizione", "book-open"), _IMAGES_TAB, Tab(MAPS, "Mappe", "map"), _RELATIONS_TAB),
        related=(links.CHARACTER, links.PLACE, links.ORGANIZATION, links.CULTURE),
        groups=(
            Group("Generale", "globe", (
                Field("population", "Popolazione"),
                Field("climate", "Clima"),
                Field("government", "Governo"),
                Field("religion", "Religione"),
                Field("organizations", "Organizzazioni", wide=True)), columns=2, weight=7),
            Group("Per il GM", "sticky-note", (
                Field("services", "Servizi"),
                Field("dangers", "Pericoli"),
                Field("hooks", "Agganci di trama", "Idee per portare i giocatori qui…")), gm=True, weight=5),
        )),
    ElementKind(
        links.ORGANIZATION, "organizzazioni", "organizzazione", "l’organizzazione", "un’organizzazione", "Nuova organizzazione",
        "Nessuna organizzazione", "Crea la prima organizzazione", "Aggiungi ordini, gilde, fazioni e governi della tua campagna.",
        "Es. Ordine della Fiamma", "Due righe per ricordare cos’è: compariranno nella scheda e nel popup sulle mappe.",
        tabs=(Tab(PROFILE, "Profilo", "flag"), Tab(MEMBERS, "Membri", "users"), _IMAGES_TAB, _RELATIONS_TAB),
        related=(links.PLACE, links.ORGANIZATION, links.CULTURE),      # i personaggi sono nei Membri
        groups=(
            Group("Identità", "shield", (
                Field("symbol", "Simbolo"),
                Field("seat", "Sede"),
                Field("leader", "Leader", leaders=True),
                Field("affiliates", "Affiliati")), columns=2),
            Group("Agenda", "target", (
                Field("objectives", "Obiettivi"),
                Field("methods", "Metodi"),
                Field("resources", "Risorse"),
                Field("ideals", "Ideali")), columns=2),
        )),
    ElementKind(
        links.CULTURE, "culture", "cultura", "la cultura", "una cultura", "Nuova cultura", "Nessuna cultura",
        "Crea la prima cultura", "Aggiungi i popoli, le religioni, le razze e le lingue del tuo mondo.", "Es. Valesi del Delta",
        "Una o due frasi per ricordarla al volo: chi sono, dove vivono, che cosa li distingue.",
        tabs=(Tab(DESCRIPTION, "Descrizione", "book-open"), _IMAGES_TAB, _RELATIONS_TAB),
        related=(links.CHARACTER, links.PLACE, links.ORGANIZATION, links.CULTURE),
        suggestions=("Origine", "Territori", "Lingue", "Aspetto", "Società", "Valori", "Credenze e culto", "Economia", "Usanze",
                     "Nomi tipici", "Feste e riti", "Tabù")),
)}
BY_SECTION = {kind.section: kind for kind in KINDS.values()}
