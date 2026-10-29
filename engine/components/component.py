"""Базовый класс Component.

Компонент живёт внутри ноды-владельца и получает те же события жизненного
цикла. У каждого компонента свои сигналы и экспортируемые свойства, поэтому
он полностью редактируется в инспекторе.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Callable, Dict, List, Optional

from engine.core.signal import Signal
from engine.math.vector2 import Vector2
from engine.math.rect2 import Rect2

logger = logging.getLogger("cloudengine.component")


class Component:
    """Базовый компонент."""

    #: Имя типа для реестра и сериализации.
    type_name: str = "Component"
    #: Описание для палитры редактора.
    description: str = ""
    #: Экспортируемые свойства (как у Node).
    exported_properties: Dict[str, Dict[str, Any]] = {}
    #: Имена сигналов компонента.
    signals: List[str] = []

    def __init__(self, **kwargs: Any) -> None:
        #: Нода-владелец (проставляется при добавлении).
        self.owner: Any = None
        #: Выключенный компонент не обновляется.
        self.enabled: bool = True
        self._signals: Dict[str, Signal] = {}
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def enabled(self):
        return getattr(self, '_enabled', True)

    @enabled.setter
    def enabled(self, value):
        old = getattr(self, '_enabled', True)
        self._enabled = bool(value)
        owner = getattr(self, 'owner', None)
        if old != self._enabled and owner is not None and getattr(owner, '_inside_tree', False):
            if self._enabled:
                owner._start_component(self)
            else:
                owner._stop_component(self)

    # ==================================================================
    # Свойства и сериализация
    # ==================================================================
    @classmethod
    def get_type_name(cls) -> str:
        """Имя типа компонента."""
        return cls.type_name or cls.__name__

    @classmethod
    def get_exported_properties(cls) -> Dict[str, Dict[str, Any]]:
        """Объединённые экспортируемые свойства по всей MRO."""
        merged: Dict[str, Dict[str, Any]] = {}
        for klass in reversed(cls.__mro__):
            merged.update(getattr(klass, "exported_properties", {}) or {})
        # enabled есть у всех компонентов.
        merged.setdefault("enabled", {"type": "bool", "default": True})
        return merged

    @classmethod
    def get_signals(cls) -> List[str]:
        result: List[str] = []
        for klass in reversed(cls.__mro__):
            for name in getattr(klass, "signals", []) or []:
                if name not in result:
                    result.append(name)
        return result

    def get(self, prop: str, default: Any = None) -> Any:
        return getattr(self, prop, default)

    def set(self, prop: str, value: Any) -> None:
        """Устанавливает свойство с приведением типов."""
        current = getattr(self, prop, None)
        try:
            if isinstance(current, Vector2) and not isinstance(value, Vector2):
                value = Vector2(value)
            elif isinstance(current, Rect2) and not isinstance(value, Rect2):
                value = Rect2(Vector2(value[0]), Vector2(value[1]))
            elif isinstance(current, bool) and not isinstance(value, bool):
                value = bool(value)
            elif isinstance(current, int) and not isinstance(current, bool) \
                    and not isinstance(value, int):
                value = int(float(value))
            elif isinstance(current, float) and not isinstance(value, float):
                value = float(value)
        except Exception:
            pass
        setattr(self, prop, value)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация компонента (для .scene)."""
        from engine.resources.scene_serializer import value_to_json
        props: Dict[str, Any] = {}
        for prop in self.get_exported_properties():
            if hasattr(self, prop):
                props[prop] = value_to_json(getattr(self, prop))
        data: Dict[str, Any] = {"type": self.get_type_name(), "properties": props}
        if getattr(self, 'prefab_id', ''):
            data['prefab_id'] = self.prefab_id
        extra = self._serialize_data()
        if extra:
            # Данные тоже приводим к JSON: внутри могут быть Vector2.
            data["data"] = value_to_json(extra)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["Component"]:
        """Восстановление компонента из словаря."""
        from engine.components.registry import get_component_class
        type_name = data.get("type", "")
        comp_class = get_component_class(type_name)
        if comp_class is None:
            from engine.resources.legacy_components import legacy_component_class
            comp_class = legacy_component_class(type_name)
        if comp_class is None:
            logger.warning("Неизвестный компонент: %s", type_name)
            return None
        component = comp_class()
        component.prefab_id = data.get("prefab_id", "")
        spec = comp_class.get_exported_properties()
        for prop, value in (data.get("properties") or {}).items():
            component.set(prop, _convert(value, (spec.get(prop) or {}).get("type")))
        if "data" in data:
            try:
                component._deserialize_data(data["data"])
            except Exception:
                logger.exception("Ошибка данных компонента %s", type_name)
        return component

    def duplicate(self) -> "Component":
        """Копия компонента."""
        new = self.__class__()
        for prop in self.get_exported_properties():
            if hasattr(self, prop):
                new.set(prop, copy.deepcopy(getattr(self, prop)))
        new._deserialize_data(copy.deepcopy(self._serialize_data()))
        return new

    # ==================================================================
    # Сигналы
    # ==================================================================
    def connect(self, signal_name: str, callback: Callable) -> None:
        """Подключает колбэк к сигналу компонента."""
        if signal_name not in self._signals:
            self._signals[signal_name] = Signal(self, signal_name)
        self._signals[signal_name].connect(callback)

    def disconnect(self, signal_name: str, callback: Callable) -> None:
        sig = self._signals.get(signal_name)
        if sig is not None:
            sig.disconnect(callback)

    def emit_signal(self, signal_name: str, *args, **kwargs) -> None:
        """Испускает сигнал компонента."""
        sig = self._signals.get(signal_name)
        if sig is not None:
            sig.emit(*args, **kwargs)

    # ==================================================================
    # Доступ к сцене
    # ==================================================================
    def get_owner(self) -> Any:
        return self.owner

    def get_tree(self) -> Any:
        return self.owner.get_tree() if self.owner is not None else None

    def get_scene(self) -> Any:
        tree = self.get_tree()
        return tree.current_scene if tree is not None else None

    def get_node(self, path: str) -> Any:
        """Нода по пути относительно владельца (или абсолютному)."""
        if self.owner is None:
            return None
        try:
            return self.owner.get_node(path)
        except Exception:
            return None

    def find_node(self, path: str) -> Any:
        """Нода по пути от корня сцены."""
        scene = self.get_scene()
        if scene is None:
            return None
        return scene.find_node_by_path(path)

    def get_component(self, comp_type: Any) -> Any:
        """Компонент указанного типа у владельца."""
        if self.owner is None:
            return None
        getter = getattr(self.owner, "get_component", None)
        return getter(comp_type) if callable(getter) else None

    # ==================================================================
    # Жизненный цикл (переопределяется)
    # ==================================================================
    def _ready(self) -> None:
        """Вызывается, когда нода-владелец готова."""

    def _process(self, delta: float) -> None:
        """Каждый кадр."""

    def _physics_process(self, delta: float) -> None:
        """Каждый физический шаг."""

    def _input(self, event: Any) -> None:
        """Событие ввода."""

    def _exit_tree(self) -> None:
        """Владелец покидает дерево."""

    # ==================================================================
    # Доп. данные для наследников
    # ==================================================================
    def _serialize_data(self) -> Dict[str, Any]:
        return {}

    def _deserialize_data(self, data: Dict[str, Any]) -> None:
        return

    def __repr__(self) -> str:
        owner = getattr(self.owner, "name", None)
        return f"<{self.get_type_name()} owner={owner}>"


def _convert(value: Any, value_type: Optional[str]) -> Any:
    """Приведение JSON-значения к типу свойства."""
    try:
        if value_type == "vector2":
            return Vector2(value)
        if value_type == "rect2":
            return Rect2(Vector2(value[0]), Vector2(value[1]))
        if value_type == "color":
            return tuple(int(v) for v in value) if isinstance(value, (list, tuple)) else value
        if value_type == "points":
            return [Vector2(p) for p in (value or [])]
    except Exception:
        pass
    return value
