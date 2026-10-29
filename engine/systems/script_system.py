"""ScriptSystem — автозагрузка пользовательских скриптов и горячая перезагрузка.

Скрипты лежат в папке scripts/ проекта. Каждый файл — Python-модуль с классом,
наследующим какой-либо класс Node (например, CharacterBody2D). При запуске игры
все модули перечитываются заново (горячая перезагрузка), и сериализатор сцен
использует классы скриптов для инстанцирования нод.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger("cloudengine.script_system")


class ScriptSystem:
    """Загружает и перезагружает пользовательские скрипты проекта."""

    def __init__(self, project_dir: str = "") -> None:
        self.project_dir = project_dir
        self.scripts_dir = os.path.join(project_dir, "scripts") if project_dir else ""
        #: Отображение: относительный путь (scripts/player.py) -> класс.
        self._classes: Dict[str, type] = {}
        #: Отображение: имя класса -> класс.
        self._by_name: Dict[str, type] = {}
        self.errors = []
        self.diagnostics = []
        self._reported_errors = set()

    def set_project_dir(self, project_dir: str) -> None:
        self.project_dir = project_dir
        self.scripts_dir = os.path.join(project_dir, "scripts") if project_dir else ""

    def reload(self) -> int:
        """(Пере)загружает все скрипты из папки scripts/. Возвращает число модулей."""
        self._classes.clear()
        self.errors.clear()
        self.diagnostics.clear()
        self._by_name.clear()
        from engine.systems.cloud_scripts import CloudRuntime
        self.cloud_runtime = CloudRuntime(self.scripts_dir or '.')
        if not self.scripts_dir or not os.path.isdir(self.scripts_dir):
            return 0

        loaded = 0
        current_errors = set()
        from pathlib import Path
        filenames = sorted(str(p.relative_to(self.scripts_dir)).replace('\\', '/') for p in Path(self.scripts_dir).rglob('*') if p.is_file() and not any(part.startswith('.') or part == '__pycache__' for part in p.relative_to(self.scripts_dir).parts))
        for filename in filenames:
            if not filename.endswith((".py", ".cloud", ".cs")) or filename.startswith("_"):
                continue
            try:
                self._load_module(filename)
                loaded += 1
            except Exception as exc:
                self.errors.append((filename, str(exc)))
                path = os.path.join(self.scripts_dir, filename)
                line = getattr(exc, 'lineno', 1) or 1
                if isinstance(exc, SyntaxError):
                    path = exc.filename or path
                else:
                    import traceback
                    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
                        if os.path.abspath(frame.filename).startswith(os.path.abspath(self.scripts_dir) + os.sep):
                            path, line = frame.filename, frame.lineno
                            break
                message = getattr(exc, 'msg', str(exc))
                diagnostic = {'path': path, 'line': line, 'column': getattr(exc, 'offset', 1) or 1,
                              'message': message, 'type': type(exc).__name__}
                self.diagnostics.append(diagnostic)
                signature = (path, line, diagnostic['column'], message)
                current_errors.add(signature)
                if signature not in self._reported_errors:
                    from engine.systems.diagnostics import explain_exception
                    logger.error('Ошибка загрузки скрипта %s\n  File "%s", line %s\n%s: %s',
                                 filename, path, line, type(exc).__name__, message,
                                 extra={'diagnostic':explain_exception(exc,self.project_dir)})
        self._reported_errors = current_errors
        return loaded

    def _load_module(self, filename: str) -> None:
        path = os.path.join(self.scripts_dir, filename)
        if filename.endswith(".cs"):
            from engine.systems.csharp_system import load_csharp
            cls = load_csharp(path)
            self._classes["scripts/" + filename] = cls
            self._by_name[cls.__name__] = cls
            return
        module_name = f"cloudengine_user_{os.path.splitext(filename)[0]}"

        # Загружаем модуль заново (горячая перезагрузка).
        if filename.endswith(".cloud"):
            from engine.systems.cloud_scripts import CloudRuntime
            if not hasattr(self, 'cloud_runtime'):
                self.cloud_runtime = CloudRuntime(self.scripts_dir)
            module = self.cloud_runtime.load(filename)
            module_name = module.__name__
        else:
            module = self._import_python(module_name, path)

        rel_path = os.path.join("scripts", filename).replace("\\", "/")
        from engine.core.node import Node
        from engine.components.behaviour import Behaviour
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, (Node, Behaviour)) and getattr(attr, "__module__", "") == module_name:
                self._classes[rel_path] = attr
                self._by_name[attr_name] = attr

    def _import_python(self, module_name, path):
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        # Recompile even when size and timestamp would reuse stale bytecode.
        import builtins
        from pathlib import Path
        namespace = dict(vars(builtins))
        namespace['__import__'] = self.cloud_runtime._import
        module.__dict__['__builtins__'] = namespace
        try:
            exec(compile(Path(path).read_text(encoding='utf-8-sig'), path, 'exec'), module.__dict__)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise

        return module

    def get_class_for(self, script_path: str) -> Optional[type]:
        """Возвращает класс скрипта по относительному пути."""
        norm = script_path.replace("\\", "/")
        if norm in self._classes:
            return self._classes[norm]
        # Пробуем найти по имени файла.
        base = os.path.splitext(os.path.basename(norm))[0]
        for path, cls in self._classes.items():
            if os.path.splitext(os.path.basename(path))[0] == base:
                return cls
        return None

    def get_class_by_name(self, class_name: str) -> Optional[type]:
        return self._by_name.get(class_name)

    def get_all_classes(self) -> Dict[str, type]:
        return dict(self._classes)
