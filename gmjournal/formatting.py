"""Testi mostrati all'utente ricavati dai dati (date relative, plurali, iniziali)."""

import re
from datetime import datetime

_STOP_WORDS = {"di", "del", "dello", "della", "dell", "dei", "degli", "delle", "il", "la", "le", "lo", "i", "e"}


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural} fa"


def thousands(value: int) -> str:
    """Un numero con il punto sulle migliaia: 5900 → «5.900»."""
    return f"{value:,}".replace(",", ".")


def modified_label(moment: datetime, now: datetime | None = None) -> str:
    """«Modificata oggi», «Modificata ieri», «3 settimane fa»… (giorni di calendario locali)."""
    today = (now or datetime.now().astimezone()).astimezone().date()
    days = (today - moment.astimezone().date()).days
    if days <= 0:
        return "Modificata oggi"
    if days == 1:
        return "Modificata ieri"
    if days < 7:
        return f"Modificata {days} giorni fa"
    if days < 30:
        return "Modificata " + _plural(days // 7, "settimana", "settimane")
    if days < 365:
        return "Modificata " + _plural(days // 30, "mese", "mesi")
    return "Modificata " + _plural(days // 365, "anno", "anni")


_MONTHS = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")


def short_date(moment: datetime, now: datetime | None = None) -> str:
    """«oggi», «ieri», poi «9 ott» (con l'anno se non è quello in corso). Giorni di calendario locali."""
    today = (now or datetime.now().astimezone()).astimezone().date()
    day = moment.astimezone().date()
    if day == today:
        return "oggi"
    if (today - day).days == 1:
        return "ieri"
    return f"{day.day} {_MONTHS[day.month - 1]}" + (f" {day.year}" if day.year != today.year else "")


def initials(name: str) -> str:
    """Le iniziali di un nome: le prime lettere delle prime due parole significative (senza articoli e preposizioni).
    «Ordine della Fiamma» → OF, «Miriel dell'Alba» → MA; una parola sola dà le prime due lettere («Aldric» → AL)."""
    words = [word for word in re.split(r"[\s’']+", name.strip()) if word]
    significant = [word for word in words if word.lower() not in _STOP_WORDS] or words
    if len(significant) == 1:
        return significant[0][:2].upper()
    return "".join(word[0] for word in significant[:2]).upper()
