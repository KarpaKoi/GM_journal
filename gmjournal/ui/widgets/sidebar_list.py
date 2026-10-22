"""La lista che una schermata mette nella barra sinistra: un titoletto con il «+» per creare una voce e, sotto, le voci."""

from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from ... import icons
from .group_label import group_label


def sidebar_list(title: str, add_tip: str, on_add: Callable[[], None], content: QWidget) -> QWidget:
    """Il titoletto `title` con il «+» (che dice `add_tip` e chiama `on_add`) sopra `content`, l'elenco delle voci."""
    add = QToolButton()
    add.setObjectName("BarButton")
    add.setIcon(icons.icon("plus"))
    add.setIconSize(QSize(16, 16))
    add.setFixedSize(28, 28)
    add.setToolTip(add_tip)
    add.setFocusPolicy(Qt.NoFocus)
    add.setCursor(Qt.PointingHandCursor)
    add.clicked.connect(lambda: on_add())

    header = QHBoxLayout()
    header.setContentsMargins(10, 0, 0, 0)
    header.addWidget(group_label(title))
    header.addStretch()
    header.addWidget(add)
    holder = QWidget()
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addLayout(header)
    layout.addWidget(content, 1)
    return holder
