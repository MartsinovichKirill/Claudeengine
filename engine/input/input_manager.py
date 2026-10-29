"""InputManager — ввод: клавиатура, мышь, колесо, геймпад и action mapping.

Action mapping хранится в project.json в виде:
    "input": {
        "jump": ["Space", "W"],
        "move_left": ["A", "Left"],
        "move_right": ["D", "Right"]
    }

Поддерживаются события pygame; менеджер транслирует их в движковые
InputEvent и отслеживает состояния "pressed" / "just_pressed" / "just_released".
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.input")

#: Таблица имён клавиш pygame -> константы pygame.
_KEY_ALIASES: Dict[str, str] = {
    "Space": "SPACE", "Enter": "RETURN", "Return": "RETURN", "Esc": "ESCAPE",
    "Escape": "ESCAPE", "Ctrl": "LCTRL", "Shift": "LSHIFT", "Alt": "LALT",
    "Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT",
    "Tab": "TAB", "Backspace": "BACKSPACE", "Delete": "DELETE",
}


class InputEvent:
    """Базовое событие ввода."""

    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        return f"<InputEvent {self.__dict__}>"


class InputEventKey(InputEvent):
    """Событие клавиатуры."""

    def __init__(self, key: Any = None, pressed: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self.key = key
        self.pressed = pressed


class InputEventMouseButton(InputEvent):
    """Событие кнопки мыши."""

    def __init__(self, button: int = 0, pressed: bool = True,
                 position: Vector2 = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.button = button
        self.pressed = pressed
        self.position = position or Vector2()


class InputEventMouseMotion(InputEvent):
    """Событие движения мыши."""

    def __init__(self, position: Vector2 = None, relative: Vector2 = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.position = position or Vector2()
        self.relative = relative or Vector2()


class InputManager:
    """Собирает и хранит состояние ввода за текущий кадр."""

    def __init__(self, action_map: Optional[Dict[str, List[str]]] = None) -> None:
        self.action_map: Dict[str, List[str]] = dict(action_map or {})

        self._keys_down: set = set()           # pygame-константы клавиш
        self._keys_just_pressed: set = set()
        self._keys_just_released: set = set()

        self.mouse_position: Vector2 = Vector2()
        self.mouse_relative: Vector2 = Vector2()
        self._mouse_buttons: Dict[int, bool] = {}
        self._mouse_just_pressed: set = set()
        self._mouse_just_released: set = set()
        self.mouse_wheel: int = 0

        self._joystick: Any = None
        self._joy_axes: Dict[int, float] = {}
        self._joy_buttons: Dict[int, bool] = {}

        self._events: List[InputEvent] = []

    # ------------------------------------------------------------------
    # Инициализация геймпада
    # ------------------------------------------------------------------
    def init_joystick(self) -> bool:
        """Пытается инициализировать первый доступный геймпад."""
        try:
            import pygame
            if pygame.joystick.get_count() > 0:
                self._joystick = pygame.joystick.Joystick(0)
                self._joystick.init()
                return True
        except Exception:
            logger.exception("Не удалось инициализировать геймпад")
        return False

    # ------------------------------------------------------------------
    # Обработка событий pygame
    # ------------------------------------------------------------------
    def process_event(self, event: Any) -> None:
        """Обрабатывает одно событие pygame."""
        try:
            import pygame
        except Exception:
            return

        if event.type == pygame.KEYDOWN:
            self._keys_down.add(event.key)
            self._keys_just_pressed.add(event.key)
            self._events.append(InputEventKey(key=event.key, pressed=True))
        elif event.type == pygame.KEYUP:
            self._keys_down.discard(event.key)
            self._keys_just_released.add(event.key)
            self._events.append(InputEventKey(key=event.key, pressed=False))
        elif event.type == pygame.MOUSEMOTION:
            self.mouse_position = Vector2(event.pos[0], event.pos[1])
            self.mouse_relative = Vector2(event.rel[0], event.rel[1])
            self._events.append(InputEventMouseMotion(
                position=self.mouse_position, relative=self.mouse_relative))
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._mouse_buttons[event.button] = True
            self._mouse_just_pressed.add(event.button)
            self._events.append(InputEventMouseButton(
                button=event.button, pressed=True,
                position=Vector2(event.pos[0], event.pos[1])))
        elif event.type == pygame.MOUSEBUTTONUP:
            self._mouse_buttons[event.button] = False
            self._mouse_just_released.add(event.button)
            self._events.append(InputEventMouseButton(
                button=event.button, pressed=False,
                position=Vector2(event.pos[0], event.pos[1])))
        elif event.type == pygame.MOUSEWHEEL:
            self.mouse_wheel += event.y
        elif event.type == pygame.JOYAXISMOTION:
            self._joy_axes[event.axis] = event.value
        elif event.type == pygame.JOYBUTTONDOWN:
            self._joy_buttons[event.button] = True
        elif event.type == pygame.JOYBUTTONUP:
            self._joy_buttons[event.button] = False

    def update(self, delta: float = 0.0) -> None:
        """Вызывается в конце кадра: очищает одноразовые состояния."""
        self._keys_just_pressed.clear()
        self._keys_just_released.clear()
        self._mouse_just_pressed.clear()
        self._mouse_just_released.clear()
        self.mouse_wheel = 0
        self.mouse_relative = Vector2()
        self._events.clear()

    def poll_events(self) -> None:
        """Забирает события из очереди pygame (для ручного цикла)."""
        try:
            import pygame
            for event in pygame.event.get():
                self.process_event(event)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Клавиатура
    # ------------------------------------------------------------------
    def is_key_pressed(self, key: Any) -> bool:
        return self._name_to_key(key) in self._keys_down

    def is_key_just_pressed(self, key: Any) -> bool:
        return self._name_to_key(key) in self._keys_just_pressed

    def is_key_just_released(self, key: Any) -> bool:
        return self._name_to_key(key) in self._keys_just_released

    def _name_to_key(self, key: Any) -> Any:
        """Преобразует имя клавиши ('Space', 'D') или константу в константу pygame.

        pygame называет буквенные клавиши строчными именами (K_a..K_z),
        поэтому для одиночных букв сначала проверяется нижний регистр,
        а уже затем верхний; для остальных — верхний.
        """
        if not isinstance(key, str):
            return key
        try:
            import pygame
        except Exception:
            return key

        name = _KEY_ALIASES.get(key, key)
        if len(name) == 1 and name.isalpha():
            candidates = [f"K_{name.lower()}", f"K_{name.upper()}", name.lower()]
        else:
            candidates = [f"K_{name.upper()}", f"K_{name}", name.upper()]
        for candidate in candidates:
            value = getattr(pygame, candidate, None)
            if value is not None:
                return value
        return key

    # ------------------------------------------------------------------
    # Мышь
    # ------------------------------------------------------------------
    def is_mouse_button_pressed(self, button: int = 1) -> bool:
        return self._mouse_buttons.get(button, False)

    def is_mouse_button_just_pressed(self, button: int = 1) -> bool:
        return button in self._mouse_just_pressed

    def is_mouse_button_just_released(self, button: int = 1) -> bool:
        return button in self._mouse_just_released

    # ------------------------------------------------------------------
    # Action mapping
    # ------------------------------------------------------------------
    def add_action(self, action: str, keys: List[str]) -> None:
        self.action_map[action] = list(keys)

    def is_action_pressed(self, action: str) -> bool:
        for key in self.action_map.get(action, []):
            if self.is_key_pressed(key):
                return True
        return False

    def is_action_just_pressed(self, action: str) -> bool:
        for key in self.action_map.get(action, []):
            if self.is_key_just_pressed(key):
                return True
        return False

    def is_action_just_released(self, action: str) -> bool:
        for key in self.action_map.get(action, []):
            if self.is_key_just_released(key):
                return True
        return False

    def get_action_strength(self, action: str) -> float:
        """Сила нажатия действия (1.0, если нажато, иначе 0.0)."""
        return 1.0 if self.is_action_pressed(action) else 0.0

    def get_axis(self, negative_action: str, positive_action: str) -> float:
        """Виртуальная ось: -1..1 из двух действий."""
        value = 0.0
        if self.is_action_pressed(negative_action):
            value -= 1.0
        if self.is_action_pressed(positive_action):
            value += 1.0
        return value

    def get_vector(self, left: str, right: str, up: str, down: str) -> Vector2:
        """Возвращает 2D-вектор направления из четырёх действий."""
        x = self.get_axis(left, right)
        y = self.get_axis(up, down)
        return Vector2(x, y).normalized()

    # ------------------------------------------------------------------
    # Геймпад
    # ------------------------------------------------------------------
    def get_joy_axis(self, axis: int) -> float:
        return self._joy_axes.get(axis, 0.0)

    def is_joy_button_pressed(self, button: int) -> bool:
        return self._joy_buttons.get(button, False)

    # ------------------------------------------------------------------
    # События
    # ------------------------------------------------------------------
    def get_events(self) -> List[InputEvent]:
        """События текущего кадра."""
        return list(self._events)
