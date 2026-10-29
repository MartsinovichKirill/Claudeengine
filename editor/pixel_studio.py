"""Small pixel-art frame editor with undo and horizontal sprite-sheet export."""
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer,QSize,QRect
from PyQt6.QtGui import QImage,QPainter,QColor,QPixmap,QIcon
from PyQt6.QtWidgets import QDialog,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QColorDialog,QFileDialog,QSpinBox,QLabel,QMessageBox,QToolButton,QFrame,QListWidget,QListWidgetItem,QAbstractItemView,QScrollArea,QComboBox

class PixelCanvas(QWidget):
    def __init__(self, editor):
        super().__init__();self.editor=editor;self.setMinimumSize(512,512)
    def paintEvent(self,event):
        p=QPainter(self)
        for y in range(0,self.height(),16):
            for x in range(0,self.width(),16):
                p.fillRect(x,y,16,16,QColor('#263443' if (x//16+y//16)%2 else '#1c2936'))
        p.drawImage(self.rect(),self.editor.frames[self.editor.index])
    def mousePressEvent(self,event):
        self.editor.history.append(([f.copy() for f in self.editor.frames],self.editor.index))
        self.draw(event)
    def mouseMoveEvent(self,event):
        if event.buttons():self.draw(event)
    def draw(self,event):
        image=self.editor.frames[self.editor.index]
        x=int(event.position().x()*image.width()/self.width());y=int(event.position().y()*image.height()/self.height())
        if 0<=x<image.width() and 0<=y<image.height():
            image.setPixelColor(x,y,QColor(0,0,0,0) if self.editor.erase else self.editor.color);self.update()

class PixelStudio(QDialog):
    def __init__(self,project,parent=None):
        super().__init__(parent);self.project=project;self.frames=[];self.index=0;self.history=[];self.color=QColor('white');self.erase=False
        self.setWindowTitle('Pixel Studio — рисунок и покадровая анимация');self.resize(720,740)
        self.resize(1120,820)
        self.setMinimumSize(900,680)
        self.setObjectName('PixelStudio')
        self.setStyleSheet("""
            QDialog#PixelStudio { background:#141e29; }
            QFrame#PixelHeader, QFrame#PixelTimeline { background:#1b2937; border:1px solid #2d4052; border-radius:8px; }
            QLabel#PixelTitle { font-size:19px; font-weight:600; color:#e6eef7; }
            QLabel#PixelMuted { color:#8fa6ba; font-size:12px; }
            QToolButton { background:transparent; border:1px solid transparent; border-radius:6px; padding:8px; }
            QToolButton:hover { background:#2a3e51; }
            QToolButton:checked { background:#294e6c; border:1px solid #579ac8; }
            QListWidget { background:#121d28; border:0; }
            QListWidget::item { padding:5px; margin:3px; border:1px solid #33495b; border-radius:5px; }
            QListWidget::item:selected { background:#294e6c; border:1px solid #72b7e6; }
            QPushButton { padding:8px 12px; border-radius:5px; }
        """)
        layout=QVBoxLayout(self);layout.setContentsMargins(16,16,16,12);layout.setSpacing(12)
        header=QFrame();header.setObjectName('PixelHeader');row=QHBoxLayout(header)
        title=QLabel('Pixel Studio');title.setObjectName('PixelTitle');row.addWidget(title)
        caption=QLabel('Рисование и покадровая анимация');caption.setObjectName('PixelMuted');row.addWidget(caption);row.addStretch()
        self.size=QSpinBox();self.size.setRange(8,256);self.size.setValue(32)
        row.addWidget(QLabel('Холст'));row.addWidget(self.size)
        self.tool_button(row,'file','Новый холст',self.new)
        self.tool_button(row,'folder','Открыть PNG',self.open_png)
        self.tool_button(row,'save','Сохранить PNG',self.save_png)
        export=QPushButton('Экспорт атласа');export.setIcon(self.icon('image'));export.clicked.connect(self.export);row.addWidget(export)
        layout.addWidget(header)
        self.new()
        body=QHBoxLayout();layout.addLayout(body,1)
        rail=QVBoxLayout();body.addLayout(rail)
        self.pen_button=self.tool_button(rail,'brush','Карандаш',lambda:self.set_tool(False),True)
        self.erase_button=self.tool_button(rail,'eraser','Ластик',lambda:self.set_tool(True),True)
        self.pen_button.setChecked(True)
        self.tool_button(rail,'undo','Отменить штрих',self.undo)
        rail.addStretch()
        self.canvas=PixelCanvas(self)
        self.canvas.setFixedSize(512,512)
        scroll=QScrollArea();scroll.setWidget(self.canvas);scroll.setWidgetResizable(False);scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setStyleSheet('QScrollArea { background:#0e1620; border:1px solid #2d4052; border-radius:8px; }')
        body.addWidget(scroll,1)
        side=QVBoxLayout();body.addLayout(side)
        label=QLabel('ЦВЕТ');label.setObjectName('PixelMuted');side.addWidget(label)
        self.swatch=QPushButton('#FFFFFF');self.swatch.clicked.connect(self.pick_color);side.addWidget(self.swatch)
        colors=['#ffffff','#17212d','#748da3','#478cbf','#72c4c3','#81b978','#f2c66d','#e58e66','#cc6b83','#9c89cf']
        for i in range(0,len(colors),2):
            palette_row=QHBoxLayout();side.addLayout(palette_row)
            for color in colors[i:i+2]:
                swatch=QPushButton();swatch.setFixedSize(38,30);swatch.setStyleSheet('background:'+color+';border:1px solid #536578;');swatch.setToolTip(color)
                swatch.clicked.connect(lambda checked=False,c=color:self.set_color(QColor(c)));palette_row.addWidget(swatch)
        side.addSpacing(20);side.addWidget(QLabel('Масштаб'))
        self.zoom=QComboBox();self.zoom.addItems(['256 px','512 px','768 px','1024 px']);self.zoom.setCurrentIndex(1)
        self.zoom.currentIndexChanged.connect(lambda i:self.canvas.setFixedSize([256,512,768,1024][i],[256,512,768,1024][i]));side.addWidget(self.zoom)
        hint=QLabel('ЛКМ — рисовать\nЛастик — прозрачность\nКадры — внизу');hint.setObjectName('PixelMuted');side.addWidget(hint);side.addStretch()
        timeline=QFrame();timeline.setObjectName('PixelTimeline');timeline_layout=QVBoxLayout(timeline)
        controls=QHBoxLayout();timeline_layout.addLayout(controls)
        controls.addWidget(QLabel('Кадры'))
        self.tool_button(controls,'add','Дублировать кадр',self.duplicate)
        self.tool_button(controls,'delete','Удалить кадр',self.delete)
        controls.addStretch()
        self.play_button=self.tool_button(controls,'play','Воспроизвести / остановить',self.play)
        self.fps=QSpinBox();self.fps.setRange(1,60);self.fps.setValue(8);controls.addWidget(QLabel('FPS'));controls.addWidget(self.fps)
        self.fps.valueChanged.connect(lambda value:self.timer.setInterval(round(1000/value)) if hasattr(self,'timer') else None)
        self.frame_list=QListWidget();self.frame_list.setViewMode(QListWidget.ViewMode.IconMode);self.frame_list.setFlow(QListWidget.Flow.LeftToRight)
        self.frame_list.setWrapping(False);self.frame_list.setIconSize(QSize(56,56));self.frame_list.setFixedHeight(108)
        self.frame_list.currentRowChanged.connect(self.choose_frame);timeline_layout.addWidget(self.frame_list);layout.addWidget(timeline)
        self.status=QLabel();self.status.setObjectName('PixelMuted');layout.addWidget(self.status)
        self.timer=QTimer(self);self.timer.timeout.connect(lambda:self.select(1));self.refresh()

    @staticmethod
    def icon(name):
        from editor.icons import get_icon
        return get_icon(name,20)
    def tool_button(self,layout,icon,tooltip,callback,checkable=False):
        button=QToolButton();button.setIcon(self.icon(icon));button.setIconSize(QSize(20,20));button.setToolTip(tooltip);button.setAccessibleName(tooltip)
        button.setCheckable(checkable);button.clicked.connect(callback);layout.addWidget(button);return button
    def set_tool(self,erase):
        self.erase=erase;self.pen_button.setChecked(not erase);self.erase_button.setChecked(erase)
    def set_color(self,color):
        self.color=color;self.set_tool(False);self.swatch.setText(color.name().upper());self.swatch.setStyleSheet('border:2px solid '+color.name()+';')
    def choose_frame(self,index):
        if 0<=index<len(self.frames):self.index=index;self.canvas.update();self.status.setText(f'Кадр {index+1} / {len(self.frames)}')
    def refresh(self):
        if hasattr(self,'frame_list'):
            self.frame_list.blockSignals(True);self.frame_list.clear()
            for i,frame in enumerate(self.frames):
                icon=QIcon(QPixmap.fromImage(frame).scaled(56,56,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))
                self.frame_list.addItem(QListWidgetItem(icon,str(i+1)))
            self.frame_list.setCurrentRow(self.index);self.frame_list.blockSignals(False)
            self.canvas.update();self.status.setText(f'{self.frames[self.index].width()} × {self.frames[self.index].height()} px   ·   Кадр {self.index+1} / {len(self.frames)}')
    def new(self):
        image=QImage(self.size.value(),self.size.value(),QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
        self.frames=[image];self.index=0;self.history=[];self.refresh()
    def pick_color(self):
        color=QColorDialog.getColor(self.color,self)
        if color.isValid():self.set_color(color)
    def eraser(self):self.set_tool(not self.erase)
    def select(self,step):self.index=(self.index+step)%len(self.frames);self.refresh()
    def duplicate(self):self.history.append(([f.copy() for f in self.frames],self.index));self.frames.insert(self.index+1,self.frames[self.index].copy());self.select(1)
    def delete(self):
        if len(self.frames)>1:self.history.append(([f.copy() for f in self.frames],self.index));self.frames.pop(self.index);self.index=min(self.index,len(self.frames)-1);self.refresh()
    def undo(self):
        if self.history:self.frames,self.index=self.history.pop();self.refresh()
    def play(self):
        if self.timer.isActive():self.timer.stop()
        else:self.timer.start(round(1000/self.fps.value()))
    def open_png(self):
        path,_=QFileDialog.getOpenFileName(self,'PNG',self.project,'PNG (*.png)')
        if path:
            image=QImage(path)
            if image.isNull():QMessageBox.warning(self,'PNG','Не удалось открыть изображение');return
            self.frames=[image.convertToFormat(QImage.Format.Format_ARGB32)];self.index=0;self.history=[];self.refresh()
    def save_png(self):self.save(self.frames[self.index])
    def save(self,image):
        path,_=QFileDialog.getSaveFileName(self,'PNG',str(Path(self.project)/'assets'/'pixel.png'),'PNG (*.png)')
        if path and not image.save(path,'PNG'):QMessageBox.warning(self,'PNG','Не удалось сохранить изображение')
        if path and hasattr(self.parent(),'assets'):self.parent().assets.refresh()
    def export(self):
        w,h=self.frames[0].width(),self.frames[0].height();sheet=QImage(w*len(self.frames),h,QImage.Format.Format_ARGB32);sheet.fill(Qt.GlobalColor.transparent)
        painter=QPainter(sheet)
        for i,frame in enumerate(self.frames):painter.drawImage(i*w,0,frame)
        painter.end();self.save(sheet)
