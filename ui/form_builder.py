# ui/form_builder.py
import os
import json
from collections import defaultdict
import hashlib
from logic.format_utils import format_date, format_number, strftime_to_qt_format

from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QLabel, QLineEdit, QDateEdit, QCheckBox, QDoubleSpinBox,
    QPushButton, QFrame, QGroupBox, QFileDialog
)

class NumberLineEdit(QLineEdit):
    """QLineEdit для чисел с форматированием после ввода.

    Пока фокус в поле — показывает сырое число (удобно редактировать).
    При потере фокуса — форматирует по настройкам поля.
    """

    def __init__(self, get_format_func, parent=None):
        super().__init__(parent)
        self._get_format = get_format_func
        self._raw = ""
        self.editingFinished.connect(self.apply_format)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self._raw and self.text() != self._raw:
            super().setText(self._raw)

    def focusOutEvent(self, event):
        self.apply_format()
        super().focusOutEvent(event)

    def apply_format(self):
        import re
        text = self.text().strip()
        if not text:
            self._raw = ""
            return
        cleaned = re.sub(r'[^\d,.\-]', '', text).replace(',', '.')
        if not cleaned or cleaned == '-':
            self._raw = text
            return
        try:
            num = float(cleaned)
        except ValueError:
            self._raw = text
            return
        self._raw = str(num)
        fmt = self._get_format()
        if fmt:
            formatted = format_number(num, fmt)
        else:
            formatted = str(int(num)) if num == int(num) else f"{num:.2f}"
        super().setText(formatted)

    def raw_value(self):
        return self._raw

    def setRawValue(self, value):
        if value is None or value == "":
            self._raw = ""
            super().setText("")
            return
        try:
            num = float(value)
        except (ValueError, TypeError):
            self._raw = str(value)
            super().setText(str(value))
            return
        self._raw = str(num)
        fmt = self._get_format()
        if fmt:
            super().setText(format_number(num, fmt))
        else:
            super().setText(str(int(num)) if num == int(num) else f"{num:.2f}")

class FormBuilder:
    def __init__(self, parent_window, template, display_names, data_dir):
        """
        parent_window: MainWindow (для доступа к statusBar, schedule_draft_save, get_display_info и т.д.)
        template: объект Template
        display_names: словарь настроек отображения
        data_dir: папка для черновиков
        """
        self.parent = parent_window
        self.template = template
        self.display_names = display_names
        self.data_dir = data_dir
        self.drafts_dir = os.path.join(data_dir, "drafts")
        os.makedirs(self.drafts_dir, exist_ok=True)

        self.simple_widgets = {}
        self.block_widgets = {}
        self.block_layouts = {}
        self.category_tabs = None
        self.right_layout = None  # будет установлен при вызове build_form

    def build_form(self, right_layout):
        """Построить форму и разместить в right_layout"""
        self.right_layout = right_layout
        self.clear_form()

        if not self.template.fields and not self.template.blocks:
            label = QLabel("В этом шаблоне нет переменных.\nВы можете использовать его как есть, нажав «Скачать DOCX».")
            label.setAlignment(Qt.AlignCenter)
            self.right_layout.addWidget(label)
            generate_btn = QPushButton("📄 Скачать DOCX")
            generate_btn.clicked.connect(self.parent.generate_document)
            self.right_layout.addWidget(generate_btn)
            return

        # Кнопка настроек шаблона
        top_btn_layout = QHBoxLayout()
        settings_btn = QPushButton("⚙️ Настройки шаблона")
        settings_btn.clicked.connect(self.parent.open_display_settings)
        top_btn_layout.addWidget(settings_btn)
        top_btn_layout.addStretch()
        self.right_layout.addLayout(top_btn_layout)

        # Сбор элементов с категориями
        items = []
        for field in self.template.fields:
            _, category = self.parent.get_display_info(self.template.id, field.name, "field")
            items.append((category, "field", field.name, field))
        for block in self.template.blocks:
            _, category = self.parent.get_display_info(self.template.id, block.name, "block")
            items.append((category, "block", block.name, block))

        groups = defaultdict(list)
        for cat, typ, name, obj in items:
            cat_key = cat.strip() if cat.strip() else "Без категории"
            groups[cat_key].append((typ, name, obj))

        saved_order = self.display_names.get(self.template.id, {}).get("_categories_order", [])
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
                    display, _ = self.parent.get_display_info(self.template.id, name, "field")
                    self.add_simple_field(form_layout, obj, display)
                else:
                    block_display, _ = self.parent.get_display_info(self.template.id, name, "block")
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

        generate_btn.clicked.connect(self.parent.generate_document)
        reset_btn.clicked.connect(self.reset_form)

    def clear_form(self):
        """Очищает правую панель от всех виджетов"""
        if self.right_layout:
            self.clear_layout(self.right_layout)
        self.simple_widgets.clear()
        self.block_widgets.clear()
        self.block_layouts.clear()
        if self.category_tabs:
            self.category_tabs.deleteLater()
            self.category_tabs = None

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def add_simple_field(self, layout, field, display_name):
        label = QLabel(display_name)
        if field.required:
            label.setText(label.text() + " *")
        key = f"field:{field.name}"
        info = self.display_names.get(self.template.id, {}).get(key, {})
        if isinstance(info, str):
            field_type = "text"
            fmt = ""
        else:
            field_type = info.get("type", "text")
            fmt = info.get("format", "")

        if field_type == "date":
            edit = QDateEdit()
            edit.setDate(QDate.currentDate())
            edit.setCalendarPopup(True)
            self._configure_date_edit(edit, fmt)
            edit.dateChanged.connect(self.parent.schedule_draft_save)
        elif field_type == "bool":
            edit = QCheckBox()
            edit.stateChanged.connect(self.parent.schedule_draft_save)
        elif field_type == "number":
            def _get_fmt(name=field.name):
                info = self.display_names.get(self.template.id, {}).get(f"field:{name}", {})
                if isinstance(info, str):
                    return ""
                return info.get("format", "")
            edit = NumberLineEdit(_get_fmt)
            edit.textChanged.connect(self.parent.schedule_draft_save)
        elif field_type == "image":
            widget_container = QWidget()
            widget_layout = QHBoxLayout(widget_container)
            widget_layout.setContentsMargins(0, 0, 0, 0)
            file_path_edit = QLineEdit()
            file_path_edit.setPlaceholderText("Путь к изображению...")
            browse_btn = QPushButton("Обзор...")
            widget_layout.addWidget(file_path_edit)
            widget_layout.addWidget(browse_btn)
            edit = widget_container
            edit.file_path_edit = file_path_edit
            browse_btn.clicked.connect(lambda: self.browse_image(file_path_edit))
            file_path_edit.textChanged.connect(self.parent.schedule_draft_save)
        else:
            edit = QLineEdit()
            edit.textChanged.connect(self.parent.schedule_draft_save)

        layout.addWidget(label)
        layout.addWidget(edit)
        self.simple_widgets[field.name] = edit

        edit.setContextMenuPolicy(Qt.CustomContextMenu)
        edit.customContextMenuRequested.connect(lambda pos, w=edit: self.parent.show_preset_menu_for_widget(w, pos))

    def browse_image(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(self.parent, "Выберите изображение", "",
                                              "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            line_edit.setText(path)

    def add_dynamic_block(self, layout, block, block_display_name):
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
            display, _ = self.parent.get_display_info(self.template.id, f"{block.name}.{field.name}", "block_field")
            if not display or display == field.name:
                display, _ = self.parent.get_display_info(self.template.id, f"{block.name}.{field.name}", "block_field")
            field_label = QLabel(display)

            key = f"block_field:{block.name}.{field.name}"
            data = self.display_names.get(self.template.id, {}).get(key, {})
            if isinstance(data, str):
                field_type = "text"
                fmt = ""
            else:
                field_type = data.get("type", "text")
                fmt = data.get("format", "")

            if field_type == "date":
                edit = QDateEdit()
                edit.setDate(QDate.currentDate())
                edit.setCalendarPopup(True)
                self._configure_date_edit(edit, fmt)
                edit.dateChanged.connect(self.parent.schedule_draft_save)
            elif field_type == "bool":
                edit = QCheckBox()
                edit.stateChanged.connect(self.parent.schedule_draft_save)
            elif field_type == "number":
                def _get_fmt(bn=block.name, fn=field.name):
                    info = self.display_names.get(self.template.id, {}).get(
                        f"block_field:{bn}.{fn}", {})
                    if isinstance(info, str):
                        return ""
                    return info.get("format", "")
                edit = NumberLineEdit(_get_fmt)
                edit.textChanged.connect(self.parent.schedule_draft_save)
            elif field_type == "image":
                widget_container = QWidget()
                widget_layout = QHBoxLayout(widget_container)
                widget_layout.setContentsMargins(0, 0, 0, 0)
                file_path_edit = QLineEdit()
                file_path_edit.setPlaceholderText("Путь к изображению...")
                browse_btn = QPushButton("Обзор...")
                widget_layout.addWidget(file_path_edit)
                widget_layout.addWidget(browse_btn)
                edit = widget_container
                edit.file_path_edit = file_path_edit
                browse_btn.clicked.connect(lambda: self.browse_image(file_path_edit))
                file_path_edit.textChanged.connect(self.parent.schedule_draft_save)
            else:
                edit = QLineEdit()
                edit.textChanged.connect(self.parent.schedule_draft_save)

            edit.setContextMenuPolicy(Qt.CustomContextMenu)
            edit.customContextMenuRequested.connect(lambda p, w=edit: self.parent.show_preset_menu_for_widget(w, p))

            card_layout.addWidget(field_label)
            card_layout.addWidget(edit)
            fields_widgets[field.name] = edit

        card_data = {"frame": card_frame, "fields": fields_widgets}
        self.block_widgets.setdefault(block_key, []).append(card_data)

        add_btn_index = parent_layout.count() - 1
        parent_layout.insertWidget(add_btn_index, card_frame)

        remove_btn.clicked.connect(lambda checked, key=block_key, card=card_data: self.remove_block_card(key, card))
        self.parent.schedule_draft_save()

    def remove_block_card(self, block_key, card_data):
        if card_data in self.block_widgets[block_key]:
            self.block_widgets[block_key].remove(card_data)
            card_data["frame"].deleteLater()
            self.renumber_block_cards(block_key)
            self.parent.schedule_draft_save()

    def renumber_block_cards(self, block_key):
        for idx, card in enumerate(self.block_widgets[block_key]):
            for child in card["frame"].findChildren(QLabel):
                if child.text().startswith("Элемент"):
                    child.setText(f"Элемент {idx+1}")
                    break

    def collect_data(self):
        data = {}
        for name, widget in self.simple_widgets.items():
            key = f"field:{name}"
            info = self.display_names.get(self.template.id, {}).get(key, {})
            field_type = info.get("type", "text")
            fmt = info.get("format", "")
            data[name] = self._extract_widget_value(widget, field_type, fmt)

        for block_name, cards in self.block_widgets.items():
            block_data = []
            for card in cards:
                item = {}
                for fname, fw in card["fields"].items():
                    key = f"block_field:{block_name}.{fname}"
                    info = self.display_names.get(self.template.id, {}).get(key, {})
                    field_type = info.get("type", "text")
                    fmt = info.get("format", "")
                    item[fname] = self._extract_widget_value(fw, field_type, fmt)
                block_data.append(item)
            data[block_name] = block_data
        return data

    def _extract_widget_value(self, widget, field_type, fmt):
        if isinstance(widget, NumberLineEdit):
            widget.apply_format()
            return widget.text()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QDateEdit):
            return format_date(widget.date(), fmt)
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QDoubleSpinBox):
            return format_number(widget.value(), fmt)
        if field_type == "image" and hasattr(widget, 'file_path_edit'):
            return widget.file_path_edit.text()
        return ""

    def save_draft(self):
        try:
            data = self._collect_raw_data()
        except RuntimeError:
            return
        draft_path = self.get_draft_path()
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _collect_raw_data(self):
        """Сырые данные для черновика: даты в ISO, числа как float."""
        data = {}
        for name, widget in self.simple_widgets.items():
            data[name] = self._extract_raw_widget_value(widget)

        for block_name, cards in self.block_widgets.items():
            block_data = []
            for card in cards:
                item = {}
                for fname, fw in card["fields"].items():
                    item[fname] = self._extract_raw_widget_value(fw)
                block_data.append(item)
            data[block_name] = block_data
        return data

    def _extract_raw_widget_value(self, widget):
        if isinstance(widget, NumberLineEdit):
            return widget.raw_value()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QDateEdit):
            return widget.date().toString(Qt.ISODate)
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if hasattr(widget, 'file_path_edit'):
            return widget.file_path_edit.text()
        return ""

    def load_draft(self):
        draft_path = self.get_draft_path()
        if not os.path.exists(draft_path):
            return
        with open(draft_path, "r", encoding="utf-8") as f:
            draft_data = json.load(f)

        for name, widget in self.simple_widgets.items():
            if name in draft_data:
                self._restore_widget_value(widget, draft_data[name])

        for block in self.template.blocks:
            block_name = block.name
            if block_name not in draft_data:
                continue
            block_items = draft_data[block_name]
            if not block_items:
                continue
            group_layout = self.block_layouts.get(block_name)
            if not group_layout:
                continue
            while self.block_widgets.get(block_name):
                self.remove_block_card(block_name, self.block_widgets[block_name][-1])
            for item_data in block_items:
                self.add_block_card(block, group_layout, block_name)
                new_card = self.block_widgets[block_name][-1]
                for field_name, value in item_data.items():
                    if field_name in new_card["fields"]:
                        self._restore_widget_value(new_card["fields"][field_name], value)

    def _restore_widget_value(self, widget, value):
        if isinstance(widget, NumberLineEdit):
            widget.setRawValue(value)
        if isinstance(widget, QLineEdit):
            widget.setText("" if value is None else str(value))
        elif isinstance(widget, QDateEdit):
            if not value:
                return
            # Поддерживаем и новый ISO-формат, и старые черновики
            for qfmt in (Qt.ISODate, "dd.MM.yyyy", "yyyy-MM-dd"):
                qdate = QDate.fromString(str(value), qfmt)
                if qdate.isValid():
                    widget.setDate(qdate)
                    return
        elif isinstance(widget, QCheckBox):
            if isinstance(value, bool):
                widget.setChecked(value)
            elif isinstance(value, str):
                widget.setChecked(value.lower() == 'true')
            else:
                widget.setChecked(bool(value))
        elif isinstance(widget, QDoubleSpinBox):
            if isinstance(value, (int, float)):
                widget.setValue(float(value))
            elif isinstance(value, str):
                try:
                    widget.setValue(self.extract_number(value))
                except (ValueError, TypeError):
                    pass
        elif hasattr(widget, 'file_path_edit'):
            widget.file_path_edit.setText("" if value is None else str(value))

    def clear_draft(self):
        draft_path = self.get_draft_path()
        if os.path.exists(draft_path):
            os.remove(draft_path)

    def get_draft_path(self):
        # Генерируем уникальное имя файла на основе полного пути к шаблону
        safe_id = hashlib.md5(self.template.file_path.encode('utf-8')).hexdigest()
        return os.path.join(self.drafts_dir, f"{safe_id}.json")

    def reset_form(self):
        for widget in self.simple_widgets.values():
            if isinstance(widget, NumberLineEdit):
                widget.setRawValue("")
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
                    if isinstance(fw, NumberLineEdit):
                        fw.setRawValue("")
                    if isinstance(fw, QLineEdit):
                        fw.clear()
                    elif isinstance(fw, QDateEdit):
                        fw.setDate(QDate.currentDate())
                    elif isinstance(fw, QCheckBox):
                        fw.setChecked(False)
                    elif isinstance(fw, QDoubleSpinBox):
                        fw.setValue(0.0)
        self.clear_draft()
        self.parent.schedule_draft_save()

    @staticmethod
    def extract_number(s):
        """Извлекает число из строки, например '1 234,56 руб.' -> 1234.56"""
        if isinstance(s, (int, float)):
            return float(s)
        import re
        # Ищем цифры, пробелы, запятые, точки, минус
        # Удаляем пробелы, заменяем запятую на точку
        cleaned = re.sub(r'[^\d,.-]', '', str(s))
        if not cleaned:
            return 0.0
        # Заменяем запятую на точку (разделитель дробной части)
        cleaned = cleaned.replace(',', '.')
        # Если несколько точек, оставляем последнюю? Но обычно одна.
        try:
            return float(cleaned)
        except:
            return 0.0

    def _configure_date_edit(self, edit, fmt):
        """Настраивает QDateEdit под формат поля.

        - Qt displayFormat получаем из strftime через конвертер;
        - для форматов с названиями месяцев ставим русскую локаль,
          чтобы отображалось «октября», а не «October».
        """
        from PySide6.QtCore import QLocale
        qt_fmt = strftime_to_qt_format(fmt)
        edit.setDisplayFormat(qt_fmt)
        if fmt and ('%B' in fmt or '%b' in fmt):
            edit.setLocale(QLocale(QLocale.Russian, QLocale.Russia))