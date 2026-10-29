"""Vector2 — двумерный вектор (аналог Godot Vector2).

Реализован на чистом Python; numpy используется опционально для
векторизованных операций там, где это выгодно.
"""

from __future__ import annotations

import math
from typing import Iterable, Tuple, Union

# Попытка подгрузить numpy: используется для быстрых массовых операций.
try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover
    _np = None


class Vector2:
    """Двумерный вектор с плавающей точкой."""

    __slots__ = ("x", "y")

    def __init__(self, x: Union[int, float, "Vector2", Iterable] = 0.0,
                 y: Union[int, float, None] = None) -> None:
        """Создаёт вектор.

        Допустимые формы: Vector2(), Vector2(x), Vector2(x, y),
        Vector2((x, y)), Vector2(Vector2).
        """
        if y is None:
            if isinstance(x, Vector2):
                self.x, self.y = x.x, x.y
            elif isinstance(x, (tuple, list)) and len(x) == 2:
                self.x, self.y = float(x[0]), float(x[1])
            else:
                self.x = float(x)
                self.y = float(x)
        else:
            self.x = float(x)
            self.y = float(y)

    # ------------------------------------------------------------------
    # Представление
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return f"Vector2({self.x!r}, {self.y!r})"

    def __str__(self) -> str:
        return f"({self.x:g}, {self.y:g})"

    def __iter__(self):
        yield self.x
        yield self.y

    def __len__(self) -> int:
        return 2

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y)[index]

    def __setitem__(self, index: int, value: float) -> None:
        if index == 0:
            self.x = float(value)
        elif index == 1:
            self.y = float(value)
        else:
            raise IndexError("Vector2 допускает индексы 0 и 1")

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Vector2):
            return self.x == other.x and self.y == other.y
        return NotImplemented

    def __bool__(self) -> bool:
        return self.x != 0.0 or self.y != 0.0

    def __neg__(self) -> "Vector2":
        return Vector2(-self.x, -self.y)

    def __pos__(self) -> "Vector2":
        return Vector2(self.x, self.y)

    def __abs__(self) -> "Vector2":
        return Vector2(abs(self.x), abs(self.y))

    # ------------------------------------------------------------------
    # Арифметика
    # ------------------------------------------------------------------
    def __add__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: Union[int, float]) -> "Vector2":
        if isinstance(scalar, Vector2):
            return Vector2(self.x * scalar.x, self.y * scalar.y)
        return Vector2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: Union[int, float]) -> "Vector2":
        if isinstance(scalar, Vector2):
            return Vector2(self.x / scalar.x, self.y / scalar.y)
        return Vector2(self.x / scalar, self.y / scalar)

    def __floordiv__(self, scalar: Union[int, float]) -> "Vector2":
        return Vector2(self.x // scalar, self.y // scalar)

    def __mod__(self, scalar: Union[int, float]) -> "Vector2":
        return Vector2(self.x % scalar, self.y % scalar)

    def __iadd__(self, other: "Vector2") -> "Vector2":
        self.x += other.x
        self.y += other.y
        return self

    def __isub__(self, other: "Vector2") -> "Vector2":
        self.x -= other.x
        self.y -= other.y
        return self

    def __imul__(self, scalar: Union[int, float]) -> "Vector2":
        self.x *= scalar
        self.y *= scalar
        return self

    def __itruediv__(self, scalar: Union[int, float]) -> "Vector2":
        self.x /= scalar
        self.y /= scalar
        return self

    # ------------------------------------------------------------------
    # Основные методы
    # ------------------------------------------------------------------
    def length_squared(self) -> float:
        """Квадрат длины (быстрее, чем length)."""
        return self.x * self.x + self.y * self.y

    def normalized(self) -> "Vector2":
        """Нормализованный вектор (единичной длины)."""
        length = math.hypot(self.x, self.y)
        if length == 0.0:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / length, self.y / length)

    def is_normalized(self) -> bool:
        """True, если длина близка к 1."""
        return math.isclose(self.length_squared(), 1.0, rel_tol=1e-6)

    def dot(self, other: "Vector2") -> float:
        """Скалярное произведение."""
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Vector2") -> float:
        """Псевдоскалярное произведение (z-компонента 3D cross)."""
        return self.x * other.y - self.y * other.x

    def distance_to(self, other: "Vector2") -> float:
        """Расстояние до другого вектора."""
        return (self - other).length

    def distance_squared_to(self, other: "Vector2") -> float:
        """Квадрат расстояния до другого вектора."""
        return (self - other).length_squared()

    def angle_to(self, other: "Vector2") -> float:
        """Угол между векторами в радианах."""
        return math.atan2(self.cross(other), self.dot(other))

    def angle_to_point(self, other: "Vector2") -> float:
        """Угол к точке относительно оси X."""
        return (other - self).angle

    def direction_to(self, other: "Vector2") -> "Vector2":
        """Единичный вектор направления к другой точке."""
        return (other - self).normalized()

    def rotate(self, angle: float) -> "Vector2":
        """Поворачивает вектор на angle радиан (против часовой стрелки)."""
        c = math.cos(angle)
        s = math.sin(angle)
        return Vector2(self.x * c - self.y * s, self.x * s + self.y * c)

    def rotated(self, angle: float) -> "Vector2":
        """Синоним rotate для совместимости с Godot."""
        return self.rotate(angle)

    def lerp(self, other: "Vector2", weight: float) -> "Vector2":
        """Линейная интерполяция."""
        return Vector2(self.x + (other.x - self.x) * weight,
                       self.y + (other.y - self.y) * weight)

    def slerp(self, other: "Vector2", weight: float) -> "Vector2":
        """Сферическая интерполяция (по углу)."""
        start_angle = self.angle
        end_angle = other.angle
        delta = (end_angle - start_angle + math.pi) % (2 * math.pi) - math.pi
        angle = start_angle + delta * weight
        length = self.length + (other.length - self.length) * weight
        return Vector2(math.cos(angle) * length, math.sin(angle) * length)

    def move_toward(self, to: "Vector2", delta: float) -> "Vector2":
        """Двигается к цели не дальше чем на delta."""
        diff = to - self
        dist = diff.length
        if dist <= delta or dist == 0.0:
            return Vector2(to.x, to.y)
        return self + diff * (delta / dist)

    def reflect(self, normal: "Vector2") -> "Vector2":
        """Отражение вектора от нормали."""
        n = normal.normalized()
        return self - n * (2.0 * self.dot(n))

    def bounce(self, normal: "Vector2") -> "Vector2":
        """Отскок от нормали (синоним reflect)."""
        return self.reflect(normal)

    def slide(self, normal: "Vector2") -> "Vector2":
        """Скольжение вдоль нормали (убирает компоненту в сторону нормали)."""
        n = normal.normalized()
        return self - n * self.dot(n)

    def abs(self) -> "Vector2":
        """Покомпонентный модуль."""
        return Vector2(abs(self.x), abs(self.y))

    def sign(self) -> "Vector2":
        """Покомпонентный знак (-1, 0, 1)."""
        return Vector2(_sign(self.x), _sign(self.y))

    def floor(self) -> "Vector2":
        """Покомпонентный floor."""
        return Vector2(math.floor(self.x), math.floor(self.y))

    def ceil(self) -> "Vector2":
        """Покомпонентный ceil."""
        return Vector2(math.ceil(self.x), math.ceil(self.y))

    def round(self) -> "Vector2":
        """Покомпонентное округление."""
        return Vector2(round(self.x), round(self.y))

    def snapped(self, step: "Vector2") -> "Vector2":
        """Привязка к сетке шага step."""
        return Vector2(_snapped(self.x, step.x), _snapped(self.y, step.y))

    def clamp(self, min_v: "Vector2", max_v: "Vector2") -> "Vector2":
        """Ограничение компонент диапазоном [min_v, max_v]."""
        return Vector2(_clamp(self.x, min_v.x, max_v.x),
                       _clamp(self.y, min_v.y, max_v.y))

    def limit_length(self, length: float) -> "Vector2":
        """Ограничивает длину вектора."""
        l = self.length
        if l > 0.0 and length < l:
            return self * (length / l)
        return Vector2(self.x, self.y)

    def posmod(self, mod: Union[int, float]) -> "Vector2":
        """Положительный остаток от деления."""
        return Vector2(_posmod(self.x, mod), _posmod(self.y, mod))

    def is_zero_approx(self) -> bool:
        """True, если вектор почти нулевой."""
        return math.isclose(self.x, 0.0, abs_tol=1e-9) and \
            math.isclose(self.y, 0.0, abs_tol=1e-9)

    def is_equal_approx(self, other: "Vector2") -> bool:
        """Приближённое сравнение."""
        return math.isclose(self.x, other.x, abs_tol=1e-6) and \
            math.isclose(self.y, other.y, abs_tol=1e-6)

    def tangent(self) -> "Vector2":
        """Перпендикулярный вектор (поворот на +90°)."""
        return Vector2(-self.y, self.x)

    def perpendicular(self) -> "Vector2":
        """Синоним tangent."""
        return self.tangent()

    def as_tuple(self) -> Tuple[float, float]:
        """Кортеж (x, y)."""
        return (self.x, self.y)

    def as_ints(self) -> Tuple[int, int]:
        """Кортеж (int(x), int(y))."""
        return (int(self.x), int(self.y))

    # ------------------------------------------------------------------
    # Свойства (совместимость с Godot)
    # ------------------------------------------------------------------
    @property
    def angle(self) -> float:
        """Угол вектора в радианах (от оси X)."""
        return math.atan2(self.y, self.x)

    @angle.setter
    def angle(self, value: float) -> None:
        length = self.length
        self.x = math.cos(value) * length
        self.y = math.sin(value) * length

    @property
    def length(self) -> float:
        """Длина вектора."""
        return math.hypot(self.x, self.y)

    @length.setter
    def length(self, value: float) -> None:
        scale = value / self.length if self.length else 0.0
        self.x *= scale
        self.y *= scale

    @classmethod
    def from_angle(cls, angle: float, length: float = 1.0) -> "Vector2":
        """Вектор из угла (радианы) и длины."""
        return cls(math.cos(angle) * length, math.sin(angle) * length)


# Вспомогательные функции модуля.
def _sign(v: float) -> float:
    return 1.0 if v > 0 else (-1.0 if v < 0 else 0.0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _snapped(v: float, step: float) -> float:
    if step == 0.0:
        return v
    return math.floor(v / step + 0.5) * step


def _posmod(v: float, mod: Union[int, float]) -> float:
    return math.fmod(math.fmod(v, mod) + mod, mod)


# Предопределённые константы (после определения класса).
Vector2.ZERO = Vector2(0.0, 0.0)
Vector2.ONE = Vector2(1.0, 1.0)
Vector2.INF = Vector2(math.inf, math.inf)
Vector2.LEFT = Vector2(-1.0, 0.0)
Vector2.RIGHT = Vector2(1.0, 0.0)
Vector2.UP = Vector2(0.0, -1.0)
Vector2.DOWN = Vector2(0.0, 1.0)
