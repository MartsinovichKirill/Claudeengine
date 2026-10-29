"""ParticleSystem — обновление CPU-эмиттеров частиц (Particles2D)."""

from __future__ import annotations

import logging
import math
import random
from typing import Any

import numpy as np

from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.particle_system")


class ParticleSystem:
    """Обновляет позиции и время жизни частиц всех эмиттеров."""

    def __init__(self, scene_tree: Any) -> None:
        self.scene_tree = scene_tree

    def update(self, delta: float) -> None:
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return
        from engine.nodes.particles2d import Particles2D
        for emitter in self.scene_tree.current_scene.get_nodes():
            if isinstance(emitter, Particles2D):
                try:
                    self._update_emitter(emitter, delta)
                except Exception:
                    logger.exception("Ошибка частиц %s", emitter.name)

    def _update_emitter(self, emitter: Any, delta: float) -> None:
        if not math.isfinite(delta) or delta <= 0:
            return
        if emitter.emitting:
            if emitter.one_shot:
                if not emitter._burst_emitted:
                    self._spawn(emitter, 0, burst=True)
                    emitter._burst_emitted = True
                emitter.emitting = False
            else:
                self._spawn(emitter, delta)

        n = len(emitter._lifetimes)
        if n == 0:
            return
        # Интеграция.
        emitter._velocities += np.array(
            [emitter.gravity.x, emitter.gravity.y], dtype=float) * delta
        emitter._positions += emitter._velocities * delta
        emitter._lifetimes += delta

        # Удаление мёртвых частиц.
        alive = emitter._lifetimes < emitter._max_lifetimes
        emitter._positions = emitter._positions[alive]
        emitter._velocities = emitter._velocities[alive]
        emitter._lifetimes = emitter._lifetimes[alive]
        emitter._max_lifetimes = emitter._max_lifetimes[alive]

        # one_shot: останавливаемся, когда частицы закончились.
        if emitter.one_shot and len(emitter._lifetimes) == 0:
            emitter.emitting = False

    def _spawn(self, emitter: Any, delta: float, burst: bool = False) -> None:
        # Эмиссия частиц с равномерной скоростью.
        capacity = max(0, min(10000, int(emitter.amount)))
        rate = capacity / max(emitter.lifetime, 0.05)
        emitter._spawn_acc += rate * delta
        requested = int(emitter._spawn_acc)
        emitter._spawn_acc -= requested
        count = min(capacity - len(emitter._lifetimes), capacity if burst else requested)

        if count <= 0:
            return

        origin = emitter.get_global_position()
        half_spread = math.radians(emitter.spread / 2.0)
        base_angle = math.radians(-emitter.rotation)

        positions = np.zeros((count, 2), dtype=float)
        velocities = np.zeros((count, 2), dtype=float)
        lifetimes = np.zeros(count, dtype=float)
        max_lifetimes = np.zeros(count, dtype=float)

        for i in range(count):
            angle = base_angle + random.uniform(-half_spread, half_spread)
            speed = emitter.speed * random.uniform(0.2, 1.0)
            positions[i] = [origin.x, origin.y]
            velocities[i] = [math.cos(angle) * speed, math.sin(angle) * speed]
            max_lifetimes[i] = emitter.lifetime * random.uniform(0.5, 1.0)

        emitter._positions = np.vstack([emitter._positions, positions])
        emitter._velocities = np.vstack([emitter._velocities, velocities])
        emitter._lifetimes = np.concatenate([emitter._lifetimes, lifetimes])
        emitter._max_lifetimes = np.concatenate(
            [emitter._max_lifetimes, max_lifetimes])
