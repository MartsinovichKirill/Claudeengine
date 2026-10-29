"""CollisionSystem — детекция коллизий: AABB/Circle/Polygon (SAT), триггеры, raycast.

Предоставляет:
- move_and_collide(body, motion) для CharacterBody2D/RigidBody2D;
- update(dt) — обновление триггеров Area2D (entered/exited);
- raycast(ray) — пересечение луча с фигурами.
"""

from __future__ import annotations

import logging
import math
from typing import Any, List, Optional, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.collision_shape import CollisionShape2D

logger = logging.getLogger("cloudengine.collision")


class CollisionSystem:
    """Детектор коллизий 2D."""

    def __init__(self, scene_tree: Any) -> None:
        self.scene_tree = scene_tree
        self._area_overlaps: dict = {}  # id(area) -> set(id(other))

    # ------------------------------------------------------------------
    # Сбор тел
    # ------------------------------------------------------------------
    def get_bodies(self, include_areas: bool = False) -> List[Any]:
        """Собирает физические тела текущей сцены."""
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return []
        from engine.nodes.rigidbody2d import PhysicsBody2D
        result = []
        for node in self.scene_tree.current_scene.get_nodes():
            if isinstance(node, PhysicsBody2D):
                if not include_areas and _is_area(node):
                    continue
                result.append(node)
            elif callable(getattr(node, 'physics_body', None)):
                body = node.physics_body()
                if body is not None:
                    result.append(body)
        return result

    def get_solid_bodies(self) -> List[Any]:
        """Тела, участвующие как препятствия (static + rigid + character)."""
        from engine.nodes.staticbody2d import StaticBody2D
        from engine.nodes.rigidbody2d import RigidBody2D
        from engine.nodes.characterbody2d import CharacterBody2D
        bodies = []
        for node in self.get_bodies(include_areas=False):
            if isinstance(node, (StaticBody2D, RigidBody2D, CharacterBody2D)):
                bodies.append(node)
        return bodies

    def get_areas(self) -> List[Any]:
        from engine.nodes.area2d import Area2D
        return [n for n in self.get_bodies(include_areas=True) if isinstance(n, Area2D)]

    # ------------------------------------------------------------------
    # Движение с коллизией
    # ------------------------------------------------------------------
    def move_and_collide(self, body: Any, motion: Vector2) -> Optional[dict]:
        """Перемещает тело на motion, разрешая столкновения."""
        shapes = body.get_collision_shapes()
        if not shapes:
            body.set_global_position(body.get_global_position() + motion)
            return None
        # Sample at less than half the smallest moving shape thickness so even
        # thin obstacles cannot be crossed between endpoint-only tests.
        extents = [hi - lo for lo, hi in (shape.get_aabb() for shape in shapes)]
        stride = max(0.05, min(min(abs(e.x), abs(e.y)) for e in extents) * 0.45)
        steps = max(1, math.ceil(motion.length / stride))
        step = motion / steps
        # Reject shapes outside the entire swept path before expensive SAT
        # tests. Include both endpoints, so fast bodies still hit thin walls.
        moving_bounds = [shape.get_aabb() for shape in shapes]
        low = Vector2(min(a.x for a, b in moving_bounds) + min(0, motion.x),
                      min(a.y for a, b in moving_bounds) + min(0, motion.y))
        high = Vector2(max(b.x for a, b in moving_bounds) + max(0, motion.x),
                       max(b.y for a, b in moving_bounds) + max(0, motion.y))
        obstacles = []
        for other in self.get_solid_bodies():
            if other is body or not _can_collide(body, other):
                continue
            candidates = []
            for shape in other.get_collision_shapes():
                a, b = shape.get_aabb()
                if a.x <= high.x + 1e-6 and b.x >= low.x - 1e-6 and a.y <= high.y + 1e-6 and b.y >= low.y - 1e-6:
                    candidates.append(shape)
            if candidates:
                obstacles.append((other, candidates))
        for index in range(steps):
            previous = [shape.get_aabb() for shape in shapes]
            body.set_global_position(body.get_global_position() + step)
            best = None
            depth_best = -1.0
            for other, other_shapes in obstacles:
                for shape_index, shape in enumerate(shapes):
                    for other_shape in other_shapes:
                        if other_shape.one_way:
                            top = other_shape.get_aabb()[0].y
                            if step.y <= 0 or previous[shape_index][1].y > top + other_shape.one_way_margin:
                                continue
                        hit = self._shapes_collide(shape, other_shape)
                        if hit is not None and hit[1] <= 1e-8 and step.dot(hit[0]) >= 0:
                            continue
                        if hit is not None and hit[1] > depth_best:
                            normal, depth_best = hit
                            best = {'normal': normal, 'collider': other,
                                    'position': body.get_global_position() + normal * depth_best,
                                    'remainder': step * (steps-index-1)}
            if best is not None:
                body.set_global_position(best['position'])
                best['position'] = Vector2(body.position)
                return best
        return None

    def test_move(self, body: Any, motion: Vector2) -> Optional[dict]:
        """Проверяет столкновение при движении, НЕ перемещая тело."""
        original = Vector2(body.position)
        result = self.move_and_collide(body, motion)
        body.position = original
        return result

    def _one_way_allows(self, motion: Vector2, body: Any, shape: Any) -> bool:
        """Проверка one-way платформы: пропускаем движение снизу вверх."""
        up = Vector2(0, -1)
        # Разрешаем только если движемся вниз.
        if motion.dot(up) >= 0:
            return False
        # Тело должно находиться выше верхней границы платформы.
        aabb = shape.get_aabb()
        body_center = body.get_global_position()
        if body_center.y > aabb[0].y + shape.one_way_margin:
            return False
        return True

    # ------------------------------------------------------------------
    # Геометрия
    # ------------------------------------------------------------------
    def _shape_polygon(self, shape: CollisionShape2D) -> Optional[List[Vector2]]:
        """Вершины фигуры в мировых координатах (для SAT)."""
        if shape.shape_type in ("rectangle", "polygon", "capsule"):
            verts = shape.get_world_vertices()
            return verts if verts else None
        return None

    def _shape_circle(self, shape: CollisionShape2D) -> Optional[Tuple[Vector2, float]]:
        if shape.shape_type == "circle":
            center = shape.get_global_position()
            scale = shape.get_global_transform().scale
            r = shape.radius * max(abs(scale.x), abs(scale.y))
            return (center, r)
        return None

    def _shapes_collide(self, a: CollisionShape2D,
                        b: CollisionShape2D) -> Optional[Tuple[Vector2, float]]:
        """Возвращает (нормаль, глубина) при столкновении, иначе None."""
        ca = self._shape_circle(a)
        cb = self._shape_circle(b)
        pa = self._shape_polygon(a)
        pb = self._shape_polygon(b)

        if ca is not None and cb is not None:
            return _circle_circle(ca[0], ca[1], cb[0], cb[1])
        if ca is not None and pb:
            return _circle_polygon(ca[0], ca[1], pb)
        if cb is not None and pa:
            hit = _circle_polygon(cb[0], cb[1], pa)
            if hit is not None:
                return (-hit[0], hit[1])
            return None
        if pa and pb:
            return _polygon_polygon(pa, pb)
        return None

    # ------------------------------------------------------------------
    # Триггеры Area2D
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Обновляет перекрытия Area2D и испускает сигналы."""
        areas = self.get_areas()
        bodies = self.get_bodies(include_areas=False)
        all_areas = areas

        current: dict = {}
        for area in areas:
            current[id(area)] = set()

        # Перекрытия областей с телами.
        for area in areas:
            if not area.monitoring:
                continue
            for body in bodies:
                if body is area or not _can_collide(area, body):
                    continue
                if self._bodies_overlap(area, body):
                    current[id(area)].add(id(body))

        # Область-область.
        for i in range(len(all_areas)):
            for j in range(i + 1, len(all_areas)):
                a1, a2 = all_areas[i], all_areas[j]
                if not (a1.monitoring and a2.monitorable):
                    continue
                if self._bodies_overlap(a1, a2):
                    current[id(a1)].add(id(a2))
                    current.setdefault(id(a2), set()).add(id(a1))

        # Сравнение с предыдущим кадром.
        for area in areas:
            prev = self._area_overlaps.get(id(area), set())
            now = current.get(id(area), set())
            entered = now - prev
            exited = prev - now
            area.overlapping_bodies = [b for b in bodies if id(b) in now]
            area.overlapping_areas = [o for o in all_areas
                                      if o is not area and id(o) in now]
            for other_id in entered:
                other = _find_by_id(bodies, other_id)
                if other is not None:
                    area.emit_signal("body_entered", other)
                else:
                    a2 = _find_by_id(all_areas, other_id)
                    if a2 is not None:
                        area.emit_signal("area_entered", a2)
            for other_id in exited:
                other = _find_by_id(bodies, other_id)
                if other is not None:
                    area.emit_signal("body_exited", other)
                else:
                    a2 = _find_by_id(all_areas, other_id)
                    if a2 is not None:
                        area.emit_signal("area_exited", a2)

        self._area_overlaps = current

    def _bodies_overlap(self, a: Any, b: Any) -> bool:
        for sa in a.get_collision_shapes():
            for sb in b.get_collision_shapes():
                if self._shapes_collide(sa, sb) is not None:
                    return True
        return False

    # ------------------------------------------------------------------
    # RayCast
    # ------------------------------------------------------------------
    def raycast(self, ray: Any) -> None:
        """Проверяет луч RayCast2D и заполняет его результат."""
        origin = ray.get_global_position()
        direction = ray.cast_to
        ray._colliding = False
        ray._collider = None

        best_t = float("inf")
        best_point = origin + direction
        best_normal = Vector2()

        for other in self.get_solid_bodies():
            if ray.exclude_parent and (other is ray or ray.is_ancestor_of(other)):
                continue
            if not _can_collide(ray, other):
                continue
            for shape in other.get_collision_shapes():
                hit = self._ray_shape(origin, direction, shape)
                if hit is not None:
                    t, point, normal = hit
                    if t < best_t:
                        best_t = t
                        best_point = point
                        best_normal = normal
                        ray._colliding = True
                        ray._collider = other
        ray._collision_point = best_point
        ray._collision_normal = best_normal

    def _ray_shape(self, origin: Vector2, direction: Vector2,
                   shape: CollisionShape2D) -> Optional[Tuple[float, Vector2, Vector2]]:
        circle = self._shape_circle(shape)
        if circle is not None:
            return _ray_circle(origin, direction, circle[0], circle[1])
        poly = self._shape_polygon(shape)
        if poly:
            return _ray_polygon(origin, direction, poly)
        aabb = shape.get_aabb()
        return _ray_aabb(origin, direction, aabb[0], aabb[1])


# ======================================================================
# Вспомогательные функции геометрии
# ======================================================================
def _is_area(node: Any) -> bool:
    from engine.nodes.area2d import Area2D
    return isinstance(node, Area2D)


def _can_collide(a: Any, b: Any) -> bool:
    """Проверка слоёв: a.mask & b.layer."""
    if not hasattr(a, "collision_mask") or not hasattr(b, "collision_layer"):
        return True
    return bool(a.collision_mask & b.collision_layer)


def _find_by_id(items: List[Any], obj_id: int) -> Optional[Any]:
    for item in items:
        if id(item) == obj_id:
            return item
    return None


def _circle_circle(ca: Vector2, ra: float, cb: Vector2, rb: float):
    """Столкновение двух окружностей.

    Нормаль направлена ОТ b К a (вдоль неё нужно сдвинуть a для разделения).
    """
    diff = ca - cb
    dist = diff.length
    rsum = ra + rb
    if dist >= rsum:
        return None
    if dist == 0:
        return (Vector2(0.0, -1.0), rsum)
    return (diff.normalized(), rsum - dist)


def _circle_polygon(center: Vector2, radius: float, verts: List[Vector2]):
    """Столкновение окружности (a) с полигоном (b).

    Нормаль направлена от полигона к центру окружности.
    """
    # Ближайшая точка полигона к центру.
    closest = _closest_point_polygon(center, verts)
    diff = center - closest
    dist = diff.length
    if dist >= radius:
        return None
    if dist == 0:
        # Центр внутри полигона: берём минимальную ось из SAT.
        hit = _polygon_polygon(_circle_as_polygon(center, radius), verts)
        return hit
    normal = diff / dist
    return (normal, radius - dist)


def _circle_as_polygon(center: Vector2, radius: float) -> List[Vector2]:
    pts = []
    for i in range(16):
        ang = i * 2 * math.pi / 16
        pts.append(Vector2(center.x + math.cos(ang) * radius,
                           center.y + math.sin(ang) * radius))
    return pts


def _closest_point_polygon(point: Vector2, verts: List[Vector2]) -> Vector2:
    if _point_in_polygon(point, verts):
        return Vector2(point)
    best = verts[0]
    best_dist = point.distance_to(best)
    for i in range(len(verts)):
        a = verts[i]
        b = verts[(i + 1) % len(verts)]
        closest = _closest_point_segment(point, a, b)
        d = point.distance_to(closest)
        if d < best_dist:
            best_dist = d
            best = closest
    return best


def _closest_point_segment(p: Vector2, a: Vector2, b: Vector2) -> Vector2:
    ab = b - a
    t = (p - a).dot(ab) / max(ab.length_squared(), 1e-12)
    t = max(0.0, min(1.0, t))
    return a + ab * t


def _point_in_polygon(p: Vector2, verts: List[Vector2]) -> bool:
    inside = False
    j = len(verts) - 1
    for i in range(len(verts)):
        if ((verts[i].y > p.y) != (verts[j].y > p.y)) and \
           (p.x < (verts[j].x - verts[i].x) * (p.y - verts[i].y) /
            (verts[j].y - verts[i].y + 1e-12) + verts[i].x):
            inside = not inside
        j = i
    return inside


def _polygon_polygon(a: List[Vector2], b: List[Vector2]):
    """SAT для двух выпуклых полигонов.

    Возвращает (нормаль, глубина), где нормаль направлена ОТ b К a:
    сдвинув a на normal * depth, фигуры разделяются.
    """
    if not a or not b:
        return None
    # Быстрая отбраковка по AABB.
    aabb_a = (_min_vec(a), _max_vec(a))
    aabb_b = (_min_vec(b), _max_vec(b))
    if not _aabb_overlap(aabb_a[0], aabb_a[1], aabb_b[0], aabb_b[1]):
        return None

    # Оси — нормали всех рёбер обоих полигонов.
    axes: List[Vector2] = []
    for poly in (a, b):
        n_pts = len(poly)
        for i in range(n_pts):
            edge = poly[(i + 1) % n_pts] - poly[i]
            if edge.length_squared() < 1e-12:
                continue
            axes.append(Vector2(-edge.y, edge.x).normalized())
    if not axes:
        return None

    # Направление «от b к a» для ориентации нормали.
    delta = _centroid(a) - _centroid(b)

    best_depth = float("inf")
    best_normal = None
    for axis in axes:
        min1, max1 = _project(a, axis)
        min2, max2 = _project(b, axis)
        if max1 < min2 or max2 < min1:
            return None
        overlap = min(max1 - min2, max2 - min1)
        if overlap < best_depth:
            best_depth = overlap
            best_normal = axis if max2 - min1 < max1 - min2 else -axis
    if best_normal is None:
        return None
    return (best_normal, best_depth)


def _centroid(verts: List[Vector2]) -> Vector2:
    """Центр масс полигона (среднее вершин)."""
    n = len(verts)
    if n == 0:
        return Vector2()
    return Vector2(sum(v.x for v in verts) / n, sum(v.y for v in verts) / n)


def _project(verts: List[Vector2], axis: Vector2) -> Tuple[float, float]:
    dots = [v.dot(axis) for v in verts]
    return (min(dots), max(dots))


def _min_vec(verts: List[Vector2]) -> Vector2:
    return Vector2(min(v.x for v in verts), min(v.y for v in verts))


def _max_vec(verts: List[Vector2]) -> Vector2:
    return Vector2(max(v.x for v in verts), max(v.y for v in verts))


def _aabb_overlap(amin: Vector2, amax: Vector2, bmin: Vector2, bmax: Vector2) -> bool:
    return not (amax.x < bmin.x or amin.x > bmax.x or
                amax.y < bmin.y or amin.y > bmax.y)


def _ray_circle(origin: Vector2, direction: Vector2, center: Vector2, radius: float):
    if direction.length_squared() == 0:
        return None
    d = direction.normalized()
    f = origin - center
    a = d.dot(d)
    b = 2 * f.dot(d)
    c = f.dot(f) - radius * radius
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    sqrt_disc = math.sqrt(disc)
    t1 = (-b - sqrt_disc) / (2 * a)
    t2 = (-b + sqrt_disc) / (2 * a)
    t = t1 if t1 >= 0 else (t2 if t2 >= 0 else None)
    if t is None:
        return None
    point = origin + d * t
    normal = (point - center).normalized()
    return (t, point, normal)


def _ray_aabb(origin: Vector2, direction: Vector2, bmin: Vector2, bmax: Vector2):
    if direction.length_squared() == 0:
        return None
    d = direction
    tmin = float("-inf")
    tmax = float("inf")
    normal = Vector2()
    for axis in (0, 1):
        if abs(d[axis]) < 1e-9:
            if origin[axis] < bmin[axis] or origin[axis] > bmax[axis]:
                return None
        else:
            inv = 1.0 / d[axis]
            t1 = (bmin[axis] - origin[axis]) * inv
            t2 = (bmax[axis] - origin[axis]) * inv
            if t1 > t2:
                t1, t2 = t2, t1
            if t1 > tmin:
                tmin = t1
                normal = Vector2()
                normal[axis] = -1.0 if inv < 0 else 1.0
            if t2 < tmax:
                tmax = t2
    if tmax < tmin or tmax < 0:
        return None
    t = tmin if tmin >= 0 else tmax
    point = origin + d * t
    return (t, point, normal)


def _ray_polygon(origin: Vector2, direction: Vector2, verts: List[Vector2]):
    """Пересечение луча с полигоном (t — абсолютное расстояние)."""
    if not verts or direction.length_squared() == 0:
        return None
    d = direction.normalized()
    max_t = direction.length
    aabb = (_min_vec(verts), _max_vec(verts))
    if _ray_aabb(origin, direction, aabb[0], aabb[1]) is None:
        return None
    best_t = float("inf")
    best_normal = Vector2()
    for i in range(len(verts)):
        a = verts[i]
        b = verts[(i + 1) % len(verts)]
        seg = b - a
        denom = d.cross(seg)
        if abs(denom) < 1e-9:
            continue
        diff = a - origin
        t = diff.cross(seg) / denom
        u = diff.cross(d) / denom
        if 0.0 <= t <= max_t and 0.0 <= u <= 1.0:
            if t < best_t:
                best_t = t
                best_normal = Vector2(-seg.y, seg.x).normalized()
    if best_t == float("inf"):
        return None
    point = origin + d * best_t
    return (best_t, point, best_normal)
