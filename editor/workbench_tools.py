"""Editor entry points for linked resources, UI composition and debugging."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QFileDialog, QMessageBox
from editor.undo_stack import UndoCommand, AddNodeCommand
from engine.resources.scene_serializer import SceneSerializer
from engine.resources.prefab import Prefab


class ObjectSnapshotsCommand(UndoCommand):
    def __init__(self, changes, script_system=None, text='Изменить объекты'):
        super().__init__(text)
        self.changes=changes; self.script_system=script_system
    def _apply(self, index):
        for change in self.changes:
            Prefab.apply(change[0],change[index],self.script_system)
    def redo(self): self._apply(2)
    def undo(self): self._apply(1)


class WorkbenchTools:
    def init_workbench(self):
        from editor.debugger_panel import DebuggerPanel
        self.debugger_panel=DebuggerPanel(self)
        self.debugger_dock=QDockWidget('Отладчик Cloud Scripts',self)
        self.debugger_dock.setObjectName('CloudDebuggerDock')
        self.debugger_dock.setWidget(self.debugger_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,self.debugger_dock)
        self.debugger_dock.hide()
        self.viewport.debugger=self.debugger_panel.debugger
        menu=self.menuBar().addMenu('Инструменты')
        menu.addAction('Сохранить объект как префаб…',self.save_prefab)
        menu.addAction('Добавить экземпляр префаба…',self.instantiate_prefab)
        menu.addAction('Обновить экземпляры префабов',self.update_prefabs)
        menu.addAction('Отвязать выбранный префаб',self.unlink_prefab)
        menu.addSeparator()
        menu.addAction('Новый материал…',self.open_material)
        menu.addAction('Редактировать материал…',self.choose_material)
        menu.addAction('Редактор интерфейсов…',self.open_ui_editor)
        menu.addAction('Pixel Studio — рисование и анимация…',self.open_pixel_studio)
        menu.addSeparator()
        menu.addAction(self.debugger_dock.toggleViewAction())
        self._add_action(menu,'Точка остановки',self.debugger_panel.toggle,'F9')
        self._add_action(menu,'Продолжить',lambda:self.debugger_panel.resume('continue'),'F6')
        self._add_action(menu,'Шаг с обходом',lambda:self.debugger_panel.resume('over'),'F10')
        self._add_action(menu,'Шаг с заходом',lambda:self.debugger_panel.resume('into'),'F11')
        self._add_action(menu,'Выйти из функции',lambda:self.debugger_panel.resume('out'),'Shift+F11')

    def refresh_workbench(self):
        self.hierarchy.refresh(); self.inspector.refresh()
        if self.current_scene:
            self.viewport.bind_node_assets(self.current_scene.root)
        self.assets.refresh()

    def save_prefab(self):
        node=self.get_selected_node()
        if node is None or not self.project_dir: return
        path,_=QFileDialog.getSaveFileName(self,'Префаб',str(Path(self.project_dir)/'assets'/(node.name+'.prefab')),'Cloud Prefab (*.prefab)')
        if not path: return
        try:
            Prefab.save(node,path,self.project_dir)
            self.update_prefabs()
            self.assets.refresh()
            self.console.log('Префаб сохранён: '+path,'INFO')
        except Exception as exc:
            QMessageBox.warning(self,'Префаб',str(exc))

    def instantiate_prefab(self, path=''):
        if not self.current_scene or not self.project_dir: return
        if not path:
            path,_=QFileDialog.getOpenFileName(self,'Префаб',self.project_dir,'Cloud Prefab (*.prefab)')
        if not path: return
        try:
            node=Prefab.instantiate(path,self.project_dir,self.script_system)
            parent=self.get_selected_node() or self.current_scene.root
            node.name=self._unique_name(parent,node.name)
            self.undo_stack.execute(AddNodeCommand(parent,node))
            self.refresh_workbench(); self.hierarchy.select_node(node)
        except Exception as exc:
            QMessageBox.warning(self,'Префаб',str(exc))

    def update_prefabs(self):
        changes=[]
        for scene in self.open_scenes:
            for node in scene.get_nodes():
                if getattr(node,'prefab',None):
                    try:
                        before=SceneSerializer.node_to_dict(node)
                        after=Prefab.updated_data(node,self.project_dir)
                        if before!=after: changes.append((node,before,after))
                    except Exception as exc:
                        self.console.log('Префаб '+node.name+': '+str(exc),'ERROR')
        if changes:
            self.undo_stack.execute(ObjectSnapshotsCommand(changes,self.script_system,'Обновить префабы'))
        self.refresh_workbench()

    def unlink_prefab(self):
        node=self.get_selected_node()
        if node and getattr(node,'prefab',None):
            before=SceneSerializer.node_to_dict(node); after=dict(before); after.pop('prefab',None)
            self.undo_stack.execute(ObjectSnapshotsCommand([(node,before,after)],self.script_system,'Отвязать префаб'))
            self.refresh_workbench()

    def open_material(self,path=''):
        if not self.project_dir: return
        from editor.material_editor import MaterialEditor
        try:
            MaterialEditor(self.project_dir,path,self).exec()
        except Exception as exc:
            QMessageBox.warning(self,'Материал',str(exc))

    def choose_material(self):
        path,_=QFileDialog.getOpenFileName(self,'Материал',self.project_dir,'Cloud Material (*.material)')
        if path: self.open_material(path)

    def open_ui_editor(self):
        if not self.current_scene: return
        from engine.nodes.canvas_layer import CanvasLayer
        from editor.ui_editor import UIEditor
        selected=self.get_selected_node()
        layer=selected if isinstance(selected,CanvasLayer) else next((node for node in self.current_scene.get_nodes() if isinstance(node,CanvasLayer)),None)
        original=layer; layer=layer or CanvasLayer('Interface')
        before=SceneSerializer.node_to_dict(layer)
        dialog=UIEditor(layer,self)
        if dialog.exec()==dialog.DialogCode.Accepted:
            if original:
                self.undo_stack.execute(ObjectSnapshotsCommand([(original,before,dialog.result_data)],self.script_system,'Изменить интерфейс'))
            else:
                node=SceneSerializer.node_from_dict(dialog.result_data,self.script_system)
                self.undo_stack.execute(AddNodeCommand(self.current_scene.root,node))
            self.refresh_workbench()

    def open_pixel_studio(self):
        from editor.pixel_studio import PixelStudio
        PixelStudio(self.project_dir or str(Path.cwd()), self).exec()
