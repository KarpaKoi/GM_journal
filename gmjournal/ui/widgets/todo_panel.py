"""Pannello «Da fare»: le cose da ricordare della campagna, con la spunta quando sono fatte. Si scrive nel campo in alto e si preme Invio;
un clic sul testo lo modifica (Invio conferma, Esc annulla), la «x» che compare passando il mouse sulla voce la elimina."""

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QScrollArea, QTextEdit, QVBoxLayout, QWidget

from ... import icons, theme
from ...data.models import Todo
from .group_label import group_label
from .icon_label import IconLabel
from .search_field import SearchField

_BOX = 18
_DELETE = 22
_BOX_BORDER = "#5a6070"


class _Box(QAbstractButton):
    """La casella da spuntare."""

    def __init__(self, done: bool):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(done)
        self.setFixedSize(_BOX, _BOX)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAccessibleName("Fatta")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        done = self.isChecked()
        color = QColor(theme.ACCENT if done else _BOX_BORDER)
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(color if done else Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4.5, 4.5)
        if done:
            icons.icon("check", theme.BG).paint(painter, QRect(2, 2, _BOX - 4, _BOX - 4))


class _DeleteButton(QAbstractButton):
    """La «x»: si vede solo mentre il mouse è sulla voce, ma il suo posto è sempre riservato (il testo non cambia a capo)."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(_DELETE, _DELETE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover)
        self.setToolTip("Elimina")
        self.setAccessibleName("Elimina")

    def paintEvent(self, event) -> None:
        if not self.parentWidget().underMouse():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER))
            painter.drawRoundedRect(self.rect(), 6, 6)
        icons.icon("x", theme.TEXT if self.underMouse() else theme.MUTED).paint(painter, QRect(4, 4, _DELETE - 8, _DELETE - 8))


class _Editor(QTextEdit):
    """Il testo di una voce mentre si modifica: va a capo, cresce con il contenuto. Invio conferma, Esc annulla, uscire conferma."""
    finished = Signal(str, bool)       # testo, confermato

    def __init__(self, text: str):
        super().__init__()
        self.setObjectName("TodoEdit")
        self.setAcceptRichText(False)
        self.setFont(theme.ui_font(14))
        self.setPlainText(text)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.document().setDocumentMargin(0)
        self.setAccessibleName("Modifica la voce")
        self.document().documentLayout().documentSizeChanged.connect(lambda _: self._fit())
        self._closed = False

    def _fit(self) -> None:
        self.setFixedHeight(int(self.document().size().height()) + 2)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def confirm(self) -> None:
        self._finish(True)

    def _finish(self, confirmed: bool) -> None:
        if not self._closed:
            self._closed = True
            self.finished.emit(self.toPlainText(), confirmed)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self._finish(True)
        elif event.key() == Qt.Key_Escape:
            self._finish(False)
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._finish(True)


class _TodoRow(QWidget):
    toggled = Signal(int, bool)
    renamed = Signal(int, str)
    removed = Signal(int)

    def __init__(self, todo: Todo):
        super().__init__()
        self._todo = todo
        self._editor: _Editor | None = None
        self.setAttribute(Qt.WA_Hover)
        self._box = _Box(todo.done)
        self._box.clicked.connect(lambda checked: self._act(self.toggled, todo.id, checked))
        self._text = QLabel(todo.text)
        self._text.setWordWrap(True)
        self._text.setFont(theme.ui_font(14))
        self._text.setStyleSheet(f"color: {theme.MUTED if todo.done else theme.TEXT}; text-decoration: {'line-through' if todo.done else 'none'};")
        self._text.setAttribute(Qt.WA_TransparentForMouseEvents)       # il clic lo riceve la voce, per modificarla
        self._delete = _DeleteButton()
        self._delete.clicked.connect(lambda: self._act(self.removed, todo.id))
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 7, 8, 7)
        self._layout.setSpacing(10)
        self._layout.addWidget(self._box, alignment=Qt.AlignTop)
        self._layout.addWidget(self._text, 1, Qt.AlignTop)
        self._layout.addWidget(self._delete, alignment=Qt.AlignTop)

    def _act(self, signal, *args) -> None:
        """Spunta o elimina; se intanto il testo si stava modificando, prima lo conferma."""
        if self._editor is not None:
            self._editor.confirm()
        signal.emit(*args)

    def paintEvent(self, event) -> None:
        if self.underMouse() or self._editor is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.HOVER_SOFT))
            painter.drawRoundedRect(self.rect(), theme.RADIUS_CONTROL, theme.RADIUS_CONTROL)

    def enterEvent(self, event) -> None:
        self._delete.update()
        self.update()

    def leaveEvent(self, event) -> None:
        self._delete.update()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._editor is None and self._text.geometry().contains(event.position().toPoint()):
            self.edit()

    def edit(self) -> None:
        """Al posto del testo compare un campo con lo stesso testo."""
        if self._editor is not None:
            return
        self._editor = _Editor(self._todo.text)
        self._editor.finished.connect(self._end_edit)
        self._text.hide()
        self._layout.insertWidget(1, self._editor, 1, Qt.AlignTop)
        self._editor.setFocus()
        self._editor.moveCursor(QTextCursor.End)          # si continua a scrivere dalla fine

    def _end_edit(self, text: str, confirmed: bool) -> None:
        editor, self._editor = self._editor, None
        self._layout.removeWidget(editor)
        editor.deleteLater()
        self._text.show()
        self.update()
        text = " ".join(text.split())
        if confirmed and text and text != self._todo.text:      # vuoto o uguale: resta com'era
            self.renamed.emit(self._todo.id, text)


class TodoPanel(QFrame):
    added = Signal(str)
    toggled = Signal(int, bool)        # ID, fatta
    renamed = Signal(int, str)
    removed = Signal(int)

    def __init__(self):
        super().__init__()
        title = QLabel("Da fare")
        title.setFont(theme.ui_font(15, 600))
        self._count = QLabel()
        self._count.setObjectName("Muted")
        self._count.setFont(theme.ui_font(13))
        header = QHBoxLayout()
        header.setContentsMargins(8, 0, 8, 0)
        header.setSpacing(8)
        header.addWidget(IconLabel("list-todo", theme.ACCENT, 16))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._count)

        self._field = SearchField("TodoField", "Aggiungi una cosa da fare…", icon="plus")
        self._field.submitted.connect(self._submit)
        self._field.dismissed.connect(self._field.clear)

        self._items = QVBoxLayout()
        self._items.setContentsMargins(0, 0, 0, 0)
        self._items.setSpacing(0)
        self._empty = QLabel("Niente da fare, per ora. Scrivi qui sopra una cosa da ricordare e premi Invio: la spunti quando l’hai fatta.")
        self._empty.setObjectName("Muted")
        self._empty.setWordWrap(True)
        self._empty.setContentsMargins(8, 6, 8, 0)
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 14)
        column.setSpacing(0)
        column.addLayout(self._items)
        column.addWidget(self._empty)
        column.addStretch(1)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidget(content)
        content.setAutoFillBackground(False)       # lo sfondo è quello del pannello

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 20, 14, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addSpacing(12)
        layout.addWidget(self._field)
        layout.addSpacing(10)
        layout.addWidget(self._scroll, 1)
        self.set_todos([])

    def _submit(self) -> None:
        text = " ".join(self._field.text().split())
        if text:
            self.added.emit(text)
            self._field.clear()

    def set_todos(self, todos: list[Todo]) -> None:
        """Mostra le voci (prima quelle da fare, poi le fatte), tenendo la posizione di scorrimento."""
        bar = self._scroll.verticalScrollBar()
        position = bar.value()
        while self._items.count():
            item = self._items.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        open_todos = [todo for todo in todos if not todo.done]
        done_todos = [todo for todo in todos if todo.done]
        for todo in open_todos:
            self._items.addWidget(self._row(todo))
        if done_todos:
            heading = group_label(f"Fatte · {len(done_todos)}")
            heading.setContentsMargins(8, 16, 8, 6)
            self._items.addWidget(heading)
            for todo in done_todos:
                self._items.addWidget(self._row(todo))
        self._count.setText(f"{len(open_todos)} da fare")
        self._count.setVisible(bool(todos))
        self._empty.setVisible(not todos)
        QTimer.singleShot(0, lambda: bar.setValue(position))

    def _row(self, todo: Todo) -> _TodoRow:
        row = _TodoRow(todo)
        row.toggled.connect(self.toggled)
        row.renamed.connect(self.renamed)
        row.removed.connect(self.removed)
        return row
