"""Project-local resource relocation with JSON reference updates and rollback."""
import copy,json,os,shutil,uuid
from pathlib import Path

FORMATS={'.json','.scene','.prefab','.material','.animation','.anim','.postfx','.component','.gamedata','.behavior','.particles'}

def remap(value, old, new):
    if isinstance(value,str):
        prefix='res://' if value.startswith('res://') else ''
        path=value[len(prefix):].replace('\\','/')
        if path==old or path.startswith(old+'/'):
            return prefix+new+path[len(old):]
        return value
    if isinstance(value,list):return [remap(v,old,new) for v in value]
    if isinstance(value,dict):return {k:remap(v,old,new) for k,v in value.items()}
    return value

def relocate_resource(project, source, destination):
    root=Path(project).resolve();source=Path(source).resolve();destination=Path(destination).resolve()
    if not source.is_relative_to(root) or not destination.is_relative_to(root) or source==root:
        raise ValueError('Ресурс должен оставаться внутри проекта')
    if not source.exists() or source.is_symlink():raise ValueError('Ресурс не найден или является ссылкой')
    if destination.exists() or destination.is_relative_to(source):raise ValueError('Папка/имя назначения уже заняты или находятся внутри исходной папки')
    if not destination.parent.is_dir():raise ValueError('Папка назначения не найдена')
    old=source.relative_to(root).as_posix();new=destination.relative_to(root).as_posix()
    changed=[]
    for file in root.rglob('*'):
        if not file.is_file() or file.is_symlink() or file.suffix not in FORMATS or any(p.startswith('.') for p in file.relative_to(root).parts):continue
        raw=file.read_bytes()
        try:data=json.loads(raw.decode('utf-8-sig'))
        except (UnicodeError,ValueError):continue
        updated=remap(data,old,new)
        if updated!=data:changed.append((file,raw,json.dumps(updated,ensure_ascii=False,indent=2).encode('utf-8')))
    backup=root/'.cloud-backups'/('resource-move-'+uuid.uuid4().hex)
    for file,raw,_ in changed:
        target=backup/file.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    moved=False;written=[]
    try:
        source.rename(destination);moved=True
        for file,raw,updated in changed:
            relocated=destination/file.relative_to(source) if file.is_relative_to(source) else file
            temporary=relocated.with_name(relocated.name+'.cloud-tmp')
            try:
                temporary.write_bytes(updated);os.replace(temporary,relocated)
            finally:
                temporary.unlink(missing_ok=True)
            written.append((relocated,raw))
    except Exception:
        for file,raw in reversed(written):file.write_bytes(raw)
        if moved:destination.rename(source)
        raise
    return old,new

def remap_scene(scene,old,new):
    if scene is None:return
    for node in scene.get_nodes():
        for target in [node,*getattr(node,'components',[])]:
            props=target.get_exported_properties() if hasattr(target,'get_exported_properties') else getattr(target,'exported_properties',{})
            names={key for key,meta in props.items() if meta.get('type')=='resource'}|{'script_path'}
            for key in names:
                value=getattr(target,key,None)
                if isinstance(value,str):setattr(target,key,remap(value,old,new))
            if hasattr(target,'tile_sources'):
                target.tile_sources=remap(target.tile_sources,old,new)
    if scene.path:
        # Full scene path is updated by the caller, relative references above.
        pass
