"""CanvasLayer / TextureRect — UI-слой и изображение в UI.

CanvasLayer рисуется поверх мира и не двигается с камерой. Дочерние
UI-ноды (Label, Button, ProgressBar, TextureRect) позиционируются в
экранных координатах.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.canvas_layer")


class CanvasLayer(Node):
    """Отдельный слой UI, не зависящий от камеры."""

    exported_properties = {
        "layer": {"type": "int", "default": 1, "min": -128, "max": 128},
        "offset": {"type": "vector2", "default": [0.0, 0.0]},
        "scale": {"type": "vector2", "default": [1.0, 1.0]},
        "visible": {"type": "bool", "default": True},
    }

    def __init__(self, name: str = "CanvasLayer") -> None:
        super().__init__(name)
        self.layer: int = 1
        self.offset: Vector2 = Vector2()
        self.scale: Vector2 = Vector2(1, 1)
        self.visible: bool = True


class TextureRect(Node2D):
    """Изображение в UI (рисуется в экранных координатах)."""

    exported_properties = {
        "texture_path": {"type": "resource", "default": ""},
        "expand_mode": {"type": "enum", "default": "keep_size",
                        "options": ["keep_size", "stretch"]},
        "size": {"type": "vector2", "default": [64.0, 64.0]},
        "anchor_left": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
        "anchor_top": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
        "anchor_right": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
        "anchor_bottom": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
    }

    def __init__(self, name: str = "TextureRect") -> None:
        super().__init__(name)
        self.texture_path: str = ""
        self.expand_mode: str = "keep_size"
        self.size: Vector2 = Vector2(64.0, 64.0)
        self.anchor_left: float = 0.0
        self.anchor_top: float = 0.0
        self.anchor_right: float = 0.0
        self.anchor_bottom: float = 0.0
        self._texture: Any = None
        self._asset_manager: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager
        if self.texture_path:
            self._texture = manager.get_texture(self.texture_path)

    def get_ui_position(self, screen_size: Vector2) -> Vector2:
        """Позиция с учётом anchor (доля экрана)."""
        transform = self.get_component('RectTransform')
        if transform and transform.enabled:
            position, size = transform.resolve(screen_size)
            if hasattr(self, 'size'):
                self.size = size
            return position
        return Vector2(self.position.x + screen_size.x * self.anchor_left,
                       self.position.y + screen_size.y * self.anchor_top)

    def draw_ui(self, surface: Any, screen_size: Vector2) -> None:
        """Отрисовка в UI-пространстве (вызывается UISystem)."""
        if self._texture is None:
            return
        try:
            import pygame
            pos = self.get_ui_position(screen_size)
            tex = self._texture
            if self.expand_mode == "stretch":
                tex = pygame.transform.scale(tex, (max(1, int(self.size.x)),
                                                   max(1, int(self.size.y))))
            surface.blit(tex, pos.as_ints())
        except Exception:
            pass
