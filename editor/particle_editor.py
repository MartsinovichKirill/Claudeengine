"""Isolated live particle preview; scene values change only after Apply."""
import json
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QElapsedTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QImage
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox, QPushButton,
    QDialogButtonBox, QColorDialog, QLabel, QFileDialog, QLineEdit, QMessageBox,
    QScrollArea)

from engine.nodes.particles2d import Particles2D
from engine.systems.particle_system import ParticleSystem
from engine.resources.scene_serializer import SceneSerializer, value_to_json
from engine.math.vector2 import Vector2


PRESETS = {
    'Искры': dict(amount=80, lifetime=.5, speed=220, spread=360, gravity=[0, 260],
                  particle_size=2, color=[255, 210, 90, 255], end_color=[255, 60, 10, 0], one_shot=True),
    'Огонь': dict(amount=120, lifetime=1, speed=65, spread=35, rotation=90,
                 gravity=[0, -20], particle_size=7, color=[255, 190, 40, 220],
                 end_color=[150, 15, 0, 0], one_shot=False),
    'Дым': dict(amount=60, lifetime=3, speed=25, spread=40, rotation=90,
               gravity=[0, -8], particle_size=8, end_size_ratio=2.5,
               color=[140, 145, 150, 120], end_color=[60, 65, 70, 0], one_shot=False),
    'Пепел': dict(amount=100, lifetime=4, speed=15, spread=100, rotation=-90,
                 gravity=[8, 10], particle_size=2, color=[180, 170, 165, 200],
                 end_color=[90, 85, 80, 0], one_shot=False),
}


def particle_values(emitter):
    return {key: value_to_json(getattr(emitter, key)) for key in emitter.get_exported_properties()
            if key in Particles2D.exported_properties or key == 'rotation'}


def apply_particle_values(emitter, values):
    """Validate external presets before applying any value."""
    import math
    specs = emitter.get_exported_properties()
    converted = {}
    for key, value in values.items():
        if key not in particle_values(emitter):
            continue
        spec = specs[key]
        kind = spec['type']
        if kind in ('float', 'int'):
            number = float(value)
            if not math.isfinite(number) or not spec.get('min', -1e9) <= number <= spec.get('max', 1e9):
                raise ValueError(f'Недопустимое значение {key}')
            value = int(number) if kind == 'int' else number
        elif kind == 'vector2':
            if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(math.isfinite(float(x)) and abs(float(x)) <= 100000 for x in value):
                raise ValueError('Ускорение должно содержать два конечных числа')
            value = Vector2(value)
        elif kind == 'color':
            if not isinstance(value, (list, tuple)) or len(value) != 4 or not all(isinstance(x, int) and 0 <= x <= 255 for x in value):
                raise ValueError('Цвет должен содержать четыре числа от 0 до 255')
            value = tuple(value)
        elif kind == 'bool':
            if not isinstance(value, bool): raise ValueError(f'{key}: ожидается true или false')
        elif kind == 'resource':
            if not isinstance(value, str): raise ValueError('Путь текстуры должен быть строкой')
        converted[key] = value
    for key, value in converted.items(): emitter.set(key, value)


class ParticlePreview(QWidget):
    def __init__(self, emitter, parent=None):
        super().__init__(parent)
        self.emitter = emitter
        self.setMinimumSize(380, 320)
        self.image = QImage()
        self.system = ParticleSystem(None)
        self.running = True
        self.clock = QElapsedTimer(); self.clock.start()
        self.timer = QTimer(self); self.timer.setInterval(16); self.timer.timeout.connect(self.tick); self.timer.start()

    def tick(self):
        delta = min(.05, self.clock.restart()/1000)
        if self.running: self.system._update_emitter(self.emitter, delta)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.fillRect(self.rect(), QColor('#141b23'))
        painter.setPen(QColor('#243240'))
        for x in range(0, self.width(), 32): painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 32): painter.drawLine(0, y, self.width(), y)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for i, pos in enumerate(self.emitter._positions):
            color, size = self.emitter.particle_style(i)
            x, y = float(pos[0])+self.width()/2, float(pos[1])+self.height()/2
            if not self.image.isNull():
                painter.save(); painter.setOpacity(color[3]/255)
                image = self.image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                tint = QPainter(image); tint.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
                tint.fillRect(image.rect(), QColor(*color[:3])); tint.end()
                painter.drawImage(QRectF(x-size, y-size, size*2, size*2), image); painter.restore()
            else:
                painter.setBrush(QColor(*color)); painter.drawEllipse(QRectF(x-size, y-size, size*2, size*2))
        painter.setPen(QColor('#a9bacb')); painter.drawText(12, 24, f'Частиц: {self.emitter.get_particle_count()} / {self.emitter.amount}')


class ParticleEditorDialog(QDialog):
    def __init__(self, emitter, project_dir='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Редактор частиц — '+emitter.name); self.resize(970, 700)
        self.project_dir = Path(project_dir or '.')
        self.preview_emitter = Particles2D()
        apply_particle_values(self.preview_emitter, particle_values(emitter))
        self.authored_emitting = emitter.emitting
        self.result_values = None
        root = QVBoxLayout(self)
        root.addWidget(QLabel('Изменения видны в предпросмотре. Объект сцены изменится после нажатия «Применить».'))
        toolbar = QHBoxLayout()
        self.presets = QComboBox(); self.presets.addItem('Выбрать заготовку…'); self.presets.addItems(PRESETS)
        self.presets.activated.connect(self.load_preset); toolbar.addWidget(self.presets)
        for title, callback in [('Загрузить эффект…', self.load_effect), ('Сохранить эффект…', self.save_effect)]:
            button = QPushButton(title); button.clicked.connect(callback); toolbar.addWidget(button)
        root.addLayout(toolbar)
        body = QHBoxLayout(); self.preview = ParticlePreview(self.preview_emitter); body.addWidget(self.preview, 1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); panel = QWidget(); form = QFormLayout(panel); scroll.setWidget(panel); body.addWidget(scroll)
        self.controls = {}
        labels = {'amount':'Количество', 'lifetime':'Жизнь, с', 'speed':'Скорость', 'spread':'Разброс, °',
                  'particle_size':'Начальный радиус', 'end_size_ratio':'Конечный размер ×', 'one_shot':'Один выброс',
                  'color':'Начальный цвет', 'end_color':'Конечный цвет', 'emitting':'Эмиссия', 'rotation':'Направление, °'}
        for key in ['amount','lifetime','speed','spread','rotation','particle_size','end_size_ratio','one_shot','emitting']:
            spec = self.preview_emitter.get_exported_properties()[key]
            if spec['type'] == 'bool':
                control = QCheckBox(); control.toggled.connect(lambda value,k=key:self.change(k,value))
            else:
                control = QSpinBox() if spec['type'] == 'int' else QDoubleSpinBox()
                control.setRange(spec.get('min', -360), spec.get('max', 360)); control.setSingleStep(spec.get('step',1))
                control.valueChanged.connect(lambda value,k=key:self.change(k,value))
            self.controls[key] = control; form.addRow(labels[key], control)
        for axis in ('x','y'):
            control = QDoubleSpinBox(); control.setRange(-100000,100000)
            control.valueChanged.connect(lambda value,a=axis:self.gravity_changed(a,value))
            self.controls['gravity_'+axis] = control; form.addRow('Ускорение '+axis.upper(),control)
        for key in ('color','end_color'):
            control = QPushButton(); control.clicked.connect(lambda checked=False,k=key:self.choose_color(k))
            self.controls[key] = control; form.addRow(labels[key],control)
        self.texture = QLineEdit(); self.texture.editingFinished.connect(self.texture_changed)
        form.addRow('Текстура',self.texture)
        browse = QPushButton('Выбрать текстуру…'); browse.clicked.connect(self.choose_texture); form.addRow(browse)
        root.addLayout(body,1)
        actions = QHBoxLayout()
        restart = QPushButton('Перезапустить'); restart.clicked.connect(self.preview_emitter.restart)
        pause = QPushButton('Пауза / продолжить'); pause.clicked.connect(lambda:self.set_running(not self.preview.running))
        actions.addWidget(restart); actions.addWidget(pause); root.addLayout(actions)
        buttons = QDialogButtonBox(); buttons.addButton('Применить',QDialogButtonBox.ButtonRole.AcceptRole); buttons.addButton('Отмена',QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.apply); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.finished.connect(lambda _:self.preview.timer.stop())
        self.refresh_controls()

    def refresh_controls(self):
        for key,control in self.controls.items():
            control.blockSignals(True)
            if key.startswith('gravity_'): control.setValue(getattr(self.preview_emitter.gravity,key[-1]))
            elif key in ('color','end_color'):
                color = QColor(*getattr(self.preview_emitter,key)); control.setText(color.name(QColor.NameFormat.HexArgb))
                text='#111111' if .2126*color.red()+.7152*color.green()+.0722*color.blue()>140 else '#ffffff'
                control.setStyleSheet('background:'+color.name()+'; color:'+text+';')
            elif isinstance(control,QCheckBox): control.setChecked(self.authored_emitting if key=='emitting' else getattr(self.preview_emitter,key))
            else: control.setValue(getattr(self.preview_emitter,key))
            control.blockSignals(False)
        self.texture.setText(self.preview_emitter.texture_path); self.refresh_texture()

    def change(self,key,value):
        if key=='emitting': self.authored_emitting=value
        self.preview_emitter.set(key,value); self.preview_emitter.restart()
        self.preview_emitter.emitting=self.authored_emitting
    def gravity_changed(self,axis,value): setattr(self.preview_emitter.gravity,axis,value)
    def set_running(self,value): self.preview.running=value; self.preview.clock.restart()

    def choose_color(self,key):
        color=QColorDialog.getColor(QColor(*getattr(self.preview_emitter,key)),self,'Цвет',QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid(): self.change(key,color.getRgb()); self.refresh_controls()

    def refresh_texture(self):
        value = self.preview_emitter.texture_path.replace('res://','',1)
        path = Path(value); path = path if path.is_absolute() else self.project_dir/path
        self.preview.image = QImage(str(path)) if value else QImage()

    def texture_changed(self): self.preview_emitter.texture_path=self.texture.text().strip(); self.refresh_texture()
    def choose_texture(self):
        path,_=QFileDialog.getOpenFileName(self,'Текстура',str(self.project_dir),'Images (*.png *.jpg *.bmp *.webp)')
        if path:
            chosen=Path(path)
            try: path=chosen.relative_to(self.project_dir.resolve()).as_posix()
            except ValueError: pass
            self.texture.setText(path); self.texture_changed()

    def load_preset(self,index):
        if index<=0: return
        base=particle_values(Particles2D()); base.update(PRESETS[self.presets.itemText(index)])
        apply_particle_values(self.preview_emitter,base); self.authored_emitting=base['emitting']
        self.preview_emitter.restart(); self.preview_emitter.emitting=self.authored_emitting; self.refresh_controls()

    def save_effect(self):
        path,_=QFileDialog.getSaveFileName(self,'Сохранить эффект',str(self.project_dir/'assets'),'Cloud Particles (*.particles)')
        if path:
            if not path.endswith('.particles'): path+='.particles'
            try: Path(path).write_text(json.dumps({'version':1,'particles':self.authored_values()},ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error: QMessageBox.warning(self,'Эффект',str(error))

    def load_effect(self):
        path,_=QFileDialog.getOpenFileName(self,'Открыть эффект',str(self.project_dir),'Cloud Particles (*.particles)')
        if path:
            try:
                data=json.loads(Path(path).read_text(encoding='utf-8')); apply_particle_values(self.preview_emitter,data['particles'])
                self.authored_emitting=data['particles'].get('emitting',True)
                self.preview_emitter.restart(); self.preview_emitter.emitting=self.authored_emitting; self.refresh_controls()
            except (OSError,ValueError,TypeError,KeyError) as error: QMessageBox.warning(self,'Эффект',str(error))

    def apply(self):
        self.texture_changed()
        if self.preview_emitter.texture_path and self.preview.image.isNull():
            QMessageBox.warning(self,'Текстура','Изображение не найдено или не читается. Выберите другой файл.'); return
        self.result_values=self.authored_values(); self.accept()

    def authored_values(self):
        values=particle_values(self.preview_emitter); values['emitting']=self.authored_emitting
        return values
