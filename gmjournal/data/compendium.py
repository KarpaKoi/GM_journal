"""Lettura dei file XML di schede tecniche nel formato «compendio» (Fight Club 5e, Game Master 5e, Encounter+…).

Un file può contenere altro oltre ai mostri (oggetti, incantesimi…): si leggono solo i `<monster>`. I file reali hanno qualche
errore di battitura nei nomi dei campi e valori sporchi: qui si accettano le varianti note e si prende ciò che c'è, senza fermarsi.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..dnd import ABILITIES, ABILITY_DEFAULT, FEATURE_KEYS, size_name
from .db import DatabaseError
from .models import CreatureInput, Feature

# Varianti dei nomi dei campi (in minuscolo) → nome corretto.
_ALIASES = {"sense": "senses", "skills": "skill", "resistance": "resist", "immunity": "immune", "imune": "immune", "environemnt": "environment"}
LARGE_FILE = 300       # da quante schede un file è «grosso»: prima di importarlo si chiede conferma
_SOURCE = re.compile(r"\bSource:\s*(.*)\Z", re.DOTALL)


def _text(element: ET.Element | None) -> str:
    """Il testo di un campo con gli spazi in eccesso tolti: le righe si ripuliscono, le righe vuote doppie diventano una."""
    if element is None:
        return ""
    lines = [line.strip() for line in "".join(element.itertext()).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _number(text: str, default: int | None) -> int | None:
    match = re.search(r"\d+", text)
    return int(match.group()) if match else default


def _feature(section: str, element: ET.Element) -> Feature:
    texts = [_text(text) for text in element.findall("text")]
    return Feature(section, _text(element.find("name")), "\n".join(text for text in texts if text))


def _creature(monster: ET.Element) -> CreatureInput:
    fields: dict[str, ET.Element] = {}
    for child in monster:
        tag = child.tag.lower()
        if tag not in FEATURE_KEYS:
            fields.setdefault(_ALIASES.get(tag, tag), child)          # se un campo è doppio vale il primo
    text = {tag: _text(element) for tag, element in fields.items()}
    description = text.get("description", "")
    found = _SOURCE.search(description)
    notes, source = (description[:found.start()].strip(), " ".join(found.group(1).split())) if found else (description, "")
    return CreatureInput(
        name=text.get("name", ""), size=size_name(text.get("size", "")), kind=text.get("type", ""), alignment=text.get("alignment", ""),
        armor_class=text.get("ac", ""), hit_points=text.get("hp", ""), speed=text.get("speed", ""),
        abilities=tuple(_number(text.get(key, ""), ABILITY_DEFAULT) for key in ABILITIES),
        saves=text.get("save", ""), skills=text.get("skill", ""), vulnerabilities=text.get("vulnerable", ""),
        resistances=text.get("resist", ""), immunities=text.get("immune", ""), condition_immunities=text.get("conditionimmune", ""),
        senses=text.get("senses", ""), passive=_number(text.get("passive", ""), None), languages=text.get("languages", ""),
        challenge=text.get("cr", ""), environment=text.get("environment", ""), source=source, notes=notes,
        features=tuple(_feature(child.tag.lower(), child) for child in monster if child.tag.lower() in FEATURE_KEYS))


def read_compendium(path: Path) -> list[CreatureInput]:
    """Tutte le schede contenute nel file, nell'ordine in cui compaiono. Un file che non si legge o senza schede è un errore chiaro."""
    creatures = []
    try:
        for _, element in ET.iterparse(path):
            if element.tag == "monster":
                creatures.append(_creature(element))
                element.clear()          # un compendio completo pesa decine di MB: non si tiene in memoria tutto l'albero
    except (ET.ParseError, OSError) as error:
        raise DatabaseError(f"Non riesco a leggere «{path.name}»: non sembra un file di schede valido. Dettaglio: {error}") from error
    creatures = [creature for creature in creatures if creature.name]
    if not creatures:
        raise DatabaseError(f"In «{path.name}» non ho trovato nessuna scheda.")
    return creatures
