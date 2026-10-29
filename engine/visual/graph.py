"""Модель визуального скрипта (node-граф) Cloud Engine.

Граф хранится в файле `.vgraph` (JSON) и состоит из узлов (VisualNode) и
связей (VisualLink) между их пинами.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cloudengine.visual")


@dataclass
class VisualNode:
    """Узел графа."""

    id: str
    type: str
    x: float = 0.0
    y: float = 0.0
    props: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type, "x": self.x, "y": self.y,
                "props": dict(self.props)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualNode":
        return cls(id=str(data.get("id") or uuid.uuid4().hex[:8]),
                   type=data.get("type", "Print"),
                   x=float(data.get("x", 0.0)),
                   y=float(data.get("y", 0.0)),
                   props=dict(data.get("props") or {}))

    def get(self, prop: str, default: Any = None) -> Any:
        return self.props.get(prop, default)

    def set(self, prop: str, value: Any) -> None:
        self.props[prop] = value


@dataclass
class VisualLink:
    """Связь между пинами двух узлов."""

    from_node: str
    from_pin: str
    to_node: str
    to_pin: str

    def to_dict(self) -> Dict[str, Any]:
        return {"from_node": self.from_node, "from_pin": self.from_pin,
                "to_node": self.to_node, "to_pin": self.to_pin}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualLink":
        return cls(from_node=str(data.get("from_node", "")),
                   from_pin=str(data.get("from_pin", "")),
                   to_node=str(data.get("to_node", "")),
                   to_pin=str(data.get("to_pin", "")))


class VisualGraph:
    """Граф визуального скрипта."""

    def __init__(self, name: str = "Graph") -> None:
        self.name = name
        self.nodes: Dict[str, VisualNode] = {}
        self.links: List[VisualLink] = []
        self.path: str = ""

    # ------------------------------------------------------------------
    # Узлы
    # ------------------------------------------------------------------
    def add_node(self, type_name: str, x: float = 0.0, y: float = 0.0,
                 props: Optional[Dict[str, Any]] = None,
                 node_id: str = "") -> VisualNode:
        """Добавляет узел и возвращает его."""
        from engine.visual.nodes import get_visual_node_type
        node_type = get_visual_node_type(type_name)
        defaults: Dict[str, Any] = {}
        if node_type is not None:
            for prop, spec in node_type.properties.items():
                defaults[prop] = spec.get("default")
        if props:
            defaults.update(props)
        node = VisualNode(id=node_id or uuid.uuid4().hex[:8], type=type_name,
                          x=float(x), y=float(y), props=defaults)
        self.nodes[node.id] = node
        return node

    def remove_node(self, node_id: str) -> None:
        """Удаляет узел вместе со всеми его связями."""
        self.nodes.pop(node_id, None)
        self.links = [l for l in self.links
                      if l.from_node != node_id and l.to_node != node_id]

    def get_node(self, node_id: str) -> Optional[VisualNode]:
        return self.nodes.get(node_id)

    # ------------------------------------------------------------------
    # Связи
    # ------------------------------------------------------------------
    def add_link(self, from_node: str, from_pin: str, to_node: str,
                 to_pin: str) -> Optional[VisualLink]:
        """Создаёт связь. Возвращает её или None, если связь некорректна."""
        if from_node == to_node or from_node not in self.nodes or to_node not in self.nodes:
            return None
        from engine.visual.nodes import get_visual_node_type
        source = get_visual_node_type(self.nodes[from_node].type)
        target = get_visual_node_type(self.nodes[to_node].type)
        if source is None or target is None:
            return None
        if not any(pin == from_pin for pin, _ in source.outputs):
            return None
        if not any(pin == to_pin for pin, _ in target.inputs):
            return None
        # У каждого входного пина может быть только одна входящая связь.
        self.links = [l for l in self.links
                      if not (l.to_node == to_node and l.to_pin == to_pin)]
        link = VisualLink(from_node, from_pin, to_node, to_pin)
        self.links.append(link)
        return link

    def remove_link(self, link: VisualLink) -> None:
        if link in self.links:
            self.links.remove(link)

    def link_into(self, node_id: str, pin: str) -> Optional[VisualLink]:
        """Связь, входящая в указанный пин."""
        for link in self.links:
            if link.to_node == node_id and link.to_pin == pin:
                return link
        return None

    def links_from(self, node_id: str, pin: str) -> List[VisualLink]:
        """Все связи, выходящие из указанного пина."""
        return [l for l in self.links if l.from_node == node_id and l.from_pin == pin]

    def is_connected(self, node_id: str, pin: str, is_input: bool) -> bool:
        for link in self.links:
            if is_input and link.to_node == node_id and link.to_pin == pin:
                return True
            if not is_input and link.from_node == node_id and link.from_pin == pin:
                return True
        return False

    def find_event_nodes(self, type_name: str) -> List[VisualNode]:
        """Все узлы-события указанного типа."""
        return [n for n in self.nodes.values() if n.type == type_name]

    # ------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": "cloudengine.vgraph",
            "version": 1,
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "links": [l.to_dict() for l in self.links],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualGraph":
        graph = cls(data.get("name", "Graph"))
        for node_data in data.get("nodes", []) or []:
            node = VisualNode.from_dict(node_data)
            graph.nodes[node.id] = node
        for link_data in data.get("links", []) or []:
            link = VisualLink.from_dict(link_data)
            if link.from_node in graph.nodes and link.to_node in graph.nodes:
                graph.links.append(link)
        return graph

    def save(self, path: str) -> None:
        """Сохраняет граф в файл .vgraph."""
        try:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)
            self.path = path
        except Exception:
            logger.exception("Не удалось сохранить граф %s", path)

    @classmethod
    def load(cls, path: str) -> "VisualGraph":
        """Загружает граф из файла .vgraph."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        graph = cls.from_dict(data)
        graph.path = path
        return graph
