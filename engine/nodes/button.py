"""Button — кнопка UI (аналог Godot Button).

Имеет состояния hover/pressed, текст и сигнал pressed. Обработка кликов
выполняется UISystem; кнопка лишь описывает внешний вид и хранит состояние.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.button")


class Button(Node2D):
    """Кнопка с текстом, состояниями и сигналом pressed."""

    exported_properties = {
        "font_path": {"type":"resource","default":""},
        "texture_normal": {"type":"resource","default":""},
        "texture_hover": {"type":"resource","default":""},
        "texture_pressed": {"type":"resource","default":""},
        "text": {"type": "string", "default": "Button"},
        "font_size": {"type": "int", "default": 16, "min": 6, "max": 256},
        "size": {"type": "vector2", "default": [120.0, 40.0]},
        "disabled": {"type": "bool", "default": False},
        "toggle_mode": {"type": "bool", "default": False},
        "button_pressed": {"type": "bool", "default": False},
        "font_color": {"type": "color", "default": [255, 255, 255, 255]},
        "bg_color": {"type": "color", "default": [70, 70, 80, 255]},
        "hover_color": {"type": "color", "default": [90, 90, 105, 255]},
        "pressed_color": {"type": "color", "default": [120, 120, 140, 255]},
        "anchor_left": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
        "anchor_top": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
    }

    signals = ["pressed", "button_down", "button_up", "mouse_entered", "mouse_exited"]

    def __init__(self, name: str = "Button") -> None:
        super().__init__(name)
        self.font_path = ""
        self.texture_normal = ""
        self.texture_hover = ""
        self.texture_pressed = ""
        self.text: str = "Button"
        self.font_size: int = 16
        self.size: Vector2 = Vector2(120.0, 40.0)
        self.disabled: bool = False
        self.toggle_mode: bool = False
        self.button_pressed: bool = False
        self.font_color: tuple = (255, 255, 255, 255)
        self.bg_color: tuple = (70, 70, 80, 255)
        self.hover_color: tuple = (90, 90, 105, 255)
        self.pressed_color: tuple = (120, 120, 140, 255)
        self.anchor_left: float = 0.0
        self.anchor_top: float = 0.0

        self.hovered: bool = False
        self._is_down: bool = False
        self._asset_manager: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager

    def get_ui_position(self, screen_size: Vector2) -> Vector2:
        transform = self.get_component('RectTransform')
        if transform and transform.enabled:
            position, size = transform.resolve(screen_size)
            if hasattr(self, 'size'):
                self.size = size
            return position
        return Vector2(self.position.x + screen_size.x * self.anchor_left,
                       self.position.y + screen_size.y * self.anchor_top)

    def get_ui_rect(self, screen_size: Vector2) -> tuple:
        pos = self.get_ui_position(screen_size)
        return (pos.x, pos.y, self.size.x, self.size.y)

    def press(self) -> None:
        """Программное нажатие кнопки (вызывает pressed)."""
        if self.disabled:
            return
        if self.toggle_mode:
            self.button_pressed = not self.button_pressed
        else:
            self.button_pressed = True
        self.emit_signal("pressed")

    def draw_ui(self, surface: Any, screen_size: Vector2) -> None:
        try:
            import pygame
        except Exception:
            return
        pos = self.get_ui_position(screen_size)
        rect = pygame.Rect(int(pos.x), int(pos.y), int(self.size.x), int(self.size.y))

        if self.disabled:
            color = (50, 50, 55, 200)
        elif self._is_down or self.button_pressed:
            color = self.pressed_color
        elif self.hovered:
            color = self.hover_color
        else:
            color = self.bg_color

        pygame.draw.rect(surface, color, rect, 0, border_radius=4)
        pygame.draw.rect(surface, (150, 150, 160, 255), rect, 1, border_radius=4)

        path = self.texture_normal
        if not self.disabled:
            if self._is_down or self.button_pressed:
                path = self.texture_pressed or path
            elif self.hovered:
                path = self.texture_hover or path
        if path and self._asset_manager is not None:
            texture = self._asset_manager.get_texture(path)
            if texture is not None and rect.width>0 and rect.height>0:
                surface.blit(pygame.transform.smoothscale(texture,rect.size),rect)

        # Текст.
        if self._asset_manager is not None:
            font = self._asset_manager.get_font(self.font_path, self.font_size)
        else:
            font = pygame.font.Font(None, self.font_size)
        rendered = font.render(self.text, True, self.font_color[:3])
        text_rect = rendered.get_rect(center=rect.center)
        surface.blit(rendered, text_rect)
