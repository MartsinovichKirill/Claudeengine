"""StaticBody2D — неподвижное физическое тело (аналог Godot StaticBody2D)."""

from __future__ import annotations

from engine.math.vector2 import Vector2
from engine.nodes.rigidbody2d import PhysicsBody2D


class StaticBody2D(PhysicsBody2D):
    """Неподвижный коллайдер. Не двигается, но участвует в коллизиях."""

    exported_properties = {
        "light_occluder": {"type": "bool", "default": True},
    }

    def __init__(self, name: str = "StaticBody2D") -> None:
        super().__init__(name)
        self.collision_layer = 1
        self.collision_mask = 1
        # Статичная геометрия по умолчанию отбрасывает тень.
        self.light_occluder = True
