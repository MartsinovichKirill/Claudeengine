"""Regression checks for project creation and editor builds. Run from C:/Cloud."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcess
from editor.project_hub import create_project
from editor.build_dialog import BuildDialog
from build_support import build_environment, default_projects_dir, validate_build_destination

APP = QApplication.instance() or QApplication([])

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)

    def test_create_with_spaces_and_custom_settings(self):
        path = Path(create_project(self.parent, 'Моя игра', 'Пустой 2D', width=1600, height=900, pixel_art=False))
        import json
        config = json.loads((path / 'project.json').read_text(encoding='utf-8'))
        self.assertEqual(config['window']['width'], 1600)
        self.assertFalse(config['render']['pixel_art'])
        self.assertEqual({p.name for p in path.iterdir() if p.is_dir()}, {'assets','scripts','scenes','shaders'})
        self.assertFalse(list(self.parent.glob('.cloud-create-*')))

    def test_existing_project_is_preserved(self):
        path = Path(create_project(self.parent, 'Existing', 'Пустой 2D'))
        marker = path / 'keep.txt'; marker.write_text('keep')
        with self.assertRaises(ValueError):
            create_project(self.parent, 'Existing', 'Платформер')
        self.assertEqual(marker.read_text(), 'keep')

    def test_failed_template_does_not_block_retry(self):
        with patch('editor.template_art.create_art', side_effect=RuntimeError('art failed')):
            with self.assertRaises(RuntimeError):
                create_project(self.parent, 'Retry', 'Платформер')
        self.assertFalse((self.parent / 'Retry').exists())
        self.assertFalse(list(self.parent.glob('.cloud-create-*')))
        self.assertTrue(Path(create_project(self.parent, 'Retry', 'Пустой 2D')).is_dir())

    def test_permission_error_has_recovery_message(self):
        with patch.object(Path, 'mkdir', side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(PermissionError, 'Выберите другую папку'):
                create_project(self.parent, 'Denied', 'Пустой 2D')

    def test_windows_names_and_traversal(self):
        for name in ('../outside', 'CON', 'con.txt', 'LPT1', '..', 'bad.', 'bad:name'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                create_project(self.parent, name, 'Пустой 2D')

    def test_portable_default_precedes_profile_path(self):
        with patch('build_support.writable_directory', return_value=True) as probe:
            self.assertEqual(default_projects_dir(), ROOT / 'projects')
            probe.assert_called_once_with(ROOT / 'projects')

    def test_frozen_projects_are_outside_replaced_app_directory(self):
        executable = ROOT / 'dist' / 'CloudEngine' / 'CloudEngine.exe'
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(executable)), patch.object(Path, 'is_dir', return_value=True), patch('build_support.writable_directory', return_value=True):
            self.assertEqual(default_projects_dir(), ROOT / 'dist' / 'Cloud Projects')

class BuildTests(unittest.TestCase):
    def test_rebuild_refuses_to_replace_user_projects(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            destination = Path(directory)
            project = destination / 'CloudEngine' / 'projects' / 'My Game'
            project.mkdir(parents=True)
            manifest = project / 'project.json'; manifest.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'есть проекты'):
                validate_build_destination(destination, 'CloudEngine', False)
            self.assertTrue(manifest.is_file())

    def test_packaged_template_is_not_a_user_project(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            destination = Path(directory)
            template = destination / 'CloudEngine' / '_internal' / 'projects' / 'sample_project'
            template.mkdir(parents=True)
            (template / 'project.json').write_text('{}')
            self.assertEqual(validate_build_destination(destination, 'CloudEngine', False), destination / 'CloudEngine')

    def test_builder_uses_requested_name_and_system_dll_environment(self):
        from build_exe import build
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory, patch('build_exe.ensure_pyinstaller', return_value=True), patch('build_exe.subprocess.call', return_value=0) as execute, patch('builtins.print'):
            self.assertEqual(build(root=str(ROOT), name='CustomEditor', output=directory), 0)
            command = execute.call_args.args[0]
            self.assertEqual(command[command.index('--name') + 1], 'CustomEditor')
            self.assertEqual(command[command.index('--distpath') + 1], directory)
            if os.name == 'nt':
                self.assertTrue(execute.call_args.kwargs['env']['PATH'].lower().startswith(str(Path(os.environ['SystemRoot']) / 'System32').lower()))

    def test_system_dlls_precede_foreign_path(self):
        with patch.dict(os.environ, {'SystemRoot':'C:/Windows', 'PATH':'C:/foreign/poppler', 'PYTHONHOME':'bad'}):
            env = build_environment()
        if os.name == 'nt':
            self.assertTrue(env['PATH'].startswith(str(Path('C:/Windows/System32')) + os.pathsep))
        self.assertNotIn('PYTHONHOME', env)
        self.assertEqual(env['PYTHONIOENCODING'], 'utf-8')

    def test_custom_filename_is_built_and_success_requires_file(self):
        class RecordingProcess(QProcess):
            def start(self, program, arguments):
                self.recorded = (program, arguments)
            def waitForStarted(self, timeout):
                return True
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            dialog = BuildDialog()
            dialog.name_edit.setText('Мой редактор')
            dialog.output_edit.setText(directory)
            with patch('editor.build_dialog.find_build_python', return_value=sys.executable), patch('editor.build_dialog.QProcess', RecordingProcess):
                dialog.start_build()
            process = dialog.process
            self.assertEqual(process.recorded[0], sys.executable)
            arguments = process.recorded[1]
            self.assertEqual(arguments[arguments.index('--name') + 1], 'Мой редактор')
            self.assertEqual(arguments[arguments.index('--output') + 1], str(Path(directory).resolve()))
            dialog._on_finished(0, QProcess.ExitStatus.NormalExit)
            self.assertNotIn('[build] Готово:', dialog.output.toPlainText())
            self.assertTrue(dialog.build_btn.isEnabled())
            dialog.close()

if __name__ == '__main__':
    unittest.main()
