"""HierarchyPanel — дерево нод текущей сцены (аналог Godot Scene dock)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QMenu, QInputDialog, QLineEdit)

from engine.core.node import Node
from editor.icons import get_icon

logger = logging.getLogger("cloudengine.hierarchy")

#: Иконка для типа ноды.
_ICON_BY_TYPE = {
    "Sprite2D": "image",
    "AnimatedSprite2D": "image",
    "TextureRect": "image",
    "Camera2D": "camera",
    "TileMap": "tilemap",
    "Particles2D": "particles",
    "ParallaxBackground": "parallax",
    "ParallaxLayer": "parallax",
    "RayCast2D": "ray",
    "CollisionShape2D": "area",
    "Area2D": "area",
    "StaticBody2D": "physics",
    "RigidBody2D": "physics",
    "CharacterBody2D": "physics",
    "PhysicsBody2D": "physics",
    "AudioStreamPlayer": "audio",
    "AudioStreamPlayer2D": "audio",
    "Timer": "timer",
    "CanvasLayer": "canvas",
    "Label": "label",
    "Button": "button",
    "ProgressBar": "progress",
    "Node2D": "node",
    "Node": "node",
}


def node_icon_name(node: Node) -> str:
    """Имя иконки для ноды (учитывает скрипты и компоненты)."""
    if getattr(node, "components", None):
        for component in node.components:
            if component.get_type_name() == "VisualScript":
                return "visual"
    if getattr(node, "script_path", ""):
        return "script"
    return _ICON_BY_TYPE.get(type(node).__name__, "node")


class HierarchyPanel(QWidget):
    """Дерево нод с drag&drop, выделением и контекстным меню."""

    node_selected = pyqtSignal(object)
    add_node_requested = pyqtSignal(str, object)       # (тип, родитель)
    delete_node_requested = pyqtSignal(object)
    duplicate_node_requested = pyqtSignal(object)
    rename_node_requested = pyqtSignal(object, str)
    node_moved = pyqtSignal(object, object, int)       # (нода, новый родитель, индекс)
    component_add_requested = pyqtSignal(str, object)     # (тип компонента, нода)
    component_remove_requested = pyqtSignal(object, object)  # (компонент, нода)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.scene: Any = None
        self._selected_node: Optional[Node] = None
        self._suspend_move = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Имя или компонент…')
        self.search.textChanged.connect(self.filter_objects)
        layout.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.tree)

    # ------------------------------------------------------------------
    # Сцена
    # ------------------------------------------------------------------
    def set_scene(self, scene: Any) -> None:
        self.scene = scene
        self.refresh()

    def refresh(self) -> None:
        """Перестраивает дерево из текущей сцены."""
        self._suspend_move = True
        self.tree.blockSignals(True)
        self.tree.clear()
        if self.scene is not None:
            root_item = self._build_item(self.scene.root)
            self.tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)
        self.tree.blockSignals(False)
        self._suspend_move = False
        self.filter_objects(self.search.text())

    def filter_objects(self, text):
        needle=text.casefold().strip()
        def apply(item):
            node=item.data(0,Qt.ItemDataRole.UserRole)
            children=[apply(item.child(i)) for i in range(item.childCount())]
            own=not needle or needle in (node.name+' '+type(node).__name__+' '+' '.join(c.get_type_name() for c in node.components)).casefold()
            match=own or any(children);item.setHidden(not match)
            if needle and match:item.setExpanded(True)
            return match
        for index in range(self.tree.topLevelItemCount()):apply(self.tree.topLevelItem(index))

    def _build_item(self, node: Node) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name])
        item.setData(0, Qt.ItemDataRole.UserRole, node)
        item.setIcon(0, get_icon(node_icon_name(node)))
        tooltip = type(node).__name__
        if getattr(node, "components", None):
            tooltip += " • " + ", ".join(c.get_type_name() for c in node.components)
        if getattr(node, "script_path", ""):
            tooltip += " • " + node.script_path
        item.setToolTip(0, tooltip)
        for child in node.get_children():
            item.addChild(self._build_item(child))
        return item

    # ------------------------------------------------------------------
    # Выделение
    # ------------------------------------------------------------------
    def _on_selection(self) -> None:
        items = self.tree.selectedItems()
        if items:
            node = items[0].data(0, Qt.ItemDataRole.UserRole)
            self._selected_node = node
            self.node_selected.emit(node)
        else:
            self._selected_node = None

    def get_selected_node(self) -> Optional[Node]:
        return self._selected_node

    def select_node(self, node: Node) -> None:
        """Выделяет заданную ноду в дереве."""
        item = self._find_item(self.tree.invisibleRootItem(), node)
        if item is not None:
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)

    def _find_item(self, parent: QTreeWidgetItem, node: Node) -> Optional[QTreeWidgetItem]:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) is node:
                return child
            found = self._find_item(child, node)
            if found is not None:
                return found
        return None

    # ------------------------------------------------------------------
    # Контекстное меню
    # ------------------------------------------------------------------
    def _on_context_menu(self, pos) -> None:
        from engine.nodes import NODE_CATEGORIES
        item = self.tree.itemAt(pos)
        if item is not None:
            node = item.data(0, Qt.ItemDataRole.UserRole)
        else:
            node = self.scene.root if self.scene else None
        if node is None:
            return
        menu = QMenu(self)

        add_menu = menu.addMenu("Добавить дочернюю ноду")
        for category, types in NODE_CATEGORIES.items():
            cat_menu = add_menu.addMenu(category)
            for type_name in types:
                action = cat_menu.addAction(type_name)
                action.triggered.connect(
                    lambda checked=False, t=type_name, p=node:
                    self.add_node_requested.emit(t, p))

        add_sibling = menu.addAction("Добавить на тот же уровень")
        add_sibling.triggered.connect(
            lambda: self.add_node_requested.emit(
                "Node2D", node.parent if node.parent else (self.scene.root if self.scene else node)))

        # Компоненты навешиваются на конкретный объект.
        from engine.components.registry import visible_categories
        components_menu = menu.addMenu(f"Добавить компонент → {node.name}")
        for category, types in visible_categories().items():
            category_menu = components_menu.addMenu(category)
            for type_name in types:
                action = category_menu.addAction(type_name)
                action.triggered.connect(
                    lambda checked=False, t=type_name, n=node:
                    self.component_add_requested.emit(t, n))
        existing = list(getattr(node, "components", []) or [])
        if existing:
            remove_menu = menu.addMenu("Снять компонент")
            for component in existing:
                action = remove_menu.addAction(component.get_type_name())
                action.setEnabled(not getattr(component, "required", False))
                action.triggered.connect(
                    lambda checked=False, c=component, n=node:
                    self.component_remove_requested.emit(c, n))

        menu.addSeparator()
        duplicate = menu.addAction("Дублировать (Ctrl+D)")
        duplicate.triggered.connect(lambda: self.duplicate_node_requested.emit(node))
        rename = menu.addAction("Переименовать")
        rename.triggered.connect(lambda: self._rename(node))
        menu.addSeparator()
        delete = menu.addAction("Удалить (Delete)")
        delete.setIcon(get_icon("delete"))
        delete.triggered.connect(lambda: self.delete_node_requested.emit(node))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _rename(self, node: Node) -> None:
        text, ok = QInputDialog.getText(self, "Переименовать", "Имя ноды:",
                                        text=node.name)
        if ok and text.strip():
            self.rename_node_requested.emit(node, text.strip())

    # ------------------------------------------------------------------
    # Drag&drop
    # ------------------------------------------------------------------
    def _on_rows_moved(self, *args) -> None:
        """Обрабатывает перемещение ноды в дереве."""
        if self._suspend_move:
            return
        item = self.tree.currentItem()
        if item is None:
            return
        node = item.data(0, Qt.ItemDataRole.UserRole)
        parent_item = item.parent()
        if parent_item is not None:
            new_parent = parent_item.data(0, Qt.ItemDataRole.UserRole)
        else:
            new_parent = self.scene.root if self.scene else None
        if node is None or new_parent is None:
            return
        children = new_parent.get_children()
        index = children.index(node) if node in children else new_parent.get_child_count()
        self.node_moved.emit(node, new_parent, index)
