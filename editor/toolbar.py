"""Toolbar — панель инструментов редактора.

Play/Pause/Stop, Save/Undo/Redo, инструменты сцены (как в Unity):
выбор, рука, перемещение, вращение, масштаб, сетка, 2D/3D.
"""

from __future__ import annotations

from typing import Any, List, Tuple

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QToolBar, QToolButton, QMenu, QWidget

from editor.align import ALIGN_MODES
from editor.icons import get_icon

#: Инструменты сцены: (код, имя иконки, подпись).
SCENE_TOOLS: List[Tuple[str, str, str]] = [
    ("select", "cursor", "Выбор (Q)"),
    ("pan", "hand", "Рука / панорама (W)"),
    ("move", "move", "Перемещение (E)"),
    ("rotate", "rotate", "Вращение (R)"),
    ("scale", "scale", "Масштаб (T)"),
]


class EditorToolbar(QToolBar):
    """Панель инструментов редактора."""

    play_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    save_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    view_mode_changed = pyqtSignal(str)
    tool_changed = pyqtSignal(str)
    grid_toggled = pyqtSignal(bool)
    gizmos_toggled = pyqtSignal(bool)
    focus_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    build_requested = pyqtSignal()
    snap_toggled = pyqtSignal(bool)
    align_requested = pyqtSignal(str)

    def __init__(self, parent: Any = None) -> None:
        super().__init__("Панель инструментов", parent)
        self.setMovable(False)
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._tool_actions = {}
        self._build()

    # ------------------------------------------------------------------
    def _action(self, icon_name: str, tooltip: str, slot,
                checkable: bool = False, shortcut: str = ""):
        action = QAction(get_icon(icon_name), tooltip, self)
        action.setToolTip(tooltip)
        if shortcut:
            action.setShortcut(shortcut)
        action.setCheckable(checkable)
        if slot is not None:
            action.triggered.connect(slot)
        return action

    def _build(self) -> None:
        # --- Воспроизведение ---
        self.play_action = self._action("play", "Играть (F5)", self.play_requested.emit)
        self.play_action.setShortcut("F5")
        self.addAction(self.play_action)

        self.pause_action = self._action("pause", "Пауза (F6)", self.pause_requested.emit)
        self.pause_action.setShortcut("F6")
        self.addAction(self.pause_action)

        self.stop_action = self._action("stop", "Остановить (F7)", self.stop_requested.emit)
        self.stop_action.setShortcut("F7")
        self.addAction(self.stop_action)

        self.addSeparator()

        # --- Файл и история ---
        self.save_action = self._action("save", "Сохранить сцену (Ctrl+S)",
                                        self.save_requested.emit)
        self.addAction(self.save_action)

        self.undo_action = self._action("undo", "Отменить (Ctrl+Z)",
                                        self.undo_requested.emit)
        self.addAction(self.undo_action)

        self.redo_action = self._action("redo", "Повторить (Ctrl+Y)",
                                        self.redo_requested.emit)
        self.addAction(self.redo_action)

        self.addSeparator()

        # --- Инструменты сцены (как в Unity) ---
        group = QActionGroup(self)
        group.setExclusive(True)
        for index, (code, icon_name, tooltip) in enumerate(SCENE_TOOLS):
            action = self._action(
                icon_name, tooltip,
                lambda checked=False, c=code: self.tool_changed.emit(c),
                checkable=True)
            if index == 0:
                action.setChecked(True)
            group.addAction(action)
            self.addAction(action)
            self._tool_actions[code] = action

        self.addSeparator()

        # --- Вид ---
        self.grid_action = self._action("grid", "Показывать сетку",
                                        self.grid_toggled.emit, checkable=True)
        self.grid_action.setChecked(True)
        self.addAction(self.grid_action)

        self.gizmo_action = self._action("eye", "Показывать маркеры нод",
                                         self.gizmos_toggled.emit, checkable=True)
        self.gizmo_action.setChecked(True)
        self.addAction(self.gizmo_action)

        self.focus_action = self._action("component", "Фокус на выбранной ноде (F)",
                                         self.focus_requested.emit)
        self.addAction(self.focus_action)

        self.mode_2d = self._action("scene", "2D режим",
                                    lambda: self.view_mode_changed.emit("2D"),
                                    checkable=True)
        self.mode_2d.setChecked(True)
        self.addAction(self.mode_2d)

        self.addSeparator()

        # --- Прилипание к сетке и выравнивание ---
        self.snap_action = self._action(
            "snap", "Прилипание к сетке (Ctrl+G)", self.snap_toggled.emit,
            checkable=True)
        self.snap_action.setChecked(True)
        self.addAction(self.snap_action)

        self.align_button = QToolButton(self)
        self.align_button.setText("Выровнять")
        self.align_button.setIcon(get_icon("align"))
        self.align_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.align_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        align_menu = QMenu(self.align_button)
        for code, title in ALIGN_MODES.items():
            action = align_menu.addAction(title)
            action.triggered.connect(
                lambda checked=False, c=code: self.align_requested.emit(c))
        self.align_button.setMenu(align_menu)
        self.addWidget(self.align_button)

        self.addSeparator()

        self.settings_action = self._action("settings", "Настройки проекта (Ctrl+,)",
                                            self.settings_requested.emit)
        self.addAction(self.settings_action)

        self.build_action = self._action("build", "Собрать EXE...",
                                         self.build_requested.emit)
        self.addAction(self.build_action)

    # ------------------------------------------------------------------
    def set_tool(self, tool: str) -> None:
        """Программно переключает активный инструмент."""
        action = self._tool_actions.get(tool)
        if action is not None:
            action.setChecked(True)

    def set_undo_enabled(self, enabled: bool) -> None:
        self.undo_action.setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool) -> None:
        self.redo_action.setEnabled(enabled)

    def set_playing(self, playing: bool, paused: bool = False) -> None:
        self.play_action.setEnabled(not playing)
        self.pause_action.setEnabled(playing and not paused)
        self.stop_action.setEnabled(playing)
