"""Material resources used by both the editor preview and sprite rendering."""
import json
from pathlib import Path
from engine.resources.prefab import atomic_json, resource_path


class Material:
    def __init__(self, texture='', shader='', color=None, parameters=None):
        self.texture = texture
        self.shader = shader
        self.color = color or [255, 255, 255, 255]
        self.parameters = parameters or {}

    def to_dict(self):
        return {'version': 1, 'texture': self.texture, 'shader': self.shader,
                'color': self.color, 'parameters': self.parameters}

    @classmethod
    def from_dict(cls, data):
        color = data.get('color', [255] * 4)
        if len(color) != 4 or any(not isinstance(v, (int, float)) or not 0 <= v <= 255 for v in color):
            raise ValueError('Цвет должен содержать четыре значения 0…255')
        if not isinstance(data.get('parameters', {}), dict):
            raise ValueError('Параметры должны быть JSON-объектом')
        return cls(str(data.get('texture', '')), str(data.get('shader', '')), color, data.get('parameters', {}))

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))

    def save(self, path):
        Material.from_dict(self.to_dict())
        atomic_json(path, self.to_dict())

    def render(self, source, project_dir, time=0.0):
        import pygame
        result = source.copy()
        result.fill(tuple(int(v) for v in self.color), special_flags=pygame.BLEND_RGBA_MULT)
        if self.shader:
            from engine.systems.shader_system import apply_shader
            apply_shader(result, resource_path(project_dir, self.shader), time, self.parameters)
        return result
