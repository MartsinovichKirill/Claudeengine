"""SceneSerializer — сохранение и загрузка сцен в JSON (.scene).

Формат файла:
{
    "cloud_engine_version": "1.0.0",
    "scene": {
        "name": "Main",
        "root": {
            "type": "Node2D",
            "name": "Main",
            "script": "scripts/player.py",   // опционально
            "properties": {"position": [0, 0], ...},
            "data": {...},                     // опционально (спец. данные ноды)
            "children": [ ... ]
        }
    }
}
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from engine.core.node import Node
from engine.core.scene import Scene
from engine.math.vector2 import Vector2
from engine.math.rect2 import Rect2
from engine.math.transform2d import Transform2D

logger = logging.getLogger("cloudengine.serializer")

from engine import __version__ as _ENGINE_VERSION


def _to_json(value: Any) -> Any:
    """Преобразует движковые типы в JSON-совместимые."""
    if isinstance(value, Vector2):
        return [value.x, value.y]
    if isinstance(value, Rect2):
        return [[value.position.x, value.position.y], [value.size.x, value.size.y]]
    if isinstance(value, Transform2D):
        return [[value.origin.x, value.origin.y], value.rotation,
                [value.scale.x, value.scale.y]]
    if isinstance(value, tuple):
        return [_to_json(v) for v in value]
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json(v) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    # pygame.Surface и прочие объекты не сериализуем.
    return str(value)


#: Публичный псевдоним (используется компонентами и другими модулями).
value_to_json = _to_json


class SceneSerializer:
    """Статические методы сериализации сцен и нод."""

    # ------------------------------------------------------------------
    # Нода -> dict
    # ------------------------------------------------------------------
    @staticmethod
    def node_to_dict(node: Node) -> Dict[str, Any]:
        """Сериализует ноду в словарь."""
        from engine.nodes import NODE_CLASSES
        builtin = next((cls.__name__ for cls in type(node).__mro__ if cls in NODE_CLASSES.values()), 'Node')
        result: Dict[str, Any] = {
            "type": builtin,
            "name": node.name,
        }
        if getattr(node, 'prefab_id', ''):
            result['prefab_id'] = node.prefab_id
        if getattr(node, 'prefab', None):
            import copy
            result['prefab'] = copy.deepcopy(node.prefab)
        if node.script_path:
            result["script"] = node.script_path

        # Экспортируемые свойства.
        properties: Dict[str, Any] = {}
        for prop in node.get_property_list():
            if prop in ("name", "script"):
                continue
            if hasattr(node, prop):
                properties[prop] = _to_json(getattr(node, prop))
        if properties:
            result["properties"] = properties

        # Дополнительные данные ноды (не входящие в экспорт, но важные).
        # Обязательно прогоняем через _to_json: внутри могут быть Vector2
        # (ключевые кадры анимаций) — иначе json.dump упадёт посреди записи
        # и испортит файл сцены.
        if hasattr(node, "_serialize_data"):
            data = node._serialize_data()
            if data:
                result["data"] = _to_json(data)

        # Компоненты (навешанное поведение без скриптов).
        components: list = []
        for comp in getattr(node, "components", []) or []:
            try:
                components.append(comp.to_dict())
            except Exception:
                logger.exception("Не удалось сериализовать компонент %r", comp)
        if components:
            result["components"] = components

        # Дети.
        children = [SceneSerializer.node_to_dict(c) for c in node.get_children()]
        if children:
            result["children"] = children

        return result

    # ------------------------------------------------------------------
    # dict -> нода
    # ------------------------------------------------------------------
    @staticmethod
    def node_from_dict(data: Dict[str, Any],
                       script_system: Any = None) -> Node:
        """Восстанавливает ноду из словаря."""
        type_name = data.get("type", "Node")
        node_class = _get_node_class(type_name)
        script_path = data.get("script", "")

        # Если задан скрипт и он загружен — используем его класс (горячая привязка).
        node: Optional[Node] = None
        if script_path and script_system is not None:
            script_class = script_system.get_class_for(script_path)
            if script_class is not None and issubclass(script_class, node_class):
                try:
                    node = script_class()
                except Exception:
                    node = None
        if node is None:
            node = node_class()

        node.prefab_id = data.get("prefab_id", "")
        node.prefab = data.get("prefab")
        node.name = data.get("name", type_name)
        node.script_path = script_path

        # Свойства.
        props = data.get("properties", {})
        spec_map = node.get_exported_properties()
        for key, value in props.items():
            spec = spec_map.get(key, {})
            converted = SceneSerializer._convert_value(value, spec.get("type"))
            node.set(key, converted)

        # Спец. данные ноды.
        if "data" in data and hasattr(node, "_deserialize_data"):
            try:
                node._deserialize_data(data["data"])
            except Exception:
                logger.exception("Ошибка восстановления данных ноды %s", node.name)

        # Компоненты.
        for comp_data in data.get("components", []) or []:
            try:
                from engine.components.component import Component
                comp = Component.from_dict(comp_data)
                if comp is not None:
                    node.add_component(comp)
            except Exception:
                logger.exception("Ошибка восстановления компонента ноды %s", node.name)

        # Дети.
        for child_data in data.get("children", []):
            child = SceneSerializer.node_from_dict(child_data, script_system)
            node.add_child(child)

        return node

    @staticmethod
    def _convert_value(value: Any, value_type: Optional[str]) -> Any:
        """Преобразует JSON-значение в нужный тип на основе спецификации."""
        if value_type is None:
            return value
        try:
            if value_type == "vector2":
                return Vector2(value)
            if value_type == "rect2":
                return Rect2(Vector2(value[0]), Vector2(value[1]))
            if value_type == "color":
                if isinstance(value, (list, tuple)):
                    return tuple(int(v) for v in value)
                return value
            if value_type == "points":
                return [Vector2(p) for p in (value or [])]
            if value_type == "string_array":
                return [str(v) for v in (value or [])]
            if value_type == "int_array":
                return [int(v) for v in (value or [])]
        except Exception:
            pass
        return value

    # ------------------------------------------------------------------
    # Сцена <-> файл
    # ------------------------------------------------------------------
    @staticmethod
    def save_scene(scene: Scene, path: str) -> None:
        """Сохраняет сцену в файл .scene.

        Запись атомарная: сначала сцена целиком превращается в текст, затем
        текст пишется во временный файл и подменяет старый. Поэтому ошибка
        сериализации никогда не испортит уже существующий файл сцены.
        """
        import os
        from engine.resources.teamwork import check_reservation, revision
        check_reservation(path)
        expected=getattr(scene,'_disk_revision',None)
        if expected is not None and os.path.abspath(str(scene.path)) == os.path.abspath(str(path)) and revision(path)!=expected:
            raise RuntimeError('Файл сцены изменён другим участником. Сохраните копию и загрузите изменения.')
        payload = {
            "cloud_engine_version": _ENGINE_VERSION,
            "scene": {
                "name": scene.name,
                "root": SceneSerializer.node_to_dict(scene.root),
            },
        }
        try:
            text = json.dumps(payload, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            logger.exception("Не удалось сериализовать сцену «%s» — файл не изменён",
                             scene.name)
            raise

        directory = os.path.dirname(os.path.abspath(path)) or "."
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception:
            pass
        temporary = f"{path}.tmp"
        with open(temporary, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except Exception:
                pass
        os.replace(temporary, path)
        scene._disk_revision=revision(path)
        scene.path = path

    @staticmethod
    def load_scene(path: str, script_system: Any = None) -> Scene:
        """Загружает сцену из файла .scene."""
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        scene_data = payload.get("scene", {})
        name = scene_data.get("name", "Scene")
        root_data = scene_data.get("root", {"type": "Node", "name": "Root"})
        root = SceneSerializer.node_from_dict(root_data, script_system)
        from pathlib import Path
        project = getattr(script_system, 'project_dir', '')
        if not project:
            project = next((str(parent) for parent in Path(path).resolve().parents if (parent / 'project.json').is_file()), '')
        if project:
            from engine.resources.prefab import Prefab
            def resolve(node):
                if getattr(node, 'prefab', None):
                    try:
                        Prefab.apply(node, Prefab.updated_data(node, project), script_system)
                    except (OSError, ValueError, KeyError):
                        logger.exception('Не удалось обновить префаб %s', node.name)
                for child in node.get_children():
                    resolve(child)
            resolve(root)
        scene = Scene(name, root)
        scene.path = path
        from engine.resources.teamwork import revision
        scene._disk_revision=revision(path)
        return scene

    @staticmethod
    def scene_to_dict(scene: Scene) -> Dict[str, Any]:
        """Сериализует сцену в словарь (для копирования/вставки)."""
        return {
            "name": scene.name,
            "root": SceneSerializer.node_to_dict(scene.root),
        }

    @staticmethod
    def node_to_json_string(node: Node) -> str:
        """Сериализует ноду в JSON-строку (для буфера обмена)."""
        return json.dumps(SceneSerializer.node_to_dict(node), ensure_ascii=False)

    @staticmethod
    def node_from_json_string(text: str, script_system: Any = None) -> Optional[Node]:
        """Восстанавливает ноду из JSON-строки."""
        try:
            data = json.loads(text)
            return SceneSerializer.node_from_dict(data, script_system)
        except Exception as exc:
            logger.warning("Не удалось распарсить ноду из JSON: %s", exc)
            return None


def _get_node_class(type_name: str):
    """Возвращает класс ноды по имени (ленивый импорт реестра)."""
    try:
        from engine.nodes import NODE_CLASSES
        cls = NODE_CLASSES.get(type_name)
        if cls is not None:
            return cls
    except Exception as exc:
        logger.error("Не удалось получить класс ноды '%s': %s", type_name, exc)
    return Node
