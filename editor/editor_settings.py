"""Настройки редактора Cloud Engine.

Хранят раскладку dock-панелей, геометрию окна, последние проекты и
пользовательские предпочтения. Файл: `CloudEngine/editor_settings.json`.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger("cloudengine.editor_settings")

#: Значения по умолчанию.
DEFAULTS: Dict[str, Any] = {
    "window": {"geometry": "", "state": "", "maximized": False},
    "layout_version": 2,
    "docks": {},                 # имя панели -> {"visible": bool}
    "recent_projects": [],
    "last_project": "",
    "editor": {
        "grid_visible": True,
        "grid_size": 32,
        "snap_to_grid": False,
        "autosave_on_play": True,
        "autosave_interval_seconds": 60,
        "show_gizmos": True,
        "confirm_delete": False,
    },
    "theme": {"accent": "#478cbf", "font_size": 12},
}


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Рекурсивно сливает словари (значения из extra побеждают)."""
    result = dict(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class EditorSettings:
    """Чтение/запись настроек редактора."""

    def __init__(self, path: str = "") -> None:
        if not path:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if getattr(sys,'frozen',False):
                root=os.path.join(os.environ.get('LOCALAPPDATA',os.path.expanduser('~')),'CloudEngine')
            from editor.ui_profile import flavor
            path = os.path.join(root, "editor_settings_"+flavor()+".json")
        self.path = path
        self.data: Dict[str, Any] = json.loads(json.dumps(DEFAULTS))
        self.load()

    # ------------------------------------------------------------------
    # Загрузка/сохранение
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Читает настройки с диска (ошибки не критичны)."""
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self.data = _deep_merge(DEFAULTS, loaded)
        except Exception:
            logger.exception("Не удалось прочитать настройки редактора")

    def save(self) -> bool:
        """Записывает настройки на диск."""
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            return True
        except Exception:
            logger.exception("Не удалось сохранить настройки редактора")
            return False

    # ------------------------------------------------------------------
    # Доступ по «пути» через точку: get("editor.grid_size")
    # ------------------------------------------------------------------
    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node = self.data
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    # ------------------------------------------------------------------
    # Геометрия окна и dock-панели
    # ------------------------------------------------------------------
    def save_window(self, window: Any, docks: Optional[Dict[str, Any]] = None,
                    visibility: Optional[Dict[str, bool]] = None) -> None:
        """Сохраняет геометрию окна, состояние dock-панелей и их видимость.

        :param visibility: заранее собранная видимость панелей. Её нужно
            запоминать во время работы: при закрытии окна все панели уже
            скрыты, и опрос isVisible() дал бы неверный результат.
        """
        try:
            self.set("window.geometry",
                     bytes(window.saveGeometry().toBase64()).decode("ascii"))
            self.set("window.state",
                     bytes(window.saveState().toBase64()).decode("ascii"))
            self.set("window.maximized", bool(window.isMaximized()))
        except Exception:
            logger.exception("Не удалось сохранить геометрию окна")

        if visibility is None and docks:
            visibility = {}
            for name, dock in docks.items():
                try:
                    visibility[name] = bool(dock.isVisible())
                except Exception:
                    continue
        if visibility:
            self.set("docks", dict(visibility))

    def restore_window(self, window: Any) -> None:
        """Восстанавливает геометрию окна и раскладку dock-панелей."""
        try:
            from PyQt6.QtCore import QByteArray
            geo = self.get("window.geometry", "")
            if geo:
                window.restoreGeometry(QByteArray.fromBase64(geo.encode("ascii")))
            state = self.get("window.state", "")
            if state:
                window.restoreState(QByteArray.fromBase64(state.encode("ascii")))
            if self.get("window.maximized", False):
                window.showMaximized()
        except Exception:
            logger.exception("Не удалось восстановить раскладку редактора")

    def apply_dock_visibility(self, docks: Dict[str, Any]) -> None:
        """Применяет сохранённую видимость dock-панелей."""
        saved = self.get("docks", {}) or {}
        for name, dock in docks.items():
            if name in saved:
                try:
                    dock.setVisible(bool(saved[name]))
                except Exception:
                    continue

    # ------------------------------------------------------------------
    # Последние проекты
    # ------------------------------------------------------------------
    def add_recent_project(self, path: str) -> None:
        if not path:
            return
        path = os.path.abspath(path)
        recent = [p for p in self.get("recent_projects", []) if p != path]
        recent.insert(0, path)
        self.set("recent_projects", recent[:10])
        self.set("last_project", path)
