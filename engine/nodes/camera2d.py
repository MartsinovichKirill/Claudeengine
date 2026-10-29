"""Camera2D — камера 2D (аналог Godot Camera2D).

Поддерживает слежение за целью, зум, границы, сглаживание и отступы (drag).
Также содержит CameraState — лёгкую камеру для редактора (пан/зум без ноды).
"""

from __future__ import annotations

import math
from typing import Any, Optional

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.math.rect2 import Rect2
from engine.nodes.node2d import Node2D


class CameraState:
    """Лёгкое состояние камеры для преобразования мировых координат в экранные.

    Используется редактором, когда активная камера в сцене не задана.
    """

    def __init__(self, center: Vector2 = None, zoom: float = 1.0,
                 screen_size: Vector2 = None) -> None:
        self.center = Vector2(center) if center is not None else Vector2()
        self.zoom = float(zoom)
        self.screen_size = Vector2(screen_size) if screen_size is not None else Vector2(800, 600)

    def world_to_screen(self, world: Vector2, camera: Any = None) -> Vector2:
        """Мировые координаты → экранные.

        Необязательный второй аргумент нужен для совместимости с
        Node2D.draw(surface, camera): камера сама является Node2D.
        """
        return (world - self.center) * self.zoom + self.screen_size * 0.5

    def screen_to_world(self, screen: Vector2, camera: Any = None) -> Vector2:
        """Экранные координаты → мировые."""
        return (screen - self.screen_size * 0.5) / max(self.zoom, 1e-6) + self.center

    def get_center(self) -> Vector2:
        return self.center

    def update_camera(self, delta: float) -> None:
        """У камеры редактора нет сглаживания — метод для совместимости."""


class Camera2D(Node2D):
    """Камера, определяющая область видимости мира."""

    exported_properties = {
        "look_ahead": {"type":"float","default":0.0,"min":0.0,"max":1000.0},
        "look_ahead_smoothing": {"type":"float","default":6.0,"min":0.1,"max":30.0},
        "pixel_snap": {"type":"bool","default":False},
        "offset": {"type":"vector2","default":[0.0,0.0]},
        "transition_duration": {"type":"float","default":0.35,"min":0.0,"max":5.0},
        "zoom": {"type": "float", "default": 1.0, "min": 0.05, "max": 20.0, "step": 0.05},
        "enabled": {"type": "bool", "default": True},
        "position_smoothing": {"type": "float", "default": 0.0, "min": 0.0, "max": 20.0, "step": 0.1},
        "target_path": {"type": "string", "default": ""},
        "limit_left": {"type": "int", "default": -10000000, "min": -100000000, "max": 100000000},
        "limit_top": {"type": "int", "default": -10000000, "min": -100000000, "max": 100000000},
        "limit_right": {"type": "int", "default": 10000000, "min": -100000000, "max": 100000000},
        "limit_bottom": {"type": "int", "default": 10000000, "min": -100000000, "max": 100000000},
        "drag_h_enabled": {"type": "bool", "default": False},
        "drag_v_enabled": {"type": "bool", "default": False},
        "drag_left_margin": {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01},
        "drag_right_margin": {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01},
        "drag_top_margin": {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01},
        "drag_bottom_margin": {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01},
        "shake_decay": {"type": "float", "default": 1.6, "min": 0.1, "max": 20.0, "step": 0.1},
        "shake_max_offset": {"type": "float", "default": 22.0, "min": 0.0, "max": 400.0, "step": 1.0},
    }

    def __init__(self, name: str = "Camera2D") -> None:
        super().__init__(name)
        self.look_ahead=0.0
        self.look_ahead_smoothing=6.0
        self._last_follow_x=None
        self._look_offset=0.0
        self.pixel_snap = False
        self.offset = Vector2()
        self.transition_duration=0.35
        self.zoom: float = 1.0
        self.enabled: bool = True
        self.position_smoothing: float = 0.0
        self.target_path: str = ""
        self.limit_left: int = -10000000
        self.limit_top: int = -10000000
        self.limit_right: int = 10000000
        self.limit_bottom: int = 10000000
        self.drag_h_enabled: bool = False
        self.drag_v_enabled: bool = False
        self.drag_left_margin: float = 0.2
        self.drag_right_margin: float = 0.2
        self.drag_top_margin: float = 0.2
        self.drag_bottom_margin: float = 0.2
        #: Тряска камеры: 0 — спокойно, 1 — максимальная амплитуда.
        self.shake_decay: float = 1.6
        self.shake_max_offset: float = 22.0
        self.shake_trauma: float = 0.0

        self.screen_size: Vector2 = Vector2(800, 600)
        self._view_center: Optional[Vector2] = None  # сглаженная позиция
        self._target_node: Optional[Node2D] = None
        self._shake_offset: Vector2 = Vector2()

    # ------------------------------------------------------------------
    # Тряска
    # ------------------------------------------------------------------
    def add_trauma(self, amount: float) -> None:
        """Добавляет «травму» камеры: 0..1, затухает сама."""
        try:
            self.shake_trauma = max(0.0, min(1.0, self.shake_trauma + float(amount)))
        except Exception:
            pass

    def shake(self, amount: float = 0.5) -> None:
        """Короткая тряска камеры."""
        self.add_trauma(amount)

    # ------------------------------------------------------------------
    # Слежение
    # ------------------------------------------------------------------
    def get_target(self) -> Optional[Node2D]:
        """Разрешает цель по target_path (или использует ранее найденную)."""
        if not self.target_path:
            return None
        tree = self.get_tree()
        if tree is None or tree.current_scene is None:
            return self._target_node
        try:
            self._target_node = tree.current_scene.root.get_node(self.target_path)
        except ValueError:
            self._target_node = None
        return self._target_node

    def update_camera(self, delta: float) -> None:
        """Обновляет сглаживание и слежение за целью."""
        target = self.get_target()
        if target is not None:
            desired = target.get_global_position()
        else:
            desired = self.get_global_position()

        if target is not None:
            x=desired.x
            direction=0 if self._last_follow_x is None or abs(x-self._last_follow_x)<0.001 else (1 if x>self._last_follow_x else -1)
            self._last_follow_x=x
            if direction:
                weight=1-math.exp(-max(.1,self.look_ahead_smoothing)*max(0,delta))
                self._look_offset+=(direction*self.look_ahead-self._look_offset)*weight
            desired.x+=self._look_offset
        desired = desired + Vector2(self.offset)
        # Применяем drag margins.
        desired = self._apply_drag(desired)

        if self._view_center is None:
            self._view_center = desired

        if self.position_smoothing > 0.0:
            weight = 1.0 - math.exp(-self.position_smoothing * max(delta, 0.0))
            self._view_center = self._view_center.lerp(desired, weight)
        else:
            self._view_center = desired

        self._update_shake(delta)

    def reset_follow(self):
        self._view_center=None
        self._target_node=None
        self._last_follow_x=None
        self._look_offset=0.0

    def _update_shake(self, delta: float) -> None:
        """Затухание тряски и случайное смещение камеры."""
        if self.shake_trauma <= 0.0:
            self._shake_offset = Vector2()
            return
        self.shake_trauma = max(0.0, self.shake_trauma
                                - self.shake_decay * max(delta, 0.0))
        amplitude = self.shake_trauma * self.shake_trauma * self.shake_max_offset
        if amplitude <= 0.01:
            self._shake_offset = Vector2()
            return
        import random
        self._shake_offset = Vector2(
            random.uniform(-amplitude, amplitude),
            random.uniform(-amplitude, amplitude))

    def _apply_drag(self, center: Vector2) -> Vector2:
        """Смещает центр камеры в пределах drag-отступов."""
        result = Vector2(center)
        if self._view_center is None:
            return result
        half_w = self.screen_size.x / (2.0 * max(self.zoom, 1e-6))
        half_h = self.screen_size.y / (2.0 * max(self.zoom, 1e-6))
        if self.drag_h_enabled:
            result.x = min(max(self._view_center.x, center.x - half_w * max(0.0, self.drag_right_margin)),
                           center.x + half_w * max(0.0, self.drag_left_margin))
        if self.drag_v_enabled:
            result.y = min(max(self._view_center.y, center.y - half_h * max(0.0, self.drag_bottom_margin)),
                           center.y + half_h * max(0.0, self.drag_top_margin))
        return result

    # ------------------------------------------------------------------
    # Преобразования координат
    # ------------------------------------------------------------------
    def get_center(self) -> Vector2:
        """Текущий центр камеры в мировых координатах (с учётом тряски)."""
        if self._view_center is None:
            return self.get_global_position() + Vector2(self.offset) + self._shake_offset
        center = self._view_center + self._shake_offset
        if self.pixel_snap:
            zoom = max(self.zoom, 1e-6)
            return Vector2(round(center.x * zoom) / zoom, round(center.y * zoom) / zoom)
        return center

    def world_to_screen(self, world: Vector2, camera: Any = None) -> Vector2:
        """Мировые координаты → экранные (camera игнорируется).

        Второй аргумент принимается для совместимости с Node2D.draw, так как
        сама камера тоже является Node2D и может отрисовываться.
        """
        center = self._clamp_center(self.get_center())
        return (world - center) * self.zoom + self.screen_size * 0.5

    def screen_to_world(self, screen: Vector2, camera: Any = None) -> Vector2:
        """Экранные координаты → мировые."""
        center = self._clamp_center(self.get_center())
        return (screen - self.screen_size * 0.5) / max(self.zoom, 1e-6) + center

    def _clamp_center(self, center: Vector2) -> Vector2:
        """Ограничивает центр камеры лимитами.

        Если лимиты уже области видимости, камера встаёт по их центру —
        иначе она «залипала» бы у края и не следила за целью.
        """
        half_w = self.screen_size.x / (2.0 * max(self.zoom, 1e-6))
        half_h = self.screen_size.y / (2.0 * max(self.zoom, 1e-6))
        cx = center.x
        cy = center.y

        span_x = self.limit_right - self.limit_left
        if span_x <= 2.0 * half_w:
            cx = (self.limit_left + self.limit_right) / 2.0
        else:
            cx = max(self.limit_left + half_w,
                     min(self.limit_right - half_w, cx))

        span_y = self.limit_bottom - self.limit_top
        if span_y <= 2.0 * half_h:
            cy = (self.limit_top + self.limit_bottom) / 2.0
        else:
            cy = max(self.limit_top + half_h,
                     min(self.limit_bottom - half_h, cy))
        return Vector2(cx, cy)
