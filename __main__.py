"""Motor Control GUI entry point."""

import multiprocessing
import sys

from PySide6.QtWidgets import QApplication

from src.main_window import MainWindow
from src.ui.style import APP_STYLE


def main():
    """Create the Qt application and show the main window."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("AK10-9 Motor Control")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
