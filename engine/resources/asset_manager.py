"""AssetManager — кэш текстур, звуков и шрифтов.

Загружает ресурсы по путям относительно каталога проекта и кэширует их,
чтобы не перечитывать файлы на каждом кадре. Поддерживает генерацию
текстур-заглушек (цветной прямоугольник), если файл не найден.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("cloudengine.asset_manager")


class AssetManager:
    """Загружает и кэширует ресурсы проекта."""

    def __init__(self, project_dir: str = "") -> None:
        self._file_signatures = {}
        self._next_poll = 0.0
        self.revision = 0
        self.project_dir = project_dir
        self.textures: Dict[str, Any] = {}   # путь -> pygame.Surface
        self.sounds: Dict[str, Any] = {}     # путь -> pygame.mixer.Sound
        self.fonts: Dict[Tuple[str, int], Any] = {}

    # ------------------------------------------------------------------
    # Пути
    # ------------------------------------------------------------------
    def set_project_dir(self, project_dir: str) -> None:
        """Устанавливает каталог проекта и сбрасывает кэш."""
        self.project_dir = project_dir
        self.clear()

    def resolve(self, path: str) -> str:
        """Превращает путь (абсолютный или относительно проекта) в абсолютный."""
        if os.path.isabs(path):
            return path
        if self.project_dir:
            return os.path.join(self.project_dir, path)
        return path

    def poll_changes(self):
        now=time.monotonic()
        if now<self._next_poll:return False
        self._next_poll=now+.5
        paths=set(self.textures)|set(self.sounds)|{key[0] for key in self.fonts}
        changed=False
        for path in paths:
            if not path:continue
            try:
                stat=os.stat(path);signature=(stat.st_mtime_ns,stat.st_size)
            except OSError:signature=None
            previous=self._file_signatures.get(path,signature)
            self._file_signatures[path]=signature
            if previous!=signature:
                self.textures.pop(path,None);self.sounds.pop(path,None)
                for key in list(self.fonts):
                    if key[0]==path:self.fonts.pop(key,None)
                changed=True
        if changed:self.revision+=1
        return changed

    def get_import_settings(self,path):
        from engine.resources.import_pipeline import import_settings
        from pathlib import Path
        resolved=self.resolve(path)
        sidecar=Path(str(resolved)+'.import.json')
        signature=sidecar.stat().st_mtime_ns if sidecar.exists() else 0
        cache=getattr(self,'_import_settings_cache',{})
        if resolved not in cache or cache[resolved][0]!=signature:
            cache[resolved]=(signature,import_settings(resolved))
        self._import_settings_cache=cache
        return cache[resolved][1]

    def exists(self, path: str) -> bool:
        return os.path.isfile(self.resolve(path))

    def get_data(self,path):
        from engine.resources.game_data import GameData
        cache=getattr(self,'_game_data_cache',{})
        if path not in cache: cache[path]=GameData(path,self.project_dir)
        self._game_data_cache=cache
        return cache[path]

    # ------------------------------------------------------------------
    # Текстуры
    # ------------------------------------------------------------------
    def get_texture(self, path: str, size: Tuple[int, int] = (32, 32)) -> Any:
        """Возвращает текстуру по пути (кэширует).

        Если файл не найден, возвращает цветную заглушку на основе хэша пути.
        """
        if not path:
            return self._placeholder(size)
        resolved = self.resolve(path)
        if resolved in self.textures:
            return self.textures[resolved]
        try:
            stat=os.stat(resolved);self._file_signatures[resolved]=(stat.st_mtime_ns,stat.st_size)
        except OSError:self._file_signatures[resolved]=None
        surface = self.load_texture(resolved, size)
        self.textures[resolved] = surface
        return surface

    def load_texture(self, path: str, size: Tuple[int, int] = (32, 32)) -> Any:
        """Загружает изображение с диска."""
        try:
            import pygame
        except Exception as exc:
            logger.error("pygame недоступен: %s", exc)
            return self._placeholder(size)

        try:
            if os.path.isfile(path):
                from engine.resources.import_pipeline import imported_path
                surface = pygame.image.load(imported_path(path,self.project_dir))
                # convert_alpha требует заданного видеорежима; в offscreen-режиме
                # редактора его нет, поэтому оптимизация необязательна.
                try:
                    surface = surface.convert_alpha()
                except Exception:
                    pass
                return surface
        except Exception as exc:
            logger.warning("Не удалось загрузить текстуру %s: %s", path, exc)
        return self._placeholder(size)

    def _placeholder(self, size: Tuple[int, int]) -> Any:
        """Создаёт цветную заглушку-квадрат."""
        try:
            import pygame
            surface = pygame.Surface(size, pygame.SRCALPHA)
            h = hash(size) & 0xFFFFFF
            color = ((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF, 255)
            surface.fill(color)
            # Рамка, чтобы заглушка была видна.
            pygame.draw.rect(surface, (255, 255, 255, 180),
                             surface.get_rect(), 1)
            return surface
        except Exception:
            return None

    def get_texture_path(self, surface: Any) -> str:
        """Возвращает путь к текстуре по поверхности (или '' если не найден)."""
        for path, s in self.textures.items():
            if s is surface:
                return path
        return ""

    # ------------------------------------------------------------------
    # Звуки
    # ------------------------------------------------------------------
    def get_sound(self, path: str) -> Any:
        """Загружает и кэширует звук (WAV/OGG)."""
        if not path:
            return None
        resolved = self.resolve(path)
        if resolved in self.sounds:
            return self.sounds[resolved]
        sound = self.load_sound(resolved)
        self.sounds[resolved] = sound
        return sound

    def load_sound(self, path: str) -> Any:
        try:
            import pygame
        except Exception as exc:
            logger.error("pygame недоступен: %s", exc)
            return None
        try:
            if os.path.isfile(path):
                from engine.resources.import_pipeline import imported_path, AUDIO_MAGIC
                actual=imported_path(path,self.project_dir)
                if actual.endswith('.caudio'):
                    import io,zlib
                    from pathlib import Path
                    raw=Path(actual).read_bytes()
                    if not raw.startswith(AUDIO_MAGIC): raise ValueError('Неверный Cloud Audio')
                    return pygame.mixer.Sound(file=io.BytesIO(zlib.decompress(raw[len(AUDIO_MAGIC):])))
                return pygame.mixer.Sound(actual)
        except Exception as exc:
            logger.warning("Не удалось загрузить звук %s: %s", path, exc)
        return None

    # ------------------------------------------------------------------
    # Шрифты
    # ------------------------------------------------------------------
    def get_font(self, path: str, size: int = 16) -> Any:
        """Загружает шрифт (файл TTF) или системный по умолчанию."""
        key = (path, size)
        if key in self.fonts:
            return self.fonts[key]
        try:
            import pygame
            if path and os.path.isfile(self.resolve(path)):
                font = pygame.font.Font(self.resolve(path), size)
            else:
                font = pygame.font.Font(None, size)
            self.fonts[key] = font
            return font
        except Exception as exc:
            logger.warning("Не удалось загрузить шрифт %s: %s", path, exc)
            return None

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------
    def tint(self, surface: Any, color: Tuple[int, int, int, int]) -> Any:
        """Возвращает копию поверхности, умноженную на цвет (modulate)."""
        if surface is None:
            return None
        if color == (255, 255, 255, 255):
            return surface
        try:
            import pygame
            copy_surface = surface.copy()
            copy_surface.fill(color, special_flags=pygame.BLEND_RGBA_MULT)
            return copy_surface
        except Exception:
            return surface

    def clear(self) -> None:
        """Очищает кэш ресурсов."""
        self._import_settings_cache={}
        self._game_data_cache={}
        self.textures.clear()
        self.sounds.clear()
        self.fonts.clear()
