"""Read-only scene checks. User scripts are compiled, never executed."""
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SceneIssue:
    node: object
    message: str
    path: str = ''
    line: int = 1

def validate_scene(scene, project_dir):
    from types import SimpleNamespace
    from engine.systems.render_system import RenderSystem
    from engine.systems.cloud_scripts import compile_cloud
    issues = []
    if RenderSystem(SimpleNamespace(current_scene=scene)).find_active_camera() is None:
        candidates = [n for n in scene.get_nodes() if 'Camera' in type(n).__name__ or any(getattr(c, 'type_name', '') == 'Camera2D' for c in getattr(n, 'components', []))]
        issues.append(SceneIssue(candidates[0] if candidates else None, 'Нет включённой Camera2D. Добавьте или включите камеру.'))
    root = Path(project_dir or '.').resolve()
    checked = set()
    for node in scene.get_nodes():
        for target in [node, *getattr(node, 'components', [])]:
            getter = getattr(target, 'get_exported_properties', None)
            properties = getter() if callable(getter) else getattr(target, 'exported_properties', {})
            paths = [getattr(target, key, '') for key, meta in properties.items() if meta.get('type') == 'resource']
            script = getattr(target, 'script_path', '')
            if script and script not in paths:
                paths.append(script)
            paths += list(getattr(target, 'tile_sources', {}).values())
            paths += list(getattr(target, '_frame_paths', []))
            for clip in getattr(target, 'animations', {}).values():
                if isinstance(clip, dict):
                    paths += list(clip.get('frames', []))
            for value in paths:
                if not isinstance(value, str) or not value:
                    continue
                path = Path(value.replace('res://', '', 1))
                path = path if path.is_absolute() else root / path
                key = (id(node), str(path))
                if key in checked:
                    continue
                checked.add(key)
                if not path.is_file():
                    issues.append(SceneIssue(node, 'Ресурс не найден: ' + value, str(path)))
                elif path.suffix.lower() == '.gamedata':
                    try:
                        import json
                        from engine.resources.game_data import validate_document
                        validate_document(json.loads(path.read_text(encoding='utf-8-sig')),root,True)
                    except (OSError,ValueError,TypeError) as error:
                        issues.append(SceneIssue(node,'Ошибка игровых данных: '+str(error),str(path)))
                elif path.suffix.lower() in ('.py', '.cloud'):
                    try:
                        source = path.read_text(encoding='utf-8-sig')
                        if path.suffix.lower() == '.cloud':
                            compile_cloud(source, str(path))
                        else:
                            compile(source, str(path), 'exec')
                    except (SyntaxError, ValueError, OSError, UnicodeError) as error:
                        issues.append(SceneIssue(node, 'Ошибка скрипта: ' + value + ': ' + str(error), str(path), getattr(error, 'lineno', 1) or 1))
    return issues


