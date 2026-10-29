"""AudioSystem — управление шинами громкости и позиционным звуком."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("cloudengine.audio_system")


class AudioSystem:
    """Управляет громкостью шин (master/music/sfx) и обновляет 2D-звук."""

    def __init__(self, scene_tree: Any) -> None:
        self.scene_tree = scene_tree
        self.bus_volumes: Dict[str, float] = {"master": 1.0, "music": 1.0, "sfx": 1.0, "ui": 1.0}

        self.muted = set()
        self._fades = {}
        config=getattr(scene_tree,'settings',{}).get('audio',{})
        for bus,value in config.get('volumes',{k:v for k,v in config.items() if k in self.bus_volumes}).items(): self.set_bus_volume(bus,value)
        self.muted=set(config.get('muted',[]))

    def gain(self,bus):
        if 'master' in self.muted or bus in self.muted:return 0.0
        return self.get_bus_volume('master') * (self.get_bus_volume(bus) if bus!='master' else 1.0)

    def set_bus_mute(self,bus,muted=True):
        if muted:self.muted.add(bus)
        else:self.muted.discard(bus)

    def fade_bus(self,bus,volume,duration=1):
        self._fades[bus]=[self.get_bus_volume(bus),max(0,min(1,float(volume))),max(0,float(duration)),0]

    def init_mixer(self) -> bool:
        """Инициализирует pygame.mixer."""
        try:
            import pygame
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            return True
        except Exception as exc:
            logger.warning("Не удалось инициализировать аудио: %s", exc)
            return False

    def set_bus_volume(self, bus: str, volume: float) -> None:
        """Устанавливает громкость шины (0..1)."""
        self.bus_volumes[bus] = max(0.0, min(1.0, volume))

    def get_bus_volume(self, bus: str) -> float:
        return self.bus_volumes.get(bus, 1.0)

    def update(self, delta: float) -> None:
        """Обновляет позиционный звук и громкость шин."""
        for bus,fade in list(self._fades.items()):
            fade[3]+=max(0,delta)
            t=1 if fade[2]==0 else min(1,fade[3]/fade[2])
            self.set_bus_volume(bus,fade[0]+(fade[1]-fade[0])*t)
            if t>=1:self._fades.pop(bus,None)
        if self.scene_tree is None or self.scene_tree.current_scene is None:
            return
        from engine.nodes.audio_stream import AudioStreamPlayer, AudioStreamPlayer2D
        nodes=list(self.scene_tree.current_scene.get_nodes())
        for obj in list(nodes):
            for component in getattr(obj,'components',[]):
                if getattr(component,'type_name','')=='AudioSource' and component.enabled:
                    component._player._scene_tree=self.scene_tree
                    nodes.append(component._player)
        for node in nodes:
            if isinstance(node, AudioStreamPlayer2D):
                try:
                    node._update_volume()
                except Exception:
                    pass
            elif isinstance(node, AudioStreamPlayer):
                if node._channel is not None:
                    bus_volume = self.gain(node.bus)
                    master = 1.0
                    try:
                        node._channel.set_volume(
                            max(0.0, min(1.0, node._db_to_volume(node.volume_db)
                                * bus_volume * master)))
                    except Exception:
                        pass
