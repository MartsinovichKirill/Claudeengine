"""InspectorPanel — свойства выбранной ноды и её компонентов.

Отображает:
- имя ноды и её экспортируемые свойства;
- список навешанных компонентов с возможностью добавить/удалить,
  включить/выключить и отредактировать их свойства.

Изменения сразу применяются и попадают в Undo/Redo через сигналы.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
                             QCheckBox, QComboBox, QPushButton, QColorDialog,
                             QFormLayout, QGroupBox, QMenu, QToolButton,
                             QSizePolicy, QFileDialog, QMessageBox, QLayout)

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.components.registry import (component_description,
                                        visible_categories)
from editor.icons import get_icon

logger = logging.getLogger("cloudengine.inspector")


class InspectorContent(QWidget):
    """Scroll vertically instead of squeezing controls or widening the viewport."""
    def event(self,event):
        result=super().event(event)
        if event.type() in (QEvent.Type.LayoutRequest,QEvent.Type.StyleChange,QEvent.Type.FontChange,QEvent.Type.Resize) and self.layout():
            layout=self.layout()
            for field in self.findChildren(QWidget):
                if isinstance(field,(QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QPushButton,QToolButton,QCheckBox)):
                    height=field.sizeHint().height()
                    if height>0 and field.minimumHeight()<height: field.setMinimumHeight(height)
            for index in range(layout.count()):
                widget=layout.itemAt(index).widget()
                if widget is not None:
                    hint=widget.sizeHint().height()
                    if widget.layout() and widget.layout().hasHeightForWidth():
                        hint=max(hint,widget.layout().heightForWidth(max(1,self.width()-16)))
                    if widget.minimumHeight()!=hint: widget.setMinimumHeight(hint)
            height=layout.minimumSize().height()
            if self.layout().hasHeightForWidth(): height=max(height,self.layout().heightForWidth(self.width()))
            if self.minimumHeight()!=height: self.setMinimumHeight(height)
        return result

    def minimumSizeHint(self):
        return QSize(0,self.minimumHeight())

    def sizeHint(self):
        return QSize(330,self.minimumHeight())


class InspectorPanel(QWidget):
    """Редактор свойств выбранной ноды и её компонентов."""

    property_changed = pyqtSignal(object, str, object, object)
    component_add_requested = pyqtSignal(object, str)          # (нода, тип)
    component_remove_requested = pyqtSignal(object, object)    # (нода, компонент)
    component_property_changed = pyqtSignal(object, object, str, object, object)
    component_enabled_changed = pyqtSignal(object, object, bool)
    animation_edited = pyqtSignal(object, dict, dict)          # (нода, было, стало)
    component_data_edited = pyqtSignal(object, dict, dict)
    particle_edited = pyqtSignal(object, dict, dict)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(330)
        self.node: Optional[Node] = None
        self._collapsed = set()
        self._build_ui()

    # ==================================================================
    # Построение
    # ==================================================================
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = InspectorContent()
        self.form_layout = QVBoxLayout(self.container)
        self.form_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.form_layout.setContentsMargins(8, 8, 8, 8)
        self.form_layout.setSpacing(12)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def set_node(self, node: Optional[Node]) -> None:
        if self.node is node:
            return
        # Commit the previous object's active field before changing selection.
        focused = self.focusWidget()
        if focused is not None:
            focused.clearFocus()
        self.node = node
        self.refresh()

    def refresh(self) -> None:
        self._rebuild()

    def _clear(self) -> None:
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _rebuild(self) -> None:
        self._clear()

        if self.node is None:
            hint = QLabel("Нода не выбрана")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet("color: #9e9e9e; padding: 20px;")
            self.form_layout.addWidget(hint)
            self.form_layout.addStretch(1)
            return

        title = QLabel(type(self.node).__name__)
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.form_layout.addWidget(title)

        # --- Нода ---
        name_group = QGroupBox("Объект")
        name_form = QFormLayout(name_group)
        edit = QLineEdit(self.node.name)
        selected_node = self.node
        edit.editingFinished.connect(lambda: self._emit_name_change(edit.text()) if self.node is selected_node else None)
        name_form.addRow("Имя", edit)
        if getattr(self.node, "script_path", ""):
            script_label = QLabel(self.node.script_path)
            script_label.setStyleSheet("color: #9e9e9e;")
            name_form.addRow("Скрипт", script_label)
        if self.node.get_component('Transform'):
            visible = QCheckBox()
            visible.setChecked(self.node.visible)
            visible.toggled.connect(lambda value: self._emit_node_property('visible', value) if self.node is selected_node else None)
            name_form.addRow('Видимость', visible)
        self.form_layout.addWidget(name_group)

        # --- Свойства ноды ---
        props = {k: v for k, v in self.node.get_property_list().items() if k not in ('name', 'script_path')}
        if self.node.get_component('Transform'):
            props = {k: v for k, v in props.items() if k not in ('position', 'rotation', 'scale', 'z_index', 'visible', 'modulate', 'z_as_relative')}
        transform = {k: v for k, v in props.items() if k in ('position', 'rotation', 'scale')}
        if transform:
            group = QGroupBox('Transform')
            self._add_rows(QFormLayout(group), self.node, transform, self._emit_node_property)
            self.form_layout.addWidget(group)
            props = {k: v for k, v in props.items() if k not in transform}
        if props:
            props_group = QGroupBox(type(self.node).__name__)
            props_form = QFormLayout(props_group)
            self._add_rows(props_form, self.node, props, self._emit_node_property)
            self.form_layout.addWidget(props_group)

        # --- Особая секция для AnimationPlayer ---
        animation_group = self._build_animation_section()
        if animation_group is not None:
            self.form_layout.addWidget(animation_group)
        from engine.nodes.particles2d import Particles2D
        if isinstance(self.node, Particles2D):
            button = QPushButton('Открыть редактор частиц…')
            button.clicked.connect(self._open_particle_editor)
            self.form_layout.addWidget(button)

        # --- Компоненты ---
        self.form_layout.addWidget(self._build_components_section())
        self.form_layout.addStretch(1)

    def _build_animation_section(self) -> Optional[QWidget]:
        """Кнопка открытия редактора анимаций для узла AnimationPlayer."""
        from engine.nodes.animation_player import AnimationPlayer
        if not isinstance(self.node, AnimationPlayer):
            return None
        group = QGroupBox("Анимации (ключевые кадры)")
        layout = QVBoxLayout(group)
        names = self.node.animation_names()
        info = QLabel(f"Анимаций: {len(names)}"
                      + (f"\n{', '.join(names)}" if names else
                         "\nАнимаций пока нет — создайте первую."))
        info.setWordWrap(True)
        info.setStyleSheet("color:#8c8c99;")
        layout.addWidget(info)
        button = QPushButton("Редактировать анимации…")
        button.setIcon(get_icon("visual"))
        button.clicked.connect(self._open_animation_editor)
        layout.addWidget(button)
        return group

    # ==================================================================
    # Секция компонентов
    # ==================================================================
    def _build_components_section(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Компоненты")
        label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        label.setStyleSheet("font-weight: bold;")
        label.setToolTip("Компоненты навешиваются на объект, а не на сцену")
        header_layout.addWidget(label)
        header_layout.addStretch(1)

        # Основной способ: диалог с поиском.
        pick_btn = QToolButton()
        pick_btn.setText("Добавить")
        pick_btn.setIcon(get_icon("add"))
        pick_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        pick_btn.setToolTip("Добавить компонент на этот объект")
        pick_btn.clicked.connect(self._open_picker)
        header_layout.addWidget(pick_btn)

        # Быстрый доступ по категориям.
        add_btn = QToolButton()
        add_btn.setIcon(get_icon('chevron_down'))
        add_btn.setToolTip("Выбрать по категориям")
        add_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(add_btn)
        for category, types in visible_categories().items():
            cat_menu = menu.addMenu(category)
            for type_name in types:
                action = cat_menu.addAction(type_name)
                action.setToolTip(component_description(type_name))
                action.triggered.connect(
                    lambda checked=False, t=type_name: self._request_add_component(t))
        add_btn.setMenu(menu)
        header_layout.addWidget(add_btn)
        layout.addWidget(header)

        components: List[Any] = list(getattr(self.node, "components", []) or [])
        if not components:
            empty = QLabel("Компоненты не навешаны.\n"
                           "Нажмите «Добавить», чтобы дать объекту поведение "
                           "без единой строки кода.")
            empty.setWordWrap(True)
            empty.setStyleSheet("color: #9e9e9e; padding: 4px 6px;")
            layout.addWidget(empty)
            return wrapper

        for component in components:
            layout.addWidget(self._build_component_group(component))
        return wrapper

    def _open_picker(self) -> None:
        """Открывает диалог выбора компонента с поиском."""
        if self.node is None:
            return
        try:
            from editor.component_picker import ComponentPickerDialog
            chosen = ComponentPickerDialog.pick(self, getattr(self.node, "name", ""))
        except Exception:
            logger.exception("Не удалось открыть выбор компонента")
            return
        if chosen:
            self._request_add_component(chosen)

    def _open_animation_editor(self) -> None:
        """Открывает редактор анимаций для узла AnimationPlayer."""
        if self.node is None:
            return
        try:
            from editor.animation_editor import AnimationEditorDialog
            dialog = AnimationEditorDialog(self.node, self)
            if dialog.exec() == dialog.DialogCode.Accepted:
                self.animation_edited.emit(self.node, dialog.before_data,
                                           self.node._serialize_data())
        except Exception:
            logger.exception("Не удалось открыть редактор анимаций")

    def _request_add_component(self, type_name: str) -> None:
        if self.node is not None:
            self.component_add_requested.emit(self.node, type_name)

    def _open_particle_editor(self):
        from editor.particle_editor import ParticleEditorDialog, particle_values
        parent = self.window()
        node = self.node
        dialog = ParticleEditorDialog(node, getattr(parent,'project_dir',''), self)
        before = particle_values(node)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.particle_edited.emit(node,before,dialog.result_values)

    def _build_component_group(self, component: Any) -> QGroupBox:
        group = QGroupBox()
        group.setObjectName('ComponentCard')
        group.setToolTip(getattr(component,'description',''))
        outer=QVBoxLayout(group); outer.setContentsMargins(12,12,12,12); outer.setSpacing(12)
        toolbar=QHBoxLayout(); toolbar.setSpacing(8)
        fold=QToolButton()
        fold.setIcon(get_icon('chevron_right' if id(component) in self._collapsed else 'chevron_down',16))
        fold.setToolTip('Свернуть / развернуть'); toolbar.addWidget(fold)
        icon=QLabel()
        icon_name={'SpriteRenderer':'image','Rigidbody2D':'physics','BoxCollider2D':'node',
            'CircleCollider2D':'physics','Transform':'move','AudioSource':'audio',
            'ScriptBehaviour':'script','Animator':'visual','Camera2D':'camera','Light2D':'light'}.get(component.get_type_name(),'component')
        icon.setPixmap(get_icon(icon_name,20,'#8cb9da').pixmap(20,20)); toolbar.addWidget(icon)
        title=QLabel(component.get_type_name()); title.setStyleSheet('font-weight:600;color:#d6e6f2;')
        title.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        title.setToolTip(component.get_type_name())
        toolbar.addWidget(title,1)
        if not getattr(component,'required',False):
            enabled=QCheckBox(); enabled.setChecked(component.enabled); enabled.setToolTip('Включить компонент')
            enabled.toggled.connect(lambda value,c=component:self._toggle_component(c,value))
            toolbar.addWidget(enabled)
        options=QToolButton(); options.setIcon(get_icon('more',16)); options.setToolTip('Действия компонента')
        options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(options)
        reset = menu.addAction('Сбросить свойства')
        reset.triggered.connect(lambda: self._reset_component(component))
        remove = menu.addAction(get_icon('delete'), 'Удалить компонент')
        remove.setEnabled(not getattr(component, 'required', False))
        remove.triggered.connect(lambda: self._request_remove_component(component))
        menu.addSeparator()
        menu.addAction('Копировать настройки', lambda: self._copy_component(component))
        paste = menu.addAction('Вставить настройки', lambda: self._paste_component(component))
        paste.setEnabled(getattr(InspectorPanel, '_component_clipboard', {}).get('type') == component.get_type_name())
        menu.addAction('Сохранить пресет…', lambda: self._save_preset(component))
        menu.addAction('Загрузить пресет…', lambda: self._load_preset(component))
        menu.addSeparator()
        up = menu.addAction('Переместить выше', lambda: self._move_component(component, -1))
        down = menu.addAction('Переместить ниже', lambda: self._move_component(component, 1))
        index = self.node.components.index(component)
        up.setEnabled(not getattr(component, 'required', False) and index > (1 if self.node.get_component('Transform') else 0))
        down.setEnabled(not getattr(component, 'required', False) and index < len(self.node.components)-1)
        options.setMenu(menu); toolbar.addWidget(options); outer.addLayout(toolbar)
        body = QWidget(); form = QFormLayout(body)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        def toggle_fold():
            collapsed = id(component) not in self._collapsed
            if collapsed:
                self._collapsed.add(id(component))
            else:
                self._collapsed.discard(id(component))
            body.setVisible(not collapsed)
            fold.setIcon(get_icon('chevron_right' if collapsed else 'chevron_down',16))
        fold.clicked.connect(toggle_fold)
        props = component.get_exported_properties()
        filtered = {k: v for k, v in props.items() if k != "enabled"}
        self._add_rows(form, component, filtered,
                       lambda prop, value, c=component:
                       self._emit_component_property(c, prop, value))
        outer.addWidget(body)
        body.setVisible(id(component) not in self._collapsed)
        if component.get_type_name() == 'ScriptBehaviour':
            system = getattr(self.window(), 'script_system', None)
            cls = system.get_class_for(component.script_path) if system and component.script_path else None
            from engine.components.behaviour import Behaviour
            if cls and issubclass(cls, Behaviour):
                defaults = cls()
                fields = {k: v for k, v in cls.get_exported_properties().items() if k != 'enabled'}
                for key in fields:
                    if key in component.fields:
                        defaults.set(key, component.fields[key])
                def field_changed(key, value):
                    import copy
                    old = component._serialize_data()
                    new = copy.deepcopy(old)
                    new['fields'][key] = value
                    self.component_data_edited.emit(component, old, new)
                self._add_rows(form, defaults, fields, field_changed)
            elif component.script_path:
                label = QLabel('Нужен скрипт, наследующий Behaviour. Перезагрузите скрипты после сохранения.')
                label.setWordWrap(True)
                outer.addWidget(label)
        if component.get_type_name() == 'Animator':
            button = QPushButton('Открыть граф состояний…')
            button.setIcon(get_icon('visual'))
            button.clicked.connect(lambda: self._edit_animator(component))
            outer.addWidget(button)
        if component.get_type_name() == 'EnemyAI':
            button=QPushButton('Редактировать поведение врага…')
            button.setIcon(get_icon('visual'))
            button.clicked.connect(lambda:self._edit_enemy_ai(component))
            outer.addWidget(button)
        if component.get_type_name() == 'DataSource':
            button=QPushButton('Открыть файл игровых данных…')
            def open_data():
                from editor.production_tools import open_data
                from engine.resources.game_data import project_path
                parent=self.window()
                try: path=str(project_path(parent.project_dir,component.data_path)) if component.data_path else ''
                except ValueError as error: QMessageBox.warning(self,'Данные',str(error)); return
                open_data(parent,path)
            button.clicked.connect(open_data); outer.addWidget(button)

        return group

    def _apply_component_values(self, component, data):
        from editor.undo_stack import ComponentValuesCommand
        if data.get('type') != component.get_type_name():
            return
        command = ComponentValuesCommand(component, component.to_dict(), data)
        self.window().undo_stack.execute(command)
        self.refresh()

    def _reset_component(self, component):
        self._apply_component_values(component, component.__class__().to_dict())

    def _copy_component(self, component):
        import copy
        InspectorPanel._component_clipboard = copy.deepcopy(component.to_dict())
        self.refresh()

    def _paste_component(self, component):
        self._apply_component_values(component, InspectorPanel._component_clipboard)

    def _move_component(self, component, direction):
        from editor.undo_stack import ReorderComponentCommand
        if not getattr(component, 'required', False):
            self.window().undo_stack.execute(ReorderComponentCommand(self.node, component, self.node.components.index(component) + direction))
            self.refresh()

    def _save_preset(self, component):
        import json
        from pathlib import Path
        path, _ = QFileDialog.getSaveFileName(self, 'Пресет компонента', '', 'Cloud Component (*.component)')
        if path:
            Path(path).write_text(json.dumps(component.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

    def _load_preset(self, component):
        import json
        from pathlib import Path
        from PyQt6.QtWidgets import QMessageBox
        path, _ = QFileDialog.getOpenFileName(self, 'Пресет компонента', '', 'Cloud Component (*.component)')
        if path:
            try:
                data = json.loads(Path(path).read_text(encoding='utf-8'))
                if not isinstance(data, dict) or data.get('type') != component.get_type_name():
                    raise ValueError('Пресет принадлежит другому типу компонента')
                self._apply_component_values(component, data)
            except (OSError, ValueError, TypeError) as exc:
                QMessageBox.warning(self, 'Пресет', str(exc))

    def _edit_animator(self, component):
        from editor.animator_editor import AnimatorEditor
        dialog = AnimatorEditor(component, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            old = component._serialize_data()
            self.component_data_edited.emit(component, old, dialog.result_data)
            self._emit_component_property(component, 'entry_state', dialog.entry.text().strip())

    def _edit_enemy_ai(self,component):
        from editor.enemy_editor import EnemyEditor
        dialog=EnemyEditor(component,self)
        if dialog.exec()==dialog.DialogCode.Accepted:
            self.component_data_edited.emit(component,component._serialize_data(),dialog.result_data)
            if hasattr(self.window(),'_mark_dirty'): self.window()._mark_dirty()

    def _toggle_component(self, component: Any, enabled: bool) -> None:
        """Включает/выключает компонент."""
        if not enabled and callable(getattr(component, "stop", None)):
            component.stop()
        component.enabled = enabled
        if self.node is not None:
            self.component_enabled_changed.emit(self.node, component, enabled)

    def _request_remove_component(self, component: Any) -> None:
        if self.node is not None:
            self.component_remove_requested.emit(self.node, component)

    # ==================================================================
    # Фабрика виджетов
    # ==================================================================
    def _add_rows(self, form: QFormLayout, target: Any, props: Dict[str, Dict[str, Any]],
                  emit: Callable[[str, Any], None]) -> None:
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        selected_node = self.node
        original_emit = emit
        emit = lambda prop, value: original_emit(prop, value) if self.node is selected_node else None
        for prop, spec in props.items():
            widget = self._make_widget(target, prop, spec, emit)
            if widget is not None:
                form.addRow(_pretty(prop), widget)

    def _make_widget(self, target: Any, prop: str, spec: Dict[str, Any],
                     emit: Callable[[str, Any], None]) -> Optional[QWidget]:
        value = getattr(target, prop, spec.get("default"))
        ptype = spec.get("type", "string")

        if ptype == "bool":
            w = QCheckBox()
            w.setChecked(bool(value))
            w.toggled.connect(lambda checked, p=prop: emit(p, checked))
            return w
        if ptype == "int":
            w = QSpinBox()
            w.setKeyboardTracking(False)
            w.setRange(int(spec.get("min", -2**31)), int(spec.get("max", 2**31 - 1)))
            w.setValue(int(value) if value is not None else 0)
            w.valueChanged.connect(lambda v, p=prop: emit(p, v))
            return w
        if ptype == "float":
            w = QDoubleSpinBox()
            w.setKeyboardTracking(False)
            w.setRange(float(spec.get("min", -1e9)), float(spec.get("max", 1e9)))
            w.setDecimals(3)
            w.setSingleStep(float(spec.get("step", 0.1)))
            w.setValue(float(value) if value is not None else 0.0)
            w.valueChanged.connect(lambda v, p=prop: emit(p, v))
            return w
        if ptype == "enum":
            w = QComboBox()
            options = [str(o) for o in spec.get("options", [])]
            w.addItems(options)
            current = str(value) if value is not None else (options[0] if options else "")
            idx = w.findText(current)
            if idx >= 0:
                w.setCurrentIndex(idx)
            w.currentTextChanged.connect(lambda v, p=prop: emit(p, v))
            return w
        if ptype == "color":
            return self._make_color_widget(prop, value, emit)
        if ptype == "vector2":
            return self._make_vector_widget(prop, value, emit)
        w = QLineEdit(str(value if value is not None else ""))
        w.editingFinished.connect(lambda p=prop, e=w: emit(p, e.text()))
        if ptype == 'resource' or prop in ('texture_path', 'normal_map', 'shader_path'):
            import os
            wrapper = QWidget(); row = QHBoxLayout(wrapper); row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(w, 1)
            browse = QToolButton(); browse.setIcon(get_icon('folder')); row.addWidget(browse)
            def choose():
                root = getattr(self.window(), 'project_dir', '')
                path, _ = QFileDialog.getOpenFileName(self, 'Ресурс', root, 'Все файлы (*)')
                if path:
                    value = os.path.relpath(path, root).replace('\\', '/') if root else path
                    w.setText(value); emit(prop, value)
            browse.clicked.connect(choose)
            return wrapper
        return w

    def _make_color_widget(self, prop: str, value: Any,
                           emit: Callable[[str, Any], None]) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton()
        btn.setFixedSize(32, 20)
        color = _tuple_to_qcolor(value)
        btn.setStyleSheet(_color_style(color))
        btn.clicked.connect(
            lambda checked=False, p=prop, b=btn, v=value: self._pick_color(p, v, b, emit))
        layout.addWidget(btn)
        layout.addStretch(1)
        return container

    def _pick_color(self, prop: str, current: Any, btn: QPushButton,
                    emit: Callable[[str, Any], None]) -> None:
        color = QColorDialog.getColor(_tuple_to_qcolor(current), self, "Выбор цвета",
                                      QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            btn.setStyleSheet(_color_style(color))
            emit(prop, (color.red(), color.green(), color.blue(), color.alpha()))

    def _make_vector_widget(self, prop: str, value: Any,
                            emit: Callable[[str, Any], None]) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        vector = value if isinstance(value, Vector2) else Vector2(value)
        x_spin = QDoubleSpinBox()
        x_spin.setKeyboardTracking(False)
        x_spin.setMinimumWidth(48)
        x_spin.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        x_spin.setRange(-1e9, 1e9)
        x_spin.setDecimals(2)
        x_spin.setValue(vector.x)
        y_spin = QDoubleSpinBox()
        y_spin.setKeyboardTracking(False)
        y_spin.setMinimumWidth(48)
        y_spin.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        y_spin.setRange(-1e9, 1e9)
        y_spin.setDecimals(2)
        y_spin.setValue(vector.y)

        def on_change(*_):
            emit(prop, Vector2(x_spin.value(), y_spin.value()))

        x_spin.valueChanged.connect(on_change)
        y_spin.valueChanged.connect(on_change)
        layout.addWidget(QLabel("X"))
        layout.addWidget(x_spin, 1)
        layout.addWidget(QLabel("Y"))
        layout.addWidget(y_spin, 1)
        return container

    # ==================================================================
    # Испускание изменений
    # ==================================================================
    def _emit_name_change(self, text: str) -> None:
        if self.node is not None and text.strip():
            old = self.node.name
            self.node.name = text.strip()
            self.property_changed.emit(self.node, "name", old, self.node.name)

    def _emit_node_property(self, prop: str, value: Any) -> None:
        if self.node is None:
            return
        old = getattr(self.node, prop, None)
        if old == value:
            return
        try:
            self.node.set(prop, value)
        except Exception:
            pass
        self.property_changed.emit(self.node, prop, old, value)

    def _emit_component_property(self, component: Any, prop: str, value: Any) -> None:
        if self.node is None or component not in self.node.components:
            return
        old = getattr(component, prop, None)
        if old == value:
            return
        try:
            component.set(prop, value)
        except Exception:
            pass
        self.component_property_changed.emit(self.node, component, prop, old, value)
        if component.get_type_name() == "ScriptBehaviour" and prop == "script_path":
            self.refresh()


def _color_style(color: QColor) -> str:
    return (f"background-color: {color.name()};"
            "border: 1px solid #1a1a1a; border-radius: 3px;")


def _pretty(prop: str) -> str:
    """Человекочитаемое имя свойства."""
    labels={'position':'Позиция','rotation':'Поворот','scale':'Масштаб','texture_path':'Текстура',
        'material_path':'Материал','color':'Цвет','flip_h':'Отразить по X','flip_v':'Отразить по Y',
        'pixel_art':'Чёткие пиксели','sorting_order':'Порядок слоя','hframes':'Столбцы атласа',
        'vframes':'Строки атласа','frame':'Кадр','mass':'Масса','gravity_scale':'Гравитация',
        'drag':'Сопротивление','bounce':'Отскок','freeze':'Заморозить','size':'Размер','offset':'Смещение',
        'radius':'Радиус','script_path':'Скрипт','stream_path':'Аудиофайл','volume_db':'Громкость, дБ',
        'entry_state':'Начальное состояние','use_import_settings':'Настройки импорта'}
    return labels.get(prop,prop.replace('_',' ').capitalize())


def _tuple_to_qcolor(value: Any) -> QColor:
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        return QColor(int(value[0]), int(value[1]), int(value[2]),
                      int(value[3]) if len(value) > 3 else 255)
    return QColor(255, 255, 255, 255)
