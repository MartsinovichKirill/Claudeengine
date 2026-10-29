import copy
import json
import logging
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from engine.core.node import Node
from engine.core.scene import Scene
from engine.nodes.game_object import GameObject
from engine.nodes.animation_player import AnimationPlayer, Animation, read_property
from engine.nodes.particles2d import Particles2D
from engine.systems.particle_system import ParticleSystem
from engine.resources.scene_serializer import SceneSerializer
from engine.math.vector2 import Vector2
from editor.recovery import RecoveryStore

ROOT=Path(__file__).resolve().parents[1]


class AnimationEventTests(unittest.TestCase):
    def create(self,loop=False):
        target=GameObject('Player'); player=AnimationPlayer(); target.add_child(player)
        clip=player.add_animation('attack',1,loop); hits=[]
        target.hit=lambda value: hits.append(value)
        return target,player,clip,hits

    def test_events_start_end_and_large_step_across_loops(self):
        target,player,clip,hits=self.create(True)
        for time,name in [(0,'start'),(.25,'hit'),(1,'end')]: clip.add_event(time,'hit',[name])
        player.play('attack'); player._process(2.5)
        self.assertEqual(hits,['start','hit','end','start','hit','end','start','hit'])
        player._process(.1); self.assertEqual(len(hits),8)
        self.assertAlmostEqual(player.current_time,.6)

    def test_seek_is_silent_pause_and_restart(self):
        _,player,clip,hits=self.create(); clip.add_event(.5,'hit',[1]); clip.add_event(1,'hit',[2])
        player.play('attack'); player.seek(.75); self.assertEqual(hits,[])
        player.pause(); player._process(.5); self.assertEqual(hits,[])
        player.resume(); player._process(.25); player._process(2)
        self.assertEqual(hits,[2]); self.assertFalse(player.playing)
        player.play('attack'); player._process(1); self.assertEqual(hits,[2,1,2])

    def test_callback_can_stop_or_switch_animation(self):
        target,player,clip,hits=self.create(True); clip.add_event(.2,'hit',[1]); clip.add_event(.3,'hit',[2])
        player.add_animation('idle',2)
        target.hit=lambda value: player.play('idle')
        player.play('attack'); player._process(.7)
        self.assertEqual(player.current_animation,'idle'); self.assertEqual(player.current_time,0)

    def test_signal_method_on_behaviour_and_bad_method(self):
        target,player,clip,hits=self.create()
        from engine.components.behaviour import ScriptBehaviour
        wrapper=target.add_component(ScriptBehaviour()); wrapper.instance=SimpleNamespace(step=lambda value:hits.append(value))
        clip.add_event(.1,'step',['sound']); clip.add_event(.2,'dust',[2],'signal')
        player.connect('animation_event',lambda name,args:hits.append((name,args)))
        player.play('attack'); player._process(.3)
        self.assertEqual(hits,['sound',('dust',[2])])
        clip.add_event(.4,'missing',[])
        with self.assertRaisesRegex(ValueError,'missing'): player._process(.2)

    def test_event_roundtrip_and_old_scene_compatibility(self):
        target,player,clip,_=self.create(); player.autoplay='attack'; clip.add_event(.25,'hit',[{'damage':2}])
        clip.add_key('position',0,Vector2()); clip.add_key('position',1,Vector2(100,0))
        restored=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(target)).get_children()[0]
        self.assertEqual(restored.get_animation('attack').events,clip.events)
        self.assertEqual(restored.autoplay,'attack')
        old=Animation.from_dict({'name':'old','keys':{}}); self.assertEqual(old.events,[])

    def test_event_validation_and_event_zero_once_at_exact_wrap(self):
        _,player,clip,hits=self.create(True)
        for time,name,args in [(-1,'hit',[]),(2,'hit',[]),(.1,'_ready',[]),(.1,'hit',{})]:
            with self.assertRaises(ValueError): clip.add_event(time,name,args)
        clip.add_event(0,'hit',[0]); clip.add_event(1,'hit',[1]); player.play('attack')
        player._process(1); self.assertEqual(hits,[0,1,0]); player._process(.01); self.assertEqual(hits,[0,1,0])

    def test_queued_clip_starts_at_end_without_extra_update(self):
        _,player,clip,hits=self.create(); clip.add_event(1,'hit',['end']); player.add_animation('idle')
        player.play('attack'); player.queue('idle'); player._process(1)
        self.assertEqual(player.current_animation,'idle'); self.assertEqual(hits,['end'])

    def test_component_tracks_and_restoration(self):
        target,player,clip,_=self.create(); renderer=target.add_component('SpriteRenderer')
        original=renderer.color
        clip.add_key('SpriteRenderer.color',0,(255,0,0,255)); clip.add_key('SpriteRenderer.color',1,(0,0,0,0))
        player.play('attack'); player._process(.5)
        self.assertEqual(tuple(renderer.color),(128,0,0,128)); player._exit_tree()
        self.assertEqual(renderer.color,original)


class ParticleTests(unittest.TestCase):
    def test_one_shot_finishes_and_restart_works(self):
        emitter=Particles2D(); emitter.amount=30; emitter.one_shot=True
        system=ParticleSystem(None); system._update_emitter(emitter,.01)
        self.assertEqual(emitter.get_particle_count(),30); self.assertFalse(emitter.emitting)
        for _ in range(200): system._update_emitter(emitter,.01)
        self.assertEqual(emitter.get_particle_count(),0)
        emitter.restart(); system._update_emitter(emitter,.01); self.assertEqual(emitter.get_particle_count(),30)

    def test_capacity_and_color_size_curves(self):
        emitter=Particles2D(); emitter.amount=20; emitter.lifetime=2
        system=ParticleSystem(None)
        for _ in range(100):
            system._update_emitter(emitter,.1); self.assertLessEqual(emitter.get_particle_count(),20)
        emitter.color=(200,100,0,200); emitter.end_color=(0,0,100,0); emitter.end_size_ratio=2
        emitter._lifetimes[0]=.5; emitter._max_lifetimes[0]=1; emitter.particle_size=4
        self.assertEqual(emitter.particle_style(0),((100,50,50,100),6))

    def test_presets_validation_scene_roundtrip_and_undo(self):
        from editor.particle_editor import apply_particle_values,particle_values,PRESETS
        from editor.undo_stack import ParticleSettingsCommand
        emitter=Particles2D(); before=particle_values(emitter)
        after={**before,**PRESETS['Дым']}
        command=ParticleSettingsCommand(emitter,before,after); command.redo()
        restored=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(emitter))
        self.assertEqual(tuple(restored.end_color),(60,65,70,0)); self.assertEqual(restored.end_size_ratio,2.5)
        command.undo(); self.assertEqual(particle_values(emitter),before)
        baseline=particle_values(emitter)
        with self.assertRaises(ValueError): apply_particle_values(emitter,{'speed':55,'color':[999,0,0,0]})
        self.assertEqual(particle_values(emitter),baseline)

    def test_alpha_visible_in_runtime_and_source_texture_unchanged(self):
        import pygame
        from engine.nodes.camera2d import CameraState
        emitter=Particles2D(); emitter.color=(255,0,0,128); emitter.one_shot=True; emitter.amount=1
        system=ParticleSystem(None); system._update_emitter(emitter,.01)
        emitter._positions[0]=[0,0]; emitter._lifetimes[0]=0
        camera=CameraState(Vector2(),1,Vector2(100,100)); surface=pygame.Surface((100,100)); surface.fill((0,0,0))
        emitter._draw_local(surface,Vector2(50,50),camera)
        self.assertIn(surface.get_at((50,50)).r,range(126,130))
        emitter._texture=pygame.Surface((4,4),pygame.SRCALPHA); emitter._texture.fill((255,255,255,255))
        emitter._draw_local(surface,Vector2(50,50),camera)
        self.assertEqual(tuple(emitter._texture.get_at((0,0))),(255,255,255,255))


class RecoveryTests(unittest.TestCase):
    def test_generations_corrupt_latest_fallback_and_project_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            store=RecoveryStore(temp)
            for n in range(8): store.save([{'path':'scenes/Моя сцена.scene','scene':{'name':str(n),'root':{}}}],[])
            self.assertEqual(len(list(store.directory.glob('*.json'))),5)
            newest=sorted(store.directory.glob('*.json'))[-1]; newest.write_text('{broken',encoding='utf-8')
            self.assertEqual(store.load()['scenes'][0]['scene']['name'],'6')
            with self.assertRaises(ValueError): store.relative(Path(temp).parent/'other.scene')
            source=Path(temp)/'source.txt'; source.write_text('keep'); store.discard(); self.assertTrue(source.exists())

    def test_atomic_failure_keeps_prior_snapshot(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            store=RecoveryStore(temp); store.save([], [{'path':'scripts/a.cloud','text':'old'}])
            with patch('editor.recovery.os.replace',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): store.save([], [{'path':'scripts/a.cloud','text':'new'}])
            self.assertEqual(store.load()['scripts'][0]['text'],'old'); self.assertFalse(list(store.directory.glob('*.tmp')))


class DiagnosticTests(unittest.TestCase):
    def test_syntax_and_runtime_locations_with_hints(self):
        from engine.systems.diagnostics import explain_exception
        try: compile('value = (1 + )','C:/Игры/scripts/player.cloud','exec')
        except SyntaxError as error:
            diag=explain_exception(error); self.assertEqual(diag.line,1); self.assertIn('скобки',diag.hint); self.assertIn('player.cloud',diag.path)
        try: exec(compile('answer = 1 / 0','C:/Игры/scripts/player.cloud','exec'),{})
        except ZeroDivisionError as error:
            diag=explain_exception(error); self.assertIn('player.cloud',diag.path); self.assertIn('Деление на ноль',diag.message)


if __name__=='__main__': unittest.main()
