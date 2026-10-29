"""AnimationSystem — продвижение анимаций и нарезка спрайтшитов."""

from __future__ import annotations

import logging
from typing import Any, List

logger = logging.getLogger("cloudengine.animation")


class AnimationSystem:
    """Обновляет анимированные спрайты и предоставляет утилиты нарезки."""

    def __init__(self, scene_tree: Any) -> None:
        self.scene_tree = scene_tree
        from engine.systems.frame_hitboxes import FrameHitboxSystem
        self.hitboxes = FrameHitboxSystem(scene_tree)

    def update(self, delta: float) -> None:
        """Продвигает анимации всех AnimatedSprite2D в сцене."""
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return
        from engine.nodes.animated_sprite import AnimatedSprite2D
        import math
        sprites=[n for n in self.scene_tree.current_scene.get_nodes() if isinstance(n,AnimatedSprite2D)]
        for node in sprites:node._ensure_animation()
        # Check every crossed animation frame, even if rendering skips frames.
        fastest=max((max(.1,n.speed)*max(0,n.speed_scale) for n in sprites),default=1)
        steps=max(1,min(600,math.ceil(max(0,delta)*fastest)))
        self.hitboxes.update()
        for _ in range(steps):
            for node in sprites:
                try:
                    node.advance(max(0,delta)/steps)
                except Exception:
                    logger.exception("Ошибка анимации %s", node.name)
            self.hitboxes.update()

    @staticmethod
    def slice_spritesheet(sheet: Any, h_frames: int, v_frames: int) -> List[Any]:
        """Нарезает спрайтшит на список кадров (построчно)."""
        frames: List[Any] = []
        if sheet is None:
            return frames
        w = sheet.get_width() // max(h_frames, 1)
        h = sheet.get_height() // max(v_frames, 1)
        for y in range(v_frames):
            for x in range(h_frames):
                try:
                    frames.append(sheet.subsurface((x * w, y * h, w, h)))
                except Exception:
                    pass
        return frames
