"""Исполнитель визуального скрипта (интерпретатор node-графа).

События графа (EventReady, EventProcess, ...) запускают поток выполнения по
exec-пинам; значения данных вычисляются лениво по связям.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.visual.graph import VisualGraph, VisualNode
from engine.visual.nodes import EXEC, get_visual_node_type

logger = logging.getLogger("cloudengine.visual.runtime")

#: Максимум шагов выполнения за одно событие (защита от зацикливания).
MAX_STEPS = 4096


class VisualScriptRuntime:
    """Выполняет граф визуального скрипта для конкретной ноды."""

    def __init__(self, graph: VisualGraph, owner: Any) -> None:
        self.graph = graph
        self.owner = owner
        #: Состояние узлов (значения выходов, таймеры, флаги).
        self.state: Dict[str, Dict[str, Any]] = {}
        self.delta: float = 0.0
        self._budget: int = MAX_STEPS
        self._eval_depth: int = 0
        #: Запомненные «нажатые» действия для EventInput.
        self._fired_actions: set = set()

    # ==================================================================
    # Доступ к сцене
    # ==================================================================
    @property
    def tree(self) -> Any:
        return self.owner.get_tree() if self.owner is not None else None

    @property
    def input(self) -> Any:
        tree = self.tree
        return getattr(tree, "input", None) if tree is not None else None

    @property
    def owner_name(self) -> str:
        return getattr(self.owner, "name", "?")

    def resolve(self, path: str) -> Any:
        """Нода по пути: "" — владелец, иначе поиск по сцене."""
        if not path:
            return self.owner
        if self.owner is None:
            return None
        try:
            return self.owner.get_node(path)
        except Exception:
            pass
        tree = self.tree
        scene = tree.current_scene if tree is not None else None
        if scene is not None:
            try:
                return scene.find_node_by_path(path)
            except Exception:
                return None
        return None

    def find_sprite(self) -> Any:
        """Первый Sprite2D среди детей владельца (для FlipSprite и т.п.)."""
        from engine.nodes.sprite2d import Sprite2D
        if self.owner is None:
            return None
        if isinstance(self.owner, Sprite2D):
            return self.owner
        for child in self.owner.get_children():
            if isinstance(child, Sprite2D):
                return child
        return None

    # ==================================================================
    # События
    # ==================================================================
    def event_ready(self) -> None:
        """Обрабатывает узлы EventReady."""
        self._reset_nodes()
        self._run_event("EventReady")

    def event_process(self, delta: float) -> None:
        """Обрабатывает EventProcess, EventInput и EventTimer."""
        self.delta = delta
        self._run_event("EventProcess")
        self._run_input_events()
        self._run_timer_events(delta)

    def event_physics_process(self, delta: float) -> None:
        """Обрабатывает EventPhysics."""
        self.delta = delta
        self._run_event("EventPhysics")

    def event_body_entered(self, body: Any) -> None:
        """Обрабатывает EventBodyEntered."""
        self._run_event("EventBodyEntered", outputs={"body": body})

    def _run_event(self, event_type: str, outputs: Optional[Dict[str, Any]] = None) -> None:
        """Запускает все узлы-события указанного типа."""
        nodes = self.graph.find_event_nodes(event_type)
        if not nodes:
            return
        for node in nodes:
            self._budget = MAX_STEPS
            if outputs:
                self.state.setdefault(node.id, {})["outputs"] = dict(outputs)
            self._follow(node, "out")

    def _run_input_events(self) -> None:
        """Проверяет EventInput: действие только что нажато."""
        input_manager = self.input
        if input_manager is None:
            return
        for node in self.graph.find_event_nodes("EventInput"):
            action = node.props.get("action", "jump")
            try:
                if input_manager.is_action_just_pressed(action):
                    self._budget = MAX_STEPS
                    self._follow(node, "out")
            except Exception:
                continue

    def _run_timer_events(self, delta: float) -> None:
        """Накапливает время для EventTimer и срабатывает по интервалу."""
        for node in self.graph.find_event_nodes("EventTimer"):
            interval = float(node.props.get("interval", 1.0) or 1.0)
            state = self.state.setdefault(node.id, {})
            left = float(state.get("timer", interval)) - delta
            if left <= 0.0:
                state["timer"] = interval
                self._budget = MAX_STEPS
                self._follow(node, "out")
            else:
                state["timer"] = left

    # ==================================================================
    # Выполнение
    # ==================================================================
    def _follow(self, node: VisualNode, pin: str) -> None:
        """Продолжает выполнение по указанному выходному exec-пину."""
        for link in self.graph.links_from(node.id, pin):
            self.exec_node(self.graph.get_node(link.to_node))

    def exec_node(self, node: Optional[VisualNode], extra: Optional[Dict[str, Any]] = None) -> None:
        """Выполняет узел и идёт дальше по его exec-выходам."""
        if node is None or node.id not in self.graph.nodes:
            return
        self._budget -= 1
        if self._budget <= 0:
            logger.warning("Визуальный скрипт: превышен лимит шагов (возможен цикл)")
            return
        node_type = get_visual_node_type(node.type)
        if node_type is None:
            return
        inputs = self._gather_inputs(node, node_type)
        if extra:
            inputs.update(extra)
        try:
            result = node_type().execute(self, node, inputs)
        except Exception:
            logger.exception("Ошибка узла визуального скрипта %s", node.type)
            return
        if result is None:
            return
        pins = result if isinstance(result, (list, tuple)) else [result]
        for pin in pins:
            self._follow(node, pin)

    def _gather_inputs(self, node: VisualNode, node_type: Any) -> Dict[str, Any]:
        """Собирает значения входных пинов узла."""
        inputs: Dict[str, Any] = {}
        for pin, _ptype in node_type.inputs:
            if pin == EXEC:
                continue
            link = self.graph.link_into(node.id, pin)
            if link is not None:
                inputs[pin] = self._eval_output(self.graph.get_node(link.from_node),
                                                link.from_pin)
            else:
                spec = node_type.properties.get(pin) or {}
                inputs[pin] = node.props.get(pin, spec.get("default"))
        return inputs

    def _eval_output(self, node: Optional[VisualNode], pin: str) -> Any:
        """Вычисляет значение выходного пина (с защитой от циклов)."""
        if node is None or node.id not in self.graph.nodes:
            return None
        state = self.state.get(node.id)
        if state:
            dynamic = state.get("outputs")
            if dynamic and pin in dynamic:
                return dynamic[pin]
        self._eval_depth += 1
        if self._eval_depth > 64:
            self._eval_depth -= 1
            logger.warning("Визуальный скрипт: слишком глубокая цепочка данных")
            return None
        try:
            node_type = get_visual_node_type(node.type)
            if node_type is None:
                return None
            inputs = self._gather_inputs(node, node_type)
            return node_type().compute(self, node, inputs)
        except Exception:
            logger.exception("Ошибка вычисления узла %s", node.type)
            return None
        finally:
            self._eval_depth -= 1

    # ==================================================================
    # Состояние
    # ==================================================================
    def _reset_nodes(self) -> None:
        """Сбрасывает состояние узлов при старте."""
        for node in self.graph.nodes.values():
            state = self.state.setdefault(node.id, {})
            if node.type == "DoOnce" and node.props.get("reset_on_ready", True):
                state["done"] = False
            if node.type == "EventTimer":
                state["timer"] = float(node.props.get("interval", 1.0) or 1.0)
