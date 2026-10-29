"""Scene — контейнер дерева нод (аналог Godot Scene/PackedScene)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from engine.core.node import Node

logger = logging.getLogger("cloudengine.scene")


class Scene:
    """Сцена — корневая нода с именем, путём и метаданными.

    Сцена хранит дерево нод (root) и предоставляет удобные методы обхода,
    сохранения/загрузки (через SceneSerializer) и клонирования.
    """

    def __init__(self, name: str = "Scene", root: Optional[Node] = None) -> None:
        self.name = name
        self.root: Node = root if root is not None else Node("Root")
        #: Путь к файлу .scene (если сцена была загружена/сохранена).
        self.path: str = ""

    def get_root(self) -> Node:
        """Возвращает корневую ноду."""
        return self.root

    def get_nodes(self) -> List[Node]:
        """Возвращает все ноды сцены в порядке обхода (pre-order)."""
        result: List[Node] = []

        def _walk(node: Node) -> None:
            result.append(node)
            for child in node.get_children():
                _walk(child)

        _walk(self.root)
        return result

    def find_node(self, name: str) -> Optional[Node]:
        """Находит первую ноду по имени (без учёта пути)."""
        for node in self.get_nodes():
            if node.name == name:
                return node
        return None

    def find_node_by_path(self, path: str) -> Optional[Node]:
        """Находит ноду по пути относительно корня."""
        try:
            return self.root.get_node(path)
        except ValueError:
            return None

    def process(self, delta: float) -> None:
        """Вызывает _process у нод и их компонентов."""
        for node in self.get_nodes():
            if node._pending_free:
                continue
            if node.process_enabled:
                node._process(delta)
            node._process_components(delta)

    def physics_process(self, delta: float) -> None:
        """Вызывает _physics_process у нод и их компонентов."""
        for node in self.get_nodes():
            if node._pending_free:
                continue
            if node.physics_process_enabled:
                node._physics_process(delta)
            node._physics_process_components(delta)

    def input(self, event: Any) -> None:
        """Передаёт событие ввода всем нодам сцены и их компонентам."""
        for node in self.get_nodes():
            if not node._pending_free:
                node._input(event)
                node._input_components(event)

    def duplicate(self) -> "Scene":
        """Создаёт глубокую копию сцены."""
        new_scene = Scene(self.name)
        new_scene.path = self.path
        new_scene.root = self.root.duplicate(deep=True)
        return new_scene

    def save(self, path: str) -> None:
        """Сохраняет сцену в файл .scene (JSON)."""
        from engine.resources.scene_serializer import SceneSerializer
        SceneSerializer.save_scene(self, path)
        self.path = path

    @classmethod
    def load(cls, path: str, script_system: Any = None) -> "Scene":
        """Загружает сцену из файла .scene."""
        from engine.resources.scene_serializer import SceneSerializer
        return SceneSerializer.load_scene(path, script_system)

    def __repr__(self) -> str:
        return f"<Scene '{self.name}'>"
