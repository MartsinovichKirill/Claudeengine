"""UndoStack — стек отмены/повтора операций редактора.

Каждая команда реализует undo()/redo(). Используется для всех операций
над сценой: добавление/удаление/дублирование нод, изменение свойств,
перемещение в иерархии.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional

logger = logging.getLogger("cloudengine.undo")


class UndoCommand:
    """Базовая команда отмены."""

    def __init__(self, text: str = "") -> None:
        self.text = text

    def undo(self) -> None:
        raise NotImplementedError

    def redo(self) -> None:
        raise NotImplementedError


class ParticleSettingsCommand(UndoCommand):
    def __init__(self, node, before, after):
        super().__init__('Настройки частиц')
        import copy
        self.node=node; self.before=copy.deepcopy(before); self.after=copy.deepcopy(after)

    def _apply(self, values):
        from editor.particle_editor import apply_particle_values
        apply_particle_values(self.node,values)
        self.node.restart()
        self.node.emitting=values.get('emitting',True)
        if self.node._asset_manager: self.node.set_asset_manager(self.node._asset_manager)

    def undo(self): self._apply(self.before)
    def redo(self): self._apply(self.after)


class NodeDataCommand(UndoCommand):
    """Изменение спец. данных ноды (анимации, точки пути и т.п.)."""

    def __init__(self, node: Any, old_data: dict, new_data: dict,
                 text: str = "Изменить данные") -> None:
        super().__init__(text)
        self.node = node
        self.old_data = old_data
        self.new_data = new_data

    def _apply(self, data: dict) -> None:
        try:
            self.node._deserialize_data(data)
        except Exception:
            logger.exception("Не удалось применить данные ноды %s",
                             getattr(self.node, "name", "?"))

    def undo(self) -> None:
        self._apply(self.old_data)

    def redo(self) -> None:
        self._apply(self.new_data)


class MultiPropertyCommand(UndoCommand):
    """Изменение одного свойства сразу у нескольких нод (групповое действие)."""

    def __init__(self, changes: list, prop: str = "position",
                 text: str = "Переместить объекты") -> None:
        #: Список (нода, старое значение, новое значение).
        super().__init__(text or f"Изменить {prop}")
        self.prop = prop
        self.changes = list(changes)

    def _apply(self, index: int) -> None:
        for node, old_value, new_value in self.changes:
            try:
                node.set(self.prop, (old_value, new_value)[index])
            except Exception:
                logger.exception("Не удалось применить %s у %s",
                                 self.prop, getattr(node, "name", "?"))

    def undo(self) -> None:
        self._apply(0)

    def redo(self) -> None:
        self._apply(1)


class TileEditCommand(UndoCommand):
    """Изменение тайловой карты (кисть, ластик, заливка, прямоугольник)."""

    def __init__(self, tilemap: Any, before: dict, after: dict,
                 text: str = "Рисование по тайлам") -> None:
        super().__init__(text)
        self.tilemap = tilemap
        self.before = before
        self.after = after

    def _apply(self, snapshot: dict) -> None:
        restore = getattr(self.tilemap, "restore", None)
        if callable(restore):
            restore(snapshot)
        else:
            self.tilemap.cells = dict(snapshot)

    def undo(self) -> None:
        self._apply(self.before)

    def redo(self) -> None:
        self._apply(self.after)


class PropertyCommand(UndoCommand):
    """Изменение свойства ноды."""

    def __init__(self, node: Any, prop: str, old_value: Any, new_value: Any,
                 text: str = "") -> None:
        super().__init__(text or f"Изменить {prop}")
        self.node = node
        self.prop = prop
        self.old_value = old_value
        self.new_value = new_value

    def _apply(self, value: Any) -> None:
        try:
            self.node.set(self.prop, value)
        except Exception:
            pass

    def undo(self) -> None:
        self._apply(self.old_value)

    def redo(self) -> None:
        self._apply(self.new_value)


class AddNodeCommand(UndoCommand):
    """Добавление ноды."""

    def __init__(self, parent: Any, node: Any, index: int = -1) -> None:
        super().__init__(f"Добавить {node.name}")
        self.parent = parent
        self.node = node
        self.index = index

    def undo(self) -> None:
        if self.node.parent is not None:
            self.node.parent.remove_child(self.node)

    def redo(self) -> None:
        self.parent.add_child(self.node, self.index)


class RemoveNodeCommand(UndoCommand):
    """Удаление ноды."""

    def __init__(self, parent: Any, node: Any, index: int = -1) -> None:
        super().__init__(f"Удалить {node.name}")
        self.parent = parent
        self.node = node
        if index < 0 and parent is not None:
            index = parent.get_child_count()
        self.index = index

    def undo(self) -> None:
        self.parent.add_child(self.node, self.index)

    def redo(self) -> None:
        if self.node.parent is not None:
            self.node.parent.remove_child(self.node)


class MoveNodeCommand(UndoCommand):
    """Перемещение ноды в иерархии (пересадка к новому родителю)."""

    def __init__(self, node: Any, old_parent: Any, new_parent: Any,
                 old_index: int, new_index: int) -> None:
        super().__init__(f"Переместить {node.name}")
        self.node = node
        self.old_parent = old_parent
        self.new_parent = new_parent
        self.old_index = old_index
        self.new_index = new_index

    def _move(self, parent: Any, index: int) -> None:
        if self.node.parent is not None:
            self.node.parent.remove_child(self.node)
        parent.add_child(self.node, index)

    def undo(self) -> None:
        self._move(self.old_parent, self.old_index)

    def redo(self) -> None:
        self._move(self.new_parent, self.new_index)


class ComponentPropertyCommand(UndoCommand):
    """Изменение свойства компонента."""

    def __init__(self, component: Any, prop: str, old_value: Any, new_value: Any,
                 text: str = "") -> None:
        super().__init__(text or f"Изменить {prop}")
        self.component = component
        self.prop = prop
        self.old_value = old_value
        self.new_value = new_value

    def _apply(self, value: Any) -> None:
        try:
            self.component.set(self.prop, value)
        except Exception:
            pass

    def undo(self) -> None:
        self._apply(self.old_value)

    def redo(self) -> None:
        self._apply(self.new_value)


class AddComponentCommand(UndoCommand):
    """Навешивание компонента на ноду."""

    def __init__(self, node: Any, component: Any) -> None:
        super().__init__(f"Добавить компонент {component.get_type_name()}")
        self.node = node
        self.component = component

    def undo(self) -> None:
        self.node.remove_component(self.component)

    def redo(self) -> None:
        self.node.add_component(self.component)


class RemoveComponentCommand(UndoCommand):
    """Снятие компонента с ноды."""

    def __init__(self, node: Any, component: Any, index: int = -1) -> None:
        super().__init__(f"Удалить компонент {component.get_type_name()}")
        self.node = node
        self.component = component
        if index < 0:
            try:
                index = list(node.components).index(component)
            except ValueError:
                index = len(node.components)
        self.index = index

    def undo(self) -> None:
        self.node.add_component(self.component, self.index)

    def redo(self) -> None:
        self.node.remove_component(self.component)


class UndoStack:
    """Стек отмены/повтора."""

    def __init__(self, limit: int = 200) -> None:
        self._undo: List[UndoCommand] = []
        self._redo: List[UndoCommand] = []
        self._limit = limit
        self.on_change: Optional[Callable] = None  # оповещение UI

    def push(self, command: UndoCommand) -> None:
        """Добавляет УЖЕ выполненную команду и очищает стек повтора."""
        self._undo.append(command)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()
        self._notify()

    def execute(self, command: UndoCommand) -> None:
        """Выполняет команду и добавляет её в стек отмены.

        Используется редактором: операция выполняется один раз, а повтор —
        через redo().
        """
        try:
            command.redo()
        except Exception:
            logger.exception("Ошибка выполнения команды: %s", command.text)
            return False
        self.push(command)
        return True

    def undo(self) -> None:
        if not self._undo:
            return
        command = self._undo.pop()
        try:
            command.undo()
            self._redo.append(command)
        except Exception:
            logger.exception("Ошибка undo: %s", command.text)
        self._notify()

    def redo(self) -> None:
        if not self._redo:
            return
        command = self._redo.pop()
        try:
            command.redo()
            self._undo.append(command)
        except Exception:
            logger.exception("Ошибка redo: %s", command.text)
        self._notify()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._notify()

    def _notify(self) -> None:
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:
                pass


class ComponentValuesCommand(UndoCommand):
    def __init__(self, component, before, after):
        super().__init__('Настройки ' + component.get_type_name())
        import copy
        self.component = component
        self.before = copy.deepcopy(before)
        self.after = copy.deepcopy(after)
    def _apply(self, data):
        from engine.components.component import Component
        restored = Component.from_dict(data)
        if restored is None:
            raise ValueError('Неизвестный тип компонента')
        import copy
        for name in restored.get_exported_properties():
            if name == 'enabled' and getattr(self.component, 'required', False):
                continue
            self.component.set(name, copy.deepcopy(getattr(restored, name)))
        self.component._deserialize_data(restored._serialize_data())
    def redo(self):
        self._apply(self.after)
    def undo(self):
        self._apply(self.before)

class ReorderComponentCommand(UndoCommand):
    def __init__(self, node, component, index):
        super().__init__('Порядок компонентов')
        self.node, self.component = node, component
        self.before = node.components.index(component)
        self.after = max(1 if node.get_component('Transform') else 0, min(index, len(node.components)-1))
    def _apply(self, index):
        self.node.components.remove(self.component)
        self.node.components.insert(index, self.component)
    def redo(self):
        self._apply(self.after)
    def undo(self):
        self._apply(self.before)
