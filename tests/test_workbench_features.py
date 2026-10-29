import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from engine.nodes.game_object import GameObject
from engine.math.vector2 import Vector2
from engine.resources.scene_serializer import SceneSerializer
from engine.resources.prefab import Prefab
from engine.resources.material import Material
from engine.components.registry import create_component, all_visible_components
from engine.components.technical import TECHNICAL_COMPONENTS, DataProcessor
from engine.systems.script_debugger import ScriptDebugger, DebugStop

ROOT=Path(__file__).resolve().parents[1]


class WorkbenchTests(unittest.TestCase):
    def test_linked_prefab_updates_and_overrides(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            root=Path(directory)
            source=GameObject('Source'); renderer=source.add_component('SpriteRenderer')
            child=GameObject('Child'); child.add_component('BoxCollider2D'); source.add_child(child)
            Prefab.save(source,'assets/object.prefab',root)
            first=Prefab.instantiate('assets/object.prefab',root)
            second=Prefab.instantiate('assets/object.prefab',root)
            second.get_component('SpriteRenderer').color=[255,0,0,255]
            second.position=Vector2(100,200)
            first.add_component('CircleCollider2D')
            renderer.color=[0,255,0,255]; renderer.texture_path='assets/new.png'
            child.name='Renamed'; child.add_component('AudioSource')
            source.add_child(GameObject('Added'))
            Prefab.save(source,'assets/object.prefab',root)
            for instance in (first,second):
                Prefab.apply(instance,Prefab.updated_data(instance,root))
                self.assertEqual(instance.get_component('SpriteRenderer').texture_path,'assets/new.png')
                self.assertEqual(instance.get_children()[0].name,'Renamed')
                self.assertTrue(instance.get_children()[0].has_component('AudioSource'))
                self.assertEqual(len(instance.get_children()),2)
            self.assertTrue(first.has_component('CircleCollider2D'))
            self.assertEqual(list(first.get_component('SpriteRenderer').color),[0,255,0,255])
            self.assertEqual(list(second.get_component('SpriteRenderer').color),[255,0,0,255])
            self.assertEqual(second.position,Vector2(100,200))
            self.assertEqual(second.transform.position,Vector2(100,200))

    def test_prefab_refreshes_on_scene_load(self):
        from engine.core.scene import Scene
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            root=Path(directory); (root/'project.json').write_text('{}')
            source=GameObject(); source.add_component('SpriteRenderer')
            Prefab.save(source,'assets/object.prefab',root)
            instance=Prefab.instantiate('assets/object.prefab',root)
            SceneSerializer.save_scene(Scene('Test',instance),str(root/'main.scene'))
            source.get_component('SpriteRenderer').sorting_order=12
            Prefab.save(source,'assets/object.prefab',root)
            restored=SceneSerializer.load_scene(str(root/'main.scene'))
            self.assertEqual(restored.root.get_component('SpriteRenderer').sorting_order,12)
            with self.assertRaises(ValueError): Prefab.instantiate('../escape.prefab',root)

    def test_material_parameters_and_original_texture(self):
        import pygame
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            root=Path(directory)
            (root/'test.shader').write_text('def fragment(rgb, uv, time, parameters):\n    return rgb * parameters["gain"]\n')
            source=pygame.Surface((3,3),pygame.SRCALPHA); source.fill((200,100,50,128))
            material=Material(shader='test.shader',parameters={'gain':.5})
            material.save(root/'test.material'); material=Material.load(root/'test.material')
            rendered=material.render(source,root)
            self.assertEqual(tuple(rendered.get_at((0,0))),(100,50,25,128))
            self.assertEqual(tuple(source.get_at((0,0))),(200,100,50,128))
            with self.assertRaises(ValueError): Material.from_dict({'color':[999,0,0,0]})

    def test_all_technical_components_execute_and_roundtrip(self):
        import pygame
        surface=pygame.Surface((256,256),pygame.SRCALPHA)
        from engine.nodes.camera2d import CameraState
        camera=CameraState(Vector2(),1,Vector2(256,256))
        self.assertGreaterEqual(len(all_visible_components()),100)
        for cls,category in TECHNICAL_COMPONENTS:
            with self.subTest(component=cls.get_type_name()):
                node=GameObject(); node.add_component('Rigidbody2D')
                component=node.add_component(cls())
                if isinstance(component,DataProcessor):
                    result=component.evaluate()
                    if isinstance(result,float): self.assertTrue(math.isfinite(result))
                component._process(.1); component._physics_process(.1)
                if callable(getattr(component,'draw',None)):
                    component.draw(surface,Vector2(128,128),camera)
                restored=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(node))
                self.assertIsNotNone(restored.get_component(cls.get_type_name()))
        add=create_component('Add'); add.a=7; add.b=3; self.assertEqual(add.evaluate(),10)
        vector=create_component('VectorDot'); vector.a=Vector2(1,2); vector.b=Vector2(3,4)
        self.assertEqual(vector.evaluate(),11)
        self.assertIsNone(create_component('Health'))

    def test_ui_rect_anchors_and_runtime_button(self):
        from engine.nodes.button import Button
        node=Button(); transform=node.add_component('RectTransform')
        transform.anchor_min=Vector2(.5,.5); transform.anchor_max=Vector2(.5,.5)
        transform.size_delta=Vector2(100,40); transform.pivot=Vector2(.5,.5)
        self.assertEqual(node.get_ui_position(Vector2(800,600)),Vector2(350,280))
        self.assertEqual(node.get_ui_position(Vector2(1600,900)),Vector2(750,430))
        transform.anchor_min=Vector2(); transform.anchor_max=Vector2(1,1)
        transform.pivot=Vector2(); transform.size_delta=Vector2(-20,-20); transform.offset=Vector2(10,10)
        self.assertEqual(node.get_ui_position(Vector2(800,600)),Vector2(10,10))
        self.assertEqual(node.size,Vector2(780,580))

    def test_cloud_debugger_breakpoint_step_over_into_out(self):
        from engine.systems.cloud_scripts import CloudRuntime
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            root=Path(directory); scripts=root/'scripts'; scripts.mkdir()
            path=scripts/'debug.cloud'
            path.write_text('func nested(value):\n    let inner = value + 1\n    return inner\n\nfunc run():\n    let value = 2\n    let answer = nested(value)\n    return answer\n')
            module=CloudRuntime(scripts).load('debug.cloud')
            hits=[]
            debugger=ScriptDebugger(root)
            def pause(frame):
                hits.append((frame.f_lineno,dict(frame.f_locals)))
                if len(hits)==1: debugger.command('into')
                elif len(hits)==2: debugger.command('out')
                else: debugger.command('continue')
            debugger.on_pause=pause; debugger.toggle(path,7)
            previous=sys.gettrace()
            with debugger.tracing(): self.assertEqual(module.run(),3)
            self.assertIs(sys.gettrace(),previous)
            self.assertEqual([line for line,values in hits],[7,2,8])
            self.assertEqual(hits[0][1]['value'],2)
            hits.clear(); debugger.reset()
            debugger.on_pause=lambda frame:(hits.append(frame.f_lineno),debugger.command('over'))
            with debugger.tracing(): module.run()
            self.assertEqual(hits[:2],[7,8])
            debugger.reset(); debugger.on_pause=lambda frame:setattr(debugger,'abort_requested',True)
            with self.assertRaises(DebugStop):
                with debugger.tracing(): module.run()
            self.assertIs(sys.gettrace(),previous)


if __name__=='__main__': unittest.main()
