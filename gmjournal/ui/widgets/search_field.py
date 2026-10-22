"""Il campo con un'icona a sinistra (di solito la lente): la base della ricerca globale (barra in alto), di «Cerca nella pagina»
e del campo «Aggiungi una cosa da fare»."""

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QWidget

from ... import theme
from .icon_label import IconLabel


class SearchField(QFrame):
    """Icona, campo di testo e, a destra, un widget a scelta (un suggerimento, un conteggio). Non cerca da solo: segnala ciò che
    l'utente fa. `object_name` sceglie l'aspetto nel foglio di stile (il bordo si evidenzia quando il campo ha il cursore)."""

    edited = Signal(str)            # il testo è cambiato
    stepped = Signal(int)           # freccia su (-1) o giù (+1)
    submitted = Signal()            # Invio
    dismissed = Signal()            # Esc
    focus_changed = Signal(bool)    # il cursore è entrato (True) o uscito (False)

    def __init__(self, object_name: str, placeholder: str, trailing: QWidget | None = None, icon: str = "search"):
        super().__init__()
        self.setObjectName(object_name)
        self.setFixedHeight(34)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.setAccessibleName(placeholder)
        self._edit.installEventFilter(self)
        self._edit.textChanged.connect(self.edited)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(8)
        layout.addWidget(IconLabel(icon, theme.MUTED, 16))
        layout.addWidget(self._edit, 1)
        if trailing is not None:
            layout.addWidget(trailing)

    def text(self) -> str:
        return self._edit.text()

    def clear(self) -> None:
        self._edit.clear()

    def focus(self) -> None:
        self._edit.setFocus()
        self._edit.selectAll()

    def release_focus(self) -> None:
        self._edit.clearFocus()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind in (QEvent.FocusIn, QEvent.FocusOut):
            gained = kind == QEvent.FocusIn
            self.setProperty("focused", gained)   # bordo evidenziato quando ha il cursore
            self.style().unpolish(self)
            self.style().polish(self)
            self.focus_changed.emit(gained)
        elif kind == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Up, Qt.Key_Down):
                self.stepped.emit(-1 if key == Qt.Key_Up else 1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.submitted.emit()
                return True
            if key == Qt.Key_Escape:
                self.dismissed.emit()
                return True
        return False
