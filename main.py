"""Punto di partenza di GM Journal."""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gmjournal import theme
from gmjournal.app import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GM Journal")
    app.setDesktopFileName("gm-journal")       # su Linux collega la finestra alla voce del menu (gm-journal.desktop)
    app.setWindowIcon(QIcon(str(theme.ASSETS_DIR / "gmjournal.png")))
    theme.load_fonts()
    theme.apply(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
