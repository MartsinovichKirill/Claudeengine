import tempfile
import unittest
from pathlib import Path

from engine.nodes.game_object import GameObject
from engine.nodes.rigidbody2d import RigidBody2D
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.math.vector2 import Vector2
from engine.resources.scene_serializer import SceneSerializer
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.components.registry import all_visible_components
from editor.undo_stack import UndoStack, ComponentValuesCommand, ReorderComponentCommand


class CompositionTests(unittest.TestCase):
    def test_empty_object_and_catalog(self):
        node = GameObject()
        self.assertNotIsInstance(node, RigidBody2D)
        self.assertEqual([c.get_type_name() for c in node.components], ['Transform'])
        self.assertIsNone(node.physics_body())
        self.assertTrue({
            'SpriteRenderer', 'Rigidbody2D', 'BoxCollider2D', 'CircleCollider2D',
            'AudioSource', 'Camera2D', 'Light2D', 'Animator', 'ScriptBehaviour'}.issubset(set(all_visible_components())))
        self.assertGreaterEqual(len(all_visible_components()), 100)
        from engine.components.registry import create_component
        self.assertIsNone(create_component('Health'))
        self.assertIsNone(create_component('DoubleJump'))
        animator = node.add_component('Animator')
        self.assertEqual(animator._serialize_data(), {'states': {}, 'transitions': [], 'parameters': {}})

    def test_transform_roundtrip_and_duplicate(self):
        node = GameObject()
        node.transform.position = Vector2(12, 34)
        node.transform.scale = Vector2(2, 3)
        self.assertEqual(node.position, Vector2(12, 34))
        with self.assertRaises(ValueError):
            node.remove_component(node.transform)
        node.transform.set('enabled', False)
        self.assertTrue(node.transform.enabled)
        for restored in (node.duplicate(), SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(node))):
            self.assertEqual(len(restored.get_components('Transform')), 1)
            self.assertEqual(restored.transform.position, Vector2(12, 34))
            self.assertEqual(restored.scale, Vector2(2, 3))

    def test_component_physics_with_static_collider(self):
        root = GameObject('Root')
        ground = GameObject('Ground'); ground.position.y = 48
        ground.add_component('BoxCollider2D').size = Vector2(200, 32)
        falling = GameObject('Falling')
        rigid = falling.add_component('Rigidbody2D')
        falling.add_component('BoxCollider2D')
        root.add_child(ground); root.add_child(falling)
        tree = SceneTree(); tree.current_scene = Scene('Test', root)
        physics = PhysicsSystem(tree); collision = CollisionSystem(tree)
        tree.collision_system = collision
        for _ in range(120):
            physics.step(1 / 120); physics.integrate(1 / 120)
        self.assertAlmostEqual(falling.position.y, 16, places=4)
        self.assertEqual(ground.position.y, 48)
        rigid.apply_impulse(Vector2(10, 0))
        self.assertGreater(rigid.velocity.x, 0)
        falling.remove_component(rigid)
        before = Vector2(falling.position)
        physics.step(0.1); physics.integrate(0.1)
        self.assertEqual(falling.position, before)

    def test_circle_camera_light_and_undo(self):
        from engine.systems.render_system import RenderSystem
        from engine.systems.light_system import LightSystem
        node = GameObject(); node.position = Vector2(20, 30)
        circle = node.add_component('CircleCollider2D'); circle.radius = 7
        camera = node.add_component('Camera2D'); camera.zoom = 2
        light = node.add_component('Light2D')
        self.assertEqual(circle.shape().shape_type, 'circle')
        self.assertEqual(circle.shape().radius, 7)
        node.scale = Vector2(2, 3)
        self.assertEqual(CollisionSystem(None)._shape_circle(circle.shape())[1], 21)
        tree = SceneTree(); tree.current_scene = Scene('Test', node)
        self.assertEqual(RenderSystem(tree).find_active_camera().get_global_position(), node.position)
        self.assertEqual(LightSystem(tree)._collect_lights()[0].world_center(), node.position)
        stack = UndoStack()
        before = circle.to_dict(); after = circle.to_dict(); after['properties']['radius'] = 15
        stack.execute(ComponentValuesCommand(circle, before, after))
        self.assertEqual(circle.radius, 15)
        stack.undo(); self.assertEqual(circle.radius, 7)
        stack.redo(); self.assertEqual(circle.radius, 15)
        stack.execute(ReorderComponentCommand(node, light, 1))
        self.assertIs(node.components[1], light)
        stack.undo(); self.assertIs(node.components[-1], light)
        self.assertIs(node.components[0], node.transform)

    def test_user_script_component_lifecycle_and_fields(self):
        from engine.systems.script_system import ScriptSystem
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'build') as directory:
            root = Path(directory); (root / 'scripts').mkdir()
            (root / 'scripts/custom.cloud').write_text(
                'script Custom extends Behaviour:\n'
                '    export amount: float = 2.0\n'
                '    on ready():\n'
                '        self.transform.position.x = self.amount\n'
                '    on process(delta):\n'
                '        self.transform.position.y += delta\n', encoding='utf-8')
            system = ScriptSystem(directory); system.reload()
            self.assertEqual(system.errors, [])
            node = GameObject()
            script = node.add_component('ScriptBehaviour')
            script.script_path = 'scripts/custom.cloud'; script.fields = {'amount': 9}
            restored = SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(node))
            tree = SceneTree(); tree.script_system = system
            tree.change_scene(Scene('Test', restored))
            self.assertEqual(restored.position.x, 9)
            tree.process(0.5); self.assertEqual(restored.position.y, 0.5)
            restored.get_component('ScriptBehaviour').enabled = False
            tree.process(0.5); self.assertEqual(restored.position.y, 0.5)
            tree.change_scene(Scene('Empty', GameObject()))
            self.assertIsNone(restored.get_component('ScriptBehaviour').instance)


if __name__ == '__main__':
    unittest.main()
