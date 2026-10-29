"""Camera and lighting components; private runtime nodes are implementation details."""
import copy
from engine.components.component import Component
from engine.nodes.camera2d import Camera2D as CameraNode
from engine.nodes.light2d import Light2D as LightNode

class NodeFeature(Component):
    allow_multiple = False
    requires_game_object = True
    node_class = None
    def __init__(self):
        super().__init__()
        self._runtime = self.node_class()
        for name, spec in self.exported_properties.items():
            setattr(self, name, copy.deepcopy(spec['default']))
    def runtime_node(self):
        node = self._runtime
        node.parent = self.owner
        node._scene_tree = self.get_tree()
        for name in self.exported_properties:
            node.set(name, getattr(self, name))
        node.enabled = self.enabled
        return node

class Camera2D(NodeFeature):
    type_name = 'Camera2D'
    description = 'Область просмотра сцены и масштаб камеры'
    node_class = CameraNode
    exported_properties = {name: copy.deepcopy(spec) for name, spec in CameraNode.exported_properties.items() if name != "enabled"}

class Light2D(NodeFeature):
    type_name = 'Light2D'
    description = 'Источник 2D-освещения: цвет, энергия, радиус и мягкость'
    node_class = LightNode
    exported_properties = {name: copy.deepcopy(LightNode.exported_properties[name])
        for name in ('cone_angle', 'direction', 'color', 'energy', 'radius', 'softness', 'blend', 'shadows', 'shadow_softness', 'shadow_quality')}
