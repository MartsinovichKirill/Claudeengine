"""PostProcess — шейдеры и постэффекты кадра.

Узел описывает набор эффектов, которые применяются к готовому кадру:
свечение (bloom), размытие, чёрно-белый, виньетка, пикселизация,
полосы развёртки, хроматическая аберрация, тонирование, контраст,
насыщенность, постеризация, эффект ЭЛТ и вспышка (например, при уроне).

Все параметры редактируются в инспекторе. Свои эффекты можно добавлять
из кода через :func:`engine.systems.post_process.register_effect`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from engine.core.node import Node

#: Порядок применения эффектов.
EFFECT_ORDER: Tuple[str, ...] = (
    "exposure", "temperature", "gamma", "pixelate", "blur", "chromatic", "posterize", "contrast", "saturation",
    "grayscale", "tint", "bloom", "scanlines", "crt", "vignette", "flash",
)

#: Человекочитаемые названия для панели профилировщика и подсказок.
EFFECT_TITLES: Dict[str, str] = {
    "pixelate": "Пикселизация",
    "blur": "Размытие",
    "chromatic": "Хроматическая аберрация",
    "posterize": "Постеризация",
    "contrast": "Контраст",
    "saturation": "Насыщенность",
    "grayscale": "Чёрно-белый",
    "tint": "Тонирование",
    "bloom": "Свечение",
    "scanlines": "Полосы развёртки",
    "crt": "Эффект ЭЛТ",
    "vignette": "Виньетка",
    "flash": "Вспышка",
}


class PostProcess(Node):
    """Набор постэффектов, применяемых к кадру."""

    type_name = "PostProcess"
    description = "Постобработка кадра: свечение, размытие, пикселизация"

    signals = ["flash_finished"]

    exported_properties = {
        "temperature": {"type":"float","default":0.0,"min":-1.0,"max":1.0,"step":0.02},
        "bloom_radius": {"type":"float","default":6.0,"min":1.0,"max":16.0},
        "bloom_soft_knee": {"type":"float","default":0.2,"min":0.0,"max":1.0},
        "exposure": {"type":"float","default":0.0,"min":-5.0,"max":5.0,"step":0.1},
        "gamma": {"type":"float","default":1.0,"min":0.1,"max":3.0,"step":0.05},
        "shader_path": {"type": "resource", "default": ""},
        "enabled": {"type": "bool", "default": True},
        "quality": {"type": "enum", "default": "full",
                    "options": ["full", "fast"]},
        # Размытие
        "blur": {"type": "float", "default": 0.0, "min": 0.0, "max": 24.0, "step": 0.5},
        # Свечение
        "bloom": {"type": "float", "default": 0.0, "min": 0.0, "max": 2.0, "step": 0.05},
        "bloom_threshold": {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0,
                            "step": 0.02},
        # Цвет
        "grayscale": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02},
        "saturation": {"type": "float", "default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05},
        "contrast": {"type": "float", "default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05},
        "posterize": {"type": "float", "default": 0.0, "min": 0.0, "max": 8.0, "step": 1.0},
        "tint_color": {"type": "color", "default": [255, 180, 120, 255]},
        "tint": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02},
        # Геометрия экрана
        "pixelate": {"type": "float", "default": 0.0, "min": 0.0, "max": 32.0, "step": 1.0},
        "vignette": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02},
        "vignette_softness": {"type": "float", "default": 0.55, "min": 0.05, "max": 1.5,
                              "step": 0.05},
        # Аналоговые артефакты
        "scanlines": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02},
        "chromatic": {"type": "float", "default": 0.0, "min": 0.0, "max": 16.0, "step": 0.5},
        "crt": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02},
        # Вспышка (урон, взрыв, телепорт)
        "flash_color": {"type": "color", "default": [255, 255, 255, 255]},
        "flash": {"type": "float", "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02},
        # Свои эффекты из кода (имена через запятую)
        "custom": {"type": "string", "default": ""},
    }

    def __init__(self, name: str = "PostProcess") -> None:
        super().__init__(name)
        self.exposure = 0.0
        self.gamma = 1.0
        self.shader_path = ""
        self._asset_manager = None
        self.enabled: bool = True
        self.temperature = 0.0
        self.bloom_radius = 6.0
        self.bloom_soft_knee = 0.2
        self.quality: str = "full"
        self.blur: float = 0.0
        self.bloom: float = 0.0
        self.bloom_threshold: float = 0.7
        self.grayscale: float = 0.0
        self.saturation: float = 1.0
        self.contrast: float = 1.0
        self.posterize: float = 0.0
        self.tint_color: Tuple[int, int, int, int] = (255, 180, 120, 255)
        self.tint: float = 0.0
        self.pixelate: float = 0.0
        self.vignette: float = 0.0
        self.vignette_softness: float = 0.55
        self.scanlines: float = 0.0
        self.chromatic: float = 0.0
        self.crt: float = 0.0
        self.flash_color: Tuple[int, int, int, int] = (255, 255, 255, 255)
        self.flash: float = 0.0
        self.custom: str = ""

    # ------------------------------------------------------------------
    def custom_effects(self) -> List[str]:
        """Имена пользовательских эффектов из строки ``custom``."""
        return [name.strip() for name in (self.custom or "").split(",") if name.strip()]

    def active_effects(self) -> List[str]:
        """Список включённых эффектов в порядке применения."""
        result: List[str] = []
        for effect in EFFECT_ORDER:
            if effect == "bloom":
                if self.bloom > 0.0:
                    result.append(effect)
            elif effect == "tint":
                if self.tint > 0.0:
                    result.append(effect)
            elif effect == "flash":
                if self.flash > 0.0:
                    result.append(effect)
            elif effect in ("exposure", "temperature"):
                if abs(getattr(self, effect))>0.001: result.append(effect)
            elif effect in ("saturation", "contrast", "gamma"):
                if abs(float(getattr(self, effect, 1.0)) - 1.0) > 0.001:
                    result.append(effect)
            elif float(getattr(self, effect, 0.0)) > 0.0:
                result.append(effect)
        return result

    def set_asset_manager(self, manager):
        self._asset_manager = manager

    def is_active(self) -> bool:
        """Есть ли что применять."""
        return bool(self.enabled and (self.active_effects() or self.custom_effects() or getattr(self, "shader_path", "")))

    # ------------------------------------------------------------------
    def trigger_flash(self, color: Any = None, duration: float = 0.18) -> None:
        """Запускает вспышку на заданное время."""
        if color is not None:
            self.flash_color = tuple(int(v) for v in color)
        self._flash_left = max(0.0, float(duration))
        self._flash_total = max(self._flash_left, 1e-5)
        self.flash = max(self.flash, 1.0)

    def update_flash(self, delta: float) -> None:
        """Гасит вспышку со временем."""
        left = getattr(self, "_flash_left", 0.0)
        if left <= 0.0:
            if self.flash != 0.0:
                self.flash = 0.0
            return
        left = max(0.0, left - delta)
        self._flash_left = left
        total = getattr(self, "_flash_total", 1.0)
        self.flash = (left / total) if total > 0 else 0.0
        if left <= 0.0:
            self.flash = 0.0
            self.emit_signal("flash_finished")


__all__ = ["PostProcess", "EFFECT_ORDER", "EFFECT_TITLES"]
