"""Exercise all ten shipped tools against disposable project data."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox, QColorDialog, QDialog
from PyQt6.QtGui import QColor
from editor.main_window import MainWindow
from editor.project_hub import create_project
from editor.plugin_system import PluginContext
from editor.builtin_plugin_tools import activate
from engine.nodes import GameObject
from engine.math.vector2 import Vector2

root = Path(__file__).resolve().parents[1]
app = QApplication([])
with tempfile.TemporaryDirectory(dir=root / 'build') as directory:
    temporary = Path(directory)
    project = Path(create_project(temporary, 'PluginTest', 'Пустой 2D'))
    editor = MainWindow(); editor.save_layout = lambda: None
    editor.open_project(str(project)); editor.show(); app.processEvents()
    context = PluginContext(editor, editor.plugins_menu)
    hero = GameObject('Hero'); hero.position = Vector2(17, 45)
    renderer = hero.add_component('SpriteRenderer')
    editor.current_scene.root.add_child(hero)
    editor.hierarchy.refresh(); editor.hierarchy.select_node(hero)
    with patch.object(QMessageBox, 'information') as message:
        activate(context, 'validator'); activate(context, 'statistics')
        assert message.call_count == 2
    with patch.object(QInputDialog, 'getDouble', return_value=(32, True)):
        activate(context, 'grid')
    assert hero.position == Vector2(32, 32)
    editor.undo(); assert hero.position == Vector2(17, 45)
    with patch.object(QColorDialog, 'getColor', return_value=QColor(20, 30, 40)):
        activate(context, 'palette')
    assert renderer.color[:3] == (20, 30, 40)
    editor.undo()
    with patch.object(QInputDialog, 'getInt', return_value=(2, True)), patch.object(QInputDialog, 'getDouble', return_value=(64, True)):
        activate(context, 'array')
    assert len(editor.current_scene.root.get_children()) == 3
    editor.undo(); editor.undo()
    with patch.object(QInputDialog, 'getText', return_value=('Hero', True)):
        activate(context, 'find')
    assert editor.get_selected_node() is hero
    backup = temporary / 'backup.zip'
    with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(backup), '')):
        activate(context, 'backup')
    with zipfile.ZipFile(backup) as archive:
        assert 'project.json' in archive.namelist()
    with patch.object(QDialog, 'exec', return_value=QDialog.DialogCode.Accepted):
        activate(context, 'notes')
    assert (project / 'PROJECT_NOTES.md').exists()
    import pygame
    source = project / 'assets' / 'sprite.png'
    pygame.image.save(pygame.Surface((12, 16), pygame.SRCALPHA), str(source))
    atlas = temporary / 'atlas.png'
    with patch.object(QFileDialog, 'getOpenFileNames', return_value=([str(source), str(source)], '')), patch.object(QFileDialog, 'getSaveFileName', return_value=(str(atlas), '')):
        activate(context, 'atlas')
    assert atlas.exists() and len(json.loads(atlas.with_suffix('.atlas.json').read_text())['frames']) == 2
    screenshot = temporary / 'capture.png'
    editor.viewport._tick_editor()
    with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(screenshot), '')):
        activate(context, 'screenshot')
    assert screenshot.exists()
    editor.current_scene = None; editor.close()
print('PASS: all 10 bundled plugin tools, including files and Undo/Redo')
