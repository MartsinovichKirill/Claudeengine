"""AudioStreamPlayer / AudioStreamPlayer2D — воспроизведение звука.

Поддерживает WAV/OGG, громкость (volume_db), pitch, зацикливание, паузу
и стоп. AudioStreamPlayer2D — позиционный звук с затуханием по расстоянию.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D

logger = logging.getLogger("cloudengine.audio")


class AudioStreamPlayer(Node):
    """Воспроизводит звуковой поток."""

    exported_properties = {
        "stream_path": {"type": "resource", "default": ""},
        "volume_db": {"type": "float", "default": 0.0, "min": -80.0, "max": 24.0, "step": 0.1},
        "pitch_scale": {"type": "float", "default": 1.0, "min": 0.01, "max": 4.0, "step": 0.01},
        "autoplay": {"type": "bool", "default": False},
        "bus": {"type": "enum", "default": "master", "options": ["master", "music", "sfx", "ui"]},
    }

    def __init__(self, name: str = "AudioStreamPlayer") -> None:
        super().__init__(name)
        self.stream_path: str = ""
        self.volume_db: float = 0.0
        self.pitch_scale: float = 1.0
        self.autoplay: bool = False
        self.bus: str = "master"

        self._sound: Any = None
        self._channel: Any = None
        self._playing: bool = False
        self._asset_manager: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager

    def _load(self) -> None:
        if self._asset_manager is not None and self.stream_path:
            self._sound = self._asset_manager.get_sound(self.stream_path)

    def play(self) -> None:
        """Начинает воспроизведение."""
        try:
            import pygame  # noqa: F401
        except Exception:
            return
        if self._sound is None:
            self._load()
        if self._sound is None:
            logger.warning("Нет звука для воспроизведения: %s", self.stream_path)
            return
        try:
            self._channel = self._sound.play()
            if self._channel is not None:
                self._channel.set_volume(self._db_to_volume(self.volume_db) * self._bus_gain())
            self._playing = True
        except Exception as exc:
            logger.warning("Ошибка воспроизведения: %s", exc)

    def stop(self) -> None:
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass
        self._playing = False

    def pause(self) -> None:
        if self._channel is not None:
            try:
                self._channel.pause()
            except Exception:
                pass

    def resume(self) -> None:
        if self._channel is not None:
            try:
                self._channel.unpause()
            except Exception:
                pass

    def is_playing(self) -> bool:
        if self._channel is not None:
            try:
                return bool(self._channel.get_busy())
            except Exception:
                pass
        return self._playing

    def set_volume_db(self, db: float) -> None:
        self.volume_db = db
        self._apply_volume()

    def _bus_gain(self):
        audio=getattr(self.get_tree(),'audio_system',None)
        return audio.gain(getattr(self,'bus','sfx')) if audio else 1.0

    def _apply_volume(self) -> None:
        if self._channel is not None:
            try:
                self._channel.set_volume(self._db_to_volume(self.volume_db) * self._bus_gain())
            except Exception:
                pass

    @staticmethod
    def _db_to_volume(db: float) -> float:
        return max(0.0, min(1.0, 10.0 ** (db / 20.0)))

    def _ready(self) -> None:
        if self.autoplay:
            self.play()


class AudioStreamPlayer2D(Node2D):
    """Позиционный звук: громкость затухает с расстоянием до камеры."""

    exported_properties = {
        "bus": {"type":"enum","default":"sfx","options":["master","music","sfx","ui"]},
        "stream_path": {"type": "resource", "default": ""},
        "volume_db": {"type": "float", "default": 0.0, "min": -80.0, "max": 24.0, "step": 0.1},
        "max_distance": {"type": "float", "default": 400.0, "min": 1.0, "max": 100000.0, "step": 10.0},
        "attenuation": {"type": "float", "default": 1.0, "min": 0.0, "max": 10.0, "step": 0.1},
        "autoplay": {"type": "bool", "default": False},
    }

    def __init__(self, name: str = "AudioStreamPlayer2D") -> None:
        super().__init__(name)
        self.bus = "sfx"
        self.stream_path: str = ""
        self.volume_db: float = 0.0
        self.max_distance: float = 400.0
        self.attenuation: float = 1.0
        self.autoplay: bool = False

        self._sound: Any = None
        self._channel: Any = None
        self._asset_manager: Any = None

    def set_asset_manager(self, manager: Any) -> None:
        self._asset_manager = manager

    def play(self) -> None:
        try:
            import pygame  # noqa: F401
        except Exception:
            return
        if self._sound is None and self._asset_manager is not None:
            self._sound = self._asset_manager.get_sound(self.stream_path)
        if self._sound is None:
            return
        try:
            self._channel = self._sound.play()
            self._update_volume()
        except Exception as exc:
            logger.warning("Ошибка воспроизведения 2D звука: %s", exc)

    def stop(self) -> None:
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass

    def _update_volume(self) -> None:
        if self._channel is None:
            return
        distance = 0.0
        tree = self.get_tree()
        camera = None
        if tree is not None and tree.render_system is not None:
            camera = tree.render_system.active_camera
        if camera is not None and hasattr(camera, "get_center"):
            distance = self.get_global_position().distance_to(camera.get_center())
        factor = 1.0
        if self.max_distance > 0:
            factor = max(0.0, 1.0 - distance / self.max_distance) ** max(self.attenuation, 0.0)
        audio=getattr(self.get_tree(),'audio_system',None)
        volume = self._db_to_volume(self.volume_db) * factor * (audio.gain(getattr(self,'bus','sfx')) if audio else 1.0)
        try:
            self._channel.set_volume(max(0.0, min(1.0, volume)))
        except Exception:
            pass

    @staticmethod
    def _db_to_volume(db: float) -> float:
        return max(0.0, min(1.0, 10.0 ** (db / 20.0)))

    def _ready(self) -> None:
        if self.autoplay:
            self.play()
