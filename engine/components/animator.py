"""Parameter-driven animation states with ordered, explicit transitions."""
import copy
import operator
from engine.components.component import Component


class Animator(Component):
    type_name = 'Animator'
    description = 'Пустой граф анимации: собственные состояния, параметры и переходы'
    exported_properties = {'player_path': {'type': 'string', 'default': ''},
                           'entry_state': {'type': 'string', 'default': ''}}
    signals = ['state_changed']

    def __init__(self, **kwargs):
        super().__init__()
        self.player_path = ''
        self.entry_state = ''
        self.states = {}
        self.transitions = []
        self.parameters = {}
        self.editor_positions = {}
        self.state = ''
        self._triggers = set()
        for key, value in kwargs.items():
            setattr(self, key, value)

    def set_parameter(self, name, value):
        self.parameters[name] = value

    def trigger(self, name):
        self.parameters[name] = True
        self._triggers.add(name)

    def _ready(self):
        self.state = ''
        self._enter(self.entry_state)

    def _player(self):
        if self.owner is None:
            return None
        if self.player_path:
            try:
                return self.owner.get_node(self.player_path)
            except (ValueError, KeyError):
                return None
        return next((c for c in self.owner.get_children() if hasattr(c, 'animations') and hasattr(c, 'play')), None)

    def _enter(self, state):
        if state not in self.states or state == self.state:
            return
        self.state = state
        player = self._player()
        clip = self.states[state]
        if player and clip in player.animations:
            player.play(clip)
        self.emit_signal('state_changed', state)

    def _process(self, delta):
        operations = {'==': operator.eq, '!=': operator.ne, '>': operator.gt, '<': operator.lt, '>=': operator.ge, '<=': operator.le}
        for transition in self.transitions:
            if transition.get('from') not in ('*', self.state):
                continue
            if transition.get('parameter') not in self.parameters:
                continue
            operation = operations.get(transition.get('operator', '=='))
            try:
                matches = operation and operation(self.parameters[transition['parameter']], transition.get('value'))
            except (TypeError, ValueError):
                matches = False
            if matches:
                self._enter(transition.get('to'))
                break
        for name in self._triggers:
            self.parameters[name] = False
        self._triggers.clear()

    def _serialize_data(self):
        data={'states':self.states,'transitions':self.transitions,'parameters':self.parameters}
        if self.editor_positions:data['editor_positions']=self.editor_positions
        return copy.deepcopy(data)

    def _deserialize_data(self, data):
        self.states = copy.deepcopy(data.get('states', self.states))
        self.transitions = copy.deepcopy(data.get('transitions', self.transitions))
        self.parameters = copy.deepcopy(data.get('parameters', self.parameters))
        self.editor_positions = copy.deepcopy(data.get('editor_positions', {}))
