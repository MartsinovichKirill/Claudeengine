"""MainWindow — главное окно редактора Cloud Engine (dock-панели, меню, тулбар).

Компоновка в стиле Godot 4:
- центральный Viewport с вкладками сцен;
- слева/справа dock-панели: Иерархия, Инспектор, Ресурсы, Консоль, Скрипты;
- меню File / Edit / Project / Scene / Node / Debug / Help;
- панель инструментов Play / Pause / Stop / Save / Undo / Redo.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QDockWidget,
                             QMessageBox, QFileDialog, QInputDialog, QLabel,
                             QMenu, QStatusBar)

from engine.core.node import Node
from engine.core.scene import Scene
from engine.resources.asset_manager import AssetManager
from engine.resources.scene_serializer import SceneSerializer
from engine.systems.script_system import ScriptSystem
from engine.nodes import NODE_CLASSES, NODE_CATEGORIES

from editor.viewport import Viewport
from editor.scene_tabs import SceneTabs
from editor.hierarchy_panel import HierarchyPanel
from editor.inspector_panel import InspectorPanel
from editor.assets_panel import AssetsPanel
from editor.console_panel import ConsolePanel, install_console_handler
from editor.script_editor import ScriptEditor
from editor.profiler_panel import ProfilerPanel
from editor.tile_palette import TilePalette
from editor.toolbar import EditorToolbar
from editor.undo_stack import (UndoStack, PropertyCommand, AddNodeCommand,
                               RemoveNodeCommand, MoveNodeCommand,
                               AddComponentCommand, RemoveComponentCommand,
                               ComponentPropertyCommand, NodeDataCommand,
                               MultiPropertyCommand, TileEditCommand)
from editor.align import ALIGN_MODES, align as align_nodes, can_align
from editor.editor_settings import EditorSettings
from engine.components.registry import visible_categories

logger = logging.getLogger("cloudengine.editor")


from editor.workbench_tools import WorkbenchTools


class MainWindow(WorkbenchTools, QMainWindow):
    """Главное окно редактора."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cloud Engine — редактор")
        self.resize(1500, 950)

        # Состояние проекта.
        self.project_dir: str = ""
        self.settings: Dict[str, Any] = {}
        self.asset_manager: Optional[AssetManager] = None
        self.script_system: Optional[ScriptSystem] = None

        # Открытые сцены: id(scene) -> Scene.
        self.open_scenes: List[Scene] = []
        self.current_scene: Optional[Scene] = None

        self.undo_stack = UndoStack()
        self.undo_stack.on_change = self._update_undo_actions
        self.clipboard_json: str = ""
        self._inspector_lock = False

        # Настройки редактора (раскладка, предпочтения).
        self.settings_store = EditorSettings()
        self.docks: Dict[str, QDockWidget] = {}
        self._dock_visibility: Dict[str, bool] = {}
        self._closing = False

        # Виджеты (создаются в _build_ui).
        self.viewport: Viewport
        self.scene_tabs: SceneTabs
        self.hierarchy: HierarchyPanel
        self.inspector: InspectorPanel
        self.assets: AssetsPanel
        self.console: ConsolePanel
        self.script_editor: ScriptEditor
        self.toolbar: EditorToolbar

        self._build_ui()
        self._build_menus()
        self.init_workbench()
        self._build_shortcuts()
        from editor.workspace_tools import install
        install(self)
        from editor.graphics_tools import install as install_graphics
        install_graphics(self)
        self.restore_layout()
        if self.settings_store.get("workspace_revision", 0) < 3:
            self._apply_workspace_layout()
            self.settings_store.set("workspace_revision", 3)

        self.console_handler = install_console_handler(self.console)
        from editor.recovery import install as install_recovery
        install_recovery(self)
        from editor.production_tools import install as install_production_tools
        install_production_tools(self)
        from editor.cinema_tools import install as install_cinema_tools
        install_cinema_tools(self)
        from editor.appearance import install as install_appearance
        install_appearance(self)
        self.inspector.particle_edited.connect(self._on_particles_edited)
        self.console.node_requested.connect(self._focus_problem_node)
        logger.info("Редактор Cloud Engine запущен")

        # Автозагрузка sample-проекта, если он есть рядом.
        # Проект выбирается в Cloud Hub.

    # ==================================================================
    # Построение интерфейса
    # ==================================================================
    def _build_ui(self) -> None:
        # Центральная область: вкладки сцен + viewport.
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scene_tabs = SceneTabs()
        self.scene_tabs.setMaximumHeight(42)
        self.scene_tabs.current_scene_changed.connect(self._on_tab_changed)
        self.scene_tabs.scene_closed.connect(self._on_scene_closed)
        layout.addWidget(self.scene_tabs)

        self.viewport = Viewport()
        self.viewport.node_selected.connect(self._on_viewport_node_selected)
        self.viewport.selection_changed.connect(self._on_viewport_selection)
        self.viewport.mouse_world_position.connect(self._on_mouse_world)
        self.viewport.asset_dropped.connect(self._on_asset_dropped)
        self.viewport.node_property_edited.connect(self._on_node_property_edited)
        self.viewport.component_add_requested.connect(self.add_component_to_node)
        self.viewport.component_remove_requested.connect(self.remove_component_from_node)
        self.viewport.nodes_property_edited.connect(self._on_nodes_property_edited)
        self.viewport.tile_edited.connect(self._on_tile_edited)
        layout.addWidget(self.viewport, 1)

        self.setCentralWidget(central)

        # Панель инструментов.
        self.toolbar = EditorToolbar(self)
        self.toolbar.setObjectName("MainToolBar")
        self.toolbar.play_requested.connect(self.play_game)
        self.toolbar.pause_requested.connect(self.pause_game)
        self.toolbar.stop_requested.connect(self.stop_game)
        self.toolbar.save_requested.connect(self.save_scene)
        self.toolbar.undo_requested.connect(self.undo)
        self.toolbar.redo_requested.connect(self.redo)
        self.toolbar.view_mode_changed.connect(self.viewport.set_view_mode)
        self.toolbar.tool_changed.connect(self._on_tool_changed)
        self.toolbar.grid_toggled.connect(self._on_grid_toggled)
        self.toolbar.gizmos_toggled.connect(self._on_gizmos_toggled)
        self.toolbar.focus_requested.connect(self.focus_selected)
        self.toolbar.settings_requested.connect(self.open_project_settings)
        self.toolbar.build_requested.connect(self.build_exe)
        self.toolbar.snap_toggled.connect(self._toggle_snap)
        self.toolbar.align_requested.connect(self.align_selected)
        self.addToolBar(self.toolbar)
        # Dock: Иерархия.
        self.hierarchy = HierarchyPanel()
        self.hierarchy.node_selected.connect(self._on_hierarchy_selected)
        self.hierarchy.add_node_requested.connect(self.add_node)
        self.hierarchy.delete_node_requested.connect(self.delete_node)
        self.hierarchy.duplicate_node_requested.connect(self.duplicate_node)
        self.hierarchy.rename_node_requested.connect(self.rename_node)
        self.hierarchy.node_moved.connect(self.move_node)
        self.hierarchy.component_add_requested.connect(
            lambda type_name, node: self.add_component_to_node(node, type_name))
        self.hierarchy.component_remove_requested.connect(
            lambda component, node: self.remove_component_from_node(node, component))
        self._add_dock("Сцена (Hierarchy)", self.hierarchy,
                       Qt.DockWidgetArea.LeftDockWidgetArea)

        # Dock: Инспектор.
        self.inspector = InspectorPanel()
        self.inspector.property_changed.connect(self._on_property_changed)
        self.inspector.component_add_requested.connect(self.add_component_to_node)
        self.inspector.component_remove_requested.connect(self.remove_component_from_node)
        self.inspector.component_property_changed.connect(self._on_component_property_changed)
        self.inspector.component_enabled_changed.connect(self._on_component_enabled_changed)
        self.inspector.animation_edited.connect(self._on_animation_edited)
        self.inspector.component_data_edited.connect(lambda component, old, new: self.undo_stack.execute(NodeDataCommand(component, old, new, 'Изменить граф состояний')))
        self._add_dock("Инспектор", self.inspector,
                       Qt.DockWidgetArea.RightDockWidgetArea)

        # Dock: Ресурсы.
        self.assets = AssetsPanel()
        self.assets.resource_moved.connect(self._resource_moved)
        self.assets.open_scene.connect(self.open_scene)
        self.assets.open_script.connect(self.open_script)
        self.assets.attach_script.connect(self.attach_text_script)
        self.assets.open_image.connect(self.open_sprite_studio)
        self.assets.new_scene_requested.connect(self._create_scene_file)
        self.assets.new_script_requested.connect(self._create_script_file)
        self.assets.assets_imported.connect(self._on_assets_imported)


        self._add_dock("Ресурсы (FileSystem)", self.assets,
                       Qt.DockWidgetArea.LeftDockWidgetArea)

        # Dock: Консоль.
        self.console = ConsolePanel()
        self.console.location_requested.connect(self.open_script_location)
        self._add_dock("Консоль", self.console, Qt.DockWidgetArea.BottomDockWidgetArea)

        # Dock: Редактор скриптов.
        self.script_editor = ScriptEditor()
        self._add_dock("Скрипт", self.script_editor,
                       Qt.DockWidgetArea.BottomDockWidgetArea)

        # Dock: Профилировщик.
        self.profiler = ProfilerPanel()
        self._add_dock("Профилировщик", self.profiler,
                       Qt.DockWidgetArea.RightDockWidgetArea)

        # Dock: Палитра тайлов (рисование по TileMap).
        self.palette = TilePalette()
        self.palette.tileset_edited.connect(lambda node, before, after: self.undo_stack.execute(NodeDataCommand(node, before, after, 'Настройки набора тайлов')))
        self.palette.tool_changed.connect(self._on_tile_tool_changed)
        self.palette.tile_changed.connect(self._on_tile_id_changed)
        self.palette.collision_changed.connect(self._on_tile_collision_changed)
        self.palette.layer_requested.connect(self._add_tile_layer)
        self.palette.cell_size_changed.connect(self._on_tile_cell_size)
        self.palette.clear_requested.connect(self.clear_tilemap)
        self.palette.grid_toggled.connect(self._on_tile_grid_toggled)
        self._add_dock("Плитки (TileMap)", self.palette,
                       Qt.DockWidgetArea.RightDockWidgetArea)

        # Статус-бар.
        self.status_label = QLabel("Готово")
        status = QStatusBar()
        status.addWidget(self.status_label)
        self.setStatusBar(status)

    def _apply_workspace_layout(self):
        self.setDockNestingEnabled(True)
        for name in ("Сцена (Hierarchy)", "Ресурсы (FileSystem)", "Инспектор", "Консоль", "Скрипт"):
            self.docks[name].show()
        self.splitDockWidget(self.docks["Сцена (Hierarchy)"],
                             self.docks["Ресурсы (FileSystem)"], Qt.Orientation.Vertical)
        self.splitDockWidget(self.docks["Консоль"], self.docks["Скрипт"], Qt.Orientation.Horizontal)
        self.docks["Профилировщик"].hide()
        self.docks["Плитки (TileMap)"].hide()
        self.resizeDocks([self.docks["Сцена (Hierarchy)"], self.docks["Инспектор"]],
                         [240, 310], Qt.Orientation.Horizontal)
        self.resizeDocks([self.docks["Консоль"]], [220], Qt.Orientation.Vertical)

    def _add_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setObjectName(title)
        dock.setWindowTitle(title.split(" (")[0])
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(area, dock)
        self.docks[title] = dock
        self._dock_visibility[title] = True
        dock.visibilityChanged.connect(
            lambda visible, name=title: self._on_dock_visibility(name, visible))
        return dock

    def _on_dock_visibility(self, name: str, visible: bool) -> None:
        """Запоминает видимость панели (кроме момента закрытия окна)."""
        if not self._closing:
            self._dock_visibility[name] = bool(visible)

    # ==================================================================
    # Сохранение и восстановление раскладки
    # ==================================================================
    def save_layout(self) -> None:
        """Сохраняет раскладку dock-панелей и геометрию окна."""
        self.settings_store.save_window(self, self.docks, self._dock_visibility)
        self.settings_store.save()

    def restore_layout(self) -> None:
        """Восстанавливает сохранённую раскладку."""
        self.settings_store.restore_window(self)
        self.settings_store.apply_dock_visibility(self.docks)
        for name, dock in self.docks.items():
            self._dock_visibility[name] = bool(dock.isVisible())

        # Настройки вида.
        self.viewport.show_gizmos = bool(
            self.settings_store.get("editor.show_gizmos", True))
        self.viewport.show_grid = bool(
            self.settings_store.get("editor.grid_visible", True))
        self.viewport.show_ui_overlay = bool(
            self.settings_store.get("editor.show_ui_overlay", False))
        if hasattr(self, "act_ui_overlay"):
            self.act_ui_overlay.setChecked(self.viewport.show_ui_overlay)
        debug_overlay = bool(self.settings_store.get("editor.debug_overlay", False))
        if hasattr(self, "act_debug_overlay"):
            self.act_debug_overlay.setChecked(debug_overlay)
        self.settings["debug_overlay"] = debug_overlay

        # Прилипание к сетке.
        self.viewport.snap_to_grid = bool(
            self.settings_store.get("editor.snap_to_grid", True))
        self.viewport.grid_size = float(
            self.settings_store.get("editor.grid_size", 32.0))
        if hasattr(self, "act_snap"):
            self.act_snap.setChecked(self.viewport.snap_to_grid)
        if hasattr(self, "toolbar") and hasattr(self.toolbar, "snap_action"):
            self.toolbar.snap_action.setChecked(self.viewport.snap_to_grid)
        if hasattr(self, "toolbar"):
            self.toolbar.gizmo_action.setChecked(self.viewport.show_gizmos)
            self.toolbar.grid_action.setChecked(self.viewport.show_grid)

    def reset_layout(self) -> None:
        """Сбрасывает раскладку к стандартной."""
        for name, dock in self.docks.items():
            dock.setFloating(False)
            dock.setVisible(True)
        areas = {
            "Сцена (Hierarchy)": Qt.DockWidgetArea.LeftDockWidgetArea,
            "Инспектор": Qt.DockWidgetArea.RightDockWidgetArea,
            "Ресурсы (FileSystem)": Qt.DockWidgetArea.LeftDockWidgetArea,
            "Консоль": Qt.DockWidgetArea.BottomDockWidgetArea,
            "Скрипт": Qt.DockWidgetArea.BottomDockWidgetArea,
            "Визуальный скрипт": Qt.DockWidgetArea.BottomDockWidgetArea,
        }
        for name, area in areas.items():
            dock = self.docks.get(name)
            if dock is not None:
                self.addDockWidget(area, dock)
        self._apply_workspace_layout()
        self.console.log("Раскладка интерфейса сброшена", "INFO")

    # ==================================================================
    # Меню
    # ==================================================================
    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # Файл.
        file_menu = menubar.addMenu("Файл")
        self.plugins_menu = menubar.addMenu('Плагины')
        templates_menu = menubar.addMenu('Шаблоны')
        templates_menu.addAction('Контроллер игрока 2D…', self.open_templates)
        templates_menu.addAction('Анимации AnimatedSprite2D…', self.edit_sprite_animations)
        templates_menu.addAction('Хитбоксы по кадрам…', self.edit_frame_hitboxes)
        self.plugins_menu.addAction('Менеджер плагинов…', self.open_plugins)
        self.plugins_menu.addSeparator()
        from editor.plugin_system import PluginHost
        self.plugin_host = PluginHost(self, self.plugins_menu)
        QTimer.singleShot(0, self.plugin_host.reload)
        self._add_action(file_menu, "Новая сцена", self.new_scene, "Ctrl+N")
        self._add_action(file_menu, "Открыть сцену...", self.open_scene_dialog, "Ctrl+O")
        self._add_action(file_menu, "Сохранить сцену", self.save_scene, "Ctrl+S")
        self._add_action(file_menu, "Сохранить как...", self.save_scene_as, "Ctrl+Shift+S")
        file_menu.addSeparator()
        self._add_action(file_menu, "Открыть проект...", self.open_project_dialog)
        self._add_action(file_menu, "Новый проект...", self.new_project_dialog)
        self._add_action(file_menu, "Настройки проекта...", self.open_project_settings,
                         "Ctrl+,")
        file_menu.addSeparator()
        self._add_action(file_menu, "Собрать EXE...", self.build_exe)
        file_menu.addSeparator()
        self._add_action(file_menu, "Выход", self.close, "Ctrl+Q")

        # Правка.
        from editor.localization import language_menu
        language_menu(menubar.addMenu("Язык / Language"))
        edit_menu = menubar.addMenu("Правка")
        self.act_undo = self._add_action(edit_menu, "Отменить", self.undo, "Ctrl+Z")
        self.act_redo = self._add_action(edit_menu, "Повторить", self.redo, "Ctrl+Y")
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Дублировать ноду", self.duplicate_selected, "Ctrl+D")
        self._add_action(edit_menu, "Удалить ноду", self.delete_selected, "Delete")
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Копировать", self.copy_selected, "Ctrl+C")
        self._add_action(edit_menu, "Вставить", self.paste_node, "Ctrl+V")
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Фокус на ноде", self.focus_selected, "F")

        # Выравнивание объектов.
        align_menu = menubar.addMenu("Выровнять")
        for code, title in ALIGN_MODES.items():
            shortcut = ""
            if code == "left":
                shortcut = "Ctrl+Alt+L"
            elif code == "right":
                shortcut = "Ctrl+Alt+R"
            elif code == "center_h":
                shortcut = "Ctrl+Alt+H"
            elif code == "center_v":
                shortcut = "Ctrl+Alt+V"
            self._add_action(align_menu, title,
                             lambda checked=False, c=code: self.align_selected(c),
                             shortcut)

        # Проект.
        project_menu = menubar.addMenu("Проект")
        self._add_action(project_menu, "Запустить проект", self.play_game, "F5")
        self._add_action(project_menu, "Настройки проекта",
                         self.show_project_settings)

        # Сцена.
        scene_menu = menubar.addMenu("Сцена")
        self._add_action(scene_menu, "Новая сцена", self.new_scene)
        self._add_action(scene_menu, "Сохранить сцену", self.save_scene, "Ctrl+S")
        self._add_action(scene_menu, "Закрыть сцену", self.close_current_scene)

        # Нода.
        node_menu = menubar.addMenu("Нода")
        for category, types in NODE_CATEGORIES.items():
            cat_menu = node_menu.addMenu(category)
            for type_name in types:
                action = cat_menu.addAction(type_name)
                action.triggered.connect(
                    lambda checked=False, t=type_name: self.add_node(t, None))
        node_menu.addSeparator()
        self._add_action(node_menu, "Привязать скрипт...", self.attach_script)
        self._add_action(node_menu, "Отвязать скрипт", self.detach_script)

        # Компоненты (навешиваются на выбранный объект).
        comp_menu = menubar.addMenu("Компонент")
        self._add_action(comp_menu, "Добавить компонент...", self.pick_component)
        comp_menu.addSeparator()
        for category, types in visible_categories().items():
            cat_menu = comp_menu.addMenu(category)
            for type_name in types:
                action = cat_menu.addAction(type_name)
                action.triggered.connect(
                    lambda checked=False, t=type_name: self.add_component_selected(t))
        comp_menu.addSeparator()
        self._add_action(comp_menu, "Удалить все компоненты", self.clear_components)

        # Вид (управление dock-панелями).
        view_menu = menubar.addMenu("Вид")
        collisions=view_menu.addAction('Проверка коллизий')
        collisions.setCheckable(True)
        collisions.toggled.connect(lambda value:setattr(self.viewport,'show_collision_debug',value))

        for name, dock in self.docks.items():
            action = dock.toggleViewAction()
            action.setText(name)
            view_menu.addAction(action)
        view_menu.addSeparator()
        # Прилипание к сетке.
        self.act_snap = self._add_action(view_menu, "Прилипание к сетке",
                                         self._toggle_snap)
        self.act_snap.setCheckable(True)
        self.act_snap.setChecked(True)
        self.act_snap.setShortcut("Ctrl+G")
        size_menu = view_menu.addMenu("Шаг сетки")
        for size in (8, 16, 32, 48, 64, 128):
            action = size_menu.addAction(f"{size} px")
            action.triggered.connect(
                lambda checked=False, s=size: self._set_grid_size(s))
        view_menu.addSeparator()
        self.act_ui_overlay = self._add_action(
            view_menu, "Показывать UI-слой в редакторе", self._toggle_ui_overlay)
        self.act_ui_overlay.setCheckable(True)
        self.act_ui_overlay.setChecked(False)
        view_menu.addSeparator()
        self._add_action(view_menu, "Сбросить раскладку", self.reset_layout)
        self._add_action(view_menu, "Сохранить раскладку", self.save_layout)

        # Отладка.
        debug_menu = menubar.addMenu("Отладка")
        self._add_action(debug_menu, "Перезагрузить скрипты", self.reload_scripts)
        self._add_action(debug_menu, "Очистить консоль", lambda: self.console.clear())
        self._add_action(debug_menu, "Играть", self.play_game, "F5")
        self._add_action(debug_menu, "Пауза", self.pause_game, "F6")
        self._add_action(debug_menu, "Стоп", self.stop_game, "F7")
        debug_menu.addSeparator()
        self.act_debug_overlay = self._add_action(
            debug_menu, "Показывать FPS в игре", self._toggle_debug_overlay)
        self.act_debug_overlay.setCheckable(True)
        self._add_action(debug_menu, "Отчёт профилировщика в консоль",
                         self.report_profiler)
        self._add_action(debug_menu, "Сбросить профилировщик",
                         lambda: self.profiler._on_reset())

        self._update_undo_actions()

    def _add_action(self, menu: QMenu, text: str, slot, shortcut: str = "") -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_shortcuts(self) -> None:
        """Дополнительные горячие клавиши на уровне окна."""
        # Инструменты сцены (как в Unity): Q W E R T.
        for key, tool in (("Q", "select"), ("W", "pan"), ("E", "move"),
                          ("R", "rotate"), ("T", "scale")):
            action = QAction(self)
            action.setObjectName("Scene tool " + tool)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(
                lambda checked=False, t=tool: self._select_tool(t))
            self.addAction(action)

    def _select_tool(self, tool: str) -> None:
        """Переключает инструмент сцены (из горячей клавиши)."""
        self.viewport.tool = tool
        if hasattr(self, "toolbar"):
            self.toolbar.set_tool(tool)
        self.status_label.setText(f"Инструмент: {tool}")

    # ==================================================================
    # Проект
    # ==================================================================
    def _autoload_sample_project(self) -> None:
        """Пытается открыть sample-проект рядом с движком."""
        if self.project_dir:
            # Проект уже открыт (например, передан аргументом командной строки).
            return
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample = os.path.join(root, "projects", "sample_project")
        if os.path.isdir(sample):
            self.open_project(sample)

    def open_project(self, path: str) -> None:
        """Открывает проект по пути."""
        self.recovery.capture()
        self.project_dir = os.path.abspath(path)
        path = self.project_dir
        self.console.project_dir = path
        self.recovery.set_project(path)
        QTimer.singleShot(0, self.recovery.offer_restore)
        project_file = os.path.join(path, "project.json")
        self.settings = {}
        if os.path.isfile(project_file):
            try:
                with open(project_file, "r", encoding="utf-8") as fh:
                    self.settings = json.load(fh)
            except Exception:
                logger.exception("Не удалось прочитать project.json")
        else:
            # Создаём минимальный project.json.
            self.settings = {"name": os.path.basename(path), "main_scene": ""}
            try:
                with open(project_file, "w", encoding="utf-8") as fh:
                    json.dump(self.settings, fh, ensure_ascii=False, indent=2)
            except Exception:
                pass

        self.asset_manager = AssetManager(path)
        from editor.project_hub import remember_project
        remember_project(path)
        self.script_editor.project_dir = path
        self.script_system = ScriptSystem(path)
        self.script_system.reload()

        self.assets.set_project_dir(path)
        self.viewport.set_asset_manager(self.asset_manager)
        self.setWindowTitle(f"Cloud Engine — {self.settings.get('name', path)}")
        self.console.log(f"Проект открыт: {path}", "INFO")

        main_scene = self.settings.get("main_scene", "")
        if main_scene:
            scene_path = os.path.join(path, main_scene)
            if os.path.isfile(scene_path):
                self.open_scene(scene_path)
                return
        # Если main_scene не задан — открываем первую сцену из scenes/.
        scenes_dir = os.path.join(path, "scenes")
        if os.path.isdir(scenes_dir):
            for fname in sorted(os.listdir(scenes_dir)):
                if fname.endswith(".scene"):
                    self.open_scene(os.path.join(scenes_dir, fname))
                    break

    def open_project_dialog(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Открыть проект", self.project_dir or "")
        if path:
            self.open_project(path)

    def new_project_dialog(self):
        from editor.project_hub import ProjectHub
        hub = ProjectHub()
        if hub.exec():
            self.open_project(hub.project_path)

    def show_project_settings(self) -> None:
        """Показывает настройки проекта в диалоге."""
        if not self.settings:
            QMessageBox.information(self, "Настройки проекта", "Проект не открыт.")
            return
        text = json.dumps(self.settings, ensure_ascii=False, indent=2)
        box = QMessageBox(self)
        box.setWindowTitle("Настройки проекта")
        box.setText(f"project.json\n\n{text}")
        box.exec()

    # ==================================================================
    # Сцены
    # ==================================================================
    def new_scene(self) -> None:
        """Создаёт новую сцену."""
        from engine.nodes.game_object import GameObject
        name, ok = QInputDialog.getText(self, "Новая сцена", "Имя сцены:", text="NewScene")
        if not ok or not name.strip():
            return
        scene = Scene(name.strip(), GameObject(name.strip()))
        self._register_scene(scene)
        self.console.log(f"Создана сцена: {scene.name}", "INFO")

    def open_scene(self, path: str) -> None:
        """Открывает сцену из файла (или переключается на уже открытую)."""
        path = os.path.abspath(path)
        for scene in self.open_scenes:
            if scene.path and os.path.abspath(scene.path) == path:
                self._activate_scene(scene)
                return
        try:
            scene = SceneSerializer.load_scene(path, self.script_system)
        except Exception:
            logger.exception("Не удалось открыть сцену %s", path)
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть сцену:\n{path}")
            return
        self._register_scene(scene)
        self.console.log(f"Открыта сцена: {path}", "INFO")

    def open_scene_dialog(self) -> None:
        start = os.path.join(self.project_dir, "scenes") if self.project_dir else ""
        path, _ = QFileDialog.getOpenFileName(self, "Открыть сцену", start,
                                              "Cloud Engine Scene (*.scene)")
        if path:
            self.open_scene(path)

    def _register_scene(self, scene: Scene) -> None:
        scene._project_dir = self.project_dir
        self.open_scenes.append(scene)
        self.scene_tabs.add_scene(scene)
        self._activate_scene(scene)

    def _activate_scene(self, scene: Scene) -> None:
        self.current_scene = scene
        # Переключаем вкладку.
        for i, sc in enumerate(self.scene_tabs.scenes()):
            if sc is scene:
                self.scene_tabs.setCurrentIndex(i)
                break
        self.hierarchy.set_scene(scene)
        self.viewport.set_scene(scene)
        if self.asset_manager is not None:
            self.viewport.set_asset_manager(self.asset_manager)
        self.undo_stack.clear()
        self.inspector.set_node(None)
        self._update_title()

    def _on_tab_changed(self, scene: Any) -> None:
        if scene is not None and scene is not self.current_scene:
            self._activate_scene(scene)

    def _on_scene_closed(self, scene: Any) -> None:
        if scene in self.open_scenes:
            self.open_scenes.remove(scene)
        if self.current_scene is scene:
            self.current_scene = self.open_scenes[0] if self.open_scenes else None
            self.hierarchy.set_scene(self.current_scene)
            self.viewport.set_scene(self.current_scene)
        self._update_title()

    def close_current_scene(self) -> None:
        if self.current_scene is None:
            return
        for i, sc in enumerate(self.scene_tabs.scenes()):
            if sc is self.current_scene:
                self.scene_tabs.close_tab(i)
                break

    def save_scene(self) -> None:
        if self.script_editor.editor.hasFocus():
            self.script_editor.save()
            return
        if self.current_scene is None:
            return
        if not self.current_scene.path:
            self.save_scene_as()
            return
        try:
            SceneSerializer.save_scene(self.current_scene, self.current_scene.path)
            self.console.log(f"Сцена сохранена: {self.current_scene.path}", "INFO")
        except Exception:
            logger.exception("Не удалось сохранить сцену")
            QMessageBox.warning(self, "Ошибка", "Не удалось сохранить сцену")

    def save_scene_as(self) -> None:
        if self.current_scene is None:
            return
        start = os.path.join(self.project_dir, "scenes") if self.project_dir else ""
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить сцену", start,
                                              "Cloud Engine Scene (*.scene)")
        if path:
            if not path.endswith(".scene"):
                path += ".scene"
            try:
                SceneSerializer.save_scene(self.current_scene, path)
                self.scene_tabs.set_scene_name(self.current_scene, self.current_scene.name)
                self.assets.refresh()
                self.console.log(f"Сцена сохранена: {path}", "INFO")
            except Exception:
                logger.exception("Не удалось сохранить сцену")
        self._update_title()

    def _update_title(self) -> None:
        if self.current_scene is None:
            self.setWindowTitle("Cloud Engine — редактор")
            return
        path = self.current_scene.path or "(без файла)"
        self.setWindowTitle(f"Cloud Engine — {self.current_scene.name} — {path}")

    # ==================================================================
    # Ноды
    # ==================================================================
    def get_selected_node(self) -> Optional[Node]:
        return self.hierarchy.get_selected_node()

    def add_node(self, type_name: str, parent: Optional[Node] = None) -> None:
        """Добавляет ноду заданного типа."""
        if self.current_scene is None:
            self.console.log("Нет открытой сцены", "WARNING")
            return
        node_class = NODE_CLASSES.get(type_name)
        if node_class is None:
            self.console.log(f"Неизвестный тип ноды: {type_name}", "ERROR")
            return
        if parent is None:
            parent = self.get_selected_node() or self.current_scene.root
        try:
            node = node_class()
        except Exception:
            logger.exception("Не удалось создать ноду %s", type_name)
            return

        # Уникальное имя.
        node.name = self._unique_name(parent, type_name)

        self.undo_stack.execute(AddNodeCommand(parent, node))
        self.hierarchy.refresh()
        self.hierarchy.select_node(node)
        self.viewport.bind_node_assets(node)
        self.console.log(f"Добавлена нода: {node.name} ({type_name})", "INFO")

    def _unique_name(self, parent: Node, base: str) -> str:
        existing = {c.name for c in parent.get_children()}
        if base not in existing:
            return base
        i = 2
        while f"{base}{i}" in existing:
            i += 1
        return f"{base}{i}"

    def delete_node(self, node: Optional[Node]) -> None:
        if node is None or node.parent is None:
            return
        if self.current_scene is not None and node is self.current_scene.root:
            self.console.log("Нельзя удалить корень сцены", "WARNING")
            return
        parent = node.parent
        index = parent.get_index()
        self.undo_stack.execute(RemoveNodeCommand(parent, node, index))
        self.hierarchy.refresh()
        self.inspector.set_node(None)
        self.console.log(f"Удалена нода: {node.name}", "INFO")

    def delete_selected(self) -> None:
        self.delete_node(self.get_selected_node())

    def duplicate_node(self, node: Optional[Node]) -> None:
        if node is None or node.parent is None:
            return
        try:
            copy_node = node.duplicate(deep=True)
        except Exception:
            logger.exception("Не удалось дублировать ноду")
            return
        copy_node.name = self._unique_name(node.parent, node.name)
        self.undo_stack.execute(AddNodeCommand(node.parent, copy_node))
        self.hierarchy.refresh()
        self.hierarchy.select_node(copy_node)
        self.viewport.bind_node_assets(copy_node)

    def duplicate_selected(self) -> None:
        self.duplicate_node(self.get_selected_node())

    def rename_node(self, node: Optional[Node], name: str) -> None:
        if node is None:
            return
        old = node.name
        node.name = name
        self.undo_stack.execute(PropertyCommand(node, "name", old, name, "Переименовать"))
        self.hierarchy.refresh()

    def move_node(self, node: Node, new_parent: Node, index: int) -> None:
        """Перемещает ноду к новому родителю (drag&drop)."""
        if node is None or new_parent is None or node is new_parent:
            self.hierarchy.refresh()
            return
        if node.is_ancestor_of(new_parent):
            self.console.log("Нельзя переместить ноду внутрь себя", "WARNING")
            self.hierarchy.refresh()
            return
        old_parent = node.parent
        if old_parent is None:
            return
        old_index = old_parent.get_index()
        self.undo_stack.execute(MoveNodeCommand(node, old_parent, new_parent,
                                             old_index, index))
        self.hierarchy.refresh()

    def copy_selected(self) -> None:
        node = self.get_selected_node()
        if node is None:
            return
        self.clipboard_json = SceneSerializer.node_to_json_string(node)
        self.console.log(f"Скопирована нода: {node.name}", "INFO")

    def paste_node(self) -> None:
        if not self.clipboard_json or self.current_scene is None:
            return
        node = SceneSerializer.node_from_json_string(self.clipboard_json,
                                                     self.script_system)
        if node is None:
            return
        parent = self.get_selected_node() or self.current_scene.root
        node.name = self._unique_name(parent, node.name)
        self.undo_stack.execute(AddNodeCommand(parent, node))
        self.hierarchy.refresh()
        self.hierarchy.select_node(node)
        self.viewport.bind_node_assets(node)

    def focus_selected(self) -> None:
        self.viewport.focus_on_selected()

    def _on_tool_changed(self, tool: str) -> None:
        self.viewport.tool = tool
        self.status_label.setText(f"Инструмент: {tool}")

    def _on_grid_toggled(self, visible: bool) -> None:
        self.viewport.show_grid = bool(visible)
        self.settings_store.set("editor.grid_visible", bool(visible))
        self.settings_store.save()

    def _on_gizmos_toggled(self, visible: bool) -> None:
        self.viewport.show_gizmos = bool(visible)
        self.settings_store.set("editor.show_gizmos", bool(visible))
        self.settings_store.save()

    def _toggle_ui_overlay(self, checked: bool = False) -> None:
        """Показ игрового UI поверх сцены в редакторе (по умолчанию выключен)."""
        state = self.act_ui_overlay.isChecked() if hasattr(self, "act_ui_overlay") else checked
        self.viewport.show_ui_overlay = bool(state)
        self.settings_store.set("editor.show_ui_overlay", bool(state))
        self.settings_store.save()

    def attach_script(self) -> None:
        """Привязывает скрипт к выбранной ноде."""
        node = self.get_selected_node()
        if node is None:
            QMessageBox.information(self, "Скрипт", "Сначала выберите ноду.")
            return
        start = os.path.join(self.project_dir, "scripts") if self.project_dir else ""
        path, _ = QFileDialog.getOpenFileName(self, "Выберите скрипт", start,
                                              "Cloud Scripts / Python / C# (*.cloud *.py *.cs)")
        if not path:
            return
        self.attach_text_script(path)

    def detach_script(self) -> None:
        node = self.get_selected_node()
        if node is None:
            return
        old = node.script_path
        node.script_path = ""
        node._script_exported_properties = {}
        self.undo_stack.execute(PropertyCommand(node, "script_path", old, "",
                                             "Отвязать скрипт"))
        self.inspector.refresh()

    # ==================================================================
    # Компоненты
    # ==================================================================
    def add_component_to_node(self, node: Any, type_name: str) -> None:
        """Навешивает компонент на ноду (с поддержкой Undo/Redo)."""
        if node is None:
            return
        from engine.components.registry import create_component
        component = create_component(type_name)
        if component is None:
            self.console.log(f"Неизвестный компонент: {type_name}", "ERROR")
            return
        if node.get_component(type_name) and not getattr(component, 'allow_multiple', True):
            self.console.log('У объекта уже есть ' + type_name, 'WARNING')
            return
        if getattr(component, 'requires_game_object', False):
            from engine.nodes.game_object import GameObject
            from engine.nodes.sprite2d import Sprite2D
            if not isinstance(node, (GameObject, Sprite2D)):
                self.console.log('Выберите спрайт или GameObject для компонента', 'WARNING')
                return
        try:
            if type_name == 'Rigidbody2D' and not node.get_components('BoxCollider2D') and not node.get_components('CircleCollider2D'):
                from engine.components.object_components import BoxCollider2D, fit_sprite_collider
                collider = BoxCollider2D()
                fit_sprite_collider(node, collider, self.asset_manager)
                self.undo_stack.execute(AddComponentCommand(node, collider))
            elif type_name == 'BoxCollider2D':
                from engine.components.object_components import fit_sprite_collider
                fit_sprite_collider(node, component, self.asset_manager)
            if not self.undo_stack.execute(AddComponentCommand(node, component)):
                return
        except ValueError as exc:
            QMessageBox.information(self, 'Компонент', str(exc))
            return
        self.inspector.refresh()
        self.console.log(f"Компонент {type_name} добавлен к «{node.name}»", "INFO")

    def add_component_selected(self, type_name: str) -> None:
        """Навешивает компонент на выбранную ноду."""
        node = self.get_selected_node()
        if node is None:
            QMessageBox.information(
                self, "Компонент",
                "Сначала выберите объект: компонент навешивается на объект, "
                "а не на сцену.\n\n"
                "Также можно нажать правой кнопкой прямо по объекту во Viewport "
                "или по ноде в панели «Сцена».")
            return
        self.add_component_to_node(node, type_name)

    def pick_component(self) -> None:
        """Диалог выбора компонента для выбранного объекта."""
        node = self.get_selected_node()
        if node is None:
            QMessageBox.information(
                self, "Компонент",
                "Сначала выберите объект в панели «Сцена» или щёлкните по нему "
                "во Viewport.")
            return
        try:
            from editor.component_picker import ComponentPickerDialog
            chosen = ComponentPickerDialog.pick(self, getattr(node, "name", ""))
        except Exception:
            logger.exception("Не удалось открыть выбор компонента")
            return
        if chosen:
            self.add_component_to_node(node, chosen)

    # ==================================================================
    # Тайлы и выравнивание
    # ==================================================================
    def _mark_dirty(self) -> None:
        """Помечает текущую сцену как изменённую."""
        try:
            scene = self.current_scene
            if scene is not None:
                self.setWindowTitle(f"Cloud Engine — редактор • {scene.name} *")
        except Exception:
            pass

    def _on_tile_tool_changed(self, mode: str) -> None:
        """Включает инструмент рисования по тайлам."""
        self.viewport.set_tile_tool(mode)
        titles = {"off": "рисование выключено", "brush": "кисть",
                  "eraser": "ластик", "fill": "заливка", "rect": "прямоугольник"}
        self.status_label.setText(f"Плитки: {titles.get(mode, mode)}")

    def _on_tile_id_changed(self, tile_id: int) -> None:
        self.viewport.set_tile_id(tile_id, self.palette.collision_check.isChecked())

    def _on_tile_collision_changed(self, value: bool) -> None:
        self.viewport.set_tile_id(self.palette.tile_id, value)

    def _on_tile_grid_toggled(self, value: bool) -> None:
        self.viewport.show_tile_grid = bool(value)

    def _on_tile_edited(self, tilemap: Any, before: dict, after: dict) -> None:
        """Мазок кистью попадает в Undo/Redo одним действием."""
        if before == after:
            return
        self.undo_stack.execute(TileEditCommand(tilemap, before, after))
        self.palette.refresh()
        self._mark_dirty()

    def clear_tilemap(self) -> None:
        """Очищает выбранную тайловую карту (с возможностью отмены)."""
        tilemap = self.palette.tilemap
        if tilemap is None:
            QMessageBox.information(self, "Плитки",
                                    "Сначала выберите ноду TileMap.")
            return
        before = tilemap.snapshot()
        tilemap.clear()
        after = tilemap.snapshot()
        self.undo_stack.execute(TileEditCommand(tilemap, before, after,
                                                "Очистить тайловую карту"))
        self.palette.refresh()
        self._mark_dirty()
        self.console.log(f"Тайловая карта «{tilemap.name}» очищена", "INFO")

    def _on_nodes_property_edited(self, changes: list) -> None:
        """Групповое перетаскивание объектов."""
        if not changes:
            return
        if len(changes) == 1:
            node, prop, old, new = changes[0]
            self.undo_stack.execute(PropertyCommand(node, prop, old, new))
        else:
            self.undo_stack.execute(MultiPropertyCommand(changes, "position",
                                                         "Переместить объекты"))
        self.inspector.refresh()
        self._mark_dirty()

    def align_selected(self, mode: str) -> None:
        """Выравнивает выделенные объекты."""
        nodes = list(self.viewport.selected)
        if not nodes:
            node = self.get_selected_node()
            nodes = [node] if node is not None else []
        if not can_align(nodes) or len(nodes) < 2:
            QMessageBox.information(
                self, "Выравнивание",
                "Выделите два и более объекта: рамкой во Viewport или "
                "с зажатым Ctrl в дереве сцены.")
            return
        changes = align_nodes(nodes, mode)
        if not changes:
            self.console.log("Выравнивание: объекты уже стоят ровно", "INFO")
            return
        self.undo_stack.execute(MultiPropertyCommand(changes, "position",
                                                     ALIGN_MODES.get(mode, mode)))
        self.inspector.refresh()
        self._mark_dirty()
        title = ALIGN_MODES.get(mode, mode)
        self.console.log(f"Выравнивание «{title}»: объектов {len(changes)}", "INFO")
        self.status_label.setText(f"{title} — объектов: {len(changes)}")

    def _toggle_snap(self, checked: bool = False) -> None:
        """Прилипание объектов к сетке.

        У прилипания два переключателя (меню и панель инструментов), поэтому
        состояние берём из сигнала и синхронизируем оба.
        """
        state = bool(checked)
        self.viewport.snap_to_grid = state
        for control in (getattr(self, "act_snap", None),
                        getattr(getattr(self, "toolbar", None), "snap_action", None)):
            if control is None or control.isChecked() == state:
                continue
            control.blockSignals(True)
            control.setChecked(state)
            control.blockSignals(False)
        self.settings_store.set("editor.snap_to_grid", state)
        self.settings_store.save()
        self.status_label.setText(
            f"Прилипание к сетке: {'включено' if state else 'выключено'} "
            f"(шаг {self.viewport.grid_size:g})")

    def _set_grid_size(self, size: float) -> None:
        """Шаг сетки для прилипания."""
        self.viewport.grid_size = float(size)
        self.settings_store.set("editor.grid_size", float(size))
        self.settings_store.save()
        self.status_label.setText(f"Шаг сетки: {size:g}")

    def _on_animation_edited(self, node: Any, old_data: dict, new_data: dict) -> None:
        """Правки в редакторе анимаций попадают в Undo/Redo."""
        if old_data == new_data:
            return
        self.undo_stack.execute(NodeDataCommand(node, old_data, new_data,
                                                "Изменить анимации"))
        self.inspector.refresh()
        count = len(getattr(node, "animations", {}) or {})
        self.console.log(f"Анимации «{node.name}»: {count} шт.", "INFO")
        self._mark_dirty()

    def _on_particles_edited(self,node,before,after):
        from editor.undo_stack import ParticleSettingsCommand
        if before != after:
            self.undo_stack.execute(ParticleSettingsCommand(node,before,after))
            self.inspector.refresh(); self._mark_dirty()

    def _focus_problem_node(self,name):
        if self.current_scene:
            node=self.current_scene.find_node(name)
            if node: self.hierarchy.select_node(node)

    def _toggle_debug_overlay(self, checked: bool = False) -> None:
        """FPS и счётчики поверх игры."""
        state = self.act_debug_overlay.isChecked() if hasattr(self, "act_debug_overlay") \
            else checked
        self.settings["debug_overlay"] = bool(state)
        self.settings_store.set("editor.debug_overlay", bool(state))
        self.settings_store.save()
        if self.viewport.game_loop is not None:
            self.viewport.game_loop.show_debug_overlay = bool(state)

    def report_profiler(self) -> None:
        """Печатает отчёт профилировщика в консоль редактора."""
        try:
            from engine.core.profiler import profiler
            self.console.log(profiler.format_report(), "INFO")
        except Exception:
            logger.exception("Отчёт профилировщика не удался")
            self.console.log("Профилировщик недоступен", "ERROR")

    def remove_component_from_node(self, node: Any, component: Any) -> None:
        """Снимает компонент с ноды."""
        if node is None or component is None or getattr(component, "required", False):
            return
        self.undo_stack.execute(RemoveComponentCommand(node, component))
        self.inspector.refresh()

    def _add_tile_layer(self):
        from engine.nodes.tilemap import TileMap
        from engine.math.vector2 import Vector2
        import copy
        source = self.palette.tilemap
        if source is None or self.current_scene is None:
            return
        layer = TileMap(self._unique_name(source.parent or self.current_scene.root, 'TileLayer'))
        for name in ('tile_texture','tile_columns','tile_rows','tile_sources','tile_collisions'):
            setattr(layer,name,copy.deepcopy(getattr(source,name)))
        layer.cell_size = Vector2(source.cell_size)
        layer.position = Vector2(source.position)
        layer.scale = Vector2(source.scale)
        layer.rotation = source.rotation
        layer.z_index = source.z_index + 1
        layer.set_asset_manager(self.asset_manager)
        self.undo_stack.execute(AddNodeCommand(source.parent or self.current_scene.root, layer))
        self.hierarchy.refresh()
        self.hierarchy.select_node(layer)

    def _on_tile_cell_size(self, value):
        from engine.math.vector2 import Vector2
        node = self.palette.tilemap
        if node is not None:
            self.undo_stack.execute(PropertyCommand(node, 'cell_size', Vector2(node.cell_size), Vector2(value,value)))
            self.viewport.set_tilemap(node)
            self.inspector.refresh()

    def clear_components(self) -> None:
        """Удаляет все компоненты выбранной ноды."""
        node = self.get_selected_node()
        if node is None:
            return
        for component in list(getattr(node, "components", [])):
            if getattr(component, "required", False):
                continue
            self.undo_stack.execute(RemoveComponentCommand(node, component))
        self.inspector.refresh()
        self.console.log(f"Компоненты ноды «{node.name}» удалены", "INFO")

    def _on_component_property_changed(self, node: Any, component: Any, prop: str,
                                       old: Any, new: Any) -> None:
        """Изменение свойства компонента (в Undo/Redo)."""
        if self._inspector_lock:
            return
        self.undo_stack.execute(
            ComponentPropertyCommand(component, prop, old, new))

    def _on_component_enabled_changed(self, node: Any, component: Any,
                                      enabled: bool) -> None:
        """Включение/выключение компонента (в Undo/Redo)."""
        self.undo_stack.execute(
            ComponentPropertyCommand(component, "enabled", not enabled, enabled,
                                     "Переключить компонент"))

    # ==================================================================
    # Настройки проекта и сборка EXE
    # ==================================================================
    def open_project_settings(self) -> None:
        """Диалог настроек проекта (вместо ручного редактирования JSON)."""
        from editor.project_settings_dialog import ProjectSettingsDialog
        dialog = ProjectSettingsDialog(self.settings, self.project_dir, self)
        if dialog.exec():
            self.settings = dialog.get_settings()
            self.console.log("Настройки проекта сохранены", "INFO")
            if self.current_scene is not None:
                self.viewport.set_scene(self.current_scene)
                if self.asset_manager is not None:
                    self.viewport.set_asset_manager(self.asset_manager)

    def build_exe(self) -> None:
        """Сборка CloudEngine.exe через PyInstaller."""
        from editor.build_dialog import BuildDialog
        if not self.project_dir:
            QMessageBox.information(self, 'Экспорт игры', 'Сначала откройте проект.')
            return
        if self.script_editor.is_modified() and not self.script_editor.save():
            return
        if self.current_scene and self.current_scene.path:
            SceneSerializer.save_scene(self.current_scene, self.current_scene.path)
        BuildDialog(self, project_dir=self.project_dir).exec()

    def open_plugins(self):
        from editor.plugin_dialog import PluginDialog
        PluginDialog(self, self.plugin_host).exec()

    def open_templates(self):
        from editor.template_dialog import TemplateDialog
        dialog = TemplateDialog(self, self.project_dir)
        dialog.exec()
        if dialog.installed_scene:
            with open(os.path.join(self.project_dir, 'project.json'), encoding='utf-8') as source:
                self.settings.update(json.load(source))
            self.script_system.reload()
            self.assets.refresh()
            self.open_scene(str(dialog.installed_scene))

    def edit_sprite_animations(self):
        from editor.sprite_frames_editor import SpriteFramesEditor
        from engine.nodes.animated_sprite import AnimatedSprite2D
        node = getattr(self.inspector, 'node', None)
        if not isinstance(node, AnimatedSprite2D):
            QMessageBox.information(self, 'Анимации', 'Выберите AnimatedSprite2D в иерархии.')
            return
        if SpriteFramesEditor(node, self.project_dir, self).exec():
            self._mark_dirty()

    def edit_frame_hitboxes(self):
        from engine.nodes.animated_sprite import AnimatedSprite2D
        from editor.hitbox_editor import HitboxEditor
        import copy
        node=getattr(self.inspector,'node',None)
        if not isinstance(node,AnimatedSprite2D) or node.animation not in node.animations:
            QMessageBox.information(self,'Хитбоксы','Выберите AnimatedSprite2D с именованной анимацией.');return
        dialog=HitboxEditor(node.animations[node.animation],self.project_dir,self)
        if dialog.exec():
            node.animations[node.animation]=copy.deepcopy(dialog.result_clip)
            self._mark_dirty()

    # ==================================================================
    # Выделение / инспектор
    # ==================================================================
    def _on_hierarchy_selected(self, node: Any) -> None:
        self._inspector_lock = True
        self.inspector.set_node(node)
        self._inspector_lock = False

        self._sync_tilemap(node)

    def _sync_tilemap(self, node: Any) -> None:
        """Подключает палитру тайлов к выбранной ноде."""
        try:
            self.palette.set_tilemap(node)
            self.viewport.set_tilemap(node)
        except Exception:
            logger.exception("Не удалось обновить палитру тайлов")

    def _on_viewport_node_selected(self, node: Any) -> None:
        if node is None:
            return
        self.hierarchy.select_node(node)

    def _on_viewport_selection(self, nodes: list) -> None:
        if nodes:
            self._inspector_lock = True
            self.inspector.set_node(nodes[0])
            self._inspector_lock = False

    def _on_mouse_world(self, pos: Any) -> None:
        self.status_label.setText(f"X: {pos.x:.0f}  Y: {pos.y:.0f}")

    def _on_node_property_edited(self, node: Any, prop: str, old_value: Any,
                                 new_value: Any) -> None:
        """Перетаскивание ноды во Viewport попадает в Undo/Redo."""
        try:
            self.undo_stack.execute(PropertyCommand(node, prop, old_value, new_value,
                                                    f"Изменить {prop}"))
        except Exception:
            pass
        self.inspector.refresh()

    def _on_property_changed(self, node: Any, prop: str, old: Any, new: Any) -> None:
        """Регистрирует изменение свойства в Undo/Redo."""
        if self._inspector_lock:
            return
        try:
            self.undo_stack.execute(PropertyCommand(node, prop, old, new))
        except Exception:
            pass
        if prop == "name":
            self.hierarchy.refresh()
        elif prop == "texture_path" and hasattr(node, "set_texture_path"):
            # Перезагружаем текстуру сразу: сначала привязываем ресурсы,
            # затем перечитываем путь (иначе останется старая текстура).
            try:
                self.viewport.bind_node_assets(node)
                node.set_texture_path(new)
            except Exception:
                pass

    # ==================================================================
    # Undo / Redo
    # ==================================================================
    def undo(self) -> None:
        self.undo_stack.undo()
        self.hierarchy.refresh()
        self.inspector.refresh()
        self.viewport.set_scene(self.current_scene)
        self.palette.refresh()

    def redo(self) -> None:
        self.undo_stack.redo()
        self.palette.refresh()
        self.hierarchy.refresh()
        self.inspector.refresh()
        self.viewport.set_scene(self.current_scene)

    def _update_undo_actions(self) -> None:
        can_undo = self.undo_stack.can_undo()
        can_redo = self.undo_stack.can_redo()
        if hasattr(self, "toolbar"):
            self.toolbar.set_undo_enabled(can_undo)
            self.toolbar.set_redo_enabled(can_redo)
        if hasattr(self, "act_undo"):
            self.act_undo.setEnabled(can_undo)
        if hasattr(self, "act_redo"):
            self.act_redo.setEnabled(can_redo)

    # ==================================================================
    # Запуск игры
    # ==================================================================
    def play_game(self) -> None:
        self.recovery.capture()
        if self.current_scene is None:
            QMessageBox.information(self, "Играть", "Нет открытой сцены.")
            return
        if self.viewport.is_playing:
            self.viewport.resume_game()
            self.toolbar.set_playing(True, False)
            return

        from editor.scene_validation import validate_scene, show_scene_issues
        if self.script_editor.is_modified() and not self.script_editor.save():
            return
        issues = validate_scene(self.current_scene, self.project_dir)
        if issues:
            show_scene_issues(self, issues)
            return

        settings = self.settings or {}
        from engine.systems.script_debugger import DebugStop
        debugger=self.debugger_panel.debugger
        debugger.project_dir=self.project_dir; debugger.reset()
        try:
            with debugger.tracing():
                self.viewport.start_game(self.current_scene, settings, self.project_dir)
        except DebugStop:
            self.viewport.stop_game()
            return
        except Exception as error:
            self.viewport.stop_game()
            logger.exception('Ошибка запуска Play')
            QMessageBox.warning(self, 'Запуск сцены', str(error))
            return
        self.toolbar.set_playing(True, False)
        self.console.log("Игра запущена (Play)", "INFO")

    def pause_game(self) -> None:
        if not self.viewport.is_playing:
            return
        if self.viewport.is_paused:
            self.viewport.resume_game()
            self.toolbar.set_playing(True, False)
            self.console.log("Игра возобновлена", "INFO")
        else:
            self.viewport.pause_game()
            self.toolbar.set_playing(True, True)
            self.console.log("Игра на паузе", "INFO")

    def stop_game(self) -> None:
        if self.debugger_panel.debugger.paused:
            self.debugger_panel.abort()
            return
        if not self.viewport.is_playing:
            return
        self.viewport.stop_game()
        self.toolbar.set_playing(False, False)
        self.console.log("Игра остановлена (Stop)", "INFO")

    # ==================================================================
    # Скрипты и ассеты
    # ==================================================================
    def attach_text_script(self, path):
        node = self.get_selected_node()
        if node is None or not self.project_dir:
            QMessageBox.information(self, "Скрипт", "Сначала выберите объект сцены.")
            return
        relative = os.path.relpath(path, self.project_dir).replace("\\", "/")
        from engine.components.behaviour import Behaviour, ScriptBehaviour
        if self.script_system:
            self.script_system.reload()
            cls = self.script_system.get_class_for(relative)
            if cls and issubclass(cls, Behaviour):
                component = ScriptBehaviour()
                component.script_path = relative
                self.undo_stack.execute(AddComponentCommand(node, component))
                self.inspector.refresh()
                self.open_script(path)
                return
        self.undo_stack.execute(PropertyCommand(node, "script_path", node.script_path, relative))
        self._bind_script_exports(node)
        self.inspector.refresh()
        self.console.log(f"Скрипт {relative} назначен объекту {node.name}", "INFO")

    def _bind_script_exports(self, node):
        import copy
        cls = self.script_system.get_class_for(node.script_path) if self.script_system and node.script_path else None
        node._script_exported_properties = cls.get_exported_properties() if cls else {}
        for name, spec in node._script_exported_properties.items():
            if not hasattr(node, name):
                node.set(name, copy.deepcopy(spec.get('default', getattr(cls, name, None))))

    def open_sprite_studio(self, path):
        from editor.sprite_slicer import SpriteSlicer
        try:
            SpriteSlicer(path, self).exec()
        except ValueError as error:
            QMessageBox.warning(self, 'Нарезка спрайтов', str(error))

    def _resource_moved(self, old, new):
        from pathlib import Path
        from editor.resource_refactor import remap_scene, remap
        root = Path(self.project_dir).resolve()
        scenes = self.scene_tabs.scenes()
        if self.current_scene is not None and self.current_scene not in scenes:
            scenes.append(self.current_scene)
        for scene in scenes:
            remap_scene(scene, old, new)
            if scene and scene.path:
                path = Path(scene.path).resolve()
                if path.is_relative_to(root):
                    scene.path = str(root / remap(path.relative_to(root).as_posix(), old, new))
        if self.script_editor.path:
            path = Path(self.script_editor.path).resolve();root = Path(self.project_dir).resolve()
            if path.is_relative_to(root):
                self.script_editor.path = str(root / remap(path.relative_to(root).as_posix(), old, new))
                self.script_editor.path_label.setText(self.script_editor.path)
        self.settings = remap(self.settings, old, new)
        self.undo_stack.clear()
        self._mark_dirty()
        self.viewport.set_asset_manager(self.asset_manager)
        if self.current_scene:
            self.viewport.bind_node_assets(self.current_scene.root)
        self.inspector.refresh()
        self.console.log('Ссылки ресурсов обновлены. История отмены очищена; резервные копии в .cloud-backups.', 'INFO')

    def open_script_location(self, path, line=1):
        from pathlib import Path
        target = Path(path).resolve()
        root = Path(self.project_dir).resolve()
        if not target.is_relative_to(root) or not target.is_file() or target.suffix not in ('.cloud', '.py', '.cs'):
            return
        self.open_script(str(target))
        if Path(self.script_editor.path).resolve() == target:
            self.script_editor.goto_line(line)
            for dock in self.findChildren(QDockWidget):
                if dock.widget() is self.script_editor:
                    dock.show();dock.raise_()

    def open_script(self, path: str) -> None:
        if path.endswith('.gamedata'):
            from editor.production_tools import open_data
            open_data(self,path); return
        if path.endswith('.material'):
            self.open_material(path); return
        if path.endswith('.prefab'):
            self.instantiate_prefab(path); return
        self.script_editor.load_file(path)
        self.debugger_panel.refresh_marks()
        self.console.log(f"Открыт скрипт: {path}", "INFO")

    def reload_scripts(self) -> None:
        if self.script_system is not None:
            count = self.script_system.reload()
            if self.current_scene:
                for node in self.current_scene.get_nodes():
                    self._bind_script_exports(node)
                self.inspector.refresh()
            errors = len(self.script_system.errors)
            self.console.log(f"Перезагружено скриптов: {count}. Ошибок: {errors}", "ERROR" if errors else "INFO")

    def _create_scene_file(self, path: str) -> None:
        try:
            from engine.nodes.game_object import GameObject
            name = os.path.splitext(os.path.basename(path))[0]
            scene = Scene(name, GameObject(name))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            SceneSerializer.save_scene(scene, path)
            self.assets.refresh()
            self.open_scene(path)
        except Exception:
            logger.exception("Не удалось создать сцену %s", path)

    def _create_script_file(self, path: str) -> None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            class_name = "".join(part.capitalize() for part in
                                 os.path.splitext(os.path.basename(path))[0].split("_"))
            template = (
                "from engine.components.behaviour import Behaviour\n\n\n"
                f"class {class_name}(Behaviour):\n"
                "    \"\"\"Пользовательский скрипт Cloud Engine.\"\"\"\n\n"
                "    def _ready(self):\n"
                "        print(\"Готово:\", self.game_object.name)\n\n"
                "    def _process(self, delta):\n"
                "        pass\n"
            )
            if path.endswith(".cloud"):
                template = f"script {class_name} extends Behaviour:\n    on ready():\n        pass\n\n    on process(delta):\n        pass\n"
            if path.endswith(".cs"):
                template = ("using CloudEngine;\n\n" + f"public class {class_name} : CloudBehaviour {{\n" +
                            "    public override void Process(double delta) {\n        // Пользовательский код\n    }\n}\n")
            if path.endswith(".shader"):
                template = "# rgb: RGB [0..1], uv: coordinates, time: seconds\ndef fragment(rgb, uv, time):\n    return rgb\n"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(template)
            self.assets.refresh()
            self.open_script(path)
            self.reload_scripts()
        except Exception:
            logger.exception("Не удалось создать скрипт %s", path)

    def _on_assets_imported(self, paths: list) -> None:
        """Файлы, скопированные в проект через файловый менеджер."""
        self.console.log(f"Импортировано файлов в проект: {len(paths)}", "INFO")

    # ==================================================================
    # Визуальные скрипты
    # ==================================================================
    def _on_asset_dropped(self, path: str) -> None:
        """Создаёт Sprite2D при перетаскивании изображения в Viewport."""
        ext = os.path.splitext(path)[1].lower()
        if ext == '.prefab':
            self.instantiate_prefab(path); return
        if ext == '.material':
            node=self.get_selected_node()
            renderer=node.get_component('SpriteRenderer') if node else None
            if renderer:
                relative=os.path.relpath(path,self.project_dir).replace('\\','/')
                self.undo_stack.execute(ComponentPropertyCommand(renderer,'material_path',renderer.material_path,relative))
                self.inspector.refresh()
            return
        if ext not in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            return
        if self.current_scene is None:
            return
        rel = path
        if self.project_dir:
            try:
                rel = os.path.relpath(path, self.project_dir).replace("\\", "/")
            except Exception:
                rel = path
        parent = self.get_selected_node()
        if parent is None or not hasattr(parent, "add_child"):
            parent = self.current_scene.root
        from engine.nodes.game_object import GameObject
        node = GameObject(self._unique_name(parent, 'Sprite'))
        node.add_component('SpriteRenderer').texture_path = rel
        if self.asset_manager is not None:
            node.set_asset_manager(self.asset_manager)
        self.undo_stack.execute(AddNodeCommand(parent, node))
        self.hierarchy.refresh()
        self.hierarchy.select_node(node)
        self.console.log(f"Создан объект со SpriteRenderer: {rel}", "INFO")

    # ==================================================================
    # Закрытие
    # ==================================================================
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.debugger_panel.debugger.paused:
            self.debugger_panel.abort()
            event.ignore()
            QTimer.singleShot(0,self.close)
            return
        self.recovery.capture()
        self.recovery.timer.stop()
        self._closing = True
        if hasattr(self, 'plugin_host'):
            self.plugin_host.close()
        if self.project_dir:
            from editor.project_hub import remember_project
            remember_project(self.project_dir)
        self.assets.stop_audio()
        if self.script_editor.is_modified():
            self.script_editor.save()
        # Останавливаем таймер отрисовки, иначе он может сработать
        # по уже уничтоженному виджету и уронить приложение.
        try:
            self.viewport.stop_timer()
        except Exception:
            pass
        try:
            self.console.shutdown()
        except Exception:
            pass
        try:
            self.profiler.shutdown()
        except Exception:
            pass
        if self.viewport.is_playing:
            self.viewport.stop_game()
        if self.current_scene is not None and self.current_scene.path:
            try:
                SceneSerializer.save_scene(self.current_scene, self.current_scene.path)
            except Exception:
                pass
        self.recovery.clean_saved()
        # Сохраняем раскладку интерфейса, чтобы восстановить её при следующем запуске.
        try:
            self.save_layout()
        except Exception:
            logger.exception("Не удалось сохранить раскладку")
        event.accept()
