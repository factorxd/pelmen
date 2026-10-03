import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QPushButton,
    QInputDialog, QMessageBox, QFileDialog, QListWidget,
    QLabel, QDialogButtonBox, QComboBox
)
from PySide6.QtCore import Qt

class CategoryListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)  # для переупорядочивания
        self.setAcceptDrops(True)
        self.setDragEnabled(True)          # можно перетаскивать элементы внутри списка
        self.setDropIndicatorShown(True)
        self.parent_dialog = None
        self._highlighted_item = None

    def _set_highlight(self, item):
        """Подсвечивает целевой элемент жирным шрифтом."""
        if self._highlighted_item is item:
            return
        # Сбрасываем предыдущий
        if self._highlighted_item is not None:
            f = self._highlighted_item.font()
            f.setBold(False)
            self._highlighted_item.setFont(f)
        self._highlighted_item = item
        # Ставим новый
        if item is not None:
            f = item.font()
            f.setBold(True)
            item.setFont(f)

    def dragMoveEvent(self, event):
        item = self.itemAt(event.pos())
        self._set_highlight(item)
        event.accept()

    def dragLeaveEvent(self, event):
        self._set_highlight(None)
        super().dragLeaveEvent(event)

    def dragEnterEvent(self, event):
        # Разрешаем дроп, если источник - дерево категорий или этот же список
        if isinstance(event.source(), CategoryTreeWidget) or event.source() is self:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        self._set_highlight(None)
        source_widget = event.source()
        if source_widget is self:
            # Внутреннее перемещение — меняем порядок категорий
            super().dropEvent(event)
            self.parent_dialog.update_categories_order()
            event.accept()
        elif isinstance(source_widget, CategoryTreeWidget):
            # Перетаскивание элемента из дерева для смены категории
            dragged_items = source_widget.selectedItems()
            if not dragged_items:
                event.ignore()
                return
            drag_item = dragged_items[0]
            if drag_item.parent() is None:
                event.ignore()
                return
            target_item = self.itemAt(event.pos())
            if not target_item:
                event.ignore()
                return
            new_category = target_item.text()
            old_parent = drag_item.parent()
            if old_parent.text(0) == new_category:
                event.accept()
                return
            # Находим новый корневой элемент (категорию) в дереве
            new_root = None
            for i in range(source_widget.topLevelItemCount()):
                if source_widget.topLevelItem(i).text(0) == new_category:
                    new_root = source_widget.topLevelItem(i)
                    break
            if new_root:
                old_parent.removeChild(drag_item)
                new_root.addChild(drag_item)
                # Обновляем данные
                key = drag_item.data(0, Qt.UserRole)
                if key:
                    existing = self.parent_dialog.display_names.get(self.parent_dialog.tid, {}).get(key, {})
                    if isinstance(existing, str):
                        existing = {"display": existing}
                    existing["category"] = new_category
                    self.parent_dialog.display_names.setdefault(self.parent_dialog.tid, {})[key] = existing
                    # Обновляем дочерние поля для блоков
                    if key.startswith("block:") and not key.startswith("block_field:"):
                        block_name = key.split(":", 1)[1]
                        for field in self.parent_dialog.template.blocks:
                            if field.name == block_name:
                                for subfield in field.fields:
                                    subkey = f"block_field:{block_name}.{subfield.name}"
                                    sub_existing = self.parent_dialog.display_names.get(self.parent_dialog.tid, {}).get(subkey, {})
                                    if isinstance(sub_existing, str):
                                        sub_existing = {"display": sub_existing}
                                    sub_existing["category"] = new_category
                                    self.parent_dialog.display_names.setdefault(self.parent_dialog.tid, {})[subkey] = sub_existing
                                break
                source_widget.expandItem(new_root)
            event.accept()
        else:
            event.ignore()

class CategoryTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QTreeWidget.DragDrop)  # вместо InternalMove
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.parent_dialog = None

    def dropEvent(self, event):
        # Получаем элемент, на который сбрасываем
        target_item = self.itemAt(event.position().toPoint())
        if not target_item:
            event.ignore()
            return
        # Получаем перетаскиваемые элементы (выделенные)
        dragged_items = self.selectedItems()
        if not dragged_items:
            event.ignore()
            return
        # Перемещаем каждый элемент в целевой родитель
        for drag_item in dragged_items:
            # Нельзя перемещать корневые элементы
            if drag_item.parent() is None:
                continue
            # Целевой родитель может быть как категория (корневой), так и элемент
            # Нам нужно, чтобы целевой родитель был корневым (категория)
            if target_item.parent() is None:
                new_parent = target_item
            else:
                # Если целевой элемент находится внутри категории, поднимаемся до родительской категории
                new_parent = target_item.parent()
            if new_parent is None:
                continue
            # Перемещаем
            old_parent = drag_item.parent()
            if old_parent == new_parent:
                continue
            old_parent.removeChild(drag_item)
            new_parent.addChild(drag_item)
            # Обновляем данные в display_names
            key = drag_item.data(0, Qt.UserRole)
            if key:
                existing = self.parent_dialog.display_names.get(self.parent_dialog.tid, {}).get(key, {})
                if isinstance(existing, str):
                    existing = {"display": existing}
                existing["category"] = new_parent.text(0)
                self.parent_dialog.display_names.setdefault(self.parent_dialog.tid, {})[key] = existing
                # Обновляем дочерние поля для блоков
                if key.startswith("block:") and not key.startswith("block_field:"):
                    block_name = key.split(":", 1)[1]
                    for field in self.parent_dialog.template.blocks:
                        if field.name == block_name:
                            for subfield in field.fields:
                                subkey = f"block_field:{block_name}.{subfield.name}"
                                sub_existing = self.parent_dialog.display_names.get(self.parent_dialog.tid, {}).get(subkey, {})
                                if isinstance(sub_existing, str):
                                    sub_existing = {"display": sub_existing}
                                sub_existing["category"] = new_parent.text(0)
                                self.parent_dialog.display_names.setdefault(self.parent_dialog.tid, {})[subkey] = sub_existing
                            break
        # Раскрываем новые родительские категории
        for i in range(self.topLevelItemCount()):
            self.expandItem(self.topLevelItem(i))
        event.accept()

    def dragEnterEvent(self, event):
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()

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

        # Вкладка 1: Имена, типы, форматы
        tab_names = QWidget()
        names_layout = QVBoxLayout(tab_names)
        names_layout.addWidget(QLabel("Двойной клик по ячейке для редактирования отображаемого имени.\n"
                                      "Тип поля и формат выбираются из списков."))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Поле / блок", "Отображаемое имя", "Тип", "Формат"])
        self.tree.header().setSectionResizeMode(QHeaderView.Stretch)
        self.tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        names_layout.addWidget(self.tree)
        tabs.addTab(tab_names, "Свойства полей")

        # Вкладка 2: Категории (с drag&drop и группировкой)
        tab_cats = QWidget()
        cats_layout = QVBoxLayout(tab_cats)

        cats_layout.addWidget(QLabel(
            "Перетаскивайте поля и блоки между категориями, меняйте порядок категорий в левом списке.\n"
            "Элементы можно также перетаскивать на названия категорий в левом списке."
        ))
        cats_layout.addSpacing(5)

        panel = QWidget()
        panel_layout = QHBoxLayout(panel)

        # Левая часть: список категорий (можно перетаскивать для изменения порядка)
        self.cat_list = CategoryListWidget()
        self.cat_list.parent_dialog = self
        self.cat_list.setMaximumWidth(200)
        panel_layout.addWidget(self.cat_list)

        # Кнопки управления категориями
        cat_btns = QVBoxLayout()
        add_btn = QPushButton("➕ Добавить")
        del_btn = QPushButton("🗑️ Удалить")
        rename_btn = QPushButton("✏️ Переименовать")
        cat_btns.addWidget(add_btn)
        cat_btns.addWidget(del_btn)
        cat_btns.addWidget(rename_btn)
        cat_btns.addSpacing(12)

        # Пунктирная стрелка-подсказка: поля тащим из дерева справа в категории слева
        arrow_label = QLabel("⇠")
        arrow_label.setAlignment(Qt.AlignCenter)
        arrow_label.setToolTip(
            "Перетащите поле или блок из дерева справа\nна категорию в списке слева"
        )
        arrow_font = arrow_label.font()
        arrow_font.setPointSize(28)
        arrow_label.setFont(arrow_font)
        arrow_label.setStyleSheet("color: #888;")
        cat_btns.addWidget(arrow_label)

        cat_btns.addStretch()
        panel_layout.addLayout(cat_btns)

        # Правая часть: дерево элементов, сгруппированных по категориям
        self.categories_tree = CategoryTreeWidget()
        self.categories_tree.parent_dialog = self
        self.categories_tree.setHeaderLabels(["Поля и блоки"])
        self.categories_tree.setIndentation(20)
        self.categories_tree.setDragDropMode(QTreeWidget.DragDrop)  # важно
        self.categories_tree.setAcceptDrops(True)
        self.categories_tree.setDragEnabled(True)
        self.categories_tree.setDropIndicatorShown(True)
        self.categories_tree.header().hide()
        panel_layout.addWidget(self.categories_tree)

        cats_layout.addWidget(panel)
        tabs.addTab(tab_cats, "Категории")

        # Загрузка данных
        self.load_categories()
        self.load_tree()
        self.load_items()  # загружает дерево категорий

        # Сигналы категорий
        add_btn.clicked.connect(self.add_category)
        del_btn.clicked.connect(self.delete_category)
        rename_btn.clicked.connect(self.rename_category)

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

        # Настройка drag & drop
        self.cat_list.setDragEnabled(True)
        self.cat_list.setAcceptDrops(True)
        self.cat_list.setDropIndicatorShown(True)
        self.categories_tree.setDragEnabled(True)
        self.categories_tree.setAcceptDrops(True)

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

    # ---------- Дерево имён, типов, форматов ----------
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

            type_combo = QComboBox()
            type_combo.addItems(["text", "number", "date", "bool", "image"])
            type_combo.setCurrentText(field_type)
            type_combo.currentTextChanged.connect(lambda t, it=item: self.on_type_changed(it, t))
            self.tree.setItemWidget(item, 2, type_combo)
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
        self.add_format_widget(item, new_type, "")

    def add_format_widget(self, item, field_type, current_format):
        combo = QComboBox()
        if field_type == "date":
            presets = [
                ("DD.MM.YYYY", "%d.%m.%Y"),
                ("DD Month YYYY (рус)", "%d %B %Y"),
                ("DD Mon YYYY (рус)", "%d %b %Y"),
                ("YYYY-MM-DD", "%Y-%m-%d"),
                ("MM/DD/YYYY", "%m/%d/%Y"),
            ]
        elif field_type == "number":
            presets = [
                ("1234", "{}"),
                ("1 234", "{:,.0f}"),
                ("1,234", "{:,}"),
                ("1 234.5", "{:,.1f}"),
                ("1 234.56", "{:,.2f}"),
            ]
        else:
            self.tree.setItemWidget(item, 3, None)
            return

        for label, fmt in presets:
            combo.addItem(label, fmt)

        # Триггер "Свой формат..." — всегда последний, никогда не перезаписывается
        combo.addItem("Свой формат...", "custom")

        # Если текущий формат не среди пресетов — добавляем его отдельным
        # пунктом ПЕРЕД триггером
        if current_format:
            found_idx = -1
            for i in range(combo.count()):
                if combo.itemData(i) == current_format:
                    found_idx = i
                    break
            if found_idx >= 0:
                combo.setCurrentIndex(found_idx)
            else:
                insert_at = combo.count() - 1
                label = current_format if len(current_format) <= 25 else current_format[:22] + "..."
                combo.insertItem(insert_at, label, current_format)
                combo.setCurrentIndex(insert_at)

        combo.currentIndexChanged.connect(
            lambda idx, it=item, cb=combo: self.on_format_changed(it, cb)
        )
        self.tree.setItemWidget(item, 3, combo)

    def on_format_changed(self, item, combo):
        type_widget = self.tree.itemWidget(item, 2)
        field_type = type_widget.currentText() if type_widget else "text"

        if combo.currentData() != "custom":
            return

        if field_type == "date":
            hint = "Введите строку форматирования для даты\nПримеры: %d.%m.%Y, %d %B %Y"
        else:
            hint = "Введите строку форматирования для числа\nПримеры: {:.2f}, {:,.2f} ₽, {:.0f}"

        custom, ok = QInputDialog.getText(self, "Свой формат", hint)
        if not (ok and custom.strip()):
            # Юзер отменил — возвращаемся к первому пресету
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            return

        custom = custom.strip()

        # Ищем, нет ли уже такого формата в списке (кроме триггера)
        existing_idx = -1
        for i in range(combo.count() - 1):  # последний — триггер "Свой формат..."
            if combo.itemData(i) == custom:
                existing_idx = i
                break

        combo.blockSignals(True)
        if existing_idx >= 0:
            combo.setCurrentIndex(existing_idx)
        else:
            insert_at = combo.count() - 1
            label = custom if len(custom) <= 25 else custom[:22] + "..."
            combo.insertItem(insert_at, label, custom)
            combo.setCurrentIndex(insert_at)
        combo.blockSignals(False)

    # ---------- Категории ----------
    def load_categories(self):
        order = self.display_names.get(self.tid, {}).get("_categories_order", ["Без категории"])
        if "Без категории" not in order:
            order.insert(0, "Без категории")
        self.cat_list.clear()
        for cat in order:
            self.cat_list.addItem(cat)

    def load_items(self):
        """Заполняет дерево категорий: корневые элементы – категории, дочерние – поля и блоки."""
        self.categories_tree.clear()

        order = self.display_names.get(self.tid, {}).get("_categories_order", ["Без категории"])
        if "Без категории" not in order:
            order.insert(0, "Без категории")

        category_items = {}
        for cat in order:
            root_item = QTreeWidgetItem(self.categories_tree)
            root_item.setText(0, cat)
            root_item.setFlags(root_item.flags() | Qt.ItemIsEditable | Qt.ItemIsDropEnabled)
            category_items[cat] = root_item

        # Поля
        for field in self.template.fields:
            key = f"field:{field.name}"
            cat = self.get_stored_category(key) or "Без категории"
            display = self.get_stored_display(key) or field.name
            item = QTreeWidgetItem(category_items.get(cat, category_items["Без категории"]))
            item.setText(0, display)
            item.setData(0, Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsSelectable)

        # Блоки
        for block in self.template.blocks:
            key = f"block:{block.name}"
            cat = self.get_stored_category(key) or "Без категории"
            display = self.get_stored_display(key) or block.name
            item = QTreeWidgetItem(category_items.get(cat, category_items["Без категории"]))
            item.setText(0, f"[Блок] {display}")
            item.setData(0, Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsSelectable)

        self.categories_tree.expandAll()

    def refresh_items(self):
        self.load_items()

    def add_category(self):
        name, ok = QInputDialog.getText(self, "Новая категория", "Название:")
        if ok and name.strip():
            name = name.strip()
            if name not in [self.cat_list.item(i).text() for i in range(self.cat_list.count())]:
                self.cat_list.addItem(name)
                # Добавляем корневой элемент в дерево
                root_item = QTreeWidgetItem(self.categories_tree)
                root_item.setText(0, name)
                root_item.setFlags(root_item.flags() | Qt.ItemIsEditable | Qt.ItemIsDropEnabled)
                self.categories_tree.addTopLevelItem(root_item)
                # Обновляем порядок категорий
                self.update_categories_order()
                self.refresh_items()  # перестроим, чтобы все элементы оказались под новыми категориями? проще перезагрузить
                self.load_items()  # полная перезагрузка

    def delete_category(self):
        cur = self.cat_list.currentItem()
        if not cur:
            return
        cat_name = cur.text()
        if cat_name == "Без категории":
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить 'Без категории'")
            return
        # Удаляем категорию из данных: все элементы этой категории переносим в "Без категории"
        for i in range(self.categories_tree.topLevelItemCount()):
            top_item = self.categories_tree.topLevelItem(i)
            if top_item.text(0) == cat_name:
                # Переносим всех детей в корневую категорию "Без категории"
                # Находим корневую категорию "Без категории"
                for j in range(self.categories_tree.topLevelItemCount()):
                    if self.categories_tree.topLevelItem(j).text(0) == "Без категории":
                        default_root = self.categories_tree.topLevelItem(j)
                        while top_item.childCount():
                            child = top_item.child(0)
                            top_item.removeChild(child)
                            default_root.addChild(child)
                        break
                self.categories_tree.takeTopLevelItem(i)
                break
        # Удаляем из cat_list
        row = self.cat_list.row(cur)
        self.cat_list.takeItem(row)
        # Обновляем порядок
        self.update_categories_order()
        # Перезагружаем дерево (чтобы обновить категории у элементов)
        self.load_items()

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
            # Переименовываем в cat_list
            cur.setText(new)
            # Переименовываем корневой элемент в дереве
            for i in range(self.categories_tree.topLevelItemCount()):
                if self.categories_tree.topLevelItem(i).text(0) == old:
                    self.categories_tree.topLevelItem(i).setText(0, new)
                    break
            # Обновляем в данных все элементы, у которых была эта категория
            for key in self.display_names.get(self.tid, {}).copy():
                if self.get_stored_category(key) == old:
                    existing = self.display_names[self.tid].get(key, {})
                    if isinstance(existing, dict):
                        existing["category"] = new
            # Обновляем порядок
            self.update_categories_order()
            self.load_items()

    def update_categories_order(self):
        """Сохраняет порядок категорий из cat_list в настройки."""
        order = [self.cat_list.item(i).text() for i in range(self.cat_list.count())]
        self.display_names.setdefault(self.tid, {})["_categories_order"] = order

    # ---------- Импорт/экспорт ----------
    def do_export(self):
        export_data = {
            "template_name": os.path.splitext(os.path.basename(self.template.file_path))[0],
            "settings": self.display_names.get(self.tid, {})
        }
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт настроек", f"{self.template.name}_settings.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Успех", f"Экспортировано в {path}")

    def do_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт настроек", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            imported = json.load(f)

        if "template_name" in imported and "settings" in imported:
            settings = imported["settings"]
        elif self.tid in imported:
            settings = imported[self.tid]
        else:
            QMessageBox.warning(self, "Ошибка", "Файл не содержит настроек для шаблона.")
            return

        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Импортировать настройки в текущий шаблон '{self.template.name}'?\nТекущие настройки будут заменены.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self.display_names[self.tid] = settings
        self.save_callback(self.display_names)
        self.load_tree()
        self.load_categories()
        self.load_items()
        QMessageBox.information(self, "Импорт", "Настройки успешно импортированы.")

    # ---------- Сохранение ----------
    def accept(self):
        # Сохраняем имена, типы, форматы из дерева self.tree
        def save_tree_item(item):
            key = item.data(0, Qt.UserRole)
            if not key:
                return
            display = item.text(1).strip()
            type_widget = self.tree.itemWidget(item, 2)
            field_type = type_widget.currentText() if type_widget else "text"
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

        # Сохраняем категории на основе дерева categories_tree
        root_count = self.categories_tree.topLevelItemCount()
        for i in range(root_count):
            category_item = self.categories_tree.topLevelItem(i)
            category_name = category_item.text(0)
            for j in range(category_item.childCount()):
                child = category_item.child(j)
                key = child.data(0, Qt.UserRole)
                if key:
                    existing = self.display_names.get(self.tid, {}).get(key, {})
                    if isinstance(existing, str):
                        existing = {"display": existing}
                    existing["category"] = category_name
                    self.display_names.setdefault(self.tid, {})[key] = existing

        self.save_callback(self.display_names)
        super().accept()

    def update_categories_from_tree(self):
        """Обновляет категории в display_names на основе текущего состояния дерева."""
        root_count = self.categories_tree.topLevelItemCount()
        for i in range(root_count):
            category_item = self.categories_tree.topLevelItem(i)
            category_name = category_item.text(0)
            for j in range(category_item.childCount()):
                child = category_item.child(j)
                key = child.data(0, Qt.UserRole)
                if key:
                    existing = self.display_names.get(self.tid, {}).get(key, {})
                    if isinstance(existing, str):
                        existing = {"display": existing}
                    existing["category"] = category_name
                    self.display_names.setdefault(self.tid, {})[key] = existing