"""Timer — таймер с сигналом timeout (аналог Godot Timer)."""

from __future__ import annotations

import logging

from engine.core.node import Node

logger = logging.getLogger("cloudengine.timer")


class Timer(Node):
    """Отсчитывает время и испускает сигнал timeout."""

    exported_properties = {
        "wait_time": {"type": "float", "default": 1.0, "min": 0.001, "max": 3600.0, "step": 0.1},
        "one_shot": {"type": "bool", "default": True},
        "autostart": {"type": "bool", "default": False},
        "paused": {"type": "bool", "default": False},
    }

    signals = ["timeout"]

    def __init__(self, name: str = "Timer") -> None:
        super().__init__(name)
        self.wait_time: float = 1.0
        self.one_shot: bool = True
        self.autostart: bool = False
        self.paused: bool = False
        self.time_left: float = 1.0

    def start(self, time_sec: float = None) -> None:
        """Запускает таймер (опционально с новым временем)."""
        if time_sec is not None:
            self.wait_time = time_sec
        self.time_left = self.wait_time
        self.paused = False

    def stop(self) -> None:
        self.time_left = self.wait_time
        self.paused = True

    def is_stopped(self) -> bool:
        return self.paused

    def _ready(self) -> None:
        self.time_left = self.wait_time
        if self.autostart:
            self.start()

    def _process(self, delta: float) -> None:
        if self.paused:
            return
        self.time_left -= delta
        if self.time_left <= 0.0:
            self.time_left = 0.0
            self.emit_signal("timeout")
            if self.one_shot:
                self.paused = True
            else:
                self.time_left += self.wait_time
