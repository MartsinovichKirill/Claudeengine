import unittest
from engine.nodes.game_object import GameObject
from engine.nodes.tilemap import TileMap
from engine.math.vector2 import Vector2
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.resources.scene_serializer import SceneSerializer

class PhysicsRegression(unittest.TestCase):
    def setup_world(self):
        root=GameObject('Root'); tree=SceneTree(); tree.current_scene=Scene('Test',root)
        tree.collision_system=CollisionSystem(tree)
        return root,tree,PhysicsSystem(tree)
    def test_fast_box_does_not_cross_thin_floor(self):
        root,tree,physics=self.setup_world()
        floor=GameObject('Floor');floor.position.y=100;floor.add_component('BoxCollider2D').size=Vector2(400,2)
        box=GameObject('Box');box.add_component('BoxCollider2D');rigid=box.add_component('Rigidbody2D');rigid.velocity=Vector2(0,20000)
        root.add_child(floor);root.add_child(box)
        physics.integrate(1/60)
        self.assertAlmostEqual(box.position.y,83,places=5)
        self.assertEqual(rigid.velocity.y,0)
    def test_tile_collision_and_disabled_tile(self):
        root,tree,physics=self.setup_world();tiles=TileMap();tiles.position=Vector2(-16,100);tiles.set_cell(0,0,0,True);root.add_child(tiles)
        box=GameObject();box.add_component('BoxCollider2D');box.add_component('Rigidbody2D');root.add_child(box)
        for _ in range(180):physics.step(1/60);physics.integrate(1/60)
        self.assertAlmostEqual(box.position.y,84,places=4)
        tiles.set_cell(0,0,0,False)
        for _ in range(60):physics.step(1/60);physics.integrate(1/60)
        self.assertGreater(box.position.y,150)
    def test_one_way_down_blocks_up_passes(self):
        root,tree,physics=self.setup_world();floor=GameObject();floor.position.y=100;shape=floor.add_component('BoxCollider2D');shape.size=Vector2(200,4);shape.one_way=True;root.add_child(floor)
        box=GameObject();box.add_component('BoxCollider2D');box.add_component('Rigidbody2D');root.add_child(box)
        collision=tree.collision_system
        self.assertIsNotNone(collision.move_and_collide(box.physics_body(),Vector2(0,200)))
        box.position.y=150
        self.assertIsNone(collision.move_and_collide(box.physics_body(),Vector2(0,-200)))
    def test_parent_scale_world_correction(self):
        root,tree,physics=self.setup_world();floor=GameObject();floor.position.y=100;floor.add_component('BoxCollider2D').size=Vector2(400,4);root.add_child(floor)
        parent=GameObject();parent.scale=Vector2(2,2);root.add_child(parent)
        box=GameObject();box.add_component('BoxCollider2D');box.add_component('Rigidbody2D');parent.add_child(box)
        tree.collision_system.move_and_collide(box.physics_body(),Vector2(0,200))
        self.assertAlmostEqual(box.get_global_position().y,66,places=4)
    def test_tileset_roundtrip(self):
        tiles=TileMap();tiles.tile_sources={0:'assets/grass.png'};tiles.tile_collisions={0:True};tiles.set_cell(0,0,0,True)
        result=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(tiles))
        self.assertEqual(result.tile_sources,tiles.tile_sources);self.assertEqual(result.tile_collisions,tiles.tile_collisions)
        self.assertEqual(len(result.physics_body().get_collision_shapes()),1)

if __name__=='__main__':unittest.main()
