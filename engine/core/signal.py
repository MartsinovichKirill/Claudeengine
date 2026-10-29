"""Система сигналов — аналог Godot Signal.

Позволяет подключать колбэки к именованным сигналам ноды и вызывать их
через emit(). Исключения внутри обработчиков перехватываются и логируются,
чтобы одна ошибка в колбэке не роняла весь движок.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, List

logger = logging.getLogger("cloudengine.signal")


class Signal:
    """Именованный сигнал, принадлежащий ноде-владельцу."""

    def __init__(self, owner: Any = None, name: str = "") -> None:
        """Создаёт сигнал.

        :param owner: объект-владелец (обычно Node).
        :param name: имя сигнала (для отладки).
        """
        self.owner = owner
        self.name = name
        self._connections: List[Callable] = []

    def connect(self, callback: Callable) -> None:
        """Подключает колбэк. Повторное подключение того же объекта игнорируется."""
        if callback not in self._connections:
            self._connections.append(callback)

    def disconnect(self, callback: Callable) -> bool:
        """Отключает колбэк. Возвращает True, если он был подключён."""
        if callback in self._connections:
            self._connections.remove(callback)
            return True
        return False

    def is_connected(self, callback: Callable) -> bool:
        """Проверяет, подключён ли колбэк."""
        return callback in self._connections

    def get_connections(self) -> List[Callable]:
        """Возвращает копию списка подключённых колбэков."""
        return list(self._connections)

    def clear(self) -> None:
        """Отключает все колбэки."""
        self._connections.clear()

    def emit(self, *args, **kwargs) -> None:
        """Вызывает все подключённые колбэки с переданными аргументами."""
        for callback in list(self._connections):
            try:
                callback(*args, **kwargs)
            except Exception:
                logger.error(
                    "Ошибка в обработчике сигнала '%s':\n%s",
                    self.name, traceback.format_exc()
                )

    def __call__(self, *args, **kwargs) -> None:
        """Позволяет вызывать сигнал как функцию: signal(...)."""
        self.emit(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<Signal '{self.name}' connections={len(self._connections)}>"
