"""Object container: physics is supplied by attached components."""
from engine.nodes.node2d import Node2D

class GameObject(Node2D):
    def __init__(self, name='GameObject'):
        super().__init__(name)
        self._asset_manager = None
        self._component_body = None
        from engine.components.transform import Transform
        self.add_component(Transform())

    @property
    def transform(self):
        return self.get_component('Transform')

    def set_asset_manager(self, manager):
        self._asset_manager = manager

    def get_effective_z(self):
        renderer = self.get_component('SpriteRenderer')
        return super().get_effective_z() + (renderer.sorting_order if renderer and renderer.enabled else 0)

    def get_collision_shapes(self):
        return [c.shape() for c in self.components if c.enabled and callable(getattr(c, 'shape', None))]

    def physics_body(self):
        from engine.components.object_components import ObjectBody
        rigid = self.get_component('Rigidbody2D')
        shapes = self.get_collision_shapes()
        if not shapes and not (rigid and rigid.enabled):
            return None
        if self._component_body is None:
            self._component_body = ObjectBody(self)
        body = self._component_body
        body.freeze = not (rigid and rigid.enabled) or rigid.freeze
        if rigid and rigid.enabled:
            for name in rigid.exported_properties:
                setattr(body, name, getattr(rigid, name))
        for name in (() if rigid and rigid.enabled else ('collision_layer', 'collision_mask')):
            setattr(body, name, getattr(shapes[0], name, 1) if shapes else 1)
        return body

    def _draw_local(self, surface, center, camera):
        for component in self.components:
            if component.enabled and callable(getattr(component, 'draw', None)):
                component.draw(surface, center, camera)
