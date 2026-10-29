import os,io,tempfile,time
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextCursor
import pygame
pygame.init();pygame.display.set_mode((1,1));app=QApplication([])
from engine.resources.asset_manager import AssetManager
from engine.nodes.game_object import GameObject
from engine.nodes.sprite2d import Sprite2D
from engine.nodes.camera2d import Camera2D
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.systems.render_system import RenderSystem
from engine.math.vector2 import Vector2
from editor.cloud_code_edit import CloudCodeEdit
from editor.workspace_tools import symbol_hits
from engine.components.ui_layout import arrange_tree
from engine.nodes.canvas_layer import CanvasLayer
from engine.nodes.button import Button
root_path=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root_path/'build') as temporary:
    directory=Path(temporary);texture=pygame.Surface((10,10));texture.fill((255,0,0));pygame.image.save(texture,str(directory/'a.png'))
    manager=AssetManager(temporary);assert manager.get_texture('a.png').get_at((0,0)).r==255
    texture.fill((0,255,0));pygame.image.save(texture,str(directory/'a.png'));os.utime(directory/'a.png',(time.time()+2,time.time()+2));manager._next_poll=0
    assert manager.poll_changes();assert manager.get_texture('a.png').get_at((0,0)).g==255
    root=GameObject();camera=Camera2D();root.add_child(camera)
    for x in range(3):
        node=Sprite2D();node.texture_path='a.png';node.position=Vector2(x*15,0);root.add_child(node)
    tree=SceneTree();tree.current_scene=Scene('Test',root);render=RenderSystem(tree,manager);render.prepare_scene(tree.current_scene);surface=pygame.Surface((100,100));render.render(surface)
    assert render.render_stats['sprite_batches']==1,render.render_stats
    (directory/'sample.cloud').write_text('let score = 2\nprint(score)\n# score\nlet name = "score"\n',encoding='utf-8')
    assert len(symbol_hits(directory,'score'))==2
code=CloudCodeEdit();code.setPlainText('script Test extends Behaviour:\n    on ready():\n        body = self.get_component("Rigidbody2D")\n        body.')
cursor=code.textCursor();cursor.movePosition(QTextCursor.MoveOperation.End);code.setTextCursor(cursor);assert 'gravity_scale' in code.symbols()
layer=CanvasLayer();layer.add_component('HorizontalLayout');a=Button();b=Button();layer.add_child(a);layer.add_child(b);arrange_tree(layer,Vector2(800,600));assert b.get_component('RectTransform').offset.x>a.get_component('RectTransform').offset.x
print('PASS: live texture reload, sprite batching, symbol token search, typed component completion, UI row layout')
