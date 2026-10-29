"""Named frame clips, reordering, FPS/loop controls and live preview."""
import copy
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QDoubleSpinBox, QCheckBox, QListWidget, QListWidgetItem, QLabel, QFileDialog,
    QInputDialog, QMessageBox, QDialogButtonBox, QAbstractItemView)


class SpriteFramesEditor(QDialog):
    def __init__(self, node, project, parent=None):
        super().__init__(parent)
        self.node, self.project = node, Path(project).resolve()
        self.clips = copy.deepcopy(node.animations)
        self.active = None
        self.index = 0
        self.setWindowTitle('AnimatedSprite2D — анимации')
        self.resize(740, 560)
        box = QVBoxLayout(self)
        row = QHBoxLayout()
        self.names = QComboBox(); row.addWidget(self.names, 1)
        add = QPushButton('Новая'); add.clicked.connect(self.add_clip); row.addWidget(add)
        delete = QPushButton('Удалить'); delete.clicked.connect(self.remove_clip); row.addWidget(delete)
        box.addLayout(row)
        settings = QHBoxLayout()
        self.fps = QDoubleSpinBox(); self.fps.setRange(.1,120); self.fps.setValue(10); settings.addWidget(QLabel('Кадров/с')); settings.addWidget(self.fps)
        self.loop = QCheckBox('Зациклить'); self.loop.setChecked(True); settings.addWidget(self.loop)
        self.preview_play = QCheckBox('Предпросмотр'); self.preview_play.setChecked(True); settings.addWidget(self.preview_play)
        box.addLayout(settings)
        content = QHBoxLayout()
        self.frames = QListWidget(); self.frames.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.frames.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.frames.currentRowChanged.connect(lambda row: setattr(self, 'index', max(0,row)))
        content.addWidget(self.frames, 1)
        self.preview = QLabel(); self.preview.setMinimumSize(280,280); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet('background:#17212c;border:1px solid #405060')
        content.addWidget(self.preview, 1); box.addLayout(content, 1)
        help_text = QLabel('Кадры можно перетаскивать для изменения порядка. Изображения должны находиться внутри проекта.')
        help_text.setWordWrap(True); box.addWidget(help_text)
        row = QHBoxLayout()
        imp = QPushButton('Добавить PNG…'); imp.clicked.connect(self.import_frames); row.addWidget(imp)
        remove = QPushButton('Убрать кадры'); remove.clicked.connect(self.remove_frames); row.addWidget(remove)
        hitboxes=QPushButton('Хитбоксы по кадрам…');hitboxes.clicked.connect(self.edit_hitboxes);row.addWidget(hitboxes)
        box.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); box.addWidget(buttons)
        self.names.currentTextChanged.connect(self.select_clip)
        self.names.addItems(self.clips)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(100)
        if node.animation in self.clips: self.names.setCurrentText(node.animation)

    def flush(self):
        if self.active in self.clips:
            spec=self.clips[self.active]
            old=list(spec.get('frames',[]))
            new=[self.frames.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.frames.count())]
            # Follow each frame occurrence when sorting/removing PNGs.
            available=list(enumerate(old));mapped={}
            for index,path in enumerate(new):
                match=next(((i,p) for i,p in available if p==path),None)
                if match:
                    available.remove(match)
                    if str(match[0]) in spec.get('hitboxes',{}):mapped[str(index)]=spec['hitboxes'][str(match[0])]
            spec.update(frames=new,fps=self.fps.value(),loop=self.loop.isChecked(),hitboxes=mapped)

    def edit_hitboxes(self):
        self.flush()
        if not self.active or not self.clips[self.active].get('frames'):return
        self.preview_play.setChecked(False)
        from editor.hitbox_editor import HitboxEditor
        dialog=HitboxEditor(self.clips[self.active],self.project,self)
        if dialog.exec():self.clips[self.active]=dialog.result_clip

    def select_clip(self, name):
        self.flush(); self.active = name; self.index = 0; self.frames.clear()
        spec = self.clips.get(name, {})
        self.fps.setValue(spec.get('fps', 10)); self.loop.setChecked(spec.get('loop', True))
        for path in spec.get('frames', []): self.append_frame(path)

    def append_frame(self, path):
        item = QListWidgetItem(path); item.setData(Qt.ItemDataRole.UserRole, path); self.frames.addItem(item)

    def add_clip(self):
        name, ok = QInputDialog.getText(self, 'Новая анимация', 'Имя')
        name = name.strip()
        if ok and name and name not in self.clips:
            self.clips[name] = {'frames':[], 'fps':10, 'loop':True}
            self.names.addItem(name); self.names.setCurrentText(name)

    def remove_clip(self):
        name = self.names.currentText(); self.active = None
        self.clips.pop(name, None); self.names.removeItem(self.names.currentIndex())

    def import_frames(self):
        if not self.active: return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Кадры анимации', str(self.project/'assets'), 'PNG (*.png)')
        for path in sorted(paths):
            file = Path(path).resolve()
            if not file.is_relative_to(self.project):
                QMessageBox.warning(self, 'Кадры', 'Сначала импортируйте изображения в папку assets проекта.'); return
            self.append_frame(file.relative_to(self.project).as_posix())

    def remove_frames(self):
        for item in self.frames.selectedItems(): self.frames.takeItem(self.frames.row(item))

    def tick(self):
        if not self.frames.count(): self.preview.clear(); return
        self.index = min(self.index, self.frames.count()-1)
        path = self.project / self.frames.item(self.index).data(Qt.ItemDataRole.UserRole)
        pixmap = QPixmap(str(path))
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
        self.timer.setInterval(max(8, round(1000/self.fps.value())))
        if self.preview_play.isChecked():
            self.index = (self.index+1) % self.frames.count() if self.loop.isChecked() else min(self.index+1,self.frames.count()-1)

    def save(self):
        self.flush()
        if any(not spec['frames'] for spec in self.clips.values()):
            QMessageBox.warning(self, 'Анимации', 'Добавьте кадры или удалите пустые анимации.'); return
        self.node.animations = copy.deepcopy(self.clips)
        self.node.animation = self.active or ''
        self.node._loaded_animation = None
        if not self.clips:
            self.node.frames = []
            self.node._frame_paths = []
            self.node.texture = None
        self.node._ensure_animation()
        self.accept()
