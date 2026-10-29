import os,json,copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import pygame
from engine.core.scene import Scene
from engine.core.scene_tree import SceneTree
from engine.nodes.node2d import Node2D
from engine.nodes.animated_sprite import AnimatedSprite2D
from engine.math.vector2 import Vector2
from engine.resources.scene_serializer import SceneSerializer
from engine.systems.frame_hitboxes import FrameHitboxSystem,validate_boxes,overlaps
from engine.systems.animation_system import AnimationSystem
from engine.systems.cutscenes import CutscenePlayer,validate_clip
from engine.systems.audio_system import AudioSystem
from engine.nodes.audio_stream import AudioStreamPlayer
from engine.components.animator import Animator
ROOT=Path(__file__).resolve().parents[1]


def box(kind='hit',rect=(0,0,10,10),ident='attack',layer=1,mask=1):
    return dict(id=ident,kind=kind,rect=list(rect),layer=layer,mask=mask)


def sprite(name,boxes,position=(0,0)):
    s=AnimatedSprite2D(name);s.position=Vector2(position);s.frames=[pygame.Surface((16,16))]
    s.animations={'Attack':{'frames':['one.png'],'fps':10,'loop':False,'hitboxes':{'0':boxes}}};s.animation='Attack'
    return s


class HitboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):pygame.init();pygame.display.set_mode((1,1))
    def pair(self):
        root=Node2D();a=sprite('a',[box()]);b=sprite('b',[box('hurt',ident='body')]);root.add_child(a);root.add_child(b)
        tree=SceneTree();tree.change_scene(Scene('combat',root));return a,b,tree,FrameHitboxSystem(tree)
    def test_once_per_active_attack_and_reactivation(self):
        a,b,tree,system=self.pair();hits=[];a.connect('hitbox_entered',lambda *args:hits.append(args))
        system.update();system.update();self.assertEqual(len(hits),1);self.assertIs(hits[0][0],b)
        b.position.x=100;system.update();b.position.x=0;system.update();self.assertEqual(len(hits),1)
        a.frame=1;system.update();a.frame=0;system.update();self.assertEqual(len(hits),2)
        a._hitbox_cycle+=1;system.update();self.assertEqual(len(hits),3)
    def test_hidden_mask_and_same_actor(self):
        a,b,tree,system=self.pair();hits=[];a.connect('hitbox_entered',lambda *args:hits.append(args))
        b.visible=False;system.update();self.assertFalse(hits)
        b.visible=True;a.animations['Attack']['hitboxes']['0'][0]['mask']=2;system.update();self.assertFalse(hits)
    def test_flip_scale_rotation_world_polygon(self):
        s=sprite('s',[box(rect=(0,0,4,6))]);s.flip_h=True;s.scale=Vector2(2,3);s.rotation=90
        points=s.get_active_hitboxes()[0]['points']
        self.assertAlmostEqual(points[0].x,24);self.assertAlmostEqual(points[0].y,16)
        self.assertFalse(overlaps([Vector2(0,0),Vector2(1,0),Vector2(1,1),Vector2(0,1)], [Vector2(2,0),Vector2(3,0),Vector2(3,1),Vector2(2,1)]))
    def test_hitboxes_roundtrip_and_invalid_rejected(self):
        s=sprite('s',[box()]);loaded=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(s));self.assertEqual(loaded.animations,s.animations)
        for boxes in ({'0':[box(rect=(0,0,-1,2))]},{'a':[]},{'0':[box(),box()]}):
            with self.assertRaises(ValueError):validate_boxes(boxes)
    def test_skipped_animation_frame_is_checked(self):
        a,b,tree,system=self.pair()
        surfaces=[pygame.Surface((16,16)) for _ in range(4)]
        manager=SimpleNamespace(get_texture=lambda path:surfaces[int(path)])
        a.animations={'Attack':{'frames':['0','1','2','3'],'fps':20,'loop':False,'hitboxes':{'1':[box()]}}};a._asset_manager=manager;a._loaded_animation=None
        b._loaded_animation=('Attack',('one.png',),10.,False)
        b.playing=False
        hits=[];a.connect('hitbox_entered',lambda *args:hits.append(args));AnimationSystem(tree).update(.16)
        self.assertEqual(len(hits),1)


class CinematicEventTests(unittest.TestCase):
    def scene(self):
        node=Node2D('Root');node.fire=Mock();scene=Scene('x',node);tree=SceneTree();tree.change_scene(scene)
        return node,scene,tree
    def event(self):return {'kind':'event','start':.2,'duration':0,'target':'.','method':'fire','args':[3]}
    def test_seek_never_calls_events_update_calls_once(self):
        node,scene,tree=self.scene();p=CutscenePlayer(tree);p.bind(scene,{'tracks':[self.event()]})
        p.seek(.2);node.fire.assert_not_called();p.seek(0);p.playing=True;p.update(.3);p.update(.1)
        node.fire.assert_called_once_with(3)
    def test_preview_never_calls_even_while_playing(self):
        node,scene,tree=self.scene();p=CutscenePlayer();p.bind(scene,{'tracks':[self.event()]});p.playing=True;p.update(.3);node.fire.assert_not_called()
    def test_event_validation_and_bind_atomic(self):
        for t in [dict(self.event(),method='_exit_tree'),dict(self.event(),args={}),dict(self.event(),start=-1)]:
            with self.assertRaises(ValueError):validate_clip({'tracks':[t]})
    def test_audio_track_starts_and_stops_own_player(self):
        node,scene,tree=self.scene();audio=AudioStreamPlayer('Sound');audio.play=Mock();audio.stop=Mock();node.add_child(audio)
        p=CutscenePlayer(tree);p.bind(scene,{'tracks':[dict(kind='audio',start=0,duration=1,target='Sound',method='play',args=[])]})
        p.playing=True;p.update(.5);audio.play.assert_called_once();p.stop(True);audio.stop.assert_called_once()


class StudioUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def window(self,tmp):
        from PyQt6.QtWidgets import QWidget
        window=QWidget();window.settings={'audio':{'music':.5}};window.project_dir=tmp
        Path(tmp,'project.json').write_text('{}')
        tree=SceneTree();tree.audio_system=AudioSystem(tree)
        window.viewport=SimpleNamespace(scene_tree=tree,camera=SimpleNamespace(center=Vector2(),zoom=1),update=lambda:None)
        window.current_scene=Scene('X',Node2D());window.assets=SimpleNamespace(refresh=lambda:None)
        return window
    def test_mixer_solo_audition_and_cancel_restore(self):
        from editor.cinema_tools import MixerDialog
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            w=self.window(tmp);audio=w.viewport.scene_tree.audio_system;old=copy.deepcopy(audio.bus_volumes)
            m=MixerDialog(w);m.solos['music'].setChecked(True);self.assertEqual(audio.gain('sfx'),0);self.assertGreater(audio.gain('music'),0)
            m.reject();self.assertEqual(audio.bus_volumes,old);self.assertFalse(audio.muted)
    def test_mixer_save_excludes_solo(self):
        from editor.cinema_tools import MixerDialog
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            w=self.window(tmp);m=MixerDialog(w);m.solos['music'].setChecked(True);m.controls['music'][0].setValue(.25);m.save()
            data=json.loads(Path(tmp,'project.json').read_text());self.assertEqual(data['audio']['volumes']['music'],.25);self.assertEqual(data['audio']['muted'],[])
            self.assertGreater(w.viewport.scene_tree.audio_system.gain('sfx'),0)
    def test_cutscene_inspector_edits_and_event_roundtrip(self):
        from editor.cinema_tools import CutsceneDialog
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            w=self.window(tmp);dialog=CutsceneDialog(w);dialog.add_track();dialog.track_fields[0].setText('2');dialog.apply_inspector()
            self.assertEqual(dialog.data()['tracks'][0]['start'],2)
            dialog.kind_control.setCurrentIndex(2);dialog.track_fields[4].setText('fire');dialog.track_fields[5].setText('[3]');dialog.apply_inspector()
            data=dialog.data();self.assertEqual(data['tracks'][0]['kind'],'event');self.assertEqual(data['tracks'][0]['args'],[3]);dialog.reject()
    def test_hitbox_editor_cancel_isolation_and_copy_undo(self):
        from editor.hitbox_editor import HitboxEditor
        clip={'frames':['a.png','b.png'],'fps':10,'loop':True,'hitboxes':{'0':[box()]}}
        old=copy.deepcopy(clip);dialog=HitboxEditor(clip,ROOT);dialog.set_frame(1);dialog.previous();self.assertEqual(dialog.boxes(),clip['hitboxes']['0']);dialog.undo();self.assertEqual(dialog.boxes(),[]);dialog.reject();self.assertEqual(clip,old)
    def test_animator_positions_saved_without_mutating_component(self):
        from editor.animator_editor import AnimatorEditor
        c=Animator();c.states={'Idle':'Idle','Run':'Run'};c.entry_state='Idle';c.parameters={'speed':0}
        dialog=AnimatorEditor(c);dialog.editor_positions={'Run':[100,250]};dialog.accept_data();self.assertEqual(dialog.result_data['editor_positions']['Run'],[100,250]);self.assertEqual(c.editor_positions,{})
        c._deserialize_data(dialog.result_data);self.assertEqual(c.editor_positions['Run'],[100,250])
    def test_timeline_drag_preserves_event_type(self):
        from editor.cinema_tools import CutsceneDialog
        from editor.studio_workspace import TimelineBlock
        from PyQt6.QtTest import QTest
        from PyQt6.QtCore import Qt,QPointF
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            w=self.window(tmp);dialog=CutsceneDialog(w);dialog.add_track();dialog.kind_control.setCurrentIndex(2)
            dialog.show();self.app.processEvents()
            block=next(i for i in dialog.timeline.scene.items() if isinstance(i,TimelineBlock))
            point=dialog.timeline.mapFromScene(block.mapToScene(QPointF(15,15)))
            end=point+dialog.timeline.mapFromScene(QPointF(90,0))-dialog.timeline.mapFromScene(QPointF(0,0))
            QTest.mousePress(dialog.timeline.viewport(),Qt.MouseButton.LeftButton,pos=point)
            QTest.mouseMove(dialog.timeline.viewport(),end,20)
            QTest.mouseRelease(dialog.timeline.viewport(),Qt.MouseButton.LeftButton,pos=end)
            self.app.processEvents()
            self.assertEqual(dialog.track_kind(0),'event');self.assertGreater(dialog.data()['tracks'][0]['start'],.5)
            dialog.reject()

    def test_sprite_frame_reorder_moves_hitbox_metadata(self):
        from editor.sprite_frames_editor import SpriteFramesEditor
        s=sprite('s',[box()]);s.animations['Attack']['frames']=['a.png','b.png'];dialog=SpriteFramesEditor(s,ROOT)
        item=dialog.frames.takeItem(0);dialog.frames.addItem(item);dialog.flush()
        self.assertIn('1',dialog.clips['Attack']['hitboxes']);self.assertNotIn('0',dialog.clips['Attack']['hitboxes']);dialog.timer.stop();dialog.reject()


if __name__=='__main__':unittest.main()
