"""Дополнительные компоненты Cloud Engine для работы с игрой.

Здесь собраны:

* коллайдеры — :class:`BoxCollider`, :class:`CircleCollider`;
* урон и защита — ``Hurtbox``, ``Invulnerability``, ``Regeneration``, ``Knockback``;
* движение персонажа — ``Dash``, ``DoubleJump``, ``WallJump``, ``Ladder``;
* зоны — ``Water``, ``GravityZone``, ``Pushable``;
* взаимодействие — ``Switch``, ``Door``, ``Pickup``, ``Breakable``;
* бой — ``Weapon``, ``Projectile``, ``Explosion``, ``CoinMagnet``;
* прочее — ``PathFollower``, ``CameraShake``, ``SpawnOnDeath``,
  ``AnimationStateMachine``, ``LightFlicker``.

Компонент навешивается на объект из инспектора. Если компоненту нужна
зона (Area2D), а её у объекта нет — она создаётся автоматически вместе с
прямоугольной формой, чтобы всё работало сразу.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional

from engine.components.component import Component
from engine.core.time import Time
from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.gameplay")


# ======================================================================
# Общие помощники
# ======================================================================
def _find_area(owner: Any) -> Any:
    """Area2D у объекта: сам объект или первый дочерний."""
    from engine.nodes.area2d import Area2D
    if owner is None:
        return None
    if isinstance(owner, Area2D):
        return owner
    for child in owner.get_children():
        if isinstance(child, Area2D):
            return child
    return None


def _ensure_area(component: Component, size: Vector2 = None,
                 name: str = "HitArea") -> Any:
    """Возвращает Area2D объекта, создавая его при необходимости."""
    owner = component.owner
    if owner is None:
        return None
    area = _find_area(owner)
    if area is not None:
        return area
    try:
        from engine.nodes.area2d import Area2D
        from engine.nodes.collision_shape import CollisionShape2D
        area = Area2D(name)
        shape = CollisionShape2D("Shape")
        box = Vector2(size) if size is not None else Vector2(32.0, 32.0)
        existing = getattr(owner, "get_collision_shapes", None)
        if callable(existing):
            shapes = existing()
            if shapes:
                box = Vector2(getattr(shapes[0], "size", box))
        shape.shape_type = "rectangle"
        shape.size = box
        area.add_child(shape)
        owner.add_child(area)
        return area
    except Exception:
        logger.exception("Не удалось создать Area2D для %s", component.get_type_name())
        return None


def _is_self(component: Component, body: Any) -> bool:
    """Тело — это сам объект или его дочерняя нода (не реагируем на себя)."""
    if body is None or component.owner is None:
        return True
    if body is component.owner:
        return True
    parent = getattr(body, "parent", None)
    while parent is not None:
        if parent is component.owner:
            return True
        parent = getattr(parent, "parent", None)
    return False


def _input_of(component: Component) -> Any:
    tree = component.get_tree()
    return getattr(tree, "input", None) if tree is not None else None


def _camera_of(component: Component) -> Any:
    tree = component.get_tree()
    if tree is None:
        return None
    return getattr(getattr(tree, "render_system", None), "active_camera", None)


def _health_of(node: Any) -> Any:
    if node is None:
        return None
    getter = getattr(node, "get_component", None)
    return getter("Health") if callable(getter) else None


def _scene_nodes(component: Component) -> List[Any]:
    scene = component.get_scene()
    return list(scene.get_nodes()) if scene is not None else []


def _velocity_of(node: Any) -> Vector2:
    velocity = getattr(node, "velocity", None)
    return Vector2(velocity) if isinstance(velocity, Vector2) else Vector2()


def _set_velocity(node: Any, velocity: Vector2) -> None:
    if hasattr(node, "velocity"):
        node.velocity = Vector2(velocity)


# ======================================================================
# Коллайдеры
# ======================================================================
class BoxCollider(Component):
    """Прямоугольный коллайдер: создаёт и настраивает форму столкновения."""

    type_name = "BoxCollider"
    description = "Прямоугольная форма столкновения (создаётся сама)"

    exported_properties = {
        "size": {"type": "vector2", "default": [32.0, 32.0]},
        "offset": {"type": "vector2", "default": [0.0, 0.0]},
        "one_way": {"type": "bool", "default": False},
        "auto_create": {"type": "bool", "default": True},
        "light_occluder": {"type": "bool", "default": False},
        "debug_color": {"type": "color", "default": [120, 220, 140, 255]},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.size: Vector2 = Vector2(32.0, 32.0)
        self.offset: Vector2 = Vector2()
        self.one_way: bool = False
        self.auto_create: bool = True
        self.light_occluder: bool = False
        self.debug_color: tuple = (120, 220, 140, 255)
        self._shape: Any = None
        self._applied: Any = None

    def _ready(self) -> None:
        self._shape = self._find_shape()
        if self._shape is None and self.auto_create:
            self._shape = self._create_shape()
        if self.light_occluder and self.owner is not None:
            setattr(self.owner, "light_occluder", True)
        self._apply()

    def _find_shape(self) -> Any:
        """Первая дочерняя CollisionShape2D объекта."""
        from engine.nodes.collision_shape import CollisionShape2D
        if self.owner is None:
            return None
        for child in self.owner.get_children():
            if isinstance(child, CollisionShape2D):
                return child
        return None

    def _create_shape(self) -> Any:
        try:
            from engine.nodes.collision_shape import CollisionShape2D
            shape = CollisionShape2D("BoxShape")
            self.owner.add_child(shape)
            return shape
        except Exception:
            logger.exception("BoxCollider: не удалось создать форму")
            return None

    def _process(self, delta: float) -> None:
        # Свойства могли поменять в инспекторе — следим за изменением.
        key = (self.size.x, self.size.y, self.offset.x, self.offset.y, self.one_way)
        if key != self._applied:
            self._apply()

    def _apply(self) -> None:
        shape = self._shape
        if shape is None:
            return
        try:
            shape.shape_type = "rectangle"
            shape.size = Vector2(self.size)
            shape.position = Vector2(self.offset)
            shape.one_way = bool(self.one_way)
            self._applied = (self.size.x, self.size.y, self.offset.x,
                             self.offset.y, self.one_way)
        except Exception:
            logger.exception("BoxCollider: не удалось применить размеры")

    def apply_now(self) -> None:
        """Принудительно перечитать настройки (например, после смены размера)."""
        self._apply()


class CircleCollider(Component):
    """Круглый коллайдер: удобен для мячей, монет и персонажей."""

    type_name = "CircleCollider"
    description = "Круглая форма столкновения"

    exported_properties = {
        "radius": {"type": "float", "default": 16.0, "min": 1.0, "max": 4096.0, "step": 1.0},
        "offset": {"type": "vector2", "default": [0.0, 0.0]},
        "auto_create": {"type": "bool", "default": True},
        "light_occluder": {"type": "bool", "default": False},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.radius: float = 16.0
        self.offset: Vector2 = Vector2()
        self.auto_create: bool = True
        self.light_occluder: bool = False
        self._shape: Any = None
        self._applied: Any = None

    def _ready(self) -> None:
        from engine.nodes.collision_shape import CollisionShape2D
        if self.owner is not None:
            for child in self.owner.get_children():
                if isinstance(child, CollisionShape2D):
                    self._shape = child
                    break
            if self._shape is None and self.auto_create:
                self._shape = CollisionShape2D("CircleShape")
                self.owner.add_child(self._shape)
        if self.light_occluder and self.owner is not None:
            setattr(self.owner, "light_occluder", True)
        self._apply()

    def _process(self, delta: float) -> None:
        key = (self.radius, self.offset.x, self.offset.y)
        if key != self._applied:
            self._apply()

    def _apply(self) -> None:
        if self._shape is None:
            return
        try:
            self._shape.shape_type = "circle"
            self._shape.radius = float(self.radius)
            self._shape.position = Vector2(self.offset)
            self._applied = (self.radius, self.offset.x, self.offset.y)
        except Exception:
            logger.exception("CircleCollider: не удалось применить радиус")


# ======================================================================
# Урон и защита
# ======================================================================
class Hurtbox(Component):
    """Приёмник урона: получает урон от источников и даёт кадры неуязвимости."""

    type_name = "Hurtbox"
    description = "Принимает урон и даёт временную неуязвимость"

    exported_properties = {
        "invulnerability_time": {"type": "float", "default": 0.8, "min": 0.0,
                                 "max": 10.0, "step": 0.05},
        "size": {"type": "vector2", "default": [32.0, 32.0]},
        "only_player": {"type": "bool", "default": False},
        "ignore_owner_components": {"type": "bool", "default": True},
    }
    signals = ["hurt", "blocked"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.invulnerability_time: float = 0.8
        self.size: Vector2 = Vector2(32.0, 32.0)
        self.only_player: bool = False
        self.ignore_owner_components: bool = True
        self._cooldown: float = 0.0
        self._area: Any = None

    def _ready(self) -> None:
        self._area = _ensure_area(self, self.size, "HurtArea")
        if self._area is None:
            logger.warning("Hurtbox: у '%s' нет Area2D — урон не будет приходить",
                           getattr(self.owner, "name", "?"))
            return
        if self.only_player:
            self._area.collision_mask = 1
        self._area.connect("body_entered", self._on_body_entered)

    def _process(self, delta: float) -> None:
        if self._cooldown > 0.0:
            self._cooldown = max(0.0, self._cooldown - delta)

    def _on_body_entered(self, body: Any) -> None:
        if body is None or body is self.owner:
            return
        if self.ignore_owner_components and self.owner is not None:
            if getattr(body, "parent", None) is self.owner:
                return
        if self._cooldown > 0.0:
            self.emit_signal("blocked", body)
            return
        amount = self._damage_from(body)
        if amount <= 0.0:
            return
        self.receive(amount, body)

    def _damage_from(self, body: Any) -> float:
        """Ищет источник урона в теле (DamageOnTouch, Projectile и т.п.)."""
        getter = getattr(body, "get_components", None)
        components = getter() if callable(getter) else []
        for component in components:
            name = component.get_type_name()
            if name in ("DamageOnTouch",):
                return float(getattr(component, "damage", 0.0))
            if name == "Projectile":
                return float(getattr(component, "damage", 0.0))
            if name == "Explosion":
                return float(getattr(component, "damage", 0.0))
        return 0.0

    def receive(self, amount: float, source: Any = None) -> bool:
        """Принимает урон: возвращает True, если урон прошёл."""
        health = _health_of(self.owner)
        if health is None:
            return False
        applied = health.damage(amount, source) if hasattr(health, "damage") else False
        if applied is False:
            self.emit_signal("blocked", source)
            return False
        self._cooldown = max(self._cooldown, self.invulnerability_time)
        self.emit_signal("hurt", amount, source)
        return True

    def is_invulnerable(self) -> bool:
        return self._cooldown > 0.0


class Invulnerability(Component):
    """Периоды неуязвимости: после урона, на старте или по таймеру."""

    type_name = "Invulnerability"
    description = "Временная неуязвимость с миганием"

    exported_properties = {
        "on_start": {"type": "float", "default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1},
        "after_damage": {"type": "float", "default": 1.0, "min": 0.0, "max": 30.0, "step": 0.1},
        "blink": {"type": "bool", "default": True},
        "blink_speed": {"type": "float", "default": 12.0, "min": 1.0, "max": 60.0, "step": 1.0},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_start: float = 1.0
        self.after_damage: float = 1.0
        self.blink: bool = True
        self.blink_speed: float = 12.0
        self._left: float = 0.0
        self._time: float = 0.0

    def _ready(self) -> None:
        self._left = self.on_start
        health = _health_of(self.owner)
        if health is not None:
            health.connect("damaged", self._on_damaged)

    def _on_damaged(self, amount: float, source: Any = None) -> None:
        self._left = max(self._left, self.after_damage)

    def _process(self, delta: float) -> None:
        self._time += delta
        if self._left <= 0.0:
            return
        self._left = max(0.0, self._left - delta)
        if self.blink and self.owner is not None and hasattr(self.owner, "modulate"):
            visible = math.sin(self._time * self.blink_speed) > 0.0
            color = tuple(self.owner.modulate)
            alpha = color[3] if len(color) > 3 else 255
            self.owner.modulate = (color[0], color[1], color[2],
                                   255 if visible else 80)
            if self._left <= 0.0:
                self.owner.modulate = (color[0], color[1], color[2], alpha)

    def is_active(self) -> bool:
        return self._left > 0.0

    def grant(self, duration: float) -> None:
        self._left = max(self._left, duration)


class Regeneration(Component):
    """Восстановление здоровья со временем."""

    type_name = "Regeneration"
    description = "Постепенно восстанавливает здоровье"

    exported_properties = {
        "per_second": {"type": "float", "default": 2.0, "min": 0.0, "max": 1000.0, "step": 0.5},
        "delay_after_damage": {"type": "float", "default": 2.0, "min": 0.0, "max": 60.0, "step": 0.1},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.per_second: float = 2.0
        self.delay_after_damage: float = 2.0
        self._delay: float = 0.0

    def _ready(self) -> None:
        health = _health_of(self.owner)
        if health is not None:
            health.connect("damaged", self._on_damaged)

    def _on_damaged(self, amount: float, source: Any = None) -> None:
        self._delay = self.delay_after_damage

    def _process(self, delta: float) -> None:
        if self._delay > 0.0:
            self._delay = max(0.0, self._delay - delta)
            return
        health = _health_of(self.owner)
        if health is not None and hasattr(health, "heal"):
            health.heal(self.per_second * delta)


class Knockback(Component):
    """Отбрасывание при получении урона."""

    type_name = "Knockback"
    description = "Отбрасывает объект при уроне"

    exported_properties = {
        "force": {"type": "float", "default": 260.0, "min": 0.0, "max": 10000.0, "step": 10.0},
        "upward": {"type": "float", "default": 0.5, "min": 0.0, "max": 2.0, "step": 0.05},
        "duration": {"type": "float", "default": 0.18, "min": 0.0, "max": 3.0, "step": 0.02},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.force: float = 260.0
        self.upward: float = 0.5
        self.duration: float = 0.18
        self._left: float = 0.0

    def _ready(self) -> None:
        health = _health_of(self.owner)
        if health is not None:
            health.connect("damaged", self._on_damaged)

    def _on_damaged(self, amount: float, source: Any = None) -> None:
        if self.owner is None or source is None:
            return
        try:
            direction = self.owner.get_global_position() - source.get_global_position()
        except Exception:
            return
        if direction.is_zero_approx():
            direction = Vector2(1.0, 0.0)
        push = direction.normalized() * self.force
        if hasattr(self.owner, "velocity"):
            self.owner.velocity = Vector2(push.x, push.y * self.upward - abs(push.y))
            self._left = self.duration

    def _physics_process(self, delta: float) -> None:
        if self._left <= 0.0:
            return
        self._left = max(0.0, self._left - delta)
        move = getattr(self.owner, "move_and_slide", None)
        if callable(move):
            move()


# ======================================================================
# Движение персонажа
# ======================================================================
class Dash(Component):
    """Рывок в сторону движения."""

    type_name = "Dash"
    description = "Рывок по нажатию кнопки"

    exported_properties = {
        "action": {"type": "string", "default": "dash"},
        "speed": {"type": "float", "default": 620.0, "min": 10.0, "max": 10000.0, "step": 10.0},
        "duration": {"type": "float", "default": 0.18, "min": 0.02, "max": 3.0, "step": 0.01},
        "cooldown": {"type": "float", "default": 0.6, "min": 0.0, "max": 10.0, "step": 0.05},
        "invulnerable": {"type": "bool", "default": True},
        "air_dash": {"type": "bool", "default": True},
    }
    signals = ["dash_started", "dash_finished"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.action: str = "dash"
        self.speed: float = 620.0
        self.duration: float = 0.18
        self.cooldown: float = 0.6
        self.invulnerable: bool = True
        self.air_dash: bool = True
        self._left: float = 0.0
        self._cooldown: float = 0.0
        self._direction: Vector2 = Vector2(1.0, 0.0)
        self._saved_gravity: Any = None

    def _physics_process(self, delta: float) -> None:
        if self._cooldown > 0.0:
            self._cooldown = max(0.0, self._cooldown - delta)

        if self._left > 0.0:
            self._left -= delta
            _set_velocity(self.owner, self._direction * self.speed)
            if self._left <= 0.0:
                self._restore_gravity()
                self.emit_signal("dash_finished")
            move = getattr(self.owner, "move_and_slide", None)
            if callable(move):
                move()
            return

        inp = _input_of(self)
        if inp is None or self._cooldown > 0.0:
            return
        if not inp.is_action_just_pressed(self.action):
            return
        on_floor = getattr(self.owner, "is_on_floor", lambda: True)()
        if not on_floor and not self.air_dash:
            return
        direction = self._input_direction(inp)
        if direction.is_zero_approx():
            return
        self._direction = direction.normalized()
        self._left = self.duration
        self._cooldown = self.cooldown
        if self.invulnerable and hasattr(self.owner, "gravity_scale"):
            self._saved_gravity = self.owner.gravity_scale
            self.owner.gravity_scale = 0.0
        self.emit_signal("dash_started", self._direction)

    def _restore_gravity(self) -> None:
        if self._saved_gravity is not None and hasattr(self.owner, "gravity_scale"):
            self.owner.gravity_scale = self._saved_gravity
        self._saved_gravity = None

    def _input_direction(self, inp: Any) -> Vector2:
        direction = Vector2()
        for name in ("move_left", "move_right"):
            try:
                if inp.is_action_pressed(name):
                    strength = inp.get_action_strength(name)
                    direction.x += strength if name == "move_right" else -strength
            except Exception:
                pass
        scale = getattr(self.owner, "scale", None)
        if direction.is_zero_approx() and scale is not None:
            direction = Vector2(-1.0 if getattr(self.owner, "flip_h", False) else 1.0, 0.0)
        return direction

    def is_dashing(self) -> bool:
        return self._left > 0.0


class DoubleJump(Component):
    """Двойной (и более) прыжок."""

    type_name = "DoubleJump"
    description = "Дополнительные прыжки в воздухе"

    exported_properties = {
        "action": {"type": "string", "default": "jump"},
        "max_jumps": {"type": "int", "default": 2, "min": 1, "max": 10},
        "force": {"type": "float", "default": 0.0, "min": 0.0, "max": 5000.0, "step": 10.0},
        "reset_on_floor": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.action: str = "jump"
        self.max_jumps: int = 2
        self.force: float = 0.0
        self.reset_on_floor: bool = True
        self._used: int = 0

    def _ready(self) -> None:
        self._used = 0

    def _physics_process(self, delta: float) -> None:
        on_floor = getattr(self.owner, "is_on_floor", lambda: False)()
        if on_floor and self.reset_on_floor:
            self._used = 0
        inp = _input_of(self)
        if inp is None or not inp.is_action_just_pressed(self.action):
            return
        if on_floor:
            return
        if self._used + 1 >= self.max_jumps:
            return
        self._used += 1
        velocity = _velocity_of(self.owner)
        force = self.force
        if force <= 0.0:
            force = abs(velocity.y) if velocity.y < 0 else 420.0
        _set_velocity(self.owner, Vector2(velocity.x, -abs(force)))
        move = getattr(self.owner, "move_and_slide", None)
        if callable(move):
            move()


class WallJump(Component):
    """Прыжок от стены."""

    type_name = "WallJump"
    description = "Отталкивание от стены"

    exported_properties = {
        "action": {"type": "string", "default": "jump"},
        "push_x": {"type": "float", "default": 300.0, "min": 0.0, "max": 5000.0, "step": 10.0},
        "push_y": {"type": "float", "default": 460.0, "min": 0.0, "max": 5000.0, "step": 10.0},
        "wall_slide": {"type": "bool", "default": True},
        "slide_speed": {"type": "float", "default": 90.0, "min": 0.0, "max": 2000.0, "step": 5.0},
    }
    signals = ["wall_jumped"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.action: str = "jump"
        self.push_x: float = 300.0
        self.push_y: float = 460.0
        self.wall_slide: bool = True
        self.slide_speed: float = 90.0
        self._direction: int = 1

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None:
            return
        on_wall = getattr(owner, "is_on_wall", lambda: False)()
        on_floor = getattr(owner, "is_on_floor", lambda: False)()
        velocity = _velocity_of(owner)

        if on_wall and not on_floor:
            self._direction = -1 if velocity.x > 0 else 1
            if self.wall_slide and velocity.y > self.slide_speed:
                _set_velocity(owner, Vector2(velocity.x, self.slide_speed))
                velocity = _velocity_of(owner)

        inp = _input_of(self)
        if inp is None or not inp.is_action_just_pressed(self.action):
            return
        if not on_wall or on_floor:
            return
        _set_velocity(owner, Vector2(self._direction * self.push_x, -abs(self.push_y)))
        move = getattr(owner, "move_and_slide", None)
        if callable(move):
            move()
        self.emit_signal("wall_jumped", self._direction)


class Ladder(Component):
    """Лазание по лестнице внутри зоны Area2D."""

    type_name = "Ladder"
    description = "Лазание по лестнице (зона Area2D)"

    exported_properties = {
        "climb_speed": {"type": "float", "default": 140.0, "min": 10.0, "max": 2000.0, "step": 5.0},
        "size": {"type": "vector2", "default": [32.0, 96.0]},
        "up_action": {"type": "string", "default": "move_up"},
        "down_action": {"type": "string", "default": "move_down"},
        "disable_gravity": {"type": "bool", "default": True},
    }
    signals = ["climb_started", "climb_stopped"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.climb_speed: float = 140.0
        self.size: Vector2 = Vector2(32.0, 96.0)
        self.up_action: str = "move_up"
        self.down_action: str = "move_down"
        self.disable_gravity: bool = True
        self._bodies: List[Any] = []
        self._saved: Dict[int, Any] = {}

    def _ready(self) -> None:
        area = _ensure_area(self, self.size, "LadderArea")
        if area is None:
            return
        area.connect("body_entered", self._on_enter)
        area.connect("body_exited", self._on_exit)
        self._area = area

    def _on_enter(self, body: Any) -> None:
        if _is_self(self, body) or body in self._bodies:
            return
        self._bodies.append(body)

    def _on_exit(self, body: Any) -> None:
        if body in self._bodies:
            self._bodies.remove(body)
        self._restore(body)

    def _restore(self, body: Any) -> None:
        saved = self._saved.pop(id(body), None)
        if saved is not None and hasattr(body, "gravity_scale"):
            body.gravity_scale = saved

    def _physics_process(self, delta: float) -> None:
        inp = _input_of(self)
        for body in list(self._bodies):
            if body is None:
                continue
            climbing = self._climbing(inp)
            if climbing and self.disable_gravity and hasattr(body, "gravity_scale"):
                if id(body) not in self._saved:
                    self._saved[id(body)] = body.gravity_scale
                    body.gravity_scale = 0.0
                    self.emit_signal("climb_started", body)
                axis = 0.0
                if inp is not None:
                    if inp.is_action_pressed(self.up_action):
                        axis -= 1.0
                    if inp.is_action_pressed(self.down_action):
                        axis += 1.0
                velocity = _velocity_of(body)
                _set_velocity(body, Vector2(velocity.x, axis * self.climb_speed))
                move = getattr(body, "move_and_slide", None)
                if callable(move):
                    move()
            else:
                if id(body) in self._saved:
                    self._restore(body)
                    self.emit_signal("climb_stopped", body)

    def _climbing(self, inp: Any) -> bool:
        if inp is None:
            return False
        for action in (self.up_action, self.down_action):
            try:
                if inp.is_action_pressed(action):
                    return True
            except Exception:
                pass
        return False


# ======================================================================
# Зоны
# ======================================================================
class Water(Component):
    """Зона воды: замедляет падение и позволяет плыть вверх."""

    type_name = "Water"
    description = "Вода: замедление, плавучесть, всплытие"

    exported_properties = {
        "size": {"type": "vector2", "default": [128.0, 96.0]},
        "drag": {"type": "float", "default": 2.6, "min": 0.0, "max": 20.0, "step": 0.1},
        "gravity_scale": {"type": "float", "default": 0.25, "min": 0.0, "max": 2.0, "step": 0.05},
        "swim_speed": {"type": "float", "default": 130.0, "min": 0.0, "max": 2000.0, "step": 5.0},
        "up_action": {"type": "string", "default": "move_up"},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.size: Vector2 = Vector2(128.0, 96.0)
        self.drag: float = 2.6
        self.gravity_scale: float = 0.25
        self.swim_speed: float = 130.0
        self.up_action: str = "move_up"
        self._bodies: List[Any] = []
        self._saved: Dict[int, Any] = {}

    def _ready(self) -> None:
        area = _ensure_area(self, self.size, "WaterArea")
        if area is None:
            return
        area.connect("body_entered", self._on_enter)
        area.connect("body_exited", self._on_exit)

    def _on_enter(self, body: Any) -> None:
        if not _is_self(self, body) and body not in self._bodies:
            self._bodies.append(body)
            if hasattr(body, "gravity_scale"):
                self._saved[id(body)] = body.gravity_scale
                body.gravity_scale = self.gravity_scale

    def _on_exit(self, body: Any) -> None:
        if body in self._bodies:
            self._bodies.remove(body)
        saved = self._saved.pop(id(body), None)
        if saved is not None and hasattr(body, "gravity_scale"):
            body.gravity_scale = saved

    def _physics_process(self, delta: float) -> None:
        inp = _input_of(self)
        swim_up = False
        if inp is not None:
            try:
                swim_up = inp.is_action_pressed(self.up_action)
            except Exception:
                swim_up = False
        for body in list(self._bodies):
            if body is None or not hasattr(body, "velocity"):
                continue
            velocity = _velocity_of(body)
            damp = max(0.0, 1.0 - self.drag * delta)
            velocity = Vector2(velocity.x * damp, velocity.y * damp)
            if swim_up:
                velocity.y = -self.swim_speed
            _set_velocity(body, velocity)
            move = getattr(body, "move_and_slide", None)
            if callable(move):
                move()


class GravityZone(Component):
    """Зона с изменённой гравитацией и направлением притяжения."""

    type_name = "GravityZone"
    description = "Зона с другой гравитацией"

    exported_properties = {
        "size": {"type": "vector2", "default": [128.0, 128.0]},
        "gravity_scale": {"type": "float", "default": 0.0, "min": 0.0, "max": 10.0, "step": 0.05},
        "extra_force": {"type": "vector2", "default": [0.0, 0.0]},
        "affect_player_only": {"type": "bool", "default": False},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.size: Vector2 = Vector2(128.0, 128.0)
        self.gravity_scale: float = 0.0
        self.extra_force: Vector2 = Vector2()
        self.affect_player_only: bool = False
        self._bodies: List[Any] = []
        self._saved: Dict[int, Any] = {}

    def _ready(self) -> None:
        area = _ensure_area(self, self.size, "GravityArea")
        if area is None:
            return
        area.connect("body_entered", self._on_enter)
        area.connect("body_exited", self._on_exit)

    def _on_enter(self, body: Any) -> None:
        if _is_self(self, body):
            return
        if self.affect_player_only and "Player" not in getattr(body, "name", ""):
            return
        if body in self._bodies:
            return
        self._bodies.append(body)
        if hasattr(body, "gravity_scale"):
            self._saved[id(body)] = body.gravity_scale
            body.gravity_scale = self.gravity_scale

    def _on_exit(self, body: Any) -> None:
        if body in self._bodies:
            self._bodies.remove(body)
        saved = self._saved.pop(id(body), None)
        if saved is not None and hasattr(body, "gravity_scale"):
            body.gravity_scale = saved

    def _physics_process(self, delta: float) -> None:
        if self.extra_force.is_zero_approx():
            return
        for body in list(self._bodies):
            if body is not None and hasattr(body, "velocity"):
                velocity = _velocity_of(body)
                _set_velocity(body, velocity + self.extra_force * delta)


class Pushable(Component):
    """Толкаемый объект: ящик, который двигает персонаж."""

    type_name = "Pushable"
    description = "Ящик, который можно толкать"

    exported_properties = {
        "size": {"type": "vector2", "default": [32.0, 32.0]},
        "push_speed": {"type": "float", "default": 90.0, "min": 1.0, "max": 1000.0, "step": 5.0},
        "weight": {"type": "float", "default": 1.0, "min": 0.1, "max": 10.0, "step": 0.1},
        "only_player": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.size: Vector2 = Vector2(32.0, 32.0)
        self.push_speed: float = 90.0
        self.weight: float = 1.0
        self.only_player: bool = True
        self._movers: List[Any] = []

    def _ready(self) -> None:
        area = _ensure_area(self, self.size, "PushArea")
        if area is not None:
            area.connect("body_entered", self._on_enter)
            area.connect("body_exited", self._on_exit)

    def _on_enter(self, body: Any) -> None:
        if body is None or body is self.owner:
            return
        if self.only_player and "Player" not in getattr(body, "name", ""):
            return
        if body not in self._movers:
            self._movers.append(body)

    def _on_exit(self, body: Any) -> None:
        if body in self._movers:
            self._movers.remove(body)

    def _physics_process(self, delta: float) -> None:
        if self.owner is None or not self._movers:
            return
        push = Vector2()
        for mover in list(self._movers):
            velocity = _velocity_of(mover)
            if abs(velocity.x) > 1.0:
                push.x += velocity.x
            if abs(velocity.y) > 1.0 and getattr(mover, "is_on_floor", lambda: True)():
                pass
        if push.is_zero_approx():
            return
        speed = self.push_speed / max(self.weight, 0.1)
        self.owner.position = self.owner.position + Vector2(
            math.copysign(min(abs(push.x), speed), push.x) * delta, 0.0)


# ======================================================================
# Взаимодействие
# ======================================================================
class Switch(Component):
    """Выключатель: реагирует на вход тела в зону."""

    type_name = "Switch"
    description = "Кнопка или рычаг: срабатывает от игрока"

    exported_properties = {
        "size": {"type": "vector2", "default": [32.0, 24.0]},
        "mode": {"type": "enum", "default": "pressure",
                 "options": ["pressure", "toggle", "once"]},
        "only_player": {"type": "bool", "default": True},
        "on_color": {"type": "color", "default": [120, 220, 120, 255]},
        "off_color": {"type": "color", "default": [200, 90, 90, 255]},
        "change_color": {"type": "bool", "default": True},
    }
    signals = ["switched_on", "switched_off", "toggled"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.size: Vector2 = Vector2(32.0, 24.0)
        self.mode: str = "pressure"
        self.only_player: bool = True
        self.on_color: tuple = (120, 220, 120, 255)
        self.off_color: tuple = (200, 90, 90, 255)
        self.change_color: bool = True
        self.active: bool = False
        self._inside: int = 0

    def _ready(self) -> None:
        area = _ensure_area(self, self.size, "SwitchArea")
        if area is None:
            return
        area.connect("body_entered", self._on_enter)
        area.connect("body_exited", self._on_exit)
        self._refresh_color()

    def _accept(self, body: Any) -> bool:
        if _is_self(self, body):
            return False
        if not self.only_player:
            return True
        return "Player" in getattr(body, "name", "")

    def _on_enter(self, body: Any) -> None:
        if not self._accept(body):
            return
        self._inside += 1
        if self.mode == "toggle":
            self.set_active(not self.active)
        elif self.mode == "once":
            if not self.active:
                self.set_active(True)
        else:
            self.set_active(True)

    def _on_exit(self, body: Any) -> None:
        if not self._accept(body):
            return
        self._inside = max(0, self._inside - 1)
        if self.mode == "pressure" and self._inside == 0:
            self.set_active(False)

    def set_active(self, value: bool) -> None:
        """Включает или выключает переключатель."""
        value = bool(value)
        if value == self.active:
            return
        self.active = value
        self._refresh_color()
        self.emit_signal("switched_on" if value else "switched_off")
        self.emit_signal("toggled", value)

    def toggle(self) -> None:
        self.set_active(not self.active)

    def _refresh_color(self) -> None:
        if not self.change_color or self.owner is None:
            return
        if hasattr(self.owner, "modulate"):
            self.owner.modulate = tuple(self.on_color if self.active else self.off_color)


class Door(Component):
    """Дверь: открывается по сигналу и перекрывает путь."""

    type_name = "Door"
    description = "Открывающаяся дверь"

    exported_properties = {
        "open_offset": {"type": "vector2", "default": [0.0, -48.0]},
        "speed": {"type": "float", "default": 120.0, "min": 5.0, "max": 2000.0, "step": 5.0},
        "locked": {"type": "bool", "default": False},
        "auto_close": {"type": "bool", "default": False},
        "auto_close_time": {"type": "float", "default": 2.0, "min": 0.1, "max": 60.0, "step": 0.1},
    }
    signals = ["opened", "closed", "locked_hit"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.open_offset: Vector2 = Vector2(0.0, -48.0)
        self.speed: float = 120.0
        self.locked: bool = False
        self.auto_close: bool = False
        self.auto_close_time: float = 2.0
        self.is_open: bool = False
        self._closed_position: Optional[Vector2] = None
        self._timer: float = 0.0

    def _ready(self) -> None:
        if self.owner is not None:
            self._closed_position = Vector2(self.owner.position)

    def _process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or self._closed_position is None:
            return
        target = self._closed_position + self.open_offset if self.is_open \
            else Vector2(self._closed_position)
        current = Vector2(owner.position)
        if current.distance_to(target) > 0.5:
            step = self.speed * delta
            offset = target - current
            distance = offset.length
            if distance <= step:
                owner.position = target
            else:
                owner.position = current + offset.normalized() * step
            self._set_blocking(not self.is_open or current.distance_to(target) > 4.0)
        if self.is_open and self.auto_close:
            self._timer -= delta
            if self._timer <= 0.0:
                self.close()

    def _set_blocking(self, blocking: bool) -> None:
        """Включает и выключает формы столкновения двери."""
        if self.owner is None:
            return
        getter = getattr(self.owner, "get_collision_shapes", None)
        shapes = getter() if callable(getter) else []
        for shape in shapes:
            try:
                shape.disabled = not blocking
            except Exception:
                pass

    def open(self) -> bool:
        """Открывает дверь (если не заперта)."""
        if self.locked:
            self.emit_signal("locked_hit")
            return False
        if self.is_open:
            return True
        self.is_open = True
        self._timer = self.auto_close_time
        self._set_blocking(False)
        self.emit_signal("opened")
        return True

    def close(self) -> None:
        if not self.is_open:
            return
        self.is_open = False
        self.emit_signal("closed")

    def unlock(self) -> None:
        self.locked = False


class Pickup(Component):
    """Подбираемый предмет: здоровье, патроны, ключ или очки."""

    type_name = "Pickup"
    description = "Подбираемый предмет: здоровье, патроны, ключ"

    exported_properties = {
        "kind": {"type": "enum", "default": "health",
                 "options": ["health", "ammo", "key", "score"]},
        "amount": {"type": "float", "default": 25.0, "min": 0.0, "max": 100000.0, "step": 1.0},
        "size": {"type": "vector2", "default": [24.0, 24.0]},
        "sound_path": {"type": "resource", "default": ""},
        "destroy": {"type": "bool", "default": True},
        "points_to_stat": {"type": "string", "default": "score"},
    }
    signals = ["picked"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.kind: str = "health"
        self.amount: float = 25.0
        self.size: Vector2 = Vector2(24.0, 24.0)
        self.sound_path: str = ""
        self.destroy: bool = True
        self.points_to_stat: str = "score"

    def _ready(self) -> None:
        area = _ensure_area(self, self.size, "PickupArea")
        if area is None:
            return
        area.connect("body_entered", self._on_body)

    def _on_body(self, body: Any) -> None:
        if _is_self(self, body):
            return
        self._apply(body)
        if self.sound_path:
            self._play_sound()
        self.emit_signal("picked", body)
        if self.destroy and self.owner is not None:
            self.owner.queue_free()

    def _apply(self, body: Any) -> None:
        if self.kind == "health":
            health = _health_of(body) or _health_of(self.owner)
            if health is not None:
                health.heal(self.amount)
        elif self.kind == "ammo":
            for component in (getattr(body, "get_components", lambda: [])() or []):
                if component.get_type_name() == "Weapon":
                    component.add_ammo(int(self.amount))
        elif self.kind == "key":
            from engine.components.builtin import add_stat
            add_stat("keys", self.amount)
        else:
            from engine.components.builtin import add_stat
            add_stat(self.points_to_stat, self.amount)

    def _play_sound(self) -> None:
        try:
            from engine.nodes.audio_stream import AudioStreamPlayer
            player = AudioStreamPlayer("PickupSound")
            player.stream_path = self.sound_path
            self.owner.add_child(player)
            player.play()
        except Exception:
            logger.exception("Pickup: не удалось проиграть звук")


class Breakable(Component):
    """Разрушаемый объект: ломается от урона или прыжка сверху."""

    type_name = "Breakable"
    description = "Ломается от урона или удара сверху"

    exported_properties = {
        "break_on_stomp": {"type": "bool", "default": True},
        "bounce_on_stomp": {"type": "float", "default": 320.0, "min": 0.0, "max": 3000.0,
                            "step": 10.0},
        "debris_count": {"type": "int", "default": 8, "min": 0, "max": 64},
        "sound_path": {"type": "resource", "default": ""},
    }
    signals = ["broken"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.break_on_stomp: bool = True
        self.bounce_on_stomp: float = 320.0
        self.debris_count: int = 8
        self.sound_path: str = ""

    def _ready(self) -> None:
        health = _health_of(self.owner)
        if health is not None:
            health.connect("died", self._on_died)
        area = _ensure_area(self, Vector2(36.0, 36.0), "StompArea")
        if area is not None and self.break_on_stomp:
            area.connect("body_entered", self._on_body)

    def _on_body(self, body: Any) -> None:
        if _is_self(self, body):
            return
        velocity = _velocity_of(body)
        above = body.get_global_position().y < self.owner.get_global_position().y - 4.0
        if above and velocity.y > 0.0:
            _set_velocity(body, Vector2(velocity.x, -abs(self.bounce_on_stomp)))
            self.break_now()

    def _on_died(self, source: Any = None) -> None:
        self.break_now()

    def break_now(self) -> None:
        """Ломает объект: частицы, звук и удаление."""
        if self.owner is None:
            return
        if self.debris_count > 0:
            self._spawn_debris()
        if self.sound_path:
            try:
                from engine.nodes.audio_stream import AudioStreamPlayer
                player = AudioStreamPlayer("BreakSound")
                player.stream_path = self.sound_path
                self.owner.add_child(player)
                player.play()
            except Exception:
                pass
        self.emit_signal("broken")
        self.owner.queue_free()

    def _spawn_debris(self) -> None:
        try:
            from engine.nodes.particles2d import Particles2D
            particles = Particles2D("Debris")
            particles.amount = self.debris_count * 3
            particles.lifetime = 0.7
            particles.one_shot = True
            particles.explosiveness = 1.0
            particles.position = Vector2()
            self.owner.add_child(particles)
            particles.restart() if hasattr(particles, "restart") else None
        except Exception:
            logger.exception("Breakable: не удалось создать частицы")


# ======================================================================
# Бой
# ======================================================================
class Weapon(Component):
    """Оружие: стреляет снарядами по нажатию кнопки."""

    type_name = "Weapon"
    description = "Стрельба снарядами по кнопке"

    exported_properties = {
        "action": {"type": "string", "default": "fire"},
        "projectile_type": {"type": "enum", "default": "Area2D",
                            "options": ["Area2D", "RigidBody2D", "Sprite2D", "Node2D"]},
        "damage": {"type": "float", "default": 10.0, "min": 0.0, "max": 10000.0, "step": 1.0},
        "speed": {"type": "float", "default": 420.0, "min": 0.0, "max": 20000.0, "step": 10.0},
        "cooldown": {"type": "float", "default": 0.25, "min": 0.02, "max": 10.0, "step": 0.01},
        "ammo": {"type": "int", "default": -1, "min": -1, "max": 100000},
        "spread": {"type": "float", "default": 0.0, "min": 0.0, "max": 90.0, "step": 0.5},
        "offset": {"type": "vector2", "default": [16.0, 0.0]},
        "auto_fire": {"type": "bool", "default": False},
        "use_flip": {"type": "bool", "default": True},
        "projectile_lifetime": {"type": "float", "default": 2.5, "min": 0.1, "max": 60.0,
                                "step": 0.1},
    }
    signals = ["fired", "empty"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.action: str = "fire"
        self.projectile_type: str = "Area2D"
        self.damage: float = 10.0
        self.speed: float = 420.0
        self.cooldown: float = 0.25
        self.ammo: int = -1
        self.spread: float = 0.0
        self.offset: Vector2 = Vector2(16.0, 0.0)
        self.auto_fire: bool = False
        self.use_flip: bool = True
        self.projectile_lifetime: float = 2.5
        self._cooldown: float = 0.0
        self.facing: int = 1

    def _process(self, delta: float) -> None:
        if self._cooldown > 0.0:
            self._cooldown = max(0.0, self._cooldown - delta)
        inp = _input_of(self)
        if inp is None or self._cooldown > 0.0:
            return
        try:
            pressed = inp.is_action_pressed(self.action) if self.auto_fire \
                else inp.is_action_just_pressed(self.action)
        except Exception:
            return
        if pressed:
            self.fire()

    def add_ammo(self, amount: int) -> None:
        """Добавляет патроны."""
        if self.ammo < 0:
            return
        self.ammo = max(0, self.ammo + int(amount))

    def fire(self) -> Any:
        """Создаёт снаряд. Возвращает ноду снаряда или None."""
        if self.owner is None:
            return None
        if self.ammo == 0:
            self.emit_signal("empty")
            return None
        if self.ammo > 0:
            self.ammo -= 1
        self._cooldown = self.cooldown

        from engine.nodes import NODE_CLASSES
        node_class = NODE_CLASSES.get(self.projectile_type)
        if node_class is None:
            return None
        bullet = node_class()
        bullet.name = "Bullet"
        self._prepare(bullet)
        parent = self.owner.parent if self.owner.parent is not None else self.owner
        parent.add_child(bullet)
        if hasattr(bullet, "set_asset_manager") and getattr(self.owner, "_asset_manager", None):
            bullet.set_asset_manager(self.owner._asset_manager)
        self.emit_signal("fired", bullet)
        return bullet

    def _prepare(self, bullet: Any) -> None:
        flip = bool(getattr(self.owner, "flip_h", False)) if self.use_flip else False
        self.facing = -1 if flip else 1
        direction = Vector2(self.facing, 0.0)
        if self.spread > 0.0:
            angle = math.radians(random.uniform(-self.spread, self.spread))
            direction = Vector2(math.cos(angle) * self.facing, math.sin(angle))
        direction = direction.normalized()
        origin = self.owner.get_global_position()
        if hasattr(bullet, "position"):
            bullet.position = origin + Vector2(self.offset.x * self.facing, self.offset.y)
        if hasattr(bullet, "velocity"):
            bullet.velocity = direction * self.speed
        # Навешиваем компонент снаряда.
        try:
            projectile = bullet.add_component("Projectile")
            projectile.damage = self.damage
            projectile.direction = direction
            projectile.speed = self.speed
            projectile.lifetime = self.projectile_lifetime
        except Exception:
            logger.exception("Weapon: не удалось навесить Projectile")


class Projectile(Component):
    """Снаряд: летит, наносит урон и исчезает."""

    type_name = "Projectile"
    description = "Снаряд с уроном и временем жизни"

    exported_properties = {
        "damage": {"type": "float", "default": 10.0, "min": 0.0, "max": 10000.0, "step": 1.0},
        "speed": {"type": "float", "default": 420.0, "min": 0.0, "max": 20000.0, "step": 10.0},
        "direction": {"type": "vector2", "default": [1.0, 0.0]},
        "lifetime": {"type": "float", "default": 2.5, "min": 0.1, "max": 120.0, "step": 0.1},
        "pierce": {"type": "int", "default": 0, "min": 0, "max": 100},
        "destroy_on_hit": {"type": "bool", "default": True},
        "size": {"type": "vector2", "default": [10.0, 10.0]},
        "hit_player_only": {"type": "bool", "default": False},
    }
    signals = ["hit", "expired"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.damage: float = 10.0
        self.speed: float = 420.0
        self.direction: Vector2 = Vector2(1.0, 0.0)
        self.lifetime: float = 2.5
        self.pierce: int = 0
        self.destroy_on_hit: bool = True
        self.size: Vector2 = Vector2(10.0, 10.0)
        self.hit_player_only: bool = False
        self._left: float = 0.0
        self._hits: int = 0

    def _ready(self) -> None:
        self._left = self.lifetime
        area = _ensure_area(self, self.size, "ProjectileArea")
        if area is not None:
            area.collision_mask = 0xFFFF
            area.connect("body_entered", self._on_body)
        if hasattr(self.owner, "velocity"):
            self.owner.velocity = Vector2(self.direction).normalized() * self.speed

    def _physics_process(self, delta: float) -> None:
        self._left -= delta
        if self._left <= 0.0:
            self.emit_signal("expired")
            if self.owner is not None:
                self.owner.queue_free()
            return
        if self.owner is None:
            return
        if hasattr(self.owner, "velocity"):
            self.owner.velocity = Vector2(self.direction).normalized() * self.speed
            move = getattr(self.owner, "move_and_slide", None)
            if callable(move):
                move()
        else:
            self.owner.position = self.owner.position + \
                Vector2(self.direction).normalized() * self.speed * delta

    def _on_body(self, body: Any) -> None:
        if body is None or body is self.owner:
            return
        if self.hit_player_only and "Player" not in getattr(body, "name", ""):
            return
        health = _health_of(body)
        if health is None or not hasattr(health, "damage"):
            return
        health.damage(self.damage, self.owner)
        self._hits += 1
        self.emit_signal("hit", body, self.damage)
        if self.destroy_on_hit and self._hits > self.pierce:
            if self.owner is not None:
                self.owner.queue_free()


class Explosion(Component):
    """Взрыв: урон по площади, отброс и вспышка экрана."""

    type_name = "Explosion"
    description = "Взрыв с уроном по площади"

    exported_properties = {
        "radius": {"type": "float", "default": 96.0, "min": 1.0, "max": 4000.0, "step": 4.0},
        "damage": {"type": "float", "default": 35.0, "min": 0.0, "max": 100000.0, "step": 1.0},
        "force": {"type": "float", "default": 320.0, "min": 0.0, "max": 10000.0, "step": 10.0},
        "auto_explode": {"type": "bool", "default": False},
        "delay": {"type": "float", "default": 1.0, "min": 0.0, "max": 60.0, "step": 0.05},
        "destroy_owner": {"type": "bool", "default": False},
        "screen_flash": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05},
        "shake": {"type": "float", "default": 0.4, "min": 0.0, "max": 1.0, "step": 0.05},
    }
    signals = ["exploded"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.radius: float = 96.0
        self.damage: float = 35.0
        self.force: float = 320.0
        self.auto_explode: bool = False
        self.delay: float = 1.0
        self.destroy_owner: bool = False
        self.screen_flash: float = 0.5
        self.shake: float = 0.4
        self._timer: float = 0.0

    def _ready(self) -> None:
        self._timer = self.delay
        health = _health_of(self.owner)
        if health is not None:
            health.connect("died", lambda source=None: self.explode())

    def _process(self, delta: float) -> None:
        if not self.auto_explode:
            return
        self._timer -= delta
        if self._timer <= 0.0:
            self.auto_explode = False
            self.explode()

    def explode(self) -> int:
        """Взрывается: возвращает число пострадавших объектов."""
        if self.owner is None:
            return 0
        center = self.owner.get_global_position()
        affected = 0
        for node in _scene_nodes(self):
            if node is self.owner:
                continue
            health = _health_of(node)
            if health is None:
                continue
            try:
                distance = node.get_global_position().distance_to(center)
            except Exception:
                continue
            if distance > self.radius:
                continue
            factor = 1.0 - (distance / max(self.radius, 1e-5)) * 0.6
            health.damage(self.damage * factor, self.owner)
            if self.force > 0.0 and hasattr(node, "velocity"):
                direction = node.get_global_position() - center
                if direction.is_zero_approx():
                    direction = Vector2(1.0, 0.0)
                push = direction.normalized() * self.force * factor
                _set_velocity(node, _velocity_of(node) + push)
            affected += 1

        self._effects(center)
        self.emit_signal("exploded", affected)
        if self.destroy_owner and self.owner is not None:
            self.owner.queue_free()
        return affected

    def _effects(self, center: Vector2) -> None:
        """Частицы, вспышка экрана и тряска камеры."""
        try:
            from engine.nodes.particles2d import Particles2D
            particles = Particles2D("ExplosionFx")
            particles.amount = 40
            particles.lifetime = 0.6
            particles.one_shot = True
            particles.explosiveness = 1.0
            particles.speed_min = 60.0
            particles.speed_max = 220.0
            owner = self.owner
            parent = owner.parent if owner.parent is not None else owner
            particles.position = center if parent is owner else Vector2()
            parent.add_child(particles)
        except Exception:
            logger.exception("Explosion: частицы не созданы")

        tree = self.get_tree()
        if tree is None:
            return
        if self.screen_flash > 0.0:
            from engine.nodes.post_process import PostProcess
            scene = self.get_scene()
            for node in (scene.get_nodes() if scene is not None else []):
                if isinstance(node, PostProcess):
                    node.trigger_flash((255, 220, 150, 255), 0.22 * self.screen_flash)
                    break
        if self.shake > 0.0:
            camera = getattr(getattr(tree, "render_system", None), "active_camera", None)
            if camera is not None and hasattr(camera, "add_trauma"):
                camera.add_trauma(self.shake)


class CoinMagnet(Component):
    """Притягивает собираемые предметы к объекту."""

    type_name = "CoinMagnet"
    description = "Притягивает монеты и бонусы"

    exported_properties = {
        "radius": {"type": "float", "default": 120.0, "min": 1.0, "max": 4000.0, "step": 5.0},
        "speed": {"type": "float", "default": 260.0, "min": 1.0, "max": 5000.0, "step": 10.0},
        "collectible_only": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.radius: float = 120.0
        self.speed: float = 260.0
        self.collectible_only: bool = True

    def _physics_process(self, delta: float) -> None:
        if self.owner is None:
            return
        center = self.owner.get_global_position()
        for node in _scene_nodes(self):
            if node is self.owner or not hasattr(node, "position"):
                continue
            if self.collectible_only:
                getter = getattr(node, "get_component", None)
                if not callable(getter) or getter("Collectible") is None:
                    continue
            try:
                delta_position = center - node.get_global_position()
            except Exception:
                continue
            distance = delta_position.length
            if distance > self.radius or distance < 1.0:
                continue
            node.position = node.position + delta_position.normalized() * \
                min(self.speed * delta, distance)


# ======================================================================
# Прочее
# ======================================================================
class PathFollower(Component):
    """Движение по точкам — по дочерним Node2D-узлам объекта."""

    type_name = "PathFollower"
    description = "Движение по точкам (дочерние Node2D)"

    exported_properties = {
        "speed": {"type": "float", "default": 90.0, "min": 1.0, "max": 5000.0, "step": 5.0},
        "loop_mode": {"type": "enum", "default": "loop",
                      "options": ["loop", "ping_pong", "once"]},
        "wait_time": {"type": "float", "default": 0.0, "min": 0.0, "max": 60.0, "step": 0.1},
        "snap_to_start": {"type": "bool", "default": True},
        "rotate_to_path": {"type": "bool", "default": False},
    }
    signals = ["path_finished", "point_reached"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.speed: float = 90.0
        self.loop_mode: str = "loop"
        self.wait_time: float = 0.0
        self.snap_to_start: bool = True
        self.rotate_to_path: bool = False
        self._points: List[Vector2] = []
        self._index: int = 0
        self._direction: int = 1
        self._wait: float = 0.0
        self._start: Optional[Vector2] = None

    def _ready(self) -> None:
        self.refresh_points()
        if self.owner is not None:
            self._start = Vector2(self.owner.position)
            if self.snap_to_start and self._points:
                self.owner.position = Vector2(self._start) + self._points[0]

    def refresh_points(self) -> None:
        """Перечитывает точки из дочерних Node2D."""
        from engine.nodes.node2d import Node2D
        self._points = []
        if self.owner is None:
            return
        for child in self.owner.get_children():
            if isinstance(child, Node2D):
                self._points.append(Vector2(child.position))
        self._index = 0

    def _physics_process(self, delta: float) -> None:
        if self.owner is None or len(self._points) < 2 or self._start is None:
            return
        if self._wait > 0.0:
            self._wait = max(0.0, self._wait - delta)
            return

        target = self._start + self._points[self._index]
        current = Vector2(self.owner.position)
        offset = target - current
        distance = offset.length
        step = self.speed * delta
        if distance <= step:
            self.owner.position = target
            self.emit_signal("point_reached", self._index)
            self._advance()
            return
        direction = offset.normalized()
        self.owner.position = current + direction * step
        if self.rotate_to_path:
            self.owner.rotation = math.degrees(math.atan2(direction.y, direction.x))

    def _advance(self) -> None:
        count = len(self._points)
        if self.loop_mode == "once":
            if self._index >= count - 1:
                self.emit_signal("path_finished")
                return
            self._index += 1
        elif self.loop_mode == "ping_pong":
            if self._index + self._direction >= count or self._index + self._direction < 0:
                self._direction *= -1
            self._index += self._direction
        else:
            self._index = (self._index + 1) % count
        self._wait = self.wait_time


class CameraShake(Component):
    """Тряска камеры: удобно вешать на игрока или на взрывы."""

    type_name = "CameraShake"
    description = "Тряска камеры при событиях"

    exported_properties = {
        "on_ready": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
        "on_damage": {"type": "float", "default": 0.35, "min": 0.0, "max": 1.0, "step": 0.05},
        "on_death": {"type": "float", "default": 0.8, "min": 0.0, "max": 1.0, "step": 0.05},
        "camera_path": {"type": "string", "default": ""},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_ready: float = 0.0
        self.on_damage: float = 0.35
        self.on_death: float = 0.8
        self.camera_path: str = ""

    def _ready(self) -> None:
        health = _health_of(self.owner)
        if health is not None:
            health.connect("damaged", lambda amount, source=None:
                           self.shake(self.on_damage))
            health.connect("died", lambda source=None: self.shake(self.on_death))
        if self.on_ready > 0.0:
            self.shake(self.on_ready)

    def camera(self) -> Any:
        """Активная камера: по пути или активная в сцене."""
        if self.camera_path:
            node = self.find_node(self.camera_path)
            if node is not None:
                return node
        return _camera_of(self)

    def shake(self, amount: float) -> None:
        """Запускает тряску."""
        camera = self.camera()
        if camera is not None and hasattr(camera, "add_trauma"):
            camera.add_trauma(amount)


class SpawnOnDeath(Component):
    """Создаёт объект, когда владелец погибает."""

    type_name = "SpawnOnDeath"
    description = "Создаёт объект при смерти владельца"

    exported_properties = {
        "node_type": {"type": "enum", "default": "Area2D",
                      "options": ["Area2D", "RigidBody2D", "Sprite2D", "Node2D", "Particles2D"]},
        "count": {"type": "int", "default": 1, "min": 1, "max": 50},
        "scatter": {"type": "float", "default": 0.0, "min": 0.0, "max": 2000.0, "step": 5.0},
        "inherit_velocity": {"type": "bool", "default": False},
    }
    signals = ["spawned"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_type: str = "Area2D"
        self.count: int = 1
        self.scatter: float = 0.0
        self.inherit_velocity: bool = False

    def _ready(self) -> None:
        health = _health_of(self.owner)
        if health is not None:
            health.connect("died", self._on_died)

    def _on_died(self, source: Any = None) -> None:
        if self.owner is None:
            return
        from engine.nodes import NODE_CLASSES
        node_class = NODE_CLASSES.get(self.node_type)
        if node_class is None:
            return
        parent = self.owner.parent if self.owner.parent is not None else self.owner
        base = self.owner.get_global_position()
        for _ in range(max(1, self.count)):
            node = node_class()
            if hasattr(node, "position"):
                offset = Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * self.scatter
                node.position = base + offset
            if self.inherit_velocity and hasattr(node, "velocity") \
                    and hasattr(self.owner, "velocity"):
                node.velocity = Vector2(self.owner.velocity)
            parent.add_child(node)
            self.emit_signal("spawned", node)


class AnimationStateMachine(Component):
    """Переключает анимации AnimationPlayer по состоянию персонажа."""

    type_name = "AnimationStateMachine"
    description = "Анимации по состоянию: покой, бег, прыжок, падение"

    exported_properties = {
        "player_path": {"type": "string", "default": ""},
        "idle_anim": {"type": "string", "default": "idle"},
        "run_anim": {"type": "string", "default": "run"},
        "jump_anim": {"type": "string", "default": "jump"},
        "fall_anim": {"type": "string", "default": "fall"},
        "run_threshold": {"type": "float", "default": 10.0, "min": 0.0, "max": 1000.0, "step": 1.0},
        "flip_sprite": {"type": "bool", "default": True},
    }
    signals = ["state_changed"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.player_path: str = ""
        self.idle_anim: str = "idle"
        self.run_anim: str = "run"
        self.jump_anim: str = "jump"
        self.fall_anim: str = "fall"
        self.run_threshold: float = 10.0
        self.flip_sprite: bool = True
        self.state: str = ""

    def _ready(self) -> None:
        self._player = self._find_player()

    def _find_player(self) -> Any:
        from engine.nodes.animation_player import AnimationPlayer
        if self.player_path:
            found = self.find_node(self.player_path)
            if found is not None:
                return found
        if isinstance(self.owner, AnimationPlayer):
            return self.owner
        if self.owner is not None:
            for child in self.owner.get_children():
                if isinstance(child, AnimationPlayer):
                    return child
        for node in _scene_nodes(self):
            if isinstance(node, AnimationPlayer):
                return node
        return None

    def _process(self, delta: float) -> None:
        owner = self.owner
        if owner is None:
            return
        player = getattr(self, "_player", None) or self._find_player()
        if player is None:
            return
        velocity = _velocity_of(owner)
        on_floor = getattr(owner, "is_on_floor", lambda: True)()
        if not on_floor:
            name = self.jump_anim if velocity.y < 0.0 else self.fall_anim
        elif abs(velocity.x) > self.run_threshold:
            name = self.run_anim
        else:
            name = self.idle_anim
        if name and name != self.state and name in getattr(player, "animations", {}):
            self.state = name
            player.play(name)
            self.emit_signal("state_changed", name)
        if self.flip_sprite and abs(velocity.x) > self.run_threshold:
            self._apply_flip(velocity.x < 0.0)

    def _apply_flip(self, flip: bool) -> None:
        from engine.nodes.sprite2d import Sprite2D
        target = self.owner
        if target is not None and isinstance(target, Sprite2D):
            target.flip_h = flip
            return
        if target is None:
            return
        for child in target.get_children():
            if isinstance(child, Sprite2D):
                child.flip_h = flip
                break


class LightFlicker(Component):
    """Мерцание источника света: свеча, факел, поломка."""

    type_name = "LightFlicker"
    description = "Мерцание света (нужен Light2D)"

    exported_properties = {
        "amount": {"type": "float", "default": 0.25, "min": 0.0, "max": 1.0, "step": 0.02},
        "speed": {"type": "float", "default": 9.0, "min": 0.1, "max": 60.0, "step": 0.5},
        "randomness": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05},
        "radius_sway": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.amount: float = 0.25
        self.speed: float = 9.0
        self.randomness: float = 0.5
        self.radius_sway: float = 0.0
        self._time: float = 0.0
        self._base_energy: Optional[float] = None
        self._base_radius: Optional[float] = None
        self._light: Any = None

    def _ready(self) -> None:
        from engine.nodes.light2d import Light2D
        if isinstance(self.owner, Light2D):
            self._light = self.owner
        elif self.owner is not None:
            for child in self.owner.get_children():
                if isinstance(child, Light2D):
                    self._light = child
                    break
        if self._light is None:
            logger.warning("LightFlicker: у '%s' нет Light2D",
                           getattr(self.owner, "name", "?"))
            return
        self._base_energy = float(self._light.energy)
        self._base_radius = float(self._light.radius)

    def _process(self, delta: float) -> None:
        if self._light is None or self._base_energy is None:
            return
        self._time += delta
        wave = math.sin(self._time * self.speed) * 0.6 + \
            math.sin(self._time * self.speed * 2.3) * 0.4
        if self.randomness > 0.0:
            wave += random.uniform(-1.0, 1.0) * self.randomness
        wave = max(-1.0, min(1.0, wave))
        self._light.energy = max(0.0, self._base_energy * (1.0 + wave * self.amount))
        if self.radius_sway > 0.0 and self._base_radius is not None:
            self._light.radius = max(4.0, self._base_radius * (1.0 + wave * self.radius_sway))


# ======================================================================
# Реестр
# ======================================================================
#: Новые компоненты и их категории.
GAMEPLAY_COMPONENTS = [
    BoxCollider, CircleCollider,
    Hurtbox, Invulnerability, Regeneration, Knockback,
    Dash, DoubleJump, WallJump, Ladder,
    Water, GravityZone, Pushable,
    Switch, Door, Pickup, Breakable,
    Weapon, Projectile, Explosion, CoinMagnet,
    PathFollower, CameraShake, SpawnOnDeath,
    AnimationStateMachine, LightFlicker,
]

GAMEPLAY_CATEGORIES: Dict[str, List[str]] = {
    "Коллайдеры": ["BoxCollider", "CircleCollider"],
    "Защита": ["Hurtbox", "Invulnerability", "Regeneration", "Knockback"],
    "Движение": ["Dash", "DoubleJump", "WallJump", "Ladder", "PathFollower"],
    "Зоны": ["Water", "GravityZone", "Pushable"],
    "Взаимодействие": ["Switch", "Door", "Pickup", "Breakable"],
    "Бой": ["Weapon", "Projectile", "Explosion", "CoinMagnet"],
    "Анимация": ["AnimationStateMachine"],
    "Свет": ["LightFlicker"],
    "Камера": ["CameraShake"],
    "Спавн": ["SpawnOnDeath"],
}


__all__ = ["GAMEPLAY_COMPONENTS", "GAMEPLAY_CATEGORIES", "BoxCollider",
           "CircleCollider", "Hurtbox", "Invulnerability", "Regeneration",
           "Knockback", "Dash", "DoubleJump", "WallJump", "Ladder", "Water",
           "GravityZone", "Pushable", "Switch", "Door", "Pickup", "Breakable",
           "Weapon", "Projectile", "Explosion", "CoinMagnet", "PathFollower",
           "CameraShake", "SpawnOnDeath", "AnimationStateMachine", "LightFlicker"]
