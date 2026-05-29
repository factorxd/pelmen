# ui/helper_dialog.py
import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QPushButton, QListWidget, QHBoxLayout, QLabel,
    QListWidgetItem, QMessageBox, QComboBox, QTextEdit, QCheckBox
)
from utils.clipboard import copy_to_clipboard


class HelperDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Помощник разметки")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # Вкладка простых полей
        self.simple_tab = QWidget()
        self.setup_simple_tab()
        tabs.addTab(self.simple_tab, "Простые поля")

        # Вкладка повторяющихся блоков
        self.block_tab = QWidget()
        self.setup_block_tab()
        tabs.addTab(self.block_tab, "Повторяющиеся блоки")

        # Вкладка условных блоков
        self.cond_tab = QWidget()
        self.setup_conditional_tab()
        tabs.addTab(self.cond_tab, "Условные блоки")

        layout.addWidget(tabs)

    # --- Простые поля ---
    def setup_simple_tab(self):
        layout = QVBoxLayout(self.simple_tab)
        form = QFormLayout()
        self.simple_name_edit = QLineEdit()
        self.simple_name_edit.setPlaceholderText("например: client_name (только латиница)")
        form.addRow("Имя переменной:", self.simple_name_edit)
        self.simple_copy_btn = QPushButton("Сгенерировать и скопировать")
        form.addRow(self.simple_copy_btn)
        layout.addLayout(form)
        layout.addStretch()
        self.simple_copy_btn.clicked.connect(self.copy_simple_tag)

    def copy_simple_tag(self):
        name = self.simple_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите имя переменной")
            return
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            QMessageBox.warning(self, "Ошибка", "Имя должно быть на латинице, без пробелов, начинаться с буквы или _")
            return
        tag = f"{{{{{name}}}}}"
        copy_to_clipboard(tag)
        QMessageBox.information(self, "Готово", f"Тег {tag} скопирован")

    # --- Повторяющиеся блоки ---
    def setup_block_tab(self):
        layout = QVBoxLayout(self.block_tab)
        form = QFormLayout()
        self.block_name_edit = QLineEdit()
        self.block_name_edit.setPlaceholderText("например: sources (латиница)")
        form.addRow("Имя списка:", self.block_name_edit)

        self.fields_list = QListWidget()
        self.fields_list.setMaximumHeight(150)
        form.addRow("Поля внутри блока:", self.fields_list)

        btn_layout = QHBoxLayout()
        self.add_field_btn = QPushButton("+ Добавить поле")
        self.remove_field_btn = QPushButton("- Удалить поле")
        btn_layout.addWidget(self.add_field_btn)
        btn_layout.addWidget(self.remove_field_btn)
        form.addRow(btn_layout)

        self.field_name_edit = QLineEdit()
        self.field_name_edit.setPlaceholderText("имя поля (title, author...)")
        form.addRow("Новое поле:", self.field_name_edit)
        self.add_field_btn.clicked.connect(self.add_block_field)
        self.remove_field_btn.clicked.connect(self.remove_block_field)

        self.block_copy_btn = QPushButton("Сгенерировать блок и скопировать")
        form.addRow(self.block_copy_btn)

        layout.addLayout(form)
        layout.addStretch()
        self.block_copy_btn.clicked.connect(self.copy_block_tag)

    def add_block_field(self):
        name = self.field_name_edit.text().strip()
        if not name:
            return
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            QMessageBox.warning(self, "Ошибка", "Имя поля только латиница")
            return
        if name not in [self.fields_list.item(i).text() for i in range(self.fields_list.count())]:
            self.fields_list.addItem(name)
        self.field_name_edit.clear()

    def remove_block_field(self):
        current = self.fields_list.currentItem()
        if current:
            self.fields_list.takeItem(self.fields_list.row(current))

    def copy_block_tag(self):
        block_name = self.block_name_edit.text().strip()
        if not block_name:
            QMessageBox.warning(self, "Ошибка", "Введите имя списка")
            return
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', block_name):
            QMessageBox.warning(self, "Ошибка", "Имя списка должно быть на латинице")
            return

        field_names = [self.fields_list.item(i).text() for i in range(self.fields_list.count())]
        if not field_names:
            QMessageBox.warning(self, "Ошибка", "Добавьте хотя бы одно поле в блок")
            return

        item_var = "item"
        inner = ", ".join(f"{{{{ {item_var}.{f} }}}}" for f in field_names)
        tag = f"{{% for {item_var} in {block_name} %}}\n{inner}\n{{% endfor %}}"
        copy_to_clipboard(tag)
        QMessageBox.information(self, "Готово", f"Тег блока скопирован")

    # --- Условные блоки ---
    def setup_conditional_tab(self):
        layout = QVBoxLayout(self.cond_tab)
        form = QFormLayout()

        self.cond_var_edit = QLineEdit()
        self.cond_var_edit.setPlaceholderText("например: has_discount")
        form.addRow("Условие (имя переменной):", self.cond_var_edit)

        self.cond_true_edit = QTextEdit()
        self.cond_true_edit.setPlaceholderText("Текст, если условие истинно...")
        self.cond_true_edit.setMaximumHeight(100)
        form.addRow("Текст при True:", self.cond_true_edit)

        self.cond_else_check = QCheckBox("Добавить блок else")
        form.addRow(self.cond_else_check)

        self.cond_false_edit = QTextEdit()
        self.cond_false_edit.setPlaceholderText("Текст, если условие ложно...")
        self.cond_false_edit.setMaximumHeight(100)
        self.cond_false_edit.setEnabled(False)
        form.addRow("Текст при False:", self.cond_false_edit)

        self.cond_else_check.stateChanged.connect(lambda state: self.cond_false_edit.setEnabled(state == 2))

        self.cond_copy_btn = QPushButton("Сгенерировать и скопировать")
        form.addRow(self.cond_copy_btn)

        layout.addLayout(form)
        layout.addStretch()
        self.cond_copy_btn.clicked.connect(self.copy_conditional_tag)

    def copy_conditional_tag(self):
        var = self.cond_var_edit.text().strip()
        if not var:
            QMessageBox.warning(self, "Ошибка", "Введите имя переменной")
            return
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var):
            QMessageBox.warning(self, "Ошибка", "Имя переменной только латиница")
            return

        true_text = self.cond_true_edit.toPlainText().strip()
        if not true_text:
            QMessageBox.warning(self, "Ошибка", "Введите текст для случая True")
            return

        if self.cond_else_check.isChecked():
            false_text = self.cond_false_edit.toPlainText().strip()
            tag = f"{{% if {var} %}}\n{true_text}\n{{% else %}}\n{false_text}\n{{% endif %}}"
        else:
            tag = f"{{% if {var} %}}\n{true_text}\n{{% endif %}}"

        copy_to_clipboard(tag)
        QMessageBox.information(self, "Готово", f"Условный тег скопирован")