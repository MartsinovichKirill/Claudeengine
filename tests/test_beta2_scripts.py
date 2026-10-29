import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import tempfile,unittest,json,logging,math
from pathlib import Path
from unittest.mock import patch
from engine.systems.cloud_scripts import CloudRuntime,compile_cloud
from engine.systems.script_system import ScriptSystem
from engine.nodes.game_object import GameObject
from engine.nodes.camera2d import Camera2D
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.math.vector2 import Vector2

ROOT=Path(__file__).resolve().parents[1]

class Beta2Scripts(unittest.TestCase):
    def test_original_source_line_and_repeated_error_diagnostics(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            scripts=Path(tmp)/'scripts';scripts.mkdir();path=scripts/'player.cloud'
            source='script Player extends Behaviour:\n    on ready():\n        let speed = Vector2(1, 0)в\n'
            path.write_text(source,encoding='utf-8');system=ScriptSystem(tmp)
            with patch('engine.systems.script_system.logger.error') as log:
                self.assertEqual(system.reload(),0);self.assertEqual(system.reload(),0)
                self.assertEqual(log.call_count,1)
            diagnostic=system.diagnostics[0];self.assertEqual(diagnostic['line'],3);self.assertEqual(Path(diagnostic['path']),path)
            with self.assertRaises(SyntaxError) as ctx:compile_cloud(source,str(path))
            self.assertIn('let speed',ctx.exception.text)
            path.write_text(source.replace(')в',')'),encoding='utf-8');self.assertEqual(system.reload(),1);self.assertFalse(system.errors)
            path.write_text(source,encoding='utf-8')
            with patch('engine.systems.script_system.logger.error') as log:
                system.reload();self.assertEqual(log.call_count,1)

    def test_python_same_size_same_timestamp_reload(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            scripts=Path(tmp)/'scripts';scripts.mkdir();path=scripts/'value.py'
            code='from engine.nodes.game_object import GameObject\nclass Value(GameObject):\n    answer = 1\n'
            path.write_text(code);stamp=path.stat().st_mtime;system=ScriptSystem(tmp);system.reload()
            self.assertEqual(system.get_class_for('scripts/value.py').answer,1)
            path.write_text(code.replace('answer = 1','answer = 2'));os.utime(path,(stamp,stamp));system.reload()
            self.assertEqual(system.get_class_for('scripts/value.py').answer,2)

    def test_python_peer_import_is_project_local_and_fresh(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            scripts=Path(tmp)/'scripts';scripts.mkdir();(scripts/'helper.py').write_text('VALUE = 7\n')
            (scripts/'use.py').write_text('from helper import VALUE\nfrom engine.nodes.game_object import GameObject\nclass Use(GameObject):\n    value=VALUE\n')
            system=ScriptSystem(tmp);system.reload();self.assertFalse(system.errors);self.assertEqual(system.get_class_for('scripts/use.py').value,7)
            (scripts/'helper.py').write_text('VALUE = 9\n');system.reload();self.assertEqual(system.get_class_for('scripts/use.py').value,9)
            self.assertEqual(CloudRuntime(scripts).load('helper.py').VALUE,9)

    def test_runtime_script_component_disabled_after_one_error(self):
        from engine.components.behaviour import ScriptBehaviour,Behaviour
        class Broken(Behaviour):
            calls=0
            def _process(self,delta):
                Broken.calls+=1;raise ValueError('runtime failure')
        node=GameObject();script=node.add_component('ScriptBehaviour');script.instance=Broken();script.instance.owner=node
        with patch('engine.core.node.logger.exception') as log:
            for _ in range(20):node._process_components(1/60)
        self.assertEqual(Broken.calls,1);self.assertFalse(script.enabled);self.assertEqual(log.call_count,1)

    def test_play_rejects_unused_broken_script_instead_of_silent_partial_load(self):
        from PyQt6.QtWidgets import QApplication
        from editor.main_window import MainWindow
        app=QApplication.instance() or QApplication([]);window=MainWindow();window.save_layout=lambda:None
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            scripts=Path(tmp)/'scripts';scripts.mkdir();(scripts/'broken.cloud').write_text('script Bad extends Behaviour:\n    invalid syntax!!!\n')
            scene=Scene();scene.root.add_child(Camera2D())
            with self.assertRaisesRegex(ValueError,'broken.cloud'):
                window.viewport.start_game(scene,{},tmp)
            self.assertFalse(window.viewport.is_playing)
        window.current_scene=None;window.close()

    def test_working_player_movement_and_diagonal_normalization(self):
        import pygame
        path=ROOT/'tests/fixtures/movement_project'
        system=ScriptSystem(str(path));system.reload();self.assertFalse(system.errors)
        owner=GameObject();owner.add_component('BoxCollider2D');body=owner.add_component('Rigidbody2D')
        script=owner.add_component('ScriptBehaviour');script.script_path='scripts/player_movement.cloud'
        tree=SceneTree();tree.script_system=system;tree.change_scene(Scene(root=owner));tree.input._keys_down={pygame.K_d,pygame.K_w}
        tree.physics_process(1/60);self.assertAlmostEqual(body.velocity.length,160);self.assertGreater(body.velocity.x,0);self.assertLess(body.velocity.y,0)
        tree.input._keys_down.clear();tree.physics_process(1/60);self.assertEqual(body.velocity,Vector2());tree._exit_scene(tree.current_scene)

    def test_plugin_uninstall_is_recoverable_and_builtin_protected(self):
        from editor.plugin_system import PluginStore
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            folder=Path(tmp);package=folder/'source';package.mkdir();(package/'plugin.json').write_text(json.dumps({'id':'beta-test','api_version':1,'entry':'plugin.py'}));(package/'plugin.py').write_text('def setup(context):pass')
            store=PluginStore(folder/'installed');store.install(package);store.set_enabled('beta-test',True);archive=store.uninstall('beta-test')
            self.assertTrue((archive/'plugin.py').is_file());self.assertFalse((store.root/'beta-test').exists());self.assertFalse(store.state()['beta-test'])
            self.assertFalse(any(p['id']=='beta-test' for p in PluginStore(store.root).discover()))
            with self.assertRaises(ValueError):store.uninstall('../escape')
            builtin=next(p for p in store.discover() if p['builtin'])
            with self.assertRaises(ValueError):store.uninstall(builtin['id'])

if __name__=='__main__':unittest.main()
