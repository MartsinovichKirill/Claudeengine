import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import qt_runtime

ROOT=Path(__file__).resolve().parents[1]


class QtRuntimeTests(unittest.TestCase):
    def fixture(self,tmp):
        root=Path(tmp);(root/'PyQt6/Qt6/bin').mkdir(parents=True);(root/'PyQt6/Qt6/plugins/platforms').mkdir(parents=True)
        return root
    def test_foreign_plugin_paths_and_platform_are_replaced(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            root=self.fixture(tmp)
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',str(root),create=True),patch.object(sys,'argv',['CloudEngine.exe']),patch.dict(os.environ,{'QT_PLUGIN_PATH':'foreign-qt','QT_QPA_PLATFORM_PLUGIN_PATH':'foreign-plugins','QT_QPA_PLATFORM':'foreign-backend','QT_STYLE_OVERRIDE':'foreign-style','PATH':'foreign-dlls'}),patch.object(os,'add_dll_directory',return_value=Mock()):
                path=qt_runtime.configure()
                self.assertEqual(path,root/'PyQt6/Qt6/plugins/platforms/qwindows.dll')
                self.assertEqual(os.environ['QT_QPA_PLATFORM'],'windows')
                self.assertNotIn('foreign-dlls',os.environ['PATH'])
                self.assertNotIn('QT_STYLE_OVERRIDE',os.environ)
                self.assertEqual(os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'],str(path.parent))
    def test_headless_allowed_only_for_explicit_checks(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            root=self.fixture(tmp)
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',str(root),create=True),patch.object(sys,'argv',['CloudEngine.exe','--smoke-test','report.json']),patch.dict(os.environ,{'QT_QPA_PLATFORM':'offscreen'}),patch.object(os,'add_dll_directory',return_value=Mock()):
                qt_runtime.configure();self.assertEqual(os.environ['QT_QPA_PLATFORM'],'offscreen')
    def test_missing_plugin_reports_path_before_qapplication(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            with patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'QT_QPA_PLATFORM':'windows','QT_QPA_PLATFORM_PLUGIN_PATH':tmp}):
                with self.assertRaisesRegex(RuntimeError,'qwindows.dll'):qt_runtime.verify_windows_plugin()
    def test_plugin_load_error_is_actionable(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
            (Path(tmp)/'qwindows.dll').write_bytes(b'test')
            with patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'QT_QPA_PLATFORM':'windows','QT_QPA_PLATFORM_PLUGIN_PATH':tmp}),patch('ctypes.WinDLL',side_effect=OSError('dependency missing')):
                with self.assertRaisesRegex(RuntimeError,'dependency missing'):qt_runtime.verify_windows_plugin()
    def test_source_environment_is_unchanged(self):
        with patch.object(sys,'frozen',False,create=True),patch.dict(os.environ,{'QT_QPA_PLATFORM':'offscreen'}):
            self.assertIsNone(qt_runtime.configure());self.assertEqual(os.environ['QT_QPA_PLATFORM'],'offscreen')
