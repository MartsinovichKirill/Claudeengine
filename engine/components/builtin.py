"""Встроенные компоненты Cloud Engine.

Каждый компонент самодостаточен: его можно навесить на ноду в инспекторе,
и он заработает без единой строки кода.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional

from engine.components.component import Component
from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.components")


# ======================================================================
# Глобальная игровая статистика (очки, жизни и т.п.)
# ======================================================================
GAME_STATS: Dict[str, float] = {"score": 0.0, "coins": 0.0, "deaths": 0.0}


def reset_game_stats() -> None:
    """Сбрасывает игровую статистику."""
    for key in GAME_STATS:
        GAME_STATS[key] = 0.0


def add_stat(name: str, amount: float = 1.0) -> float:
    """Прибавляет значение к статистике и возвращает результат."""
    GAME_STATS[name] = GAME_STATS.get(name, 0.0) + amount
    return GAME_STATS[name]


def get_stat(name: str, default: float = 0.0) -> float:
    return GAME_STATS.get(name, default)


# ======================================================================
# Здоровье
# ======================================================================
class HealthComponent(Component):
    """Здоровье: урон, лечение, неуязвимость, сигнал о смерти."""

    type_name = "Health"
    description = "Здоровье объекта: урон, лечение, смерть"
    exported_properties = {
        "max_health": {"type": "float", "default": 100.0, "min": 1.0, "max": 100000.0, "step": 1.0},
        "health": {"type": "float", "default": 100.0, "min": 0.0, "max": 100000.0, "step": 1.0},
        "destroy_on_death": {"type": "bool", "default": True},
        "invulnerability": {"type": "float", "default": 0.0, "min": 0.0, "max": 60.0, "step": 0.1},
    }
    signals = ["damaged", "healed", "died", "health_changed"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.max_health: float = 100.0
        self.health: float = 100.0
        self.destroy_on_death: bool = True
        self.invulnerability: float = 0.0
        self._invuln_left: float = 0.0
        self._dead: bool = False

    def _ready(self) -> None:
        self.health = min(self.health, self.max_health)
        self.emit_signal("health_changed", self.health, self.max_health)

    def _process(self, delta: float) -> None:
        if self._invuln_left > 0.0:
            self._invuln_left = max(0.0, self._invuln_left - delta)

    # ------------------------------------------------------------------
    def is_alive(self) -> bool:
        return not self._dead and self.health > 0.0

    def get_ratio(self) -> float:
        if self.max_health <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self.health / self.max_health))

    def damage(self, amount: float, source: Any = None) -> bool:
        """Наносит урон. Возвращает True, если урон прошёл."""
        if self._dead or amount <= 0.0 or self._invuln_left > 0.0:
            return False
        self.health = max(0.0, self.health - amount)
        self._invuln_left = self.invulnerability
        self.emit_signal("damaged", amount, source)
        self.emit_signal("health_changed", self.health, self.max_health)
        if self.health <= 0.0:
            self._die(source)
        return True

    def heal(self, amount: float) -> None:
        """Лечит объект."""
        if self._dead or amount <= 0.0:
            return
        self.health = min(self.max_health, self.health + amount)
        self.emit_signal("healed", amount)
        self.emit_signal("health_changed", self.health, self.max_health)

    def set_health(self, value: float) -> None:
        self.health = max(0.0, min(self.max_health, value))
        self.emit_signal("health_changed", self.health, self.max_health)

    def kill(self, source: Any = None) -> None:
        """Мгновенно убивает объект."""
        self.health = 0.0
        self._die(source)

    def revive(self) -> None:
        """Возрождает объект с полным здоровьем."""
        self._dead = False
        self.health = self.max_health
        self.emit_signal("health_changed", self.health, self.max_health)

    def _die(self, source: Any = None) -> None:
        if self._dead:
            return
        self._dead = True
        add_stat("deaths", 1.0)
        self.emit_signal("died", source)
        if self.destroy_on_death and self.owner is not None:
            self.owner.queue_free()


# ======================================================================
# Время жизни
# ======================================================================
class LifetimeComponent(Component):
    """Автоматически удаляет ноду через заданное время."""

    type_name = "Lifetime"
    description = "Удалить ноду через N секунд (снаряды, эффекты)"
    exported_properties = {
        "lifetime": {"type": "float", "default": 3.0, "min": 0.05, "max": 600.0, "step": 0.1},
        "start_emitting": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.lifetime: float = 3.0
        self.start_emitting: bool = True
        self._left: float = 3.0

    def _ready(self) -> None:
        if self.start_emitting:
            self.restart()

    def restart(self) -> None:
        """Перезапускает отсчёт."""
        self._left = self.lifetime

    def _process(self, delta: float) -> None:
        if self._left <= 0.0:
            return
        self._left -= delta
        if self._left <= 0.0 and self.owner is not None:
            self.owner.queue_free()


# ======================================================================
# Вращение / колебание
# ======================================================================
class RotatorComponent(Component):
    """Вращает ноду с постоянной скоростью."""

    type_name = "Rotator"
    description = "Постоянное вращение ноды"
    exported_properties = {
        "speed": {"type": "float", "default": 90.0, "min": -3600.0, "max": 3600.0, "step": 5.0},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.speed: float = 90.0  # градусов в секунду

    def _process(self, delta: float) -> None:
        if self.owner is not None and hasattr(self.owner, "rotation"):
            self.owner.rotation += self.speed * delta


class OscillatorComponent(Component):
    """Колеблет ноду вокруг исходной позиции (синус)."""

    type_name = "Oscillator"
    description = "Плавное колебание ноды вокруг стартовой точки"
    exported_properties = {
        "direction": {"type": "vector2", "default": [0.0, 1.0]},
        "amplitude": {"type": "float", "default": 32.0, "min": 0.0, "max": 10000.0, "step": 1.0},
        "frequency": {"type": "float", "default": 1.0, "min": 0.01, "max": 60.0, "step": 0.05},
        "phase": {"type": "float", "default": 0.0, "min": 0.0, "max": 6.28, "step": 0.1},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.direction: Vector2 = Vector2(0.0, 1.0)
        self.amplitude: float = 32.0
        self.frequency: float = 1.0
        self.phase: float = 0.0
        self._origin: Vector2 = Vector2()
        self._time: float = 0.0

    def _ready(self) -> None:
        if self.owner is not None:
            self._origin = Vector2(getattr(self.owner, "position", Vector2()))
        self._time = self.phase

    def _physics_process(self, delta: float) -> None:
        if self.owner is None or not hasattr(self.owner, "position"):
            return
        self._time += delta
        offset = self.direction.normalized() * (
            math.sin(self._time * self.frequency * math.tau) * self.amplitude)
        self.owner.position = self._origin + offset


# ======================================================================
# Слежение и патрулирование
# ======================================================================
class FollowComponent(Component):
    """Плавно следует за целевой нодой."""

    type_name = "Follow"
    description = "Плавное следование за другой нодой"
    exported_properties = {
        "target_path": {"type": "string", "default": "Player"},
        "speed": {"type": "float", "default": 4.0, "min": 0.1, "max": 100.0, "step": 0.1},
        "keep_distance": {"type": "float", "default": 0.0, "min": 0.0, "max": 5000.0, "step": 1.0},
        "offset": {"type": "vector2", "default": [0.0, 0.0]},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_path: str = "Player"
        self.speed: float = 4.0
        self.keep_distance: float = 0.0
        self.offset: Vector2 = Vector2()
        self._target: Any = None

    def _ready(self) -> None:
        self._target = self.find_node(self.target_path)

    def _physics_process(self, delta: float) -> None:
        if self.owner is None or not hasattr(self.owner, "position"):
            return
        if self._target is None:
            self._target = self.find_node(self.target_path)
            if self._target is None:
                return
        target_pos = self._target.get_global_position() + self.offset
        current = self.owner.get_global_position()
        distance = current.distance_to(target_pos)
        if self.keep_distance > 0.0 and distance <= self.keep_distance:
            return
        weight = max(0.0, min(1.0, self.speed * delta))
        self.owner.set_global_position(current.lerp(target_pos, weight))


class PatrolComponent(Component):
    """Двигает ноду туда-сюда по горизонтали (или по заданному вектору)."""

    type_name = "Patrol"
    description = "Патрулирование между двумя точками"
    exported_properties = {
        "direction": {"type": "vector2", "default": [1.0, 0.0]},
        "distance": {"type": "float", "default": 128.0, "min": 1.0, "max": 10000.0, "step": 4.0},
        "speed": {"type": "float", "default": 80.0, "min": 0.0, "max": 5000.0, "step": 5.0},
        "flip_sprite": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.direction: Vector2 = Vector2(1.0, 0.0)
        self.distance: float = 128.0
        self.speed: float = 80.0
        self.flip_sprite: bool = True
        self._origin: Vector2 = Vector2()
        self._sign: float = 1.0

    def _ready(self) -> None:
        if self.owner is not None:
            self._origin = Vector2(getattr(self.owner, "position", Vector2()))

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or not hasattr(self.owner, "position"):
            return
        axis = self.direction.normalized()
        step = axis * (self.speed * self._sign * delta)
        owner.position = owner.position + step

        travelled = (owner.position - self._origin).dot(axis)
        if travelled >= self.distance:
            owner.position = self._origin + axis * self.distance
            self._sign = -1.0
            self._apply_flip(owner)
        elif travelled <= 0.0:
            owner.position = Vector2(self._origin)
            self._sign = 1.0
            self._apply_flip(owner)

    def _apply_flip(self, owner: Any) -> None:
        """Отражает спрайт по направлению движения."""
        if not self.flip_sprite:
            return
        from engine.nodes.sprite2d import Sprite2D
        sprite = owner if isinstance(owner, Sprite2D) else None
        if sprite is None:
            for child in owner.get_children():
                if isinstance(child, Sprite2D):
                    sprite = child
                    break
        if sprite is not None:
            sprite.flip_h = self._sign < 0.0


class MoveAIComponent(Component):
    """Простое ИИ-движение: идёт к цели, прыгает через препятствия."""

    type_name = "MoveAI"
    description = "ИИ: движение к игроку с прыжками через препятствия"
    exported_properties = {
        "target_path": {"type": "string", "default": "Player"},
        "speed": {"type": "float", "default": 90.0, "min": 0.0, "max": 5000.0, "step": 5.0},
        "detect_range": {"type": "float", "default": 400.0, "min": 0.0, "max": 10000.0, "step": 10.0},
        "jump_force": {"type": "float", "default": 380.0, "min": 0.0, "max": 5000.0, "step": 10.0},
        "auto_move": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_path: str = "Player"
        self.speed: float = 90.0
        self.detect_range: float = 400.0
        self.jump_force: float = 380.0
        self.auto_move: bool = True
        self._target: Any = None

    def _ready(self) -> None:
        self._target = self.find_node(self.target_path)

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None:
            return
        if self._target is None:
            self._target = self.find_node(self.target_path)
            if self._target is None:
                return
        from engine.nodes.characterbody2d import CharacterBody2D
        if not isinstance(owner, CharacterBody2D):
            return

        to_target = self._target.get_global_position() - owner.get_global_position()
        if abs(to_target.x) > self.detect_range:
            owner.velocity.x = 0.0
        else:
            direction = 1.0 if to_target.x > 0.0 else -1.0
            owner.velocity.x = direction * self.speed
            self._flip(owner, direction)
            if owner.is_on_wall() and owner.is_on_floor():
                owner.velocity.y = -abs(self.jump_force)

        if self.auto_move:
            owner.move_and_slide()

    def _flip(self, owner: Any, direction: float) -> None:
        from engine.nodes.sprite2d import Sprite2D
        for child in owner.get_children():
            if isinstance(child, Sprite2D):
                child.flip_h = direction < 0.0
                return


class JumperComponent(Component):
    """Периодически заставляет CharacterBody2D прыгать."""

    type_name = "Jumper"
    description = "Периодические прыжки (для CharacterBody2D)"
    exported_properties = {
        "interval": {"type": "float", "default": 1.5, "min": 0.1, "max": 60.0, "step": 0.1},
        "jump_force": {"type": "float", "default": 420.0, "min": 0.0, "max": 5000.0, "step": 10.0},
        "random_interval": {"type": "bool", "default": False},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.interval: float = 1.5
        self.jump_force: float = 420.0
        self.random_interval: bool = False
        self._timer: float = 0.0

    def _ready(self) -> None:
        self._timer = self._next_interval()

    def _next_interval(self) -> float:
        if self.random_interval:
            return random.uniform(self.interval * 0.5, self.interval * 1.5)
        return self.interval

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None:
            return
        from engine.nodes.characterbody2d import CharacterBody2D
        if not isinstance(owner, CharacterBody2D):
            return
        self._timer -= delta
        if self._timer <= 0.0:
            self._timer = self._next_interval()
            if owner.is_on_floor():
                owner.velocity.y = -abs(self.jump_force)


# ======================================================================
# Игровые взаимодействия
# ======================================================================
class CollectibleComponent(Component):
    """Собираемый предмет: реагирует на касание телом и начисляет очки."""

    type_name = "Collectible"
    description = "Монета/бонус: собирается при касании, даёт очки"
    exported_properties = {
        "points": {"type": "float", "default": 1.0, "min": 0.0, "max": 10000.0, "step": 1.0},
        "stat_name": {"type": "string", "default": "coins"},
        "destroy_on_collect": {"type": "bool", "default": True},
        "sound_path": {"type": "resource", "default": ""},
        "only_player": {"type": "bool", "default": True},
    }
    signals = ["collected"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.points: float = 1.0
        self.stat_name: str = "coins"
        self.destroy_on_collect: bool = True
        self.sound_path: str = ""
        self.only_player: bool = True

    def _ready(self) -> None:
        area = self._find_area()
        if area is None:
            logger.warning("Collectible: у ноды '%s' нет Area2D",
                           getattr(self.owner, "name", "?"))
            return
        area.connect("body_entered", self._on_body_entered)

    def _find_area(self) -> Any:
        from engine.nodes.area2d import Area2D
        if self.owner is None:
            return None
        if isinstance(self.owner, Area2D):
            return self.owner
        for child in self.owner.get_children():
            if isinstance(child, Area2D):
                return child
        return None

    def _on_body_entered(self, body: Any) -> None:
        if body is None:
            return
        if self.only_player and "player" not in getattr(body, "groups", []):
            comp = body.get_component("Health") if hasattr(body, "get_component") else None
            if comp is None and "Player" not in getattr(body, "name", ""):
                return
        self.collect(body)

    def collect(self, collector: Any = None) -> None:
        """Собирает предмет вручную."""
        add_stat(self.stat_name, self.points)
        add_stat("score", self.points)
        self._play_sound()
        self.emit_signal("collected", collector, self.points)
        if self.destroy_on_collect and self.owner is not None:
            self.owner.queue_free()

    def _play_sound(self) -> None:
        if not self.sound_path or self.owner is None:
            return
        try:
            import pygame
            tree = self.get_tree()
            manager = None
            if tree is not None and tree.audio_system is not None:
                manager = getattr(tree.audio_system, "asset_manager", None)
            if tree is not None and tree.render_system is not None:
                manager = tree.render_system.asset_manager
            if manager is not None:
                sound = manager.get_sound(self.sound_path)
                if sound is not None:
                    sound.play()
        except Exception:
            pass


class DamageOnTouchComponent(Component):
    """Наносит урон телам, коснувшимся Area2D."""

    type_name = "DamageOnTouch"
    description = "Урон при касании (шипы, враги)"
    exported_properties = {
        "damage": {"type": "float", "default": 10.0, "min": 0.0, "max": 100000.0, "step": 1.0},
        "cooldown": {"type": "float", "default": 0.5, "min": 0.0, "max": 60.0, "step": 0.1},
        "knockback": {"type": "float", "default": 0.0, "min": 0.0, "max": 5000.0, "step": 10.0},
    }
    signals = ["hit"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.damage: float = 10.0
        self.cooldown: float = 0.5
        self.knockback: float = 0.0
        self._cooldowns: Dict[int, float] = {}

    def _ready(self) -> None:
        from engine.nodes.area2d import Area2D
        area = self.owner if isinstance(self.owner, Area2D) else None
        if area is None and self.owner is not None:
            for child in self.owner.get_children():
                if isinstance(child, Area2D):
                    area = child
                    break
        if area is None:
            logger.warning("DamageOnTouch: у ноды '%s' нет Area2D",
                           getattr(self.owner, "name", "?"))
            return
        area.connect("body_entered", self._on_body_entered)

    def _process(self, delta: float) -> None:
        for key in list(self._cooldowns.keys()):
            self._cooldowns[key] -= delta
            if self._cooldowns[key] <= 0.0:
                del self._cooldowns[key]

    def _on_body_entered(self, body: Any) -> None:
        if body is None or self.owner is not None and body is self.owner:
            return
        if self._cooldowns.get(id(body), 0.0) > 0.0:
            return
        getter = getattr(body, "get_component", None)
        health = getter("Health") if callable(getter) else None
        if health is None:
            return
        health.damage(self.damage, self.owner)
        self._cooldowns[id(body)] = self.cooldown
        self._apply_knockback(body)
        self.emit_signal("hit", body, self.damage)

    def _apply_knockback(self, body: Any) -> None:
        if self.knockback <= 0.0 or not hasattr(body, "velocity"):
            return
        direction = Vector2(1.0, -0.5)
        if self.owner is not None and hasattr(body, "get_global_position"):
            delta = body.get_global_position() - self.owner.get_global_position()
            if not delta.is_zero_approx():
                direction = Vector2(1.0 if delta.x >= 0 else -1.0, -0.5)
        body.velocity = body.velocity + direction.normalized() * self.knockback


class FlashComponent(Component):
    """Мигает модуляцией ноды при получении урона."""

    type_name = "Flash"
    description = "Вспышка цвета при уроне"
    exported_properties = {
        "flash_color": {"type": "color", "default": [255, 80, 80, 255]},
        "duration": {"type": "float", "default": 0.15, "min": 0.01, "max": 5.0, "step": 0.01},
        "blink_count": {"type": "int", "default": 2, "min": 1, "max": 20},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.flash_color: tuple = (255, 80, 80, 255)
        self.duration: float = 0.15
        self.blink_count: int = 2
        self._timer: float = 0.0
        self._original: Any = None

    def _ready(self) -> None:
        health = self.get_component("Health")
        if health is not None:
            health.connect("damaged", lambda *_: self.flash())
        if self.owner is not None and hasattr(self.owner, "modulate"):
            self._original = tuple(self.owner.modulate)

    def flash(self) -> None:
        """Запускает вспышку."""
        self._timer = self.duration * self.blink_count * 2.0
        if self.owner is not None and hasattr(self.owner, "modulate"):
            if self._original is None:
                self._original = tuple(self.owner.modulate)
            self.owner.modulate = self.flash_color

    def _process(self, delta: float) -> None:
        if self._timer <= 0.0:
            return
        self._timer -= delta
        owner = self.owner
        if owner is None or not hasattr(owner, "modulate"):
            return
        if self._timer <= 0.0:
            owner.modulate = self._original or (255, 255, 255, 255)
            return
        blink = int(self._timer / max(self.duration, 1e-5)) % 2
        owner.modulate = self.flash_color if blink else (self._original or (255, 255, 255, 255))


class SpawnerComponent(Component):
    """Периодически создаёт ноды (враги, снаряды, бонусы)."""

    type_name = "Spawner"
    description = "Спавн нод/сцен через интервал"
    exported_properties = {
        "node_type": {"type": "enum", "default": "Node2D",
                      "options": ["Node2D", "Sprite2D", "RigidBody2D",
                                  "CharacterBody2D", "Area2D", "StaticBody2D",
                                  "Particles2D", "Timer"]},
        "interval": {"type": "float", "default": 2.0, "min": 0.05, "max": 600.0, "step": 0.1},
        "max_count": {"type": "int", "default": 10, "min": 1, "max": 1000},
        "offset": {"type": "vector2", "default": [0.0, 0.0]},
        "autostart": {"type": "bool", "default": True},
        "random_offset": {"type": "float", "default": 0.0, "min": 0.0, "max": 5000.0, "step": 1.0},
    }
    signals = ["spawned"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_type: str = "Node2D"
        self.interval: float = 2.0
        self.max_count: int = 10
        self.offset: Vector2 = Vector2()
        self.autostart: bool = True
        self.random_offset: float = 0.0
        self._timer: float = 0.0
        self._spawned: List[Any] = []

    def _ready(self) -> None:
        self._timer = self.interval if self.autostart else 0.0
        if not self.autostart:
            self.enabled = False

    def start(self) -> None:
        """Включает спавн."""
        self.enabled = True
        self._timer = self.interval

    def stop(self) -> None:
        self.enabled = False

    def _process(self, delta: float) -> None:
        if not self.enabled or self.owner is None:
            return
        self._timer -= delta
        if self._timer > 0.0:
            return
        self._timer = self.interval
        self._spawned = [n for n in self._spawned if n.parent is not None]
        if len(self._spawned) >= self.max_count:
            return
        self.spawn()

    def spawn(self) -> Any:
        """Создаёт одну ноду. Возвращает созданную ноду или None."""
        if self.owner is None:
            return None
        from engine.nodes import NODE_CLASSES
        node_class = NODE_CLASSES.get(self.node_type)
        if node_class is None:
            return None
        try:
            node = node_class()
        except Exception:
            logger.exception("Spawner: не удалось создать %s", self.node_type)
            return None
        node.name = f"{self.node_type}{len(self._spawned) + 1}"
        offset = self.offset
        if self.random_offset > 0.0:
            offset = offset + Vector2(random.uniform(-self.random_offset, self.random_offset),
                                      random.uniform(-self.random_offset, self.random_offset))
        if hasattr(node, "position"):
            node.position = self.owner.get_global_position() + offset
        parent = self.owner.parent if self.owner.parent is not None else self.owner
        parent.add_child(node)
        self._spawned.append(node)
        self.emit_signal("spawned", node)
        return node


class ScoreComponent(Component):
    """Показывает счёт в Label и/или следит за статистикой."""

    type_name = "Score"
    description = "HUD-счётчик: выводит очки в Label"
    exported_properties = {
        "stat_name": {"type": "string", "default": "coins"},
        "template": {"type": "string", "default": "Счёт: {value}"},
        "label_path": {"type": "string", "default": ""},
        "show_max": {"type": "bool", "default": False},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stat_name: str = "coins"
        self.template: str = "Счёт: {value}"
        self.label_path: str = ""
        self.show_max: bool = False
        self._label: Any = None

    def _ready(self) -> None:
        if self.label_path:
            self._label = self.find_node(self.label_path)
        if self._label is None:
            from engine.nodes.label import Label
            if self.owner is not None and isinstance(self.owner, Label):
                self._label = self.owner
        self._refresh()

    def _process(self, delta: float) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if self._label is None:
            return
        value = get_stat(self.stat_name)
        text = self.template.replace("{value}", str(int(value)))
        text = text.replace("{name}", self.stat_name)
        if self._label.text != text:
            self._label.text = text


# ======================================================================
# Платформы и автоочистка
# ======================================================================
class PlatformMoverComponent(Component):
    """Двигает StaticBody2D (платформу) между двумя точками."""

    type_name = "PlatformMover"
    description = "Движущаяся платформа (StaticBody2D)"
    exported_properties = {
        "offset": {"type": "vector2", "default": [200.0, 0.0]},
        "speed": {"type": "float", "default": 60.0, "min": 0.0, "max": 5000.0, "step": 5.0},
        "wait_time": {"type": "float", "default": 0.0, "min": 0.0, "max": 30.0, "step": 0.1},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.offset: Vector2 = Vector2(200.0, 0.0)
        self.speed: float = 60.0
        self.wait_time: float = 0.0
        self._origin: Vector2 = Vector2()
        self._progress: float = 0.0
        self._direction: float = 1.0
        self._waiting: float = 0.0

    def _ready(self) -> None:
        if self.owner is not None:
            self._origin = Vector2(getattr(self.owner, "position", Vector2()))

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or not hasattr(owner, "position"):
            return
        length = self.offset.length
        if length <= 0.0 or self.speed <= 0.0:
            return
        if self._waiting > 0.0:
            self._waiting = max(0.0, self._waiting - delta)
            return
        self._progress += (self.speed * delta / length) * self._direction
        if self._progress >= 1.0:
            self._progress = 1.0
            self._direction = -1.0
            self._waiting = self.wait_time
        elif self._progress <= 0.0:
            self._progress = 0.0
            self._direction = 1.0
            self._waiting = self.wait_time
        owner.position = self._origin + self.offset * self._progress


class AutoDestroyComponent(Component):
    """Удаляет ноду, если она ушла далеко за пределы сцены."""

    type_name = "AutoDestroy"
    description = "Удаление ноды за границами сцены"
    exported_properties = {
        "margin": {"type": "float", "default": 400.0, "min": 0.0, "max": 100000.0, "step": 10.0},
        "bounds": {"type": "rect2", "default": [[-2000.0, -2000.0], [4000.0, 4000.0]]},
        "kill_below_y": {"type": "float", "default": 2000.0, "min": -1000000.0, "max": 1000000.0, "step": 50.0},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.margin: float = 400.0
        self.bounds: Any = None
        self.kill_below_y: float = 2000.0

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or not hasattr(owner, "get_global_position"):
            return
        pos = owner.get_global_position()
        if pos.y > self.kill_below_y:
            owner.queue_free()
            return
        if self.bounds is not None:
            expanded = self.bounds.grow(self.margin) if hasattr(self.bounds, "grow") else None
            if expanded is not None and not expanded.has_point(pos):
                owner.queue_free()


class BobbingLabelComponent(Component):
    """Заставляет ноду плавно покачиваться (для текста/иконок)."""

    type_name = "Bobbing"
    description = "Плавное покачивание ноды"
    exported_properties = {
        "amplitude": {"type": "float", "default": 6.0, "min": 0.0, "max": 500.0, "step": 1.0},
        "speed": {"type": "float", "default": 3.0, "min": 0.05, "max": 60.0, "step": 0.1},
        "vertical": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.amplitude: float = 6.0
        self.speed: float = 3.0
        self.vertical: bool = True
        self._origin: Vector2 = Vector2()
        self._time: float = 0.0

    def _ready(self) -> None:
        if self.owner is not None:
            self._origin = Vector2(getattr(self.owner, "position", Vector2()))

    def _process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or not hasattr(owner, "position"):
            return
        self._time += delta
        value = math.sin(self._time * self.speed) * self.amplitude
        offset = Vector2(0.0, value) if self.vertical else Vector2(value, 0.0)
        owner.position = self._origin + offset


# ======================================================================
# Дополнительные игровые компоненты
# ======================================================================
#: Точки возрождения по имени группы (заполняется Checkpoint).
RESPAWN_POINTS: Dict[str, Vector2] = {}


class HealthBarComponent(Component):
    """Связывает Health со шкалой ProgressBar."""

    type_name = "HealthBar"
    description = "Показывает здоровье на ProgressBar"
    exported_properties = {
        "bar_path": {"type": "string", "default": "UI/EnergyBar"},
        "smooth": {"type": "bool", "default": True},
        "speed": {"type": "float", "default": 4.0, "min": 0.1, "max": 60.0, "step": 0.1},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.bar_path: str = "UI/EnergyBar"
        self.smooth: bool = True
        self.speed: float = 4.0
        self._bar: Any = None
        self._target: float = 100.0

    def _ready(self) -> None:
        self._bar = self.find_node(self.bar_path)
        health = self.get_component("Health")
        if health is None:
            logger.warning("HealthBar: у ноды нет компонента Health")
            return
        self._bar = self._bar
        if self._bar is not None:
            self._bar.max_value = health.max_health
        health.connect("health_changed", self._on_health_changed)
        self._target = health.health

    def _on_health_changed(self, value: float, maximum: float) -> None:
        if self._bar is not None:
            self._bar.max_value = maximum
        self._target = value

    def _process(self, delta: float) -> None:
        if self._bar is None:
            return
        if self.smooth:
            weight = max(0.0, min(1.0, self.speed * delta))
            self._bar.value = self._bar.value + (self._target - self._bar.value) * weight
        else:
            self._bar.value = self._target


class CheckpointComponent(Component):
    """Запоминает точку возрождения при касании."""

    type_name = "Checkpoint"
    description = "Сохраняет точку возрождения (Area2D)"
    exported_properties = {
        "group": {"type": "string", "default": "default"},
        "offset": {"type": "vector2", "default": [0.0, 0.0]},
        "only_once": {"type": "bool", "default": True},
    }
    signals = ["activated"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.group: str = "default"
        self.offset: Vector2 = Vector2()
        self.only_once: bool = True

    def _ready(self) -> None:
        self._connect_area()

    def _connect_area(self) -> None:
        from engine.nodes.area2d import Area2D
        area = self.owner if isinstance(self.owner, Area2D) else None
        if area is None and self.owner is not None:
            for child in self.owner.get_children():
                if isinstance(child, Area2D):
                    area = child
                    break
        if area is None:
            return
        area.connect("body_entered", self._on_body_entered)

    def _on_body_entered(self, body: Any) -> None:
        if self.only_once and RESPAWN_POINTS.get(self.group) is not None:
            return
        if self.owner is None:
            return
        point = self.owner.get_global_position() + self.offset
        RESPAWN_POINTS[self.group] = point
        self.emit_signal("activated", point)


class RespawnComponent(Component):
    """Возрождает ноду в сохранённой точке после смерти."""

    type_name = "Respawn"
    description = "Возврат на точку возрождения после смерти"
    exported_properties = {
        "group": {"type": "string", "default": "default"},
        "lives": {"type": "int", "default": 3, "min": -1, "max": 9999},
        "respawn_delay": {"type": "float", "default": 0.0, "min": 0.0, "max": 60.0, "step": 0.1},
        "heal_on_respawn": {"type": "bool", "default": True},
    }
    signals = ["respawned", "game_over"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.group: str = "default"
        self.lives: int = 3
        self.respawn_delay: float = 0.0
        self.heal_on_respawn: bool = True
        self._delay_left: float = 0.0
        self._pending: bool = False

    def _ready(self) -> None:
        health = self.get_component("Health")
        if health is not None:
            health.destroy_on_death = False
            health.connect("died", self._on_died)

    def _on_died(self, source: Any = None) -> None:
        if self.lives == 0:
            self.emit_signal("game_over")
            return
        if self.lives > 0:
            self.lives -= 1
        self._pending = True
        self._delay_left = self.respawn_delay
        if self.respawn_delay <= 0.0:
            self._do_respawn()

    def _process(self, delta: float) -> None:
        if not self._pending:
            return
        self._delay_left -= delta
        if self._delay_left <= 0.0:
            self._do_respawn()

    def _do_respawn(self) -> None:
        self._pending = False
        if self.owner is None:
            return
        point = RESPAWN_POINTS.get(self.group)
        if point is not None:
            self.owner.set_global_position(Vector2(point))
        if hasattr(self.owner, "velocity"):
            self.owner.velocity = Vector2()
        health = self.get_component("Health")
        if health is not None and self.heal_on_respawn:
            health.revive()
        self.emit_signal("respawned")


class HomingComponent(Component):
    """Самонаведение: объект летит к цели."""

    type_name = "Homing"
    description = "Самонаведение на цель (снаряды)"
    exported_properties = {
        "target_path": {"type": "string", "default": "Player"},
        "speed": {"type": "float", "default": 160.0, "min": 0.0, "max": 10000.0, "step": 5.0},
        "turn_rate": {"type": "float", "default": 4.0, "min": 0.1, "max": 60.0, "step": 0.1},
        "use_physics": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.target_path: str = "Player"
        self.speed: float = 160.0
        self.turn_rate: float = 4.0
        self.use_physics: bool = True
        self._target: Any = None

    def _ready(self) -> None:
        self._target = self.find_node(self.target_path)

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or not hasattr(owner, "velocity"):
            return
        if self._target is None:
            self._target = self.find_node(self.target_path)
            if self._target is None:
                return
        direction = (self._target.get_global_position()
                     - owner.get_global_position()).normalized()
        weight = max(0.0, min(1.0, self.turn_rate * delta))
        velocity = Vector2(owner.velocity)
        if velocity.is_zero_approx():
            velocity = direction * self.speed
        velocity = velocity.normalized().lerp(direction, weight) * self.speed
        owner.velocity = velocity
        move = getattr(owner, "move_and_slide", None)
        if self.use_physics and callable(move):
            move()
        elif hasattr(owner, "position"):
            owner.position = owner.position + velocity * delta


class ShooterComponent(Component):
    """Периодически создаёт снаряды в заданном направлении."""

    type_name = "Shooter"
    description = "Стрельба снарядами через интервал"
    exported_properties = {
        "node_type": {"type": "enum", "default": "Area2D",
                      "options": ["Area2D", "RigidBody2D", "Sprite2D", "Node2D"]},
        "interval": {"type": "float", "default": 1.0, "min": 0.05, "max": 60.0, "step": 0.05},
        "speed": {"type": "float", "default": 220.0, "min": 0.0, "max": 10000.0, "step": 10.0},
        "direction": {"type": "vector2", "default": [1.0, 0.0]},
        "autostart": {"type": "bool", "default": True},
        "aim_at_target": {"type": "bool", "default": False},
        "target_path": {"type": "string", "default": "Player"},
        "lifetime": {"type": "float", "default": 3.0, "min": 0.1, "max": 120.0, "step": 0.1},
    }
    signals = ["shot"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_type: str = "Area2D"
        self.interval: float = 1.0
        self.speed: float = 220.0
        self.direction: Vector2 = Vector2(1.0, 0.0)
        self.autostart: bool = True
        self.aim_at_target: bool = False
        self.target_path: str = "Player"
        self.lifetime: float = 3.0
        self._timer: float = 0.0

    def _ready(self) -> None:
        self._timer = self.interval if self.autostart else 0.0

    def _physics_process(self, delta: float) -> None:
        if not self.enabled or self.owner is None:
            return
        self._timer -= delta
        if self._timer > 0.0:
            return
        self._timer = self.interval
        self.shoot()

    def shoot(self) -> Any:
        """Создаёт один снаряд."""
        from engine.nodes import NODE_CLASSES
        owner = self.owner
        if owner is None:
            return None
        node_class = NODE_CLASSES.get(self.node_type)
        if node_class is None:
            return None
        bullet = node_class()
        bullet.name = "Bullet"
        direction = Vector2(self.direction).normalized()
        if self.aim_at_target:
            target = self.find_node(self.target_path)
            if target is not None:
                direction = (target.get_global_position()
                             - owner.get_global_position()).normalized()
        if hasattr(bullet, "position"):
            bullet.position = owner.get_global_position() + direction * 24.0
        if hasattr(bullet, "velocity"):
            bullet.velocity = direction * self.speed
        try:
            bullet.add_component("Lifetime").lifetime = self.lifetime
        except Exception:
            pass
        parent = owner.parent if owner.parent is not None else owner
        parent.add_child(bullet)
        self.emit_signal("shot", bullet)
        return bullet


class BounceComponent(Component):
    """Отскок при столкновении (для CharacterBody2D)."""

    type_name = "Bounce"
    description = "Отскок от стен и пола"
    exported_properties = {
        "bounce_force": {"type": "float", "default": 420.0, "min": 0.0, "max": 10000.0, "step": 10.0},
        "only_floor": {"type": "bool", "default": False},
        "min_speed": {"type": "float", "default": 20.0, "min": 0.0, "max": 5000.0, "step": 5.0},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.bounce_force: float = 420.0
        self.only_floor: bool = False
        self.min_speed: float = 20.0

    def _physics_process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or not hasattr(owner, "velocity"):
            return
        from engine.nodes.characterbody2d import CharacterBody2D
        if not isinstance(owner, CharacterBody2D):
            return
        if self.min_speed > 0.0 and owner.velocity.length < self.min_speed \
                and owner.is_on_floor():
            return
        if owner.is_on_floor():
            owner.velocity = Vector2(owner.velocity.x, -abs(self.bounce_force))
        elif not self.only_floor and (owner.is_on_wall() or owner.is_on_ceiling()):
            if owner.is_on_wall():
                owner.velocity = Vector2(-owner.velocity.x, owner.velocity.y)
            if owner.is_on_ceiling():
                owner.velocity = Vector2(owner.velocity.x, abs(self.bounce_force) * 0.5)


class TriggerComponent(Component):
    """Реакция на вход тела в Area2D: очки, удаление, сигнал."""

    type_name = "Trigger"
    description = "Триггер: очки, удаление объекта, сигнал"
    exported_properties = {
        "points": {"type": "float", "default": 0.0, "min": 0.0, "max": 10000.0, "step": 1.0},
        "stat_name": {"type": "string", "default": "coins"},
        "destroy_target": {"type": "bool", "default": False},
        "destroy_self": {"type": "bool", "default": False},
        "message": {"type": "string", "default": ""},
        "only_player": {"type": "bool", "default": True},
    }
    signals = ["triggered"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.points: float = 0.0
        self.stat_name: str = "coins"
        self.destroy_target: bool = False
        self.destroy_self: bool = False
        self.message: str = ""
        self.only_player: bool = True

    def _ready(self) -> None:
        from engine.nodes.area2d import Area2D
        area = self.owner if isinstance(self.owner, Area2D) else None
        if area is None and self.owner is not None:
            for child in self.owner.get_children():
                if isinstance(child, Area2D):
                    area = child
                    break
        if area is None:
            logger.warning("Trigger: у ноды '%s' нет Area2D",
                           getattr(self.owner, "name", "?"))
            return
        area.connect("body_entered", self._on_body_entered)

    def _on_body_entered(self, body: Any) -> None:
        if body is None:
            return
        if self.only_player and "Player" not in getattr(body, "name", "") \
                and "player" not in getattr(body, "groups", []):
            getter = getattr(body, "get_component", None)
            if not (callable(getter) and getter("Health") is not None):
                return
        if self.points > 0.0:
            add_stat(self.stat_name, self.points)
            add_stat("score", self.points)
        if self.message:
            print(f"[{getattr(self.owner, 'name', 'Trigger')}] {self.message}")
        if self.destroy_target:
            body.queue_free()
        if self.destroy_self and self.owner is not None:
            self.owner.queue_free()
        self.emit_signal("triggered", body)


class PulseComponent(Component):
    """Пульсация масштаба ноды."""

    type_name = "Pulse"
    description = "Пульсация размера (визуальный эффект)"
    exported_properties = {
        "amount": {"type": "float", "default": 0.15, "min": 0.0, "max": 5.0, "step": 0.01},
        "speed": {"type": "float", "default": 4.0, "min": 0.05, "max": 60.0, "step": 0.1},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.amount: float = 0.15
        self.speed: float = 4.0
        self._time: float = 0.0
        self._base: Optional[Vector2] = None

    def _ready(self) -> None:
        if self.owner is not None and hasattr(self.owner, "scale"):
            self._base = Vector2(self.owner.scale)

    def _process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or self._base is None or not hasattr(owner, "scale"):
            return
        self._time += delta
        factor = 1.0 + math.sin(self._time * self.speed) * self.amount
        owner.scale = self._base * factor


class FadeComponent(Component):
    """Плавно гасит прозрачность и удаляет ноду."""

    type_name = "Fade"
    description = "Затухание и удаление ноды"
    exported_properties = {
        "duration": {"type": "float", "default": 1.0, "min": 0.05, "max": 120.0, "step": 0.05},
        "delay": {"type": "float", "default": 0.0, "min": 0.0, "max": 120.0, "step": 0.05},
        "destroy_at_end": {"type": "bool", "default": True},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.duration: float = 1.0
        self.delay: float = 0.0
        self.destroy_at_end: bool = True
        self._time: float = 0.0
        self._base_alpha: float = 255.0

    def _ready(self) -> None:
        if self.owner is not None and hasattr(self.owner, "modulate"):
            modulate = self.owner.modulate
            self._base_alpha = float(modulate[3]) if len(modulate) > 3 else 255.0

    def _process(self, delta: float) -> None:
        owner = self.owner
        if owner is None or not hasattr(owner, "modulate"):
            return
        self._time += delta
        elapsed = self._time - self.delay
        if elapsed < 0.0:
            return
        ratio = min(1.0, elapsed / max(self.duration, 1e-5))
        modulate = tuple(owner.modulate)
        rgb = modulate[:3]
        owner.modulate = (rgb[0], rgb[1], rgb[2], int(self._base_alpha * (1.0 - ratio)))
        if ratio >= 1.0 and self.destroy_at_end:
            owner.queue_free()


class LookAtMouseComponent(Component):
    """Разворачивает ноду в сторону курсора мыши."""

    type_name = "LookAtMouse"
    description = "Поворот ноды к курсору мыши"
    exported_properties = {
        "smooth": {"type": "bool", "default": True},
        "speed": {"type": "float", "default": 8.0, "min": 0.1, "max": 60.0, "step": 0.1},
        "offset": {"type": "float", "default": 0.0, "min": -360.0, "max": 360.0, "step": 1.0},
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.smooth: bool = True
        self.speed: float = 8.0
        self.offset: float = 0.0

    def _process(self, delta: float) -> None:
        owner = self.owner
        input_manager = self._input_manager()
        if owner is None or input_manager is None or not hasattr(owner, "rotation"):
            return
        mouse = input_manager.mouse_position
        camera = self._camera()
        if camera is not None and hasattr(camera, "screen_to_world"):
            world = camera.screen_to_world(mouse)
        else:
            world = mouse
        direction = world - owner.get_global_position()
        if direction.is_zero_approx():
            return
        target = math.degrees(direction.angle) + self.offset
        if self.smooth:
            weight = max(0.0, min(1.0, self.speed * delta))
            owner.rotation += (target - owner.rotation) * weight
        else:
            owner.rotation = target

    def _input_manager(self) -> Any:
        tree = self.get_tree()
        return getattr(tree, "input", None) if tree is not None else None

    def _camera(self) -> Any:
        tree = self.get_tree()
        if tree is not None and tree.render_system is not None:
            return tree.render_system.active_camera
        return None


# ======================================================================
# Реестры
# ======================================================================
#: Все встроенные компоненты.
ALL_COMPONENTS = [
    HealthComponent, LifetimeComponent, RotatorComponent, OscillatorComponent,
    FollowComponent, PatrolComponent, MoveAIComponent, JumperComponent,
    CollectibleComponent, DamageOnTouchComponent, FlashComponent,
    SpawnerComponent, ScoreComponent, PlatformMoverComponent,
    AutoDestroyComponent, BobbingLabelComponent,
    # Дополнительные
    HealthBarComponent, CheckpointComponent, RespawnComponent, HomingComponent,
    ShooterComponent, BounceComponent, TriggerComponent, PulseComponent,
    FadeComponent, LookAtMouseComponent,
]

#: Категории для меню «Добавить компонент».
CATEGORIES: Dict[str, List[str]] = {
    "Геймплей": ["Health", "HealthBar", "DamageOnTouch", "Collectible", "Score",
                 "Trigger", "Checkpoint", "Respawn", "Spawner", "Shooter"],
    "Движение": ["Patrol", "MoveAI", "Follow", "Jumper", "Homing", "Bounce",
                 "Oscillator", "Rotator", "PlatformMover", "Bobbing",
                 "LookAtMouse"],
    "Эффекты": ["Flash", "Pulse", "Fade", "Lifetime", "AutoDestroy"],
}
