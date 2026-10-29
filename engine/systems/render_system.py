"""RenderSystem — отрисовка мира с сортировкой по Z и учётом камеры.

Порядок рендера:
1. Определение активной камеры (Camera2D с enabled или камера редактора);
2. Сбор всех 2D-нод мира (исключая UI под CanvasLayer);
3. Сортировка по эффективному z-index;
4. Отрисовка на поверхность pygame.
"""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D
from engine.nodes.canvas_layer import CanvasLayer

logger = logging.getLogger("cloudengine.render")


class RenderSystem:
    """Отрисовывает текущую сцену на поверхность pygame."""

    def __init__(self, scene_tree: Any, asset_manager: Any = None) -> None:
        self.scene_tree = scene_tree
        self.asset_manager = asset_manager
        self.active_camera: Any = None
        self.render_stats = {}
        self._default_camera: Any = None
        self.background_color: tuple = (32, 32, 36)   # тёмный фон как в Godot
        self.clear_color: tuple = (32, 32, 36)

    def prepare_scene(self, scene: Any) -> None:
        """Привязывает ресурсы к нодам сцены ДО входа в дерево.

        Нужно, чтобы спрайты и компоненты (например, визуальные скрипты)
        получили доступ к AssetManager уже на этапе _ready.
        """
        if scene is None:
            return
        for node in scene.get_nodes():
            binder = getattr(node, "set_asset_manager", None)
            if callable(binder):
                try:
                    binder(self.asset_manager)
                except Exception:
                    pass
        self._apply_assets_to(scene.get_nodes())

    def bind_assets(self) -> None:
        """Привязывает AssetManager ко всем нодам текущей сцены."""
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return
        nodes = self.scene_tree.current_scene.get_nodes()
        for node in nodes:
            binder = getattr(node, "set_asset_manager", None)
            if callable(binder):
                try:
                    binder(self.asset_manager)
                except Exception:
                    pass
        self._apply_assets_to(nodes)

    def _apply_assets_to(self, nodes: Any) -> None:
        """Перечитывает текстуры/кадры/плитки после привязки менеджера."""
        for node in nodes:
            # Спрайты.
            if hasattr(node, "texture_path") and hasattr(node, "set_texture_path"):
                if node.texture_path and getattr(node, "texture", None) is None:
                    node.set_texture_path(node.texture_path)
            # Анимированные спрайты: кадры.
            if hasattr(node, "_frame_paths") and getattr(node, "_frame_paths", None):
                node.set_frame_paths(node._frame_paths)
            # TileMap.
            if hasattr(node, "_rebuild_tiles"):
                node._rebuild_tiles()

    def _apply_pending_assets(self) -> None:
        """Совместимость: применяет ресурсы к текущей сцене."""
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return
        self._apply_assets_to(self.scene_tree.current_scene.get_nodes())

    def find_active_camera(self) -> Any:
        """Ищет активную Camera2D в сцене."""
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return None
        from engine.nodes.camera2d import Camera2D
        for node in self.scene_tree.current_scene.get_nodes():
            if isinstance(node, Camera2D) and node.enabled:
                return node
            component = node.get_component('Camera2D')
            if component and component.enabled:
                return component.runtime_node()
        return None

    def render(self, surface: Any, camera_override: Any = None) -> None:
        """Отрисовывает кадр."""
        if surface is None:
            return
        try:
            surface.get_width()
        except Exception:
            return

        surface.fill(self.clear_color)

        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return

        # Камера: явная (редактор) → активная Camera2D → камера по умолчанию.
        # Без камеры в сцене игра всё равно должна показывать мир от центра.
        self.active_camera = camera_override if camera_override is not None \
            else self.find_active_camera()
        camera = self.active_camera
        if camera is None:
            from engine.nodes.camera2d import CameraState
            self._default_camera = CameraState(
                Vector2(), 1.0,
                Vector2(surface.get_width(), surface.get_height()))
            camera = self._default_camera
        if hasattr(camera, "update_camera"):
            camera.screen_size = Vector2(surface.get_width(), surface.get_height())
            from engine.core.time import Time
            camera.update_camera(Time.clamped_delta())

        from engine.nodes.camera2d import CameraState
        from engine.core.time import Time
        target_id=id(self.active_camera)
        desired=camera.get_center() if hasattr(camera,'get_center') else camera.get_global_position() if hasattr(camera,'get_global_position') else camera.center
        target_zoom=float(getattr(camera,'zoom',1))
        previous=getattr(self,'_transition_camera',None)
        if previous is not None and getattr(self,'_last_camera_id',target_id)!=target_id:
            self._transition_from=(Vector2(previous.center),previous.zoom)
            self._transition_elapsed=0.0
        self._last_camera_id=target_id
        duration=max(0,float(getattr(camera,'transition_duration',0)))
        if hasattr(self,'_transition_from') and duration>0 and getattr(self,'_transition_elapsed',duration)<duration:
            self._transition_elapsed+=Time.clamped_delta()
            t=min(1,self._transition_elapsed/duration);t=t*t*(3-2*t)
            pos,zoom=self._transition_from
            camera=CameraState(pos.lerp(desired,t),zoom+(target_zoom-zoom)*t,Vector2(surface.get_size()))
        self._transition_camera=CameraState(Vector2(camera.center if hasattr(camera,'center') else desired),float(camera.zoom),Vector2(surface.get_size()))
        start=time.perf_counter()
        from engine.systems.ui_system import UISystem
        UISystem(self.scene_tree).render(surface, background=True)
        if self.asset_manager and self.asset_manager.poll_changes():
            for node in self.scene_tree.current_scene.get_nodes():
                if hasattr(node,'texture'):node.texture=None
            self.bind_assets()
        # Сбор и сортировка.
        drawables = self._collect_drawables()
        drawables.sort(key=lambda n: n.get_effective_z())

        pending=[];batches=0;drawn=0
        class BatchSurface:
            def __init__(self,real):self.real=real
            def __getattr__(self,name):return getattr(self.real,name)
            def blit(self,source,dest,area=None,special_flags=0):
                pending.append((source,dest,area,special_flags))
        proxy=BatchSurface(surface)
        def flush():
            nonlocal batches
            if pending:surface.blits(pending,doreturn=False);pending.clear();batches+=1
        from engine.nodes.sprite2d import Sprite2D
        from engine.systems.parallax_space import draw_cameras
        for node in drawables:
            try:
                cameras = draw_cameras(node, camera)
                if len(cameras) != 1 or cameras[0] is not camera:
                    flush()
                    for projected in cameras:
                        center = node.world_to_screen(node.get_global_position(), projected)
                        node._draw_local(surface, center, projected)
                        node._execute_draw_commands(surface, projected)
                    drawn += 1
                    continue
                center = node.world_to_screen(node.get_global_position(), camera)
                # Batch only exact built-in sprites; custom drawing retains ordering.
                if type(node) is Sprite2D and not node._draw_commands:
                    node._draw_local(proxy,center,camera)
                else:
                    flush();node._draw_local(surface, center, camera)
                    node._execute_draw_commands(surface, camera)
                drawn+=1
            except Exception:
                logger.exception("Ошибка отрисовки ноды %s", node.name)

        flush()
        self.render_stats={'milliseconds':(time.perf_counter()-start)*1000,'objects':drawn,'sprite_batches':batches}
        from engine.core.profiler import profiler
        # Timing is also collected by the game-loop render profiler section.

    def _collect_drawables(self) -> List[Node2D]:
        """Собирает 2D-ноды мира, исключая UI под CanvasLayer."""
        scene = self.scene_tree.current_scene
        result: List[Node2D] = []
        self._walk(scene.root, result, in_ui=False)
        return result

    def _walk(self, node: Node, result: List[Node2D], in_ui: bool) -> None:
        if isinstance(node, Node2D) and not node.visible:
            return
        is_ui_layer = isinstance(node, CanvasLayer)
        current_in_ui = in_ui or is_ui_layer
        if isinstance(node, Node2D) and not current_in_ui:
            result.append(node)
        for child in node.get_children():
            self._walk(child, result, current_in_ui)
