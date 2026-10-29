import os
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
from PyQt6.QtWidgets import QApplication
from editor.main_window import MainWindow
from engine.nodes.sprite2d import Sprite2D
from engine.nodes.game_object import GameObject
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.resources.scene_serializer import SceneSerializer
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.math.vector2 import Vector2
import pygame
app=QApplication([]);window=MainWindow();window.save_layout=lambda:None
root=GameObject();ground=Sprite2D('Ground');ground.position.y=100;ground.texture=pygame.Surface((300,20));root.add_child(ground)
player=Sprite2D('Player');player.texture=pygame.Surface((24,48));root.add_child(player)
window.add_component_to_node(ground,'BoxCollider2D');window.add_component_to_node(player,'Rigidbody2D')
assert ground.get_component('BoxCollider2D').size==Vector2(300,20)
assert player.get_component('BoxCollider2D').size==Vector2(24,48)
assert player.get_component('Rigidbody2D') is not None
root=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(root));player=root.get_children()[1]
tree=SceneTree();tree.current_scene=Scene('Test',root);tree.collision_system=CollisionSystem(tree);physics=PhysicsSystem(tree)
for _ in range(240):physics.step(1/60);physics.integrate(1/60)
assert abs(player.position.y-66)<.001,player.position
window.current_scene=None;window.close()
print('PASS: direct Sprite2D components, automatic fitting, save/load and falling player lands on sprite floor')
