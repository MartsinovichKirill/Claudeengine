"""Label — текстовый UI-элемент (аналог Godot Label)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.label")


class Label(Node2D):
    """Выводит текст в UI (CanvasLayer) или в мире."""

    exported_properties = {
        "text": {"type": "string", "default": "Label"},
        "font_path": {"type": "resource", "default": ""},
        "font_size": {"type": "int", "default": 16, "min": 6, "max": 256},
        "color": {"type": "color", "default": [255, 255, 255, 255]},
        "align": {"type": "enum", "default": "left",
                  "options": ["left", "center", "right"]},
        "anchor_left": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
        "anchor_top": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
    }

    def __init__(self, name: str = "Label") -> None:
        super().__init__(name)
        self.text: str = "Label"
        self.font_path: str = ""
        self.font_size: int = 16
        self.color: tuple = (255, 255, 255, 255)
        self.align: str = "left"
        self.anchor_left: float = 0.0
        self.anchor_top: float = 0.0
        self._asset_manager: Any = None
        self._font: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager

    def _get_font(self) -> Any:
        if self._asset_manager is None:
            try:
                import pygame
                return pygame.font.Font(None, self.font_size)
            except Exception:
                return None
        return self._asset_manager.get_font(self.font_path, self.font_size)

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
        """Отрисовка в UI-пространстве."""
        font = self._get_font()
        if font is None:
            return
        try:
            pos = self.get_ui_position(screen_size)
            lines = self.text.split("\n")
            for i, line in enumerate(lines):
                rendered = font.render(line, True, self.color[:3])
                if len(self.color) > 3 and self.color[3] < 255:
                    rendered.set_alpha(self.color[3])
                rect = rendered.get_rect()
                if self.align == "center":
                    rect.midtop = (int(pos.x), int(pos.y) + i * self.font_size)
                elif self.align == "right":
                    rect.topright = (int(pos.x), int(pos.y) + i * self.font_size)
                else:
                    rect.topleft = (int(pos.x), int(pos.y) + i * self.font_size)
                surface.blit(rendered, rect)
        except Exception:
            pass

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        """Отрисовка в мировых координатах (если не под CanvasLayer)."""
        if self.parent is not None and hasattr(self.parent, "layer"):
            return  # под CanvasLayer рисуется через UISystem
        font = self._get_font()
        if font is None:
            return
        try:
            rendered = font.render(self.text, True, self.color[:3])
            surface.blit(rendered, center.as_ints())
        except Exception:
            pass
