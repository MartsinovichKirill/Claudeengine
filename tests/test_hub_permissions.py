import unittest
from unittest.mock import patch
from editor.project_hub import accessible_project

class HubPermissionTests(unittest.TestCase):
    def test_inaccessible_recent_project_is_skipped(self):
        with patch('editor.project_hub.Path.is_file',side_effect=PermissionError('denied')):
            self.assertFalse(accessible_project('locked project'))
    def test_existing_project_is_available(self):
        with patch('editor.project_hub.Path.is_file',return_value=True):
            self.assertTrue(accessible_project('working project'))

    def test_hub_has_no_pixel_art_checkbox(self):
        from PyQt6.QtWidgets import QApplication,QCheckBox
        from editor.project_hub import ProjectHub
        app=QApplication.instance() or QApplication([])
        with patch('editor.project_hub.recent_projects',return_value=[]):
            hub=ProjectHub()
            self.assertFalse(any('Пиксельная графика' in checkbox.text() for checkbox in hub.findChildren(QCheckBox)))
            hub.close()
