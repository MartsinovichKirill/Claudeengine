"""Native parallax container; child transforms remain in scene coordinates."""
from engine.nodes.node2d import Node2D
from engine.math.vector2 import Vector2


class Parallax2D(Node2D):
    exported_properties = {
        'scroll_scale': {'type': 'vector2', 'default': [0.5, 0.5]},
        'scroll_offset': {'type': 'vector2', 'default': [0, 0]},
        'autoscroll': {'type': 'vector2', 'default': [0, 0]},
        'repeat_size': {'type': 'vector2', 'default': [0, 0]},
    }

    def __init__(self, name='Parallax2D'):
        super().__init__(name)
        self.scroll_scale = Vector2(.5, .5)
        self.scroll_offset = Vector2()
        self.autoscroll = Vector2()
        self.repeat_size = Vector2()
        self._scroll = Vector2()

    def _process(self, delta):
        self._scroll += self.autoscroll * max(0, delta)

