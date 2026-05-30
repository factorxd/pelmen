# ui/main_window.py
import os
import json
import tempfile
import shutil
import sys

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QFileDialog, QMessageBox,
    QFileSystemModel, QScrollArea, QLineEdit, QPushButton, QLabel,
    QDateEdit, QFrame, QGroupBox, QDialog,
    QTabWidget, QCheckBox, QDoubleSpinBox, QTextEdit
)
from PySide6.QtCore import Qt, QDir, QDate
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication

from logic.template_parser import parse_docx_template
from logic.data_models import Template
from logic.doc_generator import generate_docx

from ui.helper_dialog import HelperDialog
from ui.settings_dialog import SettingsDialog
from ui.mass_generate_dialog import MassGenerateDialog

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Пельмень")
        self.setGeometry(200, 200, 1100, 700)
        self.setWindowIcon(QIcon(resource_path("icons/pelmen2.ico")))

        self.data_dir = "data"

        self.drafts_dir = os.path.join(self.data_dir, "drafts")
        os.makedirs(self.drafts_dir, exist_ok=True)
        self.draft_timer = None

        self.settings_file = os.path.join(self.data_dir, "settings.json")
        self.display_names_file = os.path.join(self.data_dir, "display_names.json")
        os.makedirs(self.data_dir, exist_ok=True)

        self.root_folder = ""
        self.current_template = None
        self.simple_widgets = {}
        self.block_widgets = {}
        self.display_names = {}  # { template_id: { key: {"display": str, "category": str} } }
        self.block_layouts = {}

        self.load_display_names()
        self.init_ui()
        self.load_settings()
        if self.root_folder:
            self.set_root_folder(self.root_folder)
        else:
            self.ask_for_folder()

        # Очистка старых временных файлов предпросмотра
        preview_temp_dir = os.path.join(self.data_dir, "temp_preview")
        if os.path.exists(preview_temp_dir):
            for f in os.listdir(preview_temp_dir):
                try:
                    os.remove(os.path.join(preview_temp_dir, f))
                except:
                    pass

    def init_ui(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл")
        choose_folder_action = file_menu.addAction("Выбрать папку с шаблонами")
        choose_folder_action.triggered.connect(self.choose_root_folder)
        helper_action = file_menu.addAction("Помощник разметки")
        helper_action.triggered.connect(self.open_helper)
        mass_btn = file_menu.addAction("Массовая генерация из CSV/Excel")
        mass_btn.triggered.connect(self.mass_generate)
        preview_action = file_menu.addAction("Предпросмотр документа")
        preview_action.triggered.connect(self.preview_document)
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        help_menu = menubar.addMenu("Справка")
        help_action = help_menu.addAction("Как пользоваться")
        help_action.triggered.connect(self.show_help)
        about_action = help_menu.addAction("О программе")
        about_action.triggered.connect(self.show_about)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Статус-бар
        self.statusBar().showMessage("Готово")

        # Горячие клавиши (добавляем как действия, невидимые в меню)
        helper_shortcut = QAction(self)
        helper_shortcut.setShortcut("Ctrl+N")
        helper_shortcut.triggered.connect(self.open_helper)
        self.addAction(helper_shortcut)

        folder_shortcut = QAction(self)
        folder_shortcut.setShortcut("Ctrl+O")
        folder_shortcut.triggered.connect(self.choose_root_folder)
        self.addAction(folder_shortcut)

        preview_shortcut = QAction(self)
        preview_shortcut.setShortcut("Ctrl+Shift+S")
        preview_shortcut.triggered.connect(self.preview_document)
        self.addAction(preview_shortcut)

        mass_shortcut = QAction(self)
        mass_shortcut.setShortcut("Ctrl+Shift+G")
        mass_shortcut.triggered.connect(self.mass_generate)
        self.addAction(mass_shortcut)

        splitter = QSplitter(Qt.Horizontal)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(15)
        self.tree_view.clicked.connect(self.on_tree_click)
        splitter.addWidget(self.tree_view)

        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        splitter.addWidget(self.right_panel)

        splitter.setSizes([300, 800])
        main_layout.addWidget(splitter)

        self.show_placeholder()

    def show_placeholder(self):
        self.clear_right_panel()
        label = QLabel("Выберите шаблон в левой панели")
        label.setAlignment(Qt.AlignCenter)
        self.right_layout.addWidget(label)

    def clear_right_panel(self):
        self.clear_layout(self.right_layout)
        self.simple_widgets.clear()
        self.block_widgets.clear()
        self.block_layouts.clear()

        if hasattr(self, 'category_tabs'):
            self.category_tabs.deleteLater()
            delattr(self, 'category_tabs')

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                self.root_folder = settings.get("root_folder", "")

    def save_settings(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump({"root_folder": self.root_folder}, f)

    def load_display_names(self):
        if os.path.exists(self.display_names_file):
            with open(self.display_names_file, "r", encoding="utf-8") as f:
                self.display_names = json.load(f)
        else:
            self.display_names = {}

    def save_display_names(self):
        with open(self.display_names_file, "w", encoding="utf-8") as f:
            json.dump(self.display_names, f, ensure_ascii=False, indent=2)

    def get_display_info(self, template_id, field_name, field_type="field"):
        """Возвращает (display_name, category) для поля/блока"""
        key = f"{field_type}:{field_name}"
        data = self.display_names.get(template_id, {}).get(key, {})
        if isinstance(data, str):
            # старый формат
            return data, ""
        return data.get("display", field_name), data.get("category", "")

    def set_display_info(self, template_id, field_name, display_name, category, field_type="field"):
        key = f"{field_type}:{field_name}"
        if template_id not in self.display_names:
            self.display_names[template_id] = {}
        self.display_names[template_id][key] = {"display": display_name, "category": category}
        self.save_display_names()

    def ask_for_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с шаблонами (.docx)")
        if folder:
            self.set_root_folder(folder)
        else:
            QMessageBox.warning(self, "Папка не выбрана", "Программа закроется, так как без папки работать нельзя.")
            self.close()

    def choose_root_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с шаблонами (.docx)")
        if folder:
            self.set_root_folder(folder)

    def set_root_folder(self, folder):
        self.statusBar().showMessage(f"Загрузка папки: {folder}...")
        QApplication.processEvents()

        self.root_folder = folder
        self.save_settings()
        model = QFileSystemModel()
        model.setRootPath(folder)
        model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Files)
        model.setNameFilters(["*.docx"])
        model.setNameFilterDisables(False)
        self.tree_view.setModel(model)
        self.tree_view.setRootIndex(model.index(folder))
        for col in range(1, model.columnCount()):
            self.tree_view.hideColumn(col)
        self.current_template = None
        self.show_placeholder()

        self.statusBar().showMessage("Готово", 2000)

    def on_tree_click(self, index):
        model = self.tree_view.model()
        file_path = model.filePath(index)
        if os.path.isfile(file_path) and file_path.lower().endswith(".docx"):
            if hasattr(self, 'templates_cache') and file_path in self.templates_cache:
                self.current_template = self.templates_cache[file_path]
                self.build_form()
                return
            try:
                fields, blocks = parse_docx_template(file_path)
                name = os.path.splitext(os.path.basename(file_path))[0]
                template = Template(file_path, name, file_path, fields, blocks)
                if not hasattr(self, 'templates_cache'):
                    self.templates_cache = {}
                self.templates_cache[file_path] = template
                self.current_template = template
                self.build_form()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось разобрать шаблон:\n{str(e)}")
                self.current_template = None
                self.show_placeholder()
        else:
            self.current_template = None
            self.show_placeholder()

    def open_display_settings(self):
        if not self.current_template:
            return

        def save_settings(display_names):
            self.display_names = display_names
            self.save_display_names()
            self.build_form()

        dialog = SettingsDialog(self.current_template, self.display_names, save_settings, self)
        dialog.exec()

    def export_settings(self, parent_dialog):
        if not self.current_template:
            return
        file_path, _ = QFileDialog.getSaveFileName(parent_dialog, "Экспорт настроек", f"{self.current_template.name}_settings.json", "JSON files (*.json)")
        if file_path:
            tid = self.current_template.id
            settings_to_export = {tid: self.display_names.get(tid, {})}
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(settings_to_export, f, ensure_ascii=False, indent=2)
            QMessageBox.information(parent_dialog, "Успех", f"Настройки экспортированы в {file_path}")

    def import_settings(self, parent_dialog, edits_widgets):
        if not self.current_template:
            return
        file_path, _ = QFileDialog.getOpenFileName(parent_dialog, "Импорт настроек", "", "JSON files (*.json)")
        if not file_path:
            return
        with open(file_path, "r", encoding="utf-8") as f:
            imported = json.load(f)
        # Импортируем настройки для текущего шаблона (по id)
        tid = self.current_template.id
        for imported_tid, settings in imported.items():
            if imported_tid == tid:
                # Обновляем self.display_names
                if tid not in self.display_names:
                    self.display_names[tid] = {}
                self.display_names[tid].update(settings)
                # Обновляем поля в диалоге
                for key, value in settings.items():
                    # value может быть строкой (старый формат) или {"display": ..., "category": ...}
                    if isinstance(value, str):
                        display = value
                        category = ""
                    else:
                        display = value.get("display", "")
                        category = value.get("category", "")
                    # key имеет вид "field:name" или "block:name" или "block_field:block.field"
                    parts = key.split(":", 1)
                    if len(parts) == 2:
                        ftype, fname = parts
                        if (ftype, fname) in edits_widgets:
                            disp_edit, cat_edit = edits_widgets[(ftype, fname)]
                            disp_edit.setText(display)
                            cat_edit.setText(category)
                break
        self.save_display_names()
        QMessageBox.information(parent_dialog, "Успех", "Настройки импортированы. Нажмите OK для применения.")

    def build_form(self):
        if not self.current_template:
            return
        self.clear_right_panel()

        if not self.current_template.fields and not self.current_template.blocks:
            label = QLabel("В этом шаблоне нет переменных.\nВы можете использовать его как есть, нажав «Скачать DOCX».")
            label.setAlignment(Qt.AlignCenter)
            self.right_layout.addWidget(label)
            generate_btn = QPushButton("📄 Скачать DOCX")
            generate_btn.clicked.connect(self.generate_document)
            self.right_layout.addWidget(generate_btn)
            return

        # Кнопка настройки отображения (активна, только если есть поля)
        top_btn_layout = QHBoxLayout()
        settings_btn = QPushButton("⚙️ Настроить отображаемые имена и категории")
        settings_btn.clicked.connect(self.open_display_settings)
        top_btn_layout.addWidget(settings_btn)
        top_btn_layout.addStretch()
        self.right_layout.addLayout(top_btn_layout)

        # Собираем поля и блоки с категориями
        items = []  # (category, type, name, obj)
        for field in self.current_template.fields:
            _, category = self.get_display_info(self.current_template.id, field.name, "field")
            items.append((category, "field", field.name, field))
        for block in self.current_template.blocks:
            _, category = self.get_display_info(self.current_template.id, block.name, "block")
            items.append((category, "block", block.name, block))

        # Группировка по категориям
        from collections import defaultdict
        groups = defaultdict(list)
        for cat, typ, name, obj in items:
            cat_key = cat.strip() if cat.strip() else "Без категории"
            groups[cat_key].append((typ, name, obj))

        # Порядок категорий из сохранённых
        saved_order = self.display_names.get(self.current_template.id, {}).get("_categories_order", [])
        if saved_order:
            ordered_cats = []
            for cat in saved_order:
                if cat in groups:
                    ordered_cats.append(cat)
            # Добавляем категории, которых нет в сохранённом порядке (например, новые)
            for cat in groups.keys():
                if cat not in ordered_cats:
                    ordered_cats.append(cat)
        else:
            ordered_cats = sorted(groups.keys(), key=lambda x: (x != "Без категории", x))

        # Создаём вкладки для категорий
        self.category_tabs = QTabWidget()
        self.right_layout.addWidget(self.category_tabs)

        # Для каждой категории создаём страницу со скроллом
        for cat in ordered_cats:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            form_widget = QWidget()
            form_layout = QVBoxLayout(form_widget)
            form_layout.setAlignment(Qt.AlignTop)

            # Добавляем поля и блоки этой категории
            for typ, name, obj in groups[cat]:
                if typ == "field":
                    display, _ = self.get_display_info(self.current_template.id, name, "field")
                    self.add_simple_field(form_layout, obj, display)
                else:  # block
                    block_display, _ = self.get_display_info(self.current_template.id, name, "block")
                    self.add_dynamic_block(form_layout, obj, block_display)

            scroll.setWidget(form_widget)
            tab_layout.addWidget(scroll)
            self.category_tabs.addTab(tab, cat)

        self.load_draft()   # без всяких вопросов

        # Кнопки внизу (добавляем после вкладок)
        btn_layout = QHBoxLayout()
        generate_btn = QPushButton("📄 Скачать DOCX")
        reset_btn = QPushButton("🔄 Очистить форму")
        btn_layout.addWidget(generate_btn)
        btn_layout.addWidget(reset_btn)
        self.right_layout.addLayout(btn_layout)

        generate_btn.clicked.connect(self.generate_document)
        reset_btn.clicked.connect(self.reset_form)

    def add_simple_field(self, layout, field, display_name):
        label = QLabel(display_name)
        if field.required:
            label.setText(label.text() + " *")
        # Получаем тип поля из настроек (по умолчанию "text")
        key = f"field:{field.name}"
        field_type = self.display_names.get(self.current_template.id, {}).get(key, {})
        if isinstance(field_type, str):
            field_type = "text"
        else:
            field_type = field_type.get("type", "text")

        if field_type == "date":
            edit = QDateEdit()
            edit.setDate(QDate.currentDate())
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("dd.MM.yyyy")
            edit.dateChanged.connect(self.schedule_draft_save)
        elif field_type == "bool":
            edit = QCheckBox()
            edit.stateChanged.connect(self.schedule_draft_save)
        elif field_type == "number":
            edit = QDoubleSpinBox()
            edit.setRange(-9999999.99, 9999999.99)
            edit.setDecimals(2)
            edit.valueChanged.connect(self.schedule_draft_save)
            edit.textChanged.connect(self.schedule_draft_save)
        else:
            edit = QLineEdit()
            edit.textChanged.connect(self.schedule_draft_save)

        layout.addWidget(label)
        layout.addWidget(edit)
        self.simple_widgets[field.name] = edit

    def add_dynamic_block(self, layout, block, block_display_name, category=None):
        group_box = QGroupBox(block_display_name)
        group_layout = QVBoxLayout(group_box)
        self.block_layouts[block.name] = group_layout
        block_key = block.name
        self.block_widgets[block_key] = []
        self.add_block_card(block, group_layout, block_key)
        add_btn = QPushButton("+ Добавить ещё")
        add_btn.clicked.connect(lambda checked, b=block, l=group_layout, key=block_key: self.add_block_card(b, l, key))
        group_layout.addWidget(add_btn)
        layout.addWidget(group_box)

    def add_block_card(self, block, parent_layout, block_key):
        card_frame = QFrame()
        card_frame.setFrameShape(QFrame.StyledPanel)
        card_layout = QVBoxLayout(card_frame)

        header_layout = QHBoxLayout()
        label = QLabel(f"Элемент {len(self.block_widgets.get(block_key, [])) + 1}")
        remove_btn = QPushButton("🗑️ Удалить")
        remove_btn.setFixedWidth(80)
        header_layout.addWidget(label)
        header_layout.addStretch()
        header_layout.addWidget(remove_btn)
        card_layout.addLayout(header_layout)

        fields_widgets = {}
        for field in block.fields:
            display, _ = self.get_display_info(self.current_template.id, f"{block.name}.{field.name}", "block_field")
            if not display or display == field.name:
                display, _ = self.get_display_info(self.current_template.id, f"{block.name}.{field.name}",
                                                   "block_field")
            field_label = QLabel(display)

            # Определяем тип поля
            key = f"block_field:{block.name}.{field.name}"
            data = self.display_names.get(self.current_template.id, {}).get(key, {})
            if isinstance(data, str):
                field_type = "text"
            else:
                field_type = data.get("type", "text")

            if field_type == "date":
                edit = QDateEdit()
                edit.setDate(QDate.currentDate())
                edit.dateChanged.connect(self.schedule_draft_save)
            elif field_type == "bool":
                edit = QCheckBox()
                edit.stateChanged.connect(self.schedule_draft_save)
            elif field_type == "number":
                edit = QDoubleSpinBox()
                edit.setRange(-9999999.99, 9999999.99)
                edit.setDecimals(2)
                edit.valueChanged.connect(self.schedule_draft_save)
                edit.textChanged.connect(self.schedule_draft_save)
            else:  # text
                edit = QLineEdit()
                edit.textChanged.connect(self.schedule_draft_save)

            card_layout.addWidget(field_label)
            card_layout.addWidget(edit)
            fields_widgets[field.name] = edit

        card_data = {"frame": card_frame, "fields": fields_widgets}
        self.block_widgets.setdefault(block_key, []).append(card_data)

        # Вставляем перед кнопкой "Добавить ещё"
        add_btn_index = parent_layout.count() - 1
        parent_layout.insertWidget(add_btn_index, card_frame)

        remove_btn.clicked.connect(lambda checked, key=block_key, card=card_data: self.remove_block_card(key, card))
        self.schedule_draft_save()

    def remove_block_card(self, block_key, card_data):
        if card_data in self.block_widgets[block_key]:
            self.block_widgets[block_key].remove(card_data)
            card_data["frame"].deleteLater()
            self.renumber_block_cards(block_key)
            self.schedule_draft_save()  # сохраняем после удаления

    def renumber_block_cards(self, block_key):
        for idx, card in enumerate(self.block_widgets[block_key]):
            for child in card["frame"].findChildren(QLabel):
                if child.text().startswith("Элемент"):
                    child.setText(f"Элемент {idx+1}")
                    break

    def collect_data(self):
        data = {}

        # ---- Русские названия месяцев (для форматирования дат) ----
        months_full = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                       'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
        months_short = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн',
                        'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

        def format_date(qdate, fmt):
            if not fmt:
                return qdate.toString("dd.MM.yyyy")
            from datetime import datetime
            dt = datetime(qdate.year(), qdate.month(), qdate.day())
            if '%B' in fmt or '%b' in fmt:
                result = fmt.replace('%B', months_full[dt.month - 1]).replace('%b', months_short[dt.month - 1])
                import locale
                locale.setlocale(locale.LC_TIME, 'C')
                temp = result.replace(months_full[dt.month - 1], 'MONTH_FULL').replace(months_short[dt.month - 1],
                                                                                       'MONTH_SHORT')
                temp = dt.strftime(temp)
                temp = temp.replace('MONTH_FULL', months_full[dt.month - 1]).replace('MONTH_SHORT',
                                                                                     months_short[dt.month - 1])
                return temp
            else:
                try:
                    return dt.strftime(fmt)
                except:
                    return qdate.toString("dd.MM.yyyy")

        # ---- Сбор простых полей ----
        for name, widget in self.simple_widgets.items():
            key = f"field:{name}"
            info = self.display_names.get(self.current_template.id, {}).get(key, {})
            field_type = info.get("type", "text")
            fmt = info.get("format", "")
            val = None

            if isinstance(widget, QLineEdit):
                val = widget.text()
            elif isinstance(widget, QDateEdit):
                val = format_date(widget.date(), fmt)
            elif isinstance(widget, QCheckBox):
                val = widget.isChecked()
            elif isinstance(widget, QDoubleSpinBox):
                val = widget.value()
                # Применяем формат для чисел, если он задан
                if fmt and field_type == "number":
                    try:
                        val = fmt.format(val)
                    except:
                        pass
            else:
                val = None

            data[name] = val

        # ---- Сбор полей внутри блоков (списки) ----
        for block_name, cards in self.block_widgets.items():
            block_data = []
            for card in cards:
                item = {}
                for fname, fw in card["fields"].items():
                    key = f"block_field:{block_name}.{fname}"
                    info = self.display_names.get(self.current_template.id, {}).get(key, {})
                    field_type = info.get("type", "text")
                    fmt = info.get("format", "")
                    val = None

                    if isinstance(fw, QLineEdit):
                        val = fw.text()
                    elif isinstance(fw, QDateEdit):
                        val = format_date(fw.date(), fmt)
                    elif isinstance(fw, QCheckBox):
                        val = fw.isChecked()
                    elif isinstance(fw, QDoubleSpinBox):
                        val = fw.value()
                        if fmt and field_type == "number":
                            try:
                                val = fmt.format(val)
                            except:
                                pass
                    else:
                        val = None

                    item[fname] = val
                block_data.append(item)
            data[block_name] = block_data

        return data

        # ---- Сбор простых полей ----
        for name, widget in self.simple_widgets.items():
            key = f"field:{name}"
            info = self.display_names.get(self.current_template.id, {}).get(key, {})
            field_type = info.get("type", "text")
            fmt = info.get("format", "")
            val = None
            if isinstance(widget, QLineEdit):
                val = widget.text()
            elif isinstance(widget, QDateEdit):
                val = format_date(widget.date(), fmt)
            elif isinstance(widget, QCheckBox):
                val = widget.isChecked()
            elif isinstance(widget, QDoubleSpinBox):
                val = widget.value()
                if fmt and field_type == "number":
                    try:
                        val = fmt.format(val)
                        # Преобразуем 1,234.56 → 1 234,56 для русской нотации
                        if ',' in fmt and '.' in fmt:
                            val = val.replace(',', ' ').replace('.', ',')
                    except:
                        pass
            data[name] = val

        # ---- Блоки ----
        for block_name, cards in self.block_widgets.items():
            block_data = []
            for card in cards:
                item = {}
                for fname, fw in card["fields"].items():
                    key = f"block_field:{block_name}.{fname}"
                    info = self.display_names.get(self.current_template.id, {}).get(key, {})
                    field_type = info.get("type", "text")
                    fmt = info.get("format", "")
                    val = None
                    if isinstance(fw, QLineEdit):
                        val = fw.text()
                    elif isinstance(fw, QDateEdit):
                        val = format_date(fw.date(), fmt)
                    elif isinstance(fw, QCheckBox):
                        val = fw.isChecked()
                    elif isinstance(widget, QDoubleSpinBox):
                        val = widget.value()
                        if fmt and field_type == "number":
                            try:
                                val = fmt.format(val)
                                # Преобразуем 1,234.56 → 1 234,56 для русской нотации
                                if ',' in fmt and '.' in fmt:
                                    val = val.replace(',', ' ').replace('.', ',')
                            except:
                                pass
                    item[fname] = val
                block_data.append(item)
            data[block_name] = block_data
        return data

    def generate_document(self):
        if not self.current_template:
            return
        data = self.collect_data()
        missing = []
        for field in self.current_template.fields:
            if field.required and not data.get(field.name, ""):
                display, _ = self.get_display_info(self.current_template.id, field.name, "field")
                missing.append(display)
        if missing:
            QMessageBox.warning(self, "Ошибка", f"Заполните обязательные поля:\n" + "\n".join(missing))
            return

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            generate_docx(self.current_template.file_path, data, tmp_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать документ:\n{str(e)}")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Сохранить документ", f"{self.current_template.name}_готовый.docx", "Word files (*.docx)")
        if save_path:
            shutil.move(tmp_path, save_path)
            QMessageBox.information(self, "Успех", f"Документ сохранён:\n{save_path}")
        else:
            os.unlink(tmp_path)
        self.clear_draft()

    def reset_form(self):
        for widget in self.simple_widgets.values():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QDateEdit):
                widget.setDate(QDate.currentDate())
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(0.0)
        for block_name, cards in list(self.block_widgets.items()):
            while len(cards) > 1:
                self.remove_block_card(block_name, cards[-1])
            if cards:
                for fw in cards[0]["fields"].values():
                    if isinstance(fw, QLineEdit):
                        fw.clear()
                    elif isinstance(fw, QDateEdit):
                        fw.setDate(QDate.currentDate())
                    elif isinstance(fw, QCheckBox):
                        fw.setChecked(False)
                    elif isinstance(fw, QDoubleSpinBox):
                        fw.setValue(0.0)
        self.clear_draft()
        self.schedule_draft_save()

    def mass_generate(self):
        if not self.current_template:
            QMessageBox.warning(self, "Нет шаблона", "Сначала выберите шаблон в дереве.")
            return
        dialog = MassGenerateDialog(self.current_template, self)
        dialog.exec()

    def preview_document(self):
        if not self.current_template:
            QMessageBox.warning(self, "Нет шаблона", "Сначала выберите шаблон.")
            return

        # Собираем данные
        data = self.collect_data()
        missing = []
        for field in self.current_template.fields:
            if field.required and not data.get(field.name, ""):
                display, _ = self.get_display_info(self.current_template.id, field.name, "field")
                missing.append(display)
        if missing:
            QMessageBox.warning(self, "Ошибка", f"Заполните обязательные поля:\n" + "\n".join(missing))
            return

        # Создаём временный файл с уникальным именем
        temp_dir = os.path.join(self.data_dir, "temp_preview")
        os.makedirs(temp_dir, exist_ok=True)
        # Используем имя шаблона + timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp_path = os.path.join(temp_dir, f"preview_{self.current_template.name}_{timestamp}.docx")

        try:
            generate_docx(self.current_template.file_path, data, tmp_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать документ:\n{str(e)}")
            return

        # Открываем в программе по умолчанию (Word)
        os.startfile(tmp_path)

        # Автоматически удалим файл через 60 секунд (чтобы не забивать диск)
        # Но можно оставить и удалять при следующем запуске программы
        # Для простоты пока оставим, можно потом добавить фоновую очистку

    def get_draft_path(self, template_id):
        return os.path.join(self.drafts_dir, f"{template_id}.json")

    def save_draft(self):
        if not self.current_template:
            return
        data = self.collect_data()
        draft_path = self.get_draft_path(self.current_template.id)
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_draft(self):
        if not self.current_template:
            return
        draft_path = self.get_draft_path(self.current_template.id)
        if not os.path.exists(draft_path):
            return
        with open(draft_path, "r", encoding="utf-8") as f:
            draft_data = json.load(f)

        # Восстанавливаем простые поля
        for name, widget in self.simple_widgets.items():
            if name in draft_data:
                val = draft_data[name]
                if isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                elif isinstance(widget, QDateEdit):
                    from PySide6.QtCore import QDate
                    if val:
                        if isinstance(val, str):
                            widget.setDate(QDate.fromString(val, "yyyy-MM-dd"))
                        else:
                            pass
                elif isinstance(widget, QCheckBox):
                    if isinstance(val, bool):
                        widget.setChecked(val)
                    elif isinstance(val, str):
                        widget.setChecked(val.lower() == 'true')
                    else:
                        widget.setChecked(bool(val))
                elif isinstance(widget, QDoubleSpinBox):
                    if isinstance(val, (int, float)):
                        widget.setValue(val)
                    elif isinstance(val, str):
                        try:
                            widget.setValue(float(val))
                        except:
                            pass

        # Восстанавливаем блоки
        for block in self.current_template.blocks:
            block_name = block.name
            if block_name not in draft_data:
                continue
            block_items = draft_data[block_name]
            if not block_items:
                continue

            group_layout = self.block_layouts.get(block_name)
            if not group_layout:
                continue

            # Удаляем все существующие карточки
            if block_name in self.block_widgets:
                while self.block_widgets[block_name]:
                    self.remove_block_card(block_name, self.block_widgets[block_name][-1])

            # Добавляем карточки из черновика
            for item_data in block_items:
                self.add_block_card(block, group_layout, block_name)
                new_card = self.block_widgets[block_name][-1]
                for field_name, value in item_data.items():
                    if field_name in new_card["fields"]:
                        widget = new_card["fields"][field_name]
                        if isinstance(widget, QLineEdit):
                            widget.setText(str(value))
                        elif isinstance(widget, QDateEdit):
                            from PySide6.QtCore import QDate
                            if value:
                                if isinstance(value, str):
                                    widget.setDate(QDate.fromString(value, "yyyy-MM-dd"))
                                else:
                                    pass
                        elif isinstance(widget, QCheckBox):
                            if isinstance(value, bool):
                                widget.setChecked(value)
                            elif isinstance(value, str):
                                widget.setChecked(value.lower() == 'true')
                            else:
                                widget.setChecked(bool(value))
                        elif isinstance(widget, QDoubleSpinBox):
                            if isinstance(value, (int, float)):
                                widget.setValue(value)
                            elif isinstance(value, str):
                                try:
                                    widget.setValue(float(value))
                                except:
                                    pass

    def clear_draft(self):
        if self.current_template:
            draft_path = self.get_draft_path(self.current_template.id)
            if os.path.exists(draft_path):
                os.remove(draft_path)

    def schedule_draft_save(self):
        if not self.current_template:
            return
        if hasattr(self, '_draft_timer') and self._draft_timer is not None:
            self._draft_timer.stop()
        else:
            from PySide6.QtCore import QTimer
            self._draft_timer = QTimer()
            self._draft_timer.setSingleShot(True)
            self._draft_timer.timeout.connect(self.save_draft)
        self._draft_timer.start(500)  # 0.5 секунды после последнего изменения

    def open_helper(self):
        dialog = HelperDialog(self)
        dialog.exec()

    def _show_html_dialog(self, title, html):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(750, 550)
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setHtml(html)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("QTextEdit { font-family: 'Segoe UI', Arial; font-size: 10pt; }")
        layout.addWidget(text_edit)
        btn = QPushButton("Закрыть")
        btn.clicked.connect(dialog.accept)
        btn.setFixedWidth(100)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        dialog.exec()

    def show_help(self):
        help_file = resource_path(os.path.join("data", "help.html"))
        if os.path.exists(help_file):
            with open(help_file, "r", encoding="utf-8") as f:
                help_text = f.read()
            styled = f"""
            <html><head><style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; line-height: 1.5; }}
                h3 {{ color: #2c3e50; }}
                code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; font-family: monospace; }}
                pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
            </style></head><body>
            {help_text}
            </body></html>
            """
            self._show_html_dialog("Как пользоваться", styled)
        else:
            QMessageBox.information(self, "Справка", "Файл справки не найден. Создайте help.html в папке data.")

    def show_about(self):
        about_html = """
        <html>
        <head><style>
            body { font-family: 'Segoe UI', Arial; text-align: center; margin: 40px; }
            h2 { color: #2c3e50; }
        </style></head>
        <body>
        <h2>Пельмень</h2>
        <p><b>Версия 1.0</b></p>
        <p>Простой шаблонизатор документов</p>
        <p>Сделано на Python + PySide6<br>
        Использует: python-docx, docxtpl</p>
        </body>
        </html>
        """
        self._show_html_dialog("О программе", about_html)