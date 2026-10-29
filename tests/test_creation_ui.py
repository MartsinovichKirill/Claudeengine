import copy
import json
import logging
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication,QMainWindow,QPlainTextEdit
from engine.core.scene import Scene
from engine.nodes.game_object import GameObject
from engine.nodes.animation_player import AnimationPlayer
from engine.math.vector2 import Vector2
from engine.nodes.particles2d import Particles2D
from engine.resources.scene_serializer import SceneSerializer
from editor.animation_editor import AnimationEditorDialog
from editor.particle_editor import ParticleEditorDialog, particle_values
from editor.recovery import RecoveryController
from editor.console_panel import ConsolePanel, ConsoleLogHandler

ROOT=Path(__file__).resolve().parents[1]
APP=QApplication.instance() or QApplication([])


class EditorTests(unittest.TestCase):
    def test_animation_preview_never_calls_events_and_cancel_restores_everything(self):
        target=GameObject(); target.position=Vector2(10,20); player=AnimationPlayer(); target.add_child(player)
        clip=player.add_animation('move'); clip.add_key('position',0,Vector2()); clip.add_key('position',1,Vector2(100,0))
        clip.add_event(.5,'not_existing',[])
        player.autoplay='move'; before=copy.deepcopy(player._serialize_data())
        dialog=AnimationEditorDialog(player); dialog._seek_preview(.5)
        self.assertEqual(target.position,Vector2(50,0)); clip.add_key('rotation',.5,30)
        dialog.autoplay_edit.setText(''); player.autoplay=''; dialog.reject()
        self.assertEqual(target.position,Vector2(10,20)); self.assertEqual(player._serialize_data(),before)
        self.assertFalse(dialog.preview_timer.isActive())

    def test_animation_accept_restores_pose_and_autoplay_undo(self):
        from editor.undo_stack import NodeDataCommand
        target=GameObject(); player=AnimationPlayer(); target.add_child(player)
        clip=player.add_animation('move'); clip.add_key('position',0,Vector2(12,0))
        dialog=AnimationEditorDialog(player); dialog.autoplay_edit.setText('move'); dialog._seek_preview(0); dialog._accept()
        self.assertEqual(target.position,Vector2())
        command=NodeDataCommand(player,dialog.before_data,player._serialize_data()); command.undo(); self.assertEqual(player.autoplay,'')
        command.redo(); self.assertEqual(player.autoplay,'move')

    def test_precise_key_delete_and_frames_import(self):
        target=GameObject(); renderer=target.add_component('SpriteRenderer'); player=AnimationPlayer(); target.add_child(player)
        clip=player.add_animation('move'); clip.add_key('position',.004,Vector2(4,0)); clip.add_key('position',.006,Vector2(6,0))
        dialog=AnimationEditorDialog(player); dialog.table.selectRow(1); dialog._remove_key()
        self.assertEqual(len(clip.keys['position']),1); self.assertEqual(clip.keys['position'][0][0],.004)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            # Root falls back to cwd in an unparented dialog.
            names=[str(Path.cwd()/'build'/'frame10.png'),str(Path.cwd()/'build'/'frame2.png')]
            with patch('editor.animation_editor.QFileDialog.getOpenFileNames',return_value=(names,'')),patch('editor.animation_editor.QInputDialog.getDouble',return_value=(10,True)):
                dialog._import_frames()
            self.assertEqual(clip.keys['SpriteRenderer.texture_path'][0][1],'build/frame2.png')
            self.assertAlmostEqual(clip.length,.2)
        dialog.reject()

    def test_particle_dialog_preview_is_isolated_accept_and_cancel(self):
        emitter=Particles2D(); before=particle_values(emitter)
        dialog=ParticleEditorDialog(emitter); dialog.load_preset(1)
        dialog.preview.system._update_emitter(dialog.preview_emitter,.02)
        self.assertEqual(particle_values(emitter),before)
        self.assertFalse(dialog.preview_emitter.emitting)
        self.assertTrue(dialog.authored_values()['emitting'])
        dialog.apply(); self.assertIsNotNone(dialog.result_values); self.assertTrue(dialog.result_values['one_shot'])
        self.assertEqual(particle_values(emitter),before); self.assertFalse(dialog.preview.timer.isActive())
        other=ParticleEditorDialog(emitter); other.controls['emitting'].setChecked(False)
        self.assertFalse(other.preview_emitter.emitting); other.reject()

    def test_console_structured_error_navigation_and_dedup(self):
        panel=ConsolePanel(); handler=ConsoleLogHandler(panel); requested=[]
        panel.location_requested.connect(lambda path,line:requested.append((path,line)))
        try: exec(compile('1/0','C:/Game/scripts/fail.cloud','exec'),{})
        except ZeroDivisionError as error:
            import sys
            record=logging.LogRecord('test',logging.ERROR,__file__,1,'ошибка',(),sys.exc_info())
            handler.emit(record); handler.emit(record)
        self.assertEqual(len(panel.problems.entries),1); self.assertEqual(panel.problems.table.item(0,3).text(),'2')
        panel.problems.open_source(); self.assertEqual(requested,[('C:\\Game\\scripts\\fail.cloud',1)])
        self.assertIn('делитель',panel.problems.details.toPlainText()); panel.shutdown()

    def test_recovery_captures_all_scenes_unsaved_script_and_restores_copies(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='Моя игра ') as temp:
            root=Path(temp); (root/'scripts').mkdir(); path=root/'scripts'/'игрок.cloud'; path.write_text('original',encoding='utf-8')
            window=QMainWindow(); window.project_dir=str(root); window.viewport=SimpleNamespace(is_playing=False)
            window.settings_store=SimpleNamespace(get=lambda key,default:default)
            window.console=SimpleNamespace(log=lambda *args:None); window._mark_dirty=lambda:None
            edit=QPlainTextEdit(); edit.setPlainText('unsaved'); edit.document().setModified(True)
            loaded=[]
            window.script_editor=SimpleNamespace(path=str(path),editor=edit,is_modified=lambda:edit.document().isModified(),load_file=lambda path:loaded.append(path))
            first=Scene('Saved',GameObject('Hero')); SceneSerializer.save_scene(first,str(root/'главная.scene'))
            first.root.position=Vector2(99,10); second=Scene('Unsaved',GameObject('New'))
            window.open_scenes=[first,second]; window._register_scene=lambda scene:window.open_scenes.append(scene)
            controller=RecoveryController(window); controller.set_project(root)
            self.assertTrue(controller.capture()); data=controller.store.load()
            self.assertEqual(len(data['scenes']),2); self.assertEqual(data['scripts'][0]['text'],'unsaved')
            controller.restore(data)
            self.assertEqual(window.open_scenes[-2].root.position,Vector2(99,10)); self.assertEqual(window.open_scenes[-1].path,'')
            self.assertEqual(path.read_text(encoding='utf-8'),'original'); self.assertIn('restored-scripts',loaded[0]); self.assertEqual(Path(loaded[0]).read_text(encoding='utf-8'),'unsaved')
            before=controller.store.load(); window.viewport.is_playing=True; first.root.position=Vector2(999,999)
            self.assertFalse(controller.capture()); self.assertEqual(controller.store.load(),before)
            controller.timer.stop(); window.deleteLater()


if __name__=='__main__': unittest.main()
