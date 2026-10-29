"""Noninteractive checks for the distributed runtime and native player."""
import json
from pathlib import Path
import sys
import tempfile

def run(app, report_path):
    from editor.project_hub import ProjectHub
    from editor.main_window import MainWindow
    from engine.nodes.game_object import GameObject
    from engine.nodes.camera2d import Camera2D
    from engine.core.scene import Scene
    from engine.resources.scene_serializer import SceneSerializer
    from engine.systems.cloud_scripts import compile_cloud
    from portable_export import export_portable
    report=Path(report_path).resolve();report.parent.mkdir(parents=True,exist_ok=True)
    results={'frozen':bool(getattr(sys,'frozen',False)), 'embedded_runtime':Path(sys.prefix).resolve()==Path(getattr(sys,'_MEIPASS', '.')).resolve()}
    hub=ProjectHub();results['hub']=hub is not None
    window=MainWindow();window.save_layout=lambda:None
    results['editor']=window is not None
    scope={'GameObject':GameObject}
    exec(compile_cloud('script RuntimeCheck extends GameObject:\n    func answer():\n        return 42\n'),scope)
    results['cloud_scripts']=scope['RuntimeCheck']().answer()==42
    with tempfile.TemporaryDirectory(prefix='runtime-check-',dir=report.parent) as tmp:
        base=Path(tmp);project=base/'project';project.mkdir();(project/'scenes').mkdir()
        scene=Scene('RuntimeCheck');camera=Camera2D();scene.root.add_child(camera)
        SceneSerializer.save_scene(scene,str(project/'scenes'/'main.scene'))
        (project/'project.json').write_text(json.dumps({'name':'RuntimeCheck','main_scene':'scenes/main.scene','window':{'width':320,'height':240}}),encoding='utf-8')
        window.open_project(str(project));window.play_game()
        results['play']=window.viewport.is_playing;window.viewport._tick_game();window.stop_game()
        template=Path(__file__).resolve().parent/'player-template'
        destination=export_portable(project,base/'output','RuntimeGame',template)
        results['export_without_python']=Path(destination,'RuntimeGame.exe' if sys.platform=='win32' else 'RuntimeGame').is_file()
    window.current_scene=None;window.close();hub.close()
    report.write_text(json.dumps(results,indent=2),encoding='utf-8')
    return 0 if all(results.values()) else 1
