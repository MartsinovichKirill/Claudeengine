"""Cooperative scene reservations and external-change detection, not live networking."""
import getpass
import hashlib
import json
import os
import socket
from pathlib import Path


def identity():return getpass.getuser()+'@'+socket.gethostname()


def project_root(path):
    return next((p for p in Path(path).resolve().parents if (p/'project.json').is_file()),None)


def lock_path(path):
    root=project_root(path)
    if root is None:return None
    key=Path(path).resolve().relative_to(root).as_posix().casefold()
    return root/'.cloud-team/locks'/(hashlib.sha256(key.encode()).hexdigest()+'.lock')


def reserve(path):
    lock=lock_path(path)
    if lock is None:raise ValueError('Сохраните сцену внутри проекта')
    lock.parent.mkdir(parents=True,exist_ok=True)
    try:
        with lock.open('x',encoding='utf-8') as file:json.dump({'owner':identity(),'scene':str(Path(path).name)},file)
    except FileExistsError:
        check_reservation(path)


def check_reservation(path):
    lock=lock_path(path)
    if lock and lock.exists():
        owner=json.loads(lock.read_text(encoding='utf-8'))['owner']
        if owner!=identity():raise PermissionError('Сцена зарезервирована: '+owner)


def release(path):
    check_reservation(path)
    lock=lock_path(path)
    if lock:lock.unlink(missing_ok=True)


def revision(path):
    file=Path(path)
    return hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None


def prepare_project(root):
    root=Path(root)
    additions={'.gitignore':'\n# Cloud Engine local files\n__pycache__/\n*.pyc\n.cloud-test-reports/\n.cloud-recovery/\neditor_settings*.json\nrecent-projects.json\nexports/\n',
               '.gitattributes':'\n# Cloud Engine text resources\n*.scene text eol=lf\n*.cloud text eol=lf\n*.gamedata text eol=lf\n*.cutscene text eol=lf\n*.png binary\n*.ogg binary\n*.wav binary\n'}
    for name,text in additions.items():
        file=root/name;old=file.read_text(encoding='utf-8') if file.exists() else ''
        if '# Cloud Engine' not in old:file.write_text(old+text,encoding='utf-8')
