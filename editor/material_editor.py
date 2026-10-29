"""Live material authoring; edits are only written on Save."""
import json
import time
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QPlainTextEdit, QColorDialog, QMessageBox)
from engine.resources.material import Material
from engine.resources.prefab import resource_path


class MaterialEditor(QDialog):
    def __init__(self, project_dir, path='', parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.path = path
        self.setWindowTitle('Материал — живой предпросмотр')
        self.resize(820, 720)
        material = Material.load(path) if path and Path(path).exists() else Material()
        self.color = list(material.color)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.texture = QLineEdit(material.texture); self.shader = QLineEdit(material.shader)
        for title, field, pattern in (('Текстура', self.texture, 'Изображения (*.png *.jpg *.bmp *.webp)'),
                                      ('Шейдер', self.shader, 'Cloud Shader (*.shader)')):
            row = QHBoxLayout(); row.addWidget(field)
            button = QPushButton('Выбрать…'); row.addWidget(button)
            button.clicked.connect(lambda checked=False, f=field, p=pattern: self.choose(f, p))
            form.addRow(title, row)
        tint = QPushButton('Выбрать цвет и прозрачность…'); tint.clicked.connect(self.choose_color)
        form.addRow('Цвет', tint)
        layout.addLayout(form)
        self.parameters = QPlainTextEdit(json.dumps(material.parameters, ensure_ascii=False, indent=2))
        self.parameters.setMaximumHeight(150)
        layout.addWidget(QLabel('Параметры шейдера (JSON)')); layout.addWidget(self.parameters)
        layout.addWidget(QLabel('fragment(rgb, uv, time, parameters) — параметры доступны шейдеру. Поддерживается и прежняя сигнатура с 3 аргументами.'))
        self.preview = QLabel(); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(260); layout.addWidget(self.preview, 1)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout()
        save = QPushButton('Сохранить материал'); save.clicked.connect(self.save)
        apply = QPushButton('Назначить выбранному объекту'); apply.clicked.connect(self.assign)
        row.addWidget(save); row.addWidget(apply); layout.addLayout(row)
        self.timer = QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.render_preview)
        self.timer.start(); self.render_preview()

    def choose(self, field, pattern):
        path, _ = QFileDialog.getOpenFileName(self, 'Ресурс', self.project_dir, pattern)
        if path:
            try:
                field.setText(resource_path(self.project_dir, path).relative_to(Path(self.project_dir).resolve()).as_posix())
            except ValueError as exc:
                QMessageBox.warning(self, 'Ресурс', str(exc))

    def choose_color(self):
        from PyQt6.QtGui import QColor
        color = QColorDialog.getColor(QColor(*self.color), self, 'Цвет', QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.color = list(color.getRgb())

    def material(self):
        return Material.from_dict({'texture': self.texture.text(), 'shader': self.shader.text(),
                                  'color': self.color, 'parameters': json.loads(self.parameters.toPlainText() or '{}')})

    def render_preview(self):
        try:
            import pygame
            material = self.material()
            if material.texture:
                source = pygame.image.load(str(resource_path(self.project_dir, material.texture)))
            else:
                source = pygame.Surface((192, 192), pygame.SRCALPHA); source.fill((235, 235, 235, 255))
            source = pygame.transform.smoothscale(source, (256, 256))
            result = material.render(source, self.project_dir, time.monotonic())
            background = pygame.Surface((256, 256))
            for x in range(0, 256, 16):
                for y in range(0, 256, 16):
                    pygame.draw.rect(background, (55, 65, 78) if (x // 16 + y // 16) % 2 else (35, 44, 56), (x, y, 16, 16))
            background.blit(result, (0, 0))
            raw = pygame.image.tobytes(background, 'RGBA')
            self.preview.setPixmap(QPixmap.fromImage(QImage(raw, 256, 256, QImage.Format.Format_RGBA8888).copy()))
            self.status.setText('Предпросмотр обновляется · изменения ещё не сохранены')
        except Exception as exc:
            self.status.setText('Ошибка материала: ' + str(exc))

    def save(self):
        try:
            material = self.material()
            if material.shader:
                resource_path(self.project_dir, material.shader)
            if material.texture:
                resource_path(self.project_dir, material.texture)
            if not self.path:
                self.path, _ = QFileDialog.getSaveFileName(self, 'Материал', str(Path(self.project_dir) / 'assets' / 'New.material'), 'Cloud Material (*.material)')
            if not self.path:
                return False
            self.path = str(resource_path(self.project_dir, self.path))
            material.save(self.path)
            if hasattr(self.parent(), 'assets'):
                self.parent().assets.refresh()
            self.status.setText('Материал сохранён: ' + self.path)
            return True
        except Exception as exc:
            QMessageBox.warning(self, 'Материал', str(exc)); return False

    def assign(self):
        window = self.parent()
        node = window.get_selected_node() if hasattr(window, 'get_selected_node') else None
        renderer = node.get_component('SpriteRenderer') if node else None
        if renderer is None:
            QMessageBox.information(self, 'Материал', 'Выберите объект с компонентом SpriteRenderer.'); return
        if self.save():
            from editor.undo_stack import ComponentPropertyCommand
            relative = Path(self.path).relative_to(Path(self.project_dir).resolve()).as_posix()
            window.undo_stack.execute(ComponentPropertyCommand(renderer, 'material_path', renderer.material_path, relative))
            window.inspector.refresh()
