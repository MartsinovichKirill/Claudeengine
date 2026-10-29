import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import tempfile
import unittest
from pathlib import Path
from engine.systems.cloud_scripts import CloudRuntime, compile_cloud
from engine.systems.script_system import ScriptSystem
from engine.nodes import Node2D, GameObject
from engine.resources.scene_serializer import SceneSerializer


class CloudLanguageTests(unittest.TestCase):
    def test_language_fields_methods_and_control_flow(self):
        source = '''script Player extends Node2D:
    export speed: float = 240.0
    let items = []
    signal finished
    func compute(limit: int) -> int:
        let values = [i * 2 for i in range(limit) if i % 2 == 0]
        try:
            return sum(values)
        except ValueError:
            return -1
    on ready():
        self.items.append("true let export")
        self.visible = true
'''
        scope = {'Node2D': Node2D}
        exec(compile_cloud(source, 'player.cloud'), scope)
        a, b = scope['Player'](), scope['Player']()
        a._ready()
        self.assertEqual(a.compute(5), 12)
        self.assertEqual(b.items, [])
        self.assertEqual(a.items, ['true let export'])
        self.assertEqual(a.get_property_list()['speed']['type'], 'float')
        self.assertIn('finished', a.get_signals())

    def test_import_reload_and_nested_modules(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'build') as directory:
            root = Path(directory); scripts = root / 'scripts'; scripts.mkdir()
            (scripts / 'util.cloud').write_text('func twice(x):\n    return x * 2\n', encoding='utf-8')
            (scripts / 'player.cloud').write_text('from util import twice\nscript Player extends Node2D:\n    on ready():\n        self.position.x = twice(4)\n', encoding='utf-8')
            runtime = ScriptSystem(directory)
            self.assertEqual(runtime.reload(), 2)
            cls = runtime.get_class_for('scripts/player.cloud'); player = cls(); player._ready()
            self.assertEqual(player.position.x, 8)
            (scripts / 'util.cloud').write_text('func twice(x):\n    return x * 3\n', encoding='utf-8')
            runtime.reload(); player = runtime.get_class_for('scripts/player.cloud')(); player._ready()
            self.assertEqual(player.position.x, 12)

    def test_diagnostic_line(self):
        with self.assertRaises(SyntaxError) as caught:
            compile_cloud('script Test extends Node2D:\n    on ready():\n        let x =\n', 'broken.cloud')
        self.assertEqual(caught.exception.lineno, 3)

    def test_const_and_multiline_strings(self):
        with self.assertRaises(SyntaxError):
            compile_cloud('const SPEED = 3\nSPEED = 4\n')
        scope = {}
        source = 'let text = """hello\nlet value = true\non ready():\n"""\n'
        exec(compile_cloud(source), scope)
        self.assertIn('let value = true', scope['text'])
        self.assertIn('on ready():', scope['text'])

    def test_components_roundtrip_and_animator(self):
        node = GameObject('Hero')
        node.add_component('SpriteRenderer')
        body = node.add_component('Rigidbody2D'); body.gravity_scale = 0.5
        collider = node.add_component('BoxCollider2D')
        animator = node.add_component('Animator')
        self.assertEqual(animator.states, {})
        self.assertEqual(animator.parameters, {})
        animator.states = {'idle': 'idle', 'run': 'run', 'attack': 'attack'}
        animator.entry_state = 'idle'
        animator.transitions = [
            {'from': '*', 'to': 'attack', 'parameter': 'attack', 'operator': '==', 'value': True},
            {'from': '*', 'to': 'run', 'parameter': 'speed', 'operator': '>', 'value': 10}]
        animator._ready(); animator.set_parameter('speed', 50); animator._process(0.1)
        self.assertEqual(animator.state, 'run')
        animator.trigger('attack'); animator._process(0.1)
        self.assertEqual(animator.state, 'attack')
        self.assertFalse(animator.parameters['attack'])
        restored = SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(node))
        self.assertEqual(len(restored.components), 5)
        self.assertEqual(restored.get_component('Rigidbody2D').gravity_scale, 0.5)
        self.assertEqual(len(restored.get_collision_shapes()), 1)
        self.assertEqual(restored.get_component('Animator').duplicate().states, animator.states)

    def test_gameobject_physics_and_renderer(self):
        import pygame
        from engine.core.scene import Scene
        from engine.core.scene_tree import SceneTree
        from engine.systems.physics_system import PhysicsSystem
        from engine.nodes.sprite2d import Sprite2D
        from engine.math.vector2 import Vector2
        node = GameObject()
        body = node.add_component('Rigidbody2D')
        tree = SceneTree(); tree.current_scene = Scene('Test', node)
        physics = PhysicsSystem(tree)
        physics.step(0.1); physics.integrate(0.1)
        self.assertGreater(node.position.y, 0)
        previous = node.position.y
        body.enabled = False
        physics.step(0.1); physics.integrate(0.1)
        self.assertEqual(node.position.y, previous)
        sprite = Sprite2D(); node.add_child(sprite)
        sprite.texture = pygame.Surface((10, 10), pygame.SRCALPHA)
        node.scale = Vector2(2, 3)
        surface, _ = sprite._get_draw_surface(None)
        self.assertEqual(surface.get_size(), (20, 30))
        calls = []
        sprite._get_draw_surface = lambda camera: calls.append(camera)
        sprite._draw_local(pygame.Surface((50, 50)), Vector2(-1000, -1000), None)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
