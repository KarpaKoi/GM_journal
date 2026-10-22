"""Schermata vuota al centro: icona, titolo, spiegazione e un pulsante che propone il primo passo."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ... import theme
from .icon_label import IconLabel


class EmptyState(QWidget):
    clicked = Signal()

    def __init__(self, icon_name: str, color: str, title: str, text: str, button_label: str):
        super().__init__()
        heading = QLabel(title)
        heading.setFont(theme.serif_font(32, 500))
        body = QLabel(text)
        body.setObjectName("Muted")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        body.setFixedWidth(380)
        button = QPushButton(button_label)
        button.setObjectName("PrimaryButton")
        button.setFixedHeight(40)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(self.clicked)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        layout.addWidget(IconLabel(icon_name, color, 56), alignment=Qt.AlignCenter)
        layout.addWidget(heading, alignment=Qt.AlignCenter)
        layout.addWidget(body, alignment=Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(button, alignment=Qt.AlignCenter)
