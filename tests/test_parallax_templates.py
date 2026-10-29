import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pygame
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D
from engine.nodes.sprite2d import Sprite2D
from engine.nodes.animated_sprite import AnimatedSprite2D
from engine.nodes.parallax2d import Parallax2D
from engine.nodes.canvas_layer import CanvasLayer
from engine.nodes.camera2d import CameraState
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.core.time import Time
from engine.resources.asset_manager import AssetManager
from engine.resources.scene_serializer import SceneSerializer
from engine.systems.render_system import RenderSystem
from engine.systems.ui_system import UISystem
from engine.systems.parallax_space import draw_cameras
from engine.systems.script_system import ScriptSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from editor.template_library import install_player_template, LIBRARY

ROOT = Path(__file__).resolve().parents[1]


class Controls:
    mouse_position = Vector2()
    def is_mouse_button_just_pressed(self, key): return False
    def is_mouse_button_just_released(self, key): return False
    def __init__(self): self.actions = set()
    def is_action_pressed(self, key): return key in self.actions
    def is_action_just_pressed(self, key): return False
    def get_axis(self, a,b): return int(b in self.actions)-int(a in self.actions)


class ParallaxTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init(); pygame.display.set_mode((1,1))

    def test_parallax_projection_preserves_scene_positions(self):
        layer=Parallax2D(); sprite=Sprite2D(); layer.add_child(sprite)
        layer.scroll_scale=Vector2(.25,.5); layer.scroll_offset=Vector2(5,8)
        layer.autoscroll=Vector2(10,0); layer._process(2)
        camera=CameraState(Vector2(100,40),1,Vector2(640,360))
        projected=draw_cameras(sprite,camera)[0]
        self.assertEqual(projected.center,Vector2(0,12)); self.assertEqual(sprite.position,Vector2())
        self.assertEqual(camera.center,Vector2(100,40))

    def test_parallax_repeat_covers_viewport_at_negative_coordinates(self):
        layer=Parallax2D(); sprite=Sprite2D(); layer.add_child(sprite)
        layer.scroll_scale=Vector2(1,1); layer.repeat_size=Vector2(32,0)
        sprite.texture=pygame.Surface((32,100)); sprite.texture.fill('red')
        tree=SceneTree(); tree.change_scene(Scene('repeat',layer))
        surface=pygame.Surface((240,80))
        RenderSystem(tree).render(surface,CameraState(Vector2(-173,0),1,Vector2(240,80)))
        self.assertTrue(all(surface.get_at((x,40)).r==255 for x in range(240)))

    def test_native_nodes_roundtrip(self):
        root=Parallax2D();root.autoscroll=Vector2(5,6);root.repeat_size=Vector2(64,0)
        ui=CanvasLayer(); ui.offset=Vector2(30,20);ui.scale=Vector2(2,2);root.add_child(ui)
        loaded=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(root))
        self.assertIsInstance(loaded,Parallax2D);self.assertEqual(loaded.repeat_size,root.repeat_size)
        self.assertEqual(loaded.get_children()[0].scale,Vector2(2,2))

    def test_canvas_transform_and_nested_layer_render_once(self):
        class Marker(Node2D):
            def __init__(self): super().__init__();self.calls=0
            def draw_ui(self,surface,size): self.calls+=1;surface.fill('red',(2,3,4,4))
        layer=CanvasLayer();layer.offset=Vector2(10,20);layer.scale=Vector2(2,2)
        marker=Marker();layer.add_child(marker)
        nested=CanvasLayer();nested.offset=Vector2(70,10);nested.layer=2;other=Marker();nested.add_child(other);layer.add_child(nested)
        tree=SimpleNamespace(current_scene=Scene('UI',layer),input=None)
        surface=pygame.Surface((100,80));surface.fill('black');UISystem(tree).render(surface)
        self.assertEqual(surface.get_at((14,26)).r,255)
        self.assertEqual(surface.get_at((72,13)).r,255)
        self.assertEqual((marker.calls,other.calls),(1,1))
        layer.visible=False;UISystem(tree).render(surface);self.assertEqual(other.calls,1)

    def test_canvas_can_draw_sprite_and_behind_world(self):
        layer=CanvasLayer();layer.layer=-1;layer.offset=Vector2(20,15)
        sprite=Sprite2D();sprite.centered=False;sprite.texture=pygame.Surface((6,6));sprite.texture.fill('green');layer.add_child(sprite)
        tree=SceneTree();tree.change_scene(Scene('canvas',layer));surface=pygame.Surface((80,60))
        RenderSystem(tree).render(surface)
        self.assertEqual(surface.get_at((22,17))[:3],pygame.Color('green')[:3])

    def test_named_clips_switch_without_restarting_same_clip(self):
        manager=AssetManager(str(LIBRARY/'player_controller'))
        sprite=AnimatedSprite2D(); sprite.add_animation('Idle',['assets/idle/idle_00.png','assets/idle/idle_01.png'],10)
        sprite.add_animation('Jump',['assets/jump/jump_00.png','assets/jump/jump_01.png'],10,False)
        sprite.set_asset_manager(manager);sprite.advance(.11);self.assertEqual(sprite.frame,1)
        sprite.play('Idle');self.assertEqual(sprite.frame,1)
        sprite.play('Jump');self.assertEqual(sprite.frame,0)
        finished=[];sprite.connect('animation_finished',lambda:finished.append(True))
        sprite.advance(1);sprite.advance(1);self.assertEqual(len(finished),1);self.assertFalse(sprite.playing)
        copy=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(sprite));self.assertEqual(copy.animations,sprite.animations)

    def test_animated_render_uses_frame_not_original_sheet(self):
        red=pygame.Surface((10,10));red.fill('red');blue=pygame.Surface((10,10));blue.fill('blue')
        sprite=AnimatedSprite2D();sprite._asset_manager=SimpleNamespace(get_texture=lambda path:red)
        sprite.texture_path='original.png';sprite.set_frames([blue]);surface=pygame.Surface((20,20))
        sprite._draw_local(surface,Vector2(10,10),CameraState())
        self.assertEqual(surface.get_at((10,10))[:3],(0,0,255))

    def test_exact_sheet_slices_preserve_pixels_and_common_pivot(self):
        for name,count in [('idle',10),('walk',10),('run',10),('jump',6)]:
            base=LIBRARY/'player_controller/assets'
            sheet=pygame.image.load(str(base/'originals'/f'male_hero_template-{name}.png'))
            for i in range(count):
                frame=pygame.image.load(str(base/name/f'{name}_{i:02}.png'))
                original=sheet.subsurface((i*128+40,24,48,64))
                self.assertEqual(pygame.image.tobytes(frame,'RGBA'),pygame.image.tobytes(original,'RGBA'))

    def test_template_import_twice_preserves_existing_scene(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            p=Path(tmp);(p/'project.json').write_text(json.dumps({'main_scene':'scenes/main.scene','input':{'jump':['J']}}))
            first=install_player_template(p);previous=first.read_bytes();second=install_player_template(p)
            self.assertNotEqual(first,second);self.assertEqual(first.read_bytes(),previous)
            config=json.loads((p/'project.json').read_text());self.assertEqual(config['input']['jump'],['J'])
            self.assertEqual(config['main_scene'],'scenes/main.scene')

    def test_controller_runtime_walk_run_jump_land_and_camera(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            p=Path(tmp);(p/'project.json').write_text('{}');path=install_player_template(p)
            scripts=ScriptSystem(tmp);scripts.reload();self.assertFalse(scripts.errors,scripts.errors)
            scene=Scene.load(str(path),scripts);tree=SceneTree({'physics':{'gravity':[0,980]}})
            controls=Controls();tree.input=controls
            tree.collision_system=CollisionSystem(tree);physics=PhysicsSystem(tree)
            renderer=RenderSystem(tree,AssetManager(tmp));renderer.prepare_scene(scene);tree.change_scene(scene)
            player=scene.find_node('Player');camera=scene.find_node('Camera');Time.physics_delta=1/60
            def step(n):
                for _ in range(n):
                    physics.step(1/60);scene.physics_process(1/60);scene.process(1/60)
                    player.sprite.advance(1/60);camera.update_camera(1/60)
            step(5);self.assertTrue(player.is_on_floor())
            controls.actions={'template_right'};step(30);walk=player.velocity.x
            self.assertEqual(player.sprite.animation,'Walk')
            controls.actions.add('template_run');step(15);self.assertGreater(player.velocity.x,walk)
            self.assertEqual(player.sprite.animation,'Run')
            controls.actions={'template_jump'};step(1);self.assertLess(player.velocity.y,0);self.assertEqual(player.sprite.animation,'Jump')
            controls.actions=set();step(120);self.assertTrue(player.is_on_floor())
            self.assertLess(player.position.y,481)
            self.assertEqual(player.sprite.animation,'Idle')
            before=camera.get_center().x;player.position.x+=100;camera.update_camera(1/60)
            self.assertGreater(camera.get_center().x,before);self.assertLess(camera.get_center().x,player.position.x+65)
            surface=pygame.Surface((1280,720));renderer.render(surface);UISystem(tree).render(surface)
            pygame.image.save(surface,str(ROOT/'build/player-template-preview.png'))


if __name__=='__main__':unittest.main()
