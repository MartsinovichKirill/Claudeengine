"""Inspect processed images, atlas cells and audio before writing any files."""
import io
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QComboBox,QSpinBox,QCheckBox,QPushButton,QDialogButtonBox,QMessageBox)
from engine.resources.import_pipeline import texture_preview,audio_preview,apply_import,import_settings


class ImportPreview(QDialog):
    def __init__(self,source,project_dir,target_dir=None,parent=None):
        super().__init__(parent)
        self.source=Path(source); self.project_dir=project_dir
        self.target_dir=target_dir or str(Path(project_dir)/'assets')
        self.kind='texture' if self.source.suffix.lower() in ('.png','.jpg','.jpeg','.bmp','.gif','.webp','.tga') else 'audio'
        self.channel=None; self.result_path=''; self.preview_wav=None; self.output=None
        self.setWindowTitle('Предпросмотр импорта — '+self.source.name); self.resize(980,740)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Исходник сохраняется. Настройки и обработанная копия записываются только после «Применить».'))
        form=QFormLayout(); saved=import_settings(source).get('settings',{})
        self.controls={}
        def combo(name,title,values,default):
            field=QComboBox()
            for text,value in values: field.addItem(text,value)
            field.setCurrentIndex(max(0,field.findData(saved.get(name,default))))
            field.currentIndexChanged.connect(self.schedule)
            self.controls[name]=field; form.addRow(title,field)
        def spin(name,title,default,maximum=8192):
            field=QSpinBox(); field.setRange(1,maximum); field.setValue(int(saved.get(name,default)))
            field.setKeyboardTracking(False); field.valueChanged.connect(self.schedule)
            self.controls[name]=field; form.addRow(title,field)
        if self.kind=='texture':
            combo('filter','Фильтрация',[('Nearest — чёткие пиксели','nearest'),('Linear — плавное увеличение','linear')],'nearest')
            spin('max_size','Максимальная сторона',4096)
            self.atlas=QCheckBox('Атлас: нарезать по сетке'); self.atlas.setChecked(bool(saved.get('atlas',False)))
            self.atlas.toggled.connect(self.schedule); form.addRow(self.atlas)
            spin('frame_width','Ширина кадра',32); spin('frame_height','Высота кадра',32)
            self.frame=QSpinBox(); self.frame.setRange(0,0); self.frame.valueChanged.connect(self.schedule)
            form.addRow('Предпросмотр кадра',self.frame)
        else:
            combo('codec','Формат',[('WAV PCM','wav'),('Cloud Audio — zlib без потерь','cloud')],'cloud')
            combo('sample_rate','Частота',[(str(rate)+' Гц',rate) for rate in (8000,11025,16000,22050,32000,44100,48000)],44100)
            combo('channels','Каналы',[('Моно',1),('Стерео',2)],2)
            combo('bits','Битность',[('16 бит',16),('8 бит',8)],16)
        layout.addLayout(form)
        row=QHBoxLayout(); self.original=QLabel(); self.processed=QLabel()
        for label in (self.original,self.processed):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter); label.setMinimumSize(220,240)
            label.setStyleSheet('background:#111d29;border:1px solid #354b60;'); row.addWidget(label,1)
        layout.addLayout(row,1)
        self.frame_preview=QLabel(); self.frame_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.kind=='texture': layout.addWidget(self.frame_preview)
        self.info=QLabel(); self.info.setWordWrap(True); layout.addWidget(self.info)
        if self.kind=='audio':
            audio=QHBoxLayout()
            for text,callback in [('Слушать исходник',self.play_original),('Слушать результат',self.play_processed),('Стоп',self.stop)]:
                button=QPushButton(text); button.clicked.connect(callback); audio.addWidget(button)
            layout.addLayout(audio)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(180); self.timer.timeout.connect(self.preview)
        self.preview()

    def settings(self):
        data={key:(field.currentData() if isinstance(field,QComboBox) else field.value()) for key,field in self.controls.items()}
        if self.kind=='texture': data['atlas']=self.atlas.isChecked()
        return data

    def schedule(self,*args):
        if hasattr(self,'timer'): self.timer.start()

    def preview(self):
        try:
            settings=self.settings()
            if self.kind=='texture':
                data,metadata=texture_preview(self.source,settings); self.output=data
                source=QPixmap(str(self.source)); target=QPixmap(); target.loadFromData(data,'PNG')
                transform=Qt.TransformationMode.SmoothTransformation if settings['filter']=='linear' else Qt.TransformationMode.FastTransformation
                preview=target.scaled(420,300,Qt.AspectRatioMode.KeepAspectRatio,transform)
                if metadata['frames']:
                    self.frame.blockSignals(True); self.frame.setRange(0,len(metadata['frames'])-1); self.frame.blockSignals(False)
                    selected=metadata['frames'][self.frame.value()]
                    painter=QPainter(preview); painter.setPen(QPen(QColor('#77baff'),1))
                    ratio=preview.width()/target.width()
                    for frame in metadata['frames']:
                        painter.drawRect(QRectF(frame['x']*ratio,frame['y']*ratio,frame['width']*ratio,frame['height']*ratio))
                    painter.end()
                    self.frame_preview.setPixmap(target.copy(selected['x'],selected['y'],selected['width'],selected['height']).scaled(128,128,Qt.AspectRatioMode.KeepAspectRatio,transform))
                else: self.frame_preview.clear()
                self.original.setPixmap(source.scaled(420,300,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))
                self.processed.setPixmap(preview)
                self.info.setText(f'Исходник: {source.width()}×{source.height()}, {self.source.stat().st_size:,} байт. Результат: {metadata["width"]}×{metadata["height"]}, {len(data):,} байт. Кадров: {len(metadata["frames"])}. Неполные края атласа пропускаются.')
            else:
                data,self.preview_wav,metadata=audio_preview(self.source,settings); self.output=data
                self.original.setText('Исходник\n'+self.source.name+f'\n{self.source.stat().st_size:,} байт')
                self.processed.setText(f'Результат\n{metadata["sample_rate"]} Гц · {metadata["bits"]} бит · {metadata["channels"]} кан.\n{len(data):,} байт')
                reduction=100*(1-len(data)/max(1,self.source.stat().st_size))
                self.info.setText(f'Длительность: {metadata["duration"]:.2f} с. Изменение размера: {reduction:.1f}% меньше. PCM в памяти: {metadata["decoded_bytes"]:,} байт. Снижение частоты/битности меняет качество; zlib сжимает полученный PCM без потерь. OGG сохраняется как исходник, но не кодируется повторно.')
            self.buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)
        except Exception as exc:
            self.info.setText('Ошибка предпросмотра: '+str(exc)); self.output=None
            self.buttons.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)

    def stop(self):
        if self.channel: self.channel.stop()
        self.channel=None

    def play_original(self):
        from engine.resources.import_pipeline import decode_audio
        # Use the same conversion at source rate for formats SDL can decode.
        import pygame
        self.stop()
        if not pygame.mixer.get_init(): pygame.mixer.init()
        if self.source.suffix.lower()=='.caudio':
            from engine.resources.import_pipeline import AUDIO_MAGIC
            import zlib
            raw=self.source.read_bytes(); self.channel=pygame.mixer.Sound(file=io.BytesIO(zlib.decompress(raw[len(AUDIO_MAGIC):]))).play()
        else: self.channel=pygame.mixer.Sound(str(self.source)).play()

    def play_processed(self):
        import pygame
        self.stop(); self.preview()
        if self.preview_wav:
            if not pygame.mixer.get_init(): pygame.mixer.init()
            self.channel=pygame.mixer.Sound(file=io.BytesIO(self.preview_wav)).play()

    def apply(self):
        try:
            self.result_path=apply_import(self.source,self.project_dir,self.target_dir,self.kind,self.settings())
            self.stop(); self.accept()
        except Exception as exc:
            QMessageBox.warning(self,'Импорт',str(exc))

    def done(self,result):
        self.stop()
        super().done(result)
