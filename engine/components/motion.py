"""Additional editable animation components."""
import math
from engine.components.component import Component
from engine.math.vector2 import Vector2

class RotateComponent(Component):
    type_name='Rotate'
    description='Постоянное вращение объекта'
    exported_properties={'speed':{'type':'float','default':45.0}}
    def __init__(self):
        super().__init__();self.speed=45.0
    def _process(self,delta):
        if self.owner is not None:self.owner.rotation+=self.speed*delta

class FloatComponent(Component):
    type_name='Float'
    description='Плавное покачивание монет и декораций'
    exported_properties={'amplitude':{'type':'float','default':8.0},'frequency':{'type':'float','default':1.0}}
    def __init__(self):
        super().__init__();self.amplitude=8.;self.frequency=1.;self._time=0.;self._offset=0.
    def _process(self,delta):
        if self.owner is None:return
        self._time+=delta
        offset=math.sin(self._time*self.frequency*math.tau)*self.amplitude
        self.owner.position.y+=offset-self._offset;self._offset=offset
