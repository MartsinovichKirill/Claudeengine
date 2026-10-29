"""PhysicsSystem — гравитация, интеграция скорости, движение тел.

Настройки гравитации берутся из project.json:
    "physics": {"gravity": [0, 980], "physics_fps": 60}
"""

from __future__ import annotations

import logging
from typing import Any

from engine.core.node import Node
from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.physics_system")


class PhysicsSystem:
    """Применяет гравитацию и интегрирует движение физических тел."""

    def __init__(self, scene_tree: Any) -> None:
        self.scene_tree = scene_tree
        settings = scene_tree.settings if scene_tree is not None else {}
        physics = settings.get("physics", {})
        grav = physics.get("gravity", [0.0, 980.0])
        self.gravity = Vector2(grav[0], grav[1])

    # ------------------------------------------------------------------
    # Шаг 1: силы (гравитация, трение)
    # ------------------------------------------------------------------
    def step(self, dt: float) -> None:
        """Применяет силы к телам перед _physics_process."""
        from engine.nodes.rigidbody2d import RigidBody2D
        from engine.nodes.characterbody2d import CharacterBody2D

        for node in self._bodies():
            if isinstance(node, RigidBody2D):
                if node.freeze or node.sleeping:
                    continue
                node.velocity += self.gravity * node.gravity_scale * dt
                # Приложенная сила -> ускорение.
                if node.mass > 0:
                    node.velocity += node.applied_force / node.mass * dt
                node.applied_force = Vector2()
                # Трение (drag).
                if node.drag > 0:
                    factor = max(0.0, 1.0 - node.drag * dt)
                    node.velocity *= factor
            elif isinstance(node, CharacterBody2D):
                # Гравитация для персонажей (кроме случаев на полу).
                if not node.is_on_floor():
                    node.velocity += self.gravity * dt

    # ------------------------------------------------------------------
    # Шаг 2: интеграция движения
    # ------------------------------------------------------------------
    def integrate(self, dt: float) -> None:
        """Перемещает RigidBody2D (CharacterBody2D двигается через move_and_slide)."""
        from engine.nodes.rigidbody2d import RigidBody2D

        collision = self.scene_tree.collision_system if self.scene_tree else None
        for node in self._bodies():
            if isinstance(node, RigidBody2D):
                if node.freeze or node.sleeping:
                    continue
                motion = node.velocity * dt
                if collision is not None and node.get_collision_shapes():
                    remaining = motion
                    for _ in range(4):
                        result = collision.move_and_collide(node, remaining)
                        if result is None:
                            break
                        self._resolve_rigid_bounce(node, result)
                        normal = Vector2(result['normal'])
                        remaining = Vector2(result.get('remainder', Vector2())).slide(normal)
                        if remaining.length < 1e-6:
                            break
                else:
                    node.position += motion
                node.rotation += node.angular_velocity * dt

    def _resolve_rigid_bounce(self, body: Any, result: dict) -> None:
        """Отскок RigidBody2D от поверхности."""
        normal = Vector2(result["normal"])
        if body.velocity.dot(normal) >= 0:
            return
        if body.bounce > 0:
            # Отражение скорости.
            reflected = body.velocity.reflect(normal)
            body.velocity = reflected * body.bounce
        else:
            # Убираем компоненту скорости вдоль нормали.
            body.velocity = body.velocity.slide(normal)
        # Трение.
        if body.friction > 0:
            body.velocity *= (1.0 - body.friction)

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------
    def _bodies(self) -> list:
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return []
        from engine.nodes.rigidbody2d import PhysicsBody2D
        bodies = [n for n in self.scene_tree.current_scene.get_nodes() if isinstance(n, PhysicsBody2D)]
        for node in self.scene_tree.current_scene.get_nodes():
            if callable(getattr(node, 'physics_body', None)):
                body = node.physics_body()
                if body is not None:
                    bodies.append(body)
        return bodies

    def move_and_slide(self, body: Any, dt: float) -> None:
        """Делегирует move_and_slide тела."""
        body.move_and_slide()
