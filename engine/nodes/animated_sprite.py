"""AnimatedSprite2D — анимированный спрайт (аналог Godot AnimatedSprite2D).

Работает с набором кадров (спрайтшит или список файлов). Анимация
продвигается через AnimationSystem, вызывающий advance().
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional
import copy

from engine.math.vector2 import Vector2
from engine.nodes.sprite2d import Sprite2D

logger = logging.getLogger("cloudengine.animated_sprite")


class AnimatedSprite2D(Sprite2D):
    """Спрайт, проигрывающий последовательность кадров."""

    exported_properties = {
        "animation": {"type": "string", "default": ""},
        "speed_scale": {"type": "float", "default": 1.0, "min": 0.0, "max": 20.0},
        "speed": {"type": "float", "default": 5.0, "min": 0.1, "max": 120.0, "step": 0.1},
        "looping": {"type": "bool", "default": True},
        "playing": {"type": "bool", "default": True},
        "frame": {"type": "int", "default": 0, "min": 0, "max": 10000},
        "h_frames": {"type": "int", "default": 1, "min": 1, "max": 64},
        "v_frames": {"type": "int", "default": 1, "min": 1, "max": 64},
    }
    signals = ['frame_changed', 'animation_finished', 'animation_looped', 'hitbox_entered', 'hurtbox_entered']

    def __init__(self, name: str = "AnimatedSprite2D") -> None:
        super().__init__(name)
        self.frames: List[Any] = []          # список pygame.Surface
        self.speed: float = 5.0              # кадров в секунду
        self.looping: bool = True
        self.playing: bool = True
        self.frame: int = 0
        self.h_frames: int = 1               # кол-во кадров по горизонтали
        self.v_frames: int = 1               # по вертикали
        self._frame_time: float = 0.0
        self._frame_paths: List[str] = []    # пути кадров (для сериализации)
        self.animations = {}
        self.animation = ''
        self.speed_scale = 1.0
        self._loaded_animation = None
        self._sheet_source = None
        self._hitbox_cycle = 0

    def set_asset_manager(self, manager):
        super().set_asset_manager(manager)
        self._loaded_animation = None
        if self.animations:
            self._ensure_animation()
        elif self._frame_paths:
            self.set_frame_paths(self._frame_paths)
        elif self.texture_path and (self.h_frames > 1 or self.v_frames > 1):
            self.load_spritesheet(self.texture_path, self.h_frames, self.v_frames)

    def add_animation(self, name, paths, fps=10.0, loop=True):
        if not name or not paths:
            raise ValueError('Animation requires a name and frame paths')
        self.animations[str(name)] = {'frames': list(paths), 'fps': max(.1, float(fps)), 'loop': bool(loop)}
        self._loaded_animation = None
        if not self.animation:
            self.animation = str(name)
        self._ensure_animation()

    def _ensure_animation(self):
        if not self.animations:
            return
        if self.animation not in self.animations:
            self.animation = next(iter(self.animations))
        spec = self.animations[self.animation]
        key = (self.animation, tuple(spec.get('frames', [])), float(spec.get('fps', 10)), bool(spec.get('loop', True)))
        if key == self._loaded_animation:
            return
        self.speed, self.looping = key[2], key[3]
        self._frame_paths = list(key[1])
        self.frames = [self._asset_manager.get_texture(p) for p in self._frame_paths] if self._asset_manager else []
        self.frames = [f for f in self.frames if f is not None]
        self._frame_time = 0.0
        self.frame = 0
        if self._asset_manager:
            self._loaded_animation = key

    # ------------------------------------------------------------------
    # Кадры
    # ------------------------------------------------------------------
    def add_frame(self, surface: Any) -> None:
        """Добавляет кадр (Surface)."""
        self.frames.append(surface)

    def set_frames(self, surfaces: List[Any]) -> None:
        self.frames = list(surfaces)
        if self.frames:
            self.frame = max(0, min(self.frame, len(self.frames) - 1))

    def set_frame_paths(self, paths: List[str]) -> None:
        """Устанавливает кадры по путям через AssetManager."""
        self._frame_paths = list(paths)
        self.frames = []
        if self._asset_manager is not None:
            for p in paths:
                surf = self._asset_manager.get_texture(p)
                if surf is not None:
                    self.frames.append(surf)
        if len(paths) == 1 and (self.h_frames > 1 or self.v_frames > 1) and self.frames:
            self._slice_sheet(self.frames[0], self.h_frames, self.v_frames)

    def load_spritesheet(self, path: str, h_frames: int, v_frames: int) -> None:
        """Загружает спрайтшит и нарезает на кадры."""
        self.texture_path = path
        self.h_frames = h_frames
        self.v_frames = v_frames
        if self._asset_manager is None:
            return
        sheet = self._asset_manager.get_texture(path)
        if sheet is None:
            return
        self._sheet_source = sheet
        self._slice_sheet(sheet, h_frames, v_frames)
        self._frame_paths = [path]

    def _slice_sheet(self, sheet: Any, h_frames: int, v_frames: int) -> None:
        """Нарезает спрайтшит на кадры."""
        self.frames = []
        w = sheet.get_width() // max(h_frames, 1)
        h = sheet.get_height() // max(v_frames, 1)
        for y in range(v_frames):
            for x in range(h_frames):
                try:
                    frame = sheet.subsurface((x * w, y * h, w, h))
                    self.frames.append(frame)
                except Exception:
                    pass

    def _apply_sheet(self) -> None:
        """Если задан спрайтшит, нарезает его."""
        if (self.h_frames > 1 or self.v_frames > 1) and self.texture is not None:
            self._slice_sheet(self.texture, self.h_frames, self.v_frames)

    # ------------------------------------------------------------------
    # Управление анимацией
    # ------------------------------------------------------------------
    def play(self, name=None, restart=False) -> None:
        previous=self.animation
        if name is not None:
            if name not in self.animations:
                raise ValueError(f'Unknown animation: {name}')
            self.animation = name
            self._ensure_animation()
        if restart:
            self.frame = 0
            self._frame_time = 0.0
        if restart or self.animation != previous:self._hitbox_cycle += 1
        self.playing = True

    def stop(self) -> None:
        self.playing = False

    def pause(self):
        self.playing = False

    def set_frame(self, index: int) -> None:
        if self.frames:
            previous = self.frame
            self.frame = max(0, min(index, len(self.frames) - 1))
            self._frame_time = 0.0
            if self.frame != previous:
                self.emit_signal('frame_changed')

    def advance(self, delta: float) -> None:
        """Продвигает анимацию на delta секунд."""
        self._ensure_animation()
        if not self.playing or not self.frames:
            return
        self._frame_time += max(0, delta) * max(0, self.speed_scale)
        interval = 1.0 / max(self.speed, 0.0001)
        while self._frame_time >= interval:
            self._frame_time -= interval
            self.frame += 1
            if self.frame >= len(self.frames):
                if self.looping:
                    self.frame = 0
                    self._hitbox_cycle += 1
                    self.emit_signal('animation_looped')
                else:
                    self.frame = len(self.frames) - 1
                    self.playing = False
                    self._frame_time = 0.0
                    self.emit_signal('animation_finished')
                    break
            self.emit_signal('frame_changed')

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def _draw_local(self, surface: Any, center: Vector2, camera: Any) -> None:
        self._ensure_animation()
        if not self.frames:
            # Пытаемся отрисовать как обычный спрайт.
            if self.texture is not None:
                super()._draw_local(surface, center, camera)
            return
        index = max(0, min(self.frame, len(self.frames) - 1))
        self.texture = self.frames[index]
        columns, rows = self.hframes, self.vframes
        self.hframes = self.vframes = 1
        self._drawing_animation = True
        try:
            super()._draw_local(surface, center, camera)
        finally:
            self._drawing_animation = False
            self.hframes, self.vframes = columns, rows

    # ------------------------------------------------------------------
    # Сериализация
    # ------------------------------------------------------------------
    def _serialize_data(self) -> dict:
        return {"frame_paths": self._frame_paths,
                "h_frames": self.h_frames, "v_frames": self.v_frames,
                'animations': copy.deepcopy(self.animations)}

    def _deserialize_data(self, data: dict) -> None:
        self._frame_paths = list(data.get("frame_paths", []))
        self.h_frames = int(data.get("h_frames", 1))
        self.v_frames = int(data.get("v_frames", 1))
        self.animations = copy.deepcopy(data.get('animations', {}))
        from engine.systems.frame_hitboxes import validate_boxes
        for spec in self.animations.values():validate_boxes(spec.get('hitboxes',{}))
        self._loaded_animation = None

    def get_active_hitboxes(self):
        from engine.systems.frame_hitboxes import active_boxes
        return active_boxes(self)
