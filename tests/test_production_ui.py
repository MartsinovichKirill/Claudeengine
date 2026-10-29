import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication,QTableWidgetItem
from PyQt6.QtCore import QEventLoop,QTimer
from engine.components.enemy_ai import EnemyAI
from editor.enemy_editor import EnemyEditor
from editor.game_data_editor import GameDataEditor
from engine.resources.game_data import GameData
from editor.project_tests_dialog import ProjectTestsDialog
from test_production_update import project

APP=QApplication.instance() or QApplication([])
ROOT=Path(__file__).resolve().parents[1]


class ProductionUITests(unittest.TestCase):
    def test_graph_drag_edit_cancel_and_apply(self):
        component=EnemyAI(); before=copy.deepcopy(component.graph)
        dialog=EnemyEditor(component); dialog.show(); APP.processEvents()
        dialog.cards['patrol'].setPos(50,80); self.assertEqual(dialog.data['positions']['patrol'],[50,80])
        dialog.entry.setCurrentText('chase'); dialog.apply()
        self.assertEqual(dialog.result_data['graph']['entry'],'chase'); self.assertEqual(component.graph,before)
        self.assertTrue(dialog.grab().width()>500)
        second=EnemyEditor(component); second.states.setCurrentRow(0); second.action.setCurrentIndex(second.action.findData('wait')); second.reject()
        self.assertEqual(component.graph,before)

    def test_data_editor_save_and_reopen(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); path=root/'data'/'sword.gamedata'
            dialog=GameDataEditor(root); dialog.name.setText('My Sword'); dialog.table.item(0,2).setText('25')
            with patch('editor.game_data_editor.QFileDialog.getSaveFileName',return_value=(str(path),'')): dialog.save()
            self.assertEqual(GameData(path,root)['damage'],25.)
            reopened=GameDataEditor(root,path); reopened.table.item(0,2).setText('99'); reopened.reject()
            self.assertEqual(GameData(path,root)['damage'],25.)
            reopened=GameDataEditor(root,path); reopened.add_field(False,'damage','int',1)
            with self.assertRaisesRegex(ValueError,'Повторяется'): reopened.document()
            reopened.reject()

    def test_project_dialog_runs_without_blocking_qt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            root=Path(folder); project(root); dialog=ProjectTestsDialog(root); dialog.frames.setValue(3); dialog.start_checks()
            loop=QEventLoop(); dialog.thread.finished.connect(loop.quit); QTimer.singleShot(12000,loop.quit); loop.exec()
            self.assertFalse(dialog.thread.isRunning()); self.assertIsNotNone(dialog.report); self.assertTrue(dialog.report['passed'],dialog.details.toPlainText())
            self.assertTrue(dialog.report_path.is_file()); dialog.reject()


if __name__=='__main__': unittest.main()
