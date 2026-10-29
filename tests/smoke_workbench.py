"""Exercise actual authoring dialogs and debugger pause/resume on disposable data."""
import os
if not os.environ.get('CLOUD_NATIVE_SMOKE'):
    os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from editor.theme import apply_theme
from editor.main_window import MainWindow
from editor.project_hub import create_project, ProjectHub
from editor.material_editor import MaterialEditor
from editor.ui_editor import UIEditor
from engine.nodes.canvas_layer import CanvasLayer
from engine.nodes.game_object import GameObject
from engine.resources.scene_serializer import SceneSerializer
from engine.components.registry import all_visible_components

ROOT=Path(__file__).resolve().parents[1]
app=QApplication([]); apply_theme(app)
with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
    project=Path(create_project(temporary,'Workbench','Пустой 2D'))
    window=MainWindow(); window.save_layout=lambda:None
    window.open_project(str(project)); window.show(); QTest.qWait(150)
    assert not hasattr(window.toolbar,'mode_3d')
    assert len(all_visible_components())>=100
    material=MaterialEditor(str(project),str(project/'assets'/'test.material'),window)
    material.color=[128,255,255,255]
    material.show(); QTest.qWait(150); material.render_preview()
    assert material.preview.pixmap() and not material.preview.pixmap().isNull(),material.status.text()
    assert material.save()
    material.grab().save(str(ROOT/'build/workbench-material.png'))
    material.close()
    ui=UIEditor(CanvasLayer('Interface'),window)
    ui.add('Button'); ui.change_anchor(1)
    ui.screen.setCurrentIndex(3); ui.rebuild()
    assert ui.selected.has_component('RectTransform')
    ui.show(); QTest.qWait(100)
    ui.grab().save(str(ROOT/'build/workbench-ui.png'))
    ui.accept_data()
    layer=SceneSerializer.node_from_dict(ui.result_data)
    window.current_scene.root.add_child(layer)
    node=GameObject('ScriptObject'); node.add_component('SpriteRenderer')
    script=project/'scripts'/'debug.cloud'
    script.write_text('script DebugExample extends Behaviour:\n    export amount: float = 2.0\n    on ready():\n        let value = self.amount\n        self.transform.position.x = value\n    on process(delta):\n        self.transform.position.y += delta\n',encoding='utf-8')
    component=node.add_component('ScriptBehaviour'); component.script_path='scripts/debug.cloud'
    window.current_scene.root.add_child(node)
    window.reload_scripts(); window.hierarchy.refresh(); window.hierarchy.select_node(node)
    debugger=window.debugger_panel.debugger
    debugger.toggle(script,4)
    original_pause=debugger.on_pause; hits=[]
    def pause(frame):
        hits.append(frame.f_lineno)
        QTimer.singleShot(150,lambda:window.debugger_panel.resume('over' if len(hits)==1 else 'continue'))
        original_pause(frame)
    debugger.on_pause=pause
    window.play_game()
    assert hits[:2]==[4,5],hits
    window.viewport._tick_game()
    assert window.viewport.is_playing
    window.stop_game()
    window.grab().save(str(ROOT/'build/workbench-editor.png'))
    hub=ProjectHub(); hub.show(); QTest.qWait(100)
    assert not hub.windowIcon().isNull()
    hub.grab().save(str(ROOT/'build/workbench-hub.png')); hub.close()
    window.current_scene=None; window.close()
print('PASS: material preview/save, visual UI anchors, 100+ catalog, icon, no 3D, actual Cloud breakpoint and stepping')
