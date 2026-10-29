"""Export a complete project using the standalone player entry point."""
import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from build_exe import ensure_pyinstaller
from build_support import build_environment, validate_name, validate_build_destination


def native_target():
    return {'win32':'windows', 'darwin':'macos'}.get(sys.platform, sys.platform)

def validate_target(target='native'):
    target = native_target() if target == 'native' else target
    if target not in ('windows', 'macos'):
        raise ValueError('Supported game targets: windows, macos')
    if target != native_target():
        raise ValueError('Сборка ' + target + ' выполняется на этой ОС. Перенесите исходники движка и проект на ' + ('Mac' if target == 'macos' else 'Windows') + ' и запустите build_game.py там.')
    return target

def game_output(output, name, target, onefile=False, console=False):
    output = Path(output)
    if target == 'macos':
        return output / (name if console else name + '.app')
    return output / (name + '.exe' if onefile else name + '/' + name + '.exe')

def prepare_source(project, output, name, target):
    """Create a portable build kit; no target binary is claimed."""
    import zipfile
    project=Path(project).resolve();output=Path(output).resolve();name=validate_name(name)
    if not (project / 'project.json').is_file():
        raise ValueError('project.json не найден')
    if output.is_relative_to(project):
        raise ValueError('Пакет сборки должен находиться вне проекта')
    output.mkdir(parents=True, exist_ok=True)
    archive=output / (name + '-' + target + '-source.zip')
    if archive.exists():
        raise ValueError('Пакет уже существует: ' + str(archive))
    root=Path(__file__).resolve().parent
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for base,prefix in ((root / 'engine','engine'),(project,'project')):
            for file in base.rglob('*'):
                relative=file.relative_to(base)
                if file.is_file() and not file.is_symlink() and not any(p.startswith('.') or p in ('__pycache__','venv','node_modules') for p in relative.parts):
                    bundle.write(file, str(Path(prefix) / relative).replace('\\','/'))
        for filename in ('build_game.py','build_exe.py','build_support.py','game_runner.py'):
            bundle.write(root / filename, filename)
        bundle.writestr('requirements-game.txt', 'pygame==2.6.1\nnumpy>=2.0,<3\npyinstaller>=6.0,<7\n')
        bundle.writestr('BUILD.txt', 'Build on '+target+' with Python 3.13.\npython3 -m pip install -r requirements-game.txt\npython3 build_game.py --project project --output output --name '+name+' --target '+target+'\nThis source kit is not a compiled game. macOS builds need testing, signing and notarization before public distribution.\n')
    print('[build] Source kit: ' + str(archive))
    return 0

def build_game(project, output, name, onefile=False, console=False, clean=False, icon='', target='native'):
    target = validate_target(target)
    project = Path(project).resolve()
    root = Path(__file__).resolve().parent
    name = validate_name(name)
    output = Path(output).resolve()
    validate_build_destination(output, name, onefile)
    if target == 'macos' and (output / (name + '.app')).exists():
        raise ValueError('Приложение уже существует. Выберите другую папку экспорта.')
    if output.is_relative_to(project):
        raise ValueError('Папка экспорта должна находиться вне проекта, чтобы сборка не включала сама себя.')
    config = json.loads((project / 'project.json').read_text(encoding='utf-8-sig'))
    scene = (project / config.get('main_scene', '')).resolve()
    if not scene.is_relative_to(project) or not scene.is_file() or scene.suffix != '.scene':
        raise ValueError('Выберите существующую стартовую сцену в настройках проекта.')
    if not ensure_pyinstaller():
        return 1
    from engine.systems.cloud_scripts import compile_cloud, transpile_cloud
    imports = set()
    for script in (project / 'scripts').rglob('*'):
        if script.suffix not in ('.py', '.cloud') or not script.is_file():
            continue
        source = script.read_text(encoding='utf-8-sig')
        if script.suffix == '.cloud':
            compile_cloud(source, str(script))
            source = transpile_cloud(source, str(script))
        tree = ast.parse(source, str(script))
        for node in ast.walk(tree):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and not node.level and node.module else []
            for module in names:
                first = module.split('.')[0]
                if not any((project / 'scripts' / (first + suffix)).exists() for suffix in ('.py', '.cloud', '')):
                    imports.add(module)
    sep = ';' if os.name == 'nt' else ':'
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--name', name,
        '--distpath', str(output), '--workpath', str(output / '.build-game'),
        '--specpath', str(output / '.spec'), '--paths', str(root),
        '--collect-submodules', 'engine', '--exclude-module', 'editor',
        '--exclude-module', 'PyQt6', '--exclude-module', 'tkinter',
        '--add-data', str(root / 'engine/scripting') + sep + 'engine/scripting']
    for file in sorted(project.rglob('*')):
        relative = file.relative_to(project)
        if file.is_file() and not file.is_symlink() and not any(p.startswith('.') or p in ('__pycache__', 'venv', 'node_modules') for p in relative.parts):
            args += ['--add-data', str(file) + sep + str(Path('game_data') / relative.parent)]
    for module in sorted(imports):
        args += ['--hidden-import', module]
    if icon:
        icon = str(Path(icon).resolve())
        if not Path(icon).is_file():
            raise ValueError('Файл иконки не найден')
        args += ['--icon', icon]
    args.append('--onefile' if onefile else '--onedir')
    args.append('--console' if console else '--windowed')
    if clean:
        args.append('--clean')
    args.append(str(root / 'game_runner.py'))
    return subprocess.call(args, cwd=root, env=build_environment())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--name', default='CloudGame')
    parser.add_argument('--icon', default='')
    parser.add_argument('--prepare-source', action='store_true')
    parser.add_argument('--target', choices=['native','windows','macos'], default='native')
    for flag in ('onefile', 'console', 'clean'):
        parser.add_argument('--' + flag, action='store_true')
    options=vars(parser.parse_args())
    prepare=options.pop('prepare_source')
    if prepare:
        raise SystemExit(prepare_source(options['project'], options['output'], options['name'], options['target']))
    raise SystemExit(build_game(**options))
