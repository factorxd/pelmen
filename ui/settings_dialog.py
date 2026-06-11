import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QPushButton,
    QInputDialog, QMessageBox, QFileDialog, QListWidget,
    QListWidgetItem, QLabel, QDialogButtonBox, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, template, display_names, save_callback, parent=None):
        super().__init__(parent)
        self.template = template
        self.display_names = display_names
        self.save_callback = save_callback
        self.tid = template.id

        self.setWindowTitle("Настройка шаблона")
        self.setSizeGripEnabled(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Вкладка 1: Имена, типы, форматы, суффиксы
        tab_names = QWidget()
        names_layout = QVBoxLayout(tab_names)
        names_layout.addWidget(QLabel("Двойной клик по ячейке для редактирования отображаемого имени.\n"
                                      "Тип поля, формат и суффикс настраиваются отдельно."))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Поле / блок", "Отображаемое имя", "Тип", "Формат"])
        self.tree.header().setSectionResizeMode(QHeaderView.Stretch)
        self.tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        names_layout.addWidget(self.tree)
        tabs.addTab(tab_names, "Имена, типы, форматы")

        # Вкладка 2: Категории (без изменений)
        tab_cats = QWidget()
        cats_layout = QVBoxLayout(tab_cats)
        panel = QWidget()
        panel_layout = QHBoxLayout(panel)
        self.cat_list = QListWidget()
        self.cat_list.setDragDropMode(QListWidget.InternalMove)
        self.cat_list.setMaximumWidth(200)
        panel_layout.addWidget(self.cat_list)

        cat_btns = QVBoxLayout()
        add_btn = QPushButton("➕ Добавить")
        del_btn = QPushButton("🗑️ Удалить")
        rename_btn = QPushButton("✏️ Переименовать")
        cat_btns.addWidget(add_btn)
        cat_btns.addWidget(del_btn)
        cat_btns.addWidget(rename_btn)
        cat_btns.addStretch()
        panel_layout.addLayout(cat_btns)

        self.items_list = QListWidget()
        self.items_list.setSelectionMode(QListWidget.SingleSelection)
        panel_layout.addWidget(self.items_list)
        cats_layout.addWidget(panel)

        change_cat_btn = QPushButton("Изменить категорию выбранного элемента")
        cats_layout.addWidget(change_cat_btn)
        tabs.addTab(tab_cats, "Категории")

        # Загрузка данных
        self.load_categories()
        self.load_tree()
        self.load_items()

        # Сигналы категорий
        add_btn.clicked.connect(self.add_category)
        del_btn.clicked.connect(self.delete_category)
        rename_btn.clicked.connect(self.rename_category)
        change_cat_btn.clicked.connect(self.set_category)

        # Импорт/экспорт
        ie_layout = QHBoxLayout()
        export_btn = QPushButton("📤 Экспорт")
        import_btn = QPushButton("📥 Импорт")
        ie_layout.addStretch()
        ie_layout.addWidget(export_btn)
        ie_layout.addWidget(import_btn)
        ie_layout.addStretch()
        layout.addLayout(ie_layout)
        export_btn.clicked.connect(self.do_export)
        import_btn.clicked.connect(self.do_import)

        # Кнопки OK/Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---------- Вспомогательные методы ----------
    def get_stored(self, key, subkey):
        data = self.display_names.get(self.tid, {}).get(key)
        if isinstance(data, dict):
            return data.get(subkey, "")
        return ""

    def get_stored_display(self, key):
        return self.get_stored(key, "display")

    def get_stored_type(self, key):
        t = self.get_stored(key, "type")
        return t if t in ("text", "number", "date", "bool", "image") else "text"

    def get_stored_format(self, key):
        return self.get_stored(key, "format")

    def get_stored_category(self, key):
        return self.get_stored(key, "category")

    def load_tree(self):
        self.tree.clear()
        # Простые поля
        for field in self.template.fields:
            key = f"field:{field.name}"
            display = self.get_stored_display(key) or field.name
            field_type = self.get_stored_type(key)
            field_format = self.get_stored_format(key)

            item = QTreeWidgetItem(self.tree)
            item.setText(0, field.name)
            item.setText(1, display)
            item.setData(0, Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

            # Тип
            type_combo = QComboBox()
            type_combo.addItems(["text", "number", "date", "bool", "image"])
            type_combo.setCurrentText(field_type)
            type_combo.currentTextChanged.connect(lambda t, it=item: self.on_type_changed(it, t))
            self.tree.setItemWidget(item, 2, type_combo)

            # Формат (всегда комбобокс, но для не-date/number отключён)
            self.add_format_widget(item, field_type, field_format)

        # Блоки и их поля
        for block in self.template.blocks:
            key_block = f"block:{block.name}"
            display_block = self.get_stored_display(key_block) or block.name
            block_item = QTreeWidgetItem(self.tree)
            block_item.setText(0, f"[Блок] {block.name}")
            block_item.setText(1, display_block)
            block_item.setData(0, Qt.UserRole, key_block)
            block_item.setFlags(block_item.flags() | Qt.ItemIsEditable)

            type_combo_block = QComboBox()
            type_combo_block.addItems(["text", "number", "date", "bool"])
            type_combo_block.setCurrentText(self.get_stored_type(key_block))
            self.tree.setItemWidget(block_item, 2, type_combo_block)
            self.add_format_widget(block_item, self.get_stored_type(key_block), self.get_stored_format(key_block))

            for field in block.fields:
                key_field = f"block_field:{block.name}.{field.name}"
                display_field = self.get_stored_display(key_field) or field.name
                field_type = self.get_stored_type(key_field)
                field_format = self.get_stored_format(key_field)

                child = QTreeWidgetItem(block_item)
                child.setText(0, f"    {field.name}")
                child.setText(1, display_field)
                child.setData(0, Qt.UserRole, key_field)
                child.setFlags(child.flags() | Qt.ItemIsEditable)

                type_combo = QComboBox()
                type_combo.addItems(["text", "number", "date", "bool", "image"])
                type_combo.setCurrentText(field_type)
                type_combo.currentTextChanged.connect(lambda t, it=child: self.on_type_changed(it, t))
                self.tree.setItemWidget(child, 2, type_combo)

                self.add_format_widget(child, field_type, field_format)

        self.tree.expandAll()

    def on_type_changed(self, item, new_type):
        """При изменении типа поля обновляем виджеты формата и суффикса"""
        key = item.data(0, Qt.UserRole)
        old_type = self.get_stored_type(key)
        # Обновляем формат
        self.add_format_widget(item, new_type, "")

    def add_format_widget(self, item, field_type, current_format):
        """Добавляет комбобокс формата в колонку 3 (индекс 3)"""
        combo = QComboBox()
        if field_type == "date":
            presets = [
                ("DD.MM.YYYY", "%d.%m.%Y"),
                ("DD Month YYYY (рус)", "%d %B %Y"),
                ("DD Mon YYYY (рус)", "%d %b %Y"),
                ("YYYY-MM-DD", "%Y-%m-%d"),
                ("MM/DD/YYYY", "%m/%d/%Y"),
                ("Свой формат...", "custom")
            ]
            combo.addItems([p[0] for p in presets])
            for label, fmt in presets:
                combo.setItemData(combo.findText(label), fmt)
        elif field_type == "number":
            presets = [
                ("1234", "{}"),
                ("1 234", "{:,.0f}"),
                ("1,234", "{:,}"),
                ("1 234.5", "{:,.1f}"),
                ("1 234.56", "{:,.2f}"),
                ("Свой формат...", "custom")
            ]
            combo.addItems([p[0] for p in presets])
            for label, fmt in presets:
                combo.setItemData(combo.findText(label), fmt)
        else:
            # Для других типов – скрываем или отключаем
            self.tree.setItemWidget(item, 3, None)
            return

        if current_format:
            # Ищем индекс по формату
            idx = -1
            for i in range(combo.count()):
                if combo.itemData(i) == current_format:
                    idx = i
                    break
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentText("Свой формат...")
                combo.setItemData(combo.count()-1, current_format)

        combo.currentIndexChanged.connect(lambda idx, it=item, cb=combo: self.on_format_changed(it, cb))
        self.tree.setItemWidget(item, 3, combo)

    def on_format_changed(self, item, combo):
        key = item.data(0, Qt.UserRole)
        field_type = self.get_stored_type(key) if key else "text"
        if combo.currentData() == "custom":
            if field_type == "date":
                hint = "Введите строку форматирования для даты\nПримеры: %d.%m.%Y, %d %B %Y"
            else:
                hint = "Введите строку форматирования для числа\nПримеры: {:.2f}, {:,.2f} ₽, {:.0f}"
            custom, ok = QInputDialog.getText(self, "Свой формат", hint)
            if ok and custom.strip():
                combo.setItemData(combo.currentIndex(), custom)
                combo.setItemText(combo.currentIndex(), custom[:25] + "..." if len(custom) > 25 else custom)
            else:
                combo.setCurrentIndex(0)
        else:
            # Для дат с русскими месяцами – предупреждение
            fmt = combo.currentData()
            if field_type == "date" and fmt and isinstance(fmt, str) and ('%B' in fmt or '%b' in fmt):
                import locale
                try:
                    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
                except:
                    QMessageBox.warning(self, "Предупреждение",
                                        "Выбран формат даты с названием месяца, но русская локаль не установлена.\n"
                                        "Названия месяцев могут не отображаться. Рекомендуется использовать цифровой формат.")

    # ---------- Категории (без изменений) ----------
    def load_categories(self):
        order = self.display_names.get(self.tid, {}).get("_categories_order", ["Без категории"])
        if "Без категории" not in order:
            order.insert(0, "Без категории")
        self.cat_list.clear()
        for cat in order:
            self.cat_list.addItem(cat)

    def load_items(self):
        self.items_list.clear()
        for field in self.template.fields:
            key = f"field:{field.name}"
            cat = self.get_stored_category(key)
            display = self.get_stored_display(key) or field.name
            text = f"{display} : {cat if cat else 'Без категории'}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.items_list.addItem(item)
        for block in self.template.blocks:
            key = f"block:{block.name}"
            cat = self.get_stored_category(key)
            display = self.get_stored_display(key) or block.name
            text = f"[Блок] {display} : {cat if cat else 'Без категории'}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.items_list.addItem(item)

    def refresh_items(self):
        for i in range(self.items_list.count()):
            key = self.items_list.item(i).data(Qt.UserRole)
            cat = self.get_stored_category(key)
            text = self.items_list.item(i).text()
            if " : " in text:
                display_part = text.split(" : ")[0]
            else:
                display_part = ""
            new_text = f"{display_part} : {cat if cat else 'Без категории'}"
            self.items_list.item(i).setText(new_text)

    def add_category(self):
        name, ok = QInputDialog.getText(self, "Новая категория", "Название:")
        if ok and name.strip():
            name = name.strip()
            if name not in [self.cat_list.item(i).text() for i in range(self.cat_list.count())]:
                self.cat_list.addItem(name)

    def delete_category(self):
        cur = self.cat_list.currentItem()
        if not cur:
            return
        if cur.text() == "Без категории":
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить 'Без категории'")
            return
        cat_name = cur.text()
        for i in range(self.items_list.count()):
            key = self.items_list.item(i).data(Qt.UserRole)
            data = self.display_names.get(self.tid, {}).get(key)
            if isinstance(data, dict) and data.get("category") == cat_name:
                data["category"] = ""
        row = self.cat_list.row(cur)
        self.cat_list.takeItem(row)
        self.refresh_items()

    def rename_category(self):
        cur = self.cat_list.currentItem()
        if not cur:
            return
        if cur.text() == "Без категории":
            QMessageBox.warning(self, "Ошибка", "Нельзя переименовать 'Без категории'")
            return
        old = cur.text()
        new, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=old)
        if ok and new.strip():
            new = new.strip()
            if new in [self.cat_list.item(i).text() for i in range(self.cat_list.count())]:
                QMessageBox.warning(self, "Ошибка", "Категория уже существует")
                return
            cur.setText(new)
            for i in range(self.items_list.count()):
                key = self.items_list.item(i).data(Qt.UserRole)
                data = self.display_names.get(self.tid, {}).get(key)
                if isinstance(data, dict) and data.get("category") == old:
                    data["category"] = new
            self.refresh_items()

    def set_category(self):
        cur = self.items_list.currentItem()
        if not cur:
            QMessageBox.warning(self, "Ошибка", "Выберите элемент из списка")
            return
        key = cur.data(Qt.UserRole)
        current_cat = self.get_stored_category(key)
        categories = [self.cat_list.item(i).text() for i in range(self.cat_list.count())]
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор категории")
        dlg_layout = QVBoxLayout(dlg)
        combo = QComboBox()
        combo.addItems(categories)
        idx = combo.findText(current_cat)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        dlg_layout.addWidget(combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        dlg_layout.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            new_cat = combo.currentText()
            existing = self.display_names.get(self.tid, {}).get(key, {})
            if isinstance(existing, str):
                existing = {"display": existing, "category": new_cat, "type": "text"}
            elif not isinstance(existing, dict):
                existing = {}
            existing["category"] = new_cat
            self.display_names.setdefault(self.tid, {})[key] = existing
            if key.startswith("block:") and not key.startswith("block_field:"):
                block_name = key.split(":", 1)[1]
                for field in self.template.blocks:
                    if field.name == block_name:
                        for subfield in field.fields:
                            subkey = f"block_field:{block_name}.{subfield.name}"
                            sub_existing = self.display_names.get(self.tid, {}).get(subkey, {})
                            if isinstance(sub_existing, str):
                                sub_existing = {"display": sub_existing, "category": new_cat, "type": "text"}
                            elif not isinstance(sub_existing, dict):
                                sub_existing = {}
                            sub_existing["category"] = new_cat
                            self.display_names[self.tid][subkey] = sub_existing
            self.refresh_items()

    # ---------- Импорт/экспорт ----------
    def do_export(self):
        data = {self.tid: self.display_names.get(self.tid, {})}
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт настроек", f"{self.template.name}_settings.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Успех", f"Экспортировано в {path}")

    def do_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт настроек", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            imported = json.load(f)
        if self.tid not in imported:
            QMessageBox.warning(self, "Ошибка", "Файл не содержит настроек для этого шаблона")
            return
        self.display_names[self.tid] = imported[self.tid]
        self.load_categories()
        self.load_tree()
        self.load_items()
        QMessageBox.information(self, "Импорт", "Настройки импортированы.")

    # ---------- Сохранение ----------
    def accept(self):
        def save_tree_item(item):
            key = item.data(0, Qt.UserRole)
            if not key:
                return
            display = item.text(1).strip()
            type_widget = self.tree.itemWidget(item, 2)
            field_type = type_widget.currentText() if type_widget else "text"

            # Формат – колонка 3
            format_widget = self.tree.itemWidget(item, 3)
            field_format = ""
            if format_widget and isinstance(format_widget, QComboBox):
                fmt_data = format_widget.currentData()
                if fmt_data != "custom":
                    field_format = fmt_data
                else:
                    field_format = format_widget.currentData()

            existing = self.display_names.get(self.tid, {}).get(key, {})
            if isinstance(existing, str):
                existing = {"display": existing}
            elif not isinstance(existing, dict):
                existing = {}
            if display:
                existing["display"] = display
            else:
                existing.pop("display", None)
            existing["type"] = field_type
            if field_type in ("date", "number") and field_format:
                existing["format"] = field_format
            else:
                existing.pop("format", None)

            if existing:
                self.display_names.setdefault(self.tid, {})[key] = existing
            else:
                self.display_names[self.tid].pop(key, None)
            for i in range(item.childCount()):
                save_tree_item(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            save_tree_item(self.tree.topLevelItem(i))

        # Сохраняем порядок категорий
        order = [self.cat_list.item(i).text() for i in range(self.cat_list.count())]
        self.display_names.setdefault(self.tid, {})["_categories_order"] = order

        self.save_callback(self.display_names)
        super().accept()