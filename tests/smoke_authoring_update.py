import os
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
from PyQt6.QtWidgets import QApplication
from unittest.mock import patch
from editor.pixel_studio import PixelStudio
from editor.tile_palette import TileGrid
from editor.main_window import MainWindow
from engine.core.scene import Scene
from engine.nodes.game_object import GameObject
from engine.nodes.post_process import PostProcess
from engine.systems.post_process import PostProcessSystem
from engine.systems.light_system import LightSystem
from engine.core.scene_tree import SceneTree
from engine.nodes.light2d import Light2D,CanvasModulate
import pygame
app=QApplication([])
studio=PixelStudio('.');studio.duplicate();assert len(studio.frames)==2;studio.delete();assert len(studio.frames)==1;studio.undo();assert len(studio.frames)==2;studio.close()
grid=TileGrid();grid.resize(168,80);grid.set_tiles(list(range(200)),{});assert grid.minimumHeight()>=2100
window=MainWindow();window.save_layout=lambda:None;window.current_scene=Scene('Empty',GameObject())
with patch('editor.main_window.QMessageBox.warning') as warning:
    window.play_game();assert warning.called;assert not window.viewport.is_playing
window.current_scene=None;window.close()
pygame.init();pygame.display.set_mode((1,1));surface=pygame.Surface((32,32));surface.fill((0,0,0))
root=GameObject();light=Light2D();light.radius=32;root.add_child(light);tree=SceneTree();tree.current_scene=Scene('Light',root)
LightSystem(tree).render(surface);assert surface.get_at((0,0))[:3]==(0,0,0),'light must not wash out black pixels'
post=PostProcess();post.exposure=1;root.add_child(post);surface.fill((50,50,50));system=PostProcessSystem(tree);system.apply(surface);assert 98<=surface.get_at((10,10)).r<=102
print('PASS: pixel frames, palette scrolling, camera gate, albedo lighting and exposure')
