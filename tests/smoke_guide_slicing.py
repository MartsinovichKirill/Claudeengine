import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import tempfile
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage,QColor
from editor.sprite_slicer import SpriteSlicer
from engine.systems.cloud_scripts import compile_cloud
app=QApplication([])
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'build') as folder:
    source=Path(folder)/'sprite.png';image=QImage(64,32,QImage.Format.Format_ARGB32);image.fill(QColor('red'));image.save(str(source))
    dialog=SpriteSlicer(source)
    with patch('editor.sprite_slicer.QMessageBox.information'),patch('editor.sprite_slicer.QMessageBox.warning') as warning:
        dialog.export()
        assert not warning.called
    assert (Path(folder)/'sprite'/'sprite_000.png').is_file()
    assert (Path(folder)/'sprite'/'sprite_001.png').is_file()
    assert source.is_file()
    dialog.close()
text=(root/'docs/CLOUD_SCRIPTS.md').read_text(encoding='utf-8')
import re
examples=re.findall(r'```python\n(.*?)```',text,re.S)
for index,code in enumerate(examples):compile_cloud(code,f'guide-example-{index}.cloud')
print(f'PASS: automatic sprite folder and {len(examples)} guide examples compile')
