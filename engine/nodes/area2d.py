"""Area2D — область-триггер (аналог Godot Area2D).

Отслеживает пересечения с телами и другими областями, генерируя сигналы
body_entered / body_exited / area_entered / area_exited.
"""

from __future__ import annotations

import logging
from typing import Any, List

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.rigidbody2d import PhysicsBody2D

logger = logging.getLogger("cloudengine.area2d")


class Area2D(PhysicsBody2D):
    """Область, обнаруживающая перекрытия."""

    exported_properties = {
        "monitoring": {"type": "bool", "default": True},
        "monitorable": {"type": "bool", "default": True},
        "priority": {"type": "int", "default": 0, "min": -128, "max": 128},
        "gravity_point": {"type": "bool", "default": False},
        "gravity": {"type": "float", "default": 980.0, "min": -100000.0, "max": 100000.0, "step": 10.0},
    }

    signals = ["body_entered", "body_exited", "area_entered", "area_exited"]

    def __init__(self, name: str = "Area2D") -> None:
        super().__init__(name)
        self.monitoring: bool = True
        self.monitorable: bool = True
        self.priority: int = 0
        self.gravity_point: bool = False
        self.gravity: float = 980.0

        # Текущие перекрытия (заполняются CollisionSystem).
        self.overlapping_bodies: List[Any] = []
        self.overlapping_areas: List[Any] = []

    def has_overlapping_bodies(self) -> bool:
        return len(self.overlapping_bodies) > 0

    def has_overlapping_areas(self) -> bool:
        return len(self.overlapping_areas) > 0

    def get_overlapping_bodies(self) -> List[Any]:
        return list(self.overlapping_bodies)

    def get_overlapping_areas(self) -> List[Any]:
        return list(self.overlapping_areas)
