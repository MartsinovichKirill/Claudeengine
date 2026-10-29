"""Node2D — базовый 2D-узел (аналог Godot Node2D).

Хранит позицию, поворот (в градусах), масштаб, z-index, видимость и модуляцию.
Отвечает за преобразование координат (локальные/глобальные) и рекурсивную
отрисовку с учётом камеры. Также предоставляет примитивы рисования:
draw_line, draw_rect, draw_circle, draw_text.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.math.transform2d import Transform2D

WHITE = (255, 255, 255, 255)


class Node2D(Node):
    """2D-нода с преобразованием (позиция, поворот, масштаб)."""

    exported_properties = {
        "position": {"type": "vector2", "default": [0.0, 0.0]},
        "rotation": {"type": "float", "default": 0.0, "min": -360.0, "max": 360.0,
                     "step": 1.0, "hint": "degrees"},
        "scale": {"type": "vector2", "default": [1.0, 1.0]},
        "z_index": {"type": "int", "default": 0, "min": -1000, "max": 1000},
        "visible": {"type": "bool", "default": True},
        "modulate": {"type": "color", "default": [255, 255, 255, 255]},
        "z_as_relative": {"type": "bool", "default": True},
    }

    def __init__(self, name: str = "Node2D") -> None:
        super().__init__(name)
        self.position: Vector2 = Vector2()
        self.rotation: float = 0.0      # градусы
        self.scale: Vector2 = Vector2(1.0, 1.0)
        self.z_index: int = 0
        self.visible: bool = True
        self.modulate: tuple = (255, 255, 255, 255)
        self.z_as_relative: bool = True
        #: Очередь команд примитивов (заполняется draw_* и очищается после кадра).
        self._draw_commands: list = []

    # ------------------------------------------------------------------
    # Преобразования
    # ------------------------------------------------------------------
    def get_transform(self) -> Transform2D:
        """Локальное преобразование ноды."""
        return Transform2D(self.position, math.radians(self.rotation), self.scale)

    def get_global_transform(self) -> Transform2D:
        """Глобальное преобразование (с учётом родителей)."""
        local = self.get_transform()
        if self.parent is not None and isinstance(self.parent, Node2D):
            return self.parent.get_global_transform() * local
        return local

    def get_global_position(self) -> Vector2:
        """Глобальная позиция."""
        return self.get_global_transform().origin

    def set_global_position(self, value: Vector2) -> None:
        """Устанавливает глобальную позицию, пересчитывая локальную."""
        if self.parent is not None and isinstance(self.parent, Node2D):
            self.position = self.parent.get_global_transform().xform_inv(value)
        else:
            self.position = Vector2(value)

    def global_to_local(self, point: Vector2) -> Vector2:
        return self.get_global_transform().xform_inv(point)

    def local_to_global(self, point: Vector2) -> Vector2:
        return self.get_global_transform().xform(point)

    def translate(self, offset: Vector2) -> None:
        """Сдвигает ноду (в локальных координатах)."""
        self.position += offset

    def rotate(self, angle_degrees: float) -> None:
        """Поворачивает ноду на угол в градусах."""
        self.rotation += angle_degrees

    def look_at(self, point: Vector2) -> None:
        """Поворачивает ноду в сторону точки."""
        global_pos = self.get_global_position()
        self.rotation = math.degrees((point - global_pos).angle)

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def world_to_screen(self, world: Vector2, camera: Any = None) -> Vector2:
        """Преобразует мировые координаты в экранные."""
        if camera is not None and hasattr(camera, "world_to_screen"):
            return camera.world_to_screen(world)
        return Vector2(world)

    def draw(self, surface: Any, camera: Any = None) -> None:
        """Рекурсивная отрисовка: сама нода, затем дети."""
        if not self.visible:
            return
        center = self.world_to_screen(self.get_global_position(), camera)
        self._draw_local(surface, center, camera)
        self._execute_draw_commands(surface, camera)
        for child in self._children:
            child.draw(surface, camera)

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        """Отрисовка самой ноды в локальных координатах (переопределяется)."""

    # ------------------------------------------------------------------
    # Примитивы (очередь команд отрисовки)
    # ------------------------------------------------------------------
    def draw_line(self, start: Vector2, end: Vector2,
                  color: tuple = (255, 255, 255, 255), width: int = 1) -> None:
        """Добавляет команду отрисовки линии."""
        self._draw_commands.append(("line", start, end, color, width))

    def draw_rect(self, rect: Any, color: tuple = (255, 255, 255, 255),
                  filled: bool = True, width: int = 1) -> None:
        """Добавляет команду отрисовки прямоугольника."""
        self._draw_commands.append(("rect", rect, color, filled, width))

    def draw_circle(self, center: Vector2, radius: float,
                    color: tuple = (255, 255, 255, 255), filled: bool = True) -> None:
        """Добавляет команду отрисовки окружности."""
        self._draw_commands.append(("circle", center, radius, color, filled))

    def draw_text(self, text: str, position: Vector2,
                  color: tuple = (255, 255, 255, 255), size: int = 16) -> None:
        """Добавляет команду отрисовки текста."""
        self._draw_commands.append(("text", text, position, color, size))

    def _execute_draw_commands(self, surface: Any, camera: Any) -> None:
        """Выполняет накопленные команды примитивов."""
        if not self._draw_commands:
            return
        try:
            import pygame
        except Exception:
            self._draw_commands.clear()
            return
        for cmd in self._draw_commands:
            kind = cmd[0]
            try:
                if kind == "line":
                    a = self.world_to_screen(self.local_to_global(cmd[1]), camera)
                    b = self.world_to_screen(self.local_to_global(cmd[2]), camera)
                    pygame.draw.line(surface, cmd[3], a.as_ints(), b.as_ints(), cmd[4])
                elif kind == "rect":
                    rect = cmd[1]
                    p1 = self.world_to_screen(
                        self.local_to_global(Vector2(rect.position.x, rect.position.y)), camera)
                    p2 = self.world_to_screen(self.local_to_global(rect.end), camera)
                    r = pygame.Rect(p1.as_ints(), (p2 - p1).as_ints())
                    pygame.draw.rect(surface, cmd[2], r, 0 if cmd[3] else cmd[4])
                elif kind == "circle":
                    c = self.world_to_screen(self.local_to_global(cmd[1]), camera)
                    zoom = getattr(camera, "zoom", 1.0) if camera else 1.0
                    pygame.draw.circle(surface, cmd[2], c.as_ints(),
                                       max(1, int(cmd[3] * zoom)), 0 if cmd[4] else 1)
                elif kind == "text":
                    pos = self.world_to_screen(self.local_to_global(cmd[2]), camera)
                    font = pygame.font.Font(None, cmd[4])
                    surface.blit(font.render(cmd[1], True, cmd[3][:3]), pos.as_ints())
            except Exception:
                continue
        self._draw_commands.clear()

    def get_effective_z(self) -> float:
        """Эффективный z-index с учётом родителей (если z_as_relative)."""
        if self.z_as_relative and self.parent is not None and isinstance(self.parent, Node2D):
            return self.parent.get_effective_z() + self.z_index
        return float(self.z_index)

    # ------------------------------------------------------------------
    # Сериализация доп. данных (для наследников)
    # ------------------------------------------------------------------
    def _serialize_data(self) -> dict:
        """Дополнительные данные для сохранения (переопределяется)."""
        return {}

    def _deserialize_data(self, data: dict) -> None:
        """Восстановление доп. данных (переопределяется)."""
