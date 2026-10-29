import os
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
from PyQt6.QtWidgets import QApplication,QLabel
from PyQt6.QtTest import QTest
from editor.localization import install
from editor.main_window import MainWindow
from editor.tile_palette import TilePalette
from engine.nodes.tilemap import TileMap
import pygame
app=QApplication([]);loc=install(app);original=loc.language
window=MainWindow();window.save_layout=lambda:None
loc.set_language('en');app.processEvents()
assert window.toolbar.play_action.text()=='Play (F5)'
loc.set_language('ru');assert window.toolbar.play_action.text()=='Играть (F5)'
tiles=TileMap();tiles._tiles={0:pygame.Surface((8,8)),1:pygame.Surface((8,8))}
tiles.set_cell(0,0,0,False);tiles.set_cell(1,0,1,False)
window.palette.set_tilemap(tiles);window.palette.collision_check.setChecked(True)
assert tiles.cells[(0,0)]['collision']
window.palette._on_tile_picked(1);assert not window.palette.collision_check.isChecked()
window.palette._on_tile_picked(0);assert window.palette.collision_check.isChecked()
window.undo_stack.undo();assert not tiles.cells[(0,0)]['collision']
window.current_scene=None;window.close();loc.set_language(original)
print('PASS: language switch and tile-specific collision with undo')
