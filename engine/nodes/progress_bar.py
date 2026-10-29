"""ProgressBar — полоса прогресса UI (аналог Godot ProgressBar)."""

from __future__ import annotations

import logging
from typing import Any

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.progress_bar")


class ProgressBar(Node2D):
    """Полоса прогресса со значением от min до max."""

    exported_properties = {
        "min_value": {"type": "float", "default": 0.0, "min": -100000.0, "max": 100000.0, "step": 1.0},
        "max_value": {"type": "float", "default": 100.0, "min": -100000.0, "max": 100000.0, "step": 1.0},
        "value": {"type": "float", "default": 0.0, "min": -100000.0, "max": 100000.0, "step": 1.0},
        "size": {"type": "vector2", "default": [200.0, 20.0]},
        "fill_color": {"type": "color", "default": [71, 140, 191, 255]},
        "bg_color": {"type": "color", "default": [40, 40, 45, 255]},
        "show_percentage": {"type": "bool", "default": False},
        "anchor_left": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
        "anchor_top": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
    }

    def __init__(self, name: str = "ProgressBar") -> None:
        super().__init__(name)
        self.min_value: float = 0.0
        self.max_value: float = 100.0
        self.value: float = 0.0
        self.size: Vector2 = Vector2(200.0, 20.0)
        self.fill_color: tuple = (71, 140, 191, 255)
        self.bg_color: tuple = (40, 40, 45, 255)
        self.show_percentage: bool = False
        self.anchor_left: float = 0.0
        self.anchor_top: float = 0.0
        self._asset_manager: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager

    def get_ratio(self) -> float:
        if self.max_value == self.min_value:
            return 0.0
        return max(0.0, min(1.0, (self.value - self.min_value) / (self.max_value - self.min_value)))

    def set_value(self, value: float) -> None:
        self.value = max(self.min_value, min(self.max_value, value))

    def get_ui_position(self, screen_size: Vector2) -> Vector2:
        transform = self.get_component('RectTransform')
        if transform and transform.enabled:
            position, size = transform.resolve(screen_size)
            if hasattr(self, 'size'):
                self.size = size
            return position
        return Vector2(self.position.x + screen_size.x * self.anchor_left,
                       self.position.y + screen_size.y * self.anchor_top)

    def draw_ui(self, surface: Any, screen_size: Vector2) -> None:
        try:
            import pygame
        except Exception:
            return
        pos = self.get_ui_position(screen_size)
        rect = pygame.Rect(int(pos.x), int(pos.y), int(self.size.x), int(self.size.y))
        pygame.draw.rect(surface, self.bg_color, rect, 0, border_radius=3)
        ratio = self.get_ratio()
        fill_w = int(self.size.x * ratio)
        if fill_w > 0:
            fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.height)
            pygame.draw.rect(surface, self.fill_color, fill_rect, 0, border_radius=3)
        pygame.draw.rect(surface, (150, 150, 160, 255), rect, 1, border_radius=3)

        if self.show_percentage:
            if self._asset_manager is not None:
                font = self._asset_manager.get_font("", max(10, int(self.size.y) - 4))
            else:
                font = pygame.font.Font(None, max(10, int(self.size.y) - 4))
            text = font.render(f"{int(ratio * 100)}%", True, (255, 255, 255))
            surface.blit(text, text.get_rect(center=rect.center))
