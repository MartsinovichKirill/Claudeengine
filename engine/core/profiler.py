"""Profiler — сбор статистики производительности движка.

Хранит скользящее окно замеров по системам (физика, коллизии, рендер,
анимация, частицы, UI, скрипты, постобработка) и общие показатели кадра:
FPS, время кадра, количество нод, объектов отрисовки и компонентов.

Использование:
    Profiler.begin_frame()
    with Profiler.measure("render"):
        ...
    Profiler.end_frame()

Редактор читает готовый снимок через :meth:`Profiler.snapshot`.
"""

from __future__ import annotations

import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Deque, Dict, Iterator, List, Optional

#: Порядок систем в отчёте (для стабильного вывода в панели профилировщика).
SYSTEM_ORDER: List[str] = [
    "input", "process", "physics", "physics_logic", "physics_move", "collisions",
    "animation", "particles", "render", "light", "post_process", "ui", "audio",
    "scripts", "cleanup",
]

#: Человекочитаемые названия для интерфейса.
SYSTEM_TITLES: Dict[str, str] = {
    "input": "Ввод",
    "process": "Логика кадра (_process)",
    "physics": "Физика (интеграция)",
    "physics_logic": "Логика физики (_physics_process)",
    "physics_move": "Движение тел",
    "collisions": "Коллизии и триггеры",
    "animation": "Анимация",
    "particles": "Частицы",
    "render": "Рендер мира",
    "light": "Свет и тени",
    "post_process": "Постобработка",
    "ui": "Интерфейс",
    "audio": "Звук",
    "scripts": "Скрипты",
    "cleanup": "Очистка",
}


class Profiler:
    """Собирает тайминги систем и показатели кадра."""

    #: Сколько последних кадров учитывать.
    window: int = 120

    def __init__(self) -> None:
        self.enabled: bool = True
        self.reset()

    # ------------------------------------------------------------------
    # Сброс
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Очищает накопленную статистику."""
        self._times: Dict[str, Deque[float]] = {}
        self._frame_times: Deque[float] = deque(maxlen=self.window)
        self._fps_samples: Deque[float] = deque(maxlen=self.window)
        self._frame_start: float = 0.0
        self._marks: Dict[str, float] = {}
        self.frame_count: int = 0
        self.counters: Dict[str, int] = {}
        self.info: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Замеры
    # ------------------------------------------------------------------
    def begin_frame(self) -> None:
        """Начало кадра."""
        if not self.enabled:
            return
        self._frame_start = time.perf_counter()

    def end_frame(self, fps: float = 0.0) -> None:
        """Конец кадра: фиксирует общее время и FPS."""
        if not self.enabled:
            return
        elapsed = time.perf_counter() - self._frame_start
        self._frame_times.append(elapsed * 1000.0)
        if fps > 0.0:
            self._fps_samples.append(fps)
        self.frame_count += 1

    def add(self, system: str, milliseconds: float) -> None:
        """Добавляет замер системы в миллисекундах."""
        if not self.enabled:
            return
        bucket = self._times.get(system)
        if bucket is None:
            bucket = deque(maxlen=self.window)
            self._times[system] = bucket
        bucket.append(milliseconds)

    @contextmanager
    def measure(self, system: str) -> Iterator[None]:
        """Контекстный менеджер замера времени системы."""
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            self.add(system, (time.perf_counter() - start) * 1000.0)

    # ------------------------------------------------------------------
    # Счётчики и произвольная информация
    # ------------------------------------------------------------------
    def set_counter(self, name: str, value: int) -> None:
        """Запоминает целочисленный показатель (ноды, спрайты и т.п.)."""
        self.counters[name] = int(value)

    def set_info(self, name: str, value: Any) -> None:
        """Запоминает произвольное значение для панели."""
        self.info[name] = value

    # ------------------------------------------------------------------
    # Отчёты
    # ------------------------------------------------------------------
    def system_stats(self) -> List[Dict[str, Any]]:
        """Список замеров по системам: последнее, среднее, максимум."""
        result: List[Dict[str, Any]] = []
        names = [n for n in SYSTEM_ORDER if n in self._times]
        names += [n for n in self._times if n not in SYSTEM_ORDER]
        for name in names:
            samples = self._times.get(name)
            if not samples:
                continue
            values = list(samples)
            result.append({
                "name": name,
                "title": SYSTEM_TITLES.get(name, name),
                "last": values[-1],
                "avg": sum(values) / len(values),
                "max": max(values),
                "total": sum(values) / max(self.frame_count, 1),
            })
        return result

    def frame_stats(self) -> Dict[str, float]:
        """Показатели кадра: FPS и время кадра в миллисекундах."""
        frames = list(self._frame_times)
        fps_samples = list(self._fps_samples)
        if not frames:
            return {"fps": 0.0, "frame_ms": 0.0, "frame_max": 0.0,
                    "frame_min": 0.0, "fps_min": 0.0, "fps_max": 0.0}
        ordered = sorted(frames)
        index = min(len(ordered) - 1, int(len(ordered) * 0.95))
        return {
            "fps": (sum(fps_samples) / len(fps_samples)) if fps_samples else 0.0,
            "fps_min": min(fps_samples) if fps_samples else 0.0,
            "fps_max": max(fps_samples) if fps_samples else 0.0,
            "frame_ms": sum(frames) / len(frames),
            "frame_max": max(frames),
            "frame_min": min(frames),
            "frame_p95": ordered[index],
        }

    def fps_history(self, limit: int = 90) -> List[float]:
        """История FPS для графика."""
        values = list(self._fps_samples)[-limit:]
        return values

    def frame_history(self, limit: int = 90) -> List[float]:
        """История времени кадра для графика."""
        return list(self._frame_times)[-limit:]

    def snapshot(self) -> Dict[str, Any]:
        """Полный снимок статистики для панели редактора."""
        frame = self.frame_stats()
        systems = self.system_stats()
        measured = sum(item["avg"] for item in systems)
        return {
            "frame": frame,
            "systems": systems,
            "counters": dict(self.counters),
            "info": dict(self.info),
            "measured_ms": measured,
            "frame_count": self.frame_count,
            "fps_history": self.fps_history(),
            "frame_history": self.frame_history(),
        }

    def format_report(self, top: int = 8) -> str:
        """Текстовый отчёт (для консоли редактора)."""
        frame = self.frame_stats()
        lines = [
            f"FPS: {frame['fps']:.1f}  (мин {frame['fps_min']:.1f}, макс {frame['fps_max']:.1f})",
            f"Кадр: {frame['frame_ms']:.2f} мс  (макс {frame['frame_max']:.2f} мс)",
            "Системы:",
        ]
        systems = sorted(self.system_stats(), key=lambda item: item["avg"], reverse=True)
        for item in systems[:top]:
            lines.append(f"  {item['title']:<28} {item['avg']:6.2f} мс")
        if self.counters:
            lines.append("Счётчики:")
            for name, value in self.counters.items():
                lines.append(f"  {name:<28} {value}")
        return "\n".join(lines)


#: Глобальный профилировщик движка.
profiler = Profiler()


__all__ = ["Profiler", "profiler", "SYSTEM_ORDER", "SYSTEM_TITLES"]
