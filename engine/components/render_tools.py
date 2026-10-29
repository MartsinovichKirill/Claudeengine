"""Technical rendering and TileMap components, without gameplay behaviours."""
import copy
from engine.components.component import Component
from engine.components.scene_features import NodeFeature
from engine.nodes.post_process import PostProcess

class TileMapCollider2D(Component):
    type_name = 'TileMapCollider2D'
    description = 'Слои столкновений и отбрасывание теней для коллизии ячеек TileMap'
    allow_multiple = False
    requires_tilemap = True
    exported_properties = {
        'collision_layer': {'type':'int','default':1,'min':0},
        'collision_mask': {'type':'int','default':1,'min':0},
        'light_occluder': {'type':'bool','default':True},
    }
    def __init__(self):
        super().__init__()
        self.collision_layer=1;self.collision_mask=1;self.light_occluder=True

class TileMapTint(Component):
    type_name = 'TileMapTint'
    description = 'Цвет и прозрачность всего слоя TileMap'
    allow_multiple = False
    requires_tilemap = True
    exported_properties = {'color': {'type':'color','default':[255,255,255,255]}}
    def __init__(self):
        super().__init__();self.color=(255,255,255,255)

class PostProcessVolume(NodeFeature):
    type_name = 'PostProcessVolume'
    description = 'Глобальная постобработка как компонент объекта: bloom, цвет, виньетка'
    node_class = PostProcess
    requires_game_object = False
    exported_properties = {k:copy.deepcopy(v) for k,v in PostProcess.exported_properties.items() if k!='enabled'}

    def runtime_node(self):
        node = super().runtime_node()
        node.set_asset_manager(getattr(self.owner, '_asset_manager', None))
        return node
