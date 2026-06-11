# ui/helper_dialog.py
import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QPushButton, QListWidget, QHBoxLayout, QGroupBox,
    QMessageBox, QTextEdit, QCheckBox, QComboBox, QLabel, QFrame
)
from PySide6.QtCore import Qt
from utils.clipboard import copy_to_clipboard


class HelperDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Помощник разметки")
        self.setSizeGripEnabled(True)

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

        # Вкладка условных блоков (расширенная)
        self.cond_tab = QWidget()
        self.setup_conditional_tab()
        tabs.addTab(self.cond_tab, "Условные блоки")

        layout.addWidget(tabs)

    # ========== ПРОСТЫЕ ПОЛЯ ==========
    def setup_simple_tab(self):
        layout = QVBoxLayout(self.simple_tab)
        form = QFormLayout()
        self.simple_name_edit = QLineEdit()
        self.simple_name_edit.setPlaceholderText("например: client_name (только латиница)")
        self.simple_name_edit.textChanged.connect(self.update_simple_preview)
        form.addRow("Имя переменной:", self.simple_name_edit)

        # Предпросмотр
        preview_label = QLabel("Предпросмотр тега:")
        self.simple_preview = QTextEdit()
        self.simple_preview.setReadOnly(True)
        self.simple_preview.setMaximumHeight(80)
        form.addRow(preview_label, self.simple_preview)

        self.simple_copy_btn = QPushButton("Сгенерировать и скопировать")
        form.addRow(self.simple_copy_btn)
        layout.addLayout(form)
        layout.addStretch()
        self.simple_copy_btn.clicked.connect(self.copy_simple_tag)
        self.update_simple_preview()

    def update_simple_preview(self):
        name = self.simple_name_edit.text().strip()
        if name and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            self.simple_preview.setPlainText(f"{{{{{name}}}}}")
        else:
            self.simple_preview.setPlainText("{{ ... }}")

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

    # ========== ПОВТОРЯЮЩИЕСЯ БЛОКИ ==========
    def setup_block_tab(self):
        layout = QVBoxLayout(self.block_tab)
        form = QFormLayout()
        self.block_name_edit = QLineEdit()
        self.block_name_edit.setPlaceholderText("например: sources (латиница)")
        self.block_name_edit.textChanged.connect(self.update_block_preview)
        form.addRow("Имя списка:", self.block_name_edit)

        self.fields_list = QListWidget()
        self.fields_list.setMaximumHeight(150)
        self.fields_list.model().rowsInserted.connect(self.update_block_preview)
        self.fields_list.model().rowsRemoved.connect(self.update_block_preview)
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

        # Предпросмотр
        preview_label = QLabel("Предпросмотр блока:")
        self.block_preview = QTextEdit()
        self.block_preview.setReadOnly(True)
        self.block_preview.setMaximumHeight(120)
        form.addRow(preview_label, self.block_preview)

        self.block_copy_btn = QPushButton("Сгенерировать блок и скопировать")
        form.addRow(self.block_copy_btn)

        layout.addLayout(form)
        layout.addStretch()
        self.block_copy_btn.clicked.connect(self.copy_block_tag)
        self.update_block_preview()

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

    def update_block_preview(self):
        block_name = self.block_name_edit.text().strip()
        field_names = [self.fields_list.item(i).text() for i in range(self.fields_list.count())]
        if not block_name or not field_names:
            self.block_preview.setPlainText("{% for ... %}\n...\n{% endfor %}")
            return
        item_var = "item"
        inner = ", ".join(f"{{{{ {item_var}.{f} }}}}" for f in field_names)
        tag = f"{{% for {item_var} in {block_name} %}}\n{inner}\n{{% endfor %}}"
        self.block_preview.setPlainText(tag)

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

    # ========== УСЛОВНЫЕ БЛОКИ (расширенные) ==========
    def setup_conditional_tab(self):
        layout = QVBoxLayout(self.cond_tab)

        # Основной блок if
        if_group = QGroupBox("Условие if")
        if_layout = QFormLayout(if_group)
        self.if_var_edit = QLineEdit()
        self.if_var_edit.setPlaceholderText("переменная (например: amount)")
        if_layout.addRow("Переменная:", self.if_var_edit)
        self.if_op_combo = QComboBox()
        self.if_op_combo.addItems(["==", "!=", ">", ">=", "<", "<=", "in", "not in"])
        if_layout.addRow("Оператор:", self.if_op_combo)
        self.if_val_edit = QLineEdit()
        self.if_val_edit.setPlaceholderText("значение (например: 10000)")
        if_layout.addRow("Значение:", self.if_val_edit)
        self.if_text_edit = QTextEdit()
        self.if_text_edit.setPlaceholderText("Текст, если условие истинно...")
        self.if_text_edit.setMaximumHeight(80)
        if_layout.addRow("Текст:", self.if_text_edit)
        layout.addWidget(if_group)

        # Блоки elif
        self.elif_container = QWidget()
        self.elif_layout = QVBoxLayout(self.elif_container)
        self.elif_layout.setContentsMargins(0, 0, 0, 0)
        self.elif_frames = []  # (frame, var_edit, op_combo, val_edit, text_edit)
        layout.addWidget(QLabel("Дополнительные условия (elif):"))
        layout.addWidget(self.elif_container)

        btn_add_elif = QPushButton("+ Добавить условие elif")
        btn_add_elif.clicked.connect(self.add_elif_block)
        layout.addWidget(btn_add_elif)

        # Блок else
        self.else_check = QCheckBox("Добавить блок else")
        self.else_check.stateChanged.connect(self.on_else_toggled)
        layout.addWidget(self.else_check)
        self.else_text_edit = QTextEdit()
        self.else_text_edit.setPlaceholderText("Текст, если ни одно условие не выполнено...")
        self.else_text_edit.setMaximumHeight(80)
        self.else_text_edit.setEnabled(False)
        layout.addWidget(self.else_text_edit)

        # Предпросмотр
        preview_label = QLabel("Предпросмотр сгенерированного кода:")
        layout.addWidget(preview_label)
        self.cond_preview = QTextEdit()
        self.cond_preview.setReadOnly(True)
        self.cond_preview.setMaximumHeight(120)
        layout.addWidget(self.cond_preview)

        self.cond_copy_btn = QPushButton("Скопировать в буфер обмена")
        self.cond_copy_btn.clicked.connect(self.copy_conditional_tag)
        layout.addWidget(self.cond_copy_btn)

        layout.addStretch()

        # Сигналы для обновления предпросмотра
        self.if_var_edit.textChanged.connect(self.update_cond_preview)
        self.if_op_combo.currentTextChanged.connect(self.update_cond_preview)
        self.if_val_edit.textChanged.connect(self.update_cond_preview)
        self.if_text_edit.textChanged.connect(self.update_cond_preview)
        self.else_check.stateChanged.connect(self.update_cond_preview)
        self.else_text_edit.textChanged.connect(self.update_cond_preview)

    def add_elif_block(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)

        var_edit = QLineEdit()
        var_edit.setPlaceholderText("переменная")
        op_combo = QComboBox()
        op_combo.addItems(["==", "!=", ">", ">=", "<", "<=", "in", "not in"])
        val_edit = QLineEdit()
        val_edit.setPlaceholderText("значение")
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("Текст для этого elif...")
        text_edit.setMaximumHeight(60)
        remove_btn = QPushButton("✖")
        remove_btn.setFixedWidth(30)

        layout.addWidget(QLabel("if not, то"))
        layout.addWidget(var_edit, 1)
        layout.addWidget(op_combo)
        layout.addWidget(val_edit, 1)
        layout.addWidget(QLabel("то текст:"))
        layout.addWidget(text_edit, 2)
        layout.addWidget(remove_btn)

        remove_btn.clicked.connect(lambda: self.remove_elif_block(frame))

        self.elif_layout.addWidget(frame)
        self.elif_frames.append((frame, var_edit, op_combo, val_edit, text_edit))

        var_edit.textChanged.connect(self.update_cond_preview)
        op_combo.currentTextChanged.connect(self.update_cond_preview)
        val_edit.textChanged.connect(self.update_cond_preview)
        text_edit.textChanged.connect(self.update_cond_preview)

        self.update_cond_preview()

    def remove_elif_block(self, frame):
        for i, (f, *_) in enumerate(self.elif_frames):
            if f is frame:
                self.elif_frames.pop(i)
                frame.deleteLater()
                break
        self.update_cond_preview()

    def on_else_toggled(self, state):
        self.else_text_edit.setEnabled(state == Qt.Checked)
        self.update_cond_preview()

    def update_cond_preview(self):
        lines = []

        # if
        var = self.if_var_edit.text().strip()
        op = self.if_op_combo.currentText()
        val = self.if_val_edit.text().strip()
        if_text = self.if_text_edit.toPlainText().strip()

        if var and val:
            condition = self._build_condition(var, op, val)
            lines.append(f"{{% if {condition} %}}")
            if if_text:
                lines.append(if_text)
        else:
            lines.append("{{% if ... %}}")
            lines.append("...")

        # elif
        for _, var_ed, op_cb, val_ed, txt_ed in self.elif_frames:
            var2 = var_ed.text().strip()
            op2 = op_cb.currentText()
            val2 = val_ed.text().strip()
            txt2 = txt_ed.toPlainText().strip()
            if var2 and val2:
                condition2 = self._build_condition(var2, op2, val2)
                lines.append(f"{{% elif {condition2} %}}")
                if txt2:
                    lines.append(txt2)

        # else
        if self.else_check.isChecked():
            else_text = self.else_text_edit.toPlainText().strip()
            lines.append("{{% else %}}")
            if else_text:
                lines.append(else_text)

        lines.append("{{% endif %}}")
        self.cond_preview.setPlainText("\n".join(lines))

    def _build_condition(self, var, op, val):
        if op in ("in", "not in"):
            val_stripped = val.strip()
            if val_stripped.startswith('[') and val_stripped.endswith(']'):
                pass
            elif ',' in val_stripped:
                parts = [p.strip() for p in val_stripped.split(',')]
                quoted = []
                for p in parts:
                    try:
                        float(p)
                        quoted.append(p)
                    except:
                        quoted.append(f"'{p}'")
                val = "[" + ", ".join(quoted) + "]"
        else:
            try:
                float(val)
            except:
                val = f"'{val}'"
        return f"{var} {op} {val}"

    def copy_conditional_tag(self):
        tag = self.cond_preview.toPlainText().strip()
        if not tag or tag == "{{% if ... %}}\n...\n{{% endif %}":
            QMessageBox.warning(self, "Ошибка", "Заполните хотя бы одно условие (if) с переменной и значением")
            return
        copy_to_clipboard(tag)
        QMessageBox.information(self, "Готово", "Условный тег скопирован в буфер обмена")