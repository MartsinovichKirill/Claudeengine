import os
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['CLOUDENGINE_CONFIG_DIR']=os.path.abspath('build/palette-test-settings')
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import tempfile
import unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from editor.tile_palette import TilePalette
from editor.scene_validation import validate_scene
from engine.core.scene import Scene
from engine.nodes.game_object import GameObject
from engine.nodes.camera2d import Camera2D
from engine.nodes.tilemap import TileMap
from engine.components.behaviour import ScriptBehaviour

class ValidationTests(unittest.TestCase):
    def test_missing_camera(self):
        self.assertTrue(any('Camera2D' in i.message for i in validate_scene(Scene(), '.')))

    def test_resources_and_script_syntax_without_execution(self):
        with tempfile.TemporaryDirectory() as root:
            scene=Scene();camera=Camera2D();camera.enabled=True;scene.root.add_child(camera)
            node=GameObject('Player');scene.root.add_child(node)
            script=ScriptBehaviour();node.add_component(script);script.script_path='bad.py'
            self.assertTrue(any(i.node is node and i.path.endswith('bad.py') for i in validate_scene(scene,root)))
            Path(root,'bad.py').write_text('if :',encoding='utf-8')
            self.assertTrue(any('invalid syntax' in i.message for i in validate_scene(scene,root)))
            Path(root,'bad.py').write_text("raise RuntimeError('must never execute')",encoding='utf-8')
            self.assertEqual(validate_scene(scene,root),[])

class PaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def test_filters_and_persisted_favorites(self):
        tilemap=TileMap('RegressionPalette')
        tilemap._tiles={0:None,1:None,2:None}
        tilemap.tile_sources={0:'grass.png',1:'stone.png',2:'water.png'}
        tilemap.tile_collisions={1:True}
        panel=TilePalette();panel.set_tilemap(tilemap)
        panel.search.setText('stone');self.assertEqual(panel.grid.ids,[1])
        panel.search.clear();panel.category.setCurrentIndex(1);self.assertEqual(panel.grid.ids,[1])
        panel.category.setCurrentIndex(2);self.assertEqual(panel.grid.ids,[0,2])
        panel.category.setCurrentIndex(0);panel._on_tile_picked(2);panel.favorite.setChecked(True)
        panel.category.setCurrentIndex(3);self.assertIn(2,panel.grid.ids)
        other=TilePalette();other.set_tilemap(tilemap);other.category.setCurrentIndex(3);self.assertIn(2,other.grid.ids)
        panel.favorite.setChecked(False)
        self.assertNotIn(2,panel.grid.ids)
        panel.close();other.close()

if __name__=='__main__':unittest.main()
