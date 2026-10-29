"""Export a game by copying the bundled native player, without Python tools."""
from pathlib import Path
import json
import os
import shutil
import tempfile
from build_support import validate_name


def filesystem_path(path):
    """Use Win32 extended paths without requiring system-wide long-path settings."""
    value=os.fspath(path)
    if os.name!='nt' or value.startswith('\\\\?\\'):
        return Path(value)
    if value.startswith('\\\\'):
        return Path('\\\\?\\UNC\\'+value[2:])
    return Path('\\\\?\\'+value)


def export_portable(project, output, name, template):
    project=Path(project).resolve();output=Path(output).resolve();template=Path(template).resolve()
    name=validate_name(name)
    if output.is_relative_to(project):
        raise ValueError('Экспорт должен находиться вне проекта')
    result=str(output/name)
    project,output,template=map(filesystem_path,(project,output,template))
    settings=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
    scene=(project/settings.get('main_scene','')).resolve()
    if not scene.is_relative_to(project) or not scene.is_file() or scene.suffix!='.scene':
        raise ValueError('Не найдена стартовая сцена')
    player=template/('CloudPlayer.exe' if os.name=='nt' else 'CloudPlayer')
    if not player.is_file() or not (template/'_internal').is_dir():
        raise ValueError('В сборке отсутствует автономный player. Переустановите полный комплект движка.')
    destination=output/name
    if destination.exists():
        raise ValueError('Папка результата уже существует. Выберите другое имя или папку.')
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cloud-export-',dir=output) as temp:
        staging=Path(temp)/name
        shutil.copytree(template,staging)
        data=staging/'_internal'/'game_data'
        if data.exists():
            raise ValueError('Player template unexpectedly contains a project')
        def ignore(folder,names):
            return [n for n in names if n.startswith('.') or n in ('__pycache__','venv','node_modules') or Path(folder,n).is_symlink()]
        shutil.copytree(project,data,ignore=ignore)
        renamed=staging/(name+'.exe' if os.name=='nt' else name)
        (staging/player.name).rename(renamed)
        (staging/'RUN.txt').write_text('Run '+renamed.name+'. Keep the complete folder including _internal. Python installation is not required.\n',encoding='utf-8')
        staging.rename(destination)
    return result
