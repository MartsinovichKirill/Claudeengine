"""Gizmos — маркеры нод, рамки выделения и инструменты редактора.

В редакторе должны быть видны ВСЕ ноды, даже те, у которых нет собственной
графики (пустой Node2D, коллайдеры, таймеры, звук, камера). Для них
рисуются маркеры с типом и именем — как в Godot/Unity.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.node2d import Node2D
from engine.nodes.sprite2d import Sprite2D

logger = logging.getLogger("cloudengine.gizmos")

SELECT_COLOR = (71, 140, 191, 255)
HANDLE_COLOR = (255, 255, 255, 255)
NAME_COLOR = (200, 210, 220, 230)
HANDLE_SIZE = 6

#: Цвет маркера по категории ноды.
CATEGORY_COLORS = {
    "node2d": (130, 170, 210, 255),
    "body": (225, 170, 90, 255),
    "area": (150, 220, 150, 255),
    "camera": (235, 150, 235, 255),
    "audio": (170, 200, 250, 255),
    "utility": (200, 200, 200, 255),
    "ui": (240, 220, 140, 255),
}

_FONT_CACHE: dict = {}


def _font(size: int = 12) -> Any:
    """Кэшированный шрифт pygame для подписей."""
    cached = _FONT_CACHE.get(size)
    if cached is not None:
        return cached
    try:
        import pygame
        if not pygame.font.get_init():
            pygame.font.init()
        _FONT_CACHE[size] = pygame.font.Font(None, size)
    except Exception:
        return None
    return _FONT_CACHE[size]


def node_category(node: Node) -> str:
    """Категория ноды для выбора цвета/формы маркера."""
    from engine.nodes.camera2d import Camera2D
    from engine.nodes.canvas_layer import CanvasLayer, TextureRect
    from engine.nodes.audio_stream import AudioStreamPlayer, AudioStreamPlayer2D
    from engine.nodes.timer import Timer
    from engine.nodes.label import Label
    from engine.nodes.button import Button
    from engine.nodes.progress_bar import ProgressBar
    from engine.nodes.rigidbody2d import PhysicsBody2D
    from engine.nodes.area2d import Area2D

    if isinstance(node, Camera2D):
        return "camera"
    if isinstance(node, Area2D):
        return "area"
    if isinstance(node, PhysicsBody2D):
        return "body"
    if isinstance(node, (CanvasLayer, TextureRect, Label, Button, ProgressBar)):
        return "ui"
    if isinstance(node, (AudioStreamPlayer, AudioStreamPlayer2D)):
        return "audio"
    if isinstance(node, Timer):
        return "utility"
    return "node2d"


def node_has_visual(node: Node) -> bool:
    """Рисует ли нода себя сама (спрайт, тайлы, частицы, текст и т.п.)."""
    from engine.nodes.tilemap import TileMap
    from engine.nodes.particles2d import Particles2D
    from engine.nodes.parallax_bg import ParallaxBackground
    from engine.nodes.collision_shape import CollisionShape2D
    from engine.nodes.raycast2d import RayCast2D
    from engine.nodes.label import Label
    from engine.nodes.button import Button
    from engine.nodes.progress_bar import ProgressBar
    from engine.nodes.canvas_layer import TextureRect

    if isinstance(node, Sprite2D):
        return getattr(node, "texture", None) is not None
    if isinstance(node, TileMap):
        return bool(node.cells)
    if isinstance(node, (Particles2D, ParallaxBackground, CollisionShape2D,
                         RayCast2D, Label, Button, ProgressBar, TextureRect)):
        return True
    return False


def node_anchor(node: Node, camera: Any = None) -> Vector2:
    """Экранная позиция маркера ноды (для нод без позиции — позиция родителя)."""
    current: Optional[Node] = node
    depth = 0
    while current is not None:
        if isinstance(current, Node2D):
            base = current.world_to_screen(current.get_global_position(), camera)
            return base + Vector2(14 * depth, -18 * depth)
        current = current.parent
        depth += 1
    return Vector2()


class Gizmos:
    """Отрисовка гиизмов редактора на поверхности pygame."""

    # ------------------------------------------------------------------
    # Позиции
    # ------------------------------------------------------------------
    @staticmethod
    def node_anchor(node: Node, camera: Any = None) -> Vector2:
        """Экранная позиция маркера ноды."""
        return node_anchor(node, camera)

    # ------------------------------------------------------------------
    # Подписи и примитивы
    # ------------------------------------------------------------------
    @staticmethod
    def draw_label(surface: Any, text: str, position: Vector2,
                   color: Tuple[int, int, int, int] = NAME_COLOR,
                   centered: bool = True) -> None:
        """Рисует подпись с полупрозрачной подложкой."""
        try:
            import pygame
            font = _font(13)
            if font is None:
                return
            rendered = font.render(text, True, color[:3])
            rect = rendered.get_rect()
            if centered:
                rect.midtop = (int(position.x), int(position.y))
            else:
                rect.topleft = (int(position.x), int(position.y))
            background = pygame.Surface((rect.width + 6, rect.height + 2),
                                        pygame.SRCALPHA)
            background.fill((20, 20, 24, 190))
            surface.blit(background, (rect.x - 3, rect.y - 1))
            surface.blit(rendered, rect)
        except Exception:
            pass

    @staticmethod
    def draw_selection_box(surface: Any, start: Vector2, end: Vector2,
                           fill: bool = True) -> None:
        """Рамка группового выделения."""
        try:
            import pygame
            rect = pygame.Rect(int(min(start.x, end.x)), int(min(start.y, end.y)),
                               int(abs(end.x - start.x)), int(abs(end.y - start.y)))
            if fill:
                layer = pygame.Surface((max(rect.width, 1), max(rect.height, 1)),
                                       pygame.SRCALPHA)
                layer.fill((71, 140, 191, 45))
                surface.blit(layer, (rect.x, rect.y))
            pygame.draw.rect(surface, SELECT_COLOR, rect, 1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Маркеры нод
    # ------------------------------------------------------------------
    @staticmethod
    def draw_node_gizmo(surface: Any, node: Node, camera: Any,
                        selected: bool = False) -> None:
        """Рисует маркер ноды, у которой нет собственной графики."""
        try:
            import pygame
        except Exception:
            return
        center = node_anchor(node, camera)
        category = node_category(node)
        color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["node2d"])
        if selected:
            color = SELECT_COLOR

        if category == "camera":
            Gizmos.draw_camera_frustum(surface, node, camera)
        elif category == "area":
            pygame.draw.circle(surface, color, center.as_ints(), 9, 1)
            pygame.draw.circle(surface, color, center.as_ints(), 2)
        elif category == "body":
            rect = pygame.Rect(0, 0, 18, 18)
            rect.center = center.as_ints()
            pygame.draw.rect(surface, color, rect, 1)
            pygame.draw.line(surface, color, rect.topleft, rect.bottomright, 1)
        elif category == "audio":
            pygame.draw.polygon(surface, color, [
                (int(center.x - 6), int(center.y - 6)),
                (int(center.x - 6), int(center.y + 6)),
                (int(center.x + 6), int(center.y))])
        elif category == "utility":
            pygame.draw.circle(surface, color, center.as_ints(), 8, 1)
            pygame.draw.line(surface, color, center.as_ints(),
                             (int(center.x), int(center.y - 6)), 1)
            pygame.draw.line(surface, color, center.as_ints(),
                             (int(center.x + 5), int(center.y)), 1)
        elif category == "ui":
            rect = pygame.Rect(0, 0, 20, 14)
            rect.center = center.as_ints()
            pygame.draw.rect(surface, color, rect, 1)
        else:
            # Ромб — универсальный маркер Node2D.
            points = [(int(center.x), int(center.y - 7)),
                      (int(center.x + 7), int(center.y)),
                      (int(center.x), int(center.y + 7)),
                      (int(center.x - 7), int(center.y))]
            pygame.draw.polygon(surface, color, points, 1)

        if selected:
            Gizmos.draw_label(surface, node.name,
                              center + Vector2(0, 12), SELECT_COLOR)
        else:
            Gizmos.draw_label(surface, node.name, center + Vector2(0, 12))

    @staticmethod
    def draw_component_badge(surface: Any, position: Vector2, count: int) -> None:
        """Значок «на ноде есть компоненты»."""
        try:
            import pygame
            center = (int(position.x), int(position.y))
            pygame.draw.circle(surface, (255, 196, 92, 255), center, 7)
            pygame.draw.circle(surface, (40, 40, 44, 255), center, 7, 1)
            font = _font(12)
            if font is not None:
                text = font.render(str(count), True, (40, 40, 44))
                surface.blit(text, text.get_rect(center=center))
        except Exception:
            pass

    @staticmethod
    def draw_camera_frustum(surface: Any, camera_node: Any, camera: Any) -> None:
        """Показывает область, которую видит камера."""
        try:
            import pygame
        except Exception:
            return
        zoom = max(getattr(camera_node, "zoom", 1.0), 1e-4)
        if camera is not None and hasattr(camera, "screen_size"):
            size = camera.screen_size
        else:
            size = Vector2(surface.get_width(), surface.get_height())
        half = Vector2(size.x / (2.0 * zoom), size.y / (2.0 * zoom))

        center = camera_node.get_global_position()
        corners = [center + Vector2(-half.x, -half.y),
                   center + Vector2(half.x, -half.y),
                   center + Vector2(half.x, half.y),
                   center + Vector2(-half.x, half.y)]
        if camera is not None:
            corners = [camera.world_to_screen(c) for c in corners]
        points = [c.as_ints() for c in corners]
        color = CATEGORY_COLORS["camera"]
        pygame.draw.polygon(surface, color, points, 1)
        anchor = node_anchor(camera_node, camera)
        pygame.draw.circle(surface, color, anchor.as_ints(), 9, 2)
        pygame.draw.circle(surface, color, anchor.as_ints(), 3)
        Gizmos.draw_label(surface, f"{camera_node.name}  ×{zoom:g}",
                          anchor + Vector2(0, 12), color)

    # ------------------------------------------------------------------
    # Выделение и попадание
    # ------------------------------------------------------------------
    @staticmethod
    def _node_box(node: Node2D, camera: Any) -> Any:
        """pygame.Rect габаритов ноды (для спрайтов) либо None."""
        import pygame
        center = node.world_to_screen(node.get_global_position(), camera)
        zoom = getattr(camera, "zoom", 1.0) if camera else 1.0
        if isinstance(node, Sprite2D) and node.texture is not None:
            texture_rect = node.texture.get_rect()
            width = texture_rect.width * abs(node.scale.x) * zoom
            height = texture_rect.height * abs(node.scale.y) * zoom
            box = pygame.Rect(0, 0, max(int(width), 2), max(int(height), 2))
            if node.centered:
                box.center = center.as_ints()
            else:
                box.topleft = center.as_ints()
            return box
        return None

    @staticmethod
    def draw_node_outline(surface: Any, node: Node2D, camera: Any) -> None:
        """Рамка выделения вокруг ноды."""
        try:
            import pygame
        except Exception:
            return
        box = Gizmos._node_box(node, camera)
        if box is not None:
            pygame.draw.rect(surface, SELECT_COLOR, box, 1)
        else:
            center = node.world_to_screen(node.get_global_position(), camera)
            pygame.draw.circle(surface, SELECT_COLOR, center.as_ints(), 9, 1)

    @staticmethod
    def draw_move_handles(surface: Any, node: Node2D, camera: Any,
                          tool: str = "move") -> None:
        """Маркеры перетаскивания/вращения/масштаба."""
        try:
            import pygame
        except Exception:
            return
        center = node.world_to_screen(node.get_global_position(), camera)
        offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
        radius = 11 if tool == "scale" else 10
        for dx, dy in offsets:
            position = (int(center.x + dx * radius), int(center.y + dy * radius))
            pygame.draw.rect(surface, HANDLE_COLOR,
                             pygame.Rect(position[0] - HANDLE_SIZE // 2,
                                         position[1] - HANDLE_SIZE // 2,
                                         HANDLE_SIZE, HANDLE_SIZE))
        if tool == "rotate":
            pygame.draw.circle(surface, (255, 210, 120, 255), center.as_ints(), 26, 1)
            pygame.draw.circle(surface, (255, 210, 120, 255),
                               (int(center.x), int(center.y - 26)), 4)

    @staticmethod
    def draw_all(surface: Any, scene: Any, selected: List[Node], camera: Any,
                 tool: str = "select", show_gizmos: bool = True) -> None:
        """Рисует выделение и маркеры для всех нод сцены."""
        selected_ids = {id(n) for n in selected}

        if show_gizmos and scene is not None:
            for node in scene.get_nodes():
                if isinstance(node, Node2D) and not node.visible:
                    continue
                if node_has_visual(node) and not isinstance(node, Node2D):
                    # UI-ноды рисуются своим оверлеем.
                    continue
                if node_has_visual(node) and isinstance(node, Node2D):
                    # У спрайта/тайлов достаточно подписи при выделении.
                    if id(node) in selected_ids:
                        Gizmos.draw_node_outline(surface, node, camera)
                        Gizmos.draw_move_handles(surface, node, camera, tool)
                    continue
                Gizmos.draw_node_gizmo(surface, node, camera,
                                       selected=id(node) in selected_ids)

        for node in selected:
            if isinstance(node, Node2D) and node_has_visual(node):
                Gizmos.draw_node_outline(surface, node, camera)
                Gizmos.draw_move_handles(surface, node, camera, tool)

        # Значки компонентов — показывают, что поведение навешано на объект.
        if show_gizmos and scene is not None:
            for node in scene.get_nodes():
                components = getattr(node, "components", None)
                if not components:
                    continue
                if isinstance(node, Node2D) and not node.visible:
                    continue
                anchor = node_anchor(node, camera)
                Gizmos.draw_component_badge(surface, anchor + Vector2(13, -13),
                                            len(components))

    @staticmethod
    def hit_test(node: Node2D, screen_point: Vector2, camera: Any) -> bool:
        """Попадание точки в габариты ноды."""
        try:
            box = Gizmos._node_box(node, camera)
        except Exception:
            box = None
        if box is not None:
            return box.collidepoint(int(screen_point.x), int(screen_point.y))
        center = node.world_to_screen(node.get_global_position(), camera)
        return screen_point.distance_to(center) <= 10
