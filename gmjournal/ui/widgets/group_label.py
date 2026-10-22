"""Il titoletto in maiuscolo sopra un gruppo di voci o un campo («CAPITOLI», «ARCHI», «RUOLO»…)."""

from PySide6.QtWidgets import QLabel

from ... import theme


def group_label(text: str = "") -> QLabel:
    """Il titoletto con `text` in maiuscolo (si può lasciare vuoto e impostare dopo con `setText`)."""
    label = QLabel(text.upper())
    label.setObjectName("GroupLabel")
    label.setFont(theme.ui_font(11, 600, 0.08))
    return label
