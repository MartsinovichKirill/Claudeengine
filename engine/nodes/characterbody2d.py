"""CharacterBody2D — кинематическое тело (аналог Godot CharacterBody2D).

Реализует move_and_slide() и move_and_collide() с определением пола.
Гравитация применяется физической системой; движение происходит только
при вызове move_and_slide/move_and_collide пользователем.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from engine.math.vector2 import Vector2
from engine.nodes.rigidbody2d import PhysicsBody2D

logger = logging.getLogger("cloudengine.character_body")


class CharacterBody2D(PhysicsBody2D):
    """Тело персонажа с кинематическим движением и скольжением по стенам."""

    exported_properties = {
        "motion_mode": {"type": "enum", "default": "grounded",
                        "options": ["grounded", "floating"]},
        "up_direction": {"type": "vector2", "default": [0.0, -1.0]},
        "floor_max_angle": {"type": "float", "default": 45.0, "min": 0.0, "max": 180.0, "step": 1.0},
        "max_slides": {"type": "int", "default": 4, "min": 1, "max": 32},
        "floor_snap_length": {"type": "float", "default": 4.0, "min": 0.0, "max": 100.0, "step": 0.5},
    }

    signals = ["body_entered", "body_exited"]

    def __init__(self, name: str = "CharacterBody2D") -> None:
        super().__init__(name)
        self.velocity: Vector2 = Vector2()
        self.motion_mode: str = "grounded"
        self.up_direction: Vector2 = Vector2(0.0, -1.0)
        self.floor_max_angle: float = 45.0
        self.max_slides: int = 4
        self.floor_snap_length: float = 4.0

        self._on_floor: bool = False
        self._on_wall: bool = False
        self._on_ceiling: bool = False
        self._was_on_floor: bool = False
        self._floor_normal: Vector2 = Vector2(0.0, -1.0)
        self._last_motion: Vector2 = Vector2()
        self._collisions_this_frame: list = []

    # ------------------------------------------------------------------
    # Состояние
    # ------------------------------------------------------------------
    def is_on_floor(self) -> bool:
        return self._on_floor

    def is_on_wall(self) -> bool:
        return self._on_wall

    def is_on_ceiling(self) -> bool:
        return self._on_ceiling

    def get_floor_normal(self) -> Vector2:
        return self._floor_normal

    def get_last_motion(self) -> Vector2:
        return self._last_motion

    def get_slide_collision_count(self) -> int:
        return len(self._collisions_this_frame)

    def get_slide_collision(self, index: int) -> Any:
        if 0 <= index < len(self._collisions_this_frame):
            return self._collisions_this_frame[index]
        return None

    # ------------------------------------------------------------------
    # Движение
    # ------------------------------------------------------------------
    def move_and_collide(self, motion: Vector2) -> Optional[dict]:
        """Перемещает тело на motion и возвращает информацию о первом столкновении.

        Внимание: CollisionSystem.move_and_collide сам применяет движение к
        позиции тела (с учётом разрешения столкновений), поэтому повторно
        прибавлять motion здесь нельзя.
        """
        tree = self.get_tree()
        collision = tree.collision_system if tree is not None else None
        if collision is None:
            self.position += motion
            return None

        result = collision.move_and_collide(self, motion)
        if result is not None:
            self.position = result["position"]
        return result

    def move_and_slide(self) -> None:
        """Перемещает тело, используя velocity, со скольжением по поверхностям."""
        delta = self._current_delta()
        tree = self.get_tree()
        collision = tree.collision_system if tree is not None else None

        self._was_on_floor = self._on_floor
        self._collisions_this_frame = []
        self._on_floor = False
        self._on_wall = False
        self._on_ceiling = False

        if collision is None:
            self.position += self.velocity * delta
            return

        remaining = self.velocity * delta
        self._last_motion = Vector2(remaining)

        for _ in range(max(1, self.max_slides)):
            result = collision.move_and_collide(self, remaining)
            if result is None:
                # Движение уже применено внутри move_and_collide.
                break

            # Перемещаемся до точки столкновения.
            self.position = result["position"]
            normal = Vector2(result["normal"])
            collider = result.get("collider")
            self._collisions_this_frame.append(result)
            self._emit_collision(collider)

            # Определяем пол/стену/потолок по нормали.
            angle = abs(self._angle_between(normal, self.up_direction))
            limit = self.floor_max_angle * math.pi / 180.0
            if angle <= limit:
                self._on_floor = True
                self._floor_normal = normal
            elif angle >= math.pi - limit:
                self._on_ceiling = True
            else:
                self._on_wall = True

            # Скольжение: убираем компоненту движения вдоль нормали.
            remaining = Vector2(result.get('remainder', remaining))
            dot = remaining.dot(normal)
            if dot < 0:
                remaining -= normal * dot
            else:
                remaining = Vector2()

        # Корректировка скорости по столкновениям (аналог поведения Godot):
        # убираем компоненту скорости, направленную в поверхность.
        for hit in self._collisions_this_frame:
            hit_normal = Vector2(hit["normal"])
            into = self.velocity.dot(hit_normal)
            if into < 0:
                self.velocity -= hit_normal * into

        # Прилипание к полу (floor snap): не даём «отрываться» на мелких шагах.
        if (not self._on_floor and self._was_on_floor
                and self.motion_mode == "grounded"
                and self.velocity.y >= 0.0
                and self.floor_snap_length > 0.0):
            probe = collision.test_move(self, Vector2(0.0, self.floor_snap_length))
            if probe is not None:
                self._on_floor = True
                self._floor_normal = Vector2(probe["normal"])

    def _current_delta(self) -> float:
        from engine.core.time import Time
        return Time.physics_delta

    @staticmethod
    def _angle_between(a: Vector2, b: Vector2) -> float:
        dot = max(-1.0, min(1.0, a.normalized().dot(b.normalized())))
        return math.acos(dot)

    def _emit_collision(self, collider: Any) -> None:
        if collider is not None:
            self.emit_signal("body_entered", collider)

    def _serialize_data(self) -> dict:
        return {"velocity": [self.velocity.x, self.velocity.y]}
