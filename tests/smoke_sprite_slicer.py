"""Exercise actual pixel crops, transparent filtering and manual mouse selection."""
import os
if not os.environ.get('CLOUD_NATIVE_SMOKE'):
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtCore import Qt, QRect, QPointF
from PyQt6.QtTest import QTest
from editor.sprite_slicer import SpriteSlicer, grid_regions
from editor.theme import apply_theme
from editor.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
app = QApplication([])
apply_theme(app)
with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
    folder = Path(temporary)
    image = QImage(70, 36, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for y in range(2, 34):
        for x in range(2, 34):
            image.setPixelColor(x, y, QColor('#ef653a'))
    image.save(str(folder/'sheet.png'))
    dialog = SpriteSlicer(folder/'sheet.png')
    dialog.offset_x.setValue(2); dialog.offset_y.setValue(2)
    dialog.gap_x.setValue(2)
    assert dialog.regions == [QRect(2, 2, 32, 32)]
    dialog.skip_empty.setChecked(False)
    assert dialog.regions == [QRect(2, 2, 32, 32), QRect(36, 2, 32, 32)]
    output = folder/'out'; output.mkdir()
    paths = dialog.save_parts(output)
    assert QImage(str(paths[0])).pixelColor(0, 0).name() == '#ef653a'
    assert QImage(str(paths[1])).pixelColor(0, 0).alpha() == 0
    assert not list(output.glob('*.json'))
    try:
        dialog.save_parts(output)
        raise AssertionError('Must refuse overwriting existing assets')
    except ValueError:
        pass
    dialog.mode.setCurrentIndex(1)
    dialog.show(); QTest.qWait(100)
    a = dialog.view.mapFromScene(QPointF(4, 4))
    b = dialog.view.mapFromScene(QPointF(15, 18))
    QTest.mousePress(dialog.view.viewport(), Qt.MouseButton.LeftButton, pos=a)
    QTest.mouseMove(dialog.view.viewport(), b)
    QTest.mouseRelease(dialog.view.viewport(), Qt.MouseButton.LeftButton, pos=b)
    assert dialog.regions == [QRect(4, 4, 12, 15)], dialog.regions
    dialog.coords[0].setValue(6)
    assert dialog.regions[0].x() == 6
    dialog.zoom.setCurrentIndex(4)
    assert dialog.view.transform().m11() == 4
    dialog.grab().save(str(ROOT/'build/sprite-studio.png'))
    dialog.delete_region(); assert not dialog.regions
    dialog.close()
    window = MainWindow(); window.save_layout = lambda: None
    window.show(); QTest.qWait(100)
    action = window.toolbar._tool_actions['move']
    action.trigger()
    assert action.isChecked() and window.viewport.tool == 'move'
    assert all(a in window.toolbar.actions() for a in window.toolbar._tool_actions.values())
    window.grab().save(str(ROOT/'build/restored-toolbar.png'))
    window.current_scene = None; window.close()
assert len(grid_regions((65, 33), (32, 32))) == 2
print('PASS: grid spacing, transparent crops, PNG-only export, overwrite protection, mouse slicing, bounds, zoom, scene toolbar')
