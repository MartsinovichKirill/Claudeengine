"""Редактор анимаций AnimationPlayer.

Позволяет создавать анимации и расставлять ключевые кадры для свойств
объекта: позиция, поворот, масштаб, цвет, прозрачность и любые другие
экспортируемые свойства.

Значение вводится текстом в зависимости от типа свойства:
* число — ``120`` или ``1.5``;
* вектор — ``0, -90``;
* цвет — ``255, 200, 120, 255``;
* флаг — ``да`` / ``нет``.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, QElapsedTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)
from PyQt6.QtWidgets import QFileDialog, QTabWidget

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.animation_player import (Animation, AnimationPlayer,
                                           COMMON_PROPERTIES, EASINGS)
from engine.nodes.animation_player import read_property, write_property
from editor.icons import get_icon

EASING_TITLES = {
    "linear": "Линейно",
    "in": "Ускорение",
    "out": "Замедление",
    "in_out": "Плавно",
    "step": "Ступенькой",
    "bounce": "Отскок",
}


class AnimationTimeline(QWidget):
    """Clickable seconds ruler with property keys and separate event markers."""
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.animation = None
        self.time = 0.0
        self.setMinimumHeight(85)
        self.setToolTip('Щёлкните или перетащите для просмотра. События при просмотре не выполняются.')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#17212b'))
        if self.animation is None:
            painter.setPen(QColor('#a5b5c4')); painter.drawText(12, 40, 'Создайте анимацию')
            return
        width, length = max(1, self.width() - 24), self.animation.length
        painter.setPen(QColor('#8c9faf'))
        for index in range(11):
            x = 12 + width * index / 10
            painter.drawLine(int(x), 25, int(x), 66)
            painter.drawText(int(x) - 8, 17, f'{length * index / 10:.2g}')
        painter.setBrush(QColor('#6bb5ee')); painter.setPen(Qt.PenStyle.NoPen)
        for keys in self.animation.keys.values():
            for time, *_ in keys:
                x = 12 + width * min(1, time / length)
                painter.drawPolygon(QPolygonF([QPointF(x, 35), QPointF(x+5, 40), QPointF(x, 45), QPointF(x-5, 40)]))
        painter.setBrush(QColor('#f1b86b'))
        for marker in self.animation.events:
            x = 12 + width * marker['time'] / length
            painter.drawRect(int(x)-3, 52, 6, 12)
        painter.setPen(QPen(QColor('#ffffff'), 2))
        x = int(12 + width * min(1, self.time / length))
        painter.drawLine(x, 23, x, 74)

    def mousePressEvent(self, event):
        if self.animation and event.button() == Qt.MouseButton.LeftButton:
            self.seek_requested.emit(max(0, min(1, (event.position().x()-12) / max(1, self.width()-24))) * self.animation.length)

    def mouseMoveEvent(self, event):
        if self.animation and event.buttons() & Qt.MouseButton.LeftButton:
            self.seek_requested.emit(max(0, min(1, (event.position().x()-12) / max(1, self.width()-24))) * self.animation.length)


def format_value(value: Any) -> str:
    """Значение свойства в текстовый вид."""
    if isinstance(value, Vector2):
        return f"{value.x:g}, {value.y:g}"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, (list, tuple)):
        return ", ".join(f"{float(v):g}" for v in value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def parse_value(text: str, sample: Any) -> Any:
    """Текст в значение того же типа, что и образец."""
    text = (text or "").strip()
    if isinstance(text, str) and "," in text:
        parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    else:
        parts = text.split()

    try:
        if isinstance(sample, Vector2):
            numbers = [float(part) for part in parts[:2]] or [0.0, 0.0]
            while len(numbers) < 2:
                numbers.append(0.0)
            return Vector2(numbers[0], numbers[1])
        if isinstance(sample, bool):
            lowered = text.lower()
            return lowered in ("да", "true", "1", "yes", "вкл", "on")
        if isinstance(sample, int) and not isinstance(sample, bool):
            return int(float(text))
        if isinstance(sample, float):
            return float(text)
        if isinstance(sample, (list, tuple)):
            numbers = [int(round(float(part))) for part in parts]
            if len(numbers) == 4:
                return tuple(numbers)
            return tuple(numbers) or tuple(sample)
    except Exception:
        return None
    return text


class AnimationEditorDialog(QDialog):
    """Диалог редактирования анимаций узла AnimationPlayer."""

    def __init__(self, player: AnimationPlayer, parent: Any = None) -> None:
        super().__init__(parent)
        self.player = player
        self.setWindowTitle(f"Анимации — {player.name}")
        self.setMinimumSize(820, 560)
        #: Снимок данных до правок (для отмены действия).
        self.before_data: Dict[str, Any] = copy.deepcopy(player._serialize_data())
        self.before_autoplay = player.autoplay
        self.current: Optional[str] = None
        self._preview_saved = {}
        self._preview_target = None
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(16)
        self.preview_timer.timeout.connect(self._preview_tick)
        self.preview_clock = QElapsedTimer()
        self._build()
        self._reload_animations()
        self.finished.connect(self._finish_preview)

    # ==================================================================
    # Интерфейс
    # ==================================================================
    def _build(self) -> None:
        root = QVBoxLayout(self)

        hint = QLabel("Ключевые кадры анимируют свойства объекта во времени.")
        hint.setStyleSheet("color:#8c8c99;")
        root.addWidget(hint)
        self.timeline = AnimationTimeline()
        self.timeline.seek_requested.connect(self._seek_preview)
        root.addWidget(self.timeline)
        preview = QHBoxLayout()
        self.preview_button = QPushButton('Предпросмотр')
        self.preview_button.setIcon(get_icon('play'))
        self.preview_button.clicked.connect(self._toggle_preview)
        preview.addWidget(self.preview_button)
        stop = QPushButton('Вернуть объект'); stop.setIcon(get_icon('stop')); stop.clicked.connect(self._restore_preview)
        preview.addWidget(stop)
        self.preview_time = QDoubleSpinBox(); self.preview_time.setRange(0, 600); self.preview_time.setDecimals(3)
        self.preview_time.valueChanged.connect(self._seek_preview)
        preview.addWidget(QLabel('Время, с')); preview.addWidget(self.preview_time)
        root.addLayout(preview)

        columns = QHBoxLayout()
        root.addLayout(columns, 1)

        # --- Список анимаций ---
        left = QVBoxLayout()
        left.addWidget(QLabel("Анимации"))
        self.anim_list = QListWidget()
        self.anim_list.currentTextChanged.connect(self._on_animation_selected)
        left.addWidget(self.anim_list, 1)

        row = QHBoxLayout()
        add_button = QPushButton("Новая")
        add_button.setIcon(get_icon("add"))
        add_button.clicked.connect(self._add_animation)
        row.addWidget(add_button)
        remove_button = QPushButton("Удалить")
        remove_button.setIcon(get_icon("delete"))
        remove_button.clicked.connect(self._remove_animation)
        row.addWidget(remove_button)
        left.addLayout(row)
        duplicate = QPushButton('Дублировать'); duplicate.clicked.connect(self._duplicate_animation)
        rename = QPushButton('Переименовать'); rename.clicked.connect(self._rename_animation)
        left.addWidget(duplicate); left.addWidget(rename)
        import_frames = QPushButton('Импортировать кадры…'); import_frames.clicked.connect(self._import_frames)
        left.addWidget(import_frames)

        # --- Параметры анимации ---
        self.settings = QGroupBox("Параметры")
        form = QFormLayout(self.settings)
        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.01, 600.0)
        self.length_spin.setSingleStep(0.1)
        self.length_spin.setDecimals(2)
        self.length_spin.valueChanged.connect(self._on_settings_changed)
        form.addRow("Длительность, с", self.length_spin)
        self.loop_check = QCheckBox("Зациклить")
        self.loop_check.toggled.connect(self._on_settings_changed)
        form.addRow("", self.loop_check)
        left.addWidget(self.settings)

        columns.addLayout(left, 0)

        # --- Таблица ключей ---
        key_panel = QWidget()
        right = QVBoxLayout(key_panel)
        track_tabs = QTabWidget()
        track_tabs.addTab(key_panel, 'Ключевые кадры')
        right.addWidget(QLabel("Ключевые кадры"))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Время, с", "Свойство", "Значение",
                                              "Плавность"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 190)
        right.addWidget(self.table, 1)
        self.table.itemSelectionChanged.connect(self._select_key)

        # --- Добавление ключа ---
        add_row = QGroupBox("Добавить ключ")
        add_form = QFormLayout(add_row)

        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("например: 0, -90")
        add_form.addRow("Значение", self.value_edit)

        self.prop_combo = QComboBox()
        self.prop_combo.setEditable(True)
        self._fill_properties()
        add_form.insertRow(0, "Свойство", self.prop_combo)

        self.time_spin = QDoubleSpinBox()
        self.time_spin.setRange(0.0, 600.0)
        self.time_spin.setSingleStep(0.05)
        self.time_spin.setDecimals(2)
        add_form.insertRow(1, "Время, с", self.time_spin)

        self.easing_combo = QComboBox()
        for name in EASINGS:
            self.easing_combo.addItem(EASING_TITLES.get(name, name), name)
        add_form.addRow("Плавность", self.easing_combo)

        actions = QHBoxLayout()
        key_button = QPushButton("Добавить ключ")
        key_button.setIcon(get_icon("add"))
        key_button.clicked.connect(self._add_key)
        actions.addWidget(key_button)
        del_button = QPushButton("Удалить ключ")
        del_button.setIcon(get_icon("delete"))
        del_button.clicked.connect(self._remove_key)
        actions.addWidget(del_button)
        clear_button = QPushButton("Очистить")
        clear_button.clicked.connect(self._clear_keys)
        actions.addWidget(clear_button)
        add_form.addRow("", actions)

        right.addWidget(add_row)
        events = QGroupBox('События — метод или сигнал в выбранный момент')
        event_layout = QVBoxLayout(events)
        self.event_table = QTableWidget(0, 4)
        self.event_table.setHorizontalHeaderLabels(['Время', 'Имя', 'Тип', 'Аргументы JSON'])
        self.event_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.event_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.event_table.setMaximumHeight(120)
        self.event_table.horizontalHeader().setStretchLastSection(True)
        event_layout.addWidget(self.event_table)
        fields = QHBoxLayout()
        self.event_name = QLineEdit(); self.event_name.setPlaceholderText('footstep')
        self.event_kind = QComboBox(); self.event_kind.addItem('Метод', 'method'); self.event_kind.addItem('Сигнал', 'signal')
        self.event_args = QLineEdit('[]'); self.event_args.setPlaceholderText('["step", 1]')
        fields.addWidget(self.event_name); fields.addWidget(self.event_kind); fields.addWidget(self.event_args)
        event_layout.addLayout(fields)
        actions = QHBoxLayout()
        add_event = QPushButton('Добавить в текущий момент'); add_event.clicked.connect(self._add_event)
        remove_event = QPushButton('Удалить событие'); remove_event.clicked.connect(self._remove_event)
        actions.addWidget(add_event); actions.addWidget(remove_event); event_layout.addLayout(actions)
        track_tabs.addTab(events, 'События')
        columns.addWidget(track_tabs, 1)

        # --- Автозапуск и кнопки диалога ---
        bottom = QHBoxLayout()
        self.autoplay_edit = QLineEdit(self.player.autoplay)
        self.autoplay_edit.setPlaceholderText("анимация при старте (необязательно)")
        bottom.addWidget(QLabel("Автозапуск:"))
        bottom.addWidget(self.autoplay_edit, 1)
        root.addLayout(bottom)

        buttons = QDialogButtonBox()
        buttons.addButton("Готово", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Отмена", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _fill_properties(self) -> None:
        """Список свойств: общие + свойства целевой ноды."""
        names: List[str] = []
        target = self.player.target_node()
        if isinstance(target, Node):
            try:
                names.extend(target.get_exported_properties().keys())
            except Exception:
                pass
            for component in target.components:
                for prop in component.get_exported_properties():
                    names.append(component.get_type_name()+'.'+prop)
        for name in COMMON_PROPERTIES:
            if name not in names:
                names.append(name)
        self.prop_combo.addItems(names)
        self.prop_combo.currentTextChanged.connect(self._on_property_changed)

    def _on_property_changed(self, name: str) -> None:
        """Подставляет текущее значение свойства как подсказку."""
        if not hasattr(self, "value_edit"):
            return
        target = self.player.target_node()
        value = read_property(target, name, "")
        self.value_edit.setPlaceholderText(f"например: {format_value(value)}")

    # ==================================================================
    # Анимации
    # ==================================================================
    def _reload_animations(self, select: str = "") -> None:
        self.anim_list.blockSignals(True)
        self.anim_list.clear()
        for name in self.player.animation_names():
            self.anim_list.addItem(QListWidgetItem(name))
        self.anim_list.blockSignals(False)
        if self.anim_list.count() == 0:
            self.current = None
            self._reload_keys()
            return
        target = select or self.current or self.anim_list.item(0).text()
        items = [self.anim_list.item(index).text()
                 for index in range(self.anim_list.count())]
        row = items.index(target) if target in items else 0
        self.anim_list.setCurrentRow(row)
        self._on_animation_selected(self.anim_list.item(row).text())

    def _on_animation_selected(self, name: str) -> None:
        self._restore_preview()
        self.current = name or None
        self.preview_time.blockSignals(True); self.preview_time.setValue(0); self.preview_time.blockSignals(False)
        self.timeline.time = 0
        animation = self.player.get_animation(name) if name else None
        has = animation is not None
        self.settings.setEnabled(has)
        if has:
            self.length_spin.blockSignals(True)
            self.loop_check.blockSignals(True)
            self.length_spin.setValue(animation.length)
            self.loop_check.setChecked(animation.loop)
            self.length_spin.blockSignals(False)
            self.loop_check.blockSignals(False)
        self._reload_keys()

    def _reload_keys(self) -> None:
        animation = self._animation()
        self.table.setRowCount(0)
        self.event_table.setRowCount(0)
        self.timeline.animation = animation
        self.timeline.update()
        if animation is None:
            return
        rows: List[tuple] = []
        for prop, keys in animation.keys.items():
            for index, key in enumerate(keys):
                rows.append((key[0], prop, key[1], key[2], index))
        rows.sort(key=lambda item: (item[1], item[0]))
        self.table.setRowCount(len(rows))
        for row, (time, prop, value, easing, _index) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(f"{time:.2f}"))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole,time)
            self.table.setItem(row, 1, QTableWidgetItem(prop))
            self.table.setItem(row, 2, QTableWidgetItem(format_value(value)))
            self.table.setItem(row, 3, QTableWidgetItem(EASING_TITLES.get(easing, easing)))
        self.table.resizeColumnsToContents()
        self.event_table.setRowCount(len(animation.events))
        for row, event in enumerate(animation.events):
            for column, value in enumerate([event['time'], event['name'], event['kind'], json.dumps(event['args'], ensure_ascii=False)]):
                self.event_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _animation(self) -> Optional[Animation]:
        if not self.current:
            return None
        return self.player.get_animation(self.current)

    # ==================================================================
    # Действия
    # ==================================================================
    def _add_animation(self) -> None:
        name, ok = QInputDialog.getText(self, "Новая анимация", "Название:",
                                        text="anim")
        if not ok or not name.strip():
            return
        name = name.strip()
        if self.player.get_animation(name) is not None:
            QMessageBox.warning(self, "Анимация", f"«{name}» уже существует.")
            return
        self.player.add_animation(name, 1.0, False)
        self._reload_animations(name)

    def _remove_animation(self) -> None:
        if not self.current:
            return
        self.player.remove_animation(self.current)
        if self.autoplay_edit.text() == self.current:
            self.autoplay_edit.clear()
        self.current = ""
        self._reload_animations()

    def _on_settings_changed(self, *_args: Any) -> None:
        animation = self._animation()
        if animation is None:
            return
        last_key = max([key[0] for keys in animation.keys.values() for key in keys] +
                       [event['time'] for event in animation.events] + [0.01])
        animation.length = max(last_key, float(self.length_spin.value()))
        self.length_spin.blockSignals(True); self.length_spin.setValue(animation.length); self.length_spin.blockSignals(False)
        animation.loop = bool(self.loop_check.isChecked())
        self.timeline.update()

    def _add_key(self) -> None:
        animation = self._animation()
        if animation is None:
            QMessageBox.information(self, "Ключ",
                                    "Сначала создайте анимацию слева.")
            return
        prop = self.prop_combo.currentText().strip()
        if not prop:
            return
        target = self.player.target_node()
        sample = read_property(target, prop)
        if sample is None:
            QMessageBox.warning(self,'Свойство','Свойство не найдено у целевого объекта или компонента.'); return
        value = parse_value(self.value_edit.text(), sample)
        if value is None:
            QMessageBox.warning(self, "Значение",
                                "Не удалось разобрать значение.\n"
                                "Число: 120\nВектор: 0, -90\nЦвет: 255, 200, 120, 255")
            return
        animation.add_key(prop, float(self.time_spin.value()), value,
                          self.easing_combo.currentData() or "linear")
        if float(self.time_spin.value()) > animation.length:
            animation.length = float(self.time_spin.value())
            self.length_spin.setValue(animation.length)
        self._reload_keys()

    def _remove_key(self) -> None:
        animation = self._animation()
        row = self.table.currentRow()
        if animation is None or row < 0:
            return
        prop_item = self.table.item(row, 1)
        time_item = self.table.item(row, 0)
        if prop_item is None or time_item is None:
            return
        prop = prop_item.text()
        time = time_item.data(Qt.ItemDataRole.UserRole)
        keys = animation.keys.get(prop, [])
        for index, key in enumerate(keys):
            if abs(key[0] - time) < 1e-6:
                animation.remove_key(prop, index)
                break
        self._reload_keys()

    def _clear_keys(self) -> None:
        animation = self._animation()
        if animation is None:
            return
        if QMessageBox.question(self, "Очистить",
                                f"Удалить все ключи анимации «{animation.name}»?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        animation.keys.clear()
        self._reload_keys()

    # ==================================================================
    def _accept(self) -> None:
        if self.autoplay_edit.text().strip() and self.autoplay_edit.text().strip() not in self.player.animations:
            QMessageBox.warning(self, 'Автозапуск', 'Выберите существующую анимацию.'); return
        self.player.autoplay = self.autoplay_edit.text().strip()
        self.accept()

    def _finish_preview(self, result):
        self._restore_preview()
        if result != QDialog.DialogCode.Accepted:
            self.player._deserialize_data(copy.deepcopy(self.before_data))

    def _restore_preview(self):
        self.preview_timer.stop()
        if hasattr(self, 'preview_button'): self.preview_button.setText('Предпросмотр')
        if self._preview_target is not None:
            for prop, value in self._preview_saved.items(): write_property(self._preview_target,prop,copy.deepcopy(value))
        self._preview_saved.clear(); self._preview_target = None

    def _seek_preview(self, time):
        animation = self._animation()
        if animation is None: return
        target = self.player.target_node()
        if self._preview_target is not None and target is not self._preview_target: self._restore_preview()
        self._preview_target = target
        time = max(0, min(float(time), animation.length))
        for prop in animation.keys:
            current=read_property(target,prop)
            if current is not None:
                if prop not in self._preview_saved: self._preview_saved[prop] = copy.deepcopy(current)
                write_property(target, prop, copy.deepcopy(animation.value_at(prop, time)))
        self.timeline.time = time; self.timeline.update()
        self.preview_time.blockSignals(True); self.preview_time.setValue(time); self.preview_time.blockSignals(False)

    def _toggle_preview(self):
        if self.preview_timer.isActive():
            self.preview_timer.stop(); self.preview_button.setText('Предпросмотр'); return
        animation = self._animation()
        if animation is None: return
        if self.preview_time.value() >= animation.length: self._seek_preview(0)
        self.preview_clock.start(); self.preview_timer.start(); self.preview_button.setText('Пауза')

    def _preview_tick(self):
        animation = self._animation()
        if animation is None: self._restore_preview(); return
        time = self.preview_time.value() + min(.1, self.preview_clock.restart()/1000)
        if time >= animation.length:
            if animation.loop: time %= animation.length
            else: time = animation.length; self.preview_timer.stop(); self.preview_button.setText('Предпросмотр')
        self._seek_preview(time)

    def _select_key(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 3) is None: return
        time = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.time_spin.setValue(time); self.prop_combo.setCurrentText(self.table.item(row, 1).text())
        self.value_edit.setText(self.table.item(row, 2).text()); self._seek_preview(time)
        self.easing_combo.setCurrentText(self.table.item(row,3).text())

    def _add_event(self):
        animation = self._animation()
        if animation is None: return
        try: animation.add_event(self.preview_time.value(), self.event_name.text().strip(), json.loads(self.event_args.text()), self.event_kind.currentData())
        except (ValueError, TypeError) as error: QMessageBox.warning(self, 'Событие', str(error)); return
        self._reload_keys()

    def _remove_event(self):
        animation = self._animation(); row = self.event_table.currentRow()
        if animation is not None and 0 <= row < len(animation.events): animation.events.pop(row); self._reload_keys()

    def _duplicate_animation(self):
        animation = self._animation()
        if animation is None: return
        name, ok = QInputDialog.getText(self, 'Копия анимации', 'Название:', text=animation.name+'_copy')
        name = name.strip()
        if ok and name and name not in self.player.animations:
            duplicate = copy.deepcopy(animation); duplicate.name = name; self.player.animations[name] = duplicate; self._reload_animations(name)

    def _rename_animation(self):
        animation = self._animation()
        if animation is None: return
        name, ok = QInputDialog.getText(self, 'Переименовать', 'Название:', text=animation.name)
        name = name.strip()
        if ok and name and name not in self.player.animations:
            old = self.current; self.player.animations.pop(old); animation.name = name; self.player.animations[name] = animation
            if self.autoplay_edit.text() == old: self.autoplay_edit.setText(name)
            self._reload_animations(name)

    def _import_frames(self):
        from pathlib import Path
        animation=self._animation()
        if animation is None:
            QMessageBox.information(self,'Кадры','Сначала создайте анимацию.'); return
        parent=self.window()
        while parent.parentWidget() is not None: parent=parent.parentWidget()
        root=Path(getattr(parent,'project_dir','') or '.').resolve()
        paths,_=QFileDialog.getOpenFileNames(self,'Кадры в порядке имени',str(root),'Images (*.png *.jpg *.bmp *.webp)')
        if not paths: return
        fps,ok=QInputDialog.getDouble(self,'Частота кадров','Кадров в секунду:',12,1,120,1)
        if not ok: return
        target=self.player.target_node()
        prop='SpriteRenderer.texture_path' if target.get_component('SpriteRenderer') else 'texture_path'
        if read_property(target,prop) is None:
            QMessageBox.warning(self,'Кадры','Выберите Sprite2D или объект с компонентом SpriteRenderer в качестве цели.'); return
        try: relative=[Path(path).resolve().relative_to(root).as_posix() for path in paths]
        except ValueError:
            QMessageBox.warning(self,'Кадры','Сначала импортируйте все кадры в папку проекта.'); return
        import re
        relative.sort(key=lambda value:[(0,int(part)) if part.isdigit() else (1,part.lower()) for part in re.split(r'(\d+)',value)])
        animation.keys.pop(prop,None)
        for index,path in enumerate(relative): animation.add_key(prop,index/fps,path,'step')
        animation.length=max([len(relative)/fps]+[key[0] for name,keys in animation.keys.items() if name!=prop for key in keys]+[event['time'] for event in animation.events])
        self.length_spin.setValue(animation.length); self._reload_keys()


__all__ = ["AnimationEditorDialog", "format_value", "parse_value"]
