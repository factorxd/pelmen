# ui/main_window.py
import os
import json
import tempfile
import shutil
import sys
from collections import defaultdict
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QFileDialog, QMessageBox, QFileSystemModel,
    QScrollArea, QLineEdit, QPushButton, QLabel, QDateEdit,
    QFrame, QGroupBox, QDialog, QTabWidget, QCheckBox,
    QDoubleSpinBox, QTextEdit, QApplication, QMenu
)
from PySide6.QtCore import Qt, QDir, QDate, QSortFilterProxyModel, QTimer
from PySide6.QtGui import QAction, QIcon, QPalette, QColor

from logic.template_parser import parse_docx_template
from logic.data_models import Template
from logic.doc_generator import generate_docx
from ui.helper_dialog import HelperDialog
from ui.settings_dialog import SettingsDialog
from ui.mass_generate_dialog import MassGenerateDialog
from ui.presets_dialog import PresetsDialog

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class TreeFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, root_folder_callback, parent=None):
        super().__init__(parent)
        self.get_root_folder = root_folder_callback

    def filterAcceptsRow(self, source_row, source_parent):
        # Сначала применяем стандартный фильтр по имени
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        file_path = model.filePath(index)
        root = self.get_root_folder()
        if not root:
            return False
        # Показываем только элементы, путь которых начинается с root
        return file_path.startswith(root)

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
        self.display_names = {}
        self.block_layouts = {}
        self.templates_cache = {}

        self.light_palette = QApplication.instance().palette()

        self.load_display_names()
        self.init_ui()
        self.load_settings()
        if self.root_folder:
            self.set_root_folder(self.root_folder)
        else:
            self.ask_for_folder()

        # Очистка временных файлов предпросмотра
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
        open_folder_action = file_menu.addAction("Открыть папку с шаблонами")
        open_folder_action.triggered.connect(self.open_templates_folder)
        helper_action = file_menu.addAction("Помощник разметки")
        helper_action.triggered.connect(self.open_helper)
        presets_action = file_menu.addAction("Пресеты")
        presets_action.triggered.connect(self.open_presets)
        mass_btn = file_menu.addAction("Массовая генерация из CSV/Excel")
        mass_btn.triggered.connect(self.mass_generate)
        preview_action = file_menu.addAction("Предпросмотр документа")
        preview_action.triggered.connect(self.preview_document)
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        view_menu = menubar.addMenu("Вид")
        self.dark_theme_action = QAction("Тёмная тема", self)
        self.dark_theme_action.setCheckable(True)
        self.dark_theme_action.triggered.connect(self.toggle_dark_theme)
        view_menu.addAction(self.dark_theme_action)

        help_menu = menubar.addMenu("Справка")
        help_action = help_menu.addAction("Как пользоваться")
        help_action.triggered.connect(self.show_help)
        about_action = help_menu.addAction("О программе")
        about_action.triggered.connect(self.show_about)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        self.statusBar().showMessage("Готово")

        # Горячие клавиши
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

        # Левая панель с поиском
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Поиск шаблонов...")
        self.search_edit.textChanged.connect(self.filter_tree)

        clear_btn = QPushButton("✖")
        clear_btn.setFixedSize(20, 20)
        clear_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")

        def clear_search():
            self.search_edit.clear()
            self.filter_tree("")  # явно сбрасываем фильтр

        clear_btn.clicked.connect(clear_search)

        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(clear_btn)
        left_layout.addLayout(search_layout)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(15)
        self.tree_view.clicked.connect(self.on_tree_click)

        self.proxy_model = TreeFilterProxyModel(lambda: self.root_folder, self)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.tree_view.setModel(self.proxy_model)
        left_layout.addWidget(self.tree_view)

        splitter.addWidget(left_widget)

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
                dark_theme = settings.get("dark_theme", False)
                if hasattr(self, 'dark_theme_action'):
                    self.dark_theme_action.setChecked(dark_theme)
                    self.toggle_dark_theme(dark_theme)

    def save_settings(self):
        dark_theme_state = self.dark_theme_action.isChecked() if hasattr(self, 'dark_theme_action') else False
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump({"root_folder": self.root_folder, "dark_theme": dark_theme_state}, f)

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
        key = f"{field_type}:{field_name}"
        data = self.display_names.get(template_id, {}).get(key, {})
        if isinstance(data, str):
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
        self.proxy_model.setSourceModel(model)
        root_index = model.index(folder)
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(root_index))
        for col in range(1, model.columnCount()):
            self.tree_view.hideColumn(col)
        self.current_template = None
        self.show_placeholder()
        self.statusBar().showMessage("Готово", 2000)
        # Сбрасываем поиск
        self.search_edit.clear()
        self.filter_tree("")

    def open_templates_folder(self):
        if not self.root_folder or not os.path.exists(self.root_folder):
            QMessageBox.warning(self, "Ошибка", "Папка с шаблонами не выбрана или не существует.")
            return
        os.startfile(self.root_folder)

    def on_tree_click(self, index):
        source_index = self.proxy_model.mapToSource(index)
        model = self.proxy_model.sourceModel()
        file_path = model.filePath(source_index)
        if os.path.isfile(file_path) and file_path.lower().endswith(".docx"):
            if file_path in self.templates_cache:
                self.current_template = self.templates_cache[file_path]
                self.build_form()
                return
            try:
                fields, blocks = parse_docx_template(file_path)
                name = os.path.splitext(os.path.basename(file_path))[0]
                template = Template(file_path, name, file_path, fields, blocks)
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
        w, h = self.get_dialog_size("settings_dialog", 900, 650)

        def save_settings(display_names):
            self.display_names = display_names
            self.save_display_names()
            self.build_form()

        dialog = SettingsDialog(self.current_template, self.display_names, save_settings, self)
        dialog.resize(w, h)
        dialog.finished.connect(lambda: self.save_dialog_size("settings_dialog", dialog.size()))
        dialog.exec()

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

        top_btn_layout = QHBoxLayout()
        settings_btn = QPushButton("⚙️ Настройки шаблона")
        settings_btn.clicked.connect(self.open_display_settings)
        top_btn_layout.addWidget(settings_btn)
        top_btn_layout.addStretch()
        self.right_layout.addLayout(top_btn_layout)

        items = []
        for field in self.current_template.fields:
            _, category = self.get_display_info(self.current_template.id, field.name, "field")
            items.append((category, "field", field.name, field))
        for block in self.current_template.blocks:
            _, category = self.get_display_info(self.current_template.id, block.name, "block")
            items.append((category, "block", block.name, block))

        groups = defaultdict(list)
        for cat, typ, name, obj in items:
            cat_key = cat.strip() if cat.strip() else "Без категории"
            groups[cat_key].append((typ, name, obj))

        saved_order = self.display_names.get(self.current_template.id, {}).get("_categories_order", [])
        if saved_order:
            ordered_cats = [cat for cat in saved_order if cat in groups]
            for cat in groups.keys():
                if cat not in ordered_cats:
                    ordered_cats.append(cat)
        else:
            ordered_cats = sorted(groups.keys(), key=lambda x: (x != "Без категории", x))

        self.category_tabs = QTabWidget()
        self.right_layout.addWidget(self.category_tabs)

        for cat in ordered_cats:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            form_widget = QWidget()
            form_layout = QVBoxLayout(form_widget)
            form_layout.setAlignment(Qt.AlignTop)

            for typ, name, obj in groups[cat]:
                if typ == "field":
                    display, _ = self.get_display_info(self.current_template.id, name, "field")
                    self.add_simple_field(form_layout, obj, display)
                else:
                    block_display, _ = self.get_display_info(self.current_template.id, name, "block")
                    self.add_dynamic_block(form_layout, obj, block_display)

            scroll.setWidget(form_widget)
            tab_layout.addWidget(scroll)
            self.category_tabs.addTab(tab, cat)

        self.load_draft()

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
        key = f"field:{field.name}"
        info = self.display_names.get(self.current_template.id, {}).get(key, {})
        if isinstance(info, str):
            field_type = "text"
        else:
            field_type = info.get("type", "text")

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

        edit.setContextMenuPolicy(Qt.CustomContextMenu)
        edit.customContextMenuRequested.connect(lambda pos, w=edit: self.show_preset_menu_for_widget(w, pos))

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
                display, _ = self.get_display_info(self.current_template.id, f"{block.name}.{field.name}", "block_field")
            field_label = QLabel(display)

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
            else:
                edit = QLineEdit()
                edit.textChanged.connect(self.schedule_draft_save)

            edit.setContextMenuPolicy(Qt.CustomContextMenu)
            edit.customContextMenuRequested.connect(lambda p, w=edit: self.show_preset_menu_for_widget(w, p))

            card_layout.addWidget(field_label)
            card_layout.addWidget(edit)
            fields_widgets[field.name] = edit

        card_data = {"frame": card_frame, "fields": fields_widgets}
        self.block_widgets.setdefault(block_key, []).append(card_data)

        add_btn_index = parent_layout.count() - 1
        parent_layout.insertWidget(add_btn_index, card_frame)

        remove_btn.clicked.connect(lambda checked, key=block_key, card=card_data: self.remove_block_card(key, card))
        self.schedule_draft_save()

    def remove_block_card(self, block_key, card_data):
        if card_data in self.block_widgets[block_key]:
            self.block_widgets[block_key].remove(card_data)
            card_data["frame"].deleteLater()
            self.renumber_block_cards(block_key)
            self.schedule_draft_save()

    def renumber_block_cards(self, block_key):
        for idx, card in enumerate(self.block_widgets[block_key]):
            for child in card["frame"].findChildren(QLabel):
                if child.text().startswith("Элемент"):
                    child.setText(f"Элемент {idx+1}")
                    break

    def collect_data(self):
        data = {}
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
                result = fmt.replace('%B', months_full[dt.month-1]).replace('%b', months_short[dt.month-1])
                import locale
                locale.setlocale(locale.LC_TIME, 'C')
                temp = result.replace(months_full[dt.month-1], 'MONTH_FULL').replace(months_short[dt.month-1], 'MONTH_SHORT')
                temp = dt.strftime(temp)
                temp = temp.replace('MONTH_FULL', months_full[dt.month-1]).replace('MONTH_SHORT', months_short[dt.month-1])
                return temp
            else:
                try:
                    return dt.strftime(fmt)
                except:
                    return qdate.toString("dd.MM.yyyy")

        for name, widget in self.simple_widgets.items():
            key = f"field:{name}"
            info = self.display_names.get(self.current_template.id, {}).get(key, {})
            field_type = info.get("type", "text")
            fmt = info.get("format", "")
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
                    except:
                        pass
            else:
                val = None
            data[name] = val

        for block_name, cards in self.block_widgets.items():
            block_data = []
            for card in cards:
                item = {}
                for fname, fw in card["fields"].items():
                    key = f"block_field:{block_name}.{fname}"
                    info = self.display_names.get(self.current_template.id, {}).get(key, {})
                    field_type = info.get("type", "text")
                    fmt = info.get("format", "")
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
        w, h = self.get_dialog_size("mass_generate_dialog", 800, 600)
        dialog = MassGenerateDialog(self.current_template, self)
        dialog.resize(w, h)
        dialog.finished.connect(lambda: self.save_dialog_size("mass_generate_dialog", dialog.size()))
        dialog.exec()

    def preview_document(self):
        if not self.current_template:
            QMessageBox.warning(self, "Нет шаблона", "Сначала выберите шаблон.")
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

        temp_dir = os.path.join(self.data_dir, "temp_preview")
        os.makedirs(temp_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp_path = os.path.join(temp_dir, f"preview_{self.current_template.name}_{timestamp}.docx")
        try:
            generate_docx(self.current_template.file_path, data, tmp_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать документ:\n{str(e)}")
            return
        os.startfile(tmp_path)

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

        for name, widget in self.simple_widgets.items():
            if name in draft_data:
                val = draft_data[name]
                if isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                elif isinstance(widget, QDateEdit):
                    if val:
                        if isinstance(val, str):
                            widget.setDate(QDate.fromString(val, "yyyy-MM-dd"))
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
            if block_name in self.block_widgets:
                while self.block_widgets[block_name]:
                    self.remove_block_card(block_name, self.block_widgets[block_name][-1])
            for item_data in block_items:
                self.add_block_card(block, group_layout, block_name)
                new_card = self.block_widgets[block_name][-1]
                for field_name, value in item_data.items():
                    if field_name in new_card["fields"]:
                        widget = new_card["fields"][field_name]
                        if isinstance(widget, QLineEdit):
                            widget.setText(str(value))
                        elif isinstance(widget, QDateEdit):
                            if value:
                                if isinstance(value, str):
                                    widget.setDate(QDate.fromString(value, "yyyy-MM-dd"))
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
            self._draft_timer = QTimer()
            self._draft_timer.setSingleShot(True)
            self._draft_timer.timeout.connect(self.save_draft)
        self._draft_timer.start(500)

    def toggle_dark_theme(self, checked):
        app = QApplication.instance()
        if checked:
            self.search_edit.setStyleSheet(
                "QLineEdit { color: white; background: #3c3c3c; } QLineEdit[placeholderText] { color: #aaaaaa; }")
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(43, 43, 43))
            palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
            palette.setColor(QPalette.Base, QColor(30, 30, 30))
            palette.setColor(QPalette.AlternateBase, QColor(43, 43, 43))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
            palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.Text, QColor(255, 255, 255))
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
            app.setPalette(palette)
            app.setStyleSheet("""
                QLineEdit {
                    color: white;
                    background: #3c3c3c;
                    selection-background-color: #2a82da;
                }
                QLineEdit:focus {
                    border: 1px solid #2a82da;
                }
                QLineEdit[placeholderText] {
                    color: #aaaaaa;
                }
                QTextEdit {
                    background: #2b2b2b;
                    color: white;
                }
                QTextEdit:focus {
                    border: 1px solid #2a82da;
                }
                QToolTip {
                    background-color: #ffffdc;
                    color: black;
                    border: 1px solid black;
                }
            """)
        else:
            self.search_edit.setStyleSheet("")
            app.setPalette(self.light_palette)
            app.setStyleSheet("")
        app.setStyle('Fusion')

    def open_presets(self):
        w, h = self.get_dialog_size("presets_dialog", 600, 450)
        dialog = PresetsDialog(self)
        dialog.resize(w, h)
        dialog.finished.connect(lambda: self.save_dialog_size("presets_dialog", dialog.size()))
        dialog.exec()

    def filter_tree(self, text):
        self.proxy_model.setFilterWildcard(text)
        # Принудительно обновляем корень дерева, чтобы после очистки не улететь на диск C:
        if self.root_folder and self.proxy_model.sourceModel():
            root_index = self.proxy_model.sourceModel().index(self.root_folder)
            self.tree_view.setRootIndex(self.proxy_model.mapFromSource(root_index))

    def open_helper(self):
        w, h = self.get_dialog_size("helper_dialog", 550, 500)
        dialog = HelperDialog(self)
        dialog.resize(w, h)
        dialog.finished.connect(lambda: self.save_dialog_size("helper_dialog", dialog.size()))
        dialog.exec()

    def _show_html_dialog(self, title, html):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(750, 550)
        dialog.setSizeGripEnabled(True)
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setHtml(html)
        text_edit.setReadOnly(True)
        # Убираем локальный стиль, доверяем HTML
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
                original_html = f.read()
            is_dark = self.dark_theme_action.isChecked() if hasattr(self, 'dark_theme_action') else False
            if is_dark:
                # Вставляем стили в начало <head>
                # Удаляем существующий <style> и вставляем свой с !important
                import re
                # Удаляем старый style
                html_no_style = re.sub(r'<style[^>]*>.*?</style>', '', original_html, flags=re.DOTALL)
                new_style = """
                <style>
                    body {
                        background-color: #2b2b2b !important;
                        color: #e0e0e0 !important;
                        font-family: 'Segoe UI', Arial, sans-serif;
                        margin: 20px;
                        line-height: 1.5;
                    }
                    h3, h4 { color: #ffffff !important; }
                    code {
                        background: #3c3c3c !important;
                        padding: 2px 4px;
                        border-radius: 4px;
                        font-family: monospace;
                        color: #ffcc00 !important;
                    }
                    pre {
                        background: #1e1e1e !important;
                        padding: 10px;
                        border-radius: 5px;
                        overflow-x: auto;
                        color: #f8f8f2 !important;
                        border: 1px solid #444;
                    }
                    .note {
                        background: #2a2a2a !important;
                        padding: 10px;
                        border-left: 4px solid #2a82da;
                        margin: 15px 0;
                        color: #cccccc !important;
                    }
                    .hotkey { color: #ffaa66 !important; font-weight: bold; }
                    table {
                        border-collapse: collapse;
                        width: 100%;
                        margin: 15px 0;
                        background-color: #2b2b2b;
                    }
                    th, td {
                        border: 1px solid #555;
                        padding: 8px;
                        text-align: left;
                        color: #e0e0e0 !important;
                    }
                    th { background-color: #3c3c3c; }
                </style>
                """
                # Вставляем новый стиль после <head>
                styled = html_no_style.replace('<head>', '<head>' + new_style, 1)
            else:
                # Светлая тема: оставляем оригинальный стиль
                styled = original_html
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

    def get_presets_data(self):
        presets_file = os.path.join(self.data_dir, "presets.json")
        if not os.path.exists(presets_file):
            return {}
        with open(presets_file, "r", encoding="utf-8") as f:
            presets = json.load(f)  # список {"name":..., "value":..., "category":...}
        result = {}
        for p in presets:
            cat = p.get("category", "") or "Без категории"
            if cat not in result:
                result[cat] = []
            result[cat].append((p["name"], p["value"]))
        return result

    def get_presets_menu(self, parent_widget):
        menu = QMenu(parent_widget)
        menu.setTitle("Вставить из пресетов")
        presets_data = self.get_presets_data()
        if not presets_data:
            no_action = QAction("Нет сохранённых пресетов", menu)
            no_action.setEnabled(False)
            menu.addAction(no_action)
            return menu
        for category, items in sorted(presets_data.items()):
            cat_menu = menu.addMenu(category)
            for name, value in sorted(items, key=lambda x: x[0]):
                action = QAction(name, cat_menu)
                action.setData(value)  # храним значение
                action.triggered.connect(lambda checked, v=value, w=parent_widget: self.insert_preset_value(w, v))
                cat_menu.addAction(action)
        return menu

    def insert_preset_value(self, widget, value):
        if isinstance(widget, QLineEdit):
            widget.insert(value)
        elif isinstance(widget, QTextEdit):
            widget.insertPlainText(value)
        elif isinstance(widget, QDoubleSpinBox):
            try:
                widget.setValue(float(value))
            except:
                pass
        elif isinstance(widget, QDateEdit):
            from PySide6.QtCore import QDate
            # пробуем разные форматы
            for fmt in ("dd.MM.yyyy", "yyyy-MM-dd", "dd/MM/yyyy"):
                date = QDate.fromString(value, fmt)
                if date.isValid():
                    widget.setDate(date)
                    break
        # Для QCheckBox? Не нужно, там пресеты не нужны.

    def show_preset_menu_for_widget(self, widget, pos):
        menu = QMenu()
        # Стандартные действия для виджета
        if hasattr(widget, 'createStandardContextMenu'):
            standard_menu = widget.createStandardContextMenu()
            # Копируем действия из стандартного меню
            for action in standard_menu.actions():
                menu.addAction(action)
        else:
            # Если стандартного нет, добавим базовые для QLineEdit
            if isinstance(widget, QLineEdit):
                copy_action = QAction("Копировать", widget)
                copy_action.triggered.connect(widget.copy)
                paste_action = QAction("Вставить", widget)
                paste_action.triggered.connect(widget.paste)
                cut_action = QAction("Вырезать", widget)
                cut_action.triggered.connect(widget.cut)
                menu.addAction(cut_action)
                menu.addAction(copy_action)
                menu.addAction(paste_action)

        menu.addSeparator()
        # Подменю пресетов
        presets_menu = self.get_presets_menu(widget)
        # get_presets_menu возвращает QMenu с вложенными категориями
        menu.addMenu(presets_menu)

        menu.exec(widget.mapToGlobal(pos))

    def get_dialog_size(self, dialog_name, default_width=800, default_height=600):
        """Возвращает сохранённый размер диалога или значение по умолчанию"""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                sizes = settings.get("dialog_sizes", {})
                size = sizes.get(dialog_name)
                if size and len(size) == 2:
                    return size[0], size[1]
        return default_width, default_height

    def save_dialog_size(self, dialog_name, size):
        """Сохраняет размер диалога в settings.json"""
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except:
            settings = {}
        if "dialog_sizes" not in settings:
            settings["dialog_sizes"] = {}
        settings["dialog_sizes"][dialog_name] = [size.width(), size.height()]
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)