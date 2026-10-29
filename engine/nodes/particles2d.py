"""Particles2D — CPU-эмиттер частиц (аналог GPUParticles2D на CPU).

Параметры эмиссии: количество, время жизни, скорость, угол, гравитация,
размер и цвет частиц. Обновление выполняется ParticleSystem.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, List, Optional

import numpy as np

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.particles")


class Particles2D(Node2D):
    """Эмиттер частиц."""

    exported_properties = {
        "emitting": {"type": "bool", "default": True},
        "amount": {"type": "int", "default": 64, "min": 1, "max": 10000},
        "lifetime": {"type": "float", "default": 1.0, "min": 0.05, "max": 30.0, "step": 0.05},
        "speed": {"type": "float", "default": 100.0, "min": 0.0, "max": 10000.0, "step": 1.0},
        "spread": {"type": "float", "default": 45.0, "min": 0.0, "max": 360.0, "step": 1.0},
        "gravity": {"type": "vector2", "default": [0.0, 200.0]},
        "particle_size": {"type": "float", "default": 3.0, "min": 0.5, "max": 100.0, "step": 0.5},
        "color": {"type": "color", "default": [255, 255, 255, 255]},
        "end_color": {"type": "color", "default": [255, 255, 255, 0]},
        "end_size_ratio": {"type": "float", "default": 0.2, "min": 0.0, "max": 5.0, "step": 0.05},
        "one_shot": {"type": "bool", "default": False},
        "texture_path": {"type": "resource", "default": ""},
    }

    def __init__(self, name: str = "Particles2D") -> None:
        super().__init__(name)
        self.emitting: bool = True
        self.amount: int = 64
        self.lifetime: float = 1.0
        self.speed: float = 100.0
        self.spread: float = 45.0
        self.gravity: Vector2 = Vector2(0.0, 200.0)
        self.particle_size: float = 3.0
        self.color: tuple = (255, 255, 255, 255)
        self.end_color: tuple = (255, 255, 255, 0)
        self.end_size_ratio = 0.2
        self.one_shot: bool = False
        self.texture_path: str = ""

        # Массивы частиц (numpy).
        self._positions: np.ndarray = np.zeros((0, 2), dtype=float)
        self._velocities: np.ndarray = np.zeros((0, 2), dtype=float)
        self._lifetimes: np.ndarray = np.zeros(0, dtype=float)
        self._max_lifetimes: np.ndarray = np.zeros(0, dtype=float)
        self._spawn_acc: float = 0.0
        self._burst_emitted = False
        self._texture: Any = None
        self._asset_manager: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager
        self._texture = manager.get_texture(self.texture_path) if self.texture_path else None

    def particle_style(self, index):
        progress = max(0.0, min(1.0, float(self._lifetimes[index] / max(self._max_lifetimes[index], 1e-6))))
        color = tuple(max(0, min(255, int(a + (b-a)*progress))) for a, b in zip(self.color, self.end_color))
        size = self.particle_size * (1 + (self.end_size_ratio-1)*progress)
        return color, max(0.0, size)

    def restart(self) -> None:
        """Перезапускает эмиттер."""
        self._positions = np.zeros((0, 2), dtype=float)
        self._velocities = np.zeros((0, 2), dtype=float)
        self._lifetimes = np.zeros(0, dtype=float)
        self._max_lifetimes = np.zeros(0, dtype=float)
        self._spawn_acc = 0.0
        self._burst_emitted = False
        self.emitting = True

    def get_particle_count(self) -> int:
        return int(len(self._lifetimes))

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        try:
            import pygame
            for i in range(len(self._positions)):
                color, radius = self.particle_style(i)
                world = Vector2(float(self._positions[i, 0]), float(self._positions[i, 1]))
                screen = self.world_to_screen(world, camera)
                if radius <= 0 or color[3] <= 0:
                    continue
                size = max(1, int(radius * max(0.001, getattr(camera, 'zoom', 1))))
                if self._texture is not None:
                    scaled = pygame.transform.scale(self._texture, (size*2, size*2)).copy()
                    scaled.fill(color, special_flags=pygame.BLEND_RGBA_MULT)
                    surface.blit(scaled, (int(screen.x)-size, int(screen.y)-size))
                else:
                    stamp = pygame.Surface((size*2+2, size*2+2), pygame.SRCALPHA)
                    pygame.draw.circle(stamp, color, (size+1, size+1), size)
                    surface.blit(stamp, (int(screen.x)-size-1, int(screen.y)-size-1))
        except Exception:
            logger.exception('Не удалось отрисовать частицы %s', self.name)

    def _serialize_data(self) -> dict:
        return {}
