"""Exercise studio authoring in both source and packaged editor."""
import copy
from pathlib import Path
from editor.hitbox_editor import HitboxEditor
from editor.animator_editor import AnimatorEditor
from engine.components.animator import Animator
from engine.resources.scene_serializer import SceneSerializer


def run(app, window, report):
    sprite=window.current_scene.find_node('Visual')
    original=copy.deepcopy(sprite.animations)
    clip=copy.deepcopy(sprite.animations['Run'])
    clip['hitboxes']={'0':[{'id':'sword','kind':'hit','rect':[28,17,16,12],'layer':1,'mask':1},
                           {'id':'body','kind':'hurt','rect':[12,14,18,30],'layer':1,'mask':1}]}
    dialog=HitboxEditor(clip,window.project_dir,window)
    dialog.select(0);dialog.show();app.processEvents()
    assert not dialog.canvas.image.isNull()
    dialog.grab().save(str(report.with_name(report.stem+'-hitboxes.png')))
    dialog.reject()
    sprite.animations['Run']=clip
    loaded=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(sprite))
    assert loaded.animations['Run']['hitboxes']==clip['hitboxes']
    sprite.animations=original
    component=Animator();component.states={'Idle':'Idle','Run':'Run','Jump':'Jump'}
    component.entry_state='Idle';component.parameters={'speed':0,'grounded':True}
    component.transitions=[{'from':'Idle','to':'Run','parameter':'speed','operator':'>','value':0.1},
                           {'from':'Run','to':'Idle','parameter':'speed','operator':'<=','value':0.1}]
    graph=AnimatorEditor(component,window);graph.show();app.processEvents()
    graph.grab().save(str(report.with_name(report.stem+'-animator.png')));graph.reject()
    return {'frame_hitbox_dialog':True,'frame_hitbox_roundtrip':True,'animator_graph_dialog':True}
