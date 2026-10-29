"""Глобальное время движка — аналог Godot Time/Engine.

Класс Time хранит текущее delta, fps и физический шаг. Доступ через
атрибуты класса: Time.delta, Time.fps.
"""

from __future__ import annotations


class Time:
    """Глобальные параметры времени движка."""

    #: Время с последнего кадра (секунды).
    delta: float = 0.0
    #: Текущий FPS (сглаженный).
    fps: float = 0.0
    #: Фиксированный шаг физики (секунды).
    physics_delta: float = 1.0 / 60.0
    #: Общее время работы игры (секунды).
    time: float = 0.0
    #: Масштаб времени (1.0 — нормально, 0.5 — замедленно).
    scale: float = 1.0
    #: Счётчик кадров.
    frame_count: int = 0
    #: Максимальное delta (защита от скачков при подвисаниях).
    max_delta: float = 0.1

    @classmethod
    def reset(cls) -> None:
        """Сбрасывает время (используется при старте игры)."""
        cls.delta = 0.0
        cls.fps = 0.0
        cls.time = 0.0
        cls.scale = 1.0
        cls.frame_count = 0

    @classmethod
    def clamped_delta(cls) -> float:
        """Возвращает delta, ограниченное max_delta, с учётом scale."""
        return min(cls.delta, cls.max_delta) * cls.scale
