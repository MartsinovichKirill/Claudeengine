"""Editor graphics controls and reusable post-processing resources."""
import json
from pathlib import Path
from PyQt6.QtWidgets import QFileDialog,QMessageBox,QColorDialog
from PyQt6.QtGui import QColor
from engine.resources.scene_serializer import SceneSerializer

def install(window):
    menu=window.menuBar().addMenu('Графика')
    def toggle_preview(checked):window.viewport.preview_post=checked
    action=menu.addAction('Предпросмотр постобработки');action.setCheckable(True);action.toggled.connect(toggle_preview)
    action=menu.addAction('Направляющие камеры');action.setCheckable(True);action.setChecked(True);action.toggled.connect(lambda checked:setattr(window.viewport,'camera_guides',checked))
    def ambient():
        if not window.project_dir:return
        color=QColorDialog.getColor(QColor(*window.settings.get('render',{}).get('ambient_color',[255,255,255])[:3]),window,'Окружающее освещение')
        if color.isValid():
            window.settings.setdefault('render',{})['ambient_color']=[color.red(),color.green(),color.blue()]
            path=Path(window.project_dir)/'project.json'
            data=json.loads(path.read_text(encoding='utf-8-sig'));data.setdefault('render',{})['ambient_color']=window.settings['render']['ambient_color'];path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    menu.addAction('Окружающее освещение…',ambient)
    def profile(save):
        from engine.nodes.post_process import PostProcess
        node=window.get_selected_node()
        if not isinstance(node,PostProcess):
            QMessageBox.information(window,'Профиль','Выберите PostProcess в сцене.');return
        chooser=QFileDialog.getSaveFileName if save else QFileDialog.getOpenFileName
        path,_=chooser(window,'Профиль постобработки',window.project_dir,'Post Profile (*.postprofile)')
        if not path:return
        try:
            if save:Path(path).write_text(json.dumps(SceneSerializer.node_to_dict(node)['properties'],ensure_ascii=False,indent=2),encoding='utf-8')
            else:
                from editor.undo_stack import PropertyCommand
                data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
                for key,value in data.items():
                    if key in node.get_exported_properties():window.undo_stack.execute(PropertyCommand(node,key,getattr(node,key),value))
                window.inspector.refresh()
        except (OSError,ValueError) as error:QMessageBox.warning(window,'Профиль',str(error))
    menu.addAction('Сохранить профиль постобработки…',lambda:profile(True));menu.addAction('Загрузить профиль постобработки…',lambda:profile(False))
    def render_report():
        render=getattr(getattr(window.viewport,'game_loop',None),'render_system',None)
        QMessageBox.information(window,'Отрисовка',str(getattr(render,'render_stats',{}))+'\nПодробные замеры доступны в профилировщике во время Play.')
    menu.addAction('Статистика отрисовки',render_report)
