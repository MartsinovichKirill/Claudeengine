import os
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
os.environ['CLOUDENGINE_CONFIG_DIR']=os.path.abspath('build/beta-settings')
import copy,json,tempfile,unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.nodes.game_object import GameObject
from engine.nodes.camera2d import Camera2D
from engine.nodes.tilemap import TileMap
from engine.components.component import Component
from engine.math.vector2 import Vector2
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.resources.scene_serializer import SceneSerializer
from editor.resource_refactor import relocate_resource,remap_scene
from editor.undo_stack import TileEditCommand,UndoStack,AddComponentCommand,RemoveComponentCommand

class BetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_tangent_motion_on_floor(self):
        root=GameObject();floor=GameObject();floor.position.y=100;floor.add_component('BoxCollider2D').size=Vector2(1000,2);root.add_child(floor)
        box=GameObject();box.add_component('BoxCollider2D');rigid=box.add_component('Rigidbody2D');root.add_child(box)
        tree=SceneTree();tree.current_scene=Scene(root=root);tree.collision_system=CollisionSystem(tree)
        rigid.velocity=Vector2(120,1000);PhysicsSystem(tree).integrate(.1)
        self.assertAlmostEqual(box.position.x,12,places=3);self.assertAlmostEqual(box.position.y,83,places=3)
    def test_component_lifecycle_toggle_and_remove(self):
        class Tracker(Component):
            def __init__(self):super().__init__();self.starts=0;self.stops=0
            def _ready(self):self.starts+=1
            def _exit_tree(self):self.stops+=1
        node=GameObject();component=Tracker();component.enabled=False;node.add_component(component);node._inside_tree=True;node._ready_components()
        self.assertEqual(component.starts,0);component.enabled=True;self.assertEqual(component.starts,1)
        component.enabled=False;self.assertEqual(component.stops,1);component.enabled=True;node.remove_component(component)
        self.assertEqual(component.starts,2);self.assertEqual(component.stops,2);self.assertIsNone(component.owner)
    def test_components_and_tiles_undo_roundtrip(self):
        t=TileMap();t.tile_sources={0:'assets/grass.png'};t.tile_collisions={0:True}
        before=t.snapshot();t.flood_fill(0,0,0,True,bounds=(0,0,2,2));after=t.snapshot();self.assertEqual(len(after),9)
        stack=UndoStack();stack.push(TileEditCommand(t,before,after));stack.undo();self.assertEqual(t.cells,{})
        stack.redo();self.assertEqual(t.cells,after)
        collider=t.add_component('TileMapCollider2D');collider.enabled=False
        restored=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(t))
        self.assertFalse(restored.get_component('TileMapCollider2D').enabled);self.assertIsNone(restored.physics_body())
        self.assertEqual(restored.cells,after)
    def test_resource_move_updates_disk_and_live(self):
        with tempfile.TemporaryDirectory(dir='build') as tmp:
            root=Path(tmp);(root/'assets').mkdir();(root/'textures').mkdir();(root/'assets/a.png').write_bytes(b'asset')
            (root/'main.scene').write_text(json.dumps({'texture':'res://assets/a.png'}),encoding='utf-8')
            obj=GameObject();renderer=obj.add_component('SpriteRenderer');renderer.texture=''
            # SpriteRenderer's exported property is texture_path.
            renderer.texture_path='assets/a.png';scene=Scene(root=obj)
            old,new=relocate_resource(root,root/'assets/a.png',root/'textures/b.png');remap_scene(scene,old,new)
            self.assertEqual(renderer.texture_path,'textures/b.png')
            self.assertEqual(json.loads((root/'main.scene').read_text(encoding='utf-8'))['texture'],'res://textures/b.png')
            self.assertTrue(list((root/'.cloud-backups').rglob('main.scene')))
            with self.assertRaises(ValueError):relocate_resource(root,root/'textures/b.png',root.parent/'outside.png')
    def test_play_uses_memory_and_restores_editor(self):
        from editor.main_window import MainWindow
        window=MainWindow();window.save_layout=lambda:None
        with tempfile.TemporaryDirectory(dir='build') as tmp:
            window.project_dir=tmp;scene=Scene('Unsaved',GameObject('Root'));scene.root.add_child(Camera2D())
            tiles=TileMap();tiles.set_cell(0,0,1,True);scene.root.add_child(tiles)
            before=copy.deepcopy(SceneSerializer.node_to_dict(scene.root));window.current_scene=scene
            window.viewport.start_game(scene,{},tmp)
            play=window.viewport.scene_tree.current_scene;self.assertIsNot(play.root,scene.root)
            play.root.name='Mutated';play.get_nodes()[-1].clear();window.viewport.stop_game()
            self.assertEqual(SceneSerializer.node_to_dict(scene.root),before);self.assertEqual(scene.path,'')
        window.current_scene=None;window.close()

    def test_resource_rollback_and_folder_move(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir='build') as tmp:
            root=Path(tmp);(root/'assets').mkdir();(root/'assets/a.png').write_bytes(b'asset')
            original=json.dumps({'file':'assets/a.png'});(root/'main.scene').write_text(original)
            with patch('editor.resource_refactor.os.replace',side_effect=OSError('write failed')):
                with self.assertRaises(OSError):relocate_resource(root,root/'assets',root/'images')
            self.assertTrue((root/'assets/a.png').is_file());self.assertEqual((root/'main.scene').read_text(),original)
            relocate_resource(root,root/'assets',root/'images')
            self.assertEqual(json.loads((root/'main.scene').read_text())['file'],'images/a.png')
    def test_error_line_navigation(self):
        from editor.script_editor import ScriptEditor
        from editor.scene_validation import validate_scene
        with tempfile.TemporaryDirectory(dir='build') as tmp:
            root=Path(tmp);path=root/'bad.cloud';path.write_text('script Bad extends Behaviour:\n    func broken():\n        if :\n',encoding='utf-8')
            obj=GameObject();obj.add_component('ScriptBehaviour').script_path='bad.cloud'
            scene=Scene(root=obj);issues=validate_scene(scene,root)
            issue=next(i for i in issues if i.path.endswith('bad.cloud'))
            editor=ScriptEditor();editor.load_file(str(path));editor.goto_line(issue.line)
            self.assertEqual(editor.editor.textCursor().blockNumber(),issue.line-1);editor.close()

    def test_scene_tab_reorder_and_close(self):
        from editor.scene_tabs import SceneTabs
        tabs=SceneTabs();a,b,c=Scene('A'),Scene('B'),Scene('C')
        for scene in (a,b,c):tabs.add_scene(scene)
        tabs.tabBar().moveTab(2,0);self.assertEqual(tabs.scenes(),[c,a,b])
        tabs.setCurrentIndex(1);self.assertIs(tabs.get_current_scene(),a)
        tabs.close_tab(0);self.assertEqual(tabs.scenes(),[a,b]);self.assertIs(tabs.get_current_scene(),a)
        tabs.close()

if __name__=='__main__':unittest.main()
