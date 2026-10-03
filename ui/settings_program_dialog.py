import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QComboBox, QDoubleSpinBox, QPushButton, QFileDialog, QHBoxLayout,
    QDialogButtonBox, QSpinBox
)


class SettingsProgramDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # MainWindow
        self.setWindowTitle("Настройки программы")
        self.setMinimumWidth(450)
        self.settings_file = os.path.join("data", "settings.json")
        self.load_settings()
        self.init_ui()
        self.update_ui_from_settings()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as f:
                self.settings = json.load(f)
        else:
            self.settings = {}

    def save_settings(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Папка с шаблонами
        self.folder_edit = QLineEdit()  # <-- убрал self.settings.get
        folder_btn = QPushButton("Обзор...")
        folder_btn.clicked.connect(self.browse_folder)
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(folder_btn)
        form.addRow("Папка с шаблонами:", folder_layout)

        # Тёмная тема
        self.dark_theme_cb = QCheckBox()
        form.addRow("Тёмная тема:", self.dark_theme_cb)

        # Проверять обновления при запуске
        self.check_updates_cb = QCheckBox()
        form.addRow("Проверять обновления при запуске:", self.check_updates_cb)

        # Размер шрифта
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 24)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(10)
        form.addRow("Размер шрифта:", self.font_size_spin)

        # Интервал автосохранения
        self.draft_interval = QDoubleSpinBox()
        self.draft_interval.setRange(0.1, 5.0)
        self.draft_interval.setSingleStep(0.1)
        self.draft_interval.setSuffix(" сек")
        form.addRow("Интервал автосохранения:", self.draft_interval)

        # Кнопка ручной проверки обновлений
        manual_update_btn = QPushButton("Проверить обновления сейчас")
        manual_update_btn.clicked.connect(self.manual_check_updates)
        form.addRow(manual_update_btn)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выбрать папку с шаблонами")
        if folder:
            self.folder_edit.setText(folder)

    def manual_check_updates(self):
        if self.parent:
            self.parent.check_for_updates(manual=True)

    def accept(self):
        # Сохраняем настройки в локальный словарь
        self.settings["root_folder"] = self.folder_edit.text()
        self.settings["dark_theme"] = self.dark_theme_cb.isChecked()
        self.settings["auto_check_updates"] = self.check_updates_cb.isChecked()
        self.settings["font_size"] = self.font_size_spin.value()
        self.settings["draft_interval"] = self.draft_interval.value()

        # Обновляем словарь главного окна
        self.parent.settings.update(self.settings)

        # Сохраняем файл через главное окно (оно запишет все настройки разом)
        self.parent.save_settings()

        # Применяем изменения к программе
        self.parent.toggle_dark_theme(self.settings["dark_theme"])
        self.parent.draft_interval_seconds = self.settings["draft_interval"]
        self.parent.apply_font_size(self.settings["font_size"])

        # Меняем папку с шаблонами, если изменилась
        if self.settings["root_folder"] != self.parent.root_folder:
            self.parent.set_root_folder(self.settings["root_folder"])

        super().accept()

    def update_ui_from_settings(self):
        """Обновляет виджеты диалога в соответствии с текущими настройками"""
        self.folder_edit.setText(self.settings.get("root_folder", ""))
        self.dark_theme_cb.setChecked(self.settings.get("dark_theme", False))
        self.check_updates_cb.setChecked(self.settings.get("auto_check_updates", True))

        font_size = self.settings.get("font_size", 10)
        # Обратная совместимость со старыми настройками-строками
        if isinstance(font_size, str):
            font_size = {"Маленький": 8, "Средний": 10, "Большой": 12}.get(font_size, 10)
        try:
            font_size = int(font_size)
        except (TypeError, ValueError):
            font_size = 10
        font_size = max(6, min(24, font_size))
        self.font_size_spin.setValue(font_size)

        try:
            self.draft_interval.setValue(float(self.settings.get("draft_interval", 0.5)))
        except:
            self.draft_interval.setValue(0.5)

        self.repaint()