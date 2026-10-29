"""Viewport — встраивание Pygame в Qt через SDL_WINDOWID.

Режимы:
- редактор: сетка, сцена, оверлей UI, гиизмо ВСЕХ нод, инструменты
  (выбор / рука / перемещение / вращение / масштаб), выделение рамкой;
- игра: GameLoop с полным стеком систем.

Ввод в игре пробрасывается из событий Qt в очередь pygame.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QImage, QPainter, QKeyEvent, QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QWidget

from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.core.game_loop import GameLoop
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D
from engine.nodes.camera2d import CameraState
from engine.nodes.canvas_layer import CanvasLayer
from editor.gizmos import Gizmos, node_has_visual

logger = logging.getLogger("cloudengine.viewport")

#: Инструменты редактора.
TOOLS = ("select", "pan", "move", "rotate", "scale")


class Viewport(QWidget):
    """Виджет рендера: pygame-поверхность внутри Qt."""

    node_selected = pyqtSignal(object)
    selection_changed = pyqtSignal(list)
    mouse_world_position = pyqtSignal(object)   # Vector2
    asset_dropped = pyqtSignal(str)
    node_property_edited = pyqtSignal(object, str, object, object)
    nodes_property_edited = pyqtSignal(list)     # [(нода, свойство, было, стало)]
    tile_edited = pyqtSignal(object, dict, dict)  # (tilemap, было, стало)
    component_add_requested = pyqtSignal(object, str)
    component_remove_requested = pyqtSignal(object, object)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 300)

        self.scene: Optional[Scene] = None
        self.selected: List[Any] = []

        # Камера редактора.
        self.camera = CameraState(Vector2(), 1.0, Vector2(800, 600))
        self.camera.editor_mode = True

        # Состояние редактора.
        self.tool: str = "select"
        self.show_gizmos: bool = True
        self.show_grid: bool = True
        #: Игровой UI в редакторе по умолчанию не рисуется (как в Godot —
        #: UI редактируется отдельно, чтобы не закрывать сцену).
        self.show_ui_overlay: bool = False
        self._panning = False
        self._pan_start = Vector2()
        self._pan_camera_start = Vector2()
        self._dragging = False
        self._drag_node: Optional[Node2D] = None
        self._drag_start_world = Vector2()
        self._drag_original_pos = Vector2()
        self._drag_original_rotation = 0.0
        self._drag_original_scale = Vector2(1.0, 1.0)
        self._drag_start_screen = Vector2()
        #: Исходные позиции всех выделенных нод (групповое перетаскивание).
        self._drag_originals: List[Any] = []

        # --- Прилипание к сетке ---
        self.snap_to_grid: bool = True
        self.grid_size: float = 32.0

        # --- Рисование по тайлам ---
        self.tile_mode: str = "off"          # off / brush / eraser / fill / rect
        self.tile_id: int = 0
        self.tile_collision: bool = False
        self.tilemap: Any = None
        self.show_tile_grid: bool = True
        self._tile_painting: bool = False
        self._tile_before: Optional[dict] = None
        self._tile_rect_start: Optional[Any] = None
        self._hover_cell: Optional[Any] = None
        self._selection_start = Vector2()
        self._selection_end = Vector2()
        self._selecting = False

        # Pygame.
        self.screen: Any = None
        self._embedded = False
        self._surface_size = (0, 0)
        self._render_errors = 0
        self._editor_timer = QTimer(self)
        self._editor_timer.timeout.connect(self._tick)
        self._editor_timer.start(1000 // 60)

        # Игровой цикл.
        self.game_loop: Optional[GameLoop] = None
        self.scene_tree: Optional[SceneTree] = None
        self.asset_manager: Any = None
        self.script_system: Any = None
        self.settings: dict = {}
        self.is_playing = False
        self.is_paused = False
        self.view_mode = "2D"

    # ==================================================================
    # Pygame: рендер в offscreen-поверхность и вывод через Qt
    # ==================================================================
    def _ensure_pygame(self) -> None:
        """Инициализирует pygame.

        По умолчанию рендерим в обычную pygame.Surface и выводим её в Qt
        через QImage. Это надёжнее встраивания SDL-окна (SDL_WINDOWID):
        пересоздание SDL-окна при изменении размеров панелей роняло
        приложение. Если нужен именно SDL-вариант, задайте переменную
        окружения CLOUDENGINE_SDL_EMBED=1.
        """
        if self.screen is not None:
            return
        try:
            import pygame
            pygame.init()
        except Exception as exc:
            logger.error("Pygame недоступен: %s", exc)
            return

        use_embed = os.environ.get("CLOUDENGINE_SDL_EMBED", "") in ("1", "true", "yes")
        if use_embed:
            try:
                import pygame
                width = max(self.width(), 1)
                height = max(self.height(), 1)
                os.environ["SDL_WINDOWID"] = str(int(self.winId()))
                pygame.display.init()
                self.screen = pygame.display.set_mode((width, height), pygame.DOUBLEBUF)
                self._embedded = True
                self._surface_size = (width, height)
                self.camera.screen_size = Vector2(width, height)
                logger.info("Pygame встроен в Qt (SDL_WINDOWID)")
                return
            except Exception as exc:
                logger.warning("Встраивание SDL не удалось (%s), работаю offscreen", exc)

        self._create_offscreen_surface()

    def _create_offscreen_surface(self) -> None:
        """Создаёт (пересоздаёт) offscreen-поверхность под размер виджета."""
        try:
            import pygame
            width = max(self.width(), 1)
            height = max(self.height(), 1)
            self.screen = pygame.Surface((width, height))
            self._embedded = False
            self._surface_size = (width, height)
            self.camera.screen_size = Vector2(width, height)
        except Exception:
            logger.exception("Не удалось создать поверхность рендера")

    def _resize_surface(self) -> None:
        """Подгоняет поверхность под новый размер виджета."""
        if self.screen is None:
            return
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        if (width, height) == self._surface_size:
            return
        if self._embedded:
            # В режиме SDL-окна пересоздание опасно: обновляем только размер.
            try:
                import pygame
                os.environ["SDL_WINDOWID"] = str(int(self.winId()))
                self.screen = pygame.display.set_mode((width, height), pygame.DOUBLEBUF)
                self._surface_size = (width, height)
                self.camera.screen_size = Vector2(width, height)
            except Exception:
                logger.exception("Не удалось изменить размер SDL-окна")
            return
        self._create_offscreen_surface()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.isVisible():
            self._resize_surface()

    def paintEvent(self, event) -> None:  # noqa: N802
        try:
            if not self._embedded and self.screen is not None:
                self._blit_surface_to_qt()
        except Exception:
            pass
        super().paintEvent(event)

    def _blit_surface_to_qt(self) -> None:
        try:
            import pygame
            raw = pygame.image.tostring(self.screen, "RGBA")
            image = QImage(raw, self.screen.get_width(), self.screen.get_height(),
                           QImage.Format.Format_RGBA8888)
            painter = QPainter(self)
            painter.drawImage(0, 0, image)
            painter.end()
        except Exception:
            pass

    # ==================================================================
    # Тик
    # ==================================================================
    def _tick(self) -> None:
        """Безопасный тик: любая ошибка логируется, но не роняет редактор."""
        try:
            if not self.isVisible():
                return
            if self.is_playing and self.game_loop is not None:
                self._tick_game()
            else:
                self._tick_editor()
        except Exception:
            self._render_errors += 1
            if self._render_errors <= 5:
                logger.exception("Ошибка отрисовки Viewport")
            elif self._render_errors == 6:
                logger.error("Дальнейшие ошибки отрисовки подавлены")

    def _tick_editor(self) -> None:
        if self.screen is None:
            self._ensure_pygame()
        if self.screen is None:
            return
        self.camera.screen_size = Vector2(self.screen.get_width(),
                                          self.screen.get_height())
        self._render_editor_frame()

    def _tick_game(self) -> None:
        if self.game_loop is not None and self.screen is not None:
            debugger=getattr(self,'debugger',None)
            if debugger and debugger.paused:
                return
            from engine.systems.script_debugger import DebugStop
            try:
                if debugger:
                    with debugger.tracing():
                        self.game_loop.step()
                else:
                    self.game_loop.step()
            except DebugStop:
                self.stop_game()
                self.window().toolbar.set_playing(False,False)
            except Exception:
                logger.exception('Игра остановлена из-за ошибки выполнения скрипта')
                self.stop_game()
                self.window().toolbar.set_playing(False, False)
            self._draw_collision_debug()
            self._present()

    def _draw_collision_debug(self):
        if not getattr(self,'show_collision_debug',False):
            return
        from editor.collision_debug import draw_collisions
        scene=self.scene_tree.current_scene if self.is_playing and self.scene_tree else self.scene
        camera=self.camera
        if self.is_playing and self.game_loop and self.game_loop.render_system:
            camera=self.game_loop.render_system.active_camera or camera
        draw_collisions(self.screen,scene,camera)

    def _present(self) -> None:
        """Выводит кадр: offscreen — через перерисовку Qt, SDL — через flip."""
        try:
            if self._embedded:
                import pygame
                pygame.display.flip()
            elif self.isVisible():
                self.update()
        except Exception:
            pass

    # ==================================================================
    # Кадр редактора
    # ==================================================================
    def _render_editor_frame(self) -> None:
        try:
            import pygame  # noqa: F401
        except Exception:
            return

        if self.asset_manager and self.asset_manager.poll_changes():
            if self.scene:
                for node in self.scene.get_nodes():
                    if hasattr(node,'texture'):node.texture=None
                self.bind_node_assets(self.scene.root)
        self.screen.fill((40, 40, 44))
        if self.show_grid:
            self._draw_grid()

        if self.scene is not None:
            if self.show_ui_overlay:
                from types import SimpleNamespace
                from engine.systems.ui_system import UISystem
                UISystem(SimpleNamespace(current_scene=self.scene, input=None)).render(self.screen, background=True)
            for node in self._collect_drawables():
                try:
                    from engine.systems.parallax_space import draw_cameras
                    for projected in draw_cameras(node, self.camera):
                        center = node.world_to_screen(node.get_global_position(), projected)
                        node._draw_local(self.screen, center, projected)
                        node._execute_draw_commands(self.screen, projected)
                except Exception:
                    logger.exception("Ошибка отрисовки ноды %s", node.name)
            if self.show_ui_overlay:
                self._draw_editor_ui()

        if getattr(self,'preview_post',False) and self.scene:
            from types import SimpleNamespace
            from engine.systems.light_system import LightSystem
            from engine.systems.post_process import PostProcessSystem
            tree=SimpleNamespace(current_scene=self.scene,settings=getattr(self,"settings",{}) or {})
            LightSystem(tree).render(self.screen,self.camera)
            PostProcessSystem(tree).apply(self.screen,0)
        if getattr(self,'camera_guides',True) and self.scene:
            from engine.nodes.camera2d import Camera2D
            for node in self.scene.get_nodes():
                feature=node.get_component('Camera2D')
                camera=node if isinstance(node,Camera2D) else feature.runtime_node() if feature and feature.enabled else None
                if camera is None:continue
                width=self.settings.get('window',{}).get('width',1280)/max(.05,camera.zoom)
                height=self.settings.get('window',{}).get('height',720)/max(.05,camera.zoom)
                center=self.camera.world_to_screen(camera.get_global_position())
                rect=pygame.Rect(0,0,round(width*self.camera.zoom),round(height*self.camera.zoom));rect.center=center.as_ints()
                pygame.draw.rect(self.screen,(112,169,196),rect,1)
                safe=rect.inflate(-round(rect.width*.1),-round(rect.height*.1));pygame.draw.rect(self.screen,(117,125,143),safe,1)
        self._draw_collision_debug()
        self._draw_tile_overlay()
        Gizmos.draw_all(self.screen, self.scene, self.selected, self.camera,
                        tool=self.tool, show_gizmos=self.show_gizmos)
        if self._selecting:
            Gizmos.draw_selection_box(self.screen, self._selection_start,
                                      self._selection_end)
        self._present()

    def _collect_drawables(self) -> List[Node2D]:
        """Ноды мира, отсортированные по Z (без UI-слоёв)."""
        result: List[Node2D] = []
        if self.scene is None:
            return result

        def walk(node):
            if isinstance(node, CanvasLayer) or (isinstance(node, Node2D) and not node.visible):
                return
            if isinstance(node, Node2D):
                result.append(node)
            for child in node.get_children():
                walk(child)

        walk(self.scene.root)
        result.sort(key=lambda n: n.get_effective_z())
        return result

    def _draw_editor_ui(self) -> None:
        """Отрисовка UI-слоёв (CanvasLayer) прямо в редакторе."""
        from types import SimpleNamespace
        from engine.systems.ui_system import UISystem
        UISystem(SimpleNamespace(current_scene=self.scene, input=None)).render(self.screen)

    def _draw_grid(self) -> None:
        try:
            import pygame
            width, height = self.screen.get_width(), self.screen.get_height()
            step = 32.0 * self.camera.zoom
            if step < 8:
                step *= 4
            if step <= 0:
                return
            origin = self.camera.world_to_screen(Vector2())
            x0 = int(origin.x % step)
            y0 = int(origin.y % step)
            for x in range(x0, width, max(int(step), 1)):
                pygame.draw.line(self.screen, (55, 55, 60), (x, 0), (x, height), 1)
            for y in range(y0, height, max(int(step), 1)):
                pygame.draw.line(self.screen, (55, 55, 60), (0, y), (width, y), 1)
            pygame.draw.line(self.screen, (95, 95, 105),
                             (int(origin.x), 0), (int(origin.x), height), 1)
            pygame.draw.line(self.screen, (95, 95, 105),
                             (0, int(origin.y)), (width, int(origin.y)), 1)
        except Exception:
            pass


    def set_scene(self, scene: Optional[Scene]) -> None:
        changed = scene is not self.scene
        self.scene = scene
        self.selected = []
        self.selection_changed.emit([])
        if scene is not None:
            self._bind_assets()
            if changed:
                # Показываем всю сцену целиком — иначе кажется, что пусто.
                self.frame_all()

    def frame_all(self) -> None:
        """Вписывает все ноды сцены в окно редактора."""
        if self.scene is None:
            return
        points = [n.get_global_position() for n in self.scene.get_nodes()
                  if isinstance(n, Node2D)]
        if not points:
            return
        min_x = min(p.x for p in points)
        max_x = max(p.x for p in points)
        min_y = min(p.y for p in points)
        max_y = max(p.y for p in points)
        margin = 160.0
        width = max(max_x - min_x + margin, 64.0)
        height = max(max_y - min_y + margin, 64.0)
        screen = Vector2(self.screen.get_width(), self.screen.get_height()) \
            if self.screen is not None else Vector2(self.width(), self.height())
        zoom = min(screen.x / width, screen.y / height)
        self.camera.zoom = max(0.25, min(4.0, zoom))
        self.camera.center = Vector2((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    def focus_on_scene_camera(self, scene: Optional[Scene] = None) -> bool:
        """Ставит камеру редактора в позицию Camera2D из сцены."""
        scene = scene or self.scene
        if scene is None:
            return False
        from engine.nodes.camera2d import Camera2D
        for node in scene.get_nodes():
            if isinstance(node, Camera2D):
                self.camera.center = node.get_global_position()
                zoom = float(getattr(node, "zoom", 1.0) or 1.0)
                self.camera.zoom = max(0.05, min(20.0, zoom))
                return True
        return False

    def set_asset_manager(self, manager: Any) -> None:
        self.asset_manager = manager
        self._bind_assets()

    def bind_node_assets(self, node: Any) -> None:
        """Привязывает ресурсы к новой ноде и её детям (важно для спрайтов!)."""
        if node is None or self.asset_manager is None:
            return
        stack = [node]
        while stack:
            current = stack.pop()
            binder = getattr(current, "set_asset_manager", None)
            if callable(binder):
                try:
                    binder(self.asset_manager)
                except Exception:
                    pass
            if (hasattr(current, "texture_path") and hasattr(current, "set_texture_path")
                    and getattr(current, "texture_path", "")
                    and getattr(current, "texture", None) is None):
                try:
                    current.set_texture_path(current.texture_path)
                except Exception:
                    pass
            if hasattr(current, "_frame_paths") and getattr(current, "_frame_paths", None):
                try:
                    current.set_frame_paths(current._frame_paths)
                except Exception:
                    pass
            if hasattr(current, "_rebuild_tiles"):
                try:
                    current._rebuild_tiles()
                except Exception:
                    pass
            stack.extend(current.get_children())

    def _bind_assets(self) -> None:
        if self.scene is None or self.asset_manager is None:
            return
        self.bind_node_assets(self.scene.root)

    def set_view_mode(self, mode: str) -> None:
        self.view_mode = mode

    def focus_on_selected(self) -> None:
        if self.selected and isinstance(self.selected[0], Node2D):
            self.camera.center = self.selected[0].get_global_position()

    def reset_camera(self) -> None:
        self.camera.center = Vector2()
        self.camera.zoom = 1.0

    def select_nodes(self, nodes: List[Any]) -> None:
        self.selected = list(nodes)
        self.selection_changed.emit(self.selected)

    def stop_timer(self) -> None:
        """Останавливает таймер отрисовки (вызывается при закрытии окна)."""
        self._editor_timer.stop()

    # ==================================================================
    # Мышь (редактор)
    # ==================================================================
    def _screen_to_world(self, pos: QPoint) -> Vector2:
        return self.camera.screen_to_world(Vector2(pos.x(), pos.y()))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.setFocus()
        if self.is_playing:
            self._post_mouse_press(event)
            return

        pos = Vector2(event.position().x(), event.position().y())

        if event.button() == Qt.MouseButton.MiddleButton or self.tool == "pan":
            self._panning = True
            self._pan_start = pos
            self._pan_camera_start = Vector2(self.camera.center)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            world = self._screen_to_world(event.position().toPoint())
            if self._tile_active():
                self._begin_tile_paint(pos)
                return
            hit = self._pick_node(pos)
            if hit is not None:
                if hit not in self.selected:
                    self.selected = [hit]
                    self.selection_changed.emit(self.selected)
                    self.node_selected.emit(hit)
                self._dragging = True
                self._drag_node = hit
                self._drag_original_pos = Vector2(hit.position)
                self._drag_original_rotation = float(getattr(hit, "rotation", 0.0))
                scale = getattr(hit, "scale", Vector2(1.0, 1.0))
                self._drag_original_scale = Vector2(scale)
                self._drag_start_world = world
                self._drag_start_screen = pos
                # Запоминаем позиции всех выделенных для группового сдвига.
                self._drag_originals = [
                    (item, Vector2(item.position)) for item in self.selected
                    if isinstance(item, Node2D) and hasattr(item, "position")]
                if not any(item is hit for item, _old in self._drag_originals):
                    self._drag_originals.append((hit, Vector2(hit.position)))
            else:
                self.selected = []
                self.selection_changed.emit([])
                self._selecting = True
                self._selection_start = pos
                self._selection_end = pos

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = Vector2(event.position().x(), event.position().y())
        self.mouse_world_position.emit(self.camera.screen_to_world(pos))

        if self.is_playing:
            self._post_mouse_move(event)
            return

        if self._tile_active():
            self._hover_cell = self._tile_cell(pos)
            if self._tile_painting:
                if self.tile_mode == "rect":
                    return
                if self._hover_cell is not None:
                    self.tilemap.paint(self._hover_cell[0], self._hover_cell[1],
                                       self._tile_paint_id(), self.tile_collision)
                return

        if self._panning:
            delta = pos - self._pan_start
            self.camera.center = self._pan_camera_start - delta / max(self.camera.zoom, 1e-6)
        elif self._dragging and self._drag_node is not None:
            node = self._drag_node
            if self.tool == "rotate":
                node.rotation = self._drag_original_rotation + \
                    (pos.x - self._drag_start_screen.x) * 0.6
            elif self.tool == "scale":
                factor = 1.0 + (pos.x - self._drag_start_screen.x) * 0.005
                node.scale = Vector2(max(0.02, self._drag_original_scale.x * factor),
                                     max(0.02, self._drag_original_scale.y * factor))
            else:
                world = self._screen_to_world(event.position().toPoint())
                offset = world - self._drag_start_world
                if self.snap_to_grid and self.grid_size > 0:
                    # Прилипает не курсор, а сама позиция объекта.
                    target = self._drag_original_pos + offset
                    snapped = Vector2(round(target.x / self.grid_size) * self.grid_size,
                                      round(target.y / self.grid_size) * self.grid_size)
                    offset = snapped - self._drag_original_pos
                for item, original in self._drag_originals:
                    item.position = original + offset
        elif self._selecting:
            self._selection_end = pos

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.is_playing:
            self._post_mouse_release(event)
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._tile_painting:
                self._end_tile_paint()
                return
            if self._selecting:
                self._selecting = False
                self._select_nodes_in_rect()
            if self._dragging:
                node = self._drag_node
                self._dragging = False
                self._drag_node = None
                originals = self._drag_originals
                self._drag_originals = []
                if node is not None:
                    if self.tool == "rotate":
                        if abs(node.rotation - self._drag_original_rotation) > 1e-4:
                            self.node_property_edited.emit(
                                node, "rotation", self._drag_original_rotation, node.rotation)
                    elif self.tool == "scale":
                        if not node.scale.is_equal_approx(self._drag_original_scale):
                            self.node_property_edited.emit(
                                node, "scale", self._drag_original_scale, Vector2(node.scale))
                    else:
                        changes = []
                        for item, original in originals:
                            if not item.position.is_equal_approx(original):
                                changes.append((item, "position", original,
                                                Vector2(item.position)))
                        if len(changes) == 1:
                            self.node_property_edited.emit(*changes[0])
                        elif changes:
                            self.nodes_property_edited.emit(changes)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self.is_playing:
            self._post_wheel_event(event)
            return
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.camera.zoom = max(0.05, min(20.0, self.camera.zoom * factor))

    # ==================================================================
    # Рисование по тайлам
    # ==================================================================
    def set_tile_tool(self, mode: str) -> None:
        """Переключает инструмент рисования по тайлам."""
        self.tile_mode = mode or "off"
        if self.tile_mode == "off":
            self._tile_painting = False
            self._tile_rect_start = None
            self._hover_cell = None
        if self.tile_mode != "off":
            # Инструменты рисования работают как курсор, а не как выбор.
            self.tool = "select"

    def set_tilemap(self, node: Any) -> None:
        """Задаёт карту, по которой рисуем."""
        self.tilemap = node if node is not None and "TileMap" in type(node).__name__ \
            else None
        self._hover_cell = None
        if self.tilemap is not None:
            try:
                self.grid_size = float(self.tilemap.cell_size.x) or 32.0
            except Exception:
                pass

    def set_tile_id(self, tile_id: int, collision: bool = False) -> None:
        """Выбирает тайл и режим коллизии для рисования."""
        self.tile_id = int(tile_id)
        self.tile_collision = bool(collision)

    def _tile_active(self) -> bool:
        """Активен ли сейчас инструмент рисования по тайлам."""
        return (self.tile_mode in ("brush", "eraser", "fill", "rect")
                and self.tilemap is not None and not self.is_playing)

    def _tile_cell(self, screen_pos: Vector2) -> Optional[Any]:
        """Ячейка тайловой карты под курсором."""
        if self.tilemap is None:
            return None
        try:
            world = self.camera.screen_to_world(screen_pos)
            return self.tilemap.world_to_cell(world)
        except Exception:
            return None

    def _tile_paint_id(self) -> int:
        """Идентификатор тайла для текущего инструмента (-1 = стереть)."""
        return -1 if self.tile_mode == "eraser" else int(self.tile_id)

    def _begin_tile_paint(self, screen_pos: Vector2) -> None:
        """Начало мазка: кисть, заливка или прямоугольник."""
        cell = self._tile_cell(screen_pos)
        if cell is None or self.tilemap is None:
            return
        self._tile_before = self.tilemap.snapshot()
        self._tile_painting = True
        self._hover_cell = cell

        if self.tile_mode == "fill":
            self.tilemap.flood_fill(cell[0], cell[1], self._tile_paint_id(),
                                    self.tile_collision)
            self._end_tile_paint()
        elif self.tile_mode == "rect":
            self._tile_rect_start = cell
        else:
            self.tilemap.paint(cell[0], cell[1], self._tile_paint_id(),
                               self.tile_collision)

    def _end_tile_paint(self) -> None:
        """Завершение мазка: прямоугольник, снимок и сигнал для отмены."""
        if self.tilemap is None:
            self._tile_painting = False
            return
        if self.tile_mode == "rect" and self._tile_rect_start is not None \
                and self._hover_cell is not None:
            self.tilemap.paint_rect(self._tile_rect_start[0], self._tile_rect_start[1],
                                    self._hover_cell[0], self._hover_cell[1],
                                    self._tile_paint_id(), self.tile_collision)
        self._tile_painting = False
        self._tile_rect_start = None
        before = self._tile_before
        self._tile_before = None
        after = self.tilemap.snapshot()
        if before is not None and before != after:
            self.tile_edited.emit(self.tilemap, before, after)

    def _draw_tile_overlay(self) -> None:
        """Сетка тайлов и подсветка ячейки под курсором."""
        if not self.show_tile_grid or self.tilemap is None or self.screen is None:
            return
        if self.tile_mode == "off" or self.scene is None:
            return
        try:
            import pygame
            cell = Vector2(self.tilemap.cell_size)
            zoom = float(self.camera.zoom)
            step_x = cell.x * zoom
            step_y = cell.y * zoom
            if step_x < 6 or step_y < 6:
                return
            width = self.screen.get_width()
            height = self.screen.get_height()
            origin = self.camera.world_to_screen(
                self.tilemap.get_global_position())
            color = (58, 58, 70)
            start_x = origin.x % step_x
            start_y = origin.y % step_y
            x = start_x
            while x < width:
                pygame.draw.line(self.screen, color, (int(x), 0), (int(x), height), 1)
                x += step_x
            y = start_y
            while y < height:
                pygame.draw.line(self.screen, color, (0, int(y)), (width, int(y)), 1)
                y += step_y

            if self._hover_cell is not None:
                world = self.tilemap.cell_to_world(self._hover_cell[0],
                                                   self._hover_cell[1])
                screen = self.camera.world_to_screen(world)
                rect = pygame.Rect(int(screen.x), int(screen.y),
                                   max(int(step_x), 1), max(int(step_y), 1))
                highlight = (200, 90, 90) if self.tile_mode == "eraser" \
                    else (120, 200, 255)
                pygame.draw.rect(self.screen, highlight, rect, 2)
        except Exception:
            pass

    def _pick_node(self, screen_pos: Vector2) -> Optional[Node2D]:
        """Ищет ноду под курсором среди всех нод (включая невидимые графически)."""
        if self.scene is None:
            return None
        candidates: List[Any] = []
        for node in self.scene.get_nodes():
            if isinstance(node, Node2D):
                candidates.append(node)
        for node in reversed(candidates):
            if not node.visible:
                continue
            if node_has_visual(node):
                if Gizmos.hit_test(node, screen_pos, self.camera):
                    return node
            else:
                center = Gizmos.node_anchor(node, self.camera)
                if screen_pos.distance_to(center) <= 12:
                    return node
        return None

    def _select_nodes_in_rect(self) -> None:
        if self.scene is None:
            return
        from engine.math.rect2 import Rect2
        p1, p2 = self._selection_start, self._selection_end
        rect = Rect2(Vector2(min(p1.x, p2.x), min(p1.y, p2.y)),
                     Vector2(abs(p2.x - p1.x), abs(p2.y - p1.y)))
        self.selected = []
        for node in self.scene.get_nodes():
            if not isinstance(node, Node2D):
                continue
            screen = node.world_to_screen(node.get_global_position(), self.camera)
            if rect.has_point(screen):
                self.selected.append(node)
        self.selection_changed.emit(self.selected)

    # ==================================================================
    # Игровой режим
    # ==================================================================
    def start_game(self, scene: Scene, settings: dict, project_dir: str) -> None:
        """Запускает игру: собирает SceneTree + системы и стартует цикл."""
        try:
            import pygame  # noqa: F401
        except Exception:
            return
        if self.screen is None:
            self._ensure_pygame()

        import copy
        settings = copy.deepcopy(settings)
        self.settings = settings
        self.is_playing = False
        self.is_paused = False

        from engine.systems.script_system import ScriptSystem
        self.script_system = ScriptSystem(project_dir)
        self.script_system.reload()
        if self.script_system.errors:
            detail = '\n'.join(f"{d['path']}:{d['line']}: {d['message']}" for d in self.script_system.diagnostics)
            raise ValueError('Исправьте ошибки загрузки скриптов перед Play:\n' + detail)

        from engine.resources.asset_manager import AssetManager
        self.asset_manager = AssetManager(project_dir)

        from engine.input.input_manager import InputManager
        input_manager = InputManager(settings.get("input", {}))
        self.scene_tree = SceneTree(settings, input_manager)

        # Play always runs a deep copy of the current in-memory scene.
        import copy
        from engine.resources.scene_serializer import SceneSerializer
        root = SceneSerializer.node_from_dict(copy.deepcopy(SceneSerializer.node_to_dict(scene.root)), self.script_system)
        play_scene = Scene(scene.name, root)

        from engine.systems.render_system import RenderSystem
        from engine.systems.physics_system import PhysicsSystem
        from engine.systems.collision_system import CollisionSystem
        from engine.systems.animation_system import AnimationSystem
        from engine.systems.audio_system import AudioSystem
        from engine.systems.particle_system import ParticleSystem
        from engine.systems.ui_system import UISystem
        from engine.systems.light_system import LightSystem
        from engine.systems.post_process import PostProcessSystem

        render_system = RenderSystem(self.scene_tree, self.asset_manager)
        physics_system = PhysicsSystem(self.scene_tree)
        collision_system = CollisionSystem(self.scene_tree)
        animation_system = AnimationSystem(self.scene_tree)
        audio_system = AudioSystem(self.scene_tree)
        particle_system = ParticleSystem(self.scene_tree)
        ui_system = UISystem(self.scene_tree)
        light_system = LightSystem(self.scene_tree)
        post_process_system = PostProcessSystem(self.scene_tree)

        audio_system.init_mixer()

        # Системы подключаем ДО входа сцены в дерево: компоненты в _ready
        # должны видеть AssetManager и ScriptSystem.
        self.game_loop = GameLoop(self.scene_tree, settings, self.screen)
        self.game_loop.attach_systems(
            physics=physics_system, collision=collision_system,
            render=render_system, animation=animation_system,
            audio=audio_system, particle=particle_system, ui=ui_system,
            script=self.script_system, light=light_system,
            post_process=post_process_system)
        self.game_loop.show_debug_overlay = bool(
            settings.get("debug_overlay", False))
        render_system.prepare_scene(play_scene)

        self.scene_tree.change_scene(play_scene)
        render_system.bind_assets()
        light_system.invalidate()
        post_process_system.invalidate()
        self.game_loop.start()
        self.is_playing = True

    def stop_game(self) -> None:
        if self.game_loop is not None:
            self.game_loop.stop()
        if self.scene_tree is not None and self.scene_tree.current_scene is not None:
            self.scene_tree._exit_scene(self.scene_tree.current_scene)
        self.game_loop = None
        self.scene_tree = None
        self.is_playing = False
        self.is_paused = False
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        except Exception:
            pass

    def pause_game(self) -> None:
        if self.game_loop is not None:
            self.game_loop.pause()
            self.is_paused = True

    def resume_game(self) -> None:
        if self.game_loop is not None:
            self.game_loop.resume()
            self.is_paused = False

    # ==================================================================
    # Проброс Qt → pygame
    # ==================================================================
    def _post_key_event(self, event: QKeyEvent, pressed: bool) -> None:
        try:
            import pygame
            key = _qt_key_to_pygame(event.key())
            if key is not None:
                etype = pygame.KEYDOWN if pressed else pygame.KEYUP
                pygame.event.post(pygame.event.Event(etype, key=key, mod=0,
                                                     unicode=event.text()))
        except Exception:
            pass

    def _post_mouse_press(self, event: QMouseEvent) -> None:
        try:
            import pygame
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=_qt_button_to_pygame(event.button()),
                pos=(int(event.position().x()), int(event.position().y()))))
        except Exception:
            pass

    def _post_mouse_release(self, event: QMouseEvent) -> None:
        try:
            import pygame
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONUP, button=_qt_button_to_pygame(event.button()),
                pos=(int(event.position().x()), int(event.position().y()))))
        except Exception:
            pass

    def _post_mouse_move(self, event: QMouseEvent) -> None:
        try:
            import pygame
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEMOTION,
                pos=(int(event.position().x()), int(event.position().y())),
                rel=(0, 0), buttons=(0, 0, 0)))
        except Exception:
            pass

    def _post_wheel_event(self, event: QWheelEvent) -> None:
        try:
            import pygame
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEWHEEL, x=0, y=1 if event.angleDelta().y() > 0 else -1))
        except Exception:
            pass

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self.is_playing:
            self._post_key_event(event, True)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self.is_playing:
            self._post_key_event(event, False)
        else:
            super().keyReleaseEvent(event)

    # ==================================================================
    # Контекстное меню объекта (правый клик)
    # ==================================================================
    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """Меню объекта: навесить/снять компоненты прямо на нём."""
        if self.is_playing or self.scene is None:
            return
        try:
            from PyQt6.QtWidgets import QMenu
            from engine.components.registry import visible_categories
        except Exception:
            return

        pos = Vector2(event.pos().x(), event.pos().y())
        node = self._pick_node(pos)
        if node is None:
            event.ignore()
            return
        self.select_nodes([node])

        menu = QMenu(self)
        title = menu.addAction(f"Объект: {node.name}")
        title.setEnabled(False)
        menu.addSeparator()

        add_menu = menu.addMenu("Добавить компонент")
        for category, types in visible_categories().items():
            category_menu = add_menu.addMenu(category)
            for type_name in types:
                action = category_menu.addAction(type_name)
                action.triggered.connect(
                    lambda checked=False, t=type_name, n=node:
                    self.component_add_requested.emit(n, t))

        components = list(getattr(node, "components", []) or [])
        if components:
            remove_menu = menu.addMenu("Снять компонент")
            for component in components:
                action = remove_menu.addAction(component.get_type_name())
                action.setEnabled(not getattr(component, "required", False))
                action.triggered.connect(
                    lambda checked=False, c=component, n=node:
                    self.component_remove_requested.emit(n, c))

        menu.addSeparator()
        focus_action = menu.addAction("Фокус на объекте")
        focus_action.triggered.connect(lambda: self.focus_on_selected())
        menu.exec(self.mapToGlobal(event.pos()))

    # ==================================================================
    # Drag&drop ассетов
    # ==================================================================
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.asset_dropped.emit(path)
        event.acceptProposedAction()


# ======================================================================
# Маппинг Qt → pygame
# ======================================================================
def _build_key_map() -> dict:
    try:
        import pygame
        from PyQt6.QtCore import Qt as QtCore
        mapping = {
            QtCore.Key.Key_Space: pygame.K_SPACE,
            QtCore.Key.Key_Return: pygame.K_RETURN,
            QtCore.Key.Key_Enter: pygame.K_RETURN,
            QtCore.Key.Key_Escape: pygame.K_ESCAPE,
            QtCore.Key.Key_Tab: pygame.K_TAB,
            QtCore.Key.Key_Backspace: pygame.K_BACKSPACE,
            QtCore.Key.Key_Delete: pygame.K_DELETE,
            QtCore.Key.Key_Up: pygame.K_UP,
            QtCore.Key.Key_Down: pygame.K_DOWN,
            QtCore.Key.Key_Left: pygame.K_LEFT,
            QtCore.Key.Key_Right: pygame.K_RIGHT,
            QtCore.Key.Key_Shift: pygame.K_LSHIFT,
            QtCore.Key.Key_Control: pygame.K_LCTRL,
            QtCore.Key.Key_Alt: pygame.K_LALT,
            QtCore.Key.Key_CapsLock: pygame.K_CAPSLOCK,
        }
        for ch in "abcdefghijklmnopqrstuvwxyz":
            mapping[getattr(QtCore.Key, f"Key_{ch.upper()}")] = getattr(pygame, f"K_{ch}")
        for digit in "0123456789":
            mapping[getattr(QtCore.Key, f"Key_{digit}")] = getattr(pygame, f"K_{digit}")
        return mapping
    except Exception:
        return {}


_QT_KEY_MAP = _build_key_map()


def _qt_key_to_pygame(key: int):
    return _QT_KEY_MAP.get(key)


def _qt_button_to_pygame(button) -> int:
    from PyQt6.QtCore import Qt as QtCore
    if button == QtCore.MouseButton.LeftButton:
        return 1
    if button == QtCore.MouseButton.MiddleButton:
        return 2
    if button == QtCore.MouseButton.RightButton:
        return 3
    return 1
