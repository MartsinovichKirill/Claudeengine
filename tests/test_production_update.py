import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from engine.resources.game_data import GameData,template,save_document,validate_document
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.nodes.game_object import GameObject
from engine.nodes.camera2d import Camera2D
from engine.math.vector2 import Vector2
from engine.resources.scene_serializer import SceneSerializer
from engine.components.enemy_ai import EnemyAI,validate_graph
from engine.testing.project_checks import ProjectCheckRunner,validate_project,run_scene

ROOT=Path(__file__).resolve().parents[1]


def project(root):
    (root/'scripts').mkdir(); (root/'scenes').mkdir()
    (root/'project.json').write_text(json.dumps({'name':'Проверка','main_scene':'scenes/main.scene','window':{'width':320,'height':180}}),encoding='utf-8')
    node=GameObject('World'); node.add_child(Camera2D('Camera'))
    SceneSerializer.save_scene(Scene('Main',node),str(root/'scenes'/'main.scene'))
    return node


class GameDataTests(unittest.TestCase):
    def test_relocation_updates_references_inside_data_files(self):
        from editor.resource_refactor import relocate_resource
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); (root/'assets').mkdir(); (root/'assets'/'old.png').write_bytes(b'png')
            data=template('item'); data['fields']['icon']['value']='assets/old.png'; save_document('item.gamedata',data,root)
            relocate_resource(root,root/'assets'/'old.png',root/'assets'/'new.png')
            self.assertEqual(GameData('item.gamedata',root)['icon'],'assets/new.png')

    def test_shared_file_reload_and_mutation_does_not_change_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); data=template('weapon','Меч'); data['fields']['direction']={'type':'vector2','value':[1,2]}
            save_document('data/sword.gamedata',data,root)
            first=GameData('data/sword.gamedata',root); second=GameData('data/sword.gamedata',root)
            self.assertEqual(first['damage'],1.); vector=first['direction']; vector.x=999; self.assertEqual(first['direction'].x,1)
            data['fields']['damage']['value']=15; save_document('data/sword.gamedata',data,root)
            self.assertEqual(first['damage'],15.); self.assertEqual(second['damage'],15.)
            self.assertEqual(first.get('absent',8),8)

    def test_validation_and_failed_save_keep_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); data=template('enemy','Враг'); save_document('enemy.gamedata',data,root); original=(root/'enemy.gamedata').read_bytes()
            for bad in [True,'3',float('nan')]:
                data['fields']['health']['value']=bad
                with self.assertRaises(ValueError): save_document('enemy.gamedata',data,root)
            self.assertEqual((root/'enemy.gamedata').read_bytes(),original)
            with self.assertRaises(ValueError): GameData('../outside.gamedata',root)
            data=template('item'); data['fields']['icon']['value']='missing.png'
            with self.assertRaisesRegex(ValueError,'не найден'): validate_document(data,root,True)

    def test_cloud_script_reads_file_and_data_source_roundtrip(self):
        from engine.systems.cloud_scripts import CloudRuntime
        from engine.components.data_source import DataSource
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); (root/'scripts').mkdir(); save_document('data/sword.gamedata',template('weapon','Sword'),root)
            (root/'scripts'/'read.cloud').write_text('func damage():\n    return load_data("data/sword.gamedata")["damage"]\n',encoding='utf-8')
            self.assertEqual(CloudRuntime(root/'scripts').load('read.cloud').damage(),1.)
            node=GameObject(); source=node.add_component(DataSource()); source.data_path='data/sword.gamedata'
            node._asset_manager=SimpleNamespace(project_dir=str(root)); self.assertEqual(source.read('damage'),1.)
            restored=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(node))
            self.assertEqual(restored.get_component('DataSource').data_path,source.data_path)


class EnemyTests(unittest.TestCase):
    def setup_enemy(self):
        root=GameObject('World'); enemy=GameObject('Enemy'); body=enemy.add_component('Rigidbody2D'); ai=enemy.add_component(EnemyAI())
        player=GameObject('Player'); player.position=Vector2(500,0); root.add_child(enemy); root.add_child(player)
        tree=SceneTree(); tree.change_scene(Scene('World',root)); return tree,enemy,player,body,ai

    def test_patrol_chase_attack_lost_and_vertical_velocity(self):
        tree,enemy,player,body,ai=self.setup_enemy(); body.velocity=Vector2(0,77); hits=[]; ai.connect('attack_requested',lambda target:hits.append(target.name))
        ai._physics_process(.1); self.assertEqual(ai.state,'patrol'); self.assertEqual(body.velocity,Vector2(80,77))
        enemy.position=Vector2(121,0); ai._physics_process(.1); self.assertLess(body.velocity.x,0)
        player.position=Vector2(200,0); ai._physics_process(.1); self.assertEqual(ai.state,'chase'); self.assertGreater(body.velocity.x,0)
        player.position=Vector2(140,0); ai._physics_process(.1); self.assertEqual(ai.state,'attack'); self.assertEqual(body.velocity.x,0); self.assertEqual(hits,['Player'])
        for _ in range(3): ai._physics_process(.1)
        self.assertEqual(len(hits),1)
        player.position=Vector2(1000,0); ai._physics_process(.1); self.assertEqual(ai.state,'patrol')
        ai.enabled=False; self.assertEqual(body.velocity.x,0)

    def test_parameter_and_timeout_transitions_and_serialization(self):
        tree,enemy,player,body,ai=self.setup_enemy()
        data=copy.deepcopy(ai.graph); data['states']['rest']={'action':'wait','duration':.2}; data['entry']='rest'
        data['parameters']={'health':3}; data['transitions']=[{'from':'rest','to':'patrol','condition':'timeout'},{'from':'*','to':'rest','condition':'parameter','parameter':'health','operator':'<=','value':0}]
        ai.graph=validate_graph(data); ai._ready(); ai._physics_process(.1); self.assertEqual(ai.state,'rest')
        ai._physics_process(.1); self.assertEqual(ai.state,'patrol'); ai.set_parameter('health',0); ai._physics_process(.01); self.assertEqual(ai.state,'rest')
        restored=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(enemy))
        self.assertEqual(restored.get_component('EnemyAI').graph,data)
        data['transitions'][0]['to']='absent'
        with self.assertRaises(ValueError): validate_graph(data)


class ProjectChecksTests(unittest.TestCase):
    def test_cancelled_run_is_not_a_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); project(root)
            runner=ProjectCheckRunner(root,root/'.reports'/'result.json'); runner.cancel(); report=runner.run()
            self.assertTrue(report['cancelled']); self.assertFalse(report['passed'])

    def test_validation_finds_bad_data_and_unused_script_without_execution(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); project(root)
            (root/'scripts'/'broken.cloud').write_text('this is invalid !',encoding='utf-8')
            (root/'scripts'/'side_effect.py').write_text('raise RuntimeError("not executed")',encoding='utf-8')
            (root/'bad.gamedata').write_text('{}')
            results=validate_project(root)
            self.assertEqual(len(results),2); self.assertTrue(all('not executed' not in row['message'] for row in results))

    def test_runtime_component_exception_is_a_failed_scene(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); node=project(root)
            (root/'scripts'/'broken.cloud').write_text('script Broken extends Behaviour:\n    func _process(delta):\n        return 1 / 0\n',encoding='utf-8')
            node.add_component('ScriptBehaviour').script_path='scripts/broken.cloud'
            SceneSerializer.save_scene(Scene('Main',node),str(root/'scenes'/'main.scene'))
            result=run_scene(root,'scenes/main.scene',3); self.assertEqual(result['status'],'failed'); self.assertIn('ZeroDivisionError',''.join(result['errors']))

    def test_subprocess_report_passes_and_original_scene_unchanged(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='Проект ') as folder:
            root=Path(folder); node=project(root); original=(root/'scenes'/'main.scene').read_bytes()
            runner=ProjectCheckRunner(root,root/'.reports'/'result.json',frames=3,timeout=10)
            report=runner.run(); self.assertTrue(report['passed'],report)
            self.assertEqual((root/'scenes'/'main.scene').read_bytes(),original); self.assertTrue((root/'.reports'/'result.md').is_file())

    def test_infinite_script_is_stopped_by_timeout(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); project(root)
            (root/'scripts'/'hang.py').write_text('while True:\n    pass\n',encoding='utf-8')
            report=ProjectCheckRunner(root,root/'.reports'/'result.json',frames=1,timeout=1).run()
            self.assertFalse(report['passed']); self.assertEqual(report['results'][0]['status'],'timeout')


if __name__=='__main__': unittest.main()
