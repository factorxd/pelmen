# ui/presets_dialog.py
import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QComboBox, QLabel, QLineEdit,
    QTextEdit, QDialogButtonBox, QMenu, QApplication
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt

class PresetsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Пресеты")
        self.setSizeGripEnabled(True)
        self.presets_file = os.path.join("data", "presets.json")
        self.presets = []  # {"name": str, "value": str, "category": str}
        self.load_presets()
        self.init_ui()
        self.populate_table()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Фильтр по категориям
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Фильтр по категории:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("Все категории")
        self.category_filter.addItem("Без категории")
        self.category_filter.currentTextChanged.connect(self.populate_table)
        filter_layout.addWidget(self.category_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Имя", "Значение", "Категория"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.on_item_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ Добавить")
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.close_btn = QPushButton("Закрыть")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        # Сигналы
        self.add_btn.clicked.connect(self.add_preset)
        self.edit_btn.clicked.connect(self.edit_preset)
        self.delete_btn.clicked.connect(self.delete_preset)
        self.close_btn.clicked.connect(self.accept)

    def load_presets(self):
        if os.path.exists(self.presets_file):
            with open(self.presets_file, "r", encoding="utf-8") as f:
                self.presets = json.load(f)
        else:
            self.presets = []

    def save_presets(self):
        with open(self.presets_file, "w", encoding="utf-8") as f:
            json.dump(self.presets, f, ensure_ascii=False, indent=2)

    def get_all_categories(self):
        """Возвращает список уникальных категорий (кроме пустой)"""
        cats = set()
        for p in self.presets:
            cat = p.get("category", "")
            if cat:
                cats.add(cat)
        return sorted(cats)

    def update_category_filter(self):
        """Обновляет список категорий в фильтре, сохраняя текущий выбор"""
        current = self.category_filter.currentText()
        cats = self.get_all_categories()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("Все категории")
        self.category_filter.addItem("Без категории")
        self.category_filter.addItems(cats)
        # Восстановить выбор, если он ещё существует
        if current in ["Все категории", "Без категории"] or current in cats:
            idx = self.category_filter.findText(current)
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)

    def get_filtered_presets(self):
        """Возвращает список пресетов с учётом выбранного фильтра"""
        filter_cat = self.category_filter.currentText()
        if filter_cat == "Все категории":
            return self.presets
        elif filter_cat == "Без категории":
            return [p for p in self.presets if p.get("category", "") == ""]
        else:
            return [p for p in self.presets if p.get("category", "") == filter_cat]

    def display_category(self, cat):
        """Для отображения в таблице: пустую строку заменяем на «Без категории»"""
        return cat if cat else "Без категории"

    def populate_table(self):
        # Обновляем фильтр (список категорий)
        self.update_category_filter()

        filtered = self.get_filtered_presets()
        self.table.setRowCount(len(filtered))
        for row, preset in enumerate(filtered):
            name_item = QTableWidgetItem(preset["name"])
            name_item.setData(Qt.UserRole, preset)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(preset["value"]))
            cat_display = self.display_category(preset.get("category", ""))
            self.table.setItem(row, 2, QTableWidgetItem(cat_display))
        self.table.resizeColumnsToContents()

    def get_selected_preset(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return None
        filtered = self.get_filtered_presets()
        if current_row >= len(filtered):
            return None
        return filtered[current_row]

    def add_preset(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить пресет")
        layout = QVBoxLayout(dialog)

        # Имя
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Название пресета (например, ООО Ромашка)")
        layout.addWidget(QLabel("Имя:"))
        layout.addWidget(name_edit)

        # Значение
        value_edit = QTextEdit()
        value_edit.setPlaceholderText("Значение, которое будет копироваться")
        value_edit.setMaximumHeight(100)
        layout.addWidget(QLabel("Значение:"))
        layout.addWidget(value_edit)

        # Категория – выпадающий список
        cat_combo = QComboBox()
        cat_combo.setEditable(True)   # можно ввести новую категорию
        # Добавляем существующие категории
        existing_cats = self.get_all_categories()
        cat_combo.addItems(existing_cats)
        cat_combo.setPlaceholderText("Выберите или введите новую категорию")
        layout.addWidget(QLabel("Категория (необязательно):"))
        layout.addWidget(cat_combo)

        # Кнопки
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            value = value_edit.toPlainText().strip()
            category = cat_combo.currentText().strip()
            if not name or not value:
                QMessageBox.warning(self, "Ошибка", "Имя и значение не могут быть пустыми")
                return
            if any(p["name"] == name for p in self.presets):
                QMessageBox.warning(self, "Ошибка", "Пресет с таким именем уже существует")
                return
            self.presets.append({"name": name, "value": value, "category": category})
            self.save_presets()
            self.populate_table()

    def edit_preset(self):
        preset = self.get_selected_preset()
        if not preset:
            QMessageBox.warning(self, "Ошибка", "Выберите пресет для редактирования")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать пресет")
        layout = QVBoxLayout(dialog)

        # Имя
        name_edit = QLineEdit(preset["name"])
        layout.addWidget(QLabel("Имя:"))
        layout.addWidget(name_edit)

        # Значение
        value_edit = QTextEdit(preset["value"])
        value_edit.setMaximumHeight(100)
        layout.addWidget(QLabel("Значение:"))
        layout.addWidget(value_edit)

        # Категория – выпадающий список
        cat_combo = QComboBox()
        cat_combo.setEditable(True)
        existing_cats = self.get_all_categories()
        cat_combo.addItems(existing_cats)
        # Устанавливаем текущую категорию (если есть)
        current_cat = preset.get("category", "")
        if current_cat:
            idx = cat_combo.findText(current_cat)
            if idx >= 0:
                cat_combo.setCurrentIndex(idx)
            else:
                cat_combo.setEditText(current_cat)
        else:
            cat_combo.setEditText("")
        cat_combo.setPlaceholderText("Выберите или введите новую категорию")
        layout.addWidget(QLabel("Категория (необязательно):"))
        layout.addWidget(cat_combo)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.Accepted:
            new_name = name_edit.text().strip()
            new_value = value_edit.toPlainText().strip()
            new_cat = cat_combo.currentText().strip()
            if not new_name or not new_value:
                QMessageBox.warning(self, "Ошибка", "Имя и значение не могут быть пустыми")
                return
            if new_name != preset["name"] and any(p["name"] == new_name for p in self.presets):
                QMessageBox.warning(self, "Ошибка", "Пресет с таким именем уже существует")
                return
            preset["name"] = new_name
            preset["value"] = new_value
            preset["category"] = new_cat
            self.save_presets()
            self.populate_table()

    def delete_preset(self):
        preset = self.get_selected_preset()
        if not preset:
            QMessageBox.warning(self, "Ошибка", "Выберите пресет для удаления")
            return
        reply = QMessageBox.question(self, "Удаление", f"Удалить пресет \"{preset['name']}\"?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.presets.remove(preset)
            self.save_presets()
            self.populate_table()

    def on_item_double_click(self, item):
        if item.column() == 1:   # колонка Значение
            value = item.text()
            QGuiApplication.clipboard().setText(value)
            QMessageBox.information(self, "Скопировано", "Значение скопировано в буфер обмена")

    def show_context_menu(self, pos):
        menu = QMenu()
        add_action = menu.addAction("➕ Добавить")
        edit_action = menu.addAction("✏️ Редактировать")
        delete_action = menu.addAction("🗑️ Удалить")
        copy_action = menu.addAction("📋 Копировать значение")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == add_action:
            self.add_preset()
        elif action == edit_action:
            self.edit_preset()
        elif action == delete_action:
            self.delete_preset()
        elif action == copy_action:
            preset = self.get_selected_preset()
            if preset:
                QGuiApplication.clipboard().setText(preset["value"])
                QMessageBox.information(self, "Скопировано", "Значение скопировано в буфер обмена")