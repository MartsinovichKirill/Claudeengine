"""Read-only compatibility lookup for previously saved scene files.

These types are deliberately absent from the component factory and public API.
"""
def legacy_component_class(type_name):
    from engine.components.builtin import ALL_COMPONENTS
    from engine.components.gameplay import GAMEPLAY_COMPONENTS
    from engine.components.motion import RotateComponent, FloatComponent
    from engine.visual.component import VisualScriptComponent
    classes = (*ALL_COMPONENTS, *GAMEPLAY_COMPONENTS, RotateComponent, FloatComponent, VisualScriptComponent)
    return next((cls for cls in classes if cls.get_type_name() == type_name), None)
