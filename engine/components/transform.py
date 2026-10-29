"""Permanent transform component sharing its object's spatial storage."""
from engine.components.component import Component
from engine.math.vector2 import Vector2

class Transform(Component):
    type_name = 'Transform'
    description = 'Положение, поворот и масштаб относительно родителя'
    enabled = property(lambda self: True, lambda self, value: None)
    required = True
    allow_multiple = False
    exported_properties = {
        'position': {'type': 'vector2', 'default': [0, 0]},
        'rotation': {'type': 'float', 'default': 0.0, 'step': 1.0},
        'scale': {'type': 'vector2', 'default': [1, 1]},
    }
    def __init__(self):
        super().__init__()
        self._position = Vector2()
        self._rotation = 0.0
        self._scale = Vector2(1, 1)
    def _read(self, name):
        return getattr(self.owner, name) if self.owner else getattr(self, '_' + name)
    def _write(self, name, value):
        value = float(value) if name == 'rotation' else Vector2(value)
        setattr(self.owner if self.owner else self, name if self.owner else '_' + name, value)
    position = property(lambda s: s._read('position'), lambda s, v: s._write('position', v))
    rotation = property(lambda s: s._read('rotation'), lambda s, v: s._write('rotation', v))
    scale = property(lambda s: s._read('scale'), lambda s, v: s._write('scale', v))
