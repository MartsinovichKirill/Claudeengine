"""Pixel-coordinate rectangular hit/hurt authoring with frame scrubbing."""
import copy
from pathlib import Path
from PyQt6.QtCore import Qt,QRectF,QPointF,pyqtSignal
from PyQt6.QtGui import QPainter,QColor,QPen,QPixmap,QKeySequence,QShortcut
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QWidget,QListWidget,QLabel,
    QPushButton,QComboBox,QDoubleSpinBox,QSpinBox,QFormLayout,QSplitter,QDialogButtonBox,
    QMessageBox,QAbstractItemView)
from engine.systems.frame_hitboxes import validate_boxes
from editor.authoring_style import apply,COLORS


class BoxCanvas(QWidget):
    changed=pyqtSignal()
    selected=pyqtSignal(int)
    def __init__(self,editor):
        super().__init__();self.editor=editor;self.setMinimumSize(440,380)
        self.start=None;self.drag=None;self.factor=1;self.origin=QPointF();self.image=QPixmap()
        self.setMouseTracking(True)

    def load(self,path):self.image=QPixmap(str(path));self.update()

    def mapping(self):
        w,h=max(1,self.image.width()),max(1,self.image.height())
        self.factor=max(.1,min((self.width()-80)/w,(self.height()-80)/h)*self.editor.zoom.value()/100)
        self.origin=QPointF((self.width()-w*self.factor)/2,(self.height()-h*self.factor)/2)

    def point(self,pos):return (pos-self.origin)/self.factor

    def paintEvent(self,event):
        self.mapping();p=QPainter(self);p.fillRect(self.rect(),QColor(COLORS['bg_dark']))
        if self.image.isNull():return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,False)
        p.translate(self.origin);p.scale(self.factor,self.factor)
        w,h=self.image.width(),self.image.height()
        p.fillRect(QRectF(0,0,w,h),QColor(COLORS['bg_alt']));p.drawPixmap(0,0,self.image)
        p.setPen(QPen(QColor(COLORS['border']),1/self.factor));p.drawRect(QRectF(0,0,w,h))
        for i,box in enumerate(self.editor.boxes()):
            c=QColor('#ef716d' if box['kind']=='hit' else '#71ba87');fill=QColor(c);fill.setAlpha(45)
            p.setBrush(fill);pen=QPen(c,(2 if i==self.editor.current else 1)/self.factor)
            if not box.get('enabled',True):pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen);p.drawRect(QRectF(*box['rect']))
            if i==self.editor.current:
                x,y,bw,bh=box['rect'];s=7/self.factor;p.fillRect(QRectF(x+bw-s/2,y+bh-s/2,s,s),c)
        if self.start is not None and self.drag=='new':
            p.setPen(QPen(QColor('#f6cd71'),1/self.factor));p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(self.start,self.end).normalized())

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        point=self.point(event.position());self.start=point;self.end=point
        boxes=self.editor.boxes()
        for i in reversed(range(len(boxes))):
            rect=QRectF(*boxes[i]['rect'])
            if rect.adjusted(-3/self.factor,-3/self.factor,3/self.factor,3/self.factor).contains(point):
                self.editor.select(i);self.editor.checkpoint()
                self.original=list(boxes[i]['rect'])
                self.drag='resize' if (point-rect.bottomRight()).manhattanLength()<14/self.factor else 'move'
                self.update();return
        self.drag='new';self.editor.select(-1);self.update()

    def mouseMoveEvent(self,event):
        if self.start is None:return
        self.end=self.point(event.position());delta=self.end-self.start
        if self.drag in ('move','resize') and self.editor.current>=0:
            x,y,w,h=self.original
            if self.drag=='move':x+=delta.x();y+=delta.y()
            else:w=max(1,w+delta.x());h=max(1,h+delta.y())
            self.editor.boxes()[self.editor.current]['rect']=[round(x),round(y),round(w),round(h)]
            self.editor.refresh_fields()
        self.update()

    def mouseReleaseEvent(self,event):
        if self.start is None:return
        if self.drag=='new':
            rect=QRectF(self.start,self.point(event.position())).normalized()
            if rect.width()>=1 and rect.height()>=1:
                self.editor.checkpoint();kind=self.editor.kind.currentData()
                used={b['id'] for b in self.editor.boxes()};index=1
                while f'{kind}_{index}' in used:index+=1
                self.editor.boxes().append({'id':f'{kind}_{index}','kind':kind,'rect':[round(rect.x()),round(rect.y()),max(1,round(rect.width())),max(1,round(rect.height()))],'layer':1,'mask':1})
                self.editor.select(len(self.editor.boxes())-1)
        self.start=None;self.drag=None;self.editor.refresh_list();self.update()


class HitboxEditor(QDialog):
    def __init__(self,clip,project,parent=None):
        super().__init__(parent);apply(self);self.setWindowTitle('Хитбоксы по кадрам');self.resize(1160,760)
        self.result_clip=None;self.clip=copy.deepcopy(clip);self.project=Path(project);self.frame=0;self.current=-1;self.history=[];self.future=[];self.loading=False
        root=QVBoxLayout(self);bar=QHBoxLayout();root.addLayout(bar)
        bar.addWidget(QLabel('Область'))
        self.kind=QComboBox();self.kind.addItem('Удар · Hit','hit');self.kind.addItem('Уязвимость · Hurt','hurt');bar.addWidget(self.kind)
        bar.addStretch();bar.addWidget(QLabel('Масштаб %'));self.zoom=QSpinBox();self.zoom.setRange(25,400);self.zoom.setValue(100);bar.addWidget(self.zoom)
        split=QSplitter();root.addWidget(split,1)
        self.canvas=BoxCanvas(self);split.addWidget(self.canvas);self.zoom.valueChanged.connect(self.canvas.update)
        panel=QWidget();panel.setObjectName('Panel');side=QVBoxLayout(panel);split.addWidget(panel)
        self.list=QListWidget();side.addWidget(QLabel('Области текущего кадра'));side.addWidget(self.list);self.list.currentRowChanged.connect(self.select)
        form=QFormLayout();side.addLayout(form);self.fields={}
        for name in ('x','y','width','height'):
            field=QDoubleSpinBox();field.setRange(-4096 if name in ('x','y') else 1,4096);field.setDecimals(0);field.valueChanged.connect(self.field_changed);form.addRow(name,field);self.fields[name]=field
        self.layer=QSpinBox();self.mask=QSpinBox()
        for title,control in [('Слой',self.layer),('Маска',self.mask)]:control.setRange(0,65535);control.setValue(1);control.valueChanged.connect(self.field_changed);form.addRow(title,control)
        for title,action in [('Удалить область',self.delete),('Копировать предыдущий кадр',self.previous),('На выделенные кадры',self.copy_to_selection),('Отменить',self.undo),('Повторить',self.redo)]:
            b=QPushButton(title);b.clicked.connect(action);side.addWidget(b)
        split.setSizes([820,300])
        self.timeline=QListWidget();self.timeline.setFlow(QListWidget.Flow.LeftToRight);self.timeline.setMaximumHeight(90)
        self.timeline.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for i in range(len(self.clip['frames'])):self.timeline.addItem(f'{i:03d}')
        self.timeline.currentRowChanged.connect(self.set_frame);root.addWidget(QLabel('Кадры · Ctrl/Shift — выделение для копирования'));root.addWidget(self.timeline)
        root.addWidget(QLabel('Тяните мышью для новой области. Внутри — перемещение; правый нижний угол — размер. Красный — удар, зелёный — уязвимость.'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);root.addWidget(buttons)
        QShortcut(QKeySequence.StandardKey.Undo,self,activated=self.undo);QShortcut(QKeySequence.StandardKey.Redo,self,activated=self.redo)
        self.timeline.setCurrentRow(0)

    def boxes(self):return self.clip.setdefault('hitboxes',{}).setdefault(str(self.frame),[])
    def checkpoint(self):self.history.append(copy.deepcopy(self.clip['hitboxes']));self.history=self.history[-100:];self.future.clear()
    def undo(self):
        if self.history:self.future.append(copy.deepcopy(self.clip['hitboxes']));self.clip['hitboxes']=self.history.pop();self.current=-1;self.refresh_list()
    def redo(self):
        if self.future:self.history.append(copy.deepcopy(self.clip['hitboxes']));self.clip['hitboxes']=self.future.pop();self.current=-1;self.refresh_list()
    def set_frame(self,index):
        if index<0:return
        self.frame=index;self.current=-1;self.canvas.load(self.project/self.clip['frames'][index]);self.refresh_list()
    def select(self,index):self.current=index;self.refresh_fields();self.canvas.update()
    def refresh_list(self):
        self.list.blockSignals(True);self.list.clear()
        for box in self.boxes():self.list.addItem(box['id']+' · '+box['kind'])
        self.list.setCurrentRow(self.current);self.list.blockSignals(False);self.refresh_fields();self.canvas.update()
    def refresh_fields(self):
        self.loading=True;valid=0<=self.current<len(self.boxes())
        for field in [*self.fields.values(),self.layer,self.mask]:field.setEnabled(valid)
        if valid:
            box=self.boxes()[self.current]
            for field,value in zip(self.fields.values(),box['rect']):field.setValue(value)
            self.layer.setValue(box.get('layer',1));self.mask.setValue(box.get('mask',1))
        self.loading=False
    def field_changed(self):
        if self.loading or not 0<=self.current<len(self.boxes()):return
        self.checkpoint();box=self.boxes()[self.current];box['rect']=[f.value() for f in self.fields.values()];box.update(layer=self.layer.value(),mask=self.mask.value());self.canvas.update()
    def delete(self):
        if 0<=self.current<len(self.boxes()):self.checkpoint();self.boxes().pop(self.current);self.current=-1;self.refresh_list()
    def previous(self):
        if self.frame>0:self.checkpoint();self.clip['hitboxes'][str(self.frame)]=copy.deepcopy(self.clip['hitboxes'].get(str(self.frame-1),[]));self.refresh_list()
    def copy_to_selection(self):
        self.checkpoint();boxes=copy.deepcopy(self.boxes())
        for item in self.timeline.selectedItems():self.clip['hitboxes'][str(self.timeline.row(item))]=copy.deepcopy(boxes)
        self.refresh_list()
    def save(self):
        try:validate_boxes(self.clip.get('hitboxes',{}));self.result_clip=copy.deepcopy(self.clip);self.accept()
        except ValueError as ex:QMessageBox.warning(self,'Хитбоксы',str(ex))
