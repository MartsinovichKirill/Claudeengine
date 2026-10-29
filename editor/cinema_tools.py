"""Project mixer, cinematic property tracks, and cooperative editing commands."""
import copy
import json
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,
    QDoubleSpinBox,QCheckBox,QFileDialog,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,QColorDialog)
from PyQt6.QtGui import QColor
from engine.systems.cutscenes import CutscenePlayer,validate_clip


def save_settings(window):
    path=Path(window.project_dir)/'project.json';tmp=path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(window.settings,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)


class MixerDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window_ref=window;self.setWindowTitle('Аудиомикшер')
        from editor.studio_workspace import build_mixer
        build_mixer(self,window)

    def live(self):
        audio=getattr(getattr(self.window_ref.viewport,'scene_tree',None),'audio_system',None)
        if audio:
            solo={bus for bus,control in self.solos.items() if control.isChecked()}
            for bus,(volume,mute) in self.controls.items():
                audio.set_bus_volume(bus,volume.value())
                audio.set_bus_mute(bus,mute.isChecked() or bool(solo and bus!='master' and bus not in solo))
    def finish(self,result):
        if result!=QDialog.DialogCode.Accepted and self.original_live:
            audio=getattr(getattr(self.window_ref.viewport,'scene_tree',None),'audio_system',None)
            if audio:audio.bus_volumes,audio.muted=self.original_live

    def save(self):
        try:
            config={'volumes':{k:v.value() for k,(v,m) in self.controls.items()},'muted':[k for k,(v,m) in self.controls.items() if m.isChecked()]}
            # Keep the legacy settings sliders in sync.
            config.update(config['volumes'])
            old=copy.deepcopy(self.window_ref.settings.get('audio',{}))
            self.window_ref.settings['audio']=config
            try:save_settings(self.window_ref)
            except OSError:
                self.window_ref.settings['audio']=old
                raise
            for control in self.solos.values():control.setChecked(False)
            self.live()
            self.accept()
        except OSError as error:QMessageBox.warning(self,'Звук',str(error))


class CutsceneDialog(QDialog):
    headers=['Начало, с','Длительность, с','Путь объекта','Компонент','Свойство','От','До','Кривая']
    def __init__(self,window,path=''):
        super().__init__(window);self.window_ref=window;self.path=path;self.player=CutscenePlayer();self.original_camera=(copy.deepcopy(window.viewport.camera.center),window.viewport.camera.zoom);self.setWindowTitle('Кат-сцены');self.resize(1120,650)
        root=QVBoxLayout(self);hint=QLabel('Числа: 0, 1.5; векторы: [100, 200]. Кривая: linear / smooth. Пример: Camera, Camera2D, zoom, 1, 2. Предпросмотр возвращает исходные значения при закрытии.');hint.setWordWrap(True);root.addWidget(hint)
        self.table=QTableWidget(0,8);self.table.setHorizontalHeaderLabels(self.headers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);root.addWidget(self.table,1)
        row=QHBoxLayout();root.addLayout(row)
        for text,action in [('Добавить дорожку',self.add_track),('Удалить дорожку',self.remove_track),('Открыть…',self.open_file),('Сохранить…',self.save),('Воспроизвести',self.play),('Остановить / вернуть',self.restore)]:
            button=QPushButton(text);button.clicked.connect(action);row.addWidget(button)
        seekrow=QHBoxLayout();root.addLayout(seekrow);seekrow.addWidget(QLabel('Позиция, с'))
        self.cursor=QDoubleSpinBox();self.cursor.setRange(0,3600);self.cursor.setDecimals(2);self.cursor.setSingleStep(.1);seekrow.addWidget(self.cursor)
        self.camera_preview=QCheckBox('Просмотр из камеры сцены');self.camera_preview.setChecked(True);seekrow.addWidget(self.camera_preview)
        seek=QPushButton('Показать кадр');seek.clicked.connect(self.scrub);seekrow.addWidget(seek)
        self.timer=QTimer(self);self.timer.setInterval(16);self.timer.timeout.connect(self.tick)
        self.finished.connect(lambda _:self.restore())
        from editor.studio_workspace import enhance_cutscene
        self.inspector_loading=False
        enhance_cutscene(self,root)
        if path:self.load(path)

    def add_track(self,checked=False,values=None):
        row=self.table.rowCount();self.table.insertRow(row)
        for col,value in enumerate(values or [0,1,'.','','position','[0, 0]','[100, 0]','smooth']):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        if hasattr(self,'timeline'):self.timeline.refresh()
        self.table.selectRow(row)
    def remove_track(self):self.restore();self.table.removeRow(self.table.currentRow());self.timeline.refresh();self.sync_inspector()
    def track_kind(self,row):
        item=self.table.item(row,0)
        return (item.data(256) if item else None) or 'property'

    def sync_inspector(self):
        if not hasattr(self,'track_fields'):return
        row=self.table.currentRow();self.inspector_loading=True
        self.kind_control.setCurrentIndex({'property':0,'audio':1,'event':2}.get(self.track_kind(row),0))
        for col,edit in enumerate(self.track_fields):
            item=self.table.item(row,col) if row>=0 else None
            edit.setText(item.text() if item else '');edit.setEnabled(row>=0)
        self.kind_control.setEnabled(row>=0);self.inspector_loading=False

    def apply_inspector(self):
        if self.inspector_loading:return
        row=self.table.currentRow()
        if row<0:return
        self.restore();kind=('property','audio','event')[self.kind_control.currentIndex()]
        self.table.blockSignals(True)
        for col,edit in enumerate(self.track_fields):
            previous=self.table.item(row,col)
            if previous:previous.setText(edit.text())
            else:self.table.setItem(row,col,QTableWidgetItem(edit.text()))
        old=self.track_kind(row);self.table.item(row,0).setData(256,kind)
        if old!=kind and kind!='property':
            self.table.item(row,4).setText('play' if kind=='audio' else 'on_cutscene')
            self.table.item(row,5).setText('[]')
        self.table.blockSignals(False);self.timeline.refresh();self.sync_inspector()

    def data(self):
        result={'version':1,'tracks':[]}
        for row in range(self.table.rowCount()):
            fields=[self.table.item(row,col).text().strip() if self.table.item(row,col) else '' for col in range(8)]
            kind=self.track_kind(row)
            if kind=='property':
                result['tracks'].append(dict(start=float(fields[0]),duration=float(fields[1]),target=fields[2],component=fields[3],property=fields[4],**{'from':json.loads(fields[5]),'to':json.loads(fields[6]),'ease':fields[7]}))
            else:
                result['tracks'].append(dict(kind=kind,start=float(fields[0]),duration=float(fields[1]),target=fields[2],component=fields[3],method=fields[4],args=json.loads(fields[5] or '[]')))
        return validate_clip(result)
    def load(self,path):
        self.restore();data=validate_clip(json.loads(Path(path).read_text(encoding='utf-8-sig')));self.table.setRowCount(0)
        for t in data['tracks']:
            self.add_track(values=[t.get('start',0),t.get('duration',0),t.get('target','.'),t.get('component',''),t.get('property',t.get('method','play')),json.dumps(t.get('from',t.get('args',[]))),json.dumps(t.get('to',0)),t.get('ease','linear')])
            self.table.item(self.table.rowCount()-1,0).setData(256,t.get('kind','property'))
        self.timeline.refresh();self.sync_inspector()
        self.path=path
    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Кат-сцена',self.window_ref.project_dir,'Кат-сцена (*.cutscene)')
        if path:
            try:self.load(path)
            except (ValueError,OSError,KeyError) as error:self.error(error)
    def save(self):
        try:
            data=self.data();path,_=QFileDialog.getSaveFileName(self,'Сохранить кат-сцену',self.path or str(Path(self.window_ref.project_dir)/'intro.cutscene'),'Кат-сцена (*.cutscene)')
            if not path:return
            root=Path(self.window_ref.project_dir).resolve();file=Path(path).resolve()
            if not file.is_relative_to(root):raise ValueError('Сохраните кат-сцену внутри проекта')
            tmp=file.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(file);self.path=str(file);self.window_ref.assets.refresh()
        except (ValueError,OSError,KeyError) as error:self.error(error)
    def bind(self):
        self.restore()
        if not self.window_ref.current_scene:raise ValueError('Откройте сцену')
        self.player.bind(self.window_ref.current_scene,self.data())
    def play(self):
        try:self.bind();self.player.playing=True;self.timer.start()
        except (ValueError,KeyError,TypeError) as error:self.error(error)
    def scrub(self):
        try:self.bind();self.player.seek(self.cursor.value());self.update_preview()
        except (ValueError,KeyError,TypeError) as error:self.error(error)
    def tick(self):
        self.player.update(.016);self.cursor.setValue(self.player.time);self.update_preview()
        if not self.player.playing:self.timer.stop()
    def update_preview(self):
        if self.camera_preview.isChecked() and self.window_ref.current_scene:
            from engine.nodes.camera2d import Camera2D
            for node in self.window_ref.current_scene.get_nodes():
                camera=node if isinstance(node,Camera2D) else node.get_component('Camera2D')
                if camera and camera.enabled:
                    runtime=camera.runtime_node() if hasattr(camera,'runtime_node') else camera
                    runtime.reset_follow();runtime.update_camera(0)
                    self.window_ref.viewport.camera.center=copy.deepcopy(runtime.get_center());self.window_ref.viewport.camera.zoom=runtime.zoom
                    break
        self.window_ref.viewport.update()
    def restore(self):
        self.timer.stop();self.player.stop(True)
        center,zoom=self.original_camera;self.window_ref.viewport.camera.center=copy.deepcopy(center);self.window_ref.viewport.camera.zoom=zoom
        self.window_ref.viewport.update()
    def error(self,error):QMessageBox.warning(self,'Кат-сцена',str(error))


def install(window):
    menus={action.text():action.menu() for action in window.menuBar().actions() if action.menu()}
    menu=menus.get('Разработка') or window.menuBar().addMenu('Разработка')
    def open_tool(cls):
        if not window.project_dir:QMessageBox.information(window,'Проект','Сначала откройте проект.');return
        if window.viewport.is_playing and cls is not MixerDialog:QMessageBox.information(window,'Проект','Остановите Play перед настройкой.');return
        cls(window).exec()
    menu.addSeparator();menu.addAction('Аудиомикшер…',lambda:open_tool(MixerDialog));menu.addAction('Редактор кат-сцен…',lambda:open_tool(CutsceneDialog))
    def lighting():
        if not window.project_dir:return
        current=window.settings.get('render',{}).get('ambient_color',[255,255,255])
        color=QColorDialog.getColor(QColor(*current[:3]),window,'Окружающий свет сцены')
        if color.isValid():
            try:window.settings.setdefault('render',{})['ambient_color']=[color.red(),color.green(),color.blue()];save_settings(window);window.viewport.settings=copy.deepcopy(window.settings);window.viewport.update()
            except OSError as error:QMessageBox.warning(window,'Освещение',str(error))
    menu.addAction('Окружающий свет…',lighting)
    team=menu.addMenu('Командная работа')
    def command(action):
        try:
            if not window.project_dir:raise ValueError('Откройте проект')
            from engine.resources.teamwork import prepare_project,reserve,release
            if action=='prepare':prepare_project(window.project_dir)
            else:
                if not window.current_scene or not window.current_scene.path:raise ValueError('Сначала сохраните сцену')
                (reserve if action=='reserve' else release)(window.current_scene.path)
            QMessageBox.information(window,'Командная работа','Готово. Резервирование работает в общей папке; изменения Git передавайте обычным commit/pull.')
        except (ValueError,OSError,KeyError) as error:QMessageBox.warning(window,'Командная работа',str(error))
    team.addAction('Подготовить проект для Git',lambda:command('prepare'))
    team.addAction('Зарезервировать текущую сцену',lambda:command('reserve'))
    team.addAction('Освободить текущую сцену',lambda:command('release'))
