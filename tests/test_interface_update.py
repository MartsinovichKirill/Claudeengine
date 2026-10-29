import copy
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication,QMainWindow,QMenu,QToolButton,QTabBar
from engine.core.scene import Scene
from engine.nodes.game_object import GameObject
from editor.scene_tabs import SceneTabs
from editor.toolbar import EditorToolbar
from editor.editor_settings import EditorSettings
from editor.appearance import install,preferences,apply_preferences,AppearanceDialog,CommandPalette
from editor.icons import get_icon,_make_svg
from editor.ui_profile import flavor

APP=QApplication.instance() or QApplication([])
ROOT=Path(__file__).resolve().parents[1]


class InterfaceTests(unittest.TestCase):
    def test_inspector_scrolls_instead_of_clipping_numeric_fields(self):
        from editor.inspector_panel import InspectorPanel
        from PyQt6.QtWidgets import QDoubleSpinBox
        from editor.appearance import apply_application_theme
        apply_application_theme(APP)
        inspector=InspectorPanel(); inspector.resize(345,330)
        node=GameObject(); node.add_component('Rigidbody2D'); node.add_component('BoxCollider2D'); node.add_component('SpriteRenderer')
        inspector.set_node(node); inspector.show()
        for _ in range(3): APP.processEvents()
        self.assertGreater(inspector.scroll.verticalScrollBar().maximum(),0)
        self.assertLessEqual(inspector.container.width(),inspector.scroll.viewport().width())
        for field in inspector.findChildren(QDoubleSpinBox): self.assertGreaterEqual(field.height(),inspector.fontMetrics().height())
        inspector.close()

    def fixture(self,path):
        window=QMainWindow(); window.resize(1300,850)
        window.settings_store=EditorSettings(str(path)); window.toolbar=EditorToolbar(window); window.addToolBar(window.toolbar)
        window.scene_tabs=SceneTabs(); window.setCentralWidget(window.scene_tabs)
        window.save_layout=lambda:None
        for name in ('Файл','Плагины','Язык / Language','Правка','Выровнять','Проект','Сцена','Нода','Компонент','Вид','Отладка','Инструменты','Рабочее пространство','Графика','Восстановление','Разработка'):
            menu=window.menuBar().addMenu(name); menu.addAction('Команда '+name)
        install(window); return window

    def test_menus_grouped_reversible_and_commands_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            window=self.fixture(Path(folder)/'settings.json')
            count=lambda:len([a for a in window.menuBar().actions() if a.menu()])
            self.assertEqual(count(),6)
            options=preferences(window.settings_store)
            for _ in range(3):
                options['group_menus']=False; apply_preferences(window,options); self.assertEqual(count(),16)
                options['group_menus']=True; apply_preferences(window,options); self.assertEqual(count(),6)
            palette=CommandPalette(window); palette.filter('Команда Разработка'); self.assertEqual(palette.list.count(),1)
            palette.reject(); window.close()

    def test_preview_cancel_restores_theme_toolbar_and_menus(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            window=self.fixture(Path(folder)/'settings.json'); before=copy.deepcopy(APP.property('cloudAppearance'))
            dialog=AppearanceDialog(window); dialog.font_size.setValue(16); dialog.grouped.setChecked(False); dialog.groups['scene'].setChecked(False)
            dialog.preview(); self.assertEqual(APP.property('cloudAppearance')['font_size'],16)
            self.assertTrue(window._ui_toolbar_groups['scene'].isHidden()); dialog.reject()
            self.assertEqual(APP.property('cloudAppearance'),before)
            self.assertFalse(window._ui_toolbar_groups['scene'].isHidden())
            self.assertEqual(len([a for a in window.menuBar().actions() if a.menu()]),6)
            window.close()

    def test_preferences_save_and_reload(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            path=Path(folder)/'settings.json'; window=self.fixture(path)
            dialog=AppearanceDialog(window); dialog.font_size.setValue(15); dialog.icon_size.setValue(24); dialog.options['accent']='#cc99ff'; dialog.save()
            loaded=preferences(EditorSettings(str(path)))
            self.assertEqual(loaded['font_size'],15); self.assertEqual(loaded['icon_size'],24); self.assertEqual(loaded['accent'],'#cc99ff')
            window.close()

    def test_close_button_closes_correct_tab_after_drag(self):
        tabs=SceneTabs(); first=Scene('A',GameObject()); second=Scene('B',GameObject()); tabs.add_scene(first); tabs.add_scene(second)
        tabs.tabBar().moveTab(0,1)
        button=tabs.tabBar().tabButton(1,QTabBar.ButtonPosition.RightSide)
        self.assertIsInstance(button,QToolButton); self.assertEqual(button.accessibleName(),'Закрыть сцену')
        button.click(); self.assertEqual(tabs.count(),1); self.assertIs(tabs.get_scene(0),second)
        tabs.close()

    def test_icons_are_svg_and_have_high_dpi_sizes(self):
        for name in ('close','layers','focus','play','save','build','camera','file'):
            self.assertIn('stroke=',_make_svg(name,'#ffffff'))
            icon=get_icon(name,20); self.assertFalse(icon.isNull()); self.assertGreaterEqual(len(icon.availableSizes()),3)

    def test_classic_recovers_beta3_colors(self):
        from editor.classic_theme import COLORS
        self.assertEqual(COLORS['bg'],'#1b2633')
        with patch('sys.argv',['main.py','--interface','classic']): self.assertEqual(flavor(),'classic')

    def test_classic_menu_migration_preserves_later_choice(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            store=EditorSettings(str(Path(folder)/'settings.json'))
            store.set('appearance',{'group_menus':False})
            with patch('sys.argv',['main.py','--interface','classic']):
                self.assertTrue(preferences(store)['group_menus'])
                store.set('appearance',{'group_menus':False,'menu_layout_version':1})
                self.assertFalse(preferences(store)['group_menus'])


if __name__=='__main__': unittest.main()

