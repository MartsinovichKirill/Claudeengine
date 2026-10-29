import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.nodes.game_object import GameObject
from engine.math.vector2 import Vector2
from engine.systems.audio_system import AudioSystem
from engine.systems.cutscenes import CutscenePlayer,validate_clip
from engine.resources.scene_serializer import SceneSerializer
from engine.resources import teamwork

ROOT=Path(__file__).resolve().parents[1]


class CinemaTests(unittest.TestCase):
    def folder(self):return tempfile.TemporaryDirectory(dir=ROOT/'build')
    def test_scene_load_is_deferred_and_preserves_shared_data(self):
        with self.folder() as tmp:
            root=Path(tmp);(root/'project.json').write_text('{}')
            Scene('second',GameObject()).save(str(root/'second.scene'))
            tree=SceneTree();tree.script_system=SimpleNamespace(project_dir=tmp)
            first=Scene('first',GameObject());tree.change_scene(first);tree.shared_data['hp']=3
            tree.load_scene('second.scene');self.assertIs(tree.current_scene,first)
            tree.flush_scene_change();self.assertEqual(tree.current_scene.name,'second');self.assertEqual(tree.shared_data['hp'],3)
            self.assertFalse(first.root.is_inside_tree())
    def test_failed_scene_load_does_not_exit_current_scene(self):
        with self.folder() as tmp:
            tree=SceneTree();tree.script_system=SimpleNamespace(project_dir=tmp);scene=Scene('A');tree.change_scene(scene)
            with self.assertRaises(ValueError):tree.load_scene('../escape.scene')
            self.assertIs(tree.current_scene,scene)
    def test_master_gain_not_applied_twice(self):
        audio=AudioSystem(SceneTree());audio.set_bus_volume('master',.5);audio.set_bus_volume('music',.4)
        self.assertEqual(audio.gain('master'),.5);self.assertAlmostEqual(audio.gain('music'),.2)
        audio.set_bus_mute('music');self.assertEqual(audio.gain('music'),0)
        audio.set_bus_mute('music',False);audio.set_bus_mute('master');self.assertEqual(audio.gain('ui'),0)
    def test_audio_fade_and_legacy_config(self):
        audio=AudioSystem(SceneTree({'audio':{'master':.3,'music':.8}}));self.assertEqual(audio.gain('master'),.3)
        audio.fade_bus('music',0,2);audio.update(1);self.assertAlmostEqual(audio.get_bus_volume('music'),.4)
        audio.update(1);self.assertEqual(audio.get_bus_volume('music'),0)
    def test_component_audio_respects_bus(self):
        obj=GameObject();component=obj.add_component('AudioSource');tree=SceneTree();audio=AudioSystem(tree);tree.audio_system=audio
        tree.change_scene(Scene('audio',obj));component.bus='music';component._sync();audio.set_bus_mute('music')
        component._player._channel=Mock();audio.update(.1)
        component._player._channel.set_volume.assert_called_with(0)
        tree._exit_scene(tree.current_scene)
    def clip(self):return {'tracks':[{'start':0,'duration':2,'target':'.','property':'position','from':[0,0],'to':[100,20],'ease':'smooth'}]}
    def test_cutscene_seek_and_restore(self):
        obj=GameObject();obj.position=Vector2(7,8);player=CutscenePlayer();player.bind(Scene('A',obj),self.clip())
        player.seek(1);self.assertEqual(obj.position,Vector2(50,10));player.stop(True);self.assertEqual(obj.position,Vector2(7,8))
    def test_invalid_cutscene_never_modifies_scene(self):
        data=self.clip();data['tracks'][0]['duration']=-1
        with self.assertRaises(ValueError):validate_clip(data)
        data=self.clip();data['tracks'][0]['to']=[1]
        with self.assertRaises(ValueError):validate_clip(data)
    def test_camera_component_switch(self):
        root=GameObject();a=GameObject('A');b=GameObject('B');root.add_child(a);root.add_child(b)
        ca=a.add_component('Camera2D');cb=b.add_component('Camera2D');tree=SceneTree();tree.change_scene(Scene('x',root));tree.set_camera('B')
        self.assertFalse(ca.enabled);self.assertTrue(cb.enabled)
    def test_camera_offset_and_lookahead_exports(self):
        from engine.nodes.camera2d import Camera2D
        camera=Camera2D();camera.offset=Vector2(20,30);self.assertEqual(camera.get_center(),Vector2(20,30))
        self.assertIn('look_ahead',camera.exported_properties)
    def test_external_scene_edit_is_not_overwritten(self):
        with self.folder() as tmp:
            path=Path(tmp)/'main.scene';Scene('A').save(str(path));scene=Scene.load(str(path));path.write_text('{"changed":true}')
            with self.assertRaises(RuntimeError):scene.save(str(path))
            self.assertEqual(path.read_text(),'{"changed":true}')
    def test_team_reservation_blocks_other_user(self):
        with self.folder() as tmp:
            root=Path(tmp);(root/'project.json').write_text('{}');scene=root/'main.scene';Scene().save(str(scene));teamwork.reserve(scene)
            with patch('engine.resources.teamwork.identity',return_value='other@machine'):
                with self.assertRaises(PermissionError):Scene().save(str(scene))
            teamwork.release(scene);self.assertFalse(teamwork.lock_path(scene).exists())
    def test_git_preparation_preserves_existing_rules(self):
        with self.folder() as tmp:
            root=Path(tmp);(root/'.gitignore').write_text('custom/\n');teamwork.prepare_project(root);teamwork.prepare_project(root)
            text=(root/'.gitignore').read_text();self.assertTrue(text.startswith('custom/'));self.assertEqual(text.count('# Cloud Engine'),1)
    def test_cone_light_has_direction(self):
        import pygame
        from engine.nodes.light2d import Light2D
        from engine.systems.light_system import LightSystem
        light=Light2D();light.radius=32;light.cone_angle=90;light.direction=0
        gradient=LightSystem(SceneTree())._gradient(light)
        self.assertGreater(sum(gradient.get_at((42,32))[:3]),sum(gradient.get_at((22,32))[:3]))
    def test_large_light_does_not_allocate_radius_sized_texture(self):
        import pygame
        from engine.nodes.light2d import Light2D
        from engine.nodes.camera2d import CameraState
        from engine.systems.light_system import LightSystem
        light=Light2D();light.radius=10000
        system=LightSystem(SceneTree());surface=pygame.Surface((96,64));surface.fill((0,0,0))
        camera=CameraState(Vector2(),20,Vector2(96,64))
        system._draw_light(surface,light,camera,[])
        self.assertGreater(sum(surface.get_at((48,32))[:3]),0)
        self.assertFalse(system._gradient_cache)

    def test_live_mixer_cancel_restores_volume(self):
        from PyQt6.QtWidgets import QApplication
        from editor.cinema_tools import MixerDialog
        app=QApplication.instance() or QApplication([])
        from PyQt6.QtWidgets import QMainWindow
        window=QMainWindow();tree=SceneTree();audio=AudioSystem(tree);tree.audio_system=audio
        window.viewport=SimpleNamespace(scene_tree=tree);window.settings={}
        dialog=MixerDialog(window);dialog.controls['music'][0].setValue(.2)
        self.assertAlmostEqual(audio.get_bus_volume('music'),.2)
        dialog.reject();self.assertEqual(audio.get_bus_volume('music'),1)
        window.close()

    def test_png_export_has_no_manifest(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QImage
        from editor.sprite_slicer import SpriteSlicer
        app=QApplication.instance() or QApplication([])
        with self.folder() as tmp:
            root=Path(tmp);image=QImage(32,32,QImage.Format.Format_ARGB32);image.fill(0xffffffff);image.save(str(root/'atlas.png'))
            dialog=SpriteSlicer(root/'atlas.png');out=root/'atlas';out.mkdir();paths=dialog.save_parts(out)
            self.assertTrue(paths);self.assertTrue(all(p.suffix=='.png' for p in out.iterdir()));dialog.close()


if __name__=='__main__':unittest.main()
