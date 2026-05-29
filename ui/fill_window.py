# ui/fill_window.py (финальная, без ошибок disconnect)
import os
import tempfile
import shutil
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QScrollArea, QLineEdit, QPushButton, QLabel,
    QDateEdit, QTextEdit, QMessageBox, QFileDialog, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, QDate
from logic.doc_generator import generate_docx


class FillWindow(QMainWindow):
    def __init__(self, template):
        super().__init__()
        self.template = template
        self.setWindowTitle(f"Заполнение: {template.name}")
        self.setGeometry(150, 150, 1000, 700)

        self.simple_widgets = {}
        self.block_widgets = {}

        self.init_ui()
        self.update_preview()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)

        self.form_widget = QWidget()
        self.form_layout = QVBoxLayout(self.form_widget)
        self.form_layout.setAlignment(Qt.AlignTop)
        self.build_form()

        left_scroll.setWidget(self.form_widget)
        left_layout.addWidget(left_scroll)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("Предпросмотр документа:"))
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        right_layout.addWidget(self.preview_text)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)

    def build_form(self):
        self.clear_layout(self.form_layout)
        for field in self.template.fields:
            self.add_simple_field(field)
        for block in self.template.blocks:
            self.add_dynamic_block(block)

        # Кнопки (создаём заново)
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("📄 Скачать DOCX")
        self.reset_btn = QPushButton("🔄 Сбросить")
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.reset_btn)
        self.form_layout.addLayout(btn_layout)

        self.generate_btn.clicked.connect(self.generate_document)
        self.reset_btn.clicked.connect(self.reset_form)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def add_simple_field(self, field):
        label = QLabel(field.display_name)
        if field.required:
            label.setText(label.text() + " *")
        if field.field_type == "date":
            edit = QDateEdit()
            edit.setDate(QDate.currentDate())
            edit.dateChanged.connect(self.update_preview)
        else:
            edit = QLineEdit()
            edit.textChanged.connect(self.update_preview)
        self.form_layout.addWidget(label)
        self.form_layout.addWidget(edit)
        self.simple_widgets[field.name] = edit

    def add_dynamic_block(self, block):
        group_box = QGroupBox(block.display_name)
        group_layout = QVBoxLayout(group_box)
        block_key = block.name
        self.block_widgets[block_key] = []
        self.add_block_card(block, group_layout, block_key)
        add_btn = QPushButton("+ Добавить ещё")
        add_btn.clicked.connect(lambda checked, b=block, l=group_layout, key=block_key: self.add_block_card(b, l, key))
        group_layout.addWidget(add_btn)
        self.form_layout.addWidget(group_box)

    def add_block_card(self, block, parent_layout, block_key):
        card_frame = QFrame()
        card_frame.setFrameShape(QFrame.StyledPanel)
        card_layout = QVBoxLayout(card_frame)
        header_layout = QHBoxLayout()
        label = QLabel(f"Элемент {len(self.block_widgets[block_key]) + 1}")
        remove_btn = QPushButton("🗑️ Удалить")
        remove_btn.setFixedWidth(80)
        header_layout.addWidget(label)
        header_layout.addStretch()
        header_layout.addWidget(remove_btn)
        card_layout.addLayout(header_layout)

        fields_widgets = {}
        for field in block.fields:
            field_label = QLabel(field.display_name)
            if field.field_type == "date":
                edit = QDateEdit()
                edit.setDate(QDate.currentDate())
                edit.dateChanged.connect(self.update_preview)
            else:
                edit = QLineEdit()
                edit.textChanged.connect(self.update_preview)
            card_layout.addWidget(field_label)
            card_layout.addWidget(edit)
            fields_widgets[field.name] = edit

        card_data = {"frame": card_frame, "fields": fields_widgets}
        self.block_widgets[block_key].append(card_data)
        add_btn_index = parent_layout.count() - 1
        parent_layout.insertWidget(add_btn_index, card_frame)
        remove_btn.clicked.connect(lambda checked, key=block_key, card=card_data: self.remove_block_card(key, card))
        self.update_preview()

    def remove_block_card(self, block_key, card_data):
        if card_data in self.block_widgets[block_key]:
            self.block_widgets[block_key].remove(card_data)
            card_data["frame"].deleteLater()
            self.renumber_block_cards(block_key)
            self.update_preview()

    def renumber_block_cards(self, block_key):
        for idx, card in enumerate(self.block_widgets[block_key]):
            for child in card["frame"].findChildren(QLabel):
                if child.text().startswith("Элемент"):
                    child.setText(f"Элемент {idx + 1}")
                    break

    def collect_data(self):
        data = {}
        for name, widget in self.simple_widgets.items():
            if isinstance(widget, QLineEdit):
                data[name] = widget.text()
            elif isinstance(widget, QDateEdit):
                data[name] = widget.date().toString("yyyy-MM-dd")
        for block_name, cards in self.block_widgets.items():
            block_data = []
            for card in cards:
                item = {}
                for fname, fw in card["fields"].items():
                    if isinstance(fw, QLineEdit):
                        item[fname] = fw.text()
                    elif isinstance(fw, QDateEdit):
                        item[fname] = fw.date().toString("yyyy-MM-dd")
                block_data.append(item)
            data[block_name] = block_data
        return data

    def update_preview(self):
        if not hasattr(self, 'preview_text'):
            return
        data = self.collect_data()
        preview = f"=== Шаблон: {self.template.name} ===\n\n"
        for key, value in data.items():
            if isinstance(value, list):
                preview += f"{key}:\n"
                for idx, item in enumerate(value):
                    preview += f"  {idx + 1}. {item}\n"
            else:
                preview += f"{key}: {value}\n"
        self.preview_text.setPlainText(preview)

    def generate_document(self):
        data = self.collect_data()
        missing = [f.display_name for f in self.template.fields if f.required and not data.get(f.name, "")]
        if missing:
            QMessageBox.warning(self, "Ошибка", f"Заполните обязательные поля:\n" + "\n".join(missing))
            return
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            generate_docx(self.template.file_path, data, tmp_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать документ:\n{str(e)}")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить документ", f"{self.template.name}_готовый.docx",
                                                   "Word files (*.docx)")
        if save_path:
            shutil.move(tmp_path, save_path)
            QMessageBox.information(self, "Успех", f"Документ сохранён:\n{save_path}")
        else:
            os.unlink(tmp_path)

    def reset_form(self):
        for widget in self.simple_widgets.values():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QDateEdit):
                widget.setDate(QDate.currentDate())
        for block_name, cards in list(self.block_widgets.items()):
            while len(cards) > 1:
                self.remove_block_card(block_name, cards[-1])
            if cards:
                for fw in cards[0]["fields"].values():
                    if isinstance(fw, QLineEdit):
                        fw.clear()
                    elif isinstance(fw, QDateEdit):
                        fw.setDate(QDate.currentDate())
        self.update_preview()