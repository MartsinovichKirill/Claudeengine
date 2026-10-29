"""Light2D и CanvasModulate — освещение 2D-сцены.

Модель освещения повторяет Godot 2D:

* :class:`CanvasModulate` — общий тон сцены. Поставьте тёмно-синий цвет,
  чтобы получилась ночь; тогда свет станет заметен.
* :class:`Light2D` — источник света с цветом, энергией и радиусом.
  Режим ``blend``: ``add`` (свечение, по умолчанию) или ``multiply``
  (подсветка без пересвета).
* :class:`LightOccluder2D` — полигон, отбрасывающий тень.

Тени считаются честно: по углам препятствий строятся лучи и получается
полигон видимости. Препятствиями служат тела с включённым
``light_occluder`` и сами узлы ``LightOccluder2D``.

Нормали: если у спрайта задан ``normal_map``, свет считается попиксельно
по нормалям (numpy) — объект получает объём вместо плоского пятна.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.light2d")


class CanvasModulate(Node2D):
    """Общий тон всей сцены (аналог CanvasModulate в Godot)."""

    type_name = "CanvasModulate"
    description = "Общий цвет и затемнение сцены"

    exported_properties = {
        "color": {"type": "color", "default": [120, 130, 170, 255]},
        "enabled": {"type": "bool", "default": True},
    }

    def __init__(self, name: str = "CanvasModulate") -> None:
        super().__init__(name)
        self.color: Tuple[int, int, int, int] = (120, 130, 170, 255)
        self.enabled: bool = True

    def get_color_rgb(self) -> Tuple[int, int, int]:
        color = tuple(self.color)
        return (int(color[0]), int(color[1]), int(color[2]))

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        """В редакторе показываем только значок — эффект делает система."""
        if not getattr(camera, "editor_mode", False):
            return
        try:
            import pygame
            center = self.world_to_screen(self.get_global_position(), camera)
            radius = int(12 * getattr(camera, "zoom", 1.0))
            color = self.get_color_rgb()
            pygame.draw.circle(surface, color, (int(center.x), int(center.y)),
                               max(radius, 4), 2)
            pygame.draw.line(surface, color, (center.x - radius, center.y),
                             (center.x + radius, center.y), 1)
        except Exception:
            pass


class LightOccluder2D(Node2D):
    """Полигон, отбрасывающий тень от источников света."""

    type_name = "LightOccluder2D"
    description = "Препятствие для света: отбрасывает тень"

    exported_properties = {
        "points": {"type": "points", "default": []},
        "closed": {"type": "bool", "default": True},
        "enabled": {"type": "bool", "default": True},
        "auto_from_shape": {"type": "bool", "default": True},
    }

    def __init__(self, name: str = "LightOccluder2D") -> None:
        super().__init__(name)
        self.points: List[Vector2] = []
        self.closed: bool = True
        self.enabled: bool = True
        #: Если своих точек нет — берём прямоугольник из CollisionShape2D.
        self.auto_from_shape: bool = True

    # ------------------------------------------------------------------
    def world_points(self) -> List[Vector2]:
        """Точки полигона в мировых координатах."""
        if self.points:
            origin = self.get_global_position()
            return [origin + Vector2(point) for point in self.points]
        if self.auto_from_shape:
            for child in self.get_children():
                if type(child).__name__ == "CollisionShape2D":
                    return _shape_corners(child)
        return []

    def segments(self) -> List[Tuple[Vector2, Vector2]]:
        """Отрезки полигона (мировые координаты)."""
        points = self.world_points()
        if len(points) < 2:
            return []
        result: List[Tuple[Vector2, Vector2]] = []
        for index in range(len(points) - 1):
            result.append((points[index], points[index + 1]))
        if self.closed and len(points) > 2:
            result.append((points[-1], points[0]))
        return result

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        if not getattr(camera, "editor_mode", False):
            return
        try:
            import pygame
            points = [self.world_to_screen(point, camera)
                      for point in self.world_points()]
            if len(points) >= 2:
                pygame.draw.polygon(surface, (255, 210, 120),
                                    [(int(p.x), int(p.y)) for p in points], 1)
        except Exception:
            pass


def _shape_corners(shape: Any) -> List[Vector2]:
    """Углы прямоугольной формы столкновения в мировых координатах."""
    try:
        position = shape.get_global_position()
        size = Vector2(getattr(shape, "size", Vector2(32, 32)))
        half = size * 0.5
        return [
            position + Vector2(-half.x, -half.y),
            position + Vector2(half.x, -half.y),
            position + Vector2(half.x, half.y),
            position + Vector2(-half.x, half.y),
        ]
    except Exception:
        return []


class Light2D(Node2D):
    """Источник света с цветом, радиусом и тенями."""

    type_name = "Light2D"
    description = "2D-свет: цвет, энергия, радиус, тени"

    exported_properties = {
        "cone_angle":{"type":"float","default":360.0,"min":1.0,"max":360.0},
        "direction":{"type":"float","default":0.0,"min":-360.0,"max":360.0},
        "color": {"type": "color", "default": [255, 236, 190, 255]},
        "energy": {"type": "float", "default": 1.0, "min": 0.0, "max": 8.0, "step": 0.05},
        "radius": {"type": "float", "default": 220.0, "min": 8.0, "max": 4000.0, "step": 8.0},
        "softness": {"type": "float", "default": 0.55, "min": 0.0, "max": 1.0, "step": 0.02},
        "blend": {"type": "enum", "default": "add", "options": ["add", "multiply"]},
        "shadows": {"type": "bool", "default": False},
        "shadow_softness": {"type":"float","default":2.0,"min":0.0,"max":16.0},
        "shadow_quality": {"type":"enum","default":"medium","options":["low","medium","high"]},
        "enabled": {"type": "bool", "default": True},
        "shows_occluders": {"type": "bool", "default": False},
    }

    def __init__(self, name: str = "Light2D") -> None:
        super().__init__(name)
        self.color: Tuple[int, int, int, int] = (255, 236, 190, 255)
        self.cone_angle=360.0
        self.direction=0.0
        self.energy: float = 1.0
        self.radius: float = 220.0
        self.softness: float = 0.55
        self.blend: str = "add"
        self.shadow_softness=2.0
        self.shadow_quality="medium"
        self.shadows: bool = False
        self.enabled: bool = True
        self.shows_occluders: bool = False
        #: Кэш полигона видимости: ключ -> точки (в локальных координатах).
        self._polygon_cache: Dict[Any, List[Vector2]] = {}

    # ------------------------------------------------------------------
    def get_color_rgb(self) -> Tuple[int, int, int]:
        color = tuple(self.color)
        return (int(color[0]), int(color[1]), int(color[2]))

    def world_center(self) -> Vector2:
        return self.get_global_position()

    def invalidate_cache(self) -> None:
        self._polygon_cache.clear()

    # ------------------------------------------------------------------
    def visibility_polygon(self, segments: List[Tuple[Vector2, Vector2]]) -> List[Vector2]:
        """Полигон видимости света с учётом препятствий.

        Используется классический приём: лучи пускаются в углы препятствий
        (и чуть левее/правее), берётся ближайшее пересечение.
        """
        origin = self.world_center()
        radius = float(self.radius)
        if not segments:
            return []

        key = (round(origin.x, 1), round(origin.y, 1), round(radius, 1),
               tuple((tuple(a),tuple(b)) for a,b in segments))
        cached = self._polygon_cache.get(key)
        if cached is not None:
            return cached

        relevant: List[Tuple[Vector2, Vector2]] = []
        for start, end in segments:
            if _segment_within_circle(start, end, origin, radius * 1.05):
                relevant.append((start, end))
        if not relevant:
            self._polygon_cache = {key: []}
            return []

        angles: List[float] = []
        for start, end in relevant:
            for point in (start, end):
                base = math.atan2(point.y - origin.y, point.x - origin.x)
                angles.append(base - 0.0002)
                angles.append(base)
                angles.append(base + 0.0002)
        angles.sort()

        points: List[Vector2] = []
        for angle in angles:
            direction = Vector2(math.cos(angle), math.sin(angle))
            best: Optional[float] = None
            for start, end in relevant:
                hit = _ray_segment(origin, direction, start, end)
                if hit is not None and (best is None or hit < best):
                    best = hit
            distance = best if best is not None else radius
            points.append(origin + direction * min(distance, radius))

        if len(self._polygon_cache) > 8:
            self._polygon_cache.clear()
        self._polygon_cache[key] = points
        return points

    # ------------------------------------------------------------------
    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        """В редакторе рисуем маркер; в игре свет делает LightSystem."""
        if not getattr(camera, "editor_mode", False):
            return
        try:
            import pygame
            center = self.world_to_screen(self.get_global_position(), camera)
            zoom = getattr(camera, "zoom", 1.0)
            color = self.get_color_rgb()
            pygame.draw.circle(surface, color, (int(center.x), int(center.y)),
                               max(int(5 * zoom), 3), 2)
            pygame.draw.circle(surface, (120, 120, 130),
                               (int(center.x), int(center.y)),
                               max(int(self.radius * zoom), 6), 1)
            pygame.draw.line(surface, color,
                             (center.x - 8 * zoom, center.y),
                             (center.x + 8 * zoom, center.y), 1)
            pygame.draw.line(surface, color,
                             (center.x, center.y - 8 * zoom),
                             (center.x, center.y + 8 * zoom), 1)
        except Exception:
            pass


# ======================================================================
# Геометрия
# ======================================================================
def _segment_within_circle(start: Vector2, end: Vector2, center: Vector2,
                           radius: float) -> bool:
    """Пересекается ли отрезок с окружностью (грубая, но быстрая проверка)."""
    if center.distance_to(start) <= radius or center.distance_to(end) <= radius:
        return True
    # Проекция центра на отрезок.
    edge = end - start
    length_sq = edge.x * edge.x + edge.y * edge.y
    if length_sq <= 1e-9:
        return False
    t = ((center.x - start.x) * edge.x + (center.y - start.y) * edge.y) / length_sq
    t = max(0.0, min(1.0, t))
    closest = Vector2(start.x + edge.x * t, start.y + edge.y * t)
    return center.distance_to(closest) <= radius


def _ray_segment(origin: Vector2, direction: Vector2, start: Vector2,
                 end: Vector2) -> Optional[float]:
    """Расстояние до пересечения луча с отрезком (или None)."""
    edge = end - start
    denominator = direction.x * edge.y - direction.y * edge.x
    if abs(denominator) < 1e-9:
        return None
    diff = start - origin
    t = (diff.x * edge.y - diff.y * edge.x) / denominator
    u = (diff.x * direction.y - diff.y * direction.x) / denominator
    if t < 0.0 or u < 0.0 or u > 1.0:
        return None
    return t


def collect_segments(scene: Any) -> List[Tuple[Vector2, Vector2]]:
    """Собирает все препятствия сцены для расчёта теней."""
    segments: List[Tuple[Vector2, Vector2]] = []
    if scene is None:
        return segments
    for node in scene.get_nodes():
        if isinstance(node, LightOccluder2D):
            if node.enabled:
                segments.extend(node.segments())
            continue
        name = type(node).__name__
        if name != "CollisionShape2D":
            continue
        parent = getattr(node, "parent", None)
        if parent is None or not getattr(parent, "light_occluder", False):
            continue
        points = _shape_corners(node)
        if len(points) == 4:
            for index in range(4):
                segments.append((points[index], points[(index + 1) % 4]))
    return segments


__all__ = ["Light2D", "CanvasModulate", "LightOccluder2D", "collect_segments"]
