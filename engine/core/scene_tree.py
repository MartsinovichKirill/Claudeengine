"""SceneTree — управление сценами и глобальным деревом (аналог Godot SceneTree)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.core.node import Node
from engine.core.scene import Scene
from engine.input.input_manager import InputManager

logger = logging.getLogger("cloudengine.scene_tree")


class SceneTree:
    """Глобальное дерево: содержит root, текущую сцену, ввод и настройки.

    Также хранит ссылки на системы (физику, коллизии и т.д.), которые
    устанавливаются игровым циклом перед запуском.
    """

    def __init__(self, settings: Optional[Dict[str, Any]] = None,
                 input_manager: Optional[InputManager] = None) -> None:
        self.root = Node("root")
        self.current_scene: Optional[Scene] = None
        self.settings: Dict[str, Any] = settings or {}
        self.input: InputManager = input_manager or InputManager(
            self.settings.get("input", {})
        )
        self.paused: bool = False
        self._scenes: Dict[str, Scene] = {}

        # Ссылки на системы (заполняются GameLoop).
        self.physics_system: Any = None
        self.collision_system: Any = None
        self.render_system: Any = None
        self.animation_system: Any = None
        self.audio_system: Any = None
        self.particle_system: Any = None
        self.ui_system: Any = None
        self.script_system: Any = None
        self.game_loop: Any = None
        self.shared_data = {}
        self._pending_scene = None
        self.transition_error = ''
        from engine.systems.cutscenes import CutscenePlayer
        self.cutscenes = CutscenePlayer(self)

    # ------------------------------------------------------------------
    # Сцены
    # ------------------------------------------------------------------
    def add_scene(self, name: str, scene: Scene) -> None:
        """Регистрирует сцену под именем."""
        self._scenes[name] = scene

    def get_scene(self, name: str) -> Optional[Scene]:
        return self._scenes.get(name)

    def change_scene(self, scene: Scene) -> None:
        """Переключает текущую сцену, корректно вызывая жизненный цикл."""
        if self.current_scene is not None:
            self._exit_scene(self.current_scene)
        self.current_scene = scene
        self._enter_scene(scene)

    def change_scene_to(self, name: str) -> None:
        """Переключается на зарегистрированную сцену по имени."""
        scene = self._scenes.get(name)
        if scene is None:
            raise ValueError(f"Сцена '{name}' не зарегистрирована")
        self.change_scene(scene)

    def load_scene(self, path):
        from pathlib import Path
        project = Path(getattr(self.script_system, 'project_dir', '')).resolve()
        target = (project / path).resolve()
        if not target.is_relative_to(project) or target.suffix != '.scene':
            raise ValueError('Укажите .scene внутри проекта')
        loaded = Scene.load(str(target), self.script_system)
        self._pending_scene = loaded
        return loaded

    def set_camera(self,path):
        if not self.current_scene: raise ValueError('Нет сцены')
        node=self.current_scene.find_node_by_path(path)
        target=node.get_component('Camera2D') if node and not hasattr(node,'zoom') else node
        if target is None or not hasattr(target,'zoom'):raise ValueError('Камера не найдена')
        from engine.nodes.camera2d import Camera2D
        for n in self.current_scene.get_nodes():
            camera=n if isinstance(n,Camera2D) else n.get_component('Camera2D')
            if camera:camera.enabled=camera is target
        runtime=target.runtime_node() if hasattr(target,'runtime_node') else target
        runtime.reset_follow()

    def flush_scene_change(self):
        if self._pending_scene is None: return
        scene, self._pending_scene = self._pending_scene, None
        self.cutscenes.stop(True)
        render = self.render_system
        if render: render.prepare_scene(scene)
        self.change_scene(scene)
        if render:
            render.bind_assets()
            render.active_camera=None
            for attr in ('_transition_camera','_transition_from','_last_camera_id'):
                if hasattr(render,attr):delattr(render,attr)
        if self.collision_system is not None:self.collision_system._area_overlaps.clear()
        loop=self.game_loop
        for name in ('light_system','post_process_system'):
            system=getattr(loop,name,None)
            if system and hasattr(system,'invalidate'): system.invalidate()

    def _enter_scene(self, scene: Scene) -> None:
        """Вход сцены в дерево: _enter_tree (сверху вниз) → _ready (снизу вверх)."""
        root = scene.root
        root.parent = self.root
        self._set_tree_refs(root, enter=True)
        # _enter_tree сверху вниз.
        for node in self._flatten(root):
            node._enter_tree()
        # _ready снизу вверх (сначала дети).
        for node in reversed(self._flatten(root)):
            node._ready()
            node._ready_components()

    def _exit_scene(self, scene: Scene) -> None:
        root = scene.root
        # _exit_tree снизу вверх.
        for node in reversed(self._flatten(root)):
            node._exit_components()
            node._exit_tree()
        self._set_tree_refs(root, enter=False)
        root.parent = None

    def _set_tree_refs(self, root: Node, enter: bool) -> None:
        for node in self._flatten(root):
            if enter:
                node._scene_tree = self
                node._inside_tree = True
            else:
                node._scene_tree = None
                node._inside_tree = False

    def _on_node_added(self, node: Node) -> None:
        """Вызывается Node.add_child при добавлении ноды в активное дерево."""
        if self.current_scene is None:
            return
        node._scene_tree = self
        node._inside_tree = True
        for n in self._flatten(node):
            n._enter_tree()
        for n in reversed(self._flatten(node)):
            n._ready()
            n._ready_components()

    def _on_node_removed(self, node: Node) -> None:
        for n in reversed(self._flatten(node)):
            n._exit_components()
            n._exit_tree()
        for n in self._flatten(node):
            n._inside_tree = False
            n._scene_tree = None

    @staticmethod
    def _flatten(root: Node) -> List[Node]:
        result: List[Node] = []

        def _walk(n: Node) -> None:
            result.append(n)
            for child in n.get_children():
                _walk(child)

        _walk(root)
        return result

    # ------------------------------------------------------------------
    # Обработка кадра
    # ------------------------------------------------------------------
    def process(self, delta: float) -> None:
        """Обрабатывает один кадр для текущей сцены."""
        if self.paused or self.current_scene is None:
            return
        self.cutscenes.update(delta)
        self.current_scene.process(delta)
        self._process_pending_free()

    def physics_process(self, delta: float) -> None:
        if self.paused or self.current_scene is None:
            return
        self.current_scene.physics_process(delta)

    def dispatch_input(self, event: Any) -> None:
        """Передаёт событие ввода всем нодам текущей сцены.

        Название отличается от атрибута self.input (InputManager), чтобы
        не перекрывать его.
        """
        if self.current_scene is None:
            return
        self.current_scene.input(event)

    def _process_pending_free(self) -> None:
        """Удаляет ноды, помеченные queue_free()."""
        if self.current_scene is None:
            return
        for node in self.current_scene.get_nodes():
            if node._pending_free and node.parent is not None:
                node.parent.remove_child(node)

    # ------------------------------------------------------------------
    # Группы
    # ------------------------------------------------------------------
    def get_nodes_in_group(self, group: str) -> List[Node]:
        if self.current_scene is None:
            return []
        return [n for n in self.current_scene.get_nodes() if group in n.groups]

    def call_group(self, group: str, method: str, *args) -> None:
        for node in self.get_nodes_in_group(group):
            fn = getattr(node, method, None)
            if callable(fn):
                try:
                    fn(*args)
                except Exception:
                    logger.exception("Ошибка вызова %s.%s", node.name, method)

    def quit(self) -> None:
        """Завершает игровой цикл."""
        if self.game_loop is not None:
            self.game_loop.stop()
