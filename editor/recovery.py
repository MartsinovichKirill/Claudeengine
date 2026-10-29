"""Atomic recovery snapshots, kept separate from the user's scene files."""
import hashlib
import json
import logging
import os
from pathlib import Path
import time
import uuid

logger = logging.getLogger('cloudengine.recovery')


class RecoveryStore:
    def __init__(self, project_dir):
        self.root = Path(project_dir).resolve()
        self.directory = self.root / '.cloud-recovery'

    def relative(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Файл восстановления находится вне проекта')
        return path.relative_to(self.root).as_posix()

    def save(self, scenes, scripts):
        """Commit a full session, retaining five independently readable generations."""
        content = {'scenes': scenes, 'scripts': scripts}
        digest = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        existing = self.load()
        if existing and existing.get('digest') == digest: return False
        if not scenes and not scripts: return False
        payload = {'version': 1, 'created': time.time(), 'digest': digest, **content}
        self.directory.mkdir(parents=True, exist_ok=True)
        # A new generation is complete before it can become visible to readers.
        temp = self.directory / (uuid.uuid4().hex + '.tmp')
        destination = self.directory / (str(time.time_ns()) + '.json')
        try:
            with temp.open('x', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, destination)
        finally:
            if temp.exists(): temp.unlink()
        for old in sorted(self.directory.glob('*.json'), reverse=True)[5:]: old.unlink()
        return True

    def load(self):
        for path in sorted(self.directory.glob('*.json'), reverse=True):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                content = {key: data[key] for key in ('scenes','scripts')}
                actual = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                if data.get('version') != 1 or actual != data.get('digest'): continue
                if not isinstance(data['scenes'],list) or not isinstance(data['scripts'],list): continue
                for record in [*data['scenes'],*data['scripts']]:
                    if record.get('path'):
                        self.relative(self.root / record['path'])
                return data
            except (OSError,ValueError,KeyError,TypeError): continue
        return None

    def discard(self):
        # Only our fixed-generation files are deleted, never project sources.
        for path in self.directory.glob('*.json'): path.unlink()


class RecoveryController:
    def __init__(self, window):
        from PyQt6.QtCore import QTimer
        self.window = window
        self.store = None
        self.pending = False
        self.timer = QTimer(window)
        interval = int(window.settings_store.get('editor.autosave_interval_seconds',60))
        self.timer.setInterval(max(15,min(3600,interval))*1000)
        self.timer.timeout.connect(self.capture)
        self.timer.start()

    def set_project(self, directory):
        self.store = RecoveryStore(directory)
        self.pending = self.store.load() is not None

    def capture(self):
        from PyQt6.QtWidgets import QApplication
        from engine.resources.scene_serializer import SceneSerializer
        window = self.window
        if self.store is None or self.pending or window.viewport.is_playing:
            return False
        # Modal tools can temporarily pose scene objects for preview.
        if QApplication.activeModalWidget() is not None: return False
        try:
            scenes = []
            for scene in window.open_scenes:
                if getattr(scene,'_project_dir',window.project_dir) != window.project_dir: continue
                path = self.store.relative(scene.path) if scene.path else ''
                scenes.append({'path':path,'scene':SceneSerializer.scene_to_dict(scene)})
            scripts = []
            script = window.script_editor
            if script.path and script.is_modified():
                scripts.append({'path':self.store.relative(script.path),'text':script.editor.toPlainText()})
            changed = self.store.save(scenes,scripts)
            if changed: window.statusBar().showMessage('Резервная копия сцен и скрипта сохранена',3500)
            return changed
        except Exception:
            logger.exception('Не удалось создать резервную копию. Исходные файлы не изменены.')
            return False

    def offer_restore(self, force=False):
        from PyQt6.QtWidgets import QMessageBox
        if self.store is None: return
        data = self.store.load()
        if not data:
            self.pending = False
            if force: QMessageBox.information(self.window,'Восстановление','Резервных копий в этом проекте нет.')
            return
        self.pending = True
        box = QMessageBox(self.window); box.setWindowTitle('Восстановление работы')
        stamp = time.strftime('%d.%m.%Y %H:%M',time.localtime(data['created']))
        box.setText(f'Найдена резервная копия от {stamp}.\nСцен: {len(data["scenes"])}; несохранённых скриптов: {len(data["scripts"])}.\nВосстановление откроет копии отдельно. Исходные файлы не заменяются.')
        restore = box.addButton('Восстановить копии',QMessageBox.ButtonRole.AcceptRole)
        later = box.addButton('Позже',QMessageBox.ButtonRole.RejectRole)
        discard = box.addButton('Удалить резервные копии',QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        if box.clickedButton() is restore:
            try: self.restore(data)
            except Exception: logger.exception('Не удалось восстановить копию'); return
            self.pending = False
        elif box.clickedButton() is discard:
            self.store.discard(); self.pending = False
        # Later keeps snapshots protected from the autosave timer.

    def restore(self,data):
        from engine.core.scene import Scene
        from engine.resources.scene_serializer import SceneSerializer
        restored=[]
        # Load as built-in nodes, never execute user scripts while recovering.
        for record in data['scenes']:
            raw=record['scene']
            scene=Scene(raw['name']+' (восстановлено)',SceneSerializer.node_from_dict(raw['root']))
            scene.path=''  # Save As is required; never overwrite the original.
            restored.append(scene)
        for scene in restored: self.window._register_scene(scene)
        script_editor=self.window.script_editor
        for record in data['scripts']:
            source=self.store.root/record['path']; self.store.relative(source)
            destination=self.store.directory/'restored-scripts'/uuid.uuid4().hex[:8]/source.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('x',encoding='utf-8') as stream: stream.write(record['text'])
            script_editor.load_file(str(destination))
        self.window._mark_dirty()
        self.window.console.log('Резервная копия восстановлена. Сохраните восстановленные сцены через «Сохранить как».','INFO')

    def clean_saved(self):
        """Keep a session if even one scene differs from its on-disk original."""
        from engine.resources.scene_serializer import SceneSerializer
        if self.store is None or self.pending: return
        try:
            for scene in self.window.open_scenes:
                if getattr(scene,'_project_dir',self.window.project_dir) != self.window.project_dir: continue
                if not scene.path: return
                data=json.loads(Path(scene.path).read_text(encoding='utf-8'))
                if data.get('scene') != SceneSerializer.scene_to_dict(scene): return
            if self.window.script_editor.is_modified(): return
            self.store.discard()
        except (OSError,ValueError): pass


def install(window):
    from PyQt6.QtWidgets import QInputDialog
    window.recovery = RecoveryController(window)
    menu=window.menuBar().addMenu('Восстановление')
    menu.addAction('Создать резервную копию сейчас',window.recovery.capture)
    menu.addAction('Открыть восстановление…',lambda:window.recovery.offer_restore(True))
    def interval():
        seconds,ok=QInputDialog.getInt(window,'Автосохранение','Интервал резервных копий, секунд:',window.recovery.timer.interval()//1000,15,3600)
        if ok:
            window.recovery.timer.setInterval(seconds*1000)
            window.settings_store.set('editor.autosave_interval_seconds',seconds); window.settings_store.save()
    menu.addAction('Интервал автосохранения…',interval)
