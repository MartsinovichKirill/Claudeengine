"""Template browser shared by the hub and editor."""
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
from editor.template_library import install_player_template


class TemplateDialog(QDialog):
    def __init__(self, parent=None, project=''):
        super().__init__(parent)
        self.project, self.installed_scene = project, None
        self.setWindowTitle('Шаблоны')
        self.resize(520, 340)
        box = QVBoxLayout(self)
        title = QLabel('Контроллер игрока 2D')
        title.setStyleSheet('font-size:22px;font-weight:600')
        box.addWidget(title)
        details = QLabel('Готовая сцена: персонаж, платформы, параллакс и плавная камера.\n\n'
                         'A / D или стрелки — ходьба\nShift — бег\nПробел — прыжок\nR — на старт\n\n'
                         '36 кадров: Idle, Walk, Run, Jump.\nШаблон доступен без интернета.')
        details.setWordWrap(True)
        box.addWidget(details)
        box.addStretch()
        add = QPushButton('Добавить в проект…')
        add.clicked.connect(self.install)
        box.addWidget(add)
        export = QPushButton('Сохранить шаблон ZIP…'); export.clicked.connect(self.export)
        box.addWidget(export)

    def export(self):
        from editor.template_library import export_player_template
        filename, _ = QFileDialog.getSaveFileName(self, 'Сохранить шаблон', 'PlayerController2D.zip', 'ZIP (*.zip)')
        if not filename: return
        try:
            export_player_template(filename)
            QMessageBox.information(self, 'Шаблон сохранён', 'Распакуйте ZIP и откройте project.json через хаб.')
        except Exception as exc:
            QMessageBox.warning(self, 'Не удалось сохранить шаблон', str(exc))

    def install(self):
        project = self.project
        if not project:
            filename, _ = QFileDialog.getOpenFileName(self, 'Выберите проект', '', 'Cloud Project (project.json)')
            if not filename: return
            project = str(Path(filename).parent)
        try:
            self.installed_scene = install_player_template(project)
            QMessageBox.information(self, 'Шаблон добавлен', 'Создана сцена:\n' + str(self.installed_scene))
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, 'Не удалось добавить шаблон', str(exc))
