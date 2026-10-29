"""Sprite2D — спрайт (аналог Godot Sprite2D).

Поддерживает PNG/JPG, modulate, flip_h/flip_v, offset, центрирование,
поворот и масштаб.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

WHITE = (255, 255, 255, 255)


class Sprite2D(Node2D):
    """Отрисовывает текстуру (Surface pygame)."""

    exported_properties = {
        "hframes": {"type": "int", "default": 1},
        "vframes": {"type": "int", "default": 1},
        "frame": {"type": "int", "default": 0},
        "pixel_art": {"type": "bool", "default": True},
        "texture_path": {"type": "resource", "default": ""},
        "normal_map": {"type": "resource", "default": ""},
        "centered": {"type": "bool", "default": True},
        "offset": {"type": "vector2", "default": [0.0, 0.0]},
        "flip_h": {"type": "bool", "default": False},
        "flip_v": {"type": "bool", "default": False},
        "blend_mode": {"type": "enum", "default": "normal",
                       "options": ["normal", "add", "subtract", "multiply"]},
    }

    def __init__(self, name: str = "Sprite2D") -> None:
        super().__init__(name)
        self._component_body = None
        self.hframes = 1
        self.vframes = 1
        self.frame = 0
        self.pixel_art = True
        self._transform_cache = {}
        self.texture_path: str = ""
        self.texture: Any = None            # pygame.Surface
        #: Карта нормалей для освещения (Light2D считает по ней объём).
        self.normal_map: str = ""
        self.normal_texture: Any = None
        self.centered: bool = True
        self.offset: Vector2 = Vector2()
        self.flip_h: bool = False
        self.flip_v: bool = False
        self.blend_mode: str = "normal"
        self._asset_manager: Any = None
        self._tint_cache: dict = {}

    # ------------------------------------------------------------------
    # Управление текстурой
    # ------------------------------------------------------------------
    def set_texture(self, texture: Any) -> None:
        """Устанавливает текстуру напрямую (Surface)."""
        self.texture = texture
        self._transform_cache.clear()
        self._tint_cache.clear()

    def set_texture_path(self, path: str) -> None:
        """Устанавливает текстуру по пути через AssetManager."""
        self.texture_path = path
        self._transform_cache.clear()
        self._tint_cache.clear()
        self.texture = None
        if self._asset_manager is not None and path:
            self.texture = self._asset_manager.get_texture(path)

    def get_collision_shapes(self):
        from engine.nodes.game_object import GameObject
        return GameObject.get_collision_shapes(self)

    def physics_body(self):
        from engine.nodes.game_object import GameObject
        return GameObject.physics_body(self)

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager
        if self.texture_path:
            self.texture = manager.get_texture(self.texture_path)
        if self.normal_map:
            self.normal_texture = self._load_normal(self.normal_map)

    def _load_normal(self, path: str) -> Any:
        """Загружает карту нормалей (без заглушки — она исказила бы свет)."""
        if self._asset_manager is None or not path:
            return None
        try:
            if not self._asset_manager.exists(path):
                return None
            return self._asset_manager.get_texture(path)
        except Exception:
            return None

    def set_normal_map(self, path: str) -> None:
        """Задаёт путь к карте нормалей и сразу загружает её."""
        self.normal_map = path
        self.normal_texture = self._load_normal(path)

    def get_texture_rect(self) -> Optional[Any]:
        """Прямоугольник текстуры (pygame.Rect) или None."""
        if self.texture is None:
            return None
        return self.texture.get_rect()

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def _get_draw_surface(self, camera: Any) -> Tuple[Any, float]:
        """Подготавливает поверхность с учётом modulate/flip/поворота/масштаба."""
        if self.texture is None:
            return None, 1.0

        surf = self.texture
        columns, rows = max(1, self.hframes), max(1, self.vframes)
        index = max(0, min(self.frame, columns * rows - 1))
        transform = self.get_global_transform()
        scale = transform.scale
        rotation = math.degrees(transform.rotation)
        zoom_value = getattr(camera, "zoom", 1.0)
        zoom_value = zoom_value.x if isinstance(zoom_value, Vector2) else zoom_value
        cache_key = (id(surf), tuple(self.modulate), self.flip_h, self.flip_v,
                     scale.x, scale.y, rotation, zoom_value,
                     columns, rows, index, self.pixel_art)
        if cache_key in self._transform_cache:
            return self._transform_cache[cache_key]
        if columns > 1 or rows > 1:
            width, height = surf.get_width() // columns, surf.get_height() // rows
            if width < 1 or height < 1:
                return None, 1.0
            surf = surf.subsurface((index % columns * width, index // columns * height, width, height))
        # modulate.
        if self.modulate != WHITE:
            key = (id(self.texture), columns, rows, index, tuple(self.modulate))
            cached = self._tint_cache.get(key)
            if cached is None:
                cached = surf.copy()
                try:
                    import pygame
                    cached.fill(self.modulate,
                                special_flags=pygame.BLEND_RGBA_MULT)
                except Exception:
                    pass
                if len(self._tint_cache) >= 64: self._tint_cache.clear()
                self._tint_cache[key] = cached
            surf = cached

        # flip.
        if self.flip_h or self.flip_v:
            try:
                import pygame
                surf = pygame.transform.flip(surf, self.flip_h, self.flip_v)
            except Exception:
                pass

        # масштаб + поворот.
        zoom = 1.0
        if camera is not None and hasattr(camera, "zoom"):
            zoom = getattr(camera, "zoom", 1.0)
            if isinstance(zoom, Vector2):
                zoom = zoom.x
        total_scale = max(abs(scale.x * zoom), 0.0001)
        angle = -rotation
        if angle != 0.0 or abs(scale.x * zoom - 1.0) > 1e-6 or abs(scale.y * zoom - 1.0) > 1e-6:
            try:
                import pygame
                size = (max(1, round(surf.get_width() * abs(scale.x * zoom))),
                        max(1, round(surf.get_height() * abs(scale.y * zoom))))
                scaler = pygame.transform.scale if self.pixel_art else pygame.transform.smoothscale
                surf = scaler(surf, size)
                if scale.x < 0 or scale.y < 0:
                    surf = pygame.transform.flip(surf, scale.x < 0, scale.y < 0)
                if angle:
                    surf = pygame.transform.rotate(surf, angle) if self.pixel_art else pygame.transform.rotozoom(surf, angle, 1)

            except Exception:
                pass
        if len(self._transform_cache) >= 64: self._transform_cache.clear()
        self._transform_cache[cache_key] = (surf, total_scale)
        return surf, total_scale

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        if self._asset_manager and self.texture_path and not getattr(self, '_drawing_animation', False):
            self.texture=self._asset_manager.get_texture(self.texture_path)
        if self.texture is None:
            return
        transform = self.get_global_transform()
        zoom = getattr(camera, 'zoom', 1.0)
        zoom = zoom.x if isinstance(zoom, Vector2) else zoom
        # Conservative radius rejects offscreen sprites before creating large
        # rotated/scaled surfaces. Includes non-centered images and offsets.
        width = self.texture.get_width() / max(1, self.hframes)
        height = self.texture.get_height() / max(1, self.vframes)
        radius = math.hypot(width * transform.scale.x, height * transform.scale.y) * abs(zoom)
        offset = transform.xform(self.offset) - transform.origin
        offset *= zoom
        target_center = center + offset
        if target_center.x + radius < 0 or target_center.y + radius < 0 or target_center.x - radius > surface.get_width() or target_center.y - radius > surface.get_height():
            return
        draw_surf, _ = self._get_draw_surface(camera)
        if draw_surf is None:
            return

        rect = draw_surf.get_rect()
        if self.centered:
            topleft = target_center - Vector2(rect.width / 2, rect.height / 2)
        else:
            topleft = target_center

        try:
            import pygame
            if not surface.get_rect().colliderect(draw_surf.get_rect(topleft=(int(topleft.x), int(topleft.y)))):
                return
            if self.blend_mode in ("add", "subtract", "multiply"):
                surface.blit(draw_surf, (int(topleft.x), int(topleft.y)),
                             special_flags={"add": pygame.BLEND_RGBA_ADD, "subtract": pygame.BLEND_RGBA_SUB, "multiply": pygame.BLEND_RGBA_MULT}[self.blend_mode])
            else:
                surface.blit(draw_surf, (int(topleft.x), int(topleft.y)))
        except Exception:
            try:
                surface.blit(draw_surf, (int(topleft.x), int(topleft.y)))
            except Exception:
                pass
