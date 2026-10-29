"""CollisionShape2D — коллайдер (аналог Godot CollisionShape2D).

Поддерживает формы: Rectangle, Circle, Capsule, Polygon.
Коллайдер является дочерним узлом физического тела и описывает его форму.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D


class CollisionShape2D(Node2D):
    """Форма коллизии, прикрепляемая к физическому телу."""

    exported_properties = {
        "shape_type": {"type": "enum", "default": "rectangle",
                       "options": ["rectangle", "circle", "capsule", "polygon"]},
        "size": {"type": "vector2", "default": [32.0, 32.0]},
        "radius": {"type": "float", "default": 16.0, "min": 0.5, "max": 10000.0, "step": 1.0},
        "height": {"type": "float", "default": 32.0, "min": 0.5, "max": 10000.0, "step": 1.0},
        "disabled": {"type": "bool", "default": False},
        "one_way": {"type": "bool", "default": False},
        "one_way_margin": {"type": "float", "default": 4.0, "min": 0.0, "max": 100.0, "step": 0.5},
    }

    def __init__(self, name: str = "CollisionShape2D") -> None:
        super().__init__(name)
        self.shape_type: str = "rectangle"
        self.size: Vector2 = Vector2(32.0, 32.0)
        self.radius: float = 16.0
        self.height: float = 32.0
        self.disabled: bool = False
        self.one_way: bool = False
        self.one_way_margin: float = 4.0
        self.points: List[Vector2] = []      # вершины полигона (локальные)

    # ------------------------------------------------------------------
    # Глобальная форма
    # ------------------------------------------------------------------
    def get_world_vertices(self) -> List[Vector2]:
        """Вершины фигуры в мировых координатах."""
        if self.shape_type == "polygon" and self.points:
            transform = self.get_global_transform()
            return [transform.xform(p) for p in self.points]
        if self.shape_type == "rectangle":
            half = self.size * 0.5
            transform = self.get_global_transform()
            return [transform.xform(Vector2(-half.x, -half.y)),
                    transform.xform(Vector2(half.x, -half.y)),
                    transform.xform(Vector2(half.x, half.y)),
                    transform.xform(Vector2(-half.x, half.y))]
        if self.shape_type == "capsule":
            # Аппроксимация капсулы прямоугольником.
            half = Vector2(self.radius, self.height * 0.5)
            transform = self.get_global_transform()
            return [transform.xform(Vector2(-half.x, -half.y)),
                    transform.xform(Vector2(half.x, -half.y)),
                    transform.xform(Vector2(half.x, half.y)),
                    transform.xform(Vector2(-half.x, half.y))]
        return []

    def get_aabb(self) -> Tuple[Vector2, Vector2]:
        """Ограничивающий прямоугольник фигуры в мировых координатах (min, max)."""
        if self.shape_type == "circle":
            center = self.get_global_position()
            scale = self.get_global_transform().scale
            r = self.radius * max(abs(scale.x), abs(scale.y))
            return (Vector2(center.x - r, center.y - r),
                    Vector2(center.x + r, center.y + r))
        vertices = self.get_world_vertices()
        if vertices:
            xs = [v.x for v in vertices]
            ys = [v.y for v in vertices]
            return (Vector2(min(xs), min(ys)), Vector2(max(xs), max(ys)))
        center = self.get_global_position()
        return (Vector2(center.x - 1, center.y - 1),
                Vector2(center.x + 1, center.y + 1))

    def set_points(self, points: List[Vector2]) -> None:
        """Задаёт вершины полигона."""
        self.points = [Vector2(p) for p in points]

    # ------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------
    def _serialize_data(self) -> dict:
        return {"points": [[p.x, p.y] for p in self.points]}

    def _deserialize_data(self, data: dict) -> None:
        self.points = [Vector2(p) for p in data.get("points", [])]

    # ------------------------------------------------------------------
    # Отрисовка (для редактора)
    # ------------------------------------------------------------------
    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        try:
            import pygame
            color = (0, 160, 255, 200)
            if self.shape_type == "circle":
                zoom = getattr(camera, "zoom", 1.0) if camera else 1.0
                r = int(self.radius * max(abs(self.scale.x), abs(self.scale.y)) * zoom)
                pygame.draw.circle(surface, color, center.as_ints(), max(r, 1), 1)
            elif self.shape_type == "rectangle":
                half = self.size * 0.5 * self.scale.abs()
                rect = pygame.Rect(0, 0, int(half.x * 2), int(half.y * 2))
                rect.center = center.as_ints()
                pygame.draw.rect(surface, color, rect, 1)
            elif self.shape_type == "capsule":
                half = Vector2(self.radius * abs(self.scale.x),
                               self.height * 0.5 * abs(self.scale.y))
                rect = pygame.Rect(0, 0, int(half.x * 2), int(half.y * 2))
                rect.center = center.as_ints()
                pygame.draw.rect(surface, color, rect, 1, border_radius=int(half.x))
            elif self.shape_type == "polygon":
                pts = [(center + p * self.scale).as_ints() for p in self.points]
                if len(pts) >= 2:
                    pygame.draw.polygon(surface, color, pts, 1)
        except Exception:
            pass
