"""Палитра узлов визуального программирования и их реализации.

Типы пинов: "exec" (поток выполнения), "float", "int", "bool", "string",
"vector2", "any" (данные).
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple, Type

from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.visual.nodes")

EXEC = "exec"


class VisualNodeType:
    """Описание одного типа узла визуального скрипта."""

    type_name: str = "Node"
    category: str = "Прочее"
    title: str = "Node"
    description: str = ""
    color: str = "#3c3c3c"
    inputs: List[Tuple[str, str]] = []
    outputs: List[Tuple[str, str]] = []
    properties: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Исполнение
    # ------------------------------------------------------------------
    def execute(self, runtime: Any, node: Any, inputs: Dict[str, Any]) -> Any:
        """Выполняет узел. Возвращает имя выходного exec-пина (или список)."""
        return "out"

    def compute(self, runtime: Any, node: Any, inputs: Dict[str, Any]) -> Any:
        """Вычисляет значение для data-узла."""
        return None

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------
    @classmethod
    def input_pins(cls) -> List[Tuple[str, str]]:
        return list(cls.inputs)

    @classmethod
    def output_pins(cls) -> List[Tuple[str, str]]:
        return list(cls.outputs)

    @classmethod
    def prop(cls, node: Any, name: str, default: Any = None) -> Any:
        value = node.props.get(name, None)
        if value is None:
            spec = cls.properties.get(name) or {}
            return spec.get("default", default)
        return value


# ======================================================================
# События
# ======================================================================
class EventReady(VisualNodeType):
    type_name = "EventReady"
    category = "События"
    title = "При готовности"
    description = "Выполняется один раз при старте сцены"
    color = "#7a4b8c"
    outputs = [("out", EXEC)]

    def execute(self, runtime, node, inputs):
        return "out"


class EventProcess(VisualNodeType):
    type_name = "EventProcess"
    category = "События"
    title = "Каждый кадр"
    description = "Выполняется каждый кадр; delta — время кадра"
    color = "#7a4b8c"
    outputs = [("out", EXEC), ("delta", "float")]

    def execute(self, runtime, node, inputs):
        return "out"


class EventPhysics(VisualNodeType):
    type_name = "EventPhysics"
    category = "События"
    title = "Каждый физ. шаг"
    description = "Выполняется на каждом шаге физики"
    color = "#7a4b8c"
    outputs = [("out", EXEC), ("delta", "float")]

    def execute(self, runtime, node, inputs):
        return "out"


class EventBodyEntered(VisualNodeType):
    type_name = "EventBodyEntered"
    category = "События"
    title = "Тело коснулось"
    description = "Сигнал Area2D body_entered"
    color = "#7a4b8c"
    outputs = [("out", EXEC), ("body", "any")]

    def execute(self, runtime, node, inputs):
        return "out"


class EventInput(VisualNodeType):
    type_name = "EventInput"
    category = "События"
    title = "Нажата клавиша"
    description = "Срабатывает при нажатии действия (project.json → input)"
    color = "#7a4b8c"
    properties = {"action": {"type": "string", "default": "jump"}}
    outputs = [("out", EXEC)]


class EventTimer(VisualNodeType):
    type_name = "EventTimer"
    category = "События"
    title = "Каждые N секунд"
    description = "Периодическое событие"
    color = "#7a4b8c"
    properties = {
        "interval": {"type": "float", "default": 1.0, "min": 0.05, "max": 600.0, "step": 0.1},
    }
    outputs = [("out", EXEC)]


# ======================================================================
# Поток управления
# ======================================================================
class FlowBranch(VisualNodeType):
    type_name = "Branch"
    category = "Логика"
    title = "Если / иначе"
    description = "Разветвление по условию"
    color = "#4b6b8c"
    inputs = [("exec", EXEC), ("condition", "bool")]
    outputs = [("true", EXEC), ("false", EXEC)]

    def execute(self, runtime, node, inputs):
        return "true" if inputs.get("condition") else "false"


class FlowSequence(VisualNodeType):
    type_name = "Sequence"
    category = "Логика"
    title = "Последовательно"
    description = "Выполняет несколько веток подряд"
    color = "#4b6b8c"
    inputs = [("exec", EXEC)]
    outputs = [("1", EXEC), ("2", EXEC), ("3", EXEC)]

    def execute(self, runtime, node, inputs):
        return ["1", "2", "3"]


class FlowDoOnce(VisualNodeType):
    type_name = "DoOnce"
    category = "Логика"
    title = "Один раз"
    description = "Пропускает выполнение только один раз"
    color = "#4b6b8c"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {"reset_on_ready": {"type": "bool", "default": True}}

    def execute(self, runtime, node, inputs):
        state = runtime.state.setdefault(node.id, {})
        if state.get("done"):
            return None
        state["done"] = True
        return "out"


class FlowToggle(VisualNodeType):
    type_name = "Toggle"
    category = "Логика"
    title = "Переключатель"
    description = "Чередует ветки A и B при каждом вызове"
    color = "#4b6b8c"
    inputs = [("exec", EXEC)]
    outputs = [("A", EXEC), ("B", EXEC)]

    def execute(self, runtime, node, inputs):
        state = runtime.state.setdefault(node.id, {})
        state["flag"] = not state.get("flag", False)
        return "A" if state["flag"] else "B"


class FlowGate(VisualNodeType):
    type_name = "Gate"
    category = "Логика"
    title = "Ворота"
    description = "Пропускает поток, только если включено"
    color = "#4b6b8c"
    inputs = [("exec", EXEC), ("open", "bool")]
    outputs = [("out", EXEC)]

    def execute(self, runtime, node, inputs):
        return "out" if inputs.get("open", True) else None


# ======================================================================
# Действия
# ======================================================================
class ActionPrint(VisualNodeType):
    type_name = "Print"
    category = "Действия"
    title = "Вывести в консоль"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("value", "any")]
    outputs = [("out", EXEC)]
    properties = {"message": {"type": "string", "default": "Привет из графа!"}}

    def execute(self, runtime, node, inputs):
        value = inputs.get("value")
        text = value if value not in (None, "") else self.prop(node, "message")
        print(f"[{runtime.owner_name}] {text}")
        return "out"


class ActionSetProperty(VisualNodeType):
    type_name = "SetProperty"
    category = "Действия"
    title = "Задать свойство"
    description = "Меняет свойство ноды (своей или другой по пути)"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("value", "any")]
    outputs = [("out", EXEC)]
    properties = {
        "property": {"type": "string", "default": "visible"},
        "node_path": {"type": "string", "default": ""},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", ""))
        if target is None:
            return "out"
        prop = self.prop(node, "property", "visible")
        value = inputs.get("value")
        try:
            target.set(prop, value)
        except Exception:
            logger.exception("SetProperty: не удалось задать %s", prop)
        return "out"


class ActionMove(VisualNodeType):
    type_name = "Move"
    category = "Действия"
    title = "Сместить ноду"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("dx", "float"), ("dy", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "dx": {"type": "float", "default": 0.0},
        "dy": {"type": "float", "default": 0.0},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", ""))
        if target is None or not hasattr(target, "position"):
            return "out"
        dx = inputs.get("dx")
        dy = inputs.get("dy")
        if dx is None:
            dx = self.prop(node, "dx", 0.0)
        if dy is None:
            dy = self.prop(node, "dy", 0.0)
        target.position = target.position + Vector2(float(dx), float(dy))
        return "out"


class ActionSetVelocity(VisualNodeType):
    type_name = "SetVelocity"
    category = "Движение"
    title = "Задать скорость"
    color = "#4b8c6b"
    inputs = [("exec", EXEC), ("x", "float"), ("y", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "x": {"type": "float", "default": 0.0},
        "y": {"type": "float", "default": 0.0},
        "keep_y": {"type": "bool", "default": False},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", ""))
        if target is None or not hasattr(target, "velocity"):
            return "out"
        x = inputs.get("x")
        y = inputs.get("y")
        if x is None:
            x = self.prop(node, "x", 0.0)
        if y is None:
            y = self.prop(node, "y", 0.0)
        if self.prop(node, "keep_y", False):
            target.velocity = Vector2(float(x), target.velocity.y)
        else:
            target.velocity = Vector2(float(x), float(y))
        return "out"


class ActionMoveAndSlide(VisualNodeType):
    type_name = "MoveAndSlide"
    category = "Движение"
    title = "Двигаться (move_and_slide)"
    color = "#4b8c6b"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {"node_path": {"type": "string", "default": ""}}

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", ""))
        if target is not None and hasattr(target, "move_and_slide"):
            target.move_and_slide()
        return "out"


class ActionJump(VisualNodeType):
    type_name = "Jump"
    category = "Движение"
    title = "Прыгнуть"
    color = "#4b8c6b"
    inputs = [("exec", EXEC), ("force", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "force": {"type": "float", "default": 480.0},
        "only_on_floor": {"type": "bool", "default": True},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", ""))
        if target is None or not hasattr(target, "velocity"):
            return "out"
        if self.prop(node, "only_on_floor", True):
            check = getattr(target, "is_on_floor", None)
            if callable(check) and not check():
                return "out"
        force = inputs.get("force")
        if force is None:
            force = self.prop(node, "force", 480.0)
        target.velocity = Vector2(target.velocity.x, -abs(float(force)))
        return "out"


class ActionDamage(VisualNodeType):
    type_name = "Damage"
    category = "Геймплей"
    title = "Нанести урон"
    color = "#8c4b4b"
    inputs = [("exec", EXEC), ("amount", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "amount": {"type": "float", "default": 10.0},
    }

    def execute(self, runtime, node, inputs):
        amount = inputs.get("amount")
        if amount is None:
            amount = self.prop(node, "amount", 10.0)
        target = runtime.resolve(node.props.get("node_path", "")) or runtime.owner
        getter = getattr(target, "get_component", None)
        health = getter("Health") if callable(getter) else None
        if health is not None:
            health.damage(float(amount), runtime.owner)
        return "out"


class ActionHeal(VisualNodeType):
    type_name = "Heal"
    category = "Геймплей"
    title = "Вылечить"
    color = "#4b8c4b"
    inputs = [("exec", EXEC), ("amount", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "amount": {"type": "float", "default": 10.0},
    }

    def execute(self, runtime, node, inputs):
        amount = inputs.get("amount")
        if amount is None:
            amount = self.prop(node, "amount", 10.0)
        target = runtime.resolve(node.props.get("node_path", "")) or runtime.owner
        getter = getattr(target, "get_component", None)
        health = getter("Health") if callable(getter) else None
        if health is not None:
            health.heal(float(amount))
        return "out"


class ActionAddScore(VisualNodeType):
    type_name = "AddScore"
    category = "Геймплей"
    title = "Добавить очки"
    color = "#8c8c4b"
    inputs = [("exec", EXEC), ("points", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "stats": {"type": "string", "default": "coins"},
        "points": {"type": "float", "default": 1.0},
    }

    def execute(self, runtime, node, inputs):
        from engine.components.builtin import add_stat
        points = inputs.get("points")
        if points is None:
            points = self.prop(node, "points", 1.0)
        add_stat(self.prop(node, "stats", "coins"), float(points))
        add_stat("score", float(points))
        return "out"


class ActionQueueFree(VisualNodeType):
    type_name = "QueueFree"
    category = "Действия"
    title = "Удалить ноду"
    color = "#8c4b4b"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {"node_path": {"type": "string", "default": ""}}

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", "")) or runtime.owner
        if target is not None:
            target.queue_free()
        return "out"


class ActionSpawn(VisualNodeType):
    type_name = "Spawn"
    category = "Действия"
    title = "Создать ноду"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("offset_x", "float"), ("offset_y", "float")]
    outputs = [("out", EXEC), ("node", "any")]
    properties = {
        "node_type": {"type": "string", "default": "Sprite2D"},
        "offset_x": {"type": "float", "default": 0.0},
        "offset_y": {"type": "float", "default": 0.0},
        "as_child": {"type": "bool", "default": False},
    }

    def execute(self, runtime, node, inputs):
        from engine.nodes import NODE_CLASSES
        cls = NODE_CLASSES.get(self.prop(node, "node_type", "Sprite2D"))
        if cls is None:
            return "out"
        spawned = cls()
        ox = inputs.get("offset_x")
        oy = inputs.get("offset_y")
        offset = Vector2(float(ox if ox is not None else self.prop(node, "offset_x", 0.0)),
                         float(oy if oy is not None else self.prop(node, "offset_y", 0.0)))
        owner = runtime.owner
        if owner is None:
            return "out"
        if self.prop(node, "as_child", False) or not hasattr(spawned, "position"):
            owner.add_child(spawned)
        else:
            if hasattr(spawned, "position"):
                spawned.position = owner.get_global_position() + offset
            parent = owner.parent if owner.parent is not None else owner
            parent.add_child(spawned)
        runtime.state[node.id] = {"last_spawned": spawned}
        return "out"


class ActionPlaySound(VisualNodeType):
    type_name = "PlaySound"
    category = "Действия"
    title = "Проиграть звук"
    color = "#6b4b8c"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {"sound_path": {"type": "resource", "default": ""},
                  "volume_db": {"type": "float", "default": 0.0}}

    def execute(self, runtime, node, inputs):
        path = self.prop(node, "sound_path", "")
        if not path:
            return "out"
        try:
            tree = runtime.tree
            manager = None
            if tree is not None and tree.render_system is not None:
                manager = tree.render_system.asset_manager
            if manager is not None:
                sound = manager.get_sound(path)
                if sound is not None:
                    channel = sound.play()
                    if channel is not None:
                        db = float(self.prop(node, "volume_db", 0.0))
                        channel.set_volume(max(0.0, min(1.0, 10.0 ** (db / 20.0))))
        except Exception:
            logger.exception("PlaySound: ошибка воспроизведения")
        return "out"


class ActionSetText(VisualNodeType):
    type_name = "SetText"
    category = "Интерфейс"
    title = "Задать текст"
    color = "#4b6b8c"
    inputs = [("exec", EXEC), ("text", "string")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": "UI/Label"},
        "template": {"type": "string", "default": "Очки: {score}"},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", ""))
        if target is None or not hasattr(target, "text"):
            return "out"
        text = inputs.get("text")
        if text in (None, ""):
            from engine.components.builtin import GAME_STATS
            template = self.prop(node, "template", "{score}")
            try:
                text = template.format(**{k: int(v) for k, v in GAME_STATS.items()})
            except Exception:
                text = template
        target.text = str(text)
        return "out"


class ActionFlip(VisualNodeType):
    type_name = "FlipSprite"
    category = "Действия"
    title = "Отразить спрайт"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("flip", "bool")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "flip": {"type": "bool", "default": True},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", ""))
        if target is None:
            target = runtime.find_sprite()
        if target is not None and hasattr(target, "flip_h"):
            value = inputs.get("flip")
            if value is None:
                value = self.prop(node, "flip", True)
            target.flip_h = bool(value)
        return "out"


class ActionSetColor(VisualNodeType):
    type_name = "SetColor"
    category = "Действия"
    title = "Задать цвет"
    color = "#8c6b4b"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "color": {"type": "color", "default": [255, 255, 255, 255]},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", "")) or runtime.owner
        color = self.prop(node, "color", [255, 255, 255, 255])
        if target is not None and hasattr(target, "modulate"):
            target.modulate = tuple(int(c) for c in color)
        return "out"


# ======================================================================
# Данные
# ======================================================================
class DataConstant(VisualNodeType):
    type_name = "Constant"
    category = "Данные"
    title = "Число"
    color = "#3c5c7a"
    outputs = [("value", "float")]
    properties = {"value": {"type": "float", "default": 0.0}}

    def compute(self, runtime, node, inputs):
        return float(self.prop(node, "value", 0.0))


class DataString(VisualNodeType):
    type_name = "String"
    category = "Данные"
    title = "Строка"
    color = "#3c5c7a"
    outputs = [("value", "string")]
    properties = {"value": {"type": "string", "default": "текст"}}

    def compute(self, runtime, node, inputs):
        return str(self.prop(node, "value", ""))


class DataBool(VisualNodeType):
    type_name = "Bool"
    category = "Данные"
    title = "Логическое"
    color = "#3c5c7a"
    outputs = [("value", "bool")]
    properties = {"value": {"type": "bool", "default": True}}

    def compute(self, runtime, node, inputs):
        return bool(self.prop(node, "value", False))


class DataMath(VisualNodeType):
    type_name = "Math"
    category = "Данные"
    title = "Математика"
    color = "#3c5c7a"
    inputs = [("a", "float"), ("b", "float")]
    outputs = [("result", "float")]
    properties = {
        "operation": {"type": "enum", "default": "add",
                      "options": ["add", "subtract", "multiply", "divide",
                                  "min", "max", "mod", "power"]},
        "a": {"type": "float", "default": 1.0},
        "b": {"type": "float", "default": 1.0},
    }

    def compute(self, runtime, node, inputs):
        op = self.prop(node, "operation", "add")
        a = inputs.get("a")
        b = inputs.get("b")
        if a is None:
            a = self.prop(node, "a", 0.0)
        if b is None:
            b = self.prop(node, "b", 0.0)
        a, b = float(a), float(b)
        try:
            if op == "add":
                return a + b
            if op == "subtract":
                return a - b
            if op == "multiply":
                return a * b
            if op == "divide":
                return a / b if b != 0 else 0.0
            if op == "min":
                return min(a, b)
            if op == "max":
                return max(a, b)
            if op == "mod":
                return math.fmod(a, b) if b != 0 else 0.0
            if op == "power":
                return a ** b
        except Exception:
            return 0.0
        return 0.0


class DataCompare(VisualNodeType):
    type_name = "Compare"
    category = "Данные"
    title = "Сравнить"
    color = "#3c5c7a"
    inputs = [("a", "float"), ("b", "float")]
    outputs = [("result", "bool")]
    properties = {
        "operation": {"type": "enum", "default": "greater",
                      "options": ["greater", "less", "equal", "not_equal",
                                  "greater_equal", "less_equal"]},
        "a": {"type": "float", "default": 0.0},
        "b": {"type": "float", "default": 0.0},
    }

    def compute(self, runtime, node, inputs):
        op = self.prop(node, "operation", "greater")
        a = inputs.get("a")
        b = inputs.get("b")
        if a is None:
            a = self.prop(node, "a", 0.0)
        if b is None:
            b = self.prop(node, "b", 0.0)
        try:
            a, b = float(a), float(b)
        except (TypeError, ValueError):
            return False
        if op == "greater":
            return a > b
        if op == "less":
            return a < b
        if op == "equal":
            return abs(a - b) < 1e-9
        if op == "not_equal":
            return abs(a - b) >= 1e-9
        if op == "greater_equal":
            return a >= b
        if op == "less_equal":
            return a <= b
        return False


class DataRandom(VisualNodeType):
    type_name = "Random"
    category = "Данные"
    title = "Случайное число"
    color = "#3c5c7a"
    outputs = [("value", "float")]
    properties = {
        "minimum": {"type": "float", "default": 0.0},
        "maximum": {"type": "float", "default": 1.0},
        "integer": {"type": "bool", "default": False},
    }

    def compute(self, runtime, node, inputs):
        low = float(self.prop(node, "minimum", 0.0))
        high = float(self.prop(node, "maximum", 1.0))
        if high < low:
            low, high = high, low
        if self.prop(node, "integer", False):
            return float(random.randint(int(low), int(high)))
        return random.uniform(low, high)


class DataGetProperty(VisualNodeType):
    type_name = "GetProperty"
    category = "Данные"
    title = "Получить свойство"
    color = "#3c5c7a"
    outputs = [("value", "any")]
    properties = {
        "property": {"type": "string", "default": "position"},
        "node_path": {"type": "string", "default": ""},
        "component": {"type": "string", "default": ""},
    }

    def compute(self, runtime, node, inputs):
        target = runtime.resolve(node.props.get("node_path", "")) or runtime.owner
        if target is None:
            return None
        component_type = self.prop(node, "component", "")
        if component_type:
            getter = getattr(target, "get_component", None)
            component = getter(component_type) if callable(getter) else None
            if component is None:
                return None
            target = component
        value = getattr(target, self.prop(node, "property", ""), None)
        if isinstance(value, Vector2):
            return value
        return value


class DataVectorComponent(VisualNodeType):
    type_name = "VectorPart"
    category = "Данные"
    title = "Компонент вектора"
    color = "#3c5c7a"
    inputs = [("vector", "vector2")]
    outputs = [("value", "float")]
    properties = {
        "axis": {"type": "enum", "default": "x", "options": ["x", "y"]},
        "default": {"type": "float", "default": 0.0},
    }

    def compute(self, runtime, node, inputs):
        vector = inputs.get("vector")
        if vector is None:
            return float(self.prop(node, "default", 0.0))
        if isinstance(vector, Vector2):
            return vector.x if self.prop(node, "axis", "x") == "x" else vector.y
        try:
            return float(vector[0] if self.prop(node, "axis", "x") == "x" else vector[1])
        except Exception:
            return 0.0


class DataInputAxis(VisualNodeType):
    type_name = "InputAxis"
    category = "Ввод"
    title = "Ось ввода"
    description = "Возвращает -1..1 по двум действиям"
    color = "#5c7a3c"
    outputs = [("value", "float")]
    properties = {
        "negative": {"type": "string", "default": "move_left"},
        "positive": {"type": "string", "default": "move_right"},
    }

    def compute(self, runtime, node, inputs):
        input_manager = runtime.input
        if input_manager is None:
            return 0.0
        return input_manager.get_axis(self.prop(node, "negative", "move_left"),
                                      self.prop(node, "positive", "move_right"))


class DataInputPressed(VisualNodeType):
    type_name = "InputPressed"
    category = "Ввод"
    title = "Действие нажато"
    color = "#5c7a3c"
    outputs = [("value", "bool")]
    properties = {
        "action": {"type": "string", "default": "jump"},
        "mode": {"type": "enum", "default": "pressed",
                 "options": ["pressed", "just_pressed", "just_released"]},
    }

    def compute(self, runtime, node, inputs):
        input_manager = runtime.input
        if input_manager is None:
            return False
        action = self.prop(node, "action", "jump")
        mode = self.prop(node, "mode", "pressed")
        if mode == "just_pressed":
            return input_manager.is_action_just_pressed(action)
        if mode == "just_released":
            return input_manager.is_action_just_released(action)
        return input_manager.is_action_pressed(action)


class DataMousePosition(VisualNodeType):
    type_name = "MousePosition"
    category = "Ввод"
    title = "Позиция мыши"
    color = "#5c7a3c"
    outputs = [("value", "vector2")]

    def compute(self, runtime, node, inputs):
        input_manager = runtime.input
        return input_manager.mouse_position if input_manager is not None else Vector2()


class DataDelta(VisualNodeType):
    type_name = "Delta"
    category = "Данные"
    title = "Delta (время кадра)"
    color = "#3c5c7a"
    outputs = [("value", "float")]

    def compute(self, runtime, node, inputs):
        return runtime.delta


class DataSelfPosition(VisualNodeType):
    type_name = "SelfPosition"
    category = "Данные"
    title = "Позиция ноды"
    color = "#3c5c7a"
    outputs = [("value", "vector2")]

    def compute(self, runtime, node, inputs):
        owner = runtime.owner
        if owner is not None and hasattr(owner, "get_global_position"):
            return owner.get_global_position()
        return Vector2()


class DataNodeByGroup(VisualNodeType):
    type_name = "FindNode"
    category = "Данные"
    title = "Найти ноду"
    color = "#3c5c7a"
    outputs = [("value", "any")]
    properties = {"path": {"type": "string", "default": "Player"}}

    def compute(self, runtime, node, inputs):
        return runtime.resolve(self.prop(node, "path", ""))


# ======================================================================
# Анимация
# ======================================================================
class ActionPlayAnimation(VisualNodeType):
    type_name = "PlayAnimation"
    category = "Анимация"
    title = "Играть анимацию"
    description = "Запускает анимацию у AnimationPlayer"
    color = "#4b7a8c"
    inputs = [("exec", EXEC), ("name", "string")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "name": {"type": "string", "default": "idle"},
        "restart": {"type": "bool", "default": True},
    }

    def execute(self, runtime, node, inputs):
        player = _animation_player(runtime, node)
        if player is not None:
            name = inputs.get("name") or self.prop(node, "name", "")
            player.play(str(name), bool(self.prop(node, "restart", True)))
        return "out"


class ActionStopAnimation(VisualNodeType):
    type_name = "StopAnimation"
    category = "Анимация"
    title = "Остановить анимацию"
    color = "#4b7a8c"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {"node_path": {"type": "string", "default": ""}}

    def execute(self, runtime, node, inputs):
        player = _animation_player(runtime, node)
        if player is not None:
            player.stop()
        return "out"


class ActionSetAnimationSpeed(VisualNodeType):
    type_name = "SetAnimationSpeed"
    category = "Анимация"
    title = "Скорость анимации"
    color = "#4b7a8c"
    inputs = [("exec", EXEC), ("speed", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "speed": {"type": "float", "default": 1.0},
    }

    def execute(self, runtime, node, inputs):
        player = _animation_player(runtime, node)
        if player is not None:
            value = inputs.get("speed")
            if value is None:
                value = self.prop(node, "speed", 1.0)
            player.speed = max(0.01, float(value))
        return "out"


# ======================================================================
# Камера, свет и эффекты
# ======================================================================
class ActionShakeCamera(VisualNodeType):
    type_name = "ShakeCamera"
    category = "Камера"
    title = "Тряска камеры"
    description = "Добавляет тряску активной камере"
    color = "#8c7a4b"
    inputs = [("exec", EXEC), ("amount", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "amount": {"type": "float", "default": 0.5},
    }

    def execute(self, runtime, node, inputs):
        camera = None
        path = self.prop(node, "node_path", "")
        if path:
            camera = runtime.resolve(path)
        if camera is None:
            tree = runtime.tree
            camera = getattr(getattr(tree, "render_system", None), "active_camera", None)
        if camera is not None and hasattr(camera, "add_trauma"):
            amount = inputs.get("amount")
            if amount is None:
                amount = self.prop(node, "amount", 0.5)
            camera.add_trauma(float(amount))
        return "out"


class ActionSetLight(VisualNodeType):
    type_name = "SetLight"
    category = "Свет"
    title = "Настроить свет"
    color = "#8c8c4b"
    inputs = [("exec", EXEC), ("energy", "float"), ("radius", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "energy": {"type": "float", "default": 1.0},
        "radius": {"type": "float", "default": 0.0},
        "enabled": {"type": "bool", "default": True},
    }

    def execute(self, runtime, node, inputs):
        light = _light_of(runtime, node)
        if light is None:
            return "out"
        energy = inputs.get("energy")
        if energy is None:
            energy = self.prop(node, "energy", None)
        if energy is not None:
            light.energy = max(0.0, float(energy))
        radius = inputs.get("radius")
        if radius is None:
            radius = self.prop(node, "radius", 0.0)
        if radius:
            light.radius = max(1.0, float(radius))
        light.enabled = bool(self.prop(node, "enabled", True))
        return "out"


class ActionScreenEffect(VisualNodeType):
    """Вспышка экрана и быстрая настройка постобработки."""

    type_name = "ScreenFlash"
    category = "Эффекты"
    title = "Вспышка экрана"
    color = "#8c4b6b"
    inputs = [("exec", EXEC), ("amount", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "color": {"type": "color", "default": [255, 255, 255, 255]},
        "amount": {"type": "float", "default": 1.0},
        "duration": {"type": "float", "default": 0.18},
    }

    def execute(self, runtime, node, inputs):
        post = _post_process(runtime)
        if post is not None:
            amount = inputs.get("amount")
            if amount is None:
                amount = self.prop(node, "amount", 1.0)
            color = self.prop(node, "color", [255, 255, 255, 255])
            post.trigger_flash(tuple(color),
                               float(self.prop(node, "duration", 0.18)))
            post.flash = max(post.flash, min(1.0, float(amount)))
        return "out"


class ActionSpawnParticles(VisualNodeType):
    type_name = "SpawnParticles"
    category = "Эффекты"
    title = "Создать частицы"
    color = "#8c4b6b"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {
        "amount": {"type": "int", "default": 24},
        "lifetime": {"type": "float", "default": 0.7},
        "speed": {"type": "float", "default": 160.0},
    }

    def execute(self, runtime, node, inputs):
        owner = runtime.owner
        if owner is None:
            return "out"
        try:
            from engine.nodes.particles2d import Particles2D
            particles = Particles2D("GraphParticles")
            particles.amount = int(self.prop(node, "amount", 24))
            particles.lifetime = float(self.prop(node, "lifetime", 0.7))
            particles.one_shot = True
            particles.speed_max = float(self.prop(node, "speed", 160.0))
            parent = owner.parent if getattr(owner, "parent", None) else owner
            particles.position = Vector2() if parent is owner \
                else owner.get_global_position()
            parent.add_child(particles)
        except Exception:
            logger.exception("SpawnParticles: не удалось создать частицы")
        return "out"


class ActionPlaySoundAt(VisualNodeType):
    type_name = "PlaySoundAt"
    category = "Эффекты"
    title = "Звук в точке"
    color = "#8c4b6b"
    inputs = [("exec", EXEC)]
    outputs = [("out", EXEC)]
    properties = {
        "sound_path": {"type": "string", "default": ""},
        "volume_db": {"type": "float", "default": 0.0},
        "positional": {"type": "bool", "default": True},
    }

    def execute(self, runtime, node, inputs):
        owner = runtime.owner
        path = self.prop(node, "sound_path", "")
        if owner is None or not path:
            return "out"
        try:
            from engine.nodes.audio_stream import (AudioStreamPlayer,
                                                   AudioStreamPlayer2D)
            factory = AudioStreamPlayer2D if self.prop(node, "positional", True) \
                else AudioStreamPlayer
            player = factory("GraphSound")
            player.stream_path = path
            player.volume_db = float(self.prop(node, "volume_db", 0.0))
            parent = owner.parent if getattr(owner, "parent", None) else owner
            player.position = owner.get_global_position()
            parent.add_child(player)
            player.play()
        except Exception:
            logger.exception("PlaySoundAt: не удалось создать источник звука")
        return "out"


# ======================================================================
# Физика и запросы
# ======================================================================
class ActionAddImpulse(VisualNodeType):
    type_name = "AddImpulse"
    category = "Движение"
    title = "Толчок"
    description = "Добавляет скорость телу"
    color = "#4b8c6b"
    inputs = [("exec", EXEC), ("x", "float"), ("y", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "x": {"type": "float", "default": 0.0},
        "y": {"type": "float", "default": -200.0},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(self.prop(node, "node_path", "")) or runtime.owner
        if target is None or not hasattr(target, "velocity"):
            return "out"
        x = inputs.get("x")
        y = inputs.get("y")
        if x is None:
            x = self.prop(node, "x", 0.0)
        if y is None:
            y = self.prop(node, "y", 0.0)
        target.velocity = Vector2(target.velocity) + Vector2(float(x), float(y))
        return "out"


class ActionSetGravityScale(VisualNodeType):
    type_name = "SetGravityScale"
    category = "Движение"
    title = "Гравитация объекта"
    color = "#4b8c6b"
    inputs = [("exec", EXEC), ("value", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "value": {"type": "float", "default": 1.0},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(self.prop(node, "node_path", "")) or runtime.owner
        if target is None or not hasattr(target, "gravity_scale"):
            return "out"
        value = inputs.get("value")
        if value is None:
            value = self.prop(node, "value", 1.0)
        target.gravity_scale = float(value)
        return "out"


class ActionTeleportTo(VisualNodeType):
    type_name = "TeleportTo"
    category = "Движение"
    title = "Телепорт"
    color = "#4b8c6b"
    inputs = [("exec", EXEC), ("x", "float"), ("y", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "target_path": {"type": "string", "default": ""},
        "x": {"type": "float", "default": 0.0},
        "y": {"type": "float", "default": 0.0},
        "reset_velocity": {"type": "bool", "default": True},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(self.prop(node, "node_path", "")) or runtime.owner
        if target is None:
            return "out"
        destination = runtime.resolve(self.prop(node, "target_path", ""))
        if destination is not None and hasattr(destination, "get_global_position"):
            point = destination.get_global_position()
        else:
            x = inputs.get("x")
            y = inputs.get("y")
            if x is None:
                x = self.prop(node, "x", 0.0)
            if y is None:
                y = self.prop(node, "y", 0.0)
            point = Vector2(float(x), float(y))
        if hasattr(target, "set_global_position"):
            target.set_global_position(Vector2(point))
        elif hasattr(target, "position"):
            target.position = Vector2(point)
        if self.prop(node, "reset_velocity", True) and hasattr(target, "velocity"):
            target.velocity = Vector2()
        return "out"


class DataRaycast(VisualNodeType):
    type_name = "Raycast"
    category = "Запросы"
    title = "Луч: есть попадание"
    description = "Проверяет, есть ли препятствие в направлении"
    color = "#3c5c7a"
    inputs = [("length", "float")]
    outputs = [("hit", "bool")]
    properties = {
        "length": {"type": "float", "default": 96.0},
        "direction": {"type": "vector2", "default": [1.0, 0.0]},
        "mask": {"type": "int", "default": 65535},
    }

    def compute(self, runtime, node, inputs):
        ray = _cast_ray(runtime, node, inputs)
        return bool(ray is not None and ray.is_colliding())


class DataRaycastDistance(VisualNodeType):
    type_name = "RaycastDistance"
    category = "Запросы"
    title = "Луч: расстояние"
    color = "#3c5c7a"
    inputs = [("length", "float")]
    outputs = [("distance", "float")]
    properties = {
        "length": {"type": "float", "default": 96.0},
        "direction": {"type": "vector2", "default": [1.0, 0.0]},
        "mask": {"type": "int", "default": 65535},
        "miss_value": {"type": "float", "default": -1.0},
    }

    def compute(self, runtime, node, inputs):
        miss = float(self.prop(node, "miss_value", -1.0))
        ray = _cast_ray(runtime, node, inputs)
        if ray is None or not ray.is_colliding():
            return miss
        try:
            point = ray.get_collision_point()
            origin = ray.get_global_position()
            return float(point.distance_to(origin))
        except Exception:
            return miss


# ======================================================================
# Видимость, масштаб и компоненты
# ======================================================================
class ActionSetVisible(VisualNodeType):
    type_name = "SetVisible"
    category = "Действия"
    title = "Показать/скрыть"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("visible", "bool")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "visible": {"type": "bool", "default": True},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(self.prop(node, "node_path", ""))
        if target is None and hasattr(runtime, "find_sprite"):
            target = runtime.find_sprite()
        if target is None:
            target = runtime.owner
        value = inputs.get("visible")
        if value is None:
            value = self.prop(node, "visible", True)
        if target is not None and hasattr(target, "visible"):
            target.visible = bool(value)
        return "out"


class ActionSetScale(VisualNodeType):
    type_name = "SetScale"
    category = "Действия"
    title = "Задать масштаб"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("x", "float"), ("y", "float")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "x": {"type": "float", "default": 1.0},
        "y": {"type": "float", "default": 1.0},
    }

    def execute(self, runtime, node, inputs):
        target = runtime.resolve(self.prop(node, "node_path", "")) or runtime.owner
        if target is None or not hasattr(target, "scale"):
            return "out"
        x = inputs.get("x")
        y = inputs.get("y")
        if x is None:
            x = self.prop(node, "x", 1.0)
        if y is None:
            y = self.prop(node, "y", 1.0)
        target.scale = Vector2(float(x), float(y))
        return "out"


class DataGetComponentProperty(VisualNodeType):
    type_name = "GetComponentProperty"
    category = "Данные"
    title = "Свойство компонента"
    color = "#3c5c7a"
    outputs = [("value", "any")]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "component": {"type": "string", "default": "Health"},
        "property": {"type": "string", "default": "health"},
    }

    def compute(self, runtime, node, inputs):
        component = _component_of(runtime, node)
        if component is None:
            return 0.0
        prop = self.prop(node, "property", "")
        return getattr(component, prop, 0.0)


class ActionSetComponentProperty(VisualNodeType):
    type_name = "SetComponentProperty"
    category = "Действия"
    title = "Задать свойство компонента"
    color = "#8c6b4b"
    inputs = [("exec", EXEC), ("value", "any")]
    outputs = [("out", EXEC)]
    properties = {
        "node_path": {"type": "string", "default": ""},
        "component": {"type": "string", "default": "Health"},
        "property": {"type": "string", "default": "health"},
        "value": {"type": "float", "default": 100.0},
    }

    def execute(self, runtime, node, inputs):
        component = _component_of(runtime, node)
        prop = self.prop(node, "property", "")
        if component is None or not prop:
            return "out"
        value = inputs.get("value")
        if value is None:
            value = self.prop(node, "value", 0.0)
        try:
            component.set(prop, value)
        except Exception:
            logger.exception("SetComponentProperty: не удалось задать %s", prop)
        return "out"


# ======================================================================
# Помощники узлов
# ======================================================================
def _find_in_scene(runtime: Any, type_name: str) -> Any:
    """Ищет первый узел сцены нужного типа."""
    tree = runtime.tree
    scene = getattr(tree, "current_scene", None) if tree is not None else None
    if scene is None:
        return None
    target_type = type_name.lower()
    for candidate in scene.get_nodes():
        if type(candidate).__name__.lower() == target_type:
            return candidate
    return None


def _animation_player(runtime: Any, node: Any) -> Any:
    """AnimationPlayer: по пути, у владельца/детей или первый в сцене."""
    path = node.props.get("node_path", "") or ""
    if path:
        found = runtime.resolve(path)
        if found is not None:
            return found
    owner = runtime.owner
    if owner is not None:
        if type(owner).__name__ == "AnimationPlayer":
            return owner
        for child in owner.get_children():
            if type(child).__name__ == "AnimationPlayer":
                return child
    return _find_in_scene(runtime, "AnimationPlayer")


def _light_of(runtime: Any, node: Any) -> Any:
    """Light2D: по пути, у владельца/детей или первый в сцене."""
    path = node.props.get("node_path", "") or ""
    if path:
        found = runtime.resolve(path)
        if found is not None:
            return found
    owner = runtime.owner
    if owner is not None:
        if type(owner).__name__ == "Light2D":
            return owner
        for child in owner.get_children():
            if type(child).__name__ == "Light2D":
                return child
    return _find_in_scene(runtime, "Light2D")


def _post_process(runtime: Any) -> Any:
    """Активный узел постобработки сцены."""
    return _find_in_scene(runtime, "PostProcess")


def _component_of(runtime: Any, node: Any) -> Any:
    """Компонент по имени у целевой ноды."""
    target = runtime.resolve(node.props.get("node_path", "") or "") or runtime.owner
    if target is None:
        return None
    getter = getattr(target, "get_component", None)
    if not callable(getter):
        return None
    name = node.props.get("component", "") or \
        (type(node).properties.get("component") or {}).get("default", "")
    return getter(name)


def _cast_ray(runtime: Any, node: Any, inputs: Dict[str, Any]) -> Any:
    """Пускать луч от владельца графа. Возвращает настроенный RayCast2D."""
    owner = runtime.owner
    if owner is None or not hasattr(owner, "get_global_position"):
        return None
    collision = getattr(runtime.tree, "collision_system", None)
    if collision is None:
        return None

    cache = getattr(runtime, "_graph_rays", None)
    if cache is None:
        cache = {}
        runtime._graph_rays = cache
    ray = cache.get(id(node))
    if ray is None:
        try:
            from engine.nodes.raycast2d import RayCast2D
            ray = RayCast2D("GraphRay")
        except Exception:
            return None
        cache[id(node)] = ray

    length = inputs.get("length")
    if length is None:
        length = node.props.get("length")
    if length is None:
        length = (type(node).properties.get("length") or {}).get("default", 96.0)
    direction = Vector2(node.props.get("direction")
                        or (type(node).properties.get("direction") or {})
                        .get("default", [1.0, 0.0])).normalized()
    mask = node.props.get("mask")
    if mask is None:
        mask = (type(node).properties.get("mask") or {}).get("default", 65535)

    ray.position = owner.get_global_position()
    ray.cast_to = direction * float(length)
    ray.collision_mask = int(mask)
    ray.exclude_parent = False
    try:
        collision.raycast(ray)
    except Exception:
        logger.exception("Не удалось пустить луч")
        return None
    return ray


# ======================================================================
# Реестр типов узлов
# ======================================================================
ALL_VISUAL_NODES: List[Type[VisualNodeType]] = [
    # События
    EventReady, EventProcess, EventPhysics, EventBodyEntered, EventInput, EventTimer,
    # Логика
    FlowBranch, FlowSequence, FlowDoOnce, FlowToggle, FlowGate,
    # Действия
    ActionPrint, ActionSetProperty, ActionMove, ActionQueueFree, ActionSpawn,
    ActionPlaySound, ActionSetText, ActionFlip, ActionSetColor,
    # Движение
    ActionSetVelocity, ActionMoveAndSlide, ActionJump,
    ActionAddImpulse, ActionSetGravityScale, ActionTeleportTo,
    # Геймплей
    ActionDamage, ActionHeal, ActionAddScore,
    # Анимация
    ActionPlayAnimation, ActionStopAnimation, ActionSetAnimationSpeed,
    # Камера, свет, эффекты
    ActionShakeCamera, ActionSetLight, ActionScreenEffect,
    ActionSpawnParticles, ActionPlaySoundAt,
    # Видимость и компоненты
    ActionSetVisible, ActionSetScale,
    DataGetComponentProperty, ActionSetComponentProperty,
    # Запросы
    DataRaycast, DataRaycastDistance,
    # Данные
    DataConstant, DataString, DataBool, DataMath, DataCompare, DataRandom,
    DataGetProperty, DataVectorComponent, DataDelta, DataSelfPosition,
    DataNodeByGroup,
    # Ввод
    DataInputAxis, DataInputPressed, DataMousePosition,
]

#: Имя типа -> класс.
VISUAL_NODE_TYPES: Dict[str, Type[VisualNodeType]] = {
    cls.type_name: cls for cls in ALL_VISUAL_NODES
}

#: Категория -> список имён типов (для палитры редактора).
VISUAL_CATEGORIES: Dict[str, List[str]] = {}
for _cls in ALL_VISUAL_NODES:
    VISUAL_CATEGORIES.setdefault(_cls.category, []).append(_cls.type_name)


def get_visual_node_type(type_name: str) -> Optional[Type[VisualNodeType]]:
    """Класс типа узла по имени."""
    return VISUAL_NODE_TYPES.get(type_name)


def is_event_node(type_name: str) -> bool:
    """Является ли узел событием."""
    cls = VISUAL_NODE_TYPES.get(type_name)
    return bool(cls is not None and cls.category == "События")
