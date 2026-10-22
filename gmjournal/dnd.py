"""Regole di D&D 5e: caratteristiche, taglie, sezioni di una scheda tecnica, modificatori, punti esperienza e difficoltà di un incontro."""

from dataclasses import dataclass

from .formatting import thousands

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_LABELS = ("FOR", "DES", "COS", "INT", "SAG", "CAR")      # nell'ordine di ABILITIES
ABILITY_MIN, ABILITY_MAX = 1, 30
ABILITY_DEFAULT = 10

SIZES = ("Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan")
_SIZE_CODES = {"T": "Tiny", "S": "Small", "M": "Medium", "L": "Large", "H": "Huge", "G": "Gargantuan"}

TRAIT, ACTION, REACTION, LEGENDARY = "trait", "action", "reaction", "legendary"
# Le sezioni di una scheda, nell'ordine in cui si leggono: (chiave, titolo). I tratti, in una scheda stampata, non hanno titolo.
FEATURE_SECTIONS = ((TRAIT, "Tratti"), (ACTION, "Azioni"), (REACTION, "Reazioni"), (LEGENDARY, "Azioni leggendarie"))
FEATURE_KEYS = {key for key, _ in FEATURE_SECTIONS}

FIELD_MAX = 300      # lunghezza massima dei campi brevi di una scheda (nome della velocità, sensi, fonte…)
TEXT_MAX = 20000     # lunghezza massima dei testi lunghi (una capacità, la descrizione)

# Punti esperienza per grado di sfida (Dungeon Master's Guide, 2014). Il grado 0 vale 0 o 10 PE secondo il manuale: nel calcolo della
# difficoltà si usa 10, così anche i mostri più deboli pesano un poco.
_XP = {
    "0": 10, "1/8": 25, "1/4": 50, "1/2": 100, "1": 200, "2": 450, "3": 700, "4": 1100, "5": 1800, "6": 2300, "7": 2900, "8": 3900,
    "9": 5000, "10": 5900, "11": 7200, "12": 8400, "13": 10000, "14": 11500, "15": 13000, "16": 15000, "17": 18000, "18": 20000,
    "19": 22000, "20": 25000, "21": 33000, "22": 41000, "23": 50000, "24": 62000, "25": 75000, "26": 90000, "27": 105000,
    "28": 120000, "29": 135000, "30": 155000,
}


def size_name(code: str) -> str:
    """La taglia per esteso: «M» → «Medium». Un testo che non è un codice noto resta com'è."""
    code = code.strip()
    return _SIZE_CODES.get(code.upper(), code)


def modifier(score: int) -> int:
    return (score - ABILITY_DEFAULT) // 2


def ability_text(score: int) -> str:
    """«21 (+5)», «8 (−1)»."""
    mod = modifier(score)
    return f"{score} ({'+' if mod >= 0 else '−'}{abs(mod)})"


def xp_label(challenge: str) -> str:
    """I punti esperienza di un grado di sfida come si leggono in una scheda: «5.900 PE». Vuoto se il grado non è noto."""
    xp = _XP.get(challenge)
    if xp is None:
        return ""
    return "0 o 10 PE" if challenge == "0" else f"{thousands(xp)} PE"


# --- Difficoltà di un incontro di combattimento (Dungeon Master's Guide, 2014, capitolo 13) ---------------------------------

LEVEL_MIN, LEVEL_MAX = 1, 20
PLAYERS_MAX = 20            # giocatori in un gruppo di pari livello
QUANTITY_MAX = 99           # quante copie della stessa creatura in un incontro

TRIVIAL, EASY, MEDIUM, HARD, DEADLY = "trivial", "easy", "medium", "hard", "deadly"
DIFFICULTIES = (EASY, MEDIUM, HARD, DEADLY)         # i livelli del manuale, dal più lieve al più duro
DIFFICULTY_LABELS = {TRIVIAL: "Banale", EASY: "Facile", MEDIUM: "Medio", HARD: "Difficile", DEADLY: "Mortale"}

# Soglie di PE per ogni personaggio, per livello: (facile, medio, difficile, mortale).
_THRESHOLDS = {
    1: (25, 50, 75, 100), 2: (50, 100, 150, 200), 3: (75, 150, 225, 400), 4: (125, 250, 375, 500), 5: (250, 500, 750, 1100),
    6: (300, 600, 900, 1400), 7: (350, 750, 1100, 1700), 8: (450, 900, 1400, 2100), 9: (550, 1100, 1600, 2400),
    10: (600, 1200, 1900, 2800), 11: (800, 1600, 2400, 3600), 12: (1000, 2000, 3000, 4500), 13: (1100, 2200, 3400, 5100),
    14: (1250, 2500, 3800, 5700), 15: (1400, 2800, 4300, 6400), 16: (1600, 3200, 4800, 7200), 17: (2000, 3900, 5900, 8800),
    18: (2100, 4200, 6300, 9500), 19: (2400, 4900, 7300, 10900), 20: (2800, 5700, 8500, 12700),
}
_MULTIPLIERS = (0.5, 1, 1.5, 2, 2.5, 3, 4)          # dal più basso al più alto
_STEP_STARTS = (2, 3, 7, 11, 15)                    # da quanti mostri si passa a ×1,5, ×2, ×2,5, ×3, ×4 (con un solo mostro è ×1)


@dataclass(frozen=True)
class Assessment:
    """Com'è fatto il calcolo della difficoltà, passo per passo (serve a mostrarlo)."""
    players: int
    thresholds: tuple[int, ...]     # PE del gruppo per facile, medio, difficile, mortale (nell'ordine di DIFFICULTIES)
    monsters: int                   # le creature che contano (quelle con un grado di sfida noto)
    unrated: int                    # creature senza grado di sfida, escluse dal calcolo
    xp: int                         # PE dei mostri, senza moltiplicatore
    multiplier: float
    adjusted: int                   # PE modificati: ciò che si confronta con le soglie
    difficulty: str                 # una chiave di DIFFICULTY_LABELS; vuota se non c'è nessun mostro che conti


def challenge_xp(challenge: str) -> int | None:
    """I PE di un grado di sfida; None se il grado non è noto."""
    return _XP.get(challenge.strip())


def monster_multiplier(monsters: int, players: int) -> float:
    """Il moltiplicatore per il numero di mostri; con meno di 3 giocatori si sale di un gradino, con più di 5 si scende."""
    step = 1 + sum(monsters >= start for start in _STEP_STARTS)
    if players < 3:
        step += 1
    elif players > 5:
        step -= 1
    return _MULTIPLIERS[max(0, min(len(_MULTIPLIERS) - 1, step))]


def assess(party: list[tuple[int, int]], monsters: list[tuple[str, int]]) -> Assessment:
    """La difficoltà di un combattimento. `party`: (livello, quanti giocatori); `monsters`: (grado di sfida, quante copie)."""
    players = sum(count for _, count in party)
    thresholds = tuple(sum(_THRESHOLDS[level][step] * count for level, count in party) for step in range(len(DIFFICULTIES)))
    rated = [(xp, quantity) for challenge, quantity in monsters if (xp := challenge_xp(challenge)) is not None]
    count = sum(quantity for _, quantity in rated)
    xp = sum(value * quantity for value, quantity in rated)
    multiplier = monster_multiplier(count, players)
    adjusted = round(xp * multiplier)
    difficulty = ""
    if count and players:
        difficulty = TRIVIAL
        for key, threshold in zip(DIFFICULTIES, thresholds):
            if adjusted >= threshold:
                difficulty = key
    return Assessment(players, thresholds, count, sum(quantity for _, quantity in monsters) - count, xp, multiplier, adjusted, difficulty)
