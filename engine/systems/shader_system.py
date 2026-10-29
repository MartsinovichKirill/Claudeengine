"""Cached programmable CPU fragment shaders (.shader Python source)."""
from pathlib import Path

_CACHE = {}

def apply_shader(surface, path, delta=0.0, parameters=None):
    import numpy as np
    import pygame
    file = Path(path)
    signature = (str(file.resolve()), file.stat().st_mtime_ns)
    entry = _CACHE.get(signature[0])
    if entry is None or entry[0] != signature:
        namespace = {'np': np}
        exec(compile(file.read_text(encoding='utf-8-sig'), str(file), 'exec'), namespace)
        fragment = namespace.get('fragment')
        if not callable(fragment):
            raise ValueError('Shader must define fragment(rgb, uv, time)')
        _CACHE[signature[0]] = (signature, fragment)
    else:
        fragment = entry[1]
    width, height = surface.get_size()
    rgb = pygame.surfarray.array3d(surface).astype(np.float32) / 255.0
    x, y = np.meshgrid(np.linspace(0, 1, width), np.linspace(0, 1, height), indexing='ij')
    import inspect
    args = (rgb, np.stack((x, y), axis=-1), delta)
    if len(inspect.signature(fragment).parameters) >= 4:
        args += (parameters or {},)
    result = np.asarray(fragment(*args))
    if result.shape != rgb.shape or not np.isfinite(result).all():
        raise ValueError('Shader must return finite RGB array with the same shape')
    alpha = pygame.surfarray.array_alpha(surface) if surface.get_masks()[3] else None
    pygame.surfarray.blit_array(surface, (np.clip(result, 0, 1) * 255).astype(np.uint8))
    if alpha is not None:
        pixels=pygame.surfarray.pixels_alpha(surface)
        pixels[:]=alpha
        del pixels
