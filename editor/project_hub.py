"""Project creation and startup window."""
import json
import re
import shutil
import tempfile
from build_support import default_projects_dir, validate_name
from pathlib import Path
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QSpinBox, QCheckBox, QFrame)


def create_project(parent, name, template, *, width=1280, height=720, pixel_art=True):
    name = validate_name(name)
    if not str(parent).strip():
        raise ValueError('Выберите папку для проектов.')
    parent_path = Path(parent).expanduser().resolve()
    target = parent_path / name
    if target.exists():
        raise ValueError('Такая папка уже существует. Выберите другое имя.')
    try:
        parent_path.mkdir(parents=True, exist_ok=True)
        # Build in a private sibling directory. Failure leaves no half-created
        # project that prevents retrying the same name.
        with tempfile.TemporaryDirectory(prefix='.cloud-create-', dir=parent_path) as temporary:
            staging = Path(temporary) / 'project'
            staging.mkdir()
            if template == 'Платформер':
                source = Path(__file__).resolve().parents[1] / 'projects' / 'sample_project'
                shutil.copytree(source, staging, dirs_exist_ok=True)
                from editor.template_art import create_art
                create_art(staging / 'assets')
                config = json.loads((staging / 'project.json').read_text(encoding='utf-8'))
            else:
                config = {'main_scene': 'scenes/main.scene'}
                (staging / 'scenes').mkdir()
                (staging / 'scenes/main.scene').write_text(json.dumps({'scene': {'name': 'Main',
                    'root': {'type': 'GameObject', 'name': 'Main'}}}), encoding='utf-8')
            for folder in ('assets', 'scenes', 'scripts', 'shaders'):
                (staging / folder).mkdir(exist_ok=True)
            config['name'] = name
            config.setdefault('window', {}).update(width=int(width), height=int(height), title=name)
            config.setdefault('render', {})['pixel_art'] = bool(pixel_art)
            scene_path = (staging / config['main_scene']).resolve()
            if not scene_path.is_relative_to(staging.resolve()):
                raise ValueError('Стартовая сцена должна находиться внутри проекта.')
            scene = json.loads(scene_path.read_text(encoding='utf-8'))
            def configure(node):
                if node.get('type') in ('Sprite2D', 'AnimatedSprite2D'):
                    node.setdefault('properties', {})['pixel_art'] = bool(pixel_art)
                for child in node.get('children', []):
                    configure(child)
            configure(scene['scene']['root'])
            scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding='utf-8')
            (staging / 'project.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
            if template == 'Контроллер игрока 2D':
                from editor.template_library import install_player_template
                demo = install_player_template(staging)
                config = json.loads((staging / 'project.json').read_text(encoding='utf-8'))
                config['main_scene'] = demo.relative_to(staging).as_posix()
                (staging / 'project.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
            if target.exists():
                raise ValueError('Такая папка уже существует. Выберите другое имя.')
            staging.rename(target)
    except PermissionError as exc:
        raise PermissionError(f'Нет прав на запись в папку «{parent_path}». Выберите другую папку кнопкой «Выбрать папку».') from exc
    return str(target)


def recent_projects():
    store = QSettings('CloudEngine', 'Hub')
    legacy = store.value('recent', [], type=list)
    try:
        data = json.loads((default_projects_dir().parent / 'recent-projects.json').read_text(encoding='utf-8'))
        if isinstance(data, list):
            return list(dict.fromkeys([p for p in data + legacy if isinstance(p, str)]))
    except (OSError, ValueError):
        pass
    return legacy


def accessible_project(path):
    try:
        return Path(path, 'project.json').is_file()
    except (OSError, ValueError, TypeError):
        return False


def remember_project(path):
    path = str(Path(path).resolve())
    if not accessible_project(path):
        return
    store = QSettings('CloudEngine', 'Hub')
    recent = recent_projects()
    recent = [path] + [p for p in recent if str(Path(p).resolve()).casefold() != path.casefold()][:19]
    store.setValue('recent', recent)
    store.sync()
    folder = default_projects_dir().parent
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='.recent-', suffix='.json', dir=folder, delete=False) as output:
            json.dump(recent, output, ensure_ascii=False, indent=2)
            temporary = Path(output.name)
        temporary.replace(folder / 'recent-projects.json')
    except OSError:
        import logging
        logging.getLogger('cloudengine.hub').warning('Не удалось сохранить список недавних проектов', exc_info=True)


class ProjectHub(QDialog):
    def __init__(self):
        super().__init__()
        self.project_path = ''
        self.setWindowTitle('Cloud Hub — проекты')
        self.resize(1020, 690)
        self.setMinimumSize(880, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        header = QHBoxLayout()
        from editor.icons import get_icon
        mascot = QLabel()
        from PyQt6.QtGui import QPixmap, QIcon
        from PyQt6.QtCore import Qt
        icon_path = str(Path(__file__).resolve().parents[1] / 'assets' / 'engine_icon.png')
        self.setWindowIcon(QIcon(icon_path))
        mascot.setPixmap(QPixmap(icon_path).scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(mascot)
        title = QLabel('CLOUD ENGINE')
        title.setStyleSheet('font-size: 28px; font-weight: 700; color: #75b8ed;')
        header.addWidget(title); header.addStretch()
        language = QComboBox()
        language.addItems(['Русский', 'English'])
        from editor.localization import install
        from PyQt6.QtWidgets import QApplication
        localization = install(QApplication.instance())
        language.setCurrentIndex(1 if localization.language == 'en' else 0)
        language.currentIndexChanged.connect(lambda index: localization.set_language('en' if index else 'ru'))
        header.addWidget(language)
        layout.addLayout(header)
        subtitle=QLabel('Рабочее пространство для ваших идей')
        subtitle.setObjectName('SecondaryText'); layout.addWidget(subtitle)
        layout.addSpacing(16)
        columns=QHBoxLayout(); columns.setSpacing(20); layout.addLayout(columns,1)
        left=QFrame(); left.setObjectName('HubCard'); recent_layout=QVBoxLayout(left)
        recent_layout.setContentsMargins(20,20,20,20)
        title=QLabel('Последние проекты'); title.setObjectName('SectionTitle'); recent_layout.addWidget(title)
        hint=QLabel('Двойной щелчок — продолжить работу'); hint.setObjectName('SecondaryText'); recent_layout.addWidget(hint)
        self.recent=QListWidget(); self.store=QSettings('CloudEngine','Hub')
        for path in recent_projects():
            if accessible_project(path):
                item=QListWidgetItem(Path(path).name+'\n'+path)
                item.setData(Qt.ItemDataRole.UserRole,path); item.setIcon(get_icon('folder'))
                item.setToolTip(path); self.recent.addItem(item)
        self.recent.itemDoubleClicked.connect(lambda item:self.select(item.data(Qt.ItemDataRole.UserRole)))
        recent_layout.addWidget(self.recent,1)
        if not self.recent.count():
            empty=QLabel('Здесь появятся проекты, которые вы открывали.'); empty.setWordWrap(True)
            empty.setObjectName('SecondaryText'); recent_layout.addWidget(empty)
        existing=QPushButton('Открыть существующий проект…'); existing.setIcon(get_icon('folder'))
        existing.clicked.connect(self.open_existing); recent_layout.addWidget(existing)
        columns.addWidget(left,1)
        right=QFrame(); right.setObjectName('HubCard'); create_layout=QVBoxLayout(right)
        create_layout.setContentsMargins(22,20,22,20); create_layout.setSpacing(10)
        title=QLabel('Новый проект'); title.setObjectName('SectionTitle'); create_layout.addWidget(title)
        self.name=QLineEdit('My Game'); self.name.setPlaceholderText('Название проекта')
        self.folder=QLineEdit(str(default_projects_dir()))
        create_layout.addWidget(QLabel('Название')); create_layout.addWidget(self.name)
        self.template = QComboBox(); self.template.addItems(['Пустой 2D', 'Контроллер игрока 2D'])
        create_layout.addWidget(QLabel('Шаблон')); create_layout.addWidget(self.template)
        create_layout.addWidget(QLabel('Папка проектов'))
        folder_row=QHBoxLayout(); folder_row.addWidget(self.folder,1)
        browse=QPushButton('…'); browse.setMaximumWidth(42); browse.clicked.connect(self.browse)
        folder_row.addWidget(browse); create_layout.addLayout(folder_row)
        create_layout.addSpacing(8)
        settings_row=QHBoxLayout(); self.window_width=QSpinBox(); self.window_height=QSpinBox()
        for label,control,value in (('Ширина',self.window_width,1280),('Высота',self.window_height,720)):
            control.setRange(320,7680); control.setValue(value)
            column=QVBoxLayout(); column.addWidget(QLabel(label)); column.addWidget(control); settings_row.addLayout(column)
        create_layout.addLayout(settings_row)
        structure=QLabel('assets  /  scenes  /  scripts  /  shaders'); structure.setObjectName('SecondaryText')
        structure.setWordWrap(True); create_layout.addWidget(structure)
        create_layout.addStretch()
        create=QPushButton('Создать проект  →'); create.setProperty('primary',True)
        create.clicked.connect(self.create); create_layout.addWidget(create)
        columns.addWidget(right,1)
        footer=QHBoxLayout(); footer.addStretch()
        plugins=QPushButton('Плагины'); plugins.setIcon(get_icon('component')); plugins.clicked.connect(self.open_plugins)
        footer.addWidget(plugins); layout.addLayout(footer)
        templates=QPushButton('Шаблоны'); templates.setIcon(get_icon('folder'))
        templates.clicked.connect(self.open_templates); footer.addWidget(templates)

    def open_templates(self):
        from editor.template_dialog import TemplateDialog
        TemplateDialog(self).exec()

    def open_plugins(self):
        from editor.plugin_dialog import PluginDialog
        PluginDialog(self).exec()

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, 'Расположение проектов', self.folder.text())
        if path: self.folder.setText(path)

    def open_existing(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Открыть проект', '', 'Cloud Project (project.json)')
        if path: self.select(str(Path(path).parent))

    def create(self):
        try:
            path = create_project(self.folder.text(), self.name.text(), self.template.currentText(),
                                  width=self.window_width.value(), height=self.window_height.value(),
                                  pixel_art=True)
            self.select(path)
        except PermissionError as exc:
            QMessageBox.warning(self, 'Выберите доступную папку', str(exc))
            self.browse()
        except Exception as exc:
            QMessageBox.warning(self, 'Не удалось создать проект', str(exc))

    def select(self, path):
        try:
            path = str(Path(path).resolve())
            with open(Path(path, 'project.json'), encoding='utf-8') as source:
                config = json.load(source)
            if not isinstance(config, dict):
                raise ValueError('project.json должен содержать настройки проекта.')
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Не удалось открыть проект', str(exc))
            return
        self.project_path = path
        remember_project(path)
        self.accept()
