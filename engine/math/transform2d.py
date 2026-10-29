"""Transform2D — двумерное преобразование (аналог Godot Transform2D).

Преобразование = перенос (origin) + поворот (rotation, радианы) + масштаб (scale).
Преобразование точки: result = origin + basis_x * v.x + basis_y * v.y.
"""

from __future__ import annotations

import math
from typing import Union

from engine.math.vector2 import Vector2


class Transform2D:
    """Двумерное аффинное преобразование."""

    __slots__ = ("origin", "rotation", "scale")

    def __init__(self, origin: Vector2 = None, rotation: float = 0.0,
                 scale: Vector2 = None) -> None:
        self.origin = Vector2(origin) if origin is not None else Vector2()
        self.rotation = float(rotation)  # радианы
        self.scale = Vector2(scale) if scale is not None else Vector2(1.0, 1.0)

    def __repr__(self) -> str:
        return f"Transform2D({self.origin!r}, {self.rotation:g}, {self.scale!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Transform2D):
            return (self.origin == other.origin and
                    self.rotation == other.rotation and
                    self.scale == other.scale)
        return NotImplemented

    # ------------------------------------------------------------------
    # Базис
    # ------------------------------------------------------------------
    def get_basis_x(self) -> Vector2:
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        return Vector2(c * self.scale.x, s * self.scale.x)

    def get_basis_y(self) -> Vector2:
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        return Vector2(-s * self.scale.y, c * self.scale.y)

    # ------------------------------------------------------------------
    # Преобразование точек
    # ------------------------------------------------------------------
    def xform(self, v: Vector2) -> Vector2:
        """Применяет преобразование к локальной точке."""
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        x = c * self.scale.x * v.x - s * self.scale.y * v.y
        y = s * self.scale.x * v.x + c * self.scale.y * v.y
        return Vector2(self.origin.x + x, self.origin.y + y)

    def xform_inv(self, v: Vector2) -> Vector2:
        """Обратное преобразование мировой точки в локальную."""
        dx = v.x - self.origin.x
        dy = v.y - self.origin.y
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        # Обратная матрица поворота+масштаба.
        ix = (c * dx + s * dy) / self.scale.x if self.scale.x != 0 else 0.0
        iy = (-s * dx + c * dy) / self.scale.y if self.scale.y != 0 else 0.0
        return Vector2(ix, iy)

    # ------------------------------------------------------------------
    # Композиция и модификация
    # ------------------------------------------------------------------
    def translated(self, offset: Vector2) -> "Transform2D":
        return Transform2D(self.origin + offset, self.rotation, self.scale)

    def rotated(self, angle: float) -> "Transform2D":
        return Transform2D(self.origin, self.rotation + angle, self.scale)

    def scaled(self, scale: Vector2) -> "Transform2D":
        return Transform2D(self.origin, self.rotation,
                           Vector2(self.scale.x * scale.x, self.scale.y * scale.y))

    def __mul__(self, other: "Transform2D") -> "Transform2D":
        """Композиция: сначала other, затем self."""
        new_origin = self.xform(other.origin)
        new_rotation = self.rotation + other.rotation
        new_scale = Vector2(self.scale.x * other.scale.x,
                            self.scale.y * other.scale.y)
        return Transform2D(new_origin, new_rotation, new_scale)

    def inverse(self) -> "Transform2D":
        """Обратное преобразование."""
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        inv_scale = Vector2(1.0 / self.scale.x if self.scale.x != 0 else 0.0,
                            1.0 / self.scale.y if self.scale.y != 0 else 0.0)
        # Обратная матрица поворота+масштаба, применённая к origin.
        ix = (c * self.origin.x + s * self.origin.y)
        iy = (-s * self.origin.x + c * self.origin.y)
        new_origin = Vector2(-ix * inv_scale.x, -iy * inv_scale.y)
        return Transform2D(new_origin, -self.rotation, inv_scale)

    def interpolate_with(self, other: "Transform2D", weight: float) -> "Transform2D":
        """Интерполяция между преобразованиями."""
        origin = self.origin.lerp(other.origin, weight)
        rotation = self.rotation + (other.rotation - self.rotation) * weight
        scale = self.scale.lerp(other.scale, weight)
        return Transform2D(origin, rotation, scale)

    @classmethod
    def identity(cls) -> "Transform2D":
        return cls(Vector2(), 0.0, Vector2(1.0, 1.0))


Transform2D.IDENTITY = Transform2D.identity()
