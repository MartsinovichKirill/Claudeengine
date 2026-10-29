"""Палитра тайлов — инструменты рисования для TileMap.

Панель показывает тайлы набора и переключает инструменты: кисть, ластик,
заливка, прямоугольник. Выбранный тайл и режим «коллизия» используются
Viewport при клике по сцене.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize, QSettings
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QImage
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
                             QDoubleSpinBox, QPushButton, QToolButton, QGroupBox,
                             QFormLayout, QScrollArea, QButtonGroup, QFileDialog, QMessageBox, QLineEdit, QComboBox)

from editor.icons import get_icon

logger = logging.getLogger("cloudengine.tile_palette")

#: Инструменты рисования: код -> (подпись, иконка).
TILE_TOOLS = [
    ("off", "Выключено", "cursor"),
    ("brush", "Кисть", "brush"),
    ("eraser", "Ластик", "eraser"),
    ("fill", "Заливка", "fill"),
    ("rect", "Прямоугольник", "area"),
]

TILE_SIZE = 42


def surface_to_pixmap(surface: Any) -> Optional[QPixmap]:
    """pygame.Surface -> QPixmap (для показа тайла в панели)."""
    if surface is None:
        return None
    try:
        import pygame
        raw = pygame.image.tostring(surface, "RGBA")
        image = QImage(raw, surface.get_width(), surface.get_height(),
                       QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(image.copy())
    except Exception:
        logger.exception("Не удалось показать тайл")
        return None


class TileGrid(QWidget):
    """Сетка тайлов набора: клик выбирает тайл."""

    tile_picked = pyqtSignal(int)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.ids: List[int] = []
        self.pixmaps: Dict[int, QPixmap] = {}
        self.selected: int = 0
        self.solid_ids = set()
        self.favorite_ids = set()
        self.setMinimumHeight(TILE_SIZE + 8)
        self.setMouseTracking(True)

    def set_tiles(self, ids: List[int], pixmaps: Dict[int, QPixmap]) -> None:
        self.ids = list(ids)
        self.pixmaps = dict(pixmaps)
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()
        self.update()

    def set_selected(self, tile_id: int) -> None:
        self.selected = tile_id
        self.update()

    def _columns(self) -> int:
        return max(1, self.width() // TILE_SIZE)

    def sizeHint(self) -> QSize:
        columns = max(1, self._columns())
        rows = (len(self.ids) + columns - 1) // columns if self.ids else 1
        return QSize(columns * TILE_SIZE, rows * TILE_SIZE + 6)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(self.sizeHint().height())

    def _index_at(self, position: Any) -> int:
        columns = self._columns()
        column = int(position.x()) // TILE_SIZE
        row = int(position.y()) // TILE_SIZE
        if column < 0 or column >= columns or row < 0:
            return -1
        index = row * columns + column
        return index if 0 <= index < len(self.ids) else -1

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121216"))
        if not self.ids:
            painter.setPen(QColor("#66666f"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Набор пуст — задайте tile_texture у TileMap")
            return

        columns = self._columns()
        for index, tile_id in enumerate(self.ids):
            column = index % columns
            row = index // columns
            cell = QRect(column * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            painter.fillRect(cell.adjusted(1, 1, -1, -1), QColor("#1a1a21"))
            pixmap = self.pixmaps.get(tile_id)
            if pixmap is not None:
                target = cell.adjusted(3, 3, -3, -3)
                painter.drawPixmap(target,
                                   pixmap.scaled(target.size(),
                                                 Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.FastTransformation))
            if tile_id in self.solid_ids:
                painter.setPen(QPen(QColor('#73d4a1'), 2))
                painter.drawRect(cell.adjusted(4, 4, -4, -4))
            if tile_id in self.favorite_ids:
                painter.setPen(QColor('#ffd36d'))
                painter.drawText(cell.adjusted(4, 0, 0, 0), Qt.AlignmentFlag.AlignLeft, '★')
            if tile_id == self.selected:
                painter.setPen(QPen(QColor("#478cbf"), 2))
                painter.drawRect(cell.adjusted(1, 1, -1, -1))
            else:
                painter.setPen(QPen(QColor("#24242c"), 1))
                painter.drawRect(cell.adjusted(1, 1, -1, -1))
            painter.setPen(QColor("#66666f"))
            painter.drawText(cell.adjusted(3, 0, -3, -2),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                             str(tile_id))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        index = self._index_at(event.position())
        if index >= 0:
            self.selected = self.ids[index]
            self.update()
            self.tile_picked.emit(self.selected)


class TilePalette(QWidget):
    """Панель инструментов рисования по TileMap."""

    tool_changed = pyqtSignal(str)
    tile_changed = pyqtSignal(int)
    collision_changed = pyqtSignal(bool)
    cell_size_changed = pyqtSignal(float)
    tileset_edited = pyqtSignal(object, dict, dict)
    layer_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    grid_toggled = pyqtSignal(bool)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        from pathlib import Path
        import os
        settings_dir = Path(os.environ.get('CLOUDENGINE_CONFIG_DIR', os.environ.get('LOCALAPPDATA', str(Path.home())))) / 'CloudEngine'
        try:
            settings_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning('Папка настроек палитры недоступна: %s', settings_dir)
        self._settings = QSettings(str(settings_dir / 'tile-palette.ini'), QSettings.Format.IniFormat)
        self.tilemap: Any = None
        self.tool: str = "off"
        self.tile_id: int = 0
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.title = QLabel("TileMap не выбран")
        self.title.setStyleSheet("font-weight:600;")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        # --- Инструменты ---
        tools_box = QGroupBox("Инструмент")
        tools_layout = QHBoxLayout(tools_box)
        tools_layout.setSpacing(4)
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        for code, title, icon in TILE_TOOLS:
            button = QToolButton()
            button.setText(title)
            button.setIcon(get_icon(icon))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setToolTip(title)
            if code == "off":
                button.setChecked(True)
            button.clicked.connect(lambda checked=False, c=code: self._set_tool(c))
            self._tool_group.addButton(button)
            tools_layout.addWidget(button)
        layout.addWidget(tools_box)

        # --- Параметры ---
        params = QGroupBox("Параметры кисти")
        form = QFormLayout(params)
        self.collision_check = QCheckBox("Коллизия (твёрдый тайл)")
        self.collision_check.setToolTip(
            "Закрашенные тайлы станут препятствием для физики")
        self.collision_check.toggled.connect(self._set_tile_collision)
        form.addRow("", self.collision_check)

        self.cell_spin = QDoubleSpinBox()
        self.cell_spin.setRange(4.0, 512.0)
        self.cell_spin.setSingleStep(4.0)
        self.cell_spin.setDecimals(1)
        self.cell_spin.setValue(32.0)
        self.cell_spin.setToolTip("Размер ячейки тайловой карты")
        self.cell_spin.valueChanged.connect(self._on_cell_size)
        form.addRow("Размер ячейки", self.cell_spin)

        self.grid_check = QCheckBox("Показывать сетку тайлов")
        self.grid_check.setChecked(True)
        self.grid_check.toggled.connect(self.grid_toggled.emit)
        form.addRow("", self.grid_check)
        layout.addWidget(params)

        # --- Набор тайлов ---
        tiles_box = QGroupBox("Тайлы набора")
        tiles_layout = QVBoxLayout(tiles_box)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск: имя файла или ID тайла")
        self.search.textChanged.connect(self._filter_tiles)
        tiles_layout.addWidget(self.search)
        self.category = QComboBox()
        self.category.addItems(["Все тайлы", "С коллизией", "Без коллизии", "Избранное"])
        self.category.currentIndexChanged.connect(self._filter_tiles)
        tiles_layout.addWidget(self.category)
        self.favorite = QCheckBox("★ Избранный тайл")
        self.favorite.toggled.connect(self._favorite_changed)
        tiles_layout.addWidget(self.favorite)
        tiles_layout.addWidget(QLabel("■ Зелёная рамка — коллизия · ★ — избранное"))
        self.grid = TileGrid()
        self.grid.tile_picked.connect(self._on_tile_picked)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid)
        scroll.setMinimumHeight(140)
        tiles_layout.addWidget(scroll)

        buttons = QHBoxLayout()
        refresh = QPushButton("Обновить")
        refresh.setIcon(get_icon("undo"))
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)
        add = QPushButton("Добавить спрайты…")
        add.clicked.connect(self.import_sprites)
        buttons.addWidget(add)
        layer = QPushButton('Новый слой')
        layer.clicked.connect(self.layer_requested.emit)
        buttons.addWidget(layer)
        clear = QPushButton("Очистить карту")
        clear.setIcon(get_icon("delete"))
        clear.clicked.connect(self.clear_requested.emit)
        buttons.addWidget(clear)
        tiles_layout.addLayout(buttons)
        layout.addWidget(tiles_box, 1)

        self.hint = QLabel("Выберите TileMap в дереве сцены, задайте tile_texture "
                           "и рисуйте прямо во Viewport.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#8c8c99;font-size:11px;")
        layout.addWidget(self.hint)

    # ------------------------------------------------------------------
    def _set_tool(self, code: str) -> None:
        self.tool = code
        self.tool_changed.emit(code)

    def _on_tile_picked(self, tile_id: int) -> None:
        self.tile_id = tile_id
        self.favorite.blockSignals(True)
        self.favorite.setChecked(tile_id in self._favorites())
        self.favorite.blockSignals(False)
        self.tile_changed.emit(tile_id)
        value = bool(getattr(self.tilemap, 'tile_collisions', {}).get(tile_id, False))
        self.collision_check.blockSignals(True)
        self.collision_check.setChecked(value)
        self.collision_check.blockSignals(False)
        self.collision_changed.emit(value)

    def _set_tile_collision(self, value):
        if self.tilemap is not None:
            import copy
            before = copy.deepcopy(self.tilemap._serialize_data())
            self.tilemap.tile_collisions[self.tile_id] = bool(value)
            for cell in self.tilemap.cells.values():
                if cell.get('id') == self.tile_id:
                    cell['collision'] = bool(value)
            self.tileset_edited.emit(self.tilemap, before, copy.deepcopy(self.tilemap._serialize_data()))
        self.grid.solid_ids = {key for key, solid in self.tilemap.tile_collisions.items() if solid} if self.tilemap else set()
        self.grid.update()
        self._filter_tiles()
        self.collision_changed.emit(value)

    def import_sprites(self):
        if self.tilemap is None:
            return
        from pathlib import Path
        import copy
        import shutil
        manager = self.tilemap._asset_manager
        if manager is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Добавить спрайты', manager.project_dir, 'Images (*.png *.jpg *.webp *.bmp)')
        if not paths:
            return
        root = Path(manager.project_dir).resolve()
        before = copy.deepcopy(self.tilemap._serialize_data())
        try:
            # Preserve existing sheet tiles when introducing individual sprites.
            if not self.tilemap.tile_sources and self.tilemap.tile_texture:
                QMessageBox.information(self, 'Набор тайлов', 'Для отдельных спрайтов используйте новую TileMap без tile_texture.')
                return
            for source in paths:
                path = Path(source).resolve()
                if not path.is_relative_to(root):
                    target = root / 'assets' / 'tiles' / path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        raise ValueError('Файл уже существует: ' + target.name)
                    shutil.copy2(path, target)
                    path = target
                relative = path.relative_to(root).as_posix()
                if relative in self.tilemap.tile_sources.values():
                    continue
                tile_id = max(self.tilemap.tile_sources, default=-1) + 1
                self.tilemap.tile_sources[tile_id] = relative
                self.tilemap.tile_collisions[tile_id] = False
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Импорт', str(error))
        self.tilemap._rebuild_tiles()
        self.tileset_edited.emit(self.tilemap, before, copy.deepcopy(self.tilemap._serialize_data()))
        self.refresh()

    def _on_cell_size(self, value: float) -> None:
        self.cell_size_changed.emit(value)

    # ------------------------------------------------------------------
    def set_tilemap(self, node: Any) -> None:
        """Показывает тайлы выбранной карты."""
        self.tilemap = node
        if node is None or "TileMap" not in type(node).__name__:
            self.title.setText("TileMap не выбран")
            self.grid.set_tiles([], {})
            self.hint.setText("Выберите TileMap в дереве сцены или добавьте ноду "
                              "TileMap (меню «Нода» → «Node2D»).")
            return

        self.title.setText(f"Карта: {node.name}   •   ячеек: "
                           f"{len(getattr(node, 'cells', {}))}")
        try:
            from engine.math.vector2 import Vector2
            self.cell_spin.blockSignals(True)
            self.cell_spin.setValue(float(getattr(node, "cell_size", Vector2(32, 32)).x))
            self.cell_spin.blockSignals(False)
        except Exception:
            pass

        ids = node.tile_ids() if hasattr(node, "tile_ids") else []
        if not ids:
            self.grid.set_tiles([], {})
            self.hint.setText("Набор пуст: у TileMap задайте «tile_texture» "
                              "(спрайтшит), «tile_columns» и «tile_rows» в инспекторе.")
            return

        pixmaps: Dict[int, QPixmap] = {}
        for tile_id, surface in (node._tiles or {}).items():
            pixmap = surface_to_pixmap(surface)
            if pixmap is not None:
                pixmaps[tile_id] = pixmap
        self.grid.solid_ids = {key for key, value in node.tile_collisions.items() if value}
        self._all_pixmaps = pixmaps
        self._filter_tiles()
        if self.tile_id not in ids:
            self.tile_id = ids[0]
        self.grid.set_selected(self.tile_id)
        self._on_tile_picked(self.tile_id)
        self.hint.setText(f"Тайлов в наборе: {len(ids)}. Выбран тайл {self.tile_id}. "
                          f"Рисуйте левой кнопкой во Viewport.")

    def _settings_key(self):
        import hashlib
        manager = getattr(self.tilemap, '_asset_manager', None)
        scope = str(getattr(manager, 'project_dir', '')) + '/' + str(getattr(self.tilemap, 'tile_texture', '')) + '/' + str(getattr(self.tilemap, 'name', ''))
        return 'tile_favorites/' + hashlib.sha256(scope.encode()).hexdigest()

    def _favorites(self):
        values = self._settings.value(self._settings_key(), [])
        if isinstance(values, str):
            values = [values]
        return {int(v) for v in (values or []) if str(v).isdigit()}

    def _favorite_changed(self, checked):
        if self.tilemap is None:
            return
        values = self._favorites()
        values.add(self.tile_id) if checked else values.discard(self.tile_id)
        self._settings.setValue(self._settings_key(), [str(v) for v in sorted(values)])
        self._settings.sync()
        self._filter_tiles()

    def _filter_tiles(self, *_):
        if self.tilemap is None:
            self.grid.set_tiles([], {})
            return
        query = self.search.text().strip().casefold()
        category = self.category.currentIndex()
        favorites = self._favorites()
        collisions = getattr(self.tilemap, 'tile_collisions', {})
        sources = getattr(self.tilemap, 'tile_sources', {})
        ids = [i for i in self.tilemap.tile_ids()
               if (not query or query in (str(i) + ' ' + str(sources.get(i, self.tilemap.tile_texture))).casefold())
               and (category != 1 or collisions.get(i, False))
               and (category != 2 or not collisions.get(i, False))
               and (category != 3 or i in favorites)]
        self.grid.favorite_ids = favorites
        self.grid.set_tiles(ids, getattr(self, '_all_pixmaps', {}))
        self.grid.set_selected(self.tile_id)

    def refresh(self) -> None:
        """Перечитывает тайлы и количество ячеек."""
        tilemap = self.tilemap
        self.set_tilemap(tilemap)


__all__ = ["TilePalette", "TileGrid", "TILE_TOOLS", "surface_to_pixmap"]
