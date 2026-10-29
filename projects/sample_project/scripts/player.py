"""Пример пользовательского скрипта Cloud Engine — игрок.

Наследуемся от CharacterBody2D и переопределяем методы жизненного цикла:
_ready, _physics_process. Гравитация применяется физической системой,
скрипт управляет горизонтальной скоростью и прыжком.
"""

from engine.core.time import Time
from engine.math.vector2 import Vector2
from engine.nodes.characterbody2d import CharacterBody2D


class Player(CharacterBody2D):
    """Управляемый игрок с прыжками и сбором монет."""

    def _ready(self) -> None:
        # Параметры движения.
        self.move_speed: float = 260.0
        self.jump_force: float = -520.0

        # Игровое состояние.
        self.coins: int = 0
        self.total_coins: int = 2
        self.spawn_position: Vector2 = Vector2(self.position)
        self.energy: float = 100.0

        # Находим UI-ноды и подключаем кнопку.
        scene = self._current_scene()
        if scene is not None:
            button = scene.find_node_by_path("UI/RestartButton")
            if button is not None:
                button.connect("pressed", self._on_restart_pressed)
            timer = scene.find_node_by_path("GameTimer")
            if timer is not None:
                timer.connect("timeout", self._on_timer_timeout)

        # Подключаемся к монетам-триггерам.
        self._connect_coins()

        print(f"[Player] Готов. Позиция: {self.position}")

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------
    def _current_scene(self):
        """Возвращает текущую сцену или None."""
        tree = self.get_tree()
        return tree.current_scene if tree is not None else None

    def _connect_coins(self) -> None:
        """Подключает сигналы body_entered ко всем Area2D с именем Coin*."""
        scene = self._current_scene()
        if scene is None:
            return
        from engine.nodes.area2d import Area2D
        for node in scene.get_nodes():
            if isinstance(node, Area2D) and node.name.startswith("Coin"):
                node.connect("body_entered", self._on_coin_collected)

    def _update_hud(self) -> None:
        """Обновляет текст счёта и полосу энергии."""
        scene = self._current_scene()
        if scene is None:
            return
        label = scene.find_node_by_path("UI/ScoreLabel")
        if label is not None:
            label.text = f"Счёт: {self.coins} / {self.total_coins}"
        bar = scene.find_node_by_path("UI/EnergyBar")
        if bar is not None:
            bar.set_value(self.energy)

    # ------------------------------------------------------------------
    # Обработчики сигналов
    # ------------------------------------------------------------------
    def _on_coin_collected(self, body) -> None:
        """Сигнал body_entered от Area2D-монеты."""
        if body is not self:
            return
        self.coins += 1
        self.energy = min(100.0, self.energy + 15.0)
        self._update_hud()
        print(f"[Player] Монета собрана! Всего: {self.coins}")
        if self.coins >= self.total_coins:
            print("[Player] Все монеты собраны — победа!")

    def _on_restart_pressed(self) -> None:
        """Кнопка UI «Сбросить игрока»."""
        self.position = Vector2(self.spawn_position)
        self.velocity = Vector2()
        self.energy = 100.0
        self._update_hud()
        print("[Player] Позиция сброшена")

    def _on_timer_timeout(self) -> None:
        """Периодический сигнал Timer."""
        self.energy = max(0.0, self.energy - 5.0)
        self._update_hud()

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------
    def _physics_process(self, delta: float) -> None:
        tree = self.get_tree()
        input_manager = tree.input if tree is not None else None
        if input_manager is None:
            return

        # Горизонтальное движение.
        direction = input_manager.get_axis("move_left", "move_right")
        self.velocity.x = direction * self.move_speed

        # Прыжок.
        if input_manager.is_action_just_pressed("jump") and self.is_on_floor():
            self.velocity.y = self.jump_force
            print("[Player] Прыжок!")

        # Перезапуск по клавише R.
        if input_manager.is_action_just_pressed("restart"):
            self._on_restart_pressed()

        # Кинематическое движение со скольжением.
        self.move_and_slide()

        # Если упали ниже уровня — возвращаемся на старт.
        if self.position.y > 900.0:
            self._on_restart_pressed()

    def _process(self, delta: float) -> None:
        # Плавное восстановление энергии.
        if self.energy < 100.0:
            self.energy = min(100.0, self.energy + 2.0 * delta)

    def _exit_tree(self) -> None:
        print("[Player] Выход из дерева сцены")
