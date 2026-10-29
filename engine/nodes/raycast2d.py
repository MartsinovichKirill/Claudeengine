"""RayCast2D — луч для проверки столкновений (аналог Godot RayCast2D)."""

from __future__ import annotations

import math
from typing import Any, Optional

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D


class RayCast2D(Node2D):
    """Испускает луч от позиции ноды в направлении cast_to."""

    exported_properties = {
        "cast_to": {"type": "vector2", "default": [0.0, 100.0]},
        "enabled": {"type": "bool", "default": True},
        "exclude_parent": {"type": "bool", "default": True},
        "collide_with_areas": {"type": "bool", "default": False},
        "collide_with_bodies": {"type": "bool", "default": True},
        "collision_mask": {"type": "int", "default": 1, "min": 0, "max": 65535},
    }

    def __init__(self, name: str = "RayCast2D") -> None:
        super().__init__(name)
        self.cast_to: Vector2 = Vector2(0.0, 100.0)
        self.enabled: bool = True
        self.exclude_parent: bool = True
        self.collide_with_areas: bool = False
        self.collide_with_bodies: bool = True
        self.collision_mask: int = 1
        self.collision_layer: int = 1

        # Результаты последнего луча.
        self._colliding: bool = False
        self._collider: Any = None
        self._collision_point: Vector2 = Vector2()
        self._collision_normal: Vector2 = Vector2()

    def force_raycast_update(self) -> None:
        """Принудительно пересчитывает луч."""
        tree = self.get_tree()
        collision = tree.collision_system if tree is not None else None
        if collision is None or not self.enabled:
            self._colliding = False
            self._collider = None
            return
        collision.raycast(self)

    def is_colliding(self) -> bool:
        return self._colliding

    def get_collider(self) -> Any:
        return self._collider

    def get_collision_point(self) -> Vector2:
        return self._collision_point

    def get_collision_normal(self) -> Vector2:
        return self._collision_normal

    def get_ray_end(self) -> Vector2:
        """Конечная точка луча в мировых координатах."""
        return self.get_global_position() + self.cast_to

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        """Отрисовка луча в редакторе."""
        try:
            import pygame
            end = self.world_to_screen(self.get_ray_end(), camera)
            pygame.draw.line(surface, (255, 80, 80, 200), center.as_ints(),
                             end.as_ints(), 1)
            pygame.draw.circle(surface, (255, 80, 80, 200), end.as_ints(), 3)
        except Exception:
            pass
