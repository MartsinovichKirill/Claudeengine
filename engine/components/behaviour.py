"""User-authored behaviour with component lifecycle and exported fields."""
from engine.components.component import Component

class Behaviour(Component):
    def _enter_tree(self):
        """Called before ready when the script instance joins the scene."""
        pass
    @property
    def transform(self):
        return self.owner.get_component('Transform') if self.owner else None
    @property
    def game_object(self):
        return self.owner

class ScriptBehaviour(Component):
    type_name = 'ScriptBehaviour'
    description = 'Пользовательский скрипт .cloud или .py, наследующий Behaviour'
    exported_properties = {'script_path': {'type': 'resource', 'default': ''}}
    def __init__(self):
        super().__init__()
        self.script_path = ''
        self.fields = {}
        self.instance = None
    def _ready(self):
        tree = self.get_tree()
        system = getattr(tree, 'script_system', None)
        cls = system.get_class_for(self.script_path) if system else None
        if cls is None:
            if self.script_path:
                raise ValueError('Скрипт не загружен: ' + self.script_path)
            return
        if not issubclass(cls, Behaviour):
            raise TypeError('Скрипт компонента должен наследовать Behaviour')
        self.instance = cls()
        self.instance.owner = self.owner
        for key, value in self.fields.items():
            self.instance.set(key, value)
        self.instance._enter_tree()
        self.instance._ready()
    def _process(self, delta):
        if self.instance:
            self.instance._process(delta)
    def _physics_process(self, delta):
        if self.instance:
            self.instance._physics_process(delta)
    def _input(self, event):
        if self.instance:
            self.instance._input(event)
    def _exit_tree(self):
        if self.instance:
            self.instance._exit_tree()
            self.instance.owner = None
        self.instance = None
    def _serialize_data(self):
        import copy
        return {'fields': copy.deepcopy(self.fields)}
    def _deserialize_data(self, data):
        import copy
        self.fields = copy.deepcopy(data.get('fields', {}))
