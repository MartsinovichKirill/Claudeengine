"""Exercise new dialogs and runtime services against isolated fixtures."""
import copy
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from PyQt6.QtGui import QImage
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.nodes.game_object import GameObject
from engine.math.vector2 import Vector2
from editor.cinema_tools import MixerDialog,CutsceneDialog


def run(app,window,report):
    results={}
    mixer=MixerDialog(window);mixer.show();app.processEvents()
    mixer.grab().save(str(report.parent/(report.stem+'-mixer.png')));mixer.reject()
    results['audio_mixer_dialog']=len(mixer.controls)==4
    scene=window.current_scene;position=copy.deepcopy(scene.root.position)
    dialog=CutsceneDialog(window);dialog.add_track();dialog.cursor.setValue(.5);dialog.scrub();app.processEvents()
    results['cutscene_preview']=scene.root.position==Vector2(50,0)
    dialog.show();app.processEvents();dialog.grab().save(str(report.parent/(report.stem+'-cutscene.png')))
    dialog.reject();results['cutscene_preview_restored']=scene.root.position==position
    with tempfile.TemporaryDirectory(dir=report.parent) as tmp:
        root=Path(tmp);(root/'project.json').write_text('{}')
        Scene('Second',GameObject()).save(str(root/'second.scene'))
        tree=SceneTree();tree.script_system=SimpleNamespace(project_dir=tmp);first=Scene('First',GameObject());tree.change_scene(first)
        tree.shared_data['score']=7;tree.load_scene('second.scene');deferred=tree.current_scene is first;tree.flush_scene_change()
        results['scene_transition']=deferred and tree.current_scene.name=='Second' and tree.shared_data['score']==7
        from editor.sprite_slicer import SpriteSlicer
        image=QImage(32,32,QImage.Format.Format_ARGB32);image.fill(0xffffffff);image.save(str(root/'sheet.png'))
        slicer=SpriteSlicer(root/'sheet.png');out=root/'parts';out.mkdir();slicer.save_parts(out);slicer.reject()
        results['png_only_slicing']=bool(list(out.glob('*.png'))) and not list(out.glob('*.json'))
        from engine.resources.teamwork import prepare_project,reserve,release,lock_path
        prepare_project(root);reserve(root/'second.scene');locked=lock_path(root/'second.scene').is_file();release(root/'second.scene')
        results['team_project_setup']=locked and (root/'.gitattributes').is_file() and not lock_path(root/'second.scene').exists()
        scene=Scene.load(str(root/'second.scene'));(root/'second.scene').write_text('{"external":true}')
        try:scene.save(str(root/'second.scene'));results['external_edit_protection']=False
        except RuntimeError:results['external_edit_protection']=True
    return results
