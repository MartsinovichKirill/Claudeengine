import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage,QColor
from pathlib import Path
import tempfile
from editor.sprite_slicer import SpriteSlicer
app=QApplication([])
with tempfile.TemporaryDirectory(dir=Path('build')) as folder:
    image=QImage(64,32,QImage.Format.Format_ARGB32);image.fill(QColor(0,0,0,0))
    for y in range(3,15):
        for x in list(range(2,12))+list(range(40,55)):image.setPixelColor(x,y,QColor('red'))
    path=Path(folder)/'tiles.png';image.save(str(path));dialog=SpriteSlicer(path);dialog.auto_slice()
    assert len(dialog.regions)==2,dialog.regions
    assert dialog.regions[0].width()==10 and dialog.regions[1].width()==15
    print('PASS: automatic slicing finds precise separated sprite bounds')
