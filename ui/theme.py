# ui/theme.py
"""Тёмная и светлая темы.

Всё рисование — на Fusion. Цвета — на QPalette.
QSS трогает ТОЛЬКО то, что палитра физически не покрывает:
read-only поля и тултипы.
"""
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


# Только read-only поля и тултипы. Никаких других правил.
QSS_DARK = """
QLineEdit[readOnly="true"],
QTextEdit[readOnly="true"],
QPlainTextEdit[readOnly="true"] {
    background-color: #1e1e1e;
    color: #a0a0a0;
}
QToolTip {
    background-color: #ffffdc;
    color: #000000;
}

"""

QSS_LIGHT = """
QLineEdit[readOnly="true"],
QTextEdit[readOnly="true"],
QPlainTextEdit[readOnly="true"] {
    background-color: #e8e8e8;
    color: #666666;
}
QToolTip {
    background-color: #ffffdc;
    color: #000000;
}
"""


def _build_dark_palette():
    p = QPalette()
    # Основные роли
    p.setColor(QPalette.Window, QColor(53, 53, 53))
    p.setColor(QPalette.WindowText, QColor(220, 220, 220))
    p.setColor(QPalette.Base, QColor(42, 42, 42))
    p.setColor(QPalette.AlternateBase, QColor(58, 58, 58))
    p.setColor(QPalette.Text, QColor(220, 220, 220))
    p.setColor(QPalette.Button, QColor(70, 70, 70))
    p.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    p.setColor(QPalette.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.Link, QColor(42, 130, 218))
    p.setColor(QPalette.Highlight, QColor(42, 130, 218))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.PlaceholderText, QColor(150, 150, 150))

    # 3D-грани: ими Fusion рисует рамки кнопок, группбоксов, табов
    p.setColor(QPalette.Light, QColor(90, 90, 90))
    p.setColor(QPalette.Midlight, QColor(75, 75, 75))
    p.setColor(QPalette.Mid, QColor(60, 60, 60))
    p.setColor(QPalette.Dark, QColor(35, 35, 35))
    p.setColor(QPalette.Shadow, QColor(20, 20, 20))

    # Тултипы
    p.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
    p.setColor(QPalette.ToolTipText, QColor(0, 0, 0))

    # Disabled
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    p.setColor(QPalette.Disabled, QPalette.Button, QColor(55, 55, 55))

    p.setColor(QPalette.Disabled, QPalette.Base, QColor(35, 35, 35))
    p.setColor(QPalette.Disabled, QPalette.Window, QColor(50, 50, 50))
    p.setColor(QPalette.Disabled, QPalette.AlternateBase, QColor(45, 45, 45))

    return p


def apply_theme(app, dark: bool):
    app.setStyle('Fusion')

    if dark:
        app.setPalette(_build_dark_palette())
        app.setStyleSheet(QSS_DARK)
    else:
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet(QSS_LIGHT)

    # Qt не всегда перерисовывает живые виджеты при смене палитры/стиля
    for widget in QApplication.allWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()