from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QHeaderView, QComboBox, QCheckBox, QLabel
)
from PySide6.QtCore import Qt
from logic.data_models import Template, TemplateField, TemplateBlock


class TemplateEditorDialog(QDialog):
    def __init__(self, template: Template, parent=None):
        super().__init__(parent)
        self.template = template
        self.setWindowTitle(f"Редактирование шаблона: {template.name}")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # Таблица для простых полей
        self.fields_table = QTableWidget()
        self.fields_table.setColumnCount(4)
        self.fields_table.setHorizontalHeaderLabels(["Внутреннее имя", "Отображаемое имя", "Тип", "Обязательное"])
        self.fields_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(self.fields_table)

        # Блоки показываем отдельно (упрощённо)
        self.blocks_label = QLabel()
        layout.addWidget(self.blocks_label)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить")
        self.cancel_btn = QPushButton("Отмена")
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self.save_changes)
        self.cancel_btn.clicked.connect(self.reject)

        self.populate_table()

    def populate_table(self):
        self.fields_table.setRowCount(len(self.template.fields))
        for row, field in enumerate(self.template.fields):
            # Имя (только для чтения)
            name_item = QTableWidgetItem(field.name)
            name_item.setFlags(Qt.ItemIsEnabled)
            self.fields_table.setItem(row, 0, name_item)

            # Отображаемое имя (редактируемое)
            display_item = QTableWidgetItem(field.display_name)
            self.fields_table.setItem(row, 1, display_item)

            # Тип (выпадающий список)
            combo = QComboBox()
            combo.addItems(["text", "number", "date"])
            combo.setCurrentText(field.field_type)
            self.fields_table.setCellWidget(row, 2, combo)

            # Обязательное (чекбокс)
            chk = QCheckBox()
            chk.setChecked(field.required)
            self.fields_table.setCellWidget(row, 3, chk)

        # Отображаем блоки (просто текст)
        if self.template.blocks:
            blocks_text = "Блоки: " + ", ".join(
                f"{b.name} (поля: {', '.join([f.name for f in b.fields])})" for b in self.template.blocks)
            self.blocks_label.setText(blocks_text)
        else:
            self.blocks_label.setText("Блоки не обнаружены")

    def save_changes(self):
        # Сохраняем изменения в полях
        for row in range(self.fields_table.rowCount()):
            field = self.template.fields[row]
            # Отображаемое имя
            display_item = self.fields_table.item(row, 1)
            if display_item:
                field.display_name = display_item.text()
            # Тип
            combo = self.fields_table.cellWidget(row, 2)
            if combo:
                field.field_type = combo.currentText()
            # Обязательное
            chk = self.fields_table.cellWidget(row, 3)
            if chk:
                field.required = chk.isChecked()
        # Пока не сохраняем блоки, только поля
        QMessageBox.information(self, "Успех", "Настройки сохранены")
        self.accept()