"""Выравнивание и распределение объектов сцены.

Работает с выделенными нодами: выравнивает по краям и центрам, а также
распределяет равномерно. Возвращает список изменений, чтобы вызывающий код
мог положить их в стек отмены одним действием.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from engine.math.vector2 import Vector2

#: Режимы выравнивания: код -> название для интерфейса.
ALIGN_MODES: Dict[str, str] = {
    "left": "По левому краю",
    "right": "По правому краю",
    "top": "По верхнему краю",
    "bottom": "По нижнему краю",
    "center_h": "По центру по горизонтали",
    "center_v": "По центру по вертикали",
    "distribute_h": "Распределить по горизонтали",
    "distribute_v": "Распределить по вертикали",
}

#: Размер по умолчанию для нод без собственной графики.
DEFAULT_SIZE = Vector2(32.0, 32.0)


def node_size(node: Any) -> Vector2:
    """Размер ноды в мировых единицах (для расчёта рамки)."""
    if node is None:
        return Vector2(DEFAULT_SIZE)
    # Спрайты и прочие ноды с текстурой.
    texture = getattr(node, "texture", None)
    if texture is not None:
        try:
            scale = Vector2(getattr(node, "scale", Vector2(1.0, 1.0)))
            return Vector2(abs(texture.get_width() * scale.x),
                           abs(texture.get_height() * scale.y))
        except Exception:
            pass
    # Формы столкновения.
    size = getattr(node, "size", None)
    if isinstance(size, Vector2):
        return Vector2(abs(size.x), abs(size.y))
    radius = getattr(node, "radius", None)
    if isinstance(radius, (int, float)) and radius:
        return Vector2(abs(radius) * 2.0, abs(radius) * 2.0)
    # Тайловая карта: габариты закрашенных ячеек.
    cells = getattr(node, "cells", None)
    if isinstance(cells, dict) and cells:
        cell_size = Vector2(getattr(node, "cell_size", DEFAULT_SIZE))
        xs = [key[0] for key in cells]
        ys = [key[1] for key in cells]
        return Vector2((max(xs) - min(xs) + 1) * cell_size.x,
                       (max(ys) - min(ys) + 1) * cell_size.y)
    scale = Vector2(getattr(node, "scale", Vector2(1.0, 1.0)))
    return Vector2(DEFAULT_SIZE.x * abs(scale.x), DEFAULT_SIZE.y * abs(scale.y))


def node_center(node: Any) -> Vector2:
    """Центр ноды в мировых координатах."""
    getter = getattr(node, "get_global_position", None)
    if callable(getter):
        return Vector2(getter())
    return Vector2(getattr(node, "position", Vector2()))


def node_rect(node: Any) -> Tuple[Vector2, Vector2]:
    """Рамка ноды: (минимум, максимум) в мировых координатах."""
    center = node_center(node)
    size = node_size(node)
    half = size * 0.5
    return center - half, center + half


def bounds_of(nodes: List[Any]) -> Optional[Tuple[Vector2, Vector2]]:
    """Общая рамка набора нод."""
    if not nodes:
        return None
    minimum = None
    maximum = None
    for node in nodes:
        low, high = node_rect(node)
        if minimum is None:
            minimum, maximum = Vector2(low), Vector2(high)
            continue
        minimum = Vector2(min(minimum.x, low.x), min(minimum.y, low.y))
        maximum = Vector2(max(maximum.x, high.x), max(maximum.y, high.y))
    return minimum, maximum


def can_align(nodes: List[Any]) -> bool:
    """Достаточно ли объектов для выравнивания."""
    movable = [node for node in nodes if hasattr(node, "position")]
    return len(movable) >= 1


def align(nodes: List[Any], mode: str) -> List[Tuple[Any, Vector2, Vector2]]:
    """Выравнивает объекты. Возвращает список (нода, старая, новая) позиции."""
    movable = [node for node in nodes if hasattr(node, "position")]
    if not movable:
        return []
    changes: List[Tuple[Any, Vector2, Vector2]] = []

    if mode in ("distribute_h", "distribute_v"):
        return _distribute(movable, mode)

    bounds = bounds_of(movable)
    if bounds is None:
        return []
    minimum, maximum = bounds
    horizontal = mode in ("left", "right", "center_h")
    target_center = (minimum + maximum) * 0.5

    for node in movable:
        low, high = node_rect(node)
        old = Vector2(node.position)
        offset = Vector2()
        if mode == "left":
            offset.x = minimum.x - low.x
        elif mode == "right":
            offset.x = maximum.x - high.x
        elif mode == "center_h":
            offset.x = target_center.x - (low.x + high.x) * 0.5
        elif mode == "top":
            offset.y = minimum.y - low.y
        elif mode == "bottom":
            offset.y = maximum.y - high.y
        elif mode == "center_v":
            offset.y = target_center.y - (low.y + high.y) * 0.5
        else:
            continue
        new = Vector2(old + offset)
        if abs(new.x - old.x) > 1e-6 or abs(new.y - old.y) > 1e-6:
            changes.append((node, old, new))
    return changes


def _distribute(nodes: List[Any], mode: str) -> List[Tuple[Any, Vector2, Vector2]]:
    """Равномерно распределяет объекты между крайними."""
    if len(nodes) < 3:
        return []
    horizontal = mode == "distribute_h"
    ordered = sorted(nodes, key=lambda node: node_center(node).x if horizontal
                     else node_center(node).y)
    first = node_center(ordered[0])
    last = node_center(ordered[-1])
    start = first.x if horizontal else first.y
    end = last.x if horizontal else last.y
    step = (end - start) / (len(ordered) - 1)

    changes: List[Tuple[Any, Vector2, Vector2]] = []
    for index, node in enumerate(ordered[1:-1], start=1):
        center = node_center(node)
        old = Vector2(node.position)
        target = start + step * index
        offset = Vector2(target - center.x, 0.0) if horizontal \
            else Vector2(0.0, target - center.y)
        new = Vector2(old + offset)
        if abs(new.x - old.x) > 1e-6 or abs(new.y - old.y) > 1e-6:
            changes.append((node, old, new))
    return changes


def snap_position(position: Vector2, grid: float, enabled: bool = True) -> Vector2:
    """Прилипание позиции к сетке."""
    value = Vector2(position)
    if not enabled or grid <= 0.0:
        return value
    return Vector2(round(value.x / grid) * grid, round(value.y / grid) * grid)


def snap_delta(delta: Vector2, grid: float, enabled: bool = True) -> Vector2:
    """Прилипание смещения к шагу сетки."""
    value = Vector2(delta)
    if not enabled or grid <= 0.0:
        return value
    return Vector2(round(value.x / grid) * grid, round(value.y / grid) * grid)


__all__ = ["ALIGN_MODES", "align", "bounds_of", "can_align", "node_center",
           "node_rect", "node_size", "snap_delta", "snap_position"]
