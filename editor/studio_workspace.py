"""Mixer channel strips and cinematic timeline shared authoring surfaces."""
import math
from PyQt6.QtCore import Qt,QPointF,QTimer
from PyQt6.QtGui import QColor,QPen,QPainter,QBrush
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QSlider,QDoubleSpinBox,
    QCheckBox,QFrame,QSplitter,QListWidget,QFormLayout,QGraphicsView,QGraphicsScene,QGraphicsRectItem,
    QAbstractItemView,QTabWidget,QLineEdit,QComboBox,QSpinBox,QTableWidgetItem)
from editor.authoring_style import apply,COLORS


def build_mixer(dialog,window):
    apply(dialog);dialog.resize(1060,650);dialog.controls={};dialog.solos={};dialog.original_live=None
    root=QVBoxLayout(dialog);top=QHBoxLayout();root.addLayout(top)
    top.addWidget(QLabel('AUDIO MIXER'));top.addStretch();top.addWidget(QLabel('Маршрут: Music / SFX / UI → Master → выход'))
    split=QSplitter();root.addWidget(split,1)
    list=QListWidget();list.addItems(['Master','  Music','  SFX','  UI']);list.setMaximumWidth(180);split.addWidget(list)
    channels=QWidget();row=QHBoxLayout(channels);row.setSpacing(12);split.addWidget(channels)
    config=window.settings.get('audio',{})
    for bus in ('master','music','sfx','ui'):
        panel=QFrame();panel.setObjectName('Panel');strip=QVBoxLayout(panel);strip.setContentsMargins(14,12,14,12)
        title=QLabel(bus.upper());title.setObjectName('PanelTitle');title.setAlignment(Qt.AlignmentFlag.AlignCenter);strip.addWidget(title)
        route=QLabel('Выход' if bus=='master' else '→ Master');route.setAlignment(Qt.AlignmentFlag.AlignCenter);strip.addWidget(route)
        mute=QCheckBox('Mute');mute.setChecked(bus in config.get('muted',[]));solo=QCheckBox('Solo');solo.setEnabled(bus!='master');dialog.solos[bus]=solo
        switches=QHBoxLayout();switches.addWidget(mute);switches.addWidget(solo);strip.addLayout(switches)
        db=QDoubleSpinBox();db.setRange(-80,0);db.setDecimals(1);db.setSuffix(' dB')
        volume=QDoubleSpinBox();volume.setRange(0,1);volume.setDecimals(4);volume.hide()
        volume.setValue(float(config.get('volumes',config).get(bus,1)));strip.addWidget(volume)
        fader=QSlider(Qt.Orientation.Vertical);fader.setRange(-800,0);fader.setTickPosition(QSlider.TickPosition.TicksBothSides);fader.setTickInterval(100)
        center=QHBoxLayout();center.addStretch();center.addWidget(fader);center.addStretch();strip.addLayout(center,1);strip.addWidget(db)
        def sync(value,slider=fader,spin=db):
            decibels=-80 if value<=.0001 else max(-80,20*math.log10(value))
            for control in (slider,spin):control.blockSignals(True)
            slider.setValue(round(decibels*10));spin.setValue(decibels)
            for control in (slider,spin):control.blockSignals(False)
        volume.valueChanged.connect(sync);sync(volume.value())
        def set_db(value,control=volume):control.setValue(0 if value<=-80 else 10**(value/20))
        fader.valueChanged.connect(lambda value,fn=set_db:fn(value/10));db.valueChanged.connect(set_db)
        reset=QPushButton('0 dB');reset.clicked.connect(lambda checked=False,v=volume:v.setValue(1));strip.addWidget(reset)
        dialog.controls[bus]=(volume,mute);row.addWidget(panel,1)
        for signal in (volume.valueChanged,mute.toggled,solo.toggled):signal.connect(dialog.live)
    audio=getattr(getattr(window.viewport,'scene_tree',None),'audio_system',None)
    if audio:dialog.original_live=(dict(audio.bus_volumes),set(audio.muted))
    dialog.finished.connect(dialog.finish)
    hint=QLabel('Фейдеры задают усиление, это не индикаторы измеренной громкости. Solo действует только для прослушивания в Play и не сохраняется.');hint.setWordWrap(True);root.addWidget(hint)
    footer=QHBoxLayout();footer.addStretch();cancel=QPushButton('Отмена');cancel.clicked.connect(dialog.reject);footer.addWidget(cancel)
    save=QPushButton('Сохранить микшер');save.clicked.connect(dialog.save);footer.addWidget(save);root.addLayout(footer)


class TimelineBlock(QGraphicsRectItem):
    def __init__(self,timeline,row,start,duration,color):
        width=max(12,duration*timeline.pps)
        super().__init__(0,0,width,36);self.timeline=timeline;self.row=row
        self.setPos(180+start*timeline.pps,42+row*58)
        self.setBrush(QBrush(QColor(color)));self.setPen(QPen(QColor('#90a5b2')))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setToolTip('Перетаскивание — начало; правый край — длительность')
    def mousePressEvent(self,event):
        self.timeline.dialog.restore()
        self.timeline.dialog.table.selectRow(self.row)
        self.start=self.pos().x();self.anchor=event.scenePos().x();self.duration=self.rect().width()
        self.resizing=event.pos().x()>self.rect().width()-9
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        delta=event.scenePos().x()-self.anchor
        if self.resizing:self.setRect(0,0,max(12,self.duration+delta),36)
        else:self.setPos(max(180,self.start+delta),self.pos().y())
    def mouseReleaseEvent(self,event):
        start=max(0,round((self.pos().x()-180)/self.timeline.pps,2))
        duration=round(self.rect().width()/self.timeline.pps,2)
        table=self.timeline.dialog.table;table.blockSignals(True)
        item=QTableWidgetItem(str(start));item.setData(Qt.ItemDataRole.UserRole,self.timeline.dialog.track_kind(self.row));table.setItem(self.row,0,item)
        if self.resizing:table.setItem(self.row,1,QTableWidgetItem(str(duration)))
        table.blockSignals(False);self.timeline.dialog.sync_inspector()
        super().mouseReleaseEvent(event)
        QTimer.singleShot(0,self.timeline.refresh)


class CinematicTimeline(QGraphicsView):
    def __init__(self,dialog):
        super().__init__();self.dialog=dialog;self.pps=90;self.scene=QGraphicsScene(self);self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing);self.setMinimumHeight(300)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.cursor_item=None
    def refresh(self,*_):
        self.scene.clear();self.cursor_item=None;table=self.dialog.table
        length=10
        for row in range(table.rowCount()):
            try:
                end=float(table.item(row,0).text())+float(table.item(row,1).text())+1
                if math.isfinite(end):length=max(length,min(3600,end))
            except (ValueError,AttributeError):pass
        width=180+length*self.pps;height=max(320,table.rowCount()*58+60)
        self.scene.setBackgroundBrush(QColor(COLORS['bg_dark']))
        for second in range(min(3600,math.ceil(length))+1):
            x=180+second*self.pps
            self.scene.addLine(x,25,x,height,QPen(QColor(COLORS['border'])))
            text=self.scene.addText(str(second)+'s');text.setDefaultTextColor(QColor(COLORS['text_dim']));text.setPos(x,0)
        for row in range(table.rowCount()):
            def value(col):return table.item(row,col).text() if table.item(row,col) else ''
            try:start=float(value(0));duration=float(value(1))
            except ValueError:continue
            if not math.isfinite(start) or not math.isfinite(duration) or start<0 or duration<0:continue
            start=min(start,3600);duration=min(duration,3600)
            kind=self.dialog.track_kind(row);color={'audio':'#5a7756','event':'#97794a'}.get(kind,'#466d88' if 'Camera' in value(2) or 'camera' in value(2).lower() else '#655a81')
            self.scene.addLine(0,40+row*58,width,40+row*58,QPen(QColor(COLORS['border'])))
            text=self.scene.addText((value(2) or '.')+'\n'+('Событие' if kind=='event' else 'Звук' if kind=='audio' else value(4)))
            text.setDefaultTextColor(QColor(COLORS['text']));text.setPos(6,40+row*58);text.setTextWidth(165)
            block=TimelineBlock(self,row,start,duration,color);self.scene.addItem(block)
            caption=self.scene.addText(value(4));caption.setDefaultTextColor(QColor('white'));caption.setPos(block.x()+6,block.y()+4);caption.setParentItem(block);caption.setPos(6,4);caption.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.cursor_item=self.scene.addLine(0,0,0,height,QPen(QColor('#f3b454'),2));self.cursor_item.setZValue(10)
        self.scene.setSceneRect(0,0,width,height);self.set_cursor(self.dialog.cursor.value())
    def set_cursor(self,value):
        if self.cursor_item:self.cursor_item.setPos(180+value*self.pps,0)
    def mousePressEvent(self,event):
        point=self.mapToScene(event.pos())
        if point.y()<38 and point.x()>=180:
            self.dialog.cursor.setValue((point.x()-180)/self.pps);self.dialog.scrub();return
        super().mousePressEvent(event)
    def wheelEvent(self,event):
        if event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            self.pps=max(20,min(400,self.pps*(1.15 if event.angleDelta().y()>0 else 1/1.15)));self.refresh()
        else:super().wheelEvent(event)


def enhance_cutscene(dialog,root):
    apply(dialog);dialog.resize(1340,800)
    # Keep the validated legacy table as an advanced data view.
    root.removeWidget(dialog.table);dialog.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    split=QSplitter();center=QWidget();center_box=QVBoxLayout(center)
    toolbar=QHBoxLayout();toolbar.addWidget(QLabel('TIMELINE'));toolbar.addStretch()
    for text,scale in [('−',.8),('+',1.25)]:
        button=QPushButton(text);button.clicked.connect(lambda checked=False,k=scale:(setattr(dialog.timeline,'pps',max(20,min(400,dialog.timeline.pps*k))),dialog.timeline.refresh()));toolbar.addWidget(button)
    center_box.addLayout(toolbar)
    dialog.timeline=CinematicTimeline(dialog);center_box.addWidget(dialog.timeline,1)
    tabs=QTabWidget();tabs.addTab(center,'Дорожки');tabs.addTab(dialog.table,'Таблица данных');split.addWidget(tabs)
    inspector=QWidget();inspector.setObjectName('Panel');form=QFormLayout(inspector);form.addRow(QLabel('Свойства выбранного клипа'))
    dialog.kind_control=QComboBox();dialog.kind_control.addItems(['Свойство','Звук','Событие']);form.addRow('Тип',dialog.kind_control)
    dialog.track_fields=[]
    for title in dialog.headers:
        edit=QLineEdit();form.addRow(title,edit);dialog.track_fields.append(edit)
        edit.editingFinished.connect(dialog.apply_inspector)
    dialog.kind_control.currentIndexChanged.connect(dialog.apply_inspector)
    help=QLabel('Звук: путь к AudioStreamPlayer, действие play.\nСобытие: путь к объекту, имя метода в поле «Свойство», аргументы JSON в «От».\nПредпросмотр не запускает звук и методы.');help.setWordWrap(True);form.addRow(help)
    split.addWidget(inspector);split.setSizes([1020,300]);root.insertWidget(1,split,1)
    dialog.table.itemChanged.connect(dialog.timeline.refresh);dialog.table.itemSelectionChanged.connect(dialog.sync_inspector)
    dialog.cursor.valueChanged.connect(dialog.timeline.set_cursor)
    dialog.timeline.refresh()
