"""Visual and functional checks of the selected interface in a frozen build."""
import copy
from PyQt6.QtWidgets import QToolButton,QTabBar
from editor.ui_profile import flavor
from editor.appearance import AppearanceDialog,CommandPalette
from engine.core.scene import Scene
from engine.nodes.game_object import GameObject


def run(app,window,report):
    modern=flavor()=='modern'
    menus=[action for action in window.menuBar().actions() if action.menu()]
    results={'interface_layout':len(menus)==6 and not any(a.text() in ('Справка','Help') for a in menus)}
    results['interface_profile']=('editor_settings_'+flavor()+'.json') in window.settings_store.path
    before=copy.deepcopy(app.property('cloudAppearance'))
    dialog=AppearanceDialog(window); dialog.show(); app.processEvents()
    dialog.grab().save(str(report.parent/(report.stem+'-appearance.png')))
    dialog.font_size.setValue(14); dialog.preview(); dialog.reject()
    results['appearance_cancel']=app.property('cloudAppearance')==before
    palette=CommandPalette(window); palette.search.setText('игровые данные'); palette.show(); app.processEvents()
    results['command_search']=palette.list.count()>0
    palette.grab().save(str(report.parent/(report.stem+'-commands.png'))); palette.reject()
    # Buttons refer to the page object, rather than a stale numeric index.
    tabs=window.scene_tabs
    original=window.current_scene
    added=Scene('Tab close check',GameObject()); tabs.add_scene(added)
    index=tabs.currentIndex(); button=tabs.tabBar().tabButton(index,QTabBar.ButtonPosition.RightSide)
    results['scene_close_icon']=isinstance(button,QToolButton) and not button.icon().isNull()
    button.click(); results['scene_close_action']=all(scene is not added for scene in tabs.scenes())
    if original is not None:
        window._activate_scene(original)
        node=original.find_node('Player')
        if node: window.hierarchy.select_node(node)
    window.resize(1500,950)
    for _ in range(12): app.processEvents()
    window.grab().save(str(report.parent/(report.stem+'-final-workspace.png')))
    return results
