"""Rect2 — прямоугольник с плавающей точкой (аналог Godot Rect2)."""

from __future__ import annotations

from typing import Union

from engine.math.vector2 import Vector2


class Rect2:
    """Прямоугольник, заданный позицией (верхний левый угол) и размером."""

    __slots__ = ("position", "size")

    def __init__(self, position: Union[Vector2, tuple] = None,
                 size: Union[Vector2, tuple] = None) -> None:
        self.position = Vector2(position) if position is not None else Vector2()
        self.size = Vector2(size) if size is not None else Vector2()

    def __repr__(self) -> str:
        return f"Rect2({self.position!r}, {self.size!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Rect2):
            return self.position == other.position and self.size == other.size
        return NotImplemented

    # ------------------------------------------------------------------
    # Геометрия
    # ------------------------------------------------------------------
    @property
    def end(self) -> Vector2:
        """Нижний правый угол."""
        return self.position + self.size

    @end.setter
    def end(self, value: Vector2) -> None:
        self.size = value - self.position

    @property
    def center(self) -> Vector2:
        return self.position + self.size * 0.5

    def area(self) -> float:
        """Площадь."""
        return self.size.x * self.size.y

    def has_point(self, point: Vector2) -> bool:
        """Содержит ли точку."""
        return (self.position.x <= point.x <= self.position.x + self.size.x and
                self.position.y <= point.y <= self.position.y + self.size.y)

    def intersects(self, other: "Rect2", include_borders: bool = True) -> bool:
        """Пересекается ли с другим прямоугольником."""
        if include_borders:
            if (self.position.x > other.position.x + other.size.x or
                    self.position.x + self.size.x < other.position.x or
                    self.position.y > other.position.y + other.size.y or
                    self.position.y + self.size.y < other.position.y):
                return False
        else:
            if (self.position.x >= other.position.x + other.size.x or
                    self.position.x + self.size.x <= other.position.x or
                    self.position.y >= other.position.y + other.size.y or
                    self.position.y + self.size.y <= other.position.y):
                return False
        return True

    def intersection(self, other: "Rect2") -> "Rect2":
        """Пересечение двух прямоугольников."""
        x1 = max(self.position.x, other.position.x)
        y1 = max(self.position.y, other.position.y)
        x2 = min(self.position.x + self.size.x, other.position.x + other.size.x)
        y2 = min(self.position.y + self.size.y, other.position.y + other.size.y)
        if x2 < x1 or y2 < y1:
            return Rect2()
        return Rect2(Vector2(x1, y1), Vector2(x2 - x1, y2 - y1))

    def merge(self, other: "Rect2") -> "Rect2":
        """Объединение двух прямоугольников."""
        x1 = min(self.position.x, other.position.x)
        y1 = min(self.position.y, other.position.y)
        x2 = max(self.position.x + self.size.x, other.position.x + other.size.x)
        y2 = max(self.position.y + self.size.y, other.position.y + other.size.y)
        return Rect2(Vector2(x1, y1), Vector2(x2 - x1, y2 - y1))

    def grow(self, amount: float) -> "Rect2":
        """Увеличивает прямоугольник на amount во все стороны."""
        return Rect2(self.position - Vector2(amount, amount),
                     self.size + Vector2(amount * 2, amount * 2))

    def expand(self, point: Vector2) -> "Rect2":
        """Расширяет прямоугольник, чтобы включить точку."""
        x1 = min(self.position.x, point.x)
        y1 = min(self.position.y, point.y)
        x2 = max(self.position.x + self.size.x, point.x)
        y2 = max(self.position.y + self.size.y, point.y)
        return Rect2(Vector2(x1, y1), Vector2(x2 - x1, y2 - y1))

    def abs(self) -> "Rect2":
        """Прямоугольник с положительным размером."""
        pos = Vector2(min(self.position.x, self.end.x),
                      min(self.position.y, self.end.y))
        size = self.size.abs()
        return Rect2(pos, size)

    def as_tuple(self) -> tuple:
        """Кортеж (x, y, w, h) — удобно для pygame.Rect."""
        return (self.position.x, self.position.y, self.size.x, self.size.y)

    def as_int_tuple(self) -> tuple:
        """Кортеж (int x, int y, int w, int h)."""
        return (int(self.position.x), int(self.position.y),
                int(self.size.x), int(self.size.y))

    def to_pygame(self):
        """Возвращает pygame.Rect (ленивый импорт)."""
        import pygame
        return pygame.Rect(self.as_int_tuple())
