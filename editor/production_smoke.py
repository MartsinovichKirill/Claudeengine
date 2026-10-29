"""Frozen package checks for project-production features."""
import json
from pathlib import Path
from engine.nodes.game_object import GameObject
from engine.nodes.camera2d import Camera2D
from engine.components.enemy_ai import EnemyAI
from engine.core.scene import Scene
from engine.resources.scene_serializer import SceneSerializer
from engine.resources.game_data import GameData
from engine.testing.project_checks import ProjectCheckRunner
from editor.game_data_editor import GameDataEditor
from editor.enemy_editor import EnemyEditor
from editor.project_tests_dialog import ProjectTestsDialog


def run(app,window,report):
    root=Path(window.project_dir)/'.checks-fixture'; (root/'scripts').mkdir(parents=True,exist_ok=True); (root/'data').mkdir(exist_ok=True); (root/'scenes').mkdir(exist_ok=True)
    (root/'project.json').write_text(json.dumps({'name':'ProductionCheck','main_scene':'scenes/main.scene','window':{'width':320,'height':180}}),encoding='utf-8')
    data_editor=GameDataEditor(root,parent=window); data_editor.resize(900,620); data_editor.name.setText('Ржавый меч'); data_editor.table.item(0,2).setText('4')
    data_editor.show(); app.processEvents(); data_editor.grab().save(str(report.parent/(report.stem+'-data.png')))
    path=root/'data'/'sword.gamedata'; data_editor.path=str(path); data_editor.save()
    world=GameObject('World'); world.add_child(Camera2D('Camera'))
    player=GameObject('Player'); player.position.x=180; world.add_child(player)
    enemy=GameObject('Enemy'); enemy.add_component('Rigidbody2D'); enemy.add_component('BoxCollider2D'); ai=enemy.add_component(EnemyAI()); world.add_child(enemy)
    editor=EnemyEditor(ai,window); editor.show(); app.processEvents(); editor.grab().save(str(report.parent/(report.stem+'-enemy.png'))); editor.reject()
    (root/'scripts'/'probe.cloud').write_text('script Probe extends Behaviour:\n    func _ready():\n        let weapon = load_data("data/sword.gamedata")\n        if weapon["damage"] != 4:\n            raise ValueError("Wrong game data")\n',encoding='utf-8')
    world.add_component('ScriptBehaviour').script_path='scripts/probe.cloud'
    SceneSerializer.save_scene(Scene('Main',world),str(root/'scenes'/'main.scene'))
    checker=ProjectCheckRunner(root,root/'.cloud-test-reports'/'smoke.json',frames=5,timeout=20)
    result=checker.run()
    dialog=ProjectTestsDialog(root,window); dialog.show()
    for row in result['results']: dialog.add_record(row)
    dialog.report_path=checker.report_path; dialog.completed(result); app.processEvents()
    dialog.grab().save(str(report.parent/(report.stem+'-project-tests.png'))); dialog.reject()
    window.resize(1500,950); app.processEvents(); window.grab().save(str(report.parent/(report.stem+'-workspace.png')))
    return {'game_data_editor':GameData(path,root)['damage']==4,'enemy_graph_editor':bool(editor.cards),
            'project_checks_subprocess':result['passed'],'project_check_report':checker.report_path.is_file()}
