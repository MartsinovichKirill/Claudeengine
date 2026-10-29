"""Диалог настроек проекта — вместо ручного редактирования project.json.

Содержит вкладки: Общее, Окно, Физика, Ввод, Аудио, Рендер.
Сохраняет всё в `project.json` выбранного проекта.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QDialog, QTabWidget, QWidget, QVBoxLayout,
                             QHBoxLayout, QFormLayout, QLineEdit, QSpinBox,
                             QDoubleSpinBox, QCheckBox, QPushButton, QComboBox,
                             QLabel, QTableWidget, QTableWidgetItem,
                             QHeaderView, QColorDialog, QDialogButtonBox,
                             QMessageBox, QGroupBox)

logger = logging.getLogger("cloudengine.project_settings")

#: Стандартный набор действий (используется в новом проекте).
DEFAULT_ACTIONS = ["jump", "move_left", "move_right", "move_up", "move_down"]


class ProjectSettingsDialog(QDialog):
    """Редактор project.json в виде удобного меню."""

    def __init__(self, settings: Dict[str, Any], project_dir: str,
                 parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки проекта")
        self.resize(680, 560)
        self.project_dir = project_dir
        self._settings: Dict[str, Any] = copy.deepcopy(settings or {})
        self._color_button: QPushButton
        self._build_ui()

    # ==================================================================
    # Построение
    # ==================================================================
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        if self.project_dir:
            path_label = QLabel(f"Проект: {self.project_dir}")
            path_label.setStyleSheet("color: #9e9e9e;")
            layout.addWidget(path_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "Общее")
        self.tabs.addTab(self._build_window_tab(), "Окно")
        self.tabs.addTab(self._build_physics_tab(), "Физика")
        self.tabs.addTab(self._build_input_tab(), "Ввод")
        self.tabs.addTab(self._build_audio_tab(), "Аудио")
        self.tabs.addTab(self._build_render_tab(), "Рендер")
        layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.name_edit = QLineEdit(self._settings.get("name", "MyProject"))
        form.addRow("Название проекта", self.name_edit)

        self.main_scene_edit = QLineEdit(self._settings.get("main_scene", ""))
        self.main_scene_edit.setPlaceholderText("scenes/main.scene")
        form.addRow("Главная сцена", self.main_scene_edit)

        hint = QLabel("Главная сцена запускается при старте игры и открывается при загрузке проекта.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9e9e9e;")
        form.addRow("", hint)
        return page

    def _build_window_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        window = self._settings.get("window", {}) or {}
        self.win_width = QSpinBox()
        self.win_width.setRange(160, 7680)
        self.win_width.setValue(int(window.get("width", 1024)))
        form.addRow("Ширина окна", self.win_width)

        self.win_height = QSpinBox()
        self.win_height.setRange(120, 4320)
        self.win_height.setValue(int(window.get("height", 600)))
        form.addRow("Высота окна", self.win_height)

        self.win_title = QLineEdit(str(window.get("title", self._settings.get("name", ""))))
        form.addRow("Заголовок окна", self.win_title)
        self.win_resizable = QCheckBox(); self.win_resizable.setChecked(bool(window.get('resizable', True)))
        form.addRow('Изменение размера', self.win_resizable)
        self.win_fullscreen = QCheckBox(); self.win_fullscreen.setChecked(bool(window.get('fullscreen', False)))
        form.addRow('Полный экран', self.win_fullscreen)
        self.win_icon = QLineEdit(window.get('icon', ''))
        self.win_icon.setPlaceholderText('assets/icon.png')
        form.addRow('Иконка окна', self.win_icon)

        self.bg_color = tuple(window.get("background_color", [32, 32, 36]))
        self._color_button = QPushButton()
        self._color_button.setFixedSize(60, 22)
        self._refresh_color_button()
        self._color_button.clicked.connect(self._pick_background_color)
        form.addRow("Цвет фона", self._color_button)
        return page

    def _build_physics_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        physics = self._settings.get("physics", {}) or {}
        gravity = physics.get("gravity", [0.0, 980.0])

        self.gravity_x = QDoubleSpinBox()
        self.gravity_x.setRange(-100000.0, 100000.0)
        self.gravity_x.setValue(float(gravity[0]))
        form.addRow("Гравитация X", self.gravity_x)

        self.gravity_y = QDoubleSpinBox()
        self.gravity_y.setRange(-100000.0, 100000.0)
        self.gravity_y.setValue(float(gravity[1]))
        form.addRow("Гравитация Y", self.gravity_y)

        self.physics_fps = QSpinBox()
        self.physics_fps.setRange(10, 480)
        self.physics_fps.setValue(int(physics.get("physics_fps", 60)))
        form.addRow("Частота физики (FPS)", self.physics_fps)
        return page

    def _build_input_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Действия и назначенные клавиши (через запятую):"))

        self.input_table = QTableWidget(0, 2)
        self.input_table.setHorizontalHeaderLabels(["Действие", "Клавиши"])
        self.input_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.input_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.input_table, 1)

        actions = self._settings.get("input", {}) or {}
        if not actions:
            actions = {name: ["Space"] for name in DEFAULT_ACTIONS}
        for action_name, keys in actions.items():
            self._add_input_row(action_name, keys)

        buttons = QHBoxLayout()
        add_btn = QPushButton("＋ Добавить действие")
        add_btn.clicked.connect(lambda: self._add_input_row("new_action", ["Space"]))
        remove_btn = QPushButton("Удалить выбранное")
        remove_btn.clicked.connect(self._remove_input_row)
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return page

    def _add_input_row(self, action: str, keys: Any) -> None:
        row = self.input_table.rowCount()
        self.input_table.insertRow(row)
        self.input_table.setItem(row, 0, QTableWidgetItem(str(action)))
        if isinstance(keys, (list, tuple)):
            text = ", ".join(str(k) for k in keys)
        else:
            text = str(keys)
        self.input_table.setItem(row, 1, QTableWidgetItem(text))

    def _remove_input_row(self) -> None:
        row = self.input_table.currentRow()
        if row >= 0:
            self.input_table.removeRow(row)

    def _build_audio_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        audio = self._settings.get("audio", {}) or {}
        self.vol_master = self._volume_spin(float(audio.get("master", 1.0)))
        self.vol_music = self._volume_spin(float(audio.get("music", 1.0)))
        self.vol_sfx = self._volume_spin(float(audio.get("sfx", 1.0)))
        form.addRow("Master", self.vol_master)
        form.addRow("Music", self.vol_music)
        form.addRow("SFX", self.vol_sfx)
        return page

    @staticmethod
    def _volume_spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 1.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(2)
        spin.setValue(value)
        return spin

    def _build_render_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        render = self._settings.get("render", {}) or {}
        self.show_grid = QCheckBox("Показывать сетку в редакторе")
        self.show_grid.setChecked(bool(render.get("show_grid", True)))
        form.addRow("", self.show_grid)

        self.grid_size = QSpinBox()
        self.grid_size.setRange(4, 512)
        self.grid_size.setValue(int(render.get("grid_size", 32)))
        form.addRow("Размер сетки", self.grid_size)
        return page

    # ==================================================================
    # Цвет фона
    # ==================================================================
    def _refresh_color_button(self) -> None:
        r, g, b = (list(self.bg_color) + [0, 0, 0])[:3]
        self._color_button.setStyleSheet(
            f"background-color: rgb({int(r)},{int(g)},{int(b)});"
            "border: 1px solid #1a1a1a; border-radius: 3px;")

    def _pick_background_color(self) -> None:
        r, g, b = (list(self.bg_color) + [0, 0, 0])[:3]
        color = QColorDialog.getColor(QColor(int(r), int(g), int(b)), self,
                                      "Цвет фона игры")
        if color.isValid():
            self.bg_color = (color.red(), color.green(), color.blue())
            self._refresh_color_button()

    # ==================================================================
    # Сохранение
    # ==================================================================
    def get_settings(self) -> Dict[str, Any]:
        """Итоговые настройки проекта."""
        return self._collect()

    def _collect(self) -> Dict[str, Any]:
        settings = copy.deepcopy(self._settings)
        settings["name"] = self.name_edit.text().strip() or "MyProject"
        settings["main_scene"] = self.main_scene_edit.text().strip()
        settings["window"] = {
            "width": self.win_width.value(),
            "height": self.win_height.value(),
            "title": self.win_title.text().strip() or settings["name"],
            "background_color": list(self.bg_color),
            'resizable': self.win_resizable.isChecked(),
            'fullscreen': self.win_fullscreen.isChecked(),
            'icon': self.win_icon.text().strip(),
        }
        settings["physics"] = {
            "gravity": [self.gravity_x.value(), self.gravity_y.value()],
            "physics_fps": self.physics_fps.value(),
        }
        actions: Dict[str, List[str]] = {}
        for row in range(self.input_table.rowCount()):
            name_item = self.input_table.item(row, 0)
            keys_item = self.input_table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            keys_text = keys_item.text() if keys_item else ""
            if not name:
                continue
            keys = [k.strip() for k in keys_text.split(",") if k.strip()]
            actions[name] = keys
        settings["input"] = actions
        settings["audio"] = {
            **settings.get("audio", {}),
            "master": self.vol_master.value(),
            "music": self.vol_music.value(),
            "sfx": self.vol_sfx.value(),
        }
        if 'volumes' in settings['audio']:
            settings['audio']['volumes'].update({k:settings['audio'][k] for k in ('master','music','sfx')})
        settings["render"] = {
            **settings.get("render", {}),
            "show_grid": self.show_grid.isChecked(),
            "grid_size": self.grid_size.value(),
        }
        return settings

    def _on_save(self) -> None:
        self._settings = self._collect()
        if self.project_dir:
            path = os.path.join(self.project_dir, "project.json")
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(self._settings, fh, ensure_ascii=False, indent=2)
            except Exception as exc:
                logger.exception("Не удалось сохранить project.json")
                QMessageBox.warning(self, "Ошибка",
                                    f"Не удалось сохранить project.json:\n{exc}")
                return
        self.accept()
