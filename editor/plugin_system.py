"""Local editor plugin packages, isolated lifecycle and persistent enable state."""
import importlib.util
import json
import logging
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

logger = logging.getLogger('cloudengine.plugins')
API_VERSION = 1


def plugin_directory():
    from build_support import default_projects_dir
    return default_projects_dir().parent / 'Cloud Plugins'


def read_manifest(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / 'plugin.json').read_text(encoding='utf-8-sig'))
    if not isinstance(manifest, dict) or not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}', manifest.get('id', '')):
        raise ValueError('plugin.json: id должен содержать 2–64 символа a-z, цифры, _ или -.')
    if manifest.get('api_version') != API_VERSION:
        raise ValueError('Плагин требует несовместимую версию API.')
    entry = (folder / manifest.get('entry', 'plugin.py')).resolve()
    if not entry.is_relative_to(folder) or entry.suffix != '.py' or not entry.is_file():
        raise ValueError('Не найден Python-файл entry внутри пакета плагина.')
    manifest['name'] = str(manifest.get('name', manifest['id']))
    manifest['version'] = str(manifest.get('version', '1.0.0'))
    return manifest


class PluginStore:
    def __init__(self, root=None):
        self.root = Path(root) if root else plugin_directory()
        self.builtin = Path(__file__).resolve().parents[1] / 'plugins' / 'builtin'

    def state(self):
        try:
            data = json.loads((self.root / 'state.json').read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def set_enabled(self, plugin_id, enabled):
        state = self.state(); state[plugin_id] = bool(enabled)
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / 'state.json'
        temporary = self.root / 'state.json.tmp'
        temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
        temporary.replace(target)

    def discover(self):
        state = self.state(); found = {}
        for base, builtin in ((self.builtin, True), (self.root, False)):
            if not base.is_dir():
                continue
            for folder in sorted(base.iterdir()):
                if not folder.is_dir() or folder.is_symlink() or folder.name.startswith('.'):
                    continue
                try:
                    data = read_manifest(folder)
                    if data['id'] in found:
                        continue
                    data.update(path=folder, builtin=builtin, enabled=state.get(data['id'], builtin), error='')
                    found[data['id']] = data
                except (OSError, ValueError, TypeError) as exc:
                    logger.warning('Invalid plugin %s: %s', folder, exc)
        return list(found.values())

    def install(self, source):
        self.root.mkdir(parents=True, exist_ok=True)
        source = Path(source).resolve()
        with tempfile.TemporaryDirectory(prefix='.install-', dir=self.root) as temporary:
            staging = Path(temporary) / 'package'; staging.mkdir()
            if source.is_file() and source.suffix.lower() == '.zip':
                with zipfile.ZipFile(source) as archive:
                    entries = archive.infolist()
                    if len(entries) > 2000 or sum(item.file_size for item in entries) > 100 * 1024 * 1024:
                        raise ValueError('Пакет превышает ограничение 100 МБ / 2000 файлов.')
                    for item in entries:
                        relative = item.filename.replace('\\', '/')
                        target = (staging / relative).resolve()
                        if ':' in relative or not target.is_relative_to(staging.resolve()) or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                            raise ValueError('Недопустимый путь или символическая ссылка в ZIP.')
                        if item.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(item) as incoming, target.open('wb') as outgoing:
                                shutil.copyfileobj(incoming, outgoing)
            else:
                folder = source.parent if source.name == 'plugin.json' else source
                if not folder.is_dir():
                    raise ValueError('Выберите ZIP, папку или plugin.json.')
                if self.root.resolve().is_relative_to(folder):
                    raise ValueError('Исходная папка не должна содержать каталог установки плагинов.')
                read_manifest(folder)
                if any(path.is_symlink() for path in folder.rglob('*')):
                    raise ValueError('Пакеты с символическими ссылками не поддерживаются.')
                shutil.copytree(folder, staging, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '.git', '.venv'))
            manifests = list(staging.rglob('plugin.json'))
            if len(manifests) != 1:
                raise ValueError('Пакет должен содержать ровно один plugin.json.')
            package = manifests[0].parent
            manifest = read_manifest(package)
            if any(p['id'] == manifest['id'] for p in self.discover()):
                raise ValueError('Плагин с таким id уже установлен. Существующие файлы не изменены.')
            target = self.root / manifest['id']
            if target.exists():
                raise ValueError('Каталог с таким id уже существует.')
            package.rename(target)
            # Installation does not run code; the user enables it explicitly.
            self.set_enabled(manifest['id'], False)
            return manifest['id']


    def uninstall(self, plugin_id):
        """Move an installed package into recoverable local trash."""
        if not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}', plugin_id):
            raise ValueError('Недопустимый ID плагина.')
        plugin = next((p for p in self.discover() if p['id'] == plugin_id), None)
        if plugin is None or plugin['builtin']:
            raise ValueError('Встроенный или отсутствующий плагин удалить нельзя.')
        source = (self.root / plugin_id).resolve()
        if source.parent != self.root.resolve() or source.is_symlink():
            raise ValueError('Каталог плагина находится вне папки установки.')
        self.set_enabled(plugin_id, False)
        import uuid
        trash = self.root / '.trash'
        trash.mkdir(exist_ok=True)
        destination = trash / (plugin_id + '-' + uuid.uuid4().hex)
        source.rename(destination)
        return destination


class PluginContext:
    def __init__(self, window, menu):
        self.editor = window
        self.menu = menu
        self.actions = []
        self.cleanups = []

    @property
    def project_dir(self):
        return self.editor.project_dir

    @property
    def scene(self):
        return self.editor.current_scene

    def selected(self):
        return list(self.editor.viewport.selected) or ([self.editor.get_selected_node()] if self.editor.get_selected_node() else [])

    def add_action(self, title, callback):
        action = self.menu.addAction(title)
        def invoke():
            try:
                callback()
            except Exception as exc:
                logger.exception('Plugin action failed: %s', title)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.editor, title, str(exc))
        action.triggered.connect(invoke)
        self.actions.append(action)
        return action

    def on_cleanup(self, callback):
        self.cleanups.append(callback)

    def log(self, message):
        self.editor.console.log(str(message), 'INFO')

    def refresh(self):
        self.editor.hierarchy.refresh(); self.editor.inspector.refresh()
        self.editor.assets.refresh(); self.editor._mark_dirty()

    def set_property(self, node, name, value):
        from editor.undo_stack import PropertyCommand
        self.editor.undo_stack.execute(PropertyCommand(node, name, getattr(node, name), value))

    def close(self):
        for callback in reversed(self.cleanups):
            try:
                callback()
            except Exception:
                logger.exception('Plugin cleanup failed')
        for action in self.actions:
            self.menu.removeAction(action); action.deleteLater()


class PluginHost:
    def __init__(self, window, menu, store=None):
        self.window, self.menu = window, menu
        self.store = store or PluginStore()
        self.loaded = []
        self.errors = {}

    def close(self):
        for module, context, module_name in reversed(self.loaded):
            try:
                if callable(getattr(module, 'teardown', None)):
                    module.teardown(context)
            except Exception:
                logger.exception('Plugin teardown failed')
            context.close()
            for key in list(sys.modules):
                if key == module_name or key.startswith(module_name + '.'):
                    sys.modules.pop(key, None)
        self.loaded.clear()

    def reload(self):
        self.close(); self.errors.clear()
        for plugin in self.store.discover():
            if not plugin['enabled']:
                continue
            context = PluginContext(self.window, self.menu)
            module_name = 'cloud_plugin_' + plugin['id'].encode('utf-8').hex()
            try:
                entry = plugin['path'] / plugin.get('entry', 'plugin.py')
                spec = importlib.util.spec_from_file_location(module_name, entry, submodule_search_locations=[str(plugin['path'])])
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                if not callable(getattr(module, 'setup', None)):
                    raise ValueError('Плагин должен объявить setup(context).')
                module.setup(context)
                self.loaded.append((module, context, module_name))
            except Exception as exc:
                context.close()
                for key in list(sys.modules):
                    if key == module_name or key.startswith(module_name + '.'):
                        sys.modules.pop(key, None)
                self.errors[plugin['id']] = str(exc)
                logger.exception('Plugin load failed: %s', plugin['id'])
