# ui/mass_generate_dialog.py
import os
import tempfile
import zipfile
import pandas as pd
from logic.format_utils import format_date, format_number
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QWidget,
    QLabel, QProgressBar, QMessageBox, QGroupBox, QFormLayout,
    QRadioButton, QLineEdit, QCheckBox, QScrollArea, QSplitter
)
from PySide6.QtCore import Qt, QThread
from ui.mass_generate_worker import MassGenerateWorker

class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()
        return

class MassGenerateDialog(QDialog):
    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.template = template
        self.setWindowTitle(f"Массовая генерация: {template.name}")
        self.setMinimumSize(600, 400)
        self.setSizeGripEnabled(True)
        self.df = None
        self.columns = []
        self.all_fields = []
        self.field_mapping = {}
        self.worker = None
        self.worker_thread = None
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        scroll.setWidget(inner)

        # Группа загрузки файла
        file_group = QGroupBox("1. Выберите файл (CSV или Excel)")
        file_layout = QHBoxLayout(file_group)
        self.file_label = QLabel("Файл не выбран")
        self.select_btn = QPushButton("Выбрать файл")
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_btn)
        layout.addWidget(file_group)

        # Таблица предпросмотра и группа сопоставления — в одном сплиттере,
        # чтобы пользователь мог перетаскивать границу между ними.
        self.preview_splitter = QSplitter(Qt.Vertical)
        self.preview_splitter.setChildrenCollapsible(False)

        self.table = QTableWidget()
        self.table.setVisible(False)
        self.table.setMinimumHeight(100)
        self.preview_splitter.addWidget(self.table)

        # Группа сопоставления колонок
        self.mapping_group = QGroupBox("2. Сопоставьте колонки с полями шаблона")
        self.mapping_group.setVisible(False)
        mapping_layout = QVBoxLayout(self.mapping_group)

        # Чекбокс для переключения отображаемых имён
        self.show_display_names_cb = QCheckBox("Показывать отображаемые имена полей")
        self.show_display_names_cb.setChecked(True)  # по умолчанию показываем красивые имена
        self.show_display_names_cb.stateChanged.connect(self.on_display_names_toggled)
        mapping_layout.addWidget(self.show_display_names_cb)

        # Scroll area для компактности
        self.mapping_scroll = QScrollArea()
        self.mapping_scroll.setWidgetResizable(True)
        # Скролл может свободно расти и сжиматься, но не в ноль.
        # Никаких setMaximumHeight — размером управляет сплиттер.
        self.mapping_scroll.setMinimumHeight(80)
        from PySide6.QtWidgets import QSizePolicy
        self.mapping_scroll.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        mapping_scroll_widget = QWidget()
        self.mapping_form_layout = QFormLayout(mapping_scroll_widget)
        self.mapping_form_layout.setVerticalSpacing(5)
        self.mapping_scroll.setWidget(mapping_scroll_widget)
        mapping_layout.addWidget(self.mapping_scroll)

        self.preview_splitter.addWidget(self.mapping_group)
        self.preview_splitter.setStretchFactor(0, 0)  # таблица — не тянется
        self.preview_splitter.setStretchFactor(1, 1)  # mapping — тянется
        self.preview_splitter.setSizes([200, 400])
        layout.addWidget(self.preview_splitter, 1)

        # Инициализация списка виджетов
        self.mapping_widgets = []

        # Группа настроек генерации
        self.settings_group = QGroupBox("3. Настройки генерации")
        self.settings_group.setVisible(False)
        settings_layout = QVBoxLayout(self.settings_group)

        # Режим генерации
        mode_layout = QHBoxLayout()
        self.single_file_radio = QRadioButton("Один файл (с разрывами страниц)")
        self.multi_file_radio = QRadioButton("Несколько файлов (ZIP)")
        self.multi_file_radio.setChecked(True)
        mode_layout.addWidget(self.single_file_radio)
        mode_layout.addWidget(self.multi_file_radio)
        settings_layout.addLayout(mode_layout)

        # Маска имени файла
        mask_layout = QHBoxLayout()
        self.name_mask_label = QLabel("Шаблон имени файла:")
        self.name_mask_edit = QLineEdit()
        self.name_mask_edit.setPlaceholderText("например: Счет_{doc_number}_{client_name}")
        mask_layout.addWidget(self.name_mask_label)
        mask_layout.addWidget(self.name_mask_edit)
        settings_layout.addLayout(mask_layout)

        # Опция ZIP (для нескольких файлов)
        self.zip_check = QCheckBox("Создать ZIP-архив (иначе сохранить в папку)")
        self.zip_check.setChecked(True)
        settings_layout.addWidget(self.zip_check)

        # Скрываем маску и ZIP в single-режиме
        self.single_file_radio.toggled.connect(self._on_mode_changed)
        self.multi_file_radio.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()

        layout.addWidget(self.settings_group)

        self.phase_label = QLabel()
        self.phase_label.setVisible(False)
        layout.addWidget(self.phase_label)

        # Прогресс
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Сгенерировать")
        self.generate_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Отмена")
        btn_layout.addStretch()
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # Сигналы
        self.select_btn.clicked.connect(self.load_file)
        self.generate_btn.clicked.connect(self.generate)
        self.cancel_btn.clicked.connect(self.reject)

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл", "",
            "Excel и CSV (*.xlsx *.xls *.xlsm *.csv);;"
            "Excel (*.xlsx *.xls *.xlsm);;"
            "CSV (*.csv);;"
            "Все файлы (*)"
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
        self.df.columns = [str(c) for c in self.df.columns]
        self.columns = list(self.df.columns)
        self.show_preview()
        self.setup_mapping()
        self.table.setVisible(True)
        self.mapping_group.setVisible(True)
        self.settings_group.setVisible(True)
        self.generate_btn.setEnabled(True)

    def show_preview(self):
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

    def setup_mapping(self):
        self.rebuild_mapping_ui()
        self.auto_select_mapping()

    def generate(self):
        if self.df is None:
            return
        mapping = {}
        for col, combo in self.mapping_widgets:
            data = combo.currentData()
            if data is not None:
                mapping[col] = data
        if not mapping:
            QMessageBox.warning(self, "Ошибка",
                                "Не выбрано ни одного сопоставления колонок")
            return

        # 1. Определяем режим и спрашиваем путь ДО старта
        if self.single_file_radio.isChecked():
            mode = "single"
            output_path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить документ",
                f"{self.template.name}_merged.docx",
                "Word files (*.docx)")
            if not output_path:
                return
            name_mask = ""
        else:
            name_mask = self.name_mask_edit.text().strip()
            if self.zip_check.isChecked():
                mode = "multi_zip"
                output_path, _ = QFileDialog.getSaveFileName(
                    self, "Сохранить архив",
                    f"{self.template.name}_mass.zip",
                    "ZIP files (*.zip)")
                if not output_path:
                    return
            else:
                mode = "multi_folder"
                output_path = QFileDialog.getExistingDirectory(
                    self, "Выберите папку для сохранения")
                if not output_path:
                    return

        # 2. UI: блокируем кнопки, показываем прогресс
        self.phase_label.setText("Генерация документов…")
        self.phase_label.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.generate_btn.setEnabled(False)

        # 3. Worker + thread
        self.worker = MassGenerateWorker(
            template=self.template,
            df=self.df,
            mapping=mapping,
            mode=mode,
            output_path=output_path,
            name_mask=name_mask,
            get_field_info=self.get_field_info,
            format_value=self.format_value,
        )
        self.worker_thread = QThread(self)
        self.worker_thread = QThread(self)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.phase_changed.connect(self._on_phase_changed)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.cancelled.connect(self._on_cancelled)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker.cancelled.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._on_thread_finished)

        self.worker_thread.start()

    def _on_progress(self, current, total):
        if total <= 0:
            return
        percent = int(current * 100 / total)
        self.progress.setValue(percent)

    def _on_mode_changed(self):
        is_single = self.single_file_radio.isChecked()
        # В single-режиме маска имени и ZIP не имеют смысла
        self.name_mask_label.setVisible(not is_single)
        self.name_mask_edit.setVisible(not is_single)
        self.zip_check.setVisible(not is_single)

    def _on_phase_changed(self, phase):
        if phase == "generating":
            self.phase_label.setText("Генерация документов…")
        elif phase == "merging":
            self.phase_label.setText("Объединение документов…")
        elif phase == "saving":
            self.phase_label.setText("Сохранение…")

    def _on_finished(self, message, count):
        QMessageBox.information(self, "Успех", message)
        self.accept()

    def _on_error(self, message, row_idx):
        QMessageBox.critical(self, "Ошибка", message)

    def _on_cancelled(self):
        QMessageBox.information(self, "Отменено", "Генерация отменена.")

    def _on_thread_finished(self):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.phase_label.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.worker = None
        self.worker_thread = None

    def reject(self):
        if self.worker is not None:
            self.worker.cancel()
            return
        super().reject()

    def get_field_info(self, field_name):
        """Возвращает информацию о поле (тип, формат и т.д.) из настроек шаблона"""
        key = f"field:{field_name}"
        data = self.parent().display_names.get(self.template.id, {}).get(key, {})
        if isinstance(data, str):
            return {"type": "text", "format": ""}
        return {
            "type": data.get("type", "text"),
            "format": data.get("format", "")
        }

    def format_value(self, value, field_info):
        field_type = field_info.get("type", "text")
        fmt = field_info.get("format", "")

        if pd.isna(value):
            return ""

        if field_type == "date":
            return format_date(value, fmt)
        elif field_type == "number":
            return format_number(value, fmt)
        elif field_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "да")
            return bool(value)
        else:
            return str(value)

    def on_display_names_toggled(self):
        if not hasattr(self, 'mapping_widgets') or not self.mapping_widgets:
            return
        # Сохраняем текущие выбранные поля для каждой колонки
        selected_fields = {}
        for col, combo in self.mapping_widgets:
            data = combo.currentData()
            if data is not None:
                selected_fields[col] = data  # (typ, field_name)
            else:
                selected_fields[col] = None
        # Перестраиваем UI сопоставления
        self.rebuild_mapping_ui()
        # Восстанавливаем выбранные значения
        for col, combo in self.mapping_widgets:
            data = selected_fields.get(col)
            if data is None:
                combo.setCurrentIndex(0)
            else:
                # ищем индекс с соответствующими данными
                for idx in range(combo.count()):
                    if combo.itemData(idx) == data:
                        combo.setCurrentIndex(idx)
                        break

    def rebuild_mapping_ui(self):
        # Очищаем старые виджеты
        for i in reversed(range(self.mapping_form_layout.count())):
            widget = self.mapping_form_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.mapping_widgets.clear()

        # Собираем список полей для отображения
        all_fields = []
        for field in self.template.fields:
            if self.show_display_names_cb.isChecked():
                display, _ = self.parent().get_display_info(self.template.id, field.name, "field")
                display_name = display if display else field.name
            else:
                display_name = field.name
            all_fields.append((display_name, "field", field.name))
        self.all_fields = all_fields  # сохраняем для auto_select

        # Создаём строки для каждой колонки
        for col in self.columns:
            label = QLabel(f"Колонка '{col}' →")
            combo = NoWheelComboBox()
            combo.addItem("(не использовать)", None)
            for display_name, typ, field_name in all_fields:
                combo.addItem(display_name, (typ, field_name))
            self.mapping_form_layout.addRow(label, combo)
            self.mapping_widgets.append((col, combo))

    def auto_select_mapping(self):
        if not hasattr(self, 'mapping_widgets') or not self.mapping_widgets:
            return
        if not hasattr(self, 'all_fields') or not self.all_fields:
            return
        lookup = {}
        for display_name, typ, field_name in self.all_fields:
            lookup[display_name.lower()] = (typ, field_name)
            lookup[field_name.lower()] = (typ, field_name)

        for col, combo in self.mapping_widgets:
            col_lower = col.lower()
            if col_lower in lookup:
                target_data = lookup[col_lower]
                for idx in range(combo.count()):
                    if combo.itemData(idx) == target_data:
                        combo.setCurrentIndex(idx)
                        break