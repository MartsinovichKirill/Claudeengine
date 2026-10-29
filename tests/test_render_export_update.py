import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import tempfile,unittest,zipfile,sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pygame
from engine.math.vector2 import Vector2
from engine.nodes.camera2d import Camera2D
from engine.nodes.tilemap import TileMap
from engine.nodes.game_object import GameObject
from engine.nodes.post_process import PostProcess
from engine.systems.post_process import PostProcessSystem
from engine.resources.scene_serializer import SceneSerializer
from build_game import validate_target,prepare_source,game_output

class RenderExportTests(unittest.TestCase):
    def test_camera_dead_zone(self):
        c=Camera2D();c.screen_size=Vector2(100,100);c.drag_h_enabled=True;c.drag_left_margin=c.drag_right_margin=.2;c._view_center=Vector2()
        self.assertAlmostEqual(c._apply_drag(Vector2(5,0)).x,0)
        self.assertAlmostEqual(c._apply_drag(Vector2(30,0)).x,20)
        c.pixel_snap=True;c.zoom=2;c._view_center=Vector2(.31,.31)
        self.assertAlmostEqual(c.get_center().x,.5)
    def test_tile_components_and_roundtrip(self):
        t=TileMap();t.set_cell(0,0,1,True)
        collider=t.add_component('TileMapCollider2D');collider.collision_layer=4
        self.assertEqual(t.physics_body().collision_layer,4)
        collider.enabled=False;self.assertIsNone(t.physics_body());collider.enabled=True
        tint=t.add_component('TileMapTint');tint.color=(100,255,255,255)
        clone=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(t))
        self.assertEqual(clone.get_component('TileMapCollider2D').collision_layer,4)
        self.assertEqual(list(clone.get_component('TileMapTint').color),[100,255,255,255])
        with self.assertRaises(ValueError):GameObject().add_component('TileMapTint')
    def test_postprocess_component(self):
        from engine.core.scene import Scene
        from types import SimpleNamespace
        t=TileMap();volume=t.add_component('PostProcessVolume');volume.temperature=-.5
        scene=Scene(root=t);system=PostProcessSystem(SimpleNamespace(current_scene=scene))
        self.assertAlmostEqual(system.find_node().temperature,-.5)
        self.assertIn('temperature',system.find_node().active_effects())
    def test_chromatic_edges_do_not_wrap(self):
        arr=np.zeros((8,4,3),np.float32);arr[-1,:,0]=255
        result=PostProcessSystem()._fx_chromatic(arr,2,PostProcess(),8,4)
        self.assertEqual(float(result[0,:,0].max()),0)
    def test_bloom_and_temperature(self):
        arr=np.zeros((24,24,3),np.float32);arr[10:14,10:14]=255
        node=PostProcess();sys=PostProcessSystem();out=sys._fx_bloom(arr,1,node,24,24)
        self.assertTrue(np.isfinite(out).all());self.assertGreater(out.sum(),arr.sum())
        warm=sys._fx_temperature(np.ones((2,2,3))*100,1,node,2,2)
        self.assertGreater(warm[0,0,0],warm[0,0,2])
    def test_platform_validation(self):
        with patch.object(sys,'platform','win32'):
            self.assertEqual(validate_target('windows'),'windows')
            with self.assertRaises(ValueError):validate_target('macos')
        self.assertEqual(game_output('/out','Game','macos').name,'Game.app')
    def test_source_kit(self):
        with tempfile.TemporaryDirectory(dir='build') as temp:
            root=Path(temp);project=root/'source';project.mkdir();(project/'project.json').write_text('{}')
            (project/'assets').mkdir();(project/'assets'/'example.txt').write_text('asset')
            prepare_source(project,root/'output','TestGame','macos')
            with zipfile.ZipFile(root/'output'/'TestGame-macos-source.zip') as z:
                self.assertIn('engine/components/render_tools.py',z.namelist())
                self.assertIn('project/assets/example.txt',z.namelist())
                self.assertIn('--target macos',z.read('BUILD.txt').decode())

if __name__=='__main__':unittest.main()
