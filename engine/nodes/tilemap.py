"""TileMap — тайловая карта (аналог Godot TileMap).

Сетка тайлов фиксированного размера. Каждый тайл имеет id текстуры и флаг
коллизии. Поддерживаются простые автотайлы (один набор текстур) и
отрисовка только видимых тайлов.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.tilemap")


class TileMap(Node2D):
    """Сетка тайлов с текстурами и коллизиями."""

    exported_properties = {
        "cell_size": {"type": "vector2", "default": [32.0, 32.0]},
        "tile_texture": {"type": "resource", "default": ""},
        "tile_columns": {"type": "int", "default": 1, "min": 1, "max": 64},
        "tile_rows": {"type": "int", "default": 1, "min": 1, "max": 64},
    }

    def __init__(self, name: str = "TileMap") -> None:
        super().__init__(name)
        self.cell_size: Vector2 = Vector2(32.0, 32.0)
        self.tile_texture: str = ""
        self.tile_columns: int = 1
        self.tile_rows: int = 1

        #: Сетка: {(cx, cy): {"id": int, "collision": bool, "flip": bool}}
        self.cells: Dict[Tuple[int, int], Dict[str, Any]] = {}
        #: Набор тайлов: id -> Surface (кэш нарезанных тайлов).
        self._tiles: Dict[int, Any] = {}
        self._asset_manager: Any = None
        self.tile_collisions = {}
        self.tile_sources = {}
        self._collision_body = None

    # ------------------------------------------------------------------
    # Управление тайлами
    # ------------------------------------------------------------------
    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager
        self._rebuild_tiles()

    def _rebuild_tiles(self) -> None:
        """Нарезает спрайтшит на отдельные тайлы."""
        self._tiles.clear()
        if self._asset_manager is not None and self.tile_sources:
            for key, path in self.tile_sources.items():
                texture = self._asset_manager.get_texture(path)
                if texture is not None:
                    self._tiles[int(key)] = texture
            return
        if not self.tile_texture or self._asset_manager is None:
            return
        sheet = self._asset_manager.get_texture(self.tile_texture)
        if sheet is None:
            return
        tw = sheet.get_width() // max(self.tile_columns, 1)
        th = sheet.get_height() // max(self.tile_rows, 1)
        idx = 0
        for row in range(self.tile_rows):
            for col in range(self.tile_columns):
                try:
                    self._tiles[idx] = sheet.subsurface((col * tw, row * th, tw, th))
                except Exception:
                    pass
                idx += 1

    def set_cell(self, cx: int, cy: int, tile_id: int = -1,
                 collision: bool = False, flip: bool = False) -> None:
        """Устанавливает тайл в ячейку (tile_id < 0 — очистить)."""
        if tile_id < 0:
            self.cells.pop((cx, cy), None)
        else:
            self.cells[(cx, cy)] = {"id": tile_id, "collision": collision,
                                    "flip": flip}

    def get_cell(self, cx: int, cy: int) -> Optional[Dict[str, Any]]:
        return self.cells.get((cx, cy))

    def clear(self) -> None:
        self.cells.clear()

    # ------------------------------------------------------------------
    # Рисование (используется инструментами редактора)
    # ------------------------------------------------------------------
    def has_tileset(self) -> bool:
        """Есть ли нарезанные тайлы (задана текстура набора)."""
        return bool(self._tiles)

    def tile_ids(self) -> List[int]:
        """Доступные идентификаторы тайлов."""
        return sorted(self._tiles.keys())

    def cell_count(self) -> int:
        """Сколько ячеек закрашено."""
        return len(self.cells)

    def paint(self, cx: int, cy: int, tile_id: int = 0,
              collision: bool = False) -> bool:
        """Красит одну ячейку. Возвращает True, если что-то изменилось."""
        if tile_id < 0:
            if (cx, cy) not in self.cells:
                return False
            self.cells.pop((cx, cy), None)
            return True
        current = self.cells.get((cx, cy))
        data = {"id": int(tile_id), "collision": bool(collision), "flip": False}
        if current == data:
            return False
        self.cells[(cx, cy)] = data
        return True

    def paint_rect(self, cx1: int, cy1: int, cx2: int, cy2: int,
                   tile_id: int = 0, collision: bool = False) -> bool:
        """Красит прямоугольную область (включительно по обеим границам)."""
        left, right = sorted((int(cx1), int(cx2)))
        top, bottom = sorted((int(cy1), int(cy2)))
        changed = False
        for cy in range(top, bottom + 1):
            for cx in range(left, right + 1):
                if self.paint(cx, cy, tile_id, collision):
                    changed = True
        return changed

    def flood_fill(self, cx: int, cy: int, tile_id: int = 0,
                   collision: bool = False, limit: int = 20000,
                   bounds: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """Заливает связную область одинаковых ячеек (как ведро в редакторе).

        Заливка ограничена рамкой уже нарисованных тайлов (с запасом в одну
        ячейку) — иначе по пустой карте она растекалась бы бесконечно.
        """
        start = self.cells.get((cx, cy))
        start_id = start.get("id") if start else None
        start_collision = bool(start.get("collision")) if start else False
        target_id = tile_id if tile_id >= 0 else None
        if start_id == target_id and start_collision == bool(collision):
            return False

        if bounds is None:
            bounds = self._fill_bounds(int(cx), int(cy))
        left, top, right, bottom = bounds
        # Ячейка, по которой щёлкнули, всегда входит в область заливки.
        left = min(left, int(cx))
        top = min(top, int(cy))
        right = max(right, int(cx))
        bottom = max(bottom, int(cy))

        stack = [(int(cx), int(cy))]
        visited = set()
        changed = False
        while stack and len(visited) < limit:
            current = stack.pop()
            if current in visited:
                continue
            if not (left <= current[0] <= right and top <= current[1] <= bottom):
                continue
            visited.add(current)
            cell = self.cells.get(current)
            cell_id = cell.get("id") if cell else None
            cell_collision = bool(cell.get("collision")) if cell else False
            if cell_id != start_id or cell_collision != start_collision:
                continue
            if self.paint(current[0], current[1], tile_id, collision):
                changed = True
            stack.append((current[0] + 1, current[1]))
            stack.append((current[0] - 1, current[1]))
            stack.append((current[0], current[1] + 1))
            stack.append((current[0], current[1] - 1))
        return changed

    def _fill_bounds(self, cx: int, cy: int) -> Tuple[int, int, int, int]:
        """Границы заливки: рамка нарисованного с запасом в одну ячейку."""
        if not self.cells:
            half = 16
            return (cx - half, cy - half, cx + half, cy + half)
        xs = [key[0] for key in self.cells]
        ys = [key[1] for key in self.cells]
        return (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)

    def snapshot(self) -> Dict[str, Any]:
        """Копия всех ячеек (для отмены действий в редакторе)."""
        return {key: dict(value) for key, value in self.cells.items()}

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """Возвращает состояние ячеек из снимка."""
        self.cells = {tuple(key) if isinstance(key, tuple) else key: dict(value)
                      for key, value in (snapshot or {}).items()}

    def world_to_cell(self, world: Vector2) -> Tuple[int, int]:
        local = self.global_to_local(world)
        return (int(local.x // self.cell_size.x), int(local.y // self.cell_size.y))

    def cell_to_world(self, cx: int, cy: int) -> Vector2:
        return self.local_to_global(Vector2(cx * self.cell_size.x, cy * self.cell_size.y))

    # ------------------------------------------------------------------
    # Коллизии
    # ------------------------------------------------------------------
    def get_solid_cells(self) -> List[Tuple[int, int, Vector2]]:
        """Список твёрдых ячеек: (cx, cy, мировые координаты центра)."""
        result = []
        for (cx, cy), data in self.cells.items():
            if data.get("collision"):
                center = self.local_to_global(Vector2((cx + 0.5) * self.cell_size.x, (cy + 0.5) * self.cell_size.y))
                result.append((cx, cy, center))
        return result

    def physics_body(self):
        from engine.nodes.staticbody2d import StaticBody2D
        from engine.nodes.collision_shape import CollisionShape2D
        if self._collision_body is None:
            self._collision_body = StaticBody2D(self.name + '_tiles')
            self._collision_body.parent = self
        body = self._collision_body
        settings = self.get_component('TileMapCollider2D')
        if settings is not None:
            if not settings.enabled:
                return None
            body.collision_layer = settings.collision_layer
            body.collision_mask = settings.collision_mask
            body.light_occluder = settings.light_occluder
        else:
            body.collision_layer = body.collision_mask = 1
            body.light_occluder = True
        signature = (self.cell_size.x, self.cell_size.y,
                     tuple(sorted(k for k, v in self.cells.items() if v.get('collision'))))
        if getattr(body, '_tile_signature', None) != signature:
            for child in body.get_children():
                body.remove_child(child)
            for cx, cy in signature[2]:
                shape = CollisionShape2D()
                shape.size = Vector2(self.cell_size)
                shape.position = Vector2((cx + .5)*self.cell_size.x, (cy + .5)*self.cell_size.y)
                body.add_child(shape)
            body._tile_signature = signature
        return body if signature[2] else None

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        if not self.cells:
            return
        try:
            import pygame
            for (cx, cy), data in self.cells.items():
                tile_id = data.get("id", 0)
                surf = self._tiles.get(tile_id)
                transform = self.get_global_transform()
                zoom = float(getattr(camera, 'zoom', 1.0)) if camera else 1.0
                world = self.local_to_global(Vector2((cx+.5)*self.cell_size.x, (cy+.5)*self.cell_size.y))
                screen = self.world_to_screen(world, camera)
                width = max(1, round(abs(self.cell_size.x * transform.scale.x * zoom)))
                height = max(1, round(abs(self.cell_size.y * transform.scale.y * zoom)))
                if surf is None:
                    surf = pygame.Surface((width, height), pygame.SRCALPHA)
                    surf.fill((90, 90, 110, 255) if data.get('collision') else (60, 60, 80, 255))
                else:
                    surf = pygame.transform.scale(surf, (width, height))
                tint = self.get_component('TileMapTint')
                if tint and tint.enabled:
                    surf = surf.copy()
                    surf.fill(tuple(tint.color), special_flags=pygame.BLEND_RGBA_MULT)
                flip_x = bool(data.get('flip')) != (transform.scale.x < 0)
                if flip_x or transform.scale.y < 0:
                    surf = pygame.transform.flip(surf, flip_x, transform.scale.y < 0)
                if transform.rotation:
                    import math
                    surf = pygame.transform.rotate(surf, -math.degrees(transform.rotation))
                rect = surf.get_rect(center=screen.as_ints())
                if surface.get_rect().colliderect(rect):
                    surface.blit(surf, rect)
        except Exception:
            logger.exception("TileMap rendering failed")

    # ------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------
    def _serialize_data(self) -> dict:
        cells = {}
        for (cx, cy), data in self.cells.items():
            cells[f"{cx},{cy}"] = data
        return {"cells": cells, "tile_collisions": self.tile_collisions, "tile_sources": self.tile_sources}

    def _deserialize_data(self, data: dict) -> None:
        self.tile_collisions = {int(k): bool(v) for k, v in data.get('tile_collisions', {}).items()}
        self.tile_sources = {int(k): str(v) for k, v in data.get('tile_sources', {}).items()}
        self.cells = {}
        self._rebuild_tiles()
        for key, value in data.get("cells", {}).items():
            try:
                cx, cy = key.split(",")
                self.cells[(int(cx), int(cy))] = dict(value)
            except Exception:
                continue
