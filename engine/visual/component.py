"""Компонент визуального скрипта.

Позволяет навесить на ноду граф `.vgraph` — программирование без текста.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from engine.components.component import Component
from engine.visual.graph import VisualGraph
from engine.visual.runtime import VisualScriptRuntime

logger = logging.getLogger("cloudengine.visual.component")


class VisualScriptComponent(Component):
    """Выполняет визуальный скрипт, привязанный к ноде."""

    type_name = "VisualScript"
    description = "Визуальный скрипт (.vgraph) — логика без кода"
    exported_properties = {
        "graph_path": {"type": "resource", "default": ""},
        "autostart": {"type": "bool", "default": True},
        "listen_area": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.graph_path: str = ""
        self.autostart: bool = True
        self.listen_area: bool = True

        self.graph: Optional[VisualGraph] = None
        self.runtime: Optional[VisualScriptRuntime] = None
        self._area: Any = None
        self._last_error: str = ""

    # ==================================================================
    # Жизненный цикл
    # ==================================================================
    def _ready(self) -> None:
        if not self.graph_path:
            return
        if not self.load_graph():
            return
        self.runtime = VisualScriptRuntime(self.graph, self.owner)
        if self.listen_area and self.graph.find_event_nodes("EventBodyEntered"):
            self._connect_area()
        if self.autostart:
            self.runtime.event_ready()

    def _process(self, delta: float) -> None:
        if self.runtime is not None:
            self.runtime.event_process(delta)

    def _physics_process(self, delta: float) -> None:
        if self.runtime is not None:
            self.runtime.event_physics_process(delta)

    def _exit_tree(self) -> None:
        self.runtime = None
        self._area = None

    # ==================================================================
    # Загрузка графа
    # ==================================================================
    def set_project_dir(self, project_dir: str) -> None:
        """Запоминает каталог проекта для относительных путей."""
        self._project_dir_hint = project_dir

    def project_dir(self) -> str:
        """Каталог проекта: явный, из систем движка или из пути сцены."""
        hint = getattr(self, "_project_dir_hint", "") or ""
        if hint:
            return hint
        tree = self.get_tree()
        if tree is None:
            return ""
        manager = getattr(getattr(tree, "render_system", None), "asset_manager", None)
        if manager is not None and getattr(manager, "project_dir", ""):
            return manager.project_dir
        script_system = getattr(tree, "script_system", None)
        if script_system is not None and getattr(script_system, "project_dir", ""):
            return script_system.project_dir
        scene = getattr(tree, "current_scene", None)
        scene_path = getattr(scene, "path", "") if scene is not None else ""
        if scene_path:
            # <project>/scenes/main.scene -> <project>
            return os.path.dirname(os.path.dirname(os.path.abspath(scene_path)))
        return ""

    def _resolve_path(self, path: str) -> str:
        """Абсолютный путь к .vgraph (с учётом каталога проекта)."""
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        directory = self.project_dir()
        if directory:
            candidate = os.path.join(directory, path)
            if os.path.isfile(candidate):
                return candidate
            return candidate
        return path

    def load_graph(self) -> bool:
        """Загружает граф из файла. Возвращает True при успехе."""
        path = self._resolve_path(self.graph_path)
        if not path or not os.path.isfile(path):
            self._last_error = f"файл не найден: {self.graph_path}"
            logger.warning("VisualScript: %s", self._last_error)
            return False
        try:
            self.graph = VisualGraph.load(path)
            self._last_error = ""
            return True
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("VisualScript: не удалось загрузить %s", path)
            return False

    def reload_graph(self) -> bool:
        """Перезагружает граф (горячая перезагрузка)."""
        if not self.load_graph():
            return False
        self.runtime = VisualScriptRuntime(self.graph, self.owner)
        self._connect_area()
        if self.autostart:
            self.runtime.event_ready()
        return True

    # ==================================================================
    # Сигналы Area2D
    # ==================================================================
    def _connect_area(self) -> None:
        """Подключает body_entered у Area2D, если граф этого ждёт."""
        from engine.nodes.area2d import Area2D
        area = self.owner if isinstance(self.owner, Area2D) else None
        if area is None and self.owner is not None:
            for child in self.owner.get_children():
                if isinstance(child, Area2D):
                    area = child
                    break
        if area is None:
            return
        self._area = area

        def on_body(body: Any) -> None:
            if self.runtime is not None:
                self.runtime.event_body_entered(body)

        area.connect("body_entered", on_body)
