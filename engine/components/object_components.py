"""Core attachable components for GameObject composition."""
import copy
from engine.components.component import Component
from engine.math.vector2 import Vector2


class SpriteRenderer(Component):
    requires_game_object = True
    allow_multiple = False
    type_name = 'SpriteRenderer'
    description = 'Изображение объекта: текстура, цвет, кадр атласа и отражение'
    exported_properties = {
        'texture_path': {'type': 'resource', 'default': ''},
        'material_path': {'type': 'resource', 'default': ''},
        'normal_map': {'type': 'resource', 'default': ''},
        'use_import_settings': {'type': 'bool', 'default': True},
        'color': {'type': 'color', 'default': [255, 255, 255, 255]},
        'flip_h': {'type': 'bool', 'default': False},
        'flip_v': {'type': 'bool', 'default': False},
        'pixel_art': {'type': 'bool', 'default': True},
        'hframes': {'type': 'int', 'default': 1, 'min': 1},
        'vframes': {'type': 'int', 'default': 1, 'min': 1},
        'frame': {'type': 'int', 'default': 0, 'min': 0},
        'sorting_order': {'type': 'int', 'default': 0},
    }

    def __init__(self, **kwargs):
        super().__init__()
        for name, spec in self.exported_properties.items():
            setattr(self, name, copy.deepcopy(spec['default']))
        self._sprite = None
        for key, value in kwargs.items():
            setattr(self, key, value)

    def draw(self, surface, center, camera):
        from engine.nodes.sprite2d import Sprite2D
        if self._sprite is None:
            self._sprite = Sprite2D()
        sprite = self._sprite
        sprite.parent = self.owner
        manager = getattr(self.owner, '_asset_manager', None)
        if manager is not None and manager is not sprite._asset_manager:
            sprite.set_asset_manager(manager)
        if sprite.normal_map != self.normal_map:
            sprite.normal_map=self.normal_map
            sprite.normal_texture=sprite._load_normal(self.normal_map)
        texture_path = self.texture_path
        material = None
        if self.material_path and manager:
            from engine.resources.material import Material
            material = Material.load(manager.resolve(self.material_path))
            texture_path = material.texture or texture_path
        if material and manager:
            import time
            original = manager.get_texture(texture_path)
            sprite.texture = material.render(original, manager.project_dir, time.monotonic())
            sprite._transform_cache.clear()
        elif sprite.texture_path != texture_path or sprite.texture is None or getattr(self, '_had_material', False) or getattr(sprite,'_resource_revision',-1)!=getattr(manager,'revision',0):
            sprite.set_texture_path(texture_path)
            sprite._resource_revision=getattr(manager,"revision",0)
        self._had_material = material is not None
        for prop in ('flip_h', 'flip_v', 'pixel_art', 'hframes', 'vframes', 'frame'):
            setattr(sprite, prop, getattr(self, prop))
        if self.use_import_settings and manager:
            imported=manager.get_import_settings(texture_path)
            settings=imported.get('settings',{})
            if 'filter' in settings:
                sprite.pixel_art=settings['filter']=='nearest'
            metadata=imported.get('metadata',{})
            if settings.get('atlas') and metadata.get('frames'):
                sprite.hframes=max(1,metadata['width']//int(settings['frame_width']))
                sprite.vframes=max(1,metadata['height']//int(settings['frame_height']))
        owner_color = getattr(self.owner, 'modulate', (255, 255, 255, 255))
        sprite.modulate = tuple(int(a * b / 255) for a, b in zip(self.color, owner_color))
        sprite._draw_local(surface, center, camera)


class Rigidbody2D(Component):
    requires_game_object = True
    allow_multiple = False
    type_name = 'Rigidbody2D'
    description = 'Динамическая физика объекта: масса, гравитация, скорость и заморозка'
    exported_properties = {
        'mass': {'type': 'float', 'default': 1.0, 'min': 0.01},
        'gravity_scale': {'type': 'float', 'default': 1.0},
        'drag': {'type': 'float', 'default': 0.0, 'min': 0.0},
        'bounce': {'type': 'float', 'default': 0.0, 'min': 0.0, 'max': 1.0},
        'freeze': {'type': 'bool', 'default': False},
        'collision_layer': {'type': 'int', 'default': 1, 'min': 0},
        'collision_mask': {'type': 'int', 'default': 1, 'min': 0},
    }

    def __init__(self, **kwargs):
        super().__init__()
        for name, spec in self.exported_properties.items():
            setattr(self, name, copy.deepcopy(spec['default']))
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def velocity(self):
        return self.owner.physics_body().velocity if self.owner is not None else Vector2()

    @velocity.setter
    def velocity(self, value):
        if self.owner is not None:
            self.owner.physics_body().velocity = Vector2(value)

    def _ready(self):
        self.sync()

    def sync(self):
        if self.owner is not None:
            return self.owner.physics_body()

    def apply_force(self, force):
        self.sync().apply_force(Vector2(force))

    def apply_impulse(self, impulse):
        self.sync().apply_impulse(Vector2(impulse))


class BoxCollider2D(Component):
    requires_game_object = True
    type_name = 'BoxCollider2D'
    description = 'Прямоугольная форма столкновений на объекте'
    exported_properties = {
        'size': {'type': 'vector2', 'default': [32, 32]},
        'offset': {'type': 'vector2', 'default': [0, 0]},
        'one_way': {'type': 'bool', 'default': False},
    }

    def __init__(self, **kwargs):
        super().__init__()
        self.size = Vector2(32, 32)
        self.offset = Vector2()
        self.one_way = False
        self._shape = None
        for key, value in kwargs.items():
            self.set(key, value)

    def shape(self):
        from engine.nodes.collision_shape import CollisionShape2D
        if self._shape is None:
            self._shape = CollisionShape2D()
        self._shape.parent = self.owner
        self._shape.size = Vector2(self.size)
        self._shape.position = Vector2(self.offset)
        self._shape.one_way = self.one_way
        return self._shape


from engine.nodes.rigidbody2d import RigidBody2D

class ObjectBody(RigidBody2D):
    """Private physics adapter, absent from the scene hierarchy and serialization."""
    def __init__(self, game_object):
        self.game_object = None
        super().__init__()
        self.game_object = game_object
    @property
    def position(self):
        return self.game_object.position if self.game_object else self._position
    @position.setter
    def position(self, value):
        if self.game_object:
            self.game_object.position = Vector2(value)
        else:
            self._position = Vector2(value)
    @property
    def rotation(self):
        return self.game_object.rotation if self.game_object else self._rotation
    @rotation.setter
    def rotation(self, value):
        if self.game_object:
            self.game_object.rotation = value
        else:
            self._rotation = value
    def get_global_transform(self):
        return self.game_object.get_global_transform()
    def set_global_position(self, value):
        self.game_object.set_global_position(value)
    def get_collision_shapes(self):
        return self.game_object.get_collision_shapes()

class CircleCollider2D(BoxCollider2D):
    type_name = 'CircleCollider2D'
    description = 'Круглая форма столкновений: радиус и смещение'
    exported_properties = {
        'radius': {'type': 'float', 'default': 16.0, 'min': 0.01},
        'offset': {'type': 'vector2', 'default': [0, 0]},
    }
    @classmethod
    def get_exported_properties(cls):
        return dict(cls.exported_properties, enabled={'type': 'bool', 'default': True})
    def __init__(self, **kwargs):
        super().__init__()
        self.radius = 16.0
        for key, value in kwargs.items():
            self.set(key, value)
    def shape(self):
        shape = super().shape()
        shape.shape_type = 'circle'
        shape.radius = self.radius
        return shape


def fit_sprite_collider(node, collider, manager=None):
    """Match the unscaled visible sprite frame; transforms are applied by physics."""
    renderer = node.get_component('SpriteRenderer')
    texture = getattr(node, 'texture', None)
    source = renderer if renderer is not None else node
    path = getattr(source, 'texture_path', '')
    if texture is None and manager is not None and path:
        texture = manager.get_texture(path)
    if texture is None:
        return
    columns = max(1, int(getattr(source, 'hframes', 1)))
    rows = max(1, int(getattr(source, 'vframes', 1)))
    collider.size = Vector2(max(1, texture.get_width()//columns), max(1, texture.get_height()//rows))
    collider.offset = Vector2(getattr(node, 'offset', Vector2()))
    if not getattr(node, 'centered', True):
        collider.offset += collider.size * .5
