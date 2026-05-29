from PySide6.QtWidgets import QApplication

def copy_to_clipboard(text: str):
    """Копирует переданный текст в системный буфер обмена"""
    clipboard = QApplication.clipboard()
    clipboard.setText(text)