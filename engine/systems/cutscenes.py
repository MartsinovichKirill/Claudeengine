"""Deterministic, seekable property tracks shared by editor and runtime."""
import copy
import json
import math
from pathlib import Path
from engine.math.vector2 import Vector2

PROPERTIES={'position','rotation','scale','zoom','offset','energy','radius','volume_db','color'}


def validate_clip(data):
    tracks=data.get('tracks',[])
    if not isinstance(tracks,list): raise ValueError('tracks должен быть списком')
    for track in tracks:
        for name in ('start','duration'):
            value=float(track.get(name,0))
            if not math.isfinite(value) or value<0: raise ValueError('Время должно быть конечным и неотрицательным')
        kind=track.get('kind','property')
        if kind not in ('property','audio','event'):raise ValueError('Неизвестный тип дорожки')
        if kind!='property':
            method=track.get('method','play' if kind=='audio' else '')
            if not isinstance(method,str) or not method.isidentifier() or method.startswith('_'):
                raise ValueError('Событие должно вызывать публичный метод')
            if kind=='audio' and method!='play':raise ValueError('Звуковая дорожка использует play')
            if not isinstance(track.get('args',[]),list):raise ValueError('Аргументы события должны быть JSON-массивом')
            continue
        if track.get('property') not in PROPERTIES: raise ValueError('Неподдерживаемое свойство дорожки')
        for name in ('from','to'):
            values=track[name] if isinstance(track[name],list) else [track[name]]
            if not values or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):
                raise ValueError('Значения дорожки должны быть числами')
        if isinstance(track['from'],list)!=isinstance(track['to'],list) or (isinstance(track['from'],list) and len(track['from'])!=len(track['to'])):
            raise ValueError('Начальное и конечное значения должны иметь одинаковую размерность')
        if track.get('ease','linear') not in ('linear','smooth'): raise ValueError('Неизвестная интерполяция')
    return copy.deepcopy(data)


class CutscenePlayer:
    def __init__(self,tree=None):
        self.tree=tree;self.playing=False;self.time=0;self.duration=0;self.bindings=[];self.scene=None
        self.events=[];self.fired=set();self.started_audio=[]

    def bind(self,scene,data):
        data=validate_clip(data); self.stop(True); bindings=[];events=[]
        for track in data.get('tracks',[]):
            node=scene.root if track.get('target','.') in ('','.','/') else scene.find_node_by_path(track['target'])
            if node is None: raise ValueError('Не найден объект: '+track.get('target',''))
            obj=node.get_component(track['component']) if track.get('component') else node
            if track.get('kind','property')!='property':
                method=track.get('method','play')
                if obj is None or not callable(getattr(obj,method,None)):
                    raise ValueError('Не найден метод события: '+method)
                if track['kind']=='audio':
                    from engine.nodes.audio_stream import AudioStreamPlayer,AudioStreamPlayer2D
                    from engine.components.audio_source import AudioSource
                    if not isinstance(obj,(AudioStreamPlayer,AudioStreamPlayer2D,AudioSource)):
                        raise ValueError('Звуковая дорожка требует AudioStreamPlayer или AudioSource')
                events.append((obj,track));continue
            prop=track['property']
            if obj is None or not hasattr(obj,prop): raise ValueError('Не найден компонент или свойство: '+prop)
            bindings.append((obj,prop,copy.deepcopy(getattr(obj,prop)),track))
        self.stop(True);self.scene=scene;self.bindings=bindings;self.time=0
        self.events=events;self.fired.clear();self.started_audio=[]
        self.duration=max((float(t.get('start',0))+float(t.get('duration',0)) for t in data.get('tracks',[])),default=0)

    def play(self,path):
        if not self.tree or not self.tree.current_scene: raise ValueError('Нет активной сцены')
        root=Path(getattr(self.tree.script_system,'project_dir','')).resolve();file=(root/path).resolve()
        if not file.is_relative_to(root): raise ValueError('Кат-сцена должна находиться внутри проекта')
        self.bind(self.tree.current_scene,json.loads(file.read_text(encoding='utf-8-sig')))
        self.playing=True;self.seek(0)

    def seek(self,time):
        self.time=max(0,min(self.duration,float(time)))
        for obj,prop,original,track in self.bindings: setattr(obj,prop,copy.deepcopy(original))
        for obj,prop,original,track in self.bindings:
            start=float(track.get('start',0));duration=float(track.get('duration',0))
            if self.time<start: continue
            t=1 if duration==0 else min(1,(self.time-start)/duration)
            if track.get('ease')=='smooth': t=t*t*(3-2*t)
            a,b=track['from'],track['to']
            value=[x+(y-x)*t for x,y in zip(a,b)] if isinstance(a,list) else a+(b-a)*t
            if isinstance(original,Vector2): value=Vector2(value)
            elif isinstance(original,tuple): value=tuple(round(v) for v in value)
            setattr(obj,prop,value)

    def update(self,delta):
        if not self.playing:return
        if self.tree and self.tree.current_scene is not self.scene: self.stop(True);return
        self.seek(self.time+max(0,delta))
        # Seek/preview never execute scripts or audio; only runtime playback does.
        if self.tree:
            for index,(obj,track) in enumerate(self.events):
                if index not in self.fired and self.time>=float(track.get('start',0)):
                    self.fired.add(index)
                    getattr(obj,track.get('method','play'))(*copy.deepcopy(track.get('args',[])))
                    if track['kind']=='audio':self.started_audio.append((obj,float(track.get('start',0))+float(track.get('duration',0))))
            for obj,end in list(self.started_audio):
                if self.time>=end:
                    obj.stop();self.started_audio.remove((obj,end))
        if self.time>=self.duration:self.playing=False

    def stop(self,restore=False):
        for obj,_ in self.started_audio:obj.stop()
        self.started_audio=[]
        if restore:
            for obj,prop,original,track in self.bindings:setattr(obj,prop,copy.deepcopy(original))
        self.playing=False
