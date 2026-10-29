"""UISystem — отрисовка UI-слоёв (CanvasLayer) поверх мира и обработка кликов."""

from __future__ import annotations

import logging
from typing import Any, List

from engine.core.node import Node
from engine.math.vector2 import Vector2
from engine.nodes.canvas_layer import CanvasLayer

logger = logging.getLogger("cloudengine.ui_system")


class UISystem:
    """Рисует UI-элементы и обрабатывает ввод для кнопок."""

    def __init__(self, scene_tree: Any) -> None:
        self.scene_tree = scene_tree
        self._button_down: dict = {}   # id(button) -> bool (удерживается)

    def get_canvas_layers(self) -> List[CanvasLayer]:
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return []
        result: List[CanvasLayer] = []
        for node in self.scene_tree.current_scene.get_nodes():
            if isinstance(node, CanvasLayer) and self._visible(node):
                result.append(node)
        result.sort(key=lambda c: c.layer)
        return result

    @staticmethod
    def _visible(node):
        while node is not None:
            if not getattr(node, 'visible', True):
                return False
            node = node.get_parent()
        return True

    def render(self, surface: Any, background=False) -> None:
        """Отрисовывает все CanvasLayer и их UI-детей."""
        if surface is None:
            return
        screen_size = Vector2(surface.get_width(), surface.get_height())
        for layer in self.get_canvas_layers():
            if (layer.layer < 0) != background:
                continue
            from engine.components.ui_layout import arrange_tree
            arrange_tree(layer,screen_size)
            if not layer.visible:
                continue
            import pygame
            canvas = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            for child in layer.get_children():
                self._draw_ui_node(child, canvas, screen_size, Vector2())
            sx, sy = max(.01, abs(layer.scale.x)), max(.01, abs(layer.scale.y))
            if sx != 1 or sy != 1:
                canvas = pygame.transform.scale(canvas, (max(1, round(screen_size.x*sx)), max(1, round(screen_size.y*sy))))
            if layer.scale.x < 0 or layer.scale.y < 0:
                canvas = pygame.transform.flip(canvas, layer.scale.x < 0, layer.scale.y < 0)
            surface.blit(canvas, layer.offset.as_ints())
        if not background:
            self.handle_input(surface)

    def _draw_ui_node(self, node: Node, surface: Any, screen_size: Vector2,
                      offset: Vector2) -> None:
        if not getattr(node, 'visible', True):
            return
        if isinstance(node, CanvasLayer):
            # Nested layers have independent screen space and are rendered once.
            return
        draw_ui = getattr(node, "draw_ui", None)
        if callable(draw_ui):
            try:
                draw_ui(surface, screen_size)
            except Exception:
                logger.exception("Ошибка отрисовки UI %s", node.name)
        elif hasattr(node, '_draw_local'):
            from engine.nodes.camera2d import CameraState
            camera = CameraState(screen_size * .5, 1, screen_size)
            center = node.world_to_screen(node.get_global_position(), camera)
            node._draw_local(surface, center, camera)
            node._execute_draw_commands(surface, camera)
        for child in node.get_children():
            self._draw_ui_node(child, surface, screen_size, offset)

    # ------------------------------------------------------------------
    # Ввод для UI (кнопки)
    # ------------------------------------------------------------------
    def handle_input(self, surface: Any) -> None:
        """Обрабатывает наведение и клики по кнопкам."""
        if self.scene_tree is None or self.scene_tree.input is None:
            return
        input_manager = self.scene_tree.input
        mouse = input_manager.mouse_position
        screen_size = Vector2(surface.get_width(), surface.get_height())

        buttons: List[Any] = []
        coordinates = {}
        for layer in self.get_canvas_layers():
            from engine.components.ui_layout import arrange_tree
            arrange_tree(layer,screen_size)
            if not layer.visible:
                continue
            layer_buttons = []
            for child in layer.get_children():
                self._collect_buttons(child, layer_buttons)
            sx, sy = max(.01, abs(layer.scale.x)), max(.01, abs(layer.scale.y))
            local_mouse = Vector2((mouse.x-layer.offset.x)/sx, (mouse.y-layer.offset.y)/sy)
            if layer.scale.x < 0: local_mouse.x = screen_size.x-local_mouse.x
            if layer.scale.y < 0: local_mouse.y = screen_size.y-local_mouse.y
            for button in layer_buttons:
                coordinates[id(button)] = local_mouse
            buttons.extend(layer_buttons)

        # Обновление hover.
        for btn in buttons:
            rect = btn.get_ui_rect(screen_size)
            btn.hovered = _point_in_rect(coordinates[id(btn)], rect) and not btn.disabled

        # Нажатие.
        if input_manager.is_mouse_button_just_pressed(1):
            for btn in reversed(buttons):
                if btn.hovered:
                    btn._is_down = True
                    self._button_down[id(btn)] = True
                    btn.emit_signal("button_down")
                    break

        if input_manager.is_mouse_button_just_released(1):
            for btn in buttons:
                if self._button_down.get(id(btn)):
                    self._button_down[id(btn)] = False
                    btn._is_down = False
                    btn.emit_signal("button_up")
                    if btn.hovered:
                        btn.press()
                else:
                    btn._is_down = False

    def _collect_buttons(self, node: Node, result: List[Any]) -> None:
        if isinstance(node, CanvasLayer) or not getattr(node, 'visible', True):
            return
        from engine.nodes.button import Button
        if isinstance(node, Button):
            result.append(node)
        for child in node.get_children():
            self._collect_buttons(child, result)


def _point_in_rect(point: Vector2, rect: tuple) -> bool:
    x, y, w, h = rect
    return x <= point.x <= x + w and y <= point.y <= y + h
