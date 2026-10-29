"""Сборка CloudEngine.exe через PyInstaller.

Использование:
    python build_exe.py                # one-dir сборка (быстрее запускается)
    python build_exe.py --onefile      # один .exe
    python build_exe.py --console      # с консольным окном (для отладки)
    python main.py --build             # то же самое из main.py

Результат: dist/CloudEngine/CloudEngine.exe либо dist/CloudEngine.exe
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from build_support import build_environment, validate_name, validate_build_destination


def _engine_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def available_output(root: str, output: str, name: str, onefile: bool) -> str:
    """Never let PyInstaller clean a previous installation or its open logs."""
    destination = Path(output or Path(root) / 'dist').resolve()
    target = destination / (name + '.exe' if onefile else name)
    if not target.exists():
        return str(destination)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    alternative = destination / ('build-' + stamp)
    index = 1
    while alternative.exists():
        alternative = destination / ('build-' + stamp + '-' + str(index))
        index += 1
    print(f'[build] Предыдущая сборка сохранена. Новый результат: {alternative}')
    return str(alternative)


def ensure_pyinstaller(auto_install: bool = True) -> bool:
    """Проверяет наличие PyInstaller, при необходимости устанавливает."""
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        pass
    if not auto_install:
        return False
    print("[build] PyInstaller не найден, устанавливаю...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "--disable-pip-version-check", "pyinstaller"])
        return True
    except Exception as exc:
        print(f"[build] Не удалось установить PyInstaller: {exc}")
        print("[build] Установите вручную: pip install pyinstaller")
        return False


def build(onefile: bool = False, console: bool = False, clean: bool = False,
          root: str = "", auto_install: bool = True, name: str = "CloudEngine",
          output: str = "", interface: str = "modern") -> int:
    """Собирает исполняемый файл. Возвращает код возврата процесса."""
    root = root or _engine_root()
    if interface not in ('modern','classic'): raise ValueError('Unknown interface profile')
    name = validate_name(name)
    output = available_output(root, output, name, onefile)
    validate_build_destination(Path(output or os.path.join(root, 'dist')), name, onefile)
    if getattr(sys, "frozen", False):
        raise RuntimeError("Сборку нужно запускать внешним python.exe, а не CloudEngine.exe.")
    if not ensure_pyinstaller(auto_install):
        return 1

    # Prebuild a standalone native game player for exports without a compiler.
    player_output = Path(output or Path(root) / 'dist') / '.player-runtime'
    player_command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--name', 'CloudPlayer',
        '--onedir', '--windowed', '--distpath', str(player_output),
        '--workpath', str(player_output / '.build'), '--specpath', str(player_output / '.spec'),
        '--paths', root, '--collect-submodules', 'engine', '--exclude-module', 'editor',
        '--exclude-module', 'PyQt6', '--exclude-module', 'tkinter',
        '--add-data', str(Path(root) / 'engine' / 'scripting') + (';' if os.name == 'nt' else ':') + 'engine/scripting',
        str(Path(root) / 'game_runner.py')]
    code = subprocess.call(player_command, cwd=root, env=build_environment())
    if code:
        return code
    sep = ";" if os.name == "nt" else ":"
    profile_dir=Path(output or Path(root)/'dist')/'.interface-profile'
    profile_dir.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path(root)/'ui-profiles'/(interface+'.json'),profile_dir/'ui-profile.json')
    icon = os.path.join(root, "assets", "engine_icon.ico")
    entry = os.path.join(root, "main.py")

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--add-data", str(player_output / "CloudPlayer") + sep + "player-template",
        "--name", name,
        "--distpath", output or os.path.join(root, "dist"),
        "--workpath", os.path.join(output, ".build") if output else os.path.join(root, "build"),
        "--specpath", os.path.join(output, ".spec") if output else root,
        "--paths", root,
        "--runtime-hook", str(Path(root)/"launcher/qt_runtime_hook.py"),
        "--hidden-import", "qt_runtime",
        '--add-data', str(profile_dir/'ui-profile.json') + sep + '.',
        '--add-data', str(Path(root)/'ui-profiles') + sep + 'ui-profiles',
        "--hidden-import", "pygame",
        "--collect-submodules", "pygame",
        "--hidden-import", "numpy",
        "--add-data", os.path.join(root, "assets") + sep + "assets",
        "--add-data", os.path.join(root, "templates") + sep + "templates",
        "--add-data", os.path.join(root, "projects", 'sample_project') + sep + "projects/sample_project",
        "--add-data", os.path.join(root, "docs") + sep + "docs",
        '--add-data', os.path.join(root, 'plugins') + sep + 'plugins',
        "--add-data", os.path.join(root, "engine", "scripting") + sep + "engine/scripting",
    ]
    # Ship the actual build sources, so rebuilding from the installed editor
    # does not attempt to execute the editor itself as a Python interpreter.
    for filename in ("main.py", "portable_export.py", "portable_diagnostics.py", "build_game.py", "build_exe.py", "build_support.py", "build_game.py", "game_runner.py", "requirements.txt", "qt_runtime.py"):
        args += ["--add-data", os.path.join(root, filename) + sep + "."]
    for package in ("engine", "editor"):
        for source in sorted((Path(root) / package).rglob("*.py")):
            destination = str(source.parent.relative_to(root))
            args += ["--add-data", str(source) + sep + destination]
    if os.path.isfile(icon):
        args += ["--icon", icon]
    if onefile:
        args.append("--onefile")
    args.append("--console" if console else "--windowed")
    if clean:
        args.append("--clean")
    args.append(entry)

    print(f'[build] Сборка {name}: {"один EXE" if onefile else "папка"} -> {output or os.path.join(root, "dist")}')
    try:
        code = subprocess.call(args, cwd=root, env=build_environment())
        if code == 0 and onefile and os.name == 'nt':
            from launcher_build import wrap_onefile
            return wrap_onefile(Path(output) / (name + '.exe'), Path(root))
        return code
    except Exception as exc:
        print(f"[build] Ошибка сборки: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборка Cloud Engine в EXE")
    parser.add_argument("--onefile", action="store_true",
                        help="собрать одним файлом")
    parser.add_argument("--console", action="store_true",
                        help="показывать консольное окно")
    parser.add_argument("--clean", action="store_true",
                        help="очистить кэш сборки")
    parser.add_argument("--no-install", action="store_true",
                        help="не устанавливать PyInstaller автоматически")
    parser.add_argument("--remove-build", action="store_true",
                        help="удалить временную папку build после сборки")
    parser.add_argument("--name", default="CloudEngine", help="имя EXE")
    parser.add_argument("--output", default="", help="папка результата сборки")
    parser.add_argument('--interface',choices=('modern','classic'),default='modern')
    args = parser.parse_args()

    root = _engine_root()
    args.output = available_output(root, args.output, validate_name(args.name), args.onefile)
    code = build(onefile=args.onefile, console=args.console, clean=args.clean,
                 root=root, auto_install=not args.no_install, name=args.name, output=args.output,interface=args.interface)

    if code == 0 and args.remove_build:
        shutil.rmtree(os.path.join(root, "build"), ignore_errors=True)

    if code == 0:
        destination = args.output or os.path.join(root, "dist")
        out = (os.path.join(destination, f"{args.name}.exe") if args.onefile
               else os.path.join(destination, args.name, f"{args.name}.exe"))
        print(f"[build] Готово: {out}")
    else:
        print("[build] Сборка завершилась с ошибкой")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
