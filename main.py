import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from PySide6.QtGui import QIcon
import os

def resource_path(relative_path):
    """Получает путь к файлу, корректно работающий и в .exe, и в разработке"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icons/pelmen2.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())