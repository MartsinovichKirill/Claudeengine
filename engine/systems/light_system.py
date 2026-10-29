"""LightSystem — освещение сцены: источники света, тени, нормали.

Порядок работы:

1. :class:`CanvasModulate` затемняет весь кадр своим цветом;
2. каждый :class:`Light2D` рисуется аддитивно (``blend="add"``) или
   умножением (``blend="multiply"``);
3. если у спрайта задан ``normal_map``, свет считается попиксельно по
   нормалям (numpy) — поверхность получает объём.

Тени: для источника с ``shadows=True`` строится полигон видимости по
препятствиям сцены, и радиальный градиент обрезается этим полигоном.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from engine.math.vector2 import Vector2

logger = logging.getLogger("cloudengine.light_system")

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:  # pragma: no cover
    np = None
    HAS_NUMPY = False


class LightSystem:
    """Рисует свет и тени поверх отрисованного мира."""

    def __init__(self, scene_tree: Any = None) -> None:
        self.scene_tree = scene_tree
        self.enabled: bool = True
        self.lights_drawn: int = 0
        self._gradient_cache: Dict[Any, Any] = {}
        self._modulate_cache: Dict[Any, Any] = {}
        self._lighting_surface = None

    # ------------------------------------------------------------------
    # Вспомогательное
    # ------------------------------------------------------------------
    def _nodes(self) -> List[Any]:
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return []
        nodes = self.scene_tree.current_scene.get_nodes()
        result = list(nodes)
        for node in nodes:
            for component in node.components:
                if component.enabled and callable(getattr(component, 'runtime_node', None)):
                    result.append(component.runtime_node())
        return result

    def invalidate(self) -> None:
        """Сбрасывает кэши (смена сцены, изменение параметров)."""
        self._gradient_cache.clear()
        self._modulate_cache.clear()

    # ------------------------------------------------------------------
    # Основной проход
    # ------------------------------------------------------------------
    def render(self, surface: Any, camera: Any = None) -> None:
        """Наносит освещение на кадр."""
        if not self.enabled or surface is None or not HAS_NUMPY:
            return
        try:
            import pygame
            from engine.nodes.light2d import CanvasModulate
            settings=getattr(self.scene_tree,"settings",{})
            ambient=tuple(settings.get("render",{}).get("ambient_color",[255,255,255])[:3])
            for node in self._nodes():
                if isinstance(node, CanvasModulate) and node.enabled:
                    ambient = node.get_color_rgb()
                    break
            # Illuminate scene albedo instead of painting bright fog onto it.
            if self._lighting_surface is None or self._lighting_surface.get_size()!=surface.get_size():
                self._lighting_surface=pygame.Surface(surface.get_size())
            lighting = self._lighting_surface
            lighting.fill(ambient)
            lights=[]
            zoom=max(.01,float(getattr(camera,'zoom',1)))
            for light in self._collect_lights():
                point=self._world_to_screen(light.world_center(),camera); radius=light.radius*zoom
                if point.x+radius>=0 and point.y+radius>=0 and point.x-radius<surface.get_width() and point.y-radius<surface.get_height():lights.append(light)
            self.lights_drawn = len(lights)
            segments = self._segments(lights)
            for light in lights:
                self._draw_light(lighting, light, camera, segments)
            self._normal_pass(lighting, lights, camera)
            surface.blit(lighting, (0,0), special_flags=pygame.BLEND_RGB_MULT)
        except Exception:
            logger.exception("Ошибка освещения")

    def _collect_lights(self) -> List[Any]:
        from engine.nodes.light2d import Light2D
        return [node for node in self._nodes()
                if isinstance(node, Light2D) and node.enabled and node.radius > 0]

    def _segments(self, lights: List[Any]) -> List[Any]:
        """Препятствия нужны только если хоть один свет бросает тени."""
        if not any(getattr(light, "shadows", False) for light in lights):
            return []
        from engine.nodes.light2d import collect_segments
        scene = self.scene_tree.current_scene if self.scene_tree else None
        return collect_segments(scene)

    # ------------------------------------------------------------------
    # Затемнение сцены
    # ------------------------------------------------------------------
    def _apply_modulate(self, surface: Any) -> None:
        from engine.nodes.light2d import CanvasModulate
        modulate = None
        for node in self._nodes():
            if isinstance(node, CanvasModulate) and node.enabled:
                modulate = node
                break
        if modulate is None:
            return
        import pygame
        rgb = modulate.get_color_rgb()
        if rgb == (255, 255, 255):
            return
        width, height = surface.get_width(), surface.get_height()
        key = (rgb, width, height)
        mask = self._modulate_cache.get(key)
        if mask is None:
            small = pygame.Surface((1, 1))
            small.fill(rgb)
            mask = pygame.transform.scale(small, (width, height))
            if len(self._modulate_cache) > 6:
                self._modulate_cache.clear()
            self._modulate_cache[key] = mask
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    # ------------------------------------------------------------------
    # Источники света
    # ------------------------------------------------------------------
    def _gradient(self, light: Any) -> Optional[Any]:
        """Радиальный градиент света (кэшируется по параметрам)."""
        import pygame
        radius = max(4, min(512,int(light.radius)))
        energy = max(0.0, min(8.0, float(light.energy)))
        softness = max(0.05, min(1.0, float(getattr(light, "softness", 0.55))))
        color = light.get_color_rgb()
        cone=max(1,min(360,float(getattr(light,'cone_angle',360))))
        direction=float(getattr(light,'direction',0))
        key = (radius, round(energy, 2), round(softness, 2), color,cone,direction)
        cached = self._gradient_cache.get(key)
        if cached is not None:
            return cached

        size = radius * 2
        axis = np.arange(size, dtype=np.float32) - radius + 0.5
        dist = np.sqrt(axis[:, None] ** 2 + axis[None, :] ** 2) / radius
        falloff = np.clip(1.0 - dist, 0.0, 1.0) ** (1.0 / softness)
        intensity = np.clip(falloff * energy, 0.0, 1.0)
        if cone<360:
            angle=np.degrees(np.arctan2(axis[None,:],axis[:,None]))
            diff=np.abs((angle-direction+180)%360-180)
            edge=max(1,cone*.08)
            intensity*=np.clip((cone*.5-diff)/edge,0,1)

        array = np.zeros((size, size, 3), dtype=np.uint8)
        for index in range(3):
            array[:, :, index] = (intensity * color[index]).astype(np.uint8)
        surface = pygame.surfarray.make_surface(array)
        # convert_alpha требует заданного видеорежима — в offscreen-режиме
        # редактора его нет, поэтому оптимизация необязательна.
        try:
            surface = surface.convert_alpha()
        except Exception:
            pass
        if len(self._gradient_cache) > 24:
            self._gradient_cache.clear()
        self._gradient_cache[key] = surface
        return surface

    def _draw_light(self, surface: Any, light: Any, camera: Any,
                    segments: List[Any]) -> None:
        import pygame
        zoom = max(0.01,float(getattr(camera,'zoom',1.0))) if camera else 1.0
        if float(light.radius)*zoom>1024:
            self._draw_large_light(surface,light,camera,segments)
            return
        gradient = self._gradient(light)
        if gradient is None:
            return
        zoom = max(0.01, float(getattr(camera, 'zoom', 1.0))) if camera else 1.0
        if zoom != 1.0 or float(light.radius)>512:
            size = max(2, round(float(light.radius)*2*zoom))
            gradient = pygame.transform.smoothscale(gradient, (size,size))
        radius = gradient.get_width() / 2.0
        center = self._world_to_screen(light.world_center(), camera)
        left = int(round(center.x - radius))
        top = int(round(center.y - radius))

        source = gradient
        if getattr(light, "shadows", False) and segments:
            polygon = light.visibility_polygon(segments)
            if polygon:
                masked = self._mask_gradient(gradient, polygon, light, camera)
                if masked is not None:
                    source = masked

        flags = pygame.BLEND_RGB_ADD if getattr(light, "blend", "add") == "add" \
            else pygame.BLEND_RGB_MULT
        if getattr(light, "blend", "add") == "add":
            surface.blit(source, (left, top), special_flags=flags)
        else:
            # Умножение затрагивает только область света.
            area = pygame.Rect(left, top, source.get_width(), source.get_height())
            area = area.clip(surface.get_rect())
            if area.width > 0 and area.height > 0:
                part = surface.subsurface(area).copy()
                part.blit(source, (area.x - left, area.y - top), special_flags=flags)
                surface.blit(part, (area.x, area.y))

    def _draw_large_light(self,surface,light,camera,segments):
        """Sample only visible pixels; huge radius/zoom never allocates a huge texture."""
        import pygame
        zoom=max(.01,float(getattr(camera,'zoom',1))) if camera else 1
        radius=max(1,float(light.radius)*zoom);center=self._world_to_screen(light.world_center(),camera)
        area=pygame.Rect(int(center.x-radius),int(center.y-radius),int(radius*2)+2,int(radius*2)+2).clip(surface.get_rect())
        if not area.width or not area.height:return
        x=np.arange(area.width,dtype=np.float32)+area.x-center.x
        y=np.arange(area.height,dtype=np.float32)+area.y-center.y
        dist=np.sqrt(x[:,None]**2+y[None,:]**2)/radius
        intensity=np.clip((np.clip(1-dist,0,1)**(1/max(.05,float(light.softness))))*max(0,min(8,float(light.energy))),0,1)
        cone=max(1,min(360,float(getattr(light,'cone_angle',360))))
        if cone<360:
            angles=np.degrees(np.arctan2(y[None,:],x[:,None]));diff=np.abs((angles-float(getattr(light,'direction',0))+180)%360-180)
            intensity*=np.clip((cone*.5-diff)/max(1,cone*.08),0,1)
        color=light.get_color_rgb();pixels=np.stack([(intensity*c).astype(np.uint8) for c in color],axis=2)
        source=pygame.surfarray.make_surface(pixels)
        if light.shadows and segments:
            polygon=light.visibility_polygon(segments)
            if polygon:
                mask=pygame.Surface(area.size);mask.fill((0,0,0))
                points=[self._world_to_screen(point,camera) for point in polygon]
                pygame.draw.polygon(mask,(255,255,255),[(p.x-area.x,p.y-area.y) for p in points])
                softness=max(0,float(getattr(light,'shadow_softness',0)))
                if softness:
                    size=(max(1,int(area.width/max(2,softness*2))),max(1,int(area.height/max(2,softness*2))))
                    mask=pygame.transform.smoothscale(pygame.transform.smoothscale(mask,size),area.size)
                source.blit(mask,(0,0),special_flags=pygame.BLEND_RGB_MULT)
        surface.blit(source,area.topleft,special_flags=pygame.BLEND_RGB_ADD if light.blend=='add' else pygame.BLEND_RGB_MULT)

    def _mask_gradient(self, gradient: Any, polygon: List[Any], light: Any,
                       camera: Any) -> Optional[Any]:
        """Обрезает градиент полигоном видимости."""
        import pygame
        try:
            size = gradient.get_width()
            radius = size / 2.0
            center = self._world_to_screen(light.world_center(), camera)
            mask = pygame.Surface((size, size), pygame.SRCALPHA)
            mask.fill((0, 0, 0, 0))
            points = []
            for point in polygon:
                screen = self._world_to_screen(point, camera)
                points.append((screen.x - (center.x - radius),
                               screen.y - (center.y - radius)))
            if len(points) < 3:
                return None
            pygame.draw.polygon(mask, (255, 255, 255, 255), points)
            softness=max(0,float(getattr(light,'shadow_softness',0)))
            if softness:
                divisor={'low':8,'medium':4,'high':2}.get(getattr(light,'shadow_quality','medium'),4)
                small=max(1,round(size/max(divisor,softness*2)))
                mask=pygame.transform.smoothscale(pygame.transform.smoothscale(mask,(small,small)),(size,size))
            result = gradient.copy()
            result.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            return result
        except Exception:
            logger.exception("Не удалось построить тень")
            return None

    # ------------------------------------------------------------------
    # Нормали
    # ------------------------------------------------------------------
    def _normal_pass(self, surface: Any, lights: List[Any], camera: Any) -> None:
        """Попиксельное освещение спрайтов с картой нормалей."""
        nodes=self._nodes()
        for node in list(nodes):
            for component in getattr(node,'components',[]):
                sprite=getattr(component,'_sprite',None)
                if component.enabled and sprite is not None:nodes.append(sprite)
        sprites = [node for node in nodes
                   if getattr(node, "normal_texture", None) is not None
                   and getattr(node, "visible", True)]
        if not sprites:
            return
        for sprite in sprites:
            for light in lights:
                if getattr(light, "blend", "add") != "add":
                    continue
                try:
                    self._shade_sprite(surface, sprite, light, camera)
                except Exception:
                    logger.exception("Ошибка освещения по нормалям")

    def _shade_sprite(self, surface: Any, sprite: Any, light: Any,
                      camera: Any) -> None:
        import pygame
        normal_texture = sprite.normal_texture
        width, height = normal_texture.get_size()
        if width < 2 or height < 2:
            return

        texture = getattr(sprite, "texture", None)
        if texture is None:
            return
        tex_w, tex_h = texture.get_size()

        screen_center = self._world_to_screen(sprite.get_global_position(), camera)
        zoom = float(getattr(camera, "zoom", 1.0)) if camera is not None else 1.0
        scale = Vector2(getattr(sprite, "scale", (1.0, 1.0)))
        draw_w = int(abs(tex_w * scale.x * zoom))
        draw_h = int(abs(tex_h * scale.y * zoom))
        if draw_w < 2 or draw_h < 2:
            return
        rect = pygame.Rect(int(screen_center.x - draw_w / 2),
                           int(screen_center.y - draw_h / 2), draw_w, draw_h)

        light_center = self._world_to_screen(light.world_center(), camera)
        light_radius = float(light.radius) * zoom
        # Быстрая проверка пересечения.
        closest_x = max(rect.left, min(light_center.x, rect.right))
        closest_y = max(rect.top, min(light_center.y, rect.bottom))
        if (closest_x - light_center.x) ** 2 + (closest_y - light_center.y) ** 2 > \
                light_radius ** 2:
            return

        step = 2 if draw_w * draw_h > 40000 else 1
        sample_w = max(1, draw_w // step)
        sample_h = max(1, draw_h // step)

        normals = pygame.surfarray.array3d(normal_texture).astype(np.float32)
        source_w, source_h = normals.shape[0], normals.shape[1]
        index_x = (np.arange(sample_w) * step + step / 2.0) / max(draw_w, 1) * source_w
        index_y = (np.arange(sample_h) * step + step / 2.0) / max(draw_h, 1) * source_h
        index_x = np.clip(index_x.astype(np.int32), 0, max(source_w - 1, 0))
        index_y = np.clip(index_y.astype(np.int32), 0, max(source_h - 1, 0))
        sampled = normals[np.ix_(index_x, index_y)]     # (sample_w, sample_h, 3)

        nx = sampled[:, :, 0] / 127.5 - 1.0
        ny = sampled[:, :, 1] / 127.5 - 1.0
        nz_sq = np.clip(1.0 - nx * nx - ny * ny, 0.0, 1.0)
        nz = np.sqrt(nz_sq)

        # Пиксели в экранных координатах.
        px = rect.left + (np.arange(sample_w) * step + step / 2.0)
        py = rect.top + (np.arange(sample_h) * step + step / 2.0)
        dx = light_center.x - px
        dy = light_center.y - py
        dist = np.sqrt(dx[:, None] ** 2 + dy[None, :] ** 2)
        length = np.maximum(dist, 1e-5)
        lx = dx[:, None] / length
        ly = dy[None, :] / length

        diffuse = np.clip(nx * lx + ny * ly + nz * 0.35, 0.0, 1.0)
        softness = max(0.05, min(1.0, float(getattr(light, "softness", 0.55))))
        falloff = np.clip(1.0 - dist / max(light_radius, 1e-5), 0.0, 1.0) ** (1.0 / softness)
        energy = max(0.0, float(light.energy))
        color = light.get_color_rgb()

        intensity = np.clip(diffuse * falloff * energy, 0.0, 1.0)
        array = np.zeros((sample_w, sample_h, 3), dtype=np.uint8)
        for index in range(3):
            array[:, :, index] = (intensity * color[index]).astype(np.uint8)

        shading = pygame.surfarray.make_surface(array)
        if (sample_w, sample_h) != (draw_w, draw_h):
            shading = pygame.transform.scale(shading, (draw_w, draw_h))
        surface.blit(shading, rect.topleft, special_flags=pygame.BLEND_RGB_ADD)

    # ------------------------------------------------------------------
    def _world_to_screen(self, world: Any, camera: Any) -> Any:
        if camera is not None and hasattr(camera, "world_to_screen"):
            return camera.world_to_screen(world)
        return world


__all__ = ["LightSystem"]
