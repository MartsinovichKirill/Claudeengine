"""RigidBody2D и базовый PhysicsBody2D (аналог Godot).

PhysicsBody2D — общая база для физических тел: слои коллизий и получение
дочерних коллайдеров. RigidBody2D — динамическое тело с гравитацией.
"""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.physics")


class PhysicsBody2D(Node2D):
    """Базовый физический узел с collision_layer / collision_mask."""

    exported_properties = {
        "collision_layer": {"type": "int", "default": 1, "min": 0, "max": 65535},
        "collision_mask": {"type": "int", "default": 1, "min": 0, "max": 65535},
        "light_occluder": {"type": "bool", "default": False},
    }

    def __init__(self, name: str = "PhysicsBody2D") -> None:
        super().__init__(name)
        self.collision_layer: int = 1
        self.collision_mask: int = 1
        #: Отбрасывает ли тело тень от источников света Light2D.
        self.light_occluder: bool = False

    def get_collision_shapes(self) -> List[Any]:
        """Возвращает дочерние CollisionShape2D (не disabled)."""
        from engine.nodes.collision_shape import CollisionShape2D
        shapes = []
        for child in self._children:
            if isinstance(child, CollisionShape2D) and not child.disabled:
                shapes.append(child)
        return shapes

    def can_collide_with(self, other: "PhysicsBody2D") -> bool:
        """Проверяет совместимость слоёв (self.mask & other.layer)."""
        return bool(self.collision_mask & other.collision_layer)

    def get_contact_shapes(self) -> List[Tuple[Any, Vector2, Vector2]]:
        """Возвращает (shape, aabb_min, aabb_max) для всех коллайдеров."""
        result = []
        for shape in self.get_collision_shapes():
            aabb = shape.get_aabb()
            result.append((shape, aabb[0], aabb[1]))
        return result


class RigidBody2D(PhysicsBody2D):
    """Динамическое тело: скорость, масса, трение, угловая скорость, заморозка."""

    exported_properties = {
        "mass": {"type": "float", "default": 1.0, "min": 0.01, "max": 100000.0, "step": 0.1},
        "gravity_scale": {"type": "float", "default": 1.0, "min": -10.0, "max": 10.0, "step": 0.1},
        "drag": {"type": "float", "default": 0.0, "min": 0.0, "max": 100.0, "step": 0.1},
        "angular_velocity": {"type": "float", "default": 0.0, "min": -1000.0, "max": 1000.0, "step": 1.0},
        "freeze": {"type": "bool", "default": False},
        "sleeping": {"type": "bool", "default": False},
        "bounce": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
        "friction": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
    }

    signals = ["body_entered", "body_exited"]

    def __init__(self, name: str = "RigidBody2D") -> None:
        super().__init__(name)
        self.mass: float = 1.0
        self.gravity_scale: float = 1.0
        self.drag: float = 0.0
        self.velocity: Vector2 = Vector2()
        self.angular_velocity: float = 0.0
        self.freeze: bool = False
        self.sleeping: bool = False
        self.bounce: float = 0.0
        self.friction: float = 0.0
        self.applied_force: Vector2 = Vector2()

    def apply_force(self, force: Vector2) -> None:
        """Прикладывает силу (F = m*a)."""
        if self.mass > 0:
            self.applied_force += force

    def apply_impulse(self, impulse: Vector2) -> None:
        """Прикладывает импульс (мгновенное изменение скорости)."""
        if self.mass > 0:
            self.velocity += impulse / self.mass

    def _serialize_data(self) -> dict:
        return {"velocity": [self.velocity.x, self.velocity.y]}
