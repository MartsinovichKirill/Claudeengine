"""Explicit state graph with physics-driven patrol and chase actions."""
import copy
import math
from engine.components.component import Component
from engine.math.vector2 import Vector2

ACTIONS=('wait','patrol','chase','attack','custom')
CONDITIONS=('target_visible','target_lost','in_attack_range','out_attack_range','timeout','parameter')
OPERATORS=('==','!=','>','<','>=','<=')


def default_graph():
    return {'entry':'patrol','states':{
        'patrol':{'action':'patrol','duration':1.0},
        'chase':{'action':'chase','duration':1.0},
        'attack':{'action':'attack','duration':1.0}},'transitions':[
        {'from':'patrol','to':'chase','condition':'target_visible'},
        {'from':'chase','to':'patrol','condition':'target_lost'},
        {'from':'chase','to':'attack','condition':'in_attack_range'},
        {'from':'attack','to':'patrol','condition':'target_lost'},
        {'from':'attack','to':'chase','condition':'out_attack_range'}], 'parameters':{},'positions':{}}


def validate_graph(data):
    import json
    if not isinstance(data,dict): raise ValueError('Граф должен быть объектом')
    states=data.get('states')
    if not isinstance(states,dict) or not states or data.get('entry') not in states:
        raise ValueError('Создайте состояния и выберите начальное')
    for name,state in states.items():
        if not isinstance(name,str) or not name.strip() or not isinstance(state,dict) or state.get('action') not in ACTIONS:
            raise ValueError('Проверьте имена состояний и действия')
        duration=state.get('duration',1)
        if type(duration) not in (int,float) or not math.isfinite(duration) or duration<0:
            raise ValueError('Длительность состояния должна быть неотрицательным числом')
    if not isinstance(data.get('transitions'),list) or not isinstance(data.get('parameters',{}),dict):
        raise ValueError('Проверьте список переходов и параметры')
    for transition in data['transitions']:
        if not isinstance(transition,dict) or transition.get('from') not in ('*',*states) or transition.get('to') not in states or transition.get('condition') not in CONDITIONS:
            raise ValueError('Переход ссылается на отсутствующее состояние или условие')
        if transition['condition']=='parameter':
            if transition.get('parameter') not in data.get('parameters',{}) or transition.get('operator') not in OPERATORS:
                raise ValueError('Переходу нужен существующий параметр и оператор сравнения')
    if not isinstance(data.get('positions',{}),dict): raise ValueError('Позиции графа должны быть объектом')
    for name,point in data.get('positions',{}).items():
        if name not in states or not isinstance(point,list) or len(point)!=2 or not all(type(x) in (int,float) and math.isfinite(x) for x in point):
            raise ValueError('Неверная позиция узла графа')
    json.dumps(data,allow_nan=False)
    return copy.deepcopy(data)


class EnemyAI(Component):
    type_name='EnemyAI'
    requires_game_object=True
    allow_multiple=False
    description='Граф поведения: патруль, погоня, атака и собственные состояния'
    exported_properties={
        'target_path':{'type':'string','default':'Player'},
        'move_speed':{'type':'float','default':80.,'min':0.,'max':10000.},
        'patrol_distance':{'type':'float','default':120.,'min':0.,'max':100000.},
        'detection_range':{'type':'float','default':300.,'min':0.,'max':100000.},
        'attack_range':{'type':'float','default':48.,'min':0.,'max':100000.},
        'attack_cooldown':{'type':'float','default':.8,'min':.01,'max':600.},
        'attack_method':{'type':'string','default':''},
    }
    signals=['state_changed','attack_requested','state_tick']

    def __init__(self):
        super().__init__()
        for name,spec in self.exported_properties.items(): setattr(self,name,copy.deepcopy(spec['default']))
        self.graph=default_graph(); self.state=''; self.elapsed=0.; self.parameters={}
        self._origin=Vector2(); self._direction=1; self._attack_timer=0.

    def set_parameter(self,name,value): self.parameters[name]=value

    def _ready(self):
        self.graph=validate_graph(self.graph)
        for name in ('move_speed','patrol_distance','detection_range','attack_range','attack_cooldown'):
            value=getattr(self,name)
            if type(value) not in (float,int) or not math.isfinite(value) or value<0:
                raise ValueError('EnemyAI: '+name+' должен быть неотрицательным конечным числом')
        if self.attack_cooldown==0: raise ValueError('EnemyAI: интервал атак должен быть больше нуля')
        self._origin=self.owner.get_global_position(); self._direction=1
        self.parameters=copy.deepcopy(self.graph.get('parameters',{})); self._enter(self.graph['entry'])

    def _enter(self,state):
        self.state=state; self.elapsed=0.; self._attack_timer=0.
        self.emit_signal('state_changed',state)

    def target(self):
        tree=self.get_tree(); scene=getattr(tree,'current_scene',None)
        if not scene or not self.target_path: return None
        target=scene.find_node_by_path(self.target_path)
        if target is None and '/' not in self.target_path: target=scene.find_node(self.target_path)
        if target is self.owner or getattr(target,'_pending_free',False): return None
        return target if callable(getattr(target,'get_global_position',None)) else None

    def _condition(self,transition,target,distance):
        condition=transition['condition']
        if condition=='target_visible': return target is not None and distance<=self.detection_range
        if condition=='target_lost': return target is None or distance>self.detection_range
        if condition=='in_attack_range': return target is not None and distance<=self.attack_range
        if condition=='out_attack_range': return target is not None and distance>self.attack_range
        if condition=='timeout': return self.elapsed>=self.graph['states'][self.state].get('duration',1.)
        import operator
        operations={'==':operator.eq,'!=':operator.ne,'>':operator.gt,'<':operator.lt,'>=':operator.ge,'<=':operator.le}
        try: return bool(operations[transition['operator']](self.parameters.get(transition['parameter']),transition.get('value')))
        except TypeError: return False

    def _move(self,speed):
        body=self.owner.get_component('Rigidbody2D')
        if body is None or not body.enabled:
            if speed: raise ValueError('EnemyAI: для движения добавьте и включите Rigidbody2D у '+self.owner.name)
            return
        current=body.velocity; body.velocity=Vector2(speed,current.y)

    def _physics_process(self,delta):
        if self.owner is None or not self.owner.is_inside_tree(): return
        if delta<=0 or not math.isfinite(delta): return
        if not self.state: self._ready()
        self.elapsed+=delta
        target=self.target()
        position=self.owner.get_global_position()
        distance=position.distance_to(target.get_global_position()) if target else math.inf
        for transition in self.graph['transitions']:
            if transition['from'] in ('*',self.state) and transition['to']!=self.state and self._condition(transition,target,distance):
                self._enter(transition['to']); break
        action=self.graph['states'][self.state]['action']
        speed=0.
        if action=='patrol' and self.patrol_distance>0:
            if position.x>=self._origin.x+self.patrol_distance: self._direction=-1
            elif position.x<=self._origin.x-self.patrol_distance: self._direction=1
            speed=self._direction*self.move_speed
        elif action=='chase' and target:
            difference=target.get_global_position().x-position.x
            speed=math.copysign(self.move_speed,difference) if abs(difference)>1 else 0.
        if action!='custom': self._move(speed)
        if action=='attack' and target and distance<=self.attack_range:
            self._attack_timer-=delta
            if self._attack_timer<=0:
                self._attack_timer=max(.01,self.attack_cooldown)
                self.emit_signal('attack_requested',target)
                if self.attack_method: self._call_attack(target)
        self.emit_signal('state_tick',self.state,delta)

    def _call_attack(self,target):
        if not self.attack_method.isidentifier() or self.attack_method.startswith('_'):
            raise ValueError('EnemyAI: укажите имя публичного метода атаки')
        candidates=[getattr(self.owner,self.attack_method,None)]
        for component in self.owner.components:
            if component is not self and component.enabled:
                candidates.append(getattr(getattr(component,'instance',component),self.attack_method,None))
        methods=[candidate for candidate in candidates if callable(candidate)]
        if len(methods)!=1: raise ValueError('EnemyAI: ожидается один метод '+self.attack_method+', найдено '+str(len(methods)))
        methods[0](target)

    def _exit_tree(self):
        if self.owner is not None: self._move(0)
        self.state=''

    def _serialize_data(self): return {'graph':copy.deepcopy(self.graph)}
    def _deserialize_data(self,data): self.graph=validate_graph(data.get('graph',default_graph()))
