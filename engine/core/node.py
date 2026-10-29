"""Базовый класс Node — аналог Godot Node.

Node образует дерево сцены: у каждой ноды есть имя, родитель и список детей.
Ноды поддерживают:
- жизненный цикл (_enter_tree, _ready, _process, _physics_process, _input, _exit_tree);
- сигналы (connect / disconnect / emit_signal);
- экспортируемые свойства (для инспектора и сериализации);
- дублирование и копирование.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Callable, Dict, List, Optional

from engine.core.signal import Signal
from engine.math.vector2 import Vector2
from engine.math.rect2 import Rect2
from engine.math.transform2d import Transform2D

logger = logging.getLogger("cloudengine.node")


def _safe_deepcopy(obj: Any) -> Any:
    """Глубокое копирование, безопасное для движковых объектов.

    Поверхности pygame и прочие ресурсы разделяются по ссылке (не копируются),
    чтобы не ломать кэш ресурсов.
    """
    if obj is None or isinstance(obj, (int, float, str, bool, bytes)):
        return obj
    # Ресурсы pygame разделяем по ссылке.
    try:
        import pygame  # type: ignore
        if isinstance(obj, pygame.Surface):
            return obj
    except Exception:
        pass
    if isinstance(obj, (Vector2, Rect2, Transform2D)):
        return copy.deepcopy(obj)
    if isinstance(obj, (list, dict, tuple, set)):
        try:
            return copy.deepcopy(obj)
        except Exception:
            return obj
    try:
        return copy.deepcopy(obj)
    except Exception:
        return obj


class Node:
    """Базовый узел дерева сцены."""

    #: Экспортируемые свойства: имя -> спецификация для инспектора.
    #: Спецификация: {"type": str, "default": Any, "min": float, "max": float,
    #:               "step": float, "options": list, "hint": str}.
    exported_properties: Dict[str, Dict[str, Any]] = {}

    #: Имена сигналов, объявленных этим классом ноды.
    signals: List[str] = []

    def __init__(self, name: str = "Node") -> None:
        """Создаёт ноду с заданным именем."""
        self.name = name
        self.parent: Optional["Node"] = None
        self._children: List["Node"] = []
        self._scene_tree: Any = None          # ссылка на SceneTree при входе в дерево
        self._signals: Dict[str, Signal] = {}  # лениво создаваемые сигналы
        self._pending_free: bool = False       # флаг queue_free()
        self._inside_tree: bool = False        # нода в активном дереве

        #: Путь к пользовательскому скрипту (относительно проекта).
        self.script_path: str = ""
        #: Группы, в которые входит нода.
        self.groups: List[str] = []
        #: Пользовательские метаданные.
        self.meta: Dict[str, Any] = {}
        #: Владелец (корень сцены) — используется редактором.
        self.owner: Optional["Node"] = None
        #: Флаг обработки _process.
        self.process_enabled: bool = True
        #: Флаг обработки _physics_process.
        self.physics_process_enabled: bool = True
        #: Навешанные компоненты (поведение без скриптов).
        self.components: List[Any] = []

    # ==================================================================
    # Свойства для инспектора и сериализации
    # ==================================================================
    @classmethod
    def get_exported_properties(cls) -> Dict[str, Dict[str, Any]]:
        """Возвращает объединённый словарь экспортируемых свойств по всей MRO."""
        merged: Dict[str, Dict[str, Any]] = {}
        for klass in reversed(cls.__mro__):
            props = getattr(klass, "exported_properties", {}) or {}
            merged.update(props)
        return merged

    @classmethod
    def get_signals(cls) -> List[str]:
        """Возвращает список имён сигналов по всей MRO."""
        result: List[str] = []
        for klass in reversed(cls.__mro__):
            for name in getattr(klass, "signals", []) or []:
                if name not in result:
                    result.append(name)
        return result

    def get_property_list(self) -> Dict[str, Dict[str, Any]]:
        """Свойства конкретного экземпляра (для инспектора)."""
        return {**self.get_exported_properties(), **getattr(self, '_script_exported_properties', {})}

    def get(self, prop: str, default: Any = None) -> Any:
        """Безопасно читает свойство по имени."""
        return getattr(self, prop, default)

    def set(self, prop: str, value: Any) -> None:
        """Устанавливает свойство по имени, приводя типы где возможно."""
        if not hasattr(self, prop):
            setattr(self, prop, value)
            return
        current = getattr(self, prop)
        try:
            if isinstance(current, Vector2) and not isinstance(value, Vector2):
                setattr(self, prop, Vector2(value))
            elif isinstance(current, Rect2) and not isinstance(value, Rect2):
                setattr(self, prop, Rect2(Vector2(value[0]), Vector2(value[1])))
            elif isinstance(current, bool) and not isinstance(value, bool):
                setattr(self, prop, bool(value))
            elif isinstance(current, int) and not isinstance(value, int):
                setattr(self, prop, int(float(value)))
            elif isinstance(current, float) and not isinstance(value, float):
                setattr(self, prop, float(value))
            else:
                setattr(self, prop, value)
        except Exception:
            setattr(self, prop, value)

    # ==================================================================
    # Управление деревом
    # ==================================================================
    def add_child(self, node: "Node", index: int = -1) -> "Node":
        """Добавляет ноду в список детей."""
        if node is self:
            raise ValueError("Нельзя добавить ноду самой себе как ребёнка")
        if node.parent is not None:
            node.parent.remove_child(node)
        if index < 0 or index > len(self._children):
            self._children.append(node)
        else:
            self._children.insert(index, node)
        node.parent = self
        if self._scene_tree is not None:
            self._scene_tree._on_node_added(node)
        return node

    def remove_child(self, node: "Node") -> None:
        """Удаляет ноду из списка детей."""
        if node in self._children:
            self._children.remove(node)
            node.parent = None
            if node._inside_tree and self._scene_tree is not None:
                self._scene_tree._on_node_removed(node)

    def get_children(self) -> List["Node"]:
        """Возвращает список детей."""
        return list(self._children)

    def get_child(self, index: int) -> "Node":
        """Возвращает ребёнка по индексу."""
        return self._children[index]

    def get_child_count(self) -> int:
        """Количество детей."""
        return len(self._children)

    def get_parent(self) -> Optional["Node"]:
        """Возвращает родителя."""
        return self.parent

    def get_index(self) -> int:
        """Индекс ноды среди детей родителя."""
        if self.parent is None:
            return -1
        return self.parent._children.index(self)

    def move_child(self, node: "Node", index: int) -> None:
        """Перемещает ребёнка на новую позицию."""
        if node in self._children:
            self._children.remove(node)
            self._children.insert(max(0, min(index, len(self._children))), node)

    def is_ancestor_of(self, node: "Node") -> bool:
        """True, если данная нода — предок node."""
        current = node.parent
        while current is not None:
            if current is self:
                return True
            current = current.parent
        return False

    def get_node(self, path: str) -> "Node":
        """Находит ноду по относительному/абсолютному пути (как Godot).

        Поддерживает "../" для подъёма и "/root" для абсолютного пути.
        """
        if not path:
            return self
        if path.startswith("/"):
            root = self._get_root()
            return _resolve_path(root, path.lstrip("/"))
        return _resolve_path(self, path)

    def get_path(self) -> str:
        """Возвращает абсолютный путь ноды от корня дерева."""
        parts = [self.name]
        current = self.parent
        while current is not None:
            parts.append(current.name)
            current = current.parent
        return "/" + "/".join(reversed(parts))

    def _get_root(self) -> "Node":
        current = self
        while current.parent is not None:
            current = current.parent
        return current

    def get_tree(self) -> Any:
        """Возвращает SceneTree, в котором находится нода (или None)."""
        if self._scene_tree is not None:
            return self._scene_tree
        # Подъём к корню, если ссылка ещё не проставлена.
        current = self
        while current.parent is not None:
            current = current.parent
        return getattr(current, "_scene_tree", None)

    def is_inside_tree(self) -> bool:
        """True, если нода находится в активном дереве сцены."""
        return self._inside_tree

    def queue_free(self) -> None:
        """Помечает ноду к удалению в конце текущего кадра."""
        self._pending_free = True

    def is_queued_for_deletion(self) -> bool:
        return self._pending_free

    # ==================================================================
    # Сигналы
    # ==================================================================
    def has_signal(self, name: str) -> bool:
        return name in self.get_signals() or name in self._signals

    def connect(self, signal_name: str, callback: Callable) -> None:
        """Подключает колбэк к сигналу по имени."""
        sig = self._signals.get(signal_name)
        if sig is None:
            sig = Signal(self, signal_name)
            self._signals[signal_name] = sig
        sig.connect(callback)

    def disconnect(self, signal_name: str, callback: Callable) -> None:
        sig = self._signals.get(signal_name)
        if sig is not None:
            sig.disconnect(callback)

    def emit_signal(self, signal_name: str, *args, **kwargs) -> None:
        """Вызывает сигнал по имени."""
        sig = self._signals.get(signal_name)
        if sig is not None:
            sig.emit(*args, **kwargs)

    def get_signal(self, signal_name: str) -> Signal:
        """Возвращает объект Signal (создаёт при необходимости)."""
        if signal_name not in self._signals:
            self._signals[signal_name] = Signal(self, signal_name)
        return self._signals[signal_name]

    def notify_group(self, group: str, method: str, *args) -> None:
        """Вызывает метод у всех нод группы."""
        tree = self.get_tree()
        if tree is not None:
            tree.call_group(group, method, *args)

    # ==================================================================
    # Компоненты
    # ==================================================================
    def add_component(self, component: Any, index: int = -1) -> Any:
        """Навешивает компонент на ноду.

        Можно передать как готовый объект Component, так и имя типа ("Health").
        Возвращает добавленный компонент.
        """
        if isinstance(component, str):
            from engine.components.registry import create_component
            component = create_component(component)
            if component is None:
                raise ValueError(f"Неизвестный компонент: {component}")
        if component.owner is not None and component.owner is not self:
            raise ValueError('Компонент уже принадлежит другому объекту')
        if component in self.components:
            return component
        if getattr(component, 'requires_tilemap', False):
            from engine.nodes.tilemap import TileMap
            if not isinstance(self, TileMap):
                raise ValueError('Этот компонент предназначен для TileMap')
        if getattr(component, 'requires_game_object', False):
            from engine.nodes.game_object import GameObject
            from engine.nodes.sprite2d import Sprite2D
            if not isinstance(self, (GameObject, Sprite2D)):
                raise ValueError('Добавляйте компонент на GameObject или Sprite2D')
        existing = self.get_component(component.get_type_name())
        if existing and getattr(component, 'required', False):
            existing.prefab_id = getattr(component, 'prefab_id', getattr(existing, 'prefab_id', ''))
            for prop in component.get_exported_properties():
                if prop != 'enabled':
                    existing.set(prop, getattr(component, prop))
            return existing
        if existing and not getattr(component, 'allow_multiple', True):
            raise ValueError('У объекта уже есть ' + component.get_type_name())
        component.owner = self
        if index < 0 or index > len(self.components):
            self.components.append(component)
        else:
            self.components.insert(index, component)
        if self._inside_tree:
            self._start_component(component)
        return component

    def remove_component(self, component: Any) -> None:
        """Снимает компонент с ноды."""
        if getattr(component, "required", False):
            raise ValueError("Transform обязателен для объекта")
        if component in self.components:
            self.components.remove(component)
            self._stop_component(component)
            component.owner = None

    def get_component(self, comp_type: Any) -> Any:
        """Возвращает первый компонент указанного типа.

        comp_type — класс или имя типа ("Health").
        """
        for comp in self.components:
            if isinstance(comp_type, str):
                getter = getattr(comp, "get_type_name", None)
                if callable(getter) and getter() == comp_type:
                    return comp
            elif isinstance(comp, comp_type):
                return comp
        return None

    def get_components(self, comp_type: Any = None) -> List[Any]:
        """Список компонентов (при необходимости — только заданного типа)."""
        if comp_type is None:
            return list(self.components)
        return [c for c in self.components if
                (c.get_type_name() == comp_type if isinstance(comp_type, str)
                 else isinstance(c, comp_type))]

    def has_component(self, comp_type: Any) -> bool:
        return self.get_component(comp_type) is not None

    def _start_component(self, comp):
        if comp.enabled and not getattr(comp, '_lifecycle_started', False):
            comp._lifecycle_started = True
            _safe_call(comp, '_ready')

    def _stop_component(self, comp):
        if getattr(comp, '_lifecycle_started', False):
            comp._lifecycle_started = False
            _safe_call(comp, '_exit_tree')

    def _ready_components(self) -> None:
        for comp in list(self.components):
            self._start_component(comp)

    def _process_components(self, delta: float) -> None:
        for comp in list(self.components):
            if getattr(comp, "enabled", True):
                _safe_call(comp, "_process", delta)

    def _physics_process_components(self, delta: float) -> None:
        for comp in list(self.components):
            if getattr(comp, "enabled", True):
                _safe_call(comp, "_physics_process", delta)

    def _input_components(self, event: Any) -> None:
        for comp in list(self.components):
            if getattr(comp, "enabled", True):
                _safe_call(comp, "_input", event)

    def _exit_components(self) -> None:
        for comp in list(self.components):
            self._stop_component(comp)

    # ==================================================================
    # Жизненный цикл (переопределяется пользователем)
    # ==================================================================
    def _enter_tree(self) -> None:
        """Вызывается при входе ноды в дерево."""

    def _ready(self) -> None:
        """Вызывается один раз после входа в дерево и готовности детей."""

    def _process(self, delta: float) -> None:
        """Вызывается каждый кадр. delta — время с прошлого кадра в секундах."""

    def _physics_process(self, delta: float) -> None:
        """Вызывается на каждом физическом шаге."""

    def _input(self, event: Any) -> None:
        """Вызывается при получении события ввода."""

    def _exit_tree(self) -> None:
        """Вызывается при выходе ноды из дерева."""

    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        """Отрисовка ноды в локальных координатах (переопределяется)."""

    def draw(self, surface: Any, camera: Any = None) -> None:
        """Рекурсивная отрисовка ноды и её детей."""
        for child in self._children:
            child.draw(surface, camera)

    # ==================================================================
    # Вспомогательные методы
    # ==================================================================
    def find_child(self, pattern: str, recursive: bool = True) -> Optional["Node"]:
        """Находит первого ребёнка по имени (с поддержкой '*' в конце)."""
        for child in self._children:
            if _match_name(child.name, pattern):
                return child
            if recursive:
                found = child.find_child(pattern, recursive)
                if found is not None:
                    return found
        return None

    def find_children(self, pattern: str, recursive: bool = True) -> List["Node"]:
        """Находит всех детей по шаблону имени."""
        result: List["Node"] = []
        for child in self._children:
            if _match_name(child.name, pattern):
                result.append(child)
            if recursive:
                result.extend(child.find_children(pattern, recursive))
        return result

    def get_children_in_group(self, group: str) -> List["Node"]:
        result: List["Node"] = []
        for child in self._children:
            if group in child.groups:
                result.append(child)
            result.extend(child.get_children_in_group(group))
        return result

    def duplicate(self, deep: bool = True) -> "Node":
        """Создаёт копию ноды (и детей при deep=True)."""
        new = self.__class__()
        new.name = self.name
        new.script_path = self.script_path
        new.groups = list(self.groups)
        new.meta = _safe_deepcopy(self.meta)
        new.process_enabled = self.process_enabled
        new.physics_process_enabled = self.physics_process_enabled
        # Копируем компоненты.
        for comp in self.components:
            try:
                new.add_component(comp.duplicate())
            except Exception:
                logger.exception("Не удалось скопировать компонент %r", comp)
        # Копируем экспортируемые свойства.
        for prop in self.get_property_list():
            if prop in ("name", "script"):
                continue
            if hasattr(self, prop):
                new.set(prop, _safe_deepcopy(getattr(self, prop)))
        # Копируем остальные простые атрибуты (не попавшие в экспорт).
        _skip = {"name", "parent", "_children", "_scene_tree", "_signals",
                 "_pending_free", "_inside_tree", "owner"}
        for key, value in self.__dict__.items():
            if key in _skip or key.startswith("_"):
                continue
            if not hasattr(new, key):
                new.__dict__[key] = _safe_deepcopy(value)
        if deep:
            for child in self._children:
                new.add_child(child.duplicate(deep))
        return new

    def __repr__(self) -> str:
        return f"<{type(self).__name__} '{self.name}'>"


def _safe_call(obj: Any, method: str, *args) -> None:
    """Вызывает метод объекта, перехватывая ошибки (чтобы не ронять цикл)."""
    fn = getattr(obj, method, None)
    if not callable(fn):
        return
    try:
        fn(*args)
    except Exception:
        logger.exception("Ошибка %s у %r", method, obj)
        if getattr(obj, 'type_name', '') == 'ScriptBehaviour' and method != '_exit_tree':
            obj.enabled = False
            logger.error('ScriptBehaviour %s отключён после ошибки. Исправьте скрипт и запустите сцену заново.',
                         getattr(obj, 'script_path', ''))


def _match_name(name: str, pattern: str) -> bool:
    """Сравнение имени с шаблоном (поддержка суффикса '*')."""
    if pattern.endswith("*"):
        return name.startswith(pattern[:-1])
    return name == pattern


def _resolve_path(start: "Node", path: str) -> "Node":
    """Разрешает путь вида "A/B/C" с поддержкой "../" и "."."""
    current: Optional["Node"] = start
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent if current is not None else None
        else:
            if current is None:
                raise ValueError(f"Нода не найдена: {path!r}")
            found = None
            for child in current._children:
                if child.name == part:
                    found = child
                    break
            if found is None:
                raise ValueError(f"Нода не найдена: {path!r}")
            current = found
    if current is None:
        raise ValueError(f"Нода не найдена: {path!r}")
    return current
