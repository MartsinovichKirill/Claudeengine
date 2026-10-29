"""GameLoop — игровой цикл с delta-time и фиксированным шагом физики.

Порядок кадра:
1. Сбор событий ввода и обновление InputManager;
2. _process(delta) для всех нод;
3. Накопление времени и фиксированные физические шаги:
   - physics_system (гравитация, интеграция);
   - _physics_process(delta);
   - collision_system (триггеры, коллизии, raycast);
4. animation_system и particle_system;
5. render_system (отрисовка мира);
6. light_system (свет и тени мира);
7. post_process_system (эффекты кадра);
8. ui_system (отрисовка UI поверх мира);
9. audio_system;
10. Очистка queue_free, отладочный оверлей и обновление Time.

Каждый этап замеряется профилировщиком (engine.core.profiler).
"""

from __future__ import annotations

import logging
import time as _time
from typing import Any, Optional

from engine.core.profiler import profiler
from engine.core.time import Time

logger = logging.getLogger("cloudengine.game_loop")


class GameLoop:
    """Управляет игровым циклом и запускает системы в правильном порядке."""

    def __init__(self, scene_tree: Any, settings: Optional[dict] = None,
                 surface: Any = None) -> None:
        self.scene_tree = scene_tree
        self.settings = settings or {}
        self.surface = surface  # pygame.Surface для рендера

        self.physics_fps: float = float(self.settings.get('physics', {}).get('physics_fps', self.settings.get("physics_fps", 60)))
        Time.physics_delta = 1.0 / max(self.physics_fps, 1.0)

        self.running: bool = False
        self.paused: bool = False

        self._accumulator: float = 0.0
        self._last_time: float = 0.0
        self._fps_accum: float = 0.0
        self._fps_frames: int = 0
        self._counter_frame: int = 0

        #: Показывать ли FPS и счётчики поверх игры.
        self.show_debug_overlay: bool = False
        self._debug_font: Any = None

        # Ссылки на системы для удобства.
        self.physics_system: Any = None
        self.collision_system: Any = None
        self.render_system: Any = None
        self.animation_system: Any = None
        self.audio_system: Any = None
        self.particle_system: Any = None
        self.ui_system: Any = None
        self.script_system: Any = None
        self.light_system: Any = None
        self.post_process_system: Any = None

    # ------------------------------------------------------------------
    # Настройка систем
    # ------------------------------------------------------------------
    def attach_systems(self, physics=None, collision=None, render=None,
                       animation=None, audio=None, particle=None,
                       ui=None, script=None, light=None, post_process=None) -> None:
        """Присоединяет системы (создаются в Viewport перед запуском)."""
        self.physics_system = physics
        self.collision_system = collision
        self.render_system = render
        self.animation_system = animation
        self.audio_system = audio
        self.particle_system = particle
        self.ui_system = ui
        self.script_system = script
        self.light_system = light
        self.post_process_system = post_process

        # Прокидываем системы в SceneTree для доступа из скриптов.
        st = self.scene_tree
        st.physics_system = physics
        st.collision_system = collision
        st.render_system = render
        st.animation_system = animation
        st.audio_system = audio
        st.particle_system = particle
        st.ui_system = ui
        st.script_system = script
        st.light_system = light
        st.post_process_system = post_process
        st.game_loop = self

    # ------------------------------------------------------------------
    # Управление циклом
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Запускает цикл."""
        self.running = True
        self._last_time = _time.perf_counter()
        self._accumulator = 0.0
        Time.reset()
        profiler.reset()

    def stop(self) -> None:
        """Останавливает цикл."""
        self.running = False

    def pause(self) -> None:
        self.paused = True
        self.scene_tree.paused = True

    def resume(self) -> None:
        self.paused = False
        self.scene_tree.paused = False

    def is_running(self) -> bool:
        return self.running

    # ------------------------------------------------------------------
    # Основной шаг
    # ------------------------------------------------------------------
    def step(self) -> None:
        """Один кадр игрового цикла."""
        if not self.running:
            return

        profiler.begin_frame()

        now = _time.perf_counter()
        delta = now - self._last_time
        self._last_time = now
        delta = min(max(delta, 0.0), Time.max_delta)
        Time.delta = delta

        # Сглаженный FPS.
        self._fps_accum += delta
        self._fps_frames += 1
        if self._fps_accum >= 0.5:
            Time.fps = self._fps_frames / self._fps_accum
            self._fps_accum = 0.0
            self._fps_frames = 0

        if not self.paused:
            Time.time += delta
            Time.frame_count += 1
            self._frame(delta)

        profiler.end_frame(Time.fps)

    # ------------------------------------------------------------------
    def _frame(self, delta: float) -> None:
        """Активная часть кадра (не выполняется на паузе)."""
        st = self.scene_tree

        # 1. Ввод.
        with profiler.measure("input"):
            if st.input is not None:
                st.input.poll_events()
                for evt in st.input.get_events():
                    st.dispatch_input(evt)

        # 2. _process.
        with profiler.measure("process"):
            st.process(Time.clamped_delta())

        # 3. Фиксированные физические шаги.
        self._accumulator += delta
        steps = 0
        while self._accumulator >= Time.physics_delta and steps < 10:
            self._fixed_step(Time.physics_delta)
            self._accumulator -= Time.physics_delta
            steps += 1
        if steps >= 10:
            self._accumulator = 0.0

        # 4. Анимация и частицы.
        with profiler.measure("animation"):
            if self.animation_system is not None:
                self.animation_system.update(Time.clamped_delta())
        with profiler.measure("particles"):
            if self.particle_system is not None:
                self.particle_system.update(Time.clamped_delta())

        # 5. Рендер мира.
        if self.render_system is not None and self.surface is not None:
            with profiler.measure("render"):
                self.render_system.render(self.surface)

        # 6. Свет и тени.
        if self.light_system is not None and self.surface is not None:
            with profiler.measure("light"):
                camera = getattr(self.render_system, "active_camera", None)
                self.light_system.render(self.surface, camera)

        # 7. Постобработка.
        if self.post_process_system is not None and self.surface is not None:
            with profiler.measure("post_process"):
                self.post_process_system.apply(self.surface, Time.clamped_delta())

        # 8. UI поверх мира.
        if self.ui_system is not None and self.surface is not None:
            with profiler.measure("ui"):
                self.ui_system.render(self.surface)

        # 9. Аудио.
        with profiler.measure("audio"):
            if self.audio_system is not None:
                self.audio_system.update(Time.clamped_delta())

        # 10. Очистка queue_free.
        with profiler.measure("cleanup"):
            st._process_pending_free()

        # 11. Обновление состояния ввода (сброс just_* флагов).
        if st.input is not None:
            st.input.update(Time.clamped_delta())

        st.flush_scene_change()
        self._update_counters()
        self._draw_debug_overlay()

    # ------------------------------------------------------------------
    def _fixed_step(self, dt: float) -> None:
        """Один фиксированный физический шаг."""
        st = self.scene_tree

        # Интеграция физики (гравитация, скорость).
        if self.physics_system is not None:
            with profiler.measure("physics"):
                self.physics_system.step(dt)

        # Пользовательская логика физики (_physics_process).
        with profiler.measure("physics_logic"):
            st.physics_process(dt)

        # Движение тел с разрешением коллизий (move_and_slide и т.п.).
        if self.physics_system is not None:
            with profiler.measure("physics_move"):
                self.physics_system.integrate(dt)

        # Детекция коллизий и триггеров.
        if self.collision_system is not None:
            with profiler.measure("collisions"):
                self.collision_system.update(dt)

    # ------------------------------------------------------------------
    # Профилировщик и отладка
    # ------------------------------------------------------------------
    def _update_counters(self) -> None:
        """Обновляет счётчики профилировщика (не каждый кадр)."""
        self._counter_frame += 1
        if self._counter_frame % 15 != 0:
            return
        st = self.scene_tree
        scene = getattr(st, "current_scene", None)
        if scene is None:
            return
        try:
            nodes = scene.get_nodes()
            profiler.set_counter("Ноды", len(nodes))
            components = sum(len(getattr(node, "components", []) or [])
                             for node in nodes)
            profiler.set_counter("Компоненты", components)
            profiler.set_counter("Кадров", Time.frame_count)
            if self.post_process_system is not None:
                profiler.set_counter("Постэффекты",
                                     len(self.post_process_system.last_effects))
            if self.light_system is not None:
                profiler.set_counter("Источники света", self.light_system.lights_drawn)
        except Exception:
            pass

    def _draw_debug_overlay(self) -> None:
        """Рисует FPS и счётчики поверх кадра (включается в меню «Отладка»)."""
        if not self.show_debug_overlay or self.surface is None:
            return
        try:
            import pygame
            if self._debug_font is None:
                if not pygame.font.get_init():
                    pygame.font.init()
                self._debug_font = pygame.font.Font(None, 20)
            frame = profiler.frame_stats()
            lines = [
                f"FPS {Time.fps:5.1f}   кадр {frame['frame_ms']:.2f} мс",
                f"Ноды {profiler.counters.get('Ноды', 0)}   "
                f"компоненты {profiler.counters.get('Компоненты', 0)}",
            ]
            systems = sorted(profiler.system_stats(),
                             key=lambda item: item["avg"], reverse=True)[:4]
            for item in systems:
                lines.append(f"{item['title'][:22]:<22} {item['avg']:5.2f} мс")
            height = 6 + len(lines) * 17
            panel = pygame.Surface((250, height), pygame.SRCALPHA)
            panel.fill((0, 0, 0, 150))
            self.surface.blit(panel, (8, 8))
            for index, text in enumerate(lines):
                rendered = self._debug_font.render(text, True, (180, 235, 180))
                self.surface.blit(rendered, (14, 12 + index * 17))
        except Exception:
            pass
