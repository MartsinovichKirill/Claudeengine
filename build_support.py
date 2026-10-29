"""Shared validation, writable locations, and external Python discovery."""
from __future__ import annotations
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager


@contextmanager
def external_dll_search():
    """Do not pass the frozen editor's DLL search directory to system Python."""
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        yield
        return
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p]
    buffer = ctypes.create_unicode_buffer(32768)
    kernel.GetDllDirectoryW(len(buffer), buffer)
    kernel.SetDllDirectoryW(None)
    try:
        yield
    finally:
        kernel.SetDllDirectoryW(buffer.value or None)


def validate_name(name: str) -> str:
    value = name.strip()
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{prefix}{i}' for prefix in ('COM', 'LPT') for i in range(1, 10)}
    if (not value or value in ('.', '..') or value.endswith(('.', ' ')) or
            re.search(r'[<>:"/\\|?*\x00-\x1f]', value) or value.split('.')[0].upper() in reserved):
        raise ValueError('Укажите имя без запрещённых символов и зарезервированных имён Windows.')
    return value


def writable_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
        return True
    except OSError:
        return False


def default_projects_dir() -> Path:
    portable = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    if getattr(sys, 'frozen', False):
        # PyInstaller replaces its application directory on rebuild. Keep
        # user projects outside that directory, shared by both release modes.
        base = portable.parent if (portable / '_internal').is_dir() else portable
        launcher=os.environ.get('CLOUDENGINE_LAUNCHER_PATH','')
        candidates = ([Path(launcher).resolve().parent / 'Cloud Projects'] if launcher else []) + [base / 'Cloud Projects']
    else:
        candidates = [portable / 'projects']
    # Profile paths are fallbacks, never an assumed writable home directory.
    if os.environ.get('LOCALAPPDATA'):
        candidates.append(Path(os.environ['LOCALAPPDATA']) / 'CloudEngine' / 'projects')
    candidates.append(Path.home() / 'Documents' / 'Cloud Projects')
    for path in candidates:
        if writable_directory(path):
            return path
    return portable  # The hub will ask the user to choose a writable location.


def validate_build_destination(destination: Path, name: str, onefile: bool) -> Path:
    destination = destination.resolve()
    target = destination / (name + '.exe' if onefile else name)
    if not target.resolve().is_relative_to(destination):
        raise ValueError('Результат сборки должен находиться внутри выбранной папки.')
    if not onefile and target.exists():
        for root in (target, target / 'projects'):
            if (root / 'project.json').is_file() or any(root.glob('*/project.json')):
                raise ValueError(f'В папке «{target}» есть проекты. Выберите другую папку результата, чтобы сохранить их.')
    return target


def build_environment() -> dict:
    env = os.environ.copy()
    if os.name == 'nt':
        windows = Path(env.get('SystemRoot', 'C:/Windows'))
        # Qt uses Windows' unversioned ICU. Foreign tools can provide an
        # incompatible icuuc.dll and obsolete CRT forwarders earlier in PATH.
        env['PATH'] = os.pathsep.join([str(windows / 'System32'), str(windows), env.get('PATH', '')])
    for key in ('PYTHONHOME', 'PYTHONPATH', '_PYI_APPLICATION_HOME_DIR', '_PYI_ARCHIVE_FILE', '_PYI_PARENT_PROCESS_LEVEL'):
        env.pop(key, None)
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def find_build_python(root: str, preferred: str = '') -> str:
    candidates = [Path(preferred)] if preferred else []
    if not getattr(sys, 'frozen', False):
        candidates.append(Path(sys.executable))
    candidates.extend(Path(value) for value in [os.environ.get('CLOUDENGINE_PYTHON', '')] if value)
    for base in [Path(root).resolve(), *list(Path(root).resolve().parents)[:4]]:
        for folder in ('.venv2', '.venv', '.venv1'):
            candidates.append(base / folder / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
    for command in ('python', 'python3'):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    seen = set()
    for candidate in candidates:
        path = str(candidate.resolve())
        if path in seen or not candidate.is_file() or 'windowsapps' in path.lower():
            continue
        seen.add(path)
        if getattr(sys, 'frozen', False) and candidate.resolve() == Path(sys.executable).resolve():
            continue
        try:
            with external_dll_search():
                result = subprocess.run([path, '-c', 'import PyQt6.QtWidgets,pygame,numpy,PyInstaller'],
                    capture_output=True, env=build_environment(), timeout=12,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode == 0:
                return path
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError('Не найден Python с PyQt6, pygame, numpy и PyInstaller. Укажите путь к python.exe в окне сборки или настройте CLOUDENGINE_PYTHON.')
