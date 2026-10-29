"""Audio playback attached to an object."""
from engine.components.component import Component
from engine.nodes.audio_stream import AudioStreamPlayer

class AudioSource(Component):
    type_name = 'AudioSource'
    description = 'Звуковой ресурс, громкость и воспроизведение через API скриптов'
    exported_properties = {
        'bus': {'type':'enum','default':'sfx','options':['master','music','sfx','ui']},
        'stream_path': {'type': 'resource', 'default': ''},
        'volume_db': {'type': 'float', 'default': 0.0, 'min': -80.0, 'max': 24.0},
        'autoplay': {'type': 'bool', 'default': False},
    }
    def __init__(self):
        super().__init__()
        self.bus = 'sfx'
        self.stream_path = ''
        self.volume_db = 0.0
        self.autoplay = False
        self._player = AudioStreamPlayer()
    def _sync(self):
        if self._player.stream_path != self.stream_path:
            self._player.stop()
            self._player._sound = None
        self._player.stream_path = self.stream_path
        self._player.bus = self.bus
        self._player._scene_tree = self.get_tree()
        self._player.set_asset_manager(getattr(self.owner, '_asset_manager', None))
        self._player.set_volume_db(self.volume_db)
    def play(self):
        if self.enabled:
            self._sync()
            self._player.play()
    def stop(self):
        self._player.stop()
    def pause(self):
        self._player.pause()
    def resume(self):
        if self.enabled:
            self._player.resume()
    def _ready(self):
        self._sync()
        if self.autoplay:
            self.play()
    def _process(self, delta):
        self._sync()
    def _exit_tree(self):
        self.stop()
