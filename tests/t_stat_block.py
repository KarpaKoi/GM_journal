"""Prove della scheda tecnica: breve resta a una colonna, molto lunga si divide in due (equilibrate, senza sovrapposizioni, senza titoli
rimasti soli in fondo), sotto una certa larghezza torna a una colonna; poi come sta nella pagina della scheda e dentro un incontro."""
from harness import *
app()
from dataclasses import fields
from PySide6.QtWidgets import QLabel
from gmjournal.data.models import Creature, CreatureInput, Encounter, Feature, Slot
from gmjournal.ui.widgets.creature_detail import CreatureDetail
from gmjournal.ui.widgets.encounter_detail import EncounterDetail
from gmjournal.ui.widgets.stat_block import BLOCK_WIDTH, COLUMN_GAP, COLUMN_WIDTH, LONG_HEIGHT, TWO_COLUMN_MIN, StatBlock, _MARGIN_X, _MARGIN_Y

ok = []
def check(name, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name)

TEXT = "The creature makes a melee attack with its claws, then a second attack with its tail, and finally breathes a gout of flame in a long cone. "

def make(creature_id, name, traits, actions, legendary=0, multiplier=1):
    features = [Feature("trait", f"Tratto {n}", TEXT * multiplier) for n in range(traits)]
    features += [Feature("action", f"Azione {n}", TEXT * multiplier) for n in range(actions)]
    features += [Feature("legendary", f"Leggendaria {n}", TEXT * multiplier) for n in range(legendary)]
    data = CreatureInput(name, "Huge", "dragon", "lawful evil", "22 (natural armor)", "546 (28d20+252)", "walk 40 ft., fly 80 ft.", (30, 10, 29, 18, 15, 23),
                         "Dex +7, Con +16", "Perception +16", "", "", "fire", "", "darkvision 120 ft.", 26, "Common, Draconic", "17", "", "", "", tuple(features))
    return Creature(**{f.name: getattr(data, f.name) for f in fields(data)}, id=creature_id)

def block_of(creature, width):
    block = StatBlock()
    block.set_creature(creature)
    block.resize(width, block.heightForWidth(width))
    block.show()
    pump(50)
    return block

def spots(block):
    """Le caselle (x, y, larghezza, altezza) dei pezzi, nell'ordine."""
    return [part.widget.geometry() for part in block._parts]

short, long_ = make(1, "Goblin", 1, 1), make(2, "Drago antico", 4, 6, 4, 2)

# --- breve o molto lunga ----------------------------------------------------------------------------------------
small, big = StatBlock(), StatBlock()
small.set_creature(short); big.set_creature(long_)
check("una scheda breve non è «molto lunga»; una lunga sì", not small.long and big.long)
check("la soglia è l'altezza a una colonna (400): la lunga la supera, la breve no", big._stack(big._heights(COLUMN_WIDTH - 2 * _MARGIN_X), 0, len(big._parts)) + 2 * _MARGIN_Y > LONG_HEIGHT
      and small.heightForWidth(COLUMN_WIDTH) < LONG_HEIGHT)
check("a 720 la breve resta a una colonna, la lunga si divide", small._plan(BLOCK_WIDTH).split == len(small._parts) and big._plan(BLOCK_WIDTH).split < len(big._parts))
check("la lunga, in due colonne, è molto più bassa che in una", big.heightForWidth(BLOCK_WIDTH) < 0.7 * big.heightForWidth(COLUMN_WIDTH))
check("sotto la larghezza minima anche la lunga resta a una colonna", big._plan(TWO_COLUMN_MIN - 1).split == len(big._parts) and big._plan(TWO_COLUMN_MIN).split < len(big._parts))
check("sizeHint: 720 di larghezza e l'altezza giusta per quella larghezza", big.sizeHint().width() == BLOCK_WIDTH == small.sizeHint().width()
      and big.sizeHint().height() == big.heightForWidth(BLOCK_WIDTH) and big.hasHeightForWidth())

# --- la lunga a 720: dove stanno i pezzi ----------------------------------------------------------------------------
block = block_of(long_, BLOCK_WIDTH)
plan = block._plan(BLOCK_WIDTH)
boxes = spots(block)
first, second = boxes[:plan.split], boxes[plan.split:]
check("due colonne larghe uguali, la seconda a destra della prima, con lo spazio in mezzo", {b.width() for b in boxes} == {plan.column}
      and {b.left() for b in first} == {_MARGIN_X} and {b.left() for b in second} == {_MARGIN_X + plan.column + COLUMN_GAP}
      and second[0].right() + 1 + _MARGIN_X == BLOCK_WIDTH)
check("ogni colonna comincia in alto e i pezzi non si sovrappongono", first[0].top() == _MARGIN_Y == second[0].top()
      and all(a.bottom() < b.top() for column in (first, second) for a, b in zip(column, column[1:])))
check("tutto sta dentro la scheda, e l'altezza è quella che la scheda ha detto", all(b.bottom() <= block.height() - _MARGIN_Y for b in boxes)
      and max(b.bottom() for b in boxes) + 1 + _MARGIN_Y == block.height())
check("le due colonne sono equilibrate", abs(first[-1].bottom() - second[-1].bottom()) < 160)
check("un titolo non resta solo in fondo alla prima colonna", not block._parts[plan.split - 1].keep and block._parts[plan.split - 1].widget.isVisible())
check("in nessuna larghezza un titolo resta solo in fondo alla prima colonna",
      all(not (p := block._plan(w)).split < len(block._parts) or not block._parts[p.split - 1].keep for w in range(TWO_COLUMN_MIN, 1100, 7)))
check("nessun testo è tagliato: ogni etichetta è alta quanto serve", all(label.height() >= label.heightForWidth(label.width())
      for label in block.findChildren(QLabel) if label.wordWrap()))
one_column = block_of(long_, 500)
check("il testo c'è tutto: stesse etichette a una e due colonne", [l.text() for l in block.findChildren(QLabel)] == [l.text() for l in one_column.findChildren(QLabel)]
      and all(part.widget.isVisible() for part in block._parts))

# --- altezza dichiarata = altezza reale, in ogni larghezza ---------------------------------------------------------------------
def bottom_of(width, creature=long_):
    b = block_of(creature, width)
    return max(box.bottom() for box in spots(b)) + 1 + _MARGIN_Y, b.height()
check("l'altezza per la larghezza corrisponde a quella davvero occupata (una e due colonne)",
      all(real == declared for real, declared in (bottom_of(w) for w in (300, 400, 679, 680, 720, 900, 1200))))
narrow = block_of(long_, 600)
check("a 600 una colonna sola, con tutti i pezzi uno sotto l'altro", all(a.bottom() < b.top() for a, b in zip(spots(narrow), spots(narrow)[1:])) and {b.left() for b in spots(narrow)} == {_MARGIN_X})

# --- la breve non cambia -------------------------------------------------------------------------------------------------------
quiet = block_of(short, BLOCK_WIDTH)
check("la breve: una colonna a tutta larghezza e nessun filetto di separazione", {b.left() for b in spots(quiet)} == {_MARGIN_X}
      and {b.width() for b in spots(quiet)} == {BLOCK_WIDTH - 2 * _MARGIN_X})
changed = StatBlock(); changed.set_creature(long_); changed.set_creature(short)
check("cambiando scheda da lunga a breve si torna a una colonna", not changed.long and changed._plan(BLOCK_WIDTH).split == len(changed._parts))

# --- la pagina della scheda ---------------------------------------------------------------------------------------------------------
page = CreatureDetail("")
page.resize(1100, 700); page.show(); pump(50)
page.show_creature(long_); pump(100)
check("pagina della scheda: la lunga è larga 720, in due colonne", page._block.width() == BLOCK_WIDTH and page._block._plan(page._block.width()).split < len(page._block._parts)
      and page._block.height() == page._block.heightForWidth(BLOCK_WIDTH))
page.show_creature(short); pump(100)
check("…la breve è larga 720 anche lei, a una colonna", page._block.width() == BLOCK_WIDTH and page._block._plan(BLOCK_WIDTH).split == len(page._block._parts))
page.resize(560, 700); page.show_creature(long_); pump(100)
check("in una finestra stretta la scheda si restringe e resta a una colonna, senza scorrere di lato", page._block.width() <= 560 and page.horizontalScrollBar().maximum() == 0
      and page._block._plan(page._block.width()).split == len(page._block._parts))

# --- dentro un incontro ------------------------------------------------------------------------------------------------------------------
detail = EncounterDetail()
detail.resize(1300, 900); detail.show(); pump(50)
detail.show_encounter(Encounter("Mix", "combat", (), (Slot(1, 2), Slot(2, 1)), 1), [short, long_]); pump(150)
low, high = detail.findChildren(StatBlock)
card_row = detail._cards
check("nell'incontro la scheda breve è larga 400, la lunga ne prende due (816) e va in due colonne", low.width() == COLUMN_WIDTH and high.width() == 2 * COLUMN_WIDTH + 16
      and high._plan(high.width()).split < len(high._parts))
check("la riga è alta quanto la scheda più alta e la lunga si vede intera", card_row.height() >= high.height()
      and high.mapTo(card_row.widget(), QPoint(0, 0)).y() + high.height() <= card_row.widget().height())
detail.show_encounter(Encounter("Solo breve", "combat", (), (Slot(1, 1),), 2), [short]); pump(100)
check("una sola scheda breve: 400 come prima", detail.findChildren(StatBlock)[0].width() == COLUMN_WIDTH)

print(f"{sum(ok)}/{len(ok)}")
