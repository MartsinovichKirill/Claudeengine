"""Visual UI composition with draggable/resizable rectangles and anchor previews."""
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QBrush, QPen, QFont, QPixmap, QFontDatabase
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QComboBox, QFormLayout, QLineEdit, QSpinBox,
    QDialogButtonBox, QLabel, QGraphicsItem, QFileDialog, QGroupBox, QScrollArea, QWidget)
from engine.math.vector2 import Vector2
from engine.nodes import NODE_CLASSES
from engine.resources.scene_serializer import SceneSerializer


class UIItem(QGraphicsRectItem):
    def __init__(self, editor, node, position, size):
        super().__init__(0,0,max(size.x,12),max(size.y,12))
        self.editor=editor; self.node=node; self.resizing=False
        self.setPos(position.x,position.y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPen(QPen(QColor('#78b8e8')))
        self.setBrush(QBrush(QColor('#284760')))
    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        texture=getattr(self.node,'texture_normal','')
        if texture:
            path=self.editor.resource_path(texture)
            if path not in self.editor.resource_cache:self.editor.resource_cache[path]=QPixmap(path)
            pixmap=self.editor.resource_cache[path]
            if not pixmap.isNull():painter.drawPixmap(self.rect().toRect(),pixmap)
        family='Segoe UI';font_path=getattr(self.node,'font_path','')
        if font_path:
            path=self.editor.resource_path(font_path)
            key='font:'+path
            if key not in self.editor.resource_cache:
                ident=QFontDatabase.addApplicationFont(path)
                names=QFontDatabase.applicationFontFamilies(ident) if ident>=0 else []
                self.editor.resource_cache[key]=names[0] if names else family
            family=self.editor.resource_cache[key]
        painter.setPen(QColor('#e0e9f4')); painter.setFont(QFont(family,max(6,min(256,getattr(self.node,'font_size',14)))))
        painter.drawText(self.rect().adjusted(6,2,-6,-2),Qt.AlignmentFlag.AlignCenter,getattr(self.node,'text',self.node.name))
        painter.fillRect(QRectF(self.rect().right()-9,self.rect().bottom()-9,8,8),QColor('#85c7f3'))
    def mousePressEvent(self,event):
        self.resizing=event.pos().x()>self.rect().right()-14 and event.pos().y()>self.rect().bottom()-14
        self.editor.select(self.node)
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.resizing:
            self.setRect(0,0,max(12,event.pos().x()),max(12,event.pos().y()))
        else:
            super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        transform=self.node.get_component('RectTransform')
        screen=Vector2(*self.editor.resolution())
        anchor=Vector2(screen.x*transform.anchor_min.x,screen.y*transform.anchor_min.y)
        size=Vector2(self.rect().width(),self.rect().height())
        transform.size_delta=size-Vector2(screen.x*(transform.anchor_max.x-transform.anchor_min.x),screen.y*(transform.anchor_max.y-transform.anchor_min.y))
        transform.offset=Vector2(self.pos().x(),self.pos().y())-anchor+Vector2(size.x*transform.pivot.x,size.y*transform.pivot.y)
        self.editor.select(self.node)
        self.editor.rebuild()


class UIEditor(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Редактор интерфейсов'); self.resize(1100,780)
        self.layer=SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(layer))
        self.selected=None; self.result_data=None; self.loading=False
        self.project_dir=getattr(parent,'project_dir','')
        self.resource_cache={}
        self.setMinimumSize(1000,700)
        self.setStyleSheet('QDialog { background:#17212d; } QGroupBox { border:1px solid #35495b; border-radius:8px; margin-top:15px; padding:15px 10px; } QGraphicsView { background:#0d151e; border:1px solid #35495b; border-radius:8px; } QPushButton { padding:8px 12px; border-radius:5px; }')
        layout=QVBoxLayout(self); toolbar=QHBoxLayout()
        self.screen=QComboBox()
        for label in ('1280 × 720','1920 × 1080','800 × 600','720 × 1280','2560 × 1440'):
            self.screen.addItem(label)
        self.screen.currentIndexChanged.connect(self.rebuild); toolbar.addWidget(self.screen)
        for kind,label in (('Label','Текст'),('Button','Кнопка'),('TextureRect','Изображение'),('ProgressBar','Прогресс')):
            button=QPushButton(label);
            from editor.icons import get_icon
            button.setIcon(get_icon({'Label':'script','Button':'component','TextureRect':'image','ProgressBar':'align'}[kind])); button.clicked.connect(lambda checked=False,k=kind:self.add(k)); toolbar.addWidget(button)
        delete=QPushButton('Удалить'); delete.clicked.connect(self.remove); toolbar.addWidget(delete)
        for title,kind in [('Строка','HorizontalLayout'),('Колонка','VerticalLayout')]:
            button=QPushButton(title);button.clicked.connect(lambda checked=False,k=kind:self.set_layout(k));toolbar.addWidget(button)
        layout.addLayout(toolbar)
        layout.addWidget(QLabel('Перетаскивайте элементы. Нижний правый угол изменяет размер. Привязки проверяются при смене разрешения.'))
        self.scene=QGraphicsScene(self); self.view=QGraphicsView(self.scene)
        body=QHBoxLayout();body.addWidget(self.view,1);layout.addLayout(body,1)
        properties=QGroupBox('Свойства элемента');properties.setMinimumWidth(290);properties.setMaximumWidth(360)
        sidebar=QScrollArea();sidebar.setWidgetResizable(True);sidebar.setWidget(properties);sidebar.setMinimumWidth(310);sidebar.setMaximumWidth(380);body.addWidget(sidebar)
        form=QFormLayout(properties); self.name=QLineEdit(); self.text=QLineEdit()
        form.addRow('Имя',self.name); form.addRow('Текст',self.text)
        self.anchor=QComboBox(); self.anchor.addItems(['Слева сверху','По центру','Справа сверху','Слева снизу','Справа снизу','Растянуть по ширине','Растянуть полностью'])
        form.addRow('Привязка',self.anchor)
        dimensions=QHBoxLayout(); self.width=QSpinBox(); self.height=QSpinBox()
        for field in (self.width,self.height): field.setRange(12,10000); dimensions.addWidget(field)
        form.addRow('Размер',dimensions)
        self.font_size=QSpinBox();self.font_size.setRange(6,256);form.addRow('Размер текста',self.font_size)
        self.font_size.valueChanged.connect(self.apply_fields)
        self.resources={}
        for key,title in [('font_path','Шрифт TTF / OTF'),('texture_normal','Текстура кнопки'),('texture_hover','При наведении'),('texture_pressed','При нажатии')]:
            row=QHBoxLayout();field=QLineEdit();field.setPlaceholderText('Ресурс проекта');self.resources[key]=field
            row.addWidget(field);pick=QPushButton('…');pick.setFixedWidth(32);pick.clicked.connect(lambda checked=False,k=key:self.pick_resource(k));row.addWidget(pick)
            form.addRow(title,row);field.editingFinished.connect(self.apply_fields)
        self.name.editingFinished.connect(self.apply_fields); self.text.editingFinished.connect(self.apply_fields)
        self.width.valueChanged.connect(self.apply_fields); self.height.valueChanged.connect(self.apply_fields)
        self.anchor.currentIndexChanged.connect(self.change_anchor)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept_data); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.rebuild()

    def set_layout(self,kind):
        for component in list(self.layer.components):
            if component.get_type_name() in ('HorizontalLayout','VerticalLayout'):self.layer.remove_component(component)
        self.layer.add_component(kind);self.rebuild()

    def pick_resource(self,key):
        from pathlib import Path
        import shutil
        filters='Fonts (*.ttf *.otf)' if key=='font_path' else 'Images (*.png *.jpg *.webp *.bmp)'
        path,_=QFileDialog.getOpenFileName(self,'Выбрать ресурс',self.project_dir,filters)
        if not path:return
        try:
            source=Path(path).resolve()
            if self.project_dir:
                root=Path(self.project_dir).resolve()
                if not source.is_relative_to(root):
                    target=root/'assets'/('fonts' if key=='font_path' else 'ui')/source.name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists():
                        if target.read_bytes()!=source.read_bytes():raise ValueError('Файл с таким именем уже существует')
                    else:shutil.copy2(source,target)
                    source=target
                value=source.relative_to(root).as_posix()
            else:value=str(source)
            self.resources[key].setText(value);self.apply_fields()
        except (OSError,ValueError) as error:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self,'Ресурс',str(error))

    def resource_path(self,path):
        from pathlib import Path
        return str(Path(self.project_dir)/path) if self.project_dir else path

    def resolution(self):
        return tuple(int(v.strip()) for v in self.screen.currentText().split('×'))

    def transform(self,node):
        transform=node.get_component('RectTransform')
        if transform is None:
            transform=node.add_component('RectTransform')
            transform.offset=Vector2(node.position)
            transform.size_delta=Vector2(getattr(node,'size',Vector2(180,40)))
            transform.anchor_min=Vector2(getattr(node,'anchor_left',0),getattr(node,'anchor_top',0))
            transform.anchor_max=Vector2(transform.anchor_min)
        return transform

    def rebuild(self,*args):
        if not hasattr(self,'scene'): return
        self.scene.clear(); w,h=self.resolution()
        from engine.components.ui_layout import arrange_tree
        arrange_tree(self.layer,Vector2(w,h))
        self.scene.setSceneRect(0,0,w,h)
        self.scene.addRect(0,0,w,h,QPen(QColor('#52728d')),QBrush(QColor('#101d29')))
        for node in self.layer.get_children():
            if hasattr(node,'position'):
                position,size=self.transform(node).resolve(Vector2(w,h))
                item=UIItem(self,node,position,size); self.scene.addItem(item)
                if node is self.selected: item.setSelected(True)
        self.view.fitInView(self.scene.sceneRect().adjusted(-20,-20,20,20),Qt.AspectRatioMode.KeepAspectRatio)

    def add(self,kind):
        node=NODE_CLASSES[kind]()
        node.name=kind+str(len(self.layer.get_children())+1)
        self.layer.add_child(node); self.transform(node)
        self.select(node); self.rebuild()

    def remove(self):
        if self.selected:
            self.layer.remove_child(self.selected); self.selected=None; self.rebuild()

    def select(self,node):
        self.selected=node; self.loading=True
        self.name.setText(node.name); self.text.setText(getattr(node,'text',''))
        self.font_size.setValue(getattr(node,'font_size',16));self.font_size.setEnabled(hasattr(node,'font_size'))
        for key,field in self.resources.items():
            field.setText(getattr(node,key,''));field.setEnabled(hasattr(node,key))
        position,size=self.transform(node).resolve(Vector2(*self.resolution()))
        self.width.setValue(round(size.x)); self.height.setValue(round(size.y))
        transform=self.transform(node)
        presets=[((0,0),(0,0)),((.5,.5),(.5,.5)),((1,0),(1,0)),((0,1),(0,1)),((1,1),(1,1)),((0,0),(1,0)),((0,0),(1,1))]
        index=next((i for i,(low,high) in enumerate(presets) if transform.anchor_min==Vector2(low) and transform.anchor_max==Vector2(high)),-1)
        self.anchor.setCurrentIndex(index)
        self.loading=False

    def apply_fields(self,*args):
        if not self.selected or self.loading: return
        self.selected.name=self.name.text().strip() or self.selected.name
        if hasattr(self.selected,'text'): self.selected.text=self.text.text()
        if hasattr(self.selected,'font_size'):self.selected.font_size=self.font_size.value()
        for key,field in self.resources.items():
            if hasattr(self.selected,key):setattr(self.selected,key,field.text().strip())
        transform=self.transform(self.selected); screen=Vector2(*self.resolution())
        transform.size_delta=Vector2(self.width.value()-screen.x*(transform.anchor_max.x-transform.anchor_min.x),self.height.value()-screen.y*(transform.anchor_max.y-transform.anchor_min.y))
        self.rebuild()

    def change_anchor(self,index):
        if not self.selected or self.loading or index < 0: return
        if hasattr(self.selected,'font_size'):self.selected.font_size=self.font_size.value()
        for key,field in self.resources.items():
            if hasattr(self.selected,key):setattr(self.selected,key,field.text().strip())
        transform=self.transform(self.selected); screen=Vector2(*self.resolution())
        position,size=transform.resolve(screen)
        presets=[((0,0),(0,0)),((.5,.5),(.5,.5)),((1,0),(1,0)),((0,1),(0,1)),((1,1),(1,1)),((0,0),(1,0)),((0,0),(1,1))]
        low,high=presets[index]; transform.anchor_min=Vector2(low); transform.anchor_max=Vector2(high)
        if low==high:
            transform.pivot=Vector2(low); transform.offset=Vector2(); transform.size_delta=size
        else:
            transform.pivot=Vector2(); transform.offset=Vector2(10,10)
            transform.size_delta=Vector2(-20 if high[0]>low[0] else size.x,-20 if high[1]>low[1] else size.y)
        self.loading=True; self.anchor.setCurrentIndex(index); self.loading=False
        self.rebuild()

    def accept_data(self):
        self.apply_fields(); self.result_data=SceneSerializer.node_to_dict(self.layer); self.accept()
