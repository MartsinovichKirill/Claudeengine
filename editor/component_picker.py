"""Диалог выбора компонента для навешивания на объект.

Открывается из инспектора кнопкой «Добавить компонент». Есть поиск по
названию и описанию, фильтр по категориям и подсказка, что делает компонент.
Компоненты визуального кода здесь не показываются — они живут в редакторе
визуальных скриптов.
"""

from __future__ import annotations

from typing import Any, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem,
                             QVBoxLayout, QComboBox, QPushButton)

from engine.components.registry import (all_visible_components,
                                        component_description,
                                        visible_categories)
from editor.icons import get_icon


class ComponentPickerDialog(QDialog):
    """Поиск и выбор компонента."""

    def __init__(self, parent: Any = None, node_name: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить компонент")
        self.setMinimumSize(560, 520)
        self.chosen: Optional[str] = None
        self._build(node_name)
        self._populate()

    # ------------------------------------------------------------------
    def _build(self, node_name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel(f"Навесить компонент на объект «{node_name}»"
                       if node_name else "Навесить компонент")
        title.setStyleSheet("font-weight:600;font-size:14px;")
        layout.addWidget(title)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск: рендер, физика, коллайдер, анимация…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._populate)
        filters.addWidget(self.search, 1)

        self.category = QComboBox()
        self.category.addItem("Все категории", "")
        for name in visible_categories():
            self.category.addItem(name, name)
        self.category.currentIndexChanged.connect(self._populate)
        filters.addWidget(self.category)
        layout.addLayout(filters)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(False)
        self.list.itemDoubleClicked.connect(lambda _item: self._accept())
        self.list.currentItemChanged.connect(self._on_current)
        layout.addWidget(self.list, 1)

        self.hint = QLabel("Выберите компонент — он появится в инспекторе.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#8c8c99;")
        layout.addWidget(self.hint)

        buttons = QDialogButtonBox()
        self.add_button = buttons.addButton("Добавить",
                                            QDialogButtonBox.ButtonRole.AcceptRole)
        self.add_button.setIcon(get_icon("add"))
        buttons.addButton("Отмена", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.search.setFocus()

    # ------------------------------------------------------------------
    def _populate(self) -> None:
        """Заполняет список с учётом поиска и категории."""
        text = self.search.text().strip().lower()
        category = self.category.currentData() or ""
        categories = visible_categories()

        self.list.clear()
        for name, names in categories.items():
            if category and name != category:
                continue
            for type_name in names:
                description = component_description(type_name)
                if text and text not in type_name.lower() \
                        and text not in description.lower() \
                        and text not in name.lower():
                    continue
                item = QListWidgetItem(f"{type_name}   —   {name}")
                item.setData(Qt.ItemDataRole.UserRole, type_name)
                item.setToolTip(description or type_name)
                item.setIcon(get_icon("rotate" if type_name == "Rotate" else "move" if type_name == "Float" else "component"))
                self.list.addItem(item)

        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        else:
            self.hint.setText("Ничего не найдено — измените запрос.")

    def _on_current(self, current: QListWidgetItem, _previous: Any) -> None:
        if current is None:
            return
        type_name = current.data(Qt.ItemDataRole.UserRole)
        description = component_description(type_name)
        self.hint.setText(description or type_name)

    # ------------------------------------------------------------------
    def _accept(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        self.chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    @staticmethod
    def pick(parent: Any = None, node_name: str = "") -> Optional[str]:
        """Показывает диалог и возвращает выбранный тип компонента."""
        dialog = ComponentPickerDialog(parent, node_name)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.chosen
        return None


__all__ = ["ComponentPickerDialog"]
