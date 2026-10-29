"""Sprite sheet authoring: grid and manual pixel regions, PNG export."""
from pathlib import Path
from PyQt6.QtCore import Qt, QRect, QRectF, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QPen
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QFileDialog, QMessageBox, QGraphicsView, QGraphicsScene,
    QComboBox, QCheckBox, QListWidget, QLineEdit, QWidget)


def grid_regions(size, cell, offset=(0, 0), gap=(0, 0)):
    w, h = cell
    if min(w, h) < 1 or min(*offset, *gap) < 0:
        raise ValueError('Некорректные размеры сетки')
    return [QRect(x, y, w, h)
            for y in range(offset[1], size[1]-h+1, h+gap[1])
            for x in range(offset[0], size[0]-w+1, w+gap[0])]


class SliceView(QGraphicsView):
    region_created = pyqtSignal(object)

    def __init__(self, pixmap):
        super().__init__()
        self.canvas = QGraphicsScene(self)
        self.setScene(self.canvas)
        self.canvas.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.bounds = pixmap.rect()
        self.manual = False
        self.start = None
        self.draft = None
        self.overlays = []
        self.setBackgroundBrush(QColor('#101923'))

    def mousePressEvent(self, event):
        if self.manual and event.button() == Qt.MouseButton.LeftButton:
            self.start = self.mapToScene(event.position().toPoint()).toPoint()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start is not None:
            rect = QRect(self.start, self.mapToScene(event.position().toPoint()).toPoint()).normalized().intersected(self.bounds)
            if self.draft:
                self.canvas.removeItem(self.draft)
            self.draft = self.canvas.addRect(QRectF(rect), QPen(QColor('#ffffff'), 1))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start is not None:
            rect = QRect(self.start, self.mapToScene(event.position().toPoint()).toPoint()).normalized().intersected(self.bounds)
            self.start = None
            if self.draft:
                self.canvas.removeItem(self.draft)
                self.draft = None
            if not rect.isEmpty():
                self.region_created.emit(rect)
            return
        super().mouseReleaseEvent(event)

    def show_regions(self, regions, selected):
        for item in self.overlays:
            self.canvas.removeItem(item)
        self.overlays = []
        for i, rect in enumerate(regions):
            pen = QPen(QColor('#ffffff' if i == selected else '#70baff'), 2 if i == selected else 1)
            pen.setCosmetic(True)
            self.overlays.append(self.canvas.addRect(QRectF(rect), pen))


class SpriteSlicer(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.pixmap = QPixmap(str(path))
        if self.pixmap.isNull():
            raise ValueError('Не удалось открыть изображение')
        self.regions = []
        self.setWindowTitle('Sprite Studio — нарезка спрайтов')
        self.resize(1050, 720)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f'{self.path.name} · {self.pixmap.width()} × {self.pixmap.height()} px'))
        row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(['Сетка', 'Вручную — выделите область мышью'])
        row.addWidget(self.mode)
        self.zoom = QComboBox()
        self.zoom.addItems(['25%', '50%', '100%', '200%', '400%'])
        self.zoom.setCurrentIndex(2)
        self.zoom.currentIndexChanged.connect(self.change_zoom)
        row.addWidget(self.zoom)
        layout.addLayout(row)
        self.grid_row = QWidget(self)
        fields = QHBoxLayout(self.grid_row)
        self.width = self.field(fields, 'Ширина', 32, self.pixmap.width())
        self.height = self.field(fields, 'Высота', 32, self.pixmap.height())
        self.offset_x = self.field(fields, 'Отступ X', 0, self.pixmap.width(), 0)
        self.offset_y = self.field(fields, 'Y', 0, self.pixmap.height(), 0)
        self.gap_x = self.field(fields, 'Зазор X', 0, self.pixmap.width(), 0)
        self.gap_y = self.field(fields, 'Y', 0, self.pixmap.height(), 0)
        layout.addWidget(self.grid_row)
        self.skip_empty = QCheckBox('Пропускать полностью прозрачные части')
        self.skip_empty.setChecked(True)
        layout.addWidget(self.skip_empty)
        automatic=QPushButton('Вырезать автоматически')
        automatic.setToolTip('Найти отдельные непрозрачные области. Для сплошного атласа используйте сетку.')
        automatic.clicked.connect(self.auto_slice)
        layout.addWidget(automatic)
        body = QHBoxLayout()
        self.view = SliceView(self.pixmap)
        self.view.region_created.connect(self.add_region)
        body.addWidget(self.view, 1)
        sidebar = QVBoxLayout()
        self.parts = QListWidget()
        self.parts.setMaximumWidth(240)
        self.parts.currentRowChanged.connect(self.select_region)
        sidebar.addWidget(self.parts)
        self.coords = []
        for label in ('X', 'Y', 'Ширина', 'Высота'):
            field = self.field(sidebar, label, 1, max(self.pixmap.width(), self.pixmap.height()), 0)
            field.valueChanged.connect(self.edit_region)
            self.coords.append(field)
        delete = QPushButton('Удалить часть')
        delete.clicked.connect(self.delete_region)
        sidebar.addWidget(delete)
        body.addLayout(sidebar)
        layout.addLayout(body, 1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel('Префикс файлов'))
        self.prefix = QLineEdit(self.path.stem)
        bottom.addWidget(self.prefix)
        save = QPushButton('Сохранить PNG…')
        save.clicked.connect(self.export)
        bottom.addWidget(save)
        layout.addLayout(bottom)
        for field in (self.width, self.height, self.offset_x, self.offset_y, self.gap_x, self.gap_y):
            field.valueChanged.connect(self.preview)
        self.skip_empty.toggled.connect(self.preview)
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.preview()

    @staticmethod
    def field(layout, label, value, maximum, minimum=1):
        layout.addWidget(QLabel(label))
        field = QSpinBox()
        field.setRange(minimum, max(minimum, maximum))
        field.setValue(min(value, maximum))
        layout.addWidget(field)
        return field

    def change_zoom(self):
        self.view.resetTransform()
        scale = (0.25, 0.5, 1, 2, 4)[self.zoom.currentIndex()]
        self.view.scale(scale, scale)

    def change_mode(self):
        self.view.manual = self.mode.currentIndex() == 1
        self.grid_row.setEnabled(not self.view.manual)
        if self.view.manual:
            self.regions = []
            self.refresh()
        else:
            self.preview()

    def preview(self):
        if self.mode.currentIndex() != 0:
            return
        self.regions = grid_regions((self.pixmap.width(), self.pixmap.height()),
            (self.width.value(), self.height.value()),
            (self.offset_x.value(), self.offset_y.value()), (self.gap_x.value(), self.gap_y.value()))
        if self.skip_empty.isChecked():
            image = self.pixmap.toImage()
            self.regions = [r for r in self.regions if any(image.pixelColor(x, y).alpha()
                for y in range(r.top(), r.bottom()+1) for x in range(r.left(), r.right()+1))]
        self.refresh()

    def refresh(self, selected=0):
        self.parts.blockSignals(True)
        self.parts.clear()
        self.parts.addItems([f'{i:03} · {r.width()} × {r.height()} · ({r.x()}, {r.y()})' for i, r in enumerate(self.regions)])
        self.parts.blockSignals(False)
        self.parts.setCurrentRow(min(selected, len(self.regions)-1))
        self.select_region(self.parts.currentRow())
        self.info.setText(f'Частей: {len(self.regions)}. Координаты в пикселях оригинала. Неполные ячейки сетки пропускаются.')

    def select_region(self, index):
        valid = 0 <= index < len(self.regions)
        for field in self.coords:
            field.setEnabled(valid)
        if valid:
            rect = self.regions[index]
            for field, value in zip(self.coords, (rect.x(), rect.y(), rect.width(), rect.height())):
                field.blockSignals(True)
                field.setValue(value)
                field.blockSignals(False)
        self.view.show_regions(self.regions, index)

    def edit_region(self):
        index = self.parts.currentRow()
        if index < 0:
            return
        x, y, w, h = [field.value() for field in self.coords]
        rect = QRect(x, y, max(1, w), max(1, h)).intersected(self.pixmap.rect())
        if rect.isEmpty():
            self.select_region(index)
            return
        self.regions[index] = rect
        self.refresh(index)

    def add_region(self, rect):
        self.regions.append(rect)
        self.refresh(len(self.regions)-1)

    def delete_region(self):
        index = self.parts.currentRow()
        if index >= 0:
            self.regions.pop(index)
            self.refresh(index)

    def auto_slice(self):
        image=self.pixmap.toImage()
        width,height=image.width(),image.height()
        if width*height>16000000:
            QMessageBox.warning(self,'Автонарезка','Изображение слишком большое для автоматического поиска. Используйте сетку.');return
        occupied=bytearray(1 if image.pixelColor(x,y).alpha()>0 else 0 for y in range(height) for x in range(width))
        regions=[]
        for start in range(len(occupied)):
            if not occupied[start]:continue
            stack=[start];occupied[start]=0;left=right=start%width;top=bottom=start//width
            while stack:
                current=stack.pop();x=current%width;y=current//width
                left=min(left,x);right=max(right,x);top=min(top,y);bottom=max(bottom,y)
                for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0<=nx<width and 0<=ny<height:
                        index=ny*width+nx
                        if occupied[index]:occupied[index]=0;stack.append(index)
            regions.append(QRect(left,top,right-left+1,bottom-top+1))
        self.mode.setCurrentIndex(1)
        self.regions=sorted(regions,key=lambda r:(r.y(),r.x()))
        self.refresh()
        self.info.setText(f'Автоматически найдено частей: {len(regions)}. Проверьте области перед сохранением.')

    def save_parts(self, directory):
        prefix = self.prefix.text().strip()
        if not prefix or any(c in prefix for c in '<>:"/\\|?*') or prefix.endswith('.'):
            raise ValueError('Введите допустимый префикс имени файла')
        if not self.regions:
            raise ValueError('Нет частей для сохранения')
        directory = Path(directory)
        paths = [directory / f'{prefix}_{i:03}.png' for i in range(len(self.regions))]
        if any(p.exists() for p in paths):
            raise ValueError('Файлы уже существуют. Выберите другую папку или префикс.')
        created = []
        try:
            for path, rect in zip(paths, self.regions):
                created.append(path)
                if not self.pixmap.copy(rect).save(str(path), 'PNG'):
                    raise OSError(f'Не удалось сохранить {path.name}')
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        return paths

    def export(self):
        directory = self.path.parent / self.path.stem
        try:
            directory.mkdir(exist_ok=True)
            paths = self.save_parts(directory)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, 'Нарезка спрайтов', str(error))
            return
        if hasattr(self.parent(), 'assets'):
            self.parent().assets.refresh()
        QMessageBox.information(self, 'Готово', f'Сохранено частей: {len(paths)}. PNG можно использовать как спрайты и кадры анимации.')
        self.accept()
