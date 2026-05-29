# ui/mass_generate_dialog.py
import os
import json
import tempfile
import zipfile
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLabel, QProgressBar, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt
from logic.doc_generator import generate_docx

class MassGenerateDialog(QDialog):
    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.template = template
        self.setWindowTitle(f"Массовая генерация: {template.name}")
        self.setMinimumSize(800, 600)
        self.df = None
        self.columns = []
        self.field_mapping = {}   # колонка -> имя поля
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Группа загрузки файла
        file_group = QGroupBox("1. Выберите файл (CSV или Excel)")
        file_layout = QHBoxLayout(file_group)
        self.file_label = QLabel("Файл не выбран")
        self.select_btn = QPushButton("Выбрать файл")
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_btn)
        layout.addWidget(file_group)

        # Таблица предпросмотра
        self.table = QTableWidget()
        self.table.setVisible(False)
        layout.addWidget(self.table)

        # Группа сопоставления колонок
        self.mapping_group = QGroupBox("2. Сопоставьте колонки с полями шаблона")
        self.mapping_group.setVisible(False)
        mapping_layout = QFormLayout(self.mapping_group)
        self.mapping_widgets = []  # (label, combo)
        layout.addWidget(self.mapping_group)

        # Прогресс и кнопки
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Сгенерировать ZIP")
        self.generate_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Отмена")
        btn_layout.addStretch()
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # Сигналы
        self.select_btn.clicked.connect(self.load_file)
        self.generate_btn.clicked.connect(self.generate_zip)
        self.cancel_btn.clicked.connect(self.reject)

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл", "",
            "CSV files (*.csv) || Excel files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        self.file_label.setText(file_path)
        try:
            if file_path.endswith('.csv'):
                self.df = pd.read_csv(file_path, encoding='utf-8')
            else:
                self.df = pd.read_excel(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать файл:\n{str(e)}")
            return

        if self.df.empty:
            QMessageBox.critical(self, "Ошибка", "Файл пуст")
            return

        self.columns = list(self.df.columns)
        self.show_preview()
        self.setup_mapping()
        self.table.setVisible(True)
        self.mapping_group.setVisible(True)
        self.generate_btn.setEnabled(True)

    def show_preview(self):
        """Показать первые 5 строк в таблице"""
        self.table.clear()
        preview = self.df.head(5)
        self.table.setRowCount(len(preview))
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        for i, row in preview.iterrows():
            for j, col in enumerate(self.columns):
                item = QTableWidgetItem(str(row[col]))
                self.table.setItem(i, j, item)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMaximumHeight(200)

    def setup_mapping(self):
        """Создаёт комбобоксы для сопоставления колонок с полями шаблона"""
        # Собираем все возможные поля шаблона (простые и поля внутри блоков)
        all_fields = []
        # Простые поля
        for field in self.template.fields:
            all_fields.append(("field", field.name))
        # Поля внутри блоков (опционально, можно ограничиться только простыми)
        for block in self.template.blocks:
            for field in block.fields:
                all_fields.append(("block_field", f"{block.name}.{field.name}"))

        # Очищаем старые виджеты
        layout = self.mapping_group.layout()
        # Удаляем все строки из form layout
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.mapping_widgets.clear()

        # Добавляем комбобоксы для каждой колонки
        for col in self.columns:
            label = QLabel(f"Колонка '{col}' →")
            combo = QComboBox()
            combo.addItem("(не использовать)", None)
            for typ, field_name in all_fields:
                combo.addItem(field_name, (typ, field_name))
            layout.addRow(label, combo)
            self.mapping_widgets.append((col, combo))

    def generate_zip(self):
        """Генерирует документы для каждой строки и упаковывает в ZIP"""
        if self.df is None:
            return

        # Собираем маппинг колонка -> (тип, имя поля)
        mapping = {}
        for col, combo in self.mapping_widgets:
            data = combo.currentData()
            if data is not None:
                typ, field_name = data
                mapping[col] = (typ, field_name)

        if not mapping:
            QMessageBox.warning(self, "Ошибка", "Не выбрано ни одного сопоставления колонок")
            return

        # Создаём временную папку для документов
        with tempfile.TemporaryDirectory() as tmpdir:
            output_files = []
            total_rows = len(self.df)
            self.progress.setVisible(True)
            self.progress.setMaximum(total_rows)
            self.generate_btn.setEnabled(False)

            for idx, row in self.df.iterrows():
                # Строим data_dict для текущей строки
                data_dict = {}
                for col, (typ, field_name) in mapping.items():
                    value = row[col]
                    if pd.isna(value):
                        value = ""
                    # Если поле внутри блока — надо поместить в список? Нет, при массовой генерации
                    # мы обычно генерируем один документ на строку, без повторяющихся блоков.
                    # Поэтому поля внутри блока не поддерживаем в простом варианте.
                    # Если всё же нужны блоки, надо парсить сложнее. Пока игнорируем block_field.
                    if typ == "field":
                        data_dict[field_name] = str(value)
                # Добавляем пустые списки для блоков (чтобы docxtpl не ругался)
                for block in self.template.blocks:
                    if block.name not in data_dict:
                        data_dict[block.name] = []

                # Генерируем документ
                out_name = f"doc_{idx+1}.docx"
                out_path = os.path.join(tmpdir, out_name)
                try:
                    generate_docx(self.template.file_path, data_dict, out_path)
                    output_files.append(out_path)
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Ошибка в строке {idx+1}:\n{str(e)}")
                    self.progress.setVisible(False)
                    self.generate_btn.setEnabled(True)
                    return
                self.progress.setValue(idx+1)

            # Создаём ZIP
            zip_path, _ = QFileDialog.getSaveFileName(self, "Сохранить архив", f"{self.template.name}_mass.zip", "ZIP files (*.zip)")
            if zip_path:
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for fpath in output_files:
                        zipf.write(fpath, os.path.basename(fpath))
                QMessageBox.information(self, "Успех", f"Создано {len(output_files)} документов\nСохранено в {zip_path}")
            else:
                QMessageBox.warning(self, "Отменено", "Архив не сохранён")
            self.accept()