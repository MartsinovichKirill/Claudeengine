"""AnimationPlayer — анимации по ключевым кадрам.

В отличие от AnimatedSprite2D (покадровая смена картинок), AnimationPlayer
анимирует **свойства объектов во времени**: позицию, поворот, масштаб, цвет,
прозрачность, видимость и любые другие экспортируемые свойства ноды.

Пример:
    player = AnimationPlayer("Anim")
    player.add_animation("jump", 0.6)
    player.add_key("jump", "position", 0.0, Vector2(0, 0))
    player.add_key("jump", "position", 0.3, Vector2(0, -90), "out")
    player.add_key("jump", "position", 0.6, Vector2(0, 0), "in")
    player.play("jump")

Анимации сохраняются в файл сцены (поле ``data``).
"""

from __future__ import annotations

import logging
import copy
import math
from typing import Any, Dict, List, Optional, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.animation_player")

#: Доступные способы сглаживания.
EASINGS: Tuple[str, ...] = ("linear", "in", "out", "in_out", "step", "bounce")

#: Свойства, которые предлагаются в редакторе анимаций по умолчанию.
COMMON_PROPERTIES: Tuple[str, ...] = (
    "position", "rotation", "scale", "modulate", "visible", "z_index",
    "texture_path", "color", "font_size",
)


def property_target(target, path):
    """Resolve node properties or ComponentName.property tracks."""
    parts = path.split('.')
    if len(parts) == 2:
        component = target.get_component(parts[0]) if target is not None else None
        return component, parts[1]
    return target, path


def read_property(target, path, default=None):
    owner, prop = property_target(target,path)
    return getattr(owner,prop,default)


def write_property(target, path, value):
    owner, prop = property_target(target,path)
    if owner is not None and hasattr(owner,prop) and not prop.startswith('_'):
        setter=getattr(owner,'set_'+prop,None)
        if callable(setter): setter(value)
        else: owner.set(prop,value)


def apply_easing(t: float, easing: str) -> float:
    """Преобразует линейный прогресс 0..1 согласно сглаживанию."""
    t = max(0.0, min(1.0, t))
    if easing == "step":
        return 0.0 if t < 1.0 else 1.0
    if easing == "in":
        return t * t
    if easing == "out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    if easing == "in_out":
        return 2.0 * t * t if t < 0.5 else 1.0 - 2.0 * (1.0 - t) * (1.0 - t)
    if easing == "bounce":
        return 1.0 - math.pow(1.0 - t, 3.0)
    return t


def _lerp_value(a: Any, b: Any, t: float) -> Any:
    """Интерполяция значения произвольного типа."""
    if isinstance(a, Vector2) or isinstance(b, Vector2):
        first = a if isinstance(a, Vector2) else Vector2(a, a)
        second = b if isinstance(b, Vector2) else Vector2(b, b)
        return first.lerp(second, t)
    if isinstance(a, bool) or isinstance(b, bool):
        return a if t < 1.0 else b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        value = a + (b - a) * t
        return int(round(value)) if isinstance(a, int) and isinstance(b, int) else value
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b):
        return tuple(
            int(round(x + (y - x) * t)) if isinstance(x, int) and isinstance(y, int)
            else x + (y - x) * t
            for x, y in zip(a, b)
        )
    return a if t < 1.0 else b


class Animation:
    """Набор ключевых кадров одного действия."""

    def __init__(self, name: str = "new", length: float = 1.0,
                 loop: bool = False) -> None:
        self.name: str = name
        self.length: float = max(0.01, float(length))
        self.loop: bool = loop
        #: Свойство -> список ключей [время, значение, сглаживание].
        self.keys: Dict[str, List[List[Any]]] = {}
        self.events: List[Dict[str, Any]] = []

    def add_event(self, time: float, name: str, args=None, kind: str = 'method') -> None:
        """Place a method call or signal marker on the clip, without executing it."""
        import copy
        import json
        time = float(time)
        if not math.isfinite(time) or time < 0 or time > self.length:
            raise ValueError('Время события должно находиться внутри анимации')
        if not name.isidentifier() or name.startswith('_'):
            raise ValueError('Укажите имя публичного метода или сигнала')
        if kind not in ('method', 'signal'):
            raise ValueError('Неизвестный тип события')
        args = [] if args is None else args
        if not isinstance(args, list):
            raise ValueError('Аргументы события должны быть JSON-массивом')
        json.dumps(args, allow_nan=False)
        self.events.append({'time': time, 'name': name, 'args': copy.deepcopy(args), 'kind': kind})
        self.events.sort(key=lambda event: event['time'])

    # ------------------------------------------------------------------
    def add_key(self, prop: str, time: float, value: Any,
                easing: str = "linear") -> None:
        """Добавляет или заменяет ключ свойства."""
        keys = self.keys.setdefault(prop, [])
        time = max(0.0, float(time))
        for key in keys:
            if abs(key[0] - time) < 1e-6:
                key[1] = value
                key[2] = easing
                keys.sort(key=lambda item: item[0])
                return
        keys.append([time, value, easing])
        keys.sort(key=lambda item: item[0])

    def remove_key(self, prop: str, index: int) -> None:
        keys = self.keys.get(prop)
        if keys and 0 <= index < len(keys):
            keys.pop(index)
            if not keys:
                self.keys.pop(prop, None)

    def value_at(self, prop: str, time: float, fallback: Any = None) -> Any:
        """Значение свойства в момент времени."""
        keys = self.keys.get(prop)
        if not keys:
            return fallback
        if time <= keys[0][0]:
            return keys[0][1]
        if time >= keys[-1][0]:
            return keys[-1][1]
        for index in range(len(keys) - 1):
            current = keys[index]
            following = keys[index + 1]
            if current[0] <= time <= following[0]:
                span = following[0] - current[0]
                if span <= 1e-9:
                    return following[1]
                progress = (time - current[0]) / span
                progress = apply_easing(progress, current[2] or "linear")
                return _lerp_value(current[1], following[1], progress)
        return keys[-1][1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "length": self.length,
            "loop": self.loop,
            "events": copy.deepcopy(self.events),
            "keys": {prop: [list(key) for key in keys]
                     for prop, keys in self.keys.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Animation":
        animation = cls(data.get("name", "anim"), data.get("length", 1.0),
                        bool(data.get("loop", False)))
        for prop, keys in (data.get("keys") or {}).items():
            for key in keys:
                try:
                    value = key[1]
                    if isinstance(value, (list, tuple)) and len(value) == 2 \
                            and prop not in ("modulate",):
                        value = Vector2(value)
                    animation.add_key(prop, key[0], value,
                                      key[2] if len(key) > 2 else "linear")
                except Exception:
                    logger.exception("Повреждённый ключ анимации %s", prop)
        for event in data.get('events', []):
            animation.add_event(event['time'], event['name'], event.get('args', []), event.get('kind', 'method'))
        return animation


class AnimationPlayer(Node):
    """Проигрывает анимации по ключевым кадрам."""

    type_name = "AnimationPlayer"
    description = "Анимации по ключевым кадрам: позиция, поворот, цвет"
    signals = ["finished", "started", "animation_changed", "animation_event"]

    exported_properties = {
        "autoplay": {"type": "string", "default": ""},
        "speed": {"type": "float", "default": 1.0, "min": 0.01, "max": 10.0, "step": 0.05},
        "root_path": {"type": "string", "default": ""},
        "reset_on_play": {"type": "bool", "default": True},
    }

    def __init__(self, name: str = "AnimationPlayer") -> None:
        super().__init__(name)
        self.autoplay: str = ""
        self.speed: float = 1.0
        #: Путь к ноде, которой управляем (пусто — родитель, иначе сама нода).
        self.root_path: str = ""
        self.reset_on_play: bool = True

        #: Имя -> Animation.
        self.animations: Dict[str, Animation] = {}
        self.current_animation: str = ""
        self.current_time: float = 0.0
        self.playing: bool = False
        self._queue: str = ""
        self._saved: Dict[str, Any] = {}
        self._finished_emitted: bool = False
        self._event_start_pending = False
        self._playback_revision = 0
        self._saved_target = None

    # ==================================================================
    # Авторство анимаций
    # ==================================================================
    def add_animation(self, name: str, length: float = 1.0,
                      loop: bool = False) -> Animation:
        """Создаёт (или заменяет) анимацию."""
        animation = Animation(name, length, loop)
        self.animations[name] = animation
        return animation

    def get_animation(self, name: str) -> Optional[Animation]:
        return self.animations.get(name)

    def remove_animation(self, name: str) -> None:
        self.animations.pop(name, None)
        if self.current_animation == name:
            self.stop()

    def add_key(self, animation: str, prop: str, time: float, value: Any,
                easing: str = "linear") -> Animation:
        """Добавляет ключ в анимацию (создаёт её при необходимости)."""
        target = self.animations.get(animation)
        if target is None:
            target = self.add_animation(animation, max(time, 1.0))
        target.add_key(prop, time, value, easing)
        if time > target.length:
            target.length = time
        return target

    def animation_names(self) -> List[str]:
        return sorted(self.animations.keys())

    # ==================================================================
    # Управление воспроизведением
    # ==================================================================
    def play(self, name: str = "", restart: bool = True) -> bool:
        """Запускает анимацию по имени."""
        name = name or self.current_animation or \
            (self.animation_names()[0] if self.animations else "")
        if name not in self.animations:
            if name:
                logger.warning("AnimationPlayer '%s': нет анимации '%s'",
                               self.name, name)
            return False
        if self.playing and self.current_animation == name and not restart:
            return True
        if self.reset_on_play and self.current_animation != name:
            self._restore_saved()
        self.current_animation = name
        self.current_time = 0.0
        self._playback_revision += 1
        self._event_start_pending = True
        self.playing = True
        self._finished_emitted = False
        self._capture_saved()
        self.emit_signal("started", name)
        self.emit_signal("animation_changed", name)
        return True

    def queue(self, name: str) -> None:
        """Ставит анимацию следующей после текущей."""
        self._queue = name

    def stop(self) -> None:
        """Останавливает воспроизведение."""
        self.playing = False
        self._playback_revision += 1
        self._queue = ""

    def pause(self) -> None:
        self.playing = False

    def resume(self) -> None:
        if self.current_animation:
            self.playing = True

    def seek(self, time: float) -> None:
        """Переходит к указанному моменту времени."""
        self._playback_revision += 1
        self._event_start_pending = False
        self.current_time = min(self.duration(), max(0.0, float(time)))
        self._apply(self.current_time)

    def is_playing(self) -> bool:
        return self.playing

    def duration(self, name: str = "") -> float:
        animation = self.animations.get(name or self.current_animation)
        return animation.length if animation is not None else 0.0

    # ==================================================================
    # Жизненный цикл ноды
    # ==================================================================
    def _ready(self) -> None:
        if self.autoplay:
            self.play(self.autoplay)

    def _process(self, delta: float) -> None:
        if not self.playing or not self.current_animation:
            return
        animation = self.animations.get(self.current_animation)
        if animation is None:
            self.playing = False
            return

        advance = float(delta) * max(self.speed, 0.0)
        if not math.isfinite(advance) or advance <= 0:
            return
        start, end = self.current_time, self.current_time + advance
        span = max(0.01, animation.length)
        if not animation.loop or self._queue:
            end = min(end, span)
        revision = self._playback_revision
        pending = self._event_start_pending
        self._event_start_pending = False
        count = 0
        # Include zero only on play and on entry to a new loop; seeking is silent.
        loops = int(end // span) if animation.loop and not self._queue else 0
        if animation.events and loops > 10000:
            raise RuntimeError('Слишком большой шаг времени для событий анимации')
        for cycle in range(loops + 1) if animation.events else ():
            for event in list(animation.events):
                when = cycle * span + event['time']
                if (start < when <= end) or (pending and cycle == 0 and when == start == 0):
                    count += 1
                    if count > 10000:
                        raise RuntimeError('Слишком много событий анимации за один кадр')
                    self.current_time = event['time']
                    self._apply(self.current_time)
                    self._dispatch_event(event)
                    if revision != self._playback_revision or not self.playing:
                        return
        if end >= span and self._queue:
            queued = self._queue
            self._queue = ''
            self.play(queued)
            return
        self.current_time = end % span if animation.loop else end
        self._apply(self.current_time)
        if not animation.loop and end >= span:
            self.playing = False
            if not self._finished_emitted:
                self._finished_emitted = True
                self.emit_signal('finished', self.current_animation)

    def _dispatch_event(self, event):
        from copy import deepcopy
        args = deepcopy(event.get('args', []))
        name = event['name']
        if event.get('kind') == 'signal':
            self.emit_signal('animation_event', name, args)
            return
        target = self.target_node()
        receivers = [getattr(target, name, None)]
        for component in getattr(target, 'components', []):
            if component.enabled:
                receivers.append(getattr(getattr(component, 'instance', component), name, None))
        methods = [method for method in receivers if callable(method)]
        if len(methods) != 1:
            raise ValueError(f'Событие «{name}» анимации «{self.current_animation}»: '
                             f'ожидается один метод у «{getattr(target, "name", "?")}», найдено {len(methods)}')
        methods[0](*args)

    def _exit_tree(self) -> None:
        self._restore_saved()

    # ==================================================================
    # Применение значений
    # ==================================================================
    def target_node(self) -> Any:
        """Нода, свойства которой анимируются."""
        if self.root_path:
            found = self._resolve(self.root_path)
            if found is not None:
                return found
        return self.parent if self.parent is not None else self

    def _resolve(self, path: str) -> Any:
        """Нода сцены по пути (относительно корня сцены)."""
        tree = self.get_tree()
        scene = getattr(tree, "current_scene", None) if tree is not None else None
        if scene is None:
            return None
        try:
            return scene.find_node_by_path(path)
        except Exception:
            return None

    def _capture_saved(self) -> None:
        """Запоминает исходные значения свойств (для возврата)."""
        target = self.target_node()
        if target is None:
            return
        self._saved_target = target
        for prop in self.animations.get(self.current_animation, Animation()).keys:
            if prop not in self._saved:
                value = read_property(target, prop)
                if value is not None:
                    from copy import deepcopy
                    try:
                        self._saved[prop] = deepcopy(value)
                    except Exception:
                        self._saved[prop] = value

    def _restore_saved(self) -> None:
        """Возвращает свойства к значениям до анимации."""
        target = self._saved_target or self.target_node()
        if target is None or not self._saved:
            return
        for prop, value in self._saved.items():
            try:
                write_property(target, prop, value)
            except Exception:
                pass
        self._saved.clear()
        self._saved_target = None

    def _apply(self, time: float) -> None:
        """Применяет значения анимации к целевой ноде."""
        animation = self.animations.get(self.current_animation)
        target = self.target_node()
        if animation is None or target is None:
            return
        for prop, keys in animation.keys.items():
            if not keys:
                continue
            current = read_property(target, prop)
            value = animation.value_at(prop, time, current)
            if value is None:
                continue
            try:
                write_property(target, prop, value)
            except Exception:
                logger.exception("AnimationPlayer '%s': свойство %s", self.name, prop)

    # ==================================================================
    # Сериализация
    # ==================================================================
    def _serialize_data(self) -> Dict[str, Any]:
        return {"autoplay": self.autoplay, "animations": {name: anim.to_dict()
                               for name, anim in self.animations.items()}}

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        if 'autoplay' in data:
            self.autoplay = data['autoplay']
        self.animations = {}
        for name, raw in (data.get("animations") or {}).items():
            try:
                self.animations[name] = Animation.from_dict(raw)
            except Exception:
                logger.exception("Не удалось прочитать анимацию %s", name)


__all__ = ["AnimationPlayer", "Animation", "EASINGS", "COMMON_PROPERTIES",
           "apply_easing"]
