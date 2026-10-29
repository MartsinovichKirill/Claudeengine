"""Foundational components. Game rules belong in project scripts."""
from engine.components.component import Component

_LAZY = {'COMPONENT_CLASSES', 'COMPONENT_CATEGORIES', 'get_component_class',
         'create_component', 'register_component', 'visible_categories',
         'all_visible_components', 'is_visual_component', 'is_hidden',
         'component_description', 'VISUAL_COMPONENTS'}
__all__ = ['Component', *_LAZY]

def __getattr__(name):
    if name in _LAZY:
        from engine.components import registry
        return getattr(registry, name)
    raise AttributeError(name)
