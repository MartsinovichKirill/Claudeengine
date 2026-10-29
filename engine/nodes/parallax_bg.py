"""ParallaxBackground / ParallaxLayer — параллакс-фон.

Фоновые слои двигаются с разной скоростью относительно камеры, создавая
эффект глубины. ParallaxLayer — дочерний слой с текстурой и motion_scale.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.parallax")


class ParallaxLayer(Node2D):
    """Один слой параллакса с текстурой."""

    exported_properties = {
        "motion_scale": {"type": "vector2", "default": [0.2, 0.2]},
        "texture_path": {"type": "resource", "default": ""},
        "mirroring": {"type": "vector2", "default": [0.0, 0.0]},
        "scroll_offset": {"type": "vector2", "default": [0.0, 0.0]},
    }

    def __init__(self, name: str = "ParallaxLayer") -> None:
        super().__init__(name)
        self.motion_scale: Vector2 = Vector2(0.2, 0.2)
        self.texture_path: str = ""
        self.mirroring: Vector2 = Vector2()
        self.scroll_offset: Vector2 = Vector2()
        self._texture: Any = None
        self._asset_manager: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager
        if not self.texture_path:
            self._texture = None
            return
        # Если файла нет — слой НЕ рисуем: иначе цветная заглушка
        # замостит весь экран и скроет всю сцену.
        try:
            exists = manager.exists(self.texture_path)
        except Exception:
            exists = False
        if not exists:
            logger.info("ParallaxLayer '%s': пропуск отсутствующей текстуры %s",
                        self.name, self.texture_path)
            self._texture = None
            return
        self._texture = manager.get_texture(self.texture_path)


class ParallaxBackground(Node2D):
    """Контейнер параллакс-слоёв. Отрисовывает дочерние ParallaxLayer."""

    exported_properties = {
        "scroll_ignore_camera": {"type": "bool", "default": True},
        "scroll_scale": {"type": "vector2", "default": [1.0, 1.0]},
    }

    def __init__(self, name: str = "ParallaxBackground") -> None:
        super().__init__(name)
        self.scroll_ignore_camera: bool = True
        self.scroll_scale: Vector2 = Vector2(1.0, 1.0)

    def get_layers(self) -> list:
        return [c for c in self._children if isinstance(c, ParallaxLayer)]

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        try:
            import pygame  # noqa: F401
        except Exception:
            return

        camera_center = Vector2()
        if camera is not None and hasattr(camera, "get_center"):
            camera_center = camera.get_center()
        screen_size = Vector2(surface.get_width(), surface.get_height())

        for layer in self.get_layers():
            if layer._texture is None:
                continue
            tex = layer._texture
            # Смещение слоя относительно камеры.
            offset = camera_center * layer.motion_scale + layer.scroll_offset
            tw, th = tex.get_width(), tex.get_height()
            if tw <= 0 or th <= 0:
                continue
            start_x = int(-_mod(offset.x, tw)) - tw
            start_y = int(-_mod(offset.y, th)) - th
            y = start_y
            while y < screen_size.y:
                x = start_x
                while x < screen_size.x:
                    surface.blit(tex, (x, y))
                    x += tw
                y += th


def _mod(a: float, b: float) -> float:
    return a % b if b != 0 else a
