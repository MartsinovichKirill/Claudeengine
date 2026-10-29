"""PostProcessSystem — применение эффектов к готовому кадру.

Работает с numpy: кадр забирается как массив, к нему применяются эффекты,
и результат возвращается на поверхность pygame.

Тяжёлые эффекты (свечение, ЭЛТ) можно отключить переключателем качества
``quality = fast`` у узла PostProcess.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("cloudengine.post_process")

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:  # pragma: no cover
    np = None
    HAS_NUMPY = False

#: Эффекты, которые делаются средствами самого pygame (быстрые).
PYGAME_EFFECTS = ("pixelate", "blur")

#: Тяжёлые эффекты — пропускаются в режиме качества "fast".
HEAVY_EFFECTS = ("bloom", "crt", "chromatic", "blur")

#: Пользовательские эффекты: имя -> функция(surface, value, node, context).
CUSTOM_EFFECTS: Dict[str, Callable] = {}


def register_effect(name: str, func: Callable) -> None:
    """Регистрирует свой постэффект.

    Функция вызывается как ``func(surface, value, node, context)`` и может
    менять поверхность на месте.
    """
    CUSTOM_EFFECTS[name] = func


def _luminance(arr: Any) -> Any:
    """Яркость по кадру, форма (w, h, 1)."""
    return (arr[:, :, 0:1] * 0.299 + arr[:, :, 1:2] * 0.587
            + arr[:, :, 2:3] * 0.114)


class PostProcessSystem:
    """Применяет постэффекты к кадру."""

    def __init__(self, scene_tree: Any = None) -> None:
        self.scene_tree = scene_tree
        self.node: Any = None
        self.enabled: bool = True
        self._vignette_cache: Dict[Tuple[int, int, float], Any] = {}
        self.last_effects: List[str] = []
        self._shader_time = 0.0

    # ------------------------------------------------------------------
    # Поиск узла
    # ------------------------------------------------------------------
    def find_node(self) -> Any:
        """Первый включённый узел PostProcess в сцене."""
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return None
        from engine.nodes.post_process import PostProcess
        for node in self.scene_tree.current_scene.get_nodes():
            if isinstance(node, PostProcess) and node.enabled:
                return node
            component = node.get_component("PostProcessVolume")
            if component and component.enabled:
                return component.runtime_node()
        return None

    # ------------------------------------------------------------------
    # Применение
    # ------------------------------------------------------------------
    def apply(self, surface: Any, delta: float = 0.0) -> None:
        """Применяет эффекты к поверхности кадра."""
        if not self.enabled or surface is None or not HAS_NUMPY:
            return
        node = self.find_node()
        self.node = node
        if node is None:
            self.last_effects = []
            return

        node.update_flash(delta)
        if not node.is_active():
            self.last_effects = []
            return

        try:
            width, height = surface.get_width(), surface.get_height()
            if width < 2 or height < 2:
                return
            effects = self._build_plan(node)
            self.last_effects = [name for name, _ in effects]
            self._run(surface, effects, node, width, height)
            self._shader_time += delta
            shader = getattr(node, "shader_path", "")
            manager = getattr(node, "_asset_manager", None)
            if shader and manager:
                from pathlib import Path
                from engine.systems.shader_system import apply_shader
                root = Path(manager.project_dir).resolve()
                path = (root / shader.removeprefix("res://")).resolve()
                if not path.is_relative_to(root):
                    raise ValueError("Shader path must be inside project")
                apply_shader(surface, path, self._shader_time)
                self.last_effects.append("Cloud Shader")
        except Exception:
            logger.exception("Ошибка постобработки")
            self.last_effects = []

    def _build_plan(self, node: Any) -> List[Tuple[str, float]]:
        """Список (эффект, значение) с учётом качества."""
        plan: List[Tuple[str, float]] = []
        fast = getattr(node, "quality", "full") == "fast"
        for name in node.active_effects():
            if fast and name in HEAVY_EFFECTS:
                continue
            plan.append((name, float(getattr(node, name, 0.0))))
        return plan

    def _run(self, surface: Any, plan: List[Tuple[str, float]], node: Any,
             width: int, height: int) -> None:
        """Выполняет план, группируя numpy-эффекты в один проход."""
        import pygame

        batch: List[Tuple[str, float]] = []
        for name, value in plan:
            if name in PYGAME_EFFECTS:
                self._flush(surface, batch, node, width, height)
                batch = []
                self._apply_pygame(surface, name, value, pygame, width, height)
            else:
                batch.append((name, value))
        self._flush(surface, batch, node, width, height)

        for name in node.custom_effects():
            func = CUSTOM_EFFECTS.get(name)
            if func is None:
                continue
            try:
                func(surface, 1.0, node, {"width": width, "height": height,
                                          "pygame": pygame, "np": np})
            except Exception:
                logger.exception("Ошибка своего эффекта %s", name)

    def _flush(self, surface: Any, batch: List[Tuple[str, float]], node: Any,
               width: int, height: int) -> None:
        """Применяет накопленные numpy-эффекты за один проход."""
        if not batch:
            return
        import pygame
        arr = pygame.surfarray.array3d(surface).astype(np.float32)
        for name, value in batch:
            handler = getattr(self, f"_fx_{name}", None)
            if handler is None:
                continue
            try:
                arr = handler(arr, value, node, width, height)
            except Exception:
                logger.exception("Ошибка эффекта %s", name)
        pygame.surfarray.blit_array(surface, np.clip(arr, 0, 255).astype(np.uint8))

    # ------------------------------------------------------------------
    # Быстрые эффекты средствами pygame
    # ------------------------------------------------------------------
    def _apply_pygame(self, surface: Any, name: str, value: float, pygame: Any,
                      width: int, height: int) -> None:
        if value <= 0.0:
            return
        try:
            if name == "pixelate":
                block = max(2, int(round(value)))
                small = pygame.transform.scale(
                    surface, (max(1, width // block), max(1, height // block)))
                surface.blit(pygame.transform.scale(small, (width, height)), (0, 0))
            elif name == "blur":
                factor = max(2, int(round(value / 2.0)) + 1)
                small = pygame.transform.smoothscale(
                    surface, (max(1, width // factor), max(1, height // factor)))
                surface.blit(pygame.transform.smoothscale(small, (width, height)), (0, 0))
        except Exception:
            logger.exception("Ошибка быстрого эффекта %s", name)

    # ------------------------------------------------------------------
    # Эффекты на numpy
    # ------------------------------------------------------------------
    def _fx_exposure(self, arr, value, node, width, height):
        return np.clip(arr * (2.0 ** max(-5.0,min(5.0,value))), 0, 255)

    def _fx_gamma(self, arr, value, node, width, height):
        return np.power(np.clip(arr/255.0,0,1), 1.0/max(0.1,value))*255.0

    def _fx_bloom(self, arr: Any, value: float, node: Any, width: int, height: int) -> Any:
        import pygame
        threshold = max(0.0, min(1.0, float(getattr(node, "bloom_threshold", .7))))
        knee = max(.001, float(getattr(node, "bloom_soft_knee", .2)))
        lum = _luminance(arr) / 255.0
        soft = np.clip((lum - threshold + knee) / (2 * knee), 0, 1)
        soft = soft * soft * (3 - 2 * soft)
        mask = np.maximum(np.maximum(lum - threshold, 0), soft * knee) / np.maximum(lum, .001)
        bright_surface = pygame.surfarray.make_surface(np.clip(arr * mask, 0, 255).astype(np.uint8))
        radius = max(1, min(16, float(getattr(node, 'bloom_radius', 6))))
        glow = np.zeros_like(arr)
        for factor, weight in ((radius, .6), (radius * 2, .3), (radius * 4, .1)):
            small = pygame.transform.smoothscale(bright_surface, (max(1, int(width / factor)), max(1, int(height / factor))))
            blurred = pygame.transform.smoothscale(small, (width, height))
            glow += pygame.surfarray.array3d(blurred).astype(np.float32) * weight
        return arr + glow * value

    def _fx_temperature(self, arr, value, node, width, height):
        balance = max(-1.0, min(1.0, value))
        return arr * np.array([1 + balance * .15, 1, 1 - balance * .15], dtype=np.float32)

    def _fx_chromatic(self, arr: Any, value: float, node: Any, width: int,
                      height: int) -> Any:
        shift = int(round(value))
        if shift <= 0:
            return arr
        result = arr.copy()
        indices = np.arange(width)
        result[:, :, 0] = arr[np.clip(indices - shift, 0, width - 1), :, 0]
        result[:, :, 2] = arr[np.clip(indices + shift, 0, width - 1), :, 2]
        return result

    def _fx_posterize(self, arr: Any, value: float, node: Any, width: int,
                      height: int) -> Any:
        levels = max(2.0, 9.0 - float(value))
        return np.floor(arr / 255.0 * levels) / levels * 255.0

    def _fx_contrast(self, arr: Any, value: float, node: Any, width: int,
                     height: int) -> Any:
        return (arr - 128.0) * value + 128.0

    def _fx_saturation(self, arr: Any, value: float, node: Any, width: int,
                       height: int) -> Any:
        gray = _luminance(arr)
        return gray + (arr - gray) * value

    def _fx_grayscale(self, arr: Any, value: float, node: Any, width: int,
                      height: int) -> Any:
        gray = _luminance(arr)
        return arr + (gray - arr) * max(0.0, min(1.0, value))

    def _fx_tint(self, arr: Any, value: float, node: Any, width: int,
                 height: int) -> Any:
        color = tuple(int(v) for v in tuple(node.tint_color)[:3])
        target = np.array(color, dtype=np.float32).reshape(1, 1, 3)
        return arr + (target - arr) * max(0.0, min(1.0, value))

    def _fx_scanlines(self, arr: Any, value: float, node: Any, width: int,
                      height: int) -> Any:
        result = arr.copy()
        result[:, ::2, :] *= (1.0 - 0.75 * max(0.0, min(1.0, value)))
        return result

    def _fx_vignette(self, arr: Any, value: float, node: Any, width: int,
                     height: int) -> Any:
        softness = float(getattr(node, "vignette_softness", 0.55))
        key = (width, height, round(softness, 2))
        mask = self._vignette_cache.get(key)
        if mask is None:
            xs = (np.arange(width, dtype=np.float32) - width / 2.0) / max(width / 2.0, 1.0)
            ys = (np.arange(height, dtype=np.float32) - height / 2.0) / max(height / 2.0, 1.0)
            dist = np.sqrt(xs[:, None] ** 2 + ys[None, :] ** 2)
            mask = np.clip(dist / max(softness, 0.05), 0.0, 2.0)
            if len(self._vignette_cache) > 6:
                self._vignette_cache.clear()
            self._vignette_cache[key] = mask
        factor = np.clip(1.0 - value * np.clip(mask - 0.45, 0.0, None) ** 1.5,
                         0.0, 1.0)
        return arr * factor[:, :, None]

    def _fx_crt(self, arr: Any, value: float, node: Any, width: int,
                height: int) -> Any:
        amount = max(0.0, min(1.0, value))
        result = arr.copy()
        # Полосы развёртки.
        result[:, ::2, :] *= (1.0 - 0.35 * amount)
        # Небольшой сдвиг каналов.
        shift = max(1, int(round(amount * 2.0)))
        result[:, :, 0] = np.roll(result[:, :, 0], shift, axis=0)
        result[:, :, 2] = np.roll(result[:, :, 2], -shift, axis=0)
        # Мягкое затемнение краёв.
        factor = 1.0 - 0.35 * amount
        result[:, : max(1, width // 12), :] *= factor
        result[:, -max(1, width // 12):, :] *= factor
        return result

    def _fx_flash(self, arr: Any, value: float, node: Any, width: int,
                  height: int) -> Any:
        color = tuple(int(v) for v in tuple(node.flash_color)[:3])
        target = np.array(color, dtype=np.float32).reshape(1, 1, 3)
        return arr + (target - arr) * max(0.0, min(1.0, value))

    # ------------------------------------------------------------------
    def invalidate(self) -> None:
        """Сбрасывает кэши (например, при смене сцены)."""
        self._vignette_cache.clear()
        self.node = None


__all__ = ["PostProcessSystem", "register_effect", "CUSTOM_EFFECTS"]
