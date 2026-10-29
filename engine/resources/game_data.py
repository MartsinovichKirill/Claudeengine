"""Typed project data. Values are shared on disk and copied on access."""
import copy
import json
import math
import os
from pathlib import Path
from collections.abc import Mapping
import uuid

from engine.math.vector2 import Vector2

FIELD_TYPES = ('int','float','bool','string','vector2','color','resource')
TEMPLATES = {
    'weapon': {'damage':('float',1.0),'cooldown':('float',.3),'range':('float',48.0),'icon':('resource','')},
    'enemy': {'health':('int',3),'speed':('float',80.0),'damage':('float',1.0),'reward':('int',5)},
    'item': {'title':('string','Предмет'),'stackable':('bool',False),'price':('int',10),'icon':('resource','')},
    'custom': {},
}


def project_path(project_dir,path):
    root=Path(project_dir).resolve()
    candidate=Path(str(path).removeprefix('res://'))
    candidate=(root/candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not candidate.is_relative_to(root): raise ValueError('Ресурс должен находиться внутри проекта: '+str(path))
    return candidate


def validate_document(data,project_dir=None,check_resources=False):
    if not isinstance(data,dict) or data.get('version')!=1:
        raise ValueError('Неизвестный формат игровых данных. Ожидается version: 1.')
    if data.get('kind') not in TEMPLATES: raise ValueError('Неизвестная категория игровых данных')
    if not isinstance(data.get('name'),str) or not data['name'].strip(): raise ValueError('Укажите название записи')
    fields=data.get('fields')
    if not isinstance(fields,dict): raise ValueError('fields должен быть объектом')
    values={}
    for name,field in fields.items():
        if not isinstance(name,str) or not name.isidentifier() or name.startswith('_'):
            raise ValueError('Некорректное имя поля: '+str(name))
        if not isinstance(field,dict) or field.get('type') not in FIELD_TYPES or 'value' not in field:
            raise ValueError('Укажите тип и значение поля '+name)
        kind,value=field['type'],field['value']
        valid=True
        if kind=='int': valid=type(value) is int
        elif kind=='float': valid=type(value) in (int,float) and math.isfinite(value)
        elif kind=='bool': valid=type(value) is bool
        elif kind in ('string','resource'): valid=isinstance(value,str)
        elif kind=='vector2': valid=isinstance(value,list) and len(value)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in value)
        elif kind=='color': valid=isinstance(value,list) and len(value)==4 and all(type(v) is int and 0<=v<=255 for v in value)
        if not valid: raise ValueError(f'Поле {name}: значение не соответствует типу {kind}')
        if kind=='resource' and value and project_dir:
            resolved=project_path(project_dir,value)
            if check_resources and not resolved.is_file(): raise ValueError(f'Поле {name}: ресурс не найден — {value}')
        values[name]=Vector2(value) if kind=='vector2' else float(value) if kind=='float' else copy.deepcopy(value)
    return values


def template(kind='custom',name='NewData'):
    if kind not in TEMPLATES: raise ValueError('Неизвестный шаблон')
    return {'version':1,'kind':kind,'name':name,'fields':{key:{'type':t,'value':copy.deepcopy(v)} for key,(t,v) in TEMPLATES[kind].items()}}


def save_document(path,data,project_dir):
    destination=project_path(project_dir,path)
    if destination.suffix!='.gamedata': raise ValueError('Используйте расширение .gamedata')
    validate_document(data,project_dir)
    text=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary.exists(): temporary.unlink()


class GameData(Mapping):
    """Read-only view, automatically refreshed after an atomic file update."""
    def __init__(self,path,project_dir):
        self.project_dir=Path(project_dir).resolve()
        self.path=project_path(self.project_dir,path)
        self._signature=None; self._values={}; self.document={}
        self.reload()

    @classmethod
    def load(cls,path,project_dir): return cls(path,project_dir)

    def reload(self):
        data=json.loads(self.path.read_text(encoding='utf-8-sig'))
        values=validate_document(data,self.project_dir)
        stat=self.path.stat()
        self._values=values; self.document=copy.deepcopy(data); self._signature=(stat.st_mtime_ns,stat.st_size)
        return self

    def _refresh(self):
        stat=self.path.stat()
        if (stat.st_mtime_ns,stat.st_size)!=self._signature: self.reload()

    def __getitem__(self,key): self._refresh(); return copy.deepcopy(self._values[key])
    def __iter__(self): self._refresh(); return iter(self._values)
    def __len__(self): self._refresh(); return len(self._values)


def load_data(path,project_dir): return GameData(path,project_dir)
