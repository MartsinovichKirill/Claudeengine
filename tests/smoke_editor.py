import os, sys, tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['SDL_VIDEODRIVER']='dummy'
sys.path.insert(0,str(Path('CloudEngine').resolve()))
from PyQt6.QtWidgets import QApplication
app=QApplication([])
from editor.theme import apply_theme
apply_theme(app)
from editor.project_hub import ProjectHub,create_project
hub=ProjectHub()
from editor.main_window import MainWindow
window=MainWindow()
with tempfile.TemporaryDirectory(dir="C:/Cloud") as d:
    p=create_project(d,'Smoke','Пустой 2D')
    window.open_project(p)
    Path(p,'scripts','actor.cloud').write_text('script Actor extends Node2D:\n    on ready():\n        let self.value = 42\n',encoding='utf-8')
    assert window.script_system.reload()==1
    actor=window.script_system.get_class_for('scripts/actor.cloud')()
    actor._ready()
    assert actor.value==42
window.resize(1400,900); window.show(); app.processEvents()
assert all(window.docks[name].isVisible() for name in ("Консоль", "Скрипт", "Инспектор"))
assert hub.window_width.value() == 1280
import pygame
pygame.init(); pygame.display.set_mode((1,1))
from engine.nodes.sprite2d import Sprite2D
sprite=Sprite2D(); texture=pygame.Surface((32,16),pygame.SRCALPHA)
texture.fill('red', (0,0,16,16));texture.fill('blue',(16,0,16,16))
sprite.set_texture(texture);sprite.hframes=2;sprite.frame=1
result,_=sprite._get_draw_surface(None)
assert result.get_size()==(16,16) and result.get_at((0,0)).b==255
assert sprite._get_draw_surface(None)[0] is result
print('PASS: hub, project, editor, Cloud Scripts, slicing, cache')
