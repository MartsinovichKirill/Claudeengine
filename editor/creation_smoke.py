"""Creation tools exercised by the existing frozen-editor smoke command."""
from pathlib import Path
from editor.animation_editor import AnimationEditorDialog
from editor.particle_editor import ParticleEditorDialog
from editor.recovery import RecoveryStore
from engine.nodes.game_object import GameObject
from engine.nodes.animation_player import AnimationPlayer
from engine.nodes.particles2d import Particles2D
from engine.math.vector2 import Vector2


def run(app,window,report):
    result={}
    hero=GameObject('PreviewCheck'); hero.add_component('SpriteRenderer')
    hero.position=Vector2(30,40)
    player=AnimationPlayer(); hero.add_child(player)
    clip=player.add_animation('move',1,True)
    clip.add_key('position',0,Vector2()); clip.add_key('position',1,Vector2(100,0))
    clip.add_event(.25,'footstep',['stone'],'signal')
    dialog=AnimationEditorDialog(player,window)
    dialog.resize(1000,720); dialog.show(); app.processEvents(); dialog._seek_preview(.5)
    result['animation_preview']=hero.position==Vector2(50,0)
    dialog.grab().save(str(report.parent/(report.stem+'-animation.png')))
    dialog.reject()
    result['animation_preview_restored']=hero.position==Vector2(30,40)
    hits=[]; player.connect('animation_event',lambda name,args:hits.append((name,args)))
    player.play('move'); player._process(2.5)
    result['animation_events']=len(hits)==3
    particles=Particles2D(); effects=ParticleEditorDialog(particles,window.project_dir,window)
    effects.resize(1000,720); effects.show(); effects.load_preset(2)
    for _ in range(20): effects.preview.system._update_emitter(effects.preview_emitter,.02)
    app.processEvents(); effects.grab().save(str(report.parent/(report.stem+'-particles.png')))
    effects.apply()
    result['particle_editor']=effects.result_values is not None and effects.result_values['amount']==120
    result['particle_editor_isolated']=particles.amount==64
    store=RecoveryStore(window.project_dir)
    store.save([{'path':'','scene':{'name':'unsaved','root':{'type':'Node','name':'Root'}}}],[])
    result['recovery_snapshot']=store.load()['scenes'][0]['scene']['name']=='unsaved'
    store.discard()
    from engine.systems.diagnostics import explain_exception
    try: exec(compile('1/0',str(Path(window.project_dir)/'scripts'/'smoke.cloud'),'exec'),{})
    except ZeroDivisionError as error: window.console.diagnostic_requested.emit(explain_exception(error,window.project_dir))
    result['readable_errors']=bool(window.console.problems.entries)
    return result
