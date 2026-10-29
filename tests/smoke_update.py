import os
if not os.environ.get('CLOUD_NATIVE_SMOKE'):
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QLineEdit, QDoubleSpinBox
from PyQt6.QtCore import QTimer
from editor.theme import apply_theme
from editor.main_window import MainWindow
from editor.project_hub import ProjectHub
from editor.animator_editor import AnimatorEditor
from engine.nodes import GameObject
from engine.core.scene import Scene
from engine.resources.scene_serializer import SceneSerializer

root = Path(__file__).resolve().parents[1]
app = QApplication([]); apply_theme(app)
window = MainWindow(); window.save_layout = lambda: None
window.open_project(str(root / 'build/export-fixture/CloudDemo'))
node = GameObject('Hero')
node.add_component('SpriteRenderer').texture_path = 'assets/player.png'
node.add_component('Rigidbody2D')
node.add_component('BoxCollider2D')
animator = node.add_component('Animator')
window.current_scene.root.add_child(node)
window.viewport.bind_node_assets(node)
window.hierarchy.refresh(); window.hierarchy.select_node(node)
window.show(); app.processEvents()
window.inspector.refresh(); app.processEvents()
from PyQt6.QtTest import QTest
QTest.qWait(200)
assert len(window.plugin_host.loaded) == 10, window.plugin_host.errors
from editor.plugin_dialog import PluginDialog
plugins = PluginDialog(window, window.plugin_host)
assert plugins.list.count() == 10
plugins.show(); QTest.qWait(100)
plugins.grab().save(str(root / 'build/update-plugins.png'))
plugins.close()
assert window.inspector.findChildren(QDoubleSpinBox)
window.grab().save(str(root / 'build/update-editor.png'))
dialog = AnimatorEditor(animator, window); dialog.show(); app.processEvents()
dialog.grab().save(str(root / 'build/update-animator.png'))
dialog.accept_data(); assert dialog.result_data['states'] == {}
hub = ProjectHub(); hub.show(); app.processEvents()
hub.grab().save(str(root / 'build/update-hub.png'))
assert not hasattr(hub, 'template')
hub.close()
window.current_scene = None # Do not modify fixture on close.
window.close()
print('PASS: updated inspector, component controls, animator graph, hub, screenshots')
