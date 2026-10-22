"""Pannello destro: contiene i dettagli veloci o i collegamenti della schermata attiva."""

from PySide6.QtWidgets import QFrame, QStackedWidget, QVBoxLayout, QWidget

from ... import theme


class RightPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("RightPanel")
        self.setFixedWidth(theme.PANEL_WIDTH)
        self._stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def show_content(self, widget: QWidget) -> None:
        if self._stack.indexOf(widget) < 0:
            self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)
