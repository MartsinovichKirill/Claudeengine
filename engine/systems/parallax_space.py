"""Camera projections shared by editor and runtime (no scene mutation)."""
import math
from engine.math.vector2 import Vector2
from engine.nodes.camera2d import CameraState
from engine.nodes.parallax2d import Parallax2D


def draw_cameras(node, camera):
    ancestors = []
    parent = node.get_parent()
    while parent is not None:
        if isinstance(parent, Parallax2D):
            ancestors.append(parent)
        parent = parent.get_parent()
    if not ancestors:
        return [camera]
    center = Vector2(camera.get_center())
    repeat = Vector2()
    origin = Vector2()
    for layer in reversed(ancestors):
        scale = layer.scroll_scale
        center = Vector2(center.x * scale.x, center.y * scale.y) - layer.scroll_offset - layer._scroll
        if layer.repeat_size.x > 0 or layer.repeat_size.y > 0:
            repeat = Vector2(layer.repeat_size)
            origin = layer.get_global_position()
    zoom = max(.0001, float(camera.zoom))
    size = Vector2(camera.screen_size)
    def copies(axis, period, span, anchor):
        if period <= 0:
            return [0]
        first = math.floor((axis - span / (2 * zoom) - anchor) / period) - 1
        last = math.ceil((axis + span / (2 * zoom) - anchor) / period) + 1
        # Bad period values must not freeze the editor.
        if last - first > 128:
            first = round((axis-anchor)/period) - 64
            last = first + 128
        return range(first, last + 1)
    xs = copies(center.x, repeat.x, size.x, origin.x)
    ys = copies(center.y, repeat.y, size.y, origin.y)
    result = []
    for y in ys:
        for x in xs:
            result.append(CameraState(center - Vector2(x * repeat.x, y * repeat.y), zoom, size))
            if len(result) >= 512:
                return result
    return result
