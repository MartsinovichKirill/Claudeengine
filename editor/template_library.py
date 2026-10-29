"""Bundled offline templates, installed into a unique project namespace."""
import json
import shutil
import tempfile
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[1] / 'templates'


def export_player_template(destination):
    import zipfile
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cloud-template-', dir=destination.parent) as tmp:
        root = Path(tmp)
        (root/'project.json').write_text(json.dumps({'name':'Player Controller 2D',
            'window':{'width':1280,'height':720}, 'render':{'pixel_art':True}}), encoding='utf-8')
        scene = install_player_template(root)
        config = json.loads((root/'project.json').read_text(encoding='utf-8'))
        config['main_scene'] = scene.relative_to(root).as_posix()
        (root/'project.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
        archive = root/'template.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
            for path in root.rglob('*'):
                if path.is_file() and path != archive:
                    output.write(path, 'PlayerController2D/'+path.relative_to(root).as_posix())
        archive.replace(destination)
    return destination


def install_player_template(project):
    root = Path(project).resolve()
    config_path = root / 'project.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    source = LIBRARY / 'player_controller'
    if not (source / 'scene.json').is_file():
        raise FileNotFoundError('Шаблон контроллера не включён в эту сборку.')
    name, index = 'player_controller', 2
    while any((root / path).exists() for path in (f'assets/templates/{name}', f'scripts/templates/{name}.cloud', f'scenes/{name}.scene')):
        name = f'player_controller_{index}'
        index += 1
    created = []
    try:
        assets = root / 'assets/templates' / name
        assets.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source / 'assets', assets)
        created.append(assets)
        script = root / 'scripts/templates' / (name + '.cloud')
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / 'player.cloud', script)
        created.append(script)
        data = (source / 'scene.json').read_text(encoding='utf-8').replace('@TEMPLATE@', name)
        scene = root / 'scenes' / (name + '.scene')
        scene.parent.mkdir(parents=True, exist_ok=True)
        scene.write_text(data, encoding='utf-8')
        created.append(scene)
        actions = config.setdefault('input', {})
        for key, keys in {'template_left':['A','Left'], 'template_right':['D','Right'],
                          'template_jump':['Space','W','Up'], 'template_run':['Shift'],
                          'template_restart':['R']}.items():
            actions.setdefault(key, keys)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=root, suffix='.json', delete=False) as output:
            json.dump(config, output, ensure_ascii=False, indent=2)
            temporary = Path(output.name)
        temporary.replace(config_path)
        return scene
    except Exception:
        for path in reversed(created):
            if not path.resolve().is_relative_to(root):
                continue
            if path.is_dir(): shutil.rmtree(path)
            elif path.exists(): path.unlink()
        raise
