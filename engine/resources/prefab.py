"""Linked object resources with three-way updates and local overrides."""
import copy
import json
import uuid
from pathlib import Path


def atomic_json(path, data):
    import os
    import tempfile
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        except BaseException:
            stream.close(); temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def assign_ids(node):
    node.prefab_id = getattr(node, 'prefab_id', '') or uuid.uuid4().hex
    for component in node.components:
        component.prefab_id = getattr(component, 'prefab_id', '') or uuid.uuid4().hex
    for child in node.get_children():
        assign_ids(child)


def merge(base, local, remote):
    """Keep local changes; accept remote changes where local equals base."""
    if local == base:
        return copy.deepcopy(remote)
    if isinstance(base, dict) and isinstance(local, dict) and isinstance(remote, dict):
        result = {}
        for key in set(base) | set(local) | set(remote):
            if key not in local:
                if key not in base and key in remote:
                    result[key] = copy.deepcopy(remote[key])
            elif key not in remote:
                if key not in base or local[key] != base[key]:
                    result[key] = copy.deepcopy(local[key])
            elif key not in base:
                result[key] = copy.deepcopy(local[key])
            else:
                result[key] = merge(base[key], local[key], remote[key])
        return result
    if all(isinstance(items, list) for items in (base, local, remote)):
        if all(isinstance(item, dict) and item.get('prefab_id') for items in (base, local, remote) for item in items):
            maps = [{item['prefab_id']: item for item in items} for items in (base, local, remote)]
            merged = merge(*maps)
            order = list(dict.fromkeys([item['prefab_id'] for item in remote + local]))
            return [merged[key] for key in order if key in merged]
    return copy.deepcopy(local)


def resource_path(project_dir, relative):
    root = Path(project_dir).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Ресурс должен находиться внутри проекта')
    return path


class Prefab:
    @staticmethod
    def save(node, path, project_dir):
        from engine.resources.scene_serializer import SceneSerializer
        path = resource_path(project_dir, path)
        assign_ids(node)
        data = SceneSerializer.node_to_dict(node)
        data.pop('prefab', None)
        atomic_json(path, {'version': 1, 'root': data})
        node.prefab = {'path': path.relative_to(Path(project_dir).resolve()).as_posix(), 'base': copy.deepcopy(data)}
        return node.prefab['path']

    @staticmethod
    def instantiate(path, project_dir, script_system=None):
        from engine.resources.scene_serializer import SceneSerializer
        path = resource_path(project_dir, path)
        data = json.loads(path.read_text(encoding='utf-8'))['root']
        node = SceneSerializer.node_from_dict(data, script_system)
        node.prefab = {'path': path.relative_to(Path(project_dir).resolve()).as_posix(), 'base': copy.deepcopy(data)}
        return node

    @staticmethod
    def updated_data(node, project_dir):
        from engine.resources.scene_serializer import SceneSerializer
        link = getattr(node, 'prefab', None)
        if not link:
            return None
        assign_ids(node)
        remote = json.loads(resource_path(project_dir, link['path']).read_text(encoding='utf-8'))['root']
        local = SceneSerializer.node_to_dict(node); local.pop('prefab', None)
        data = merge(link['base'], local, remote)
        # Placement belongs to the instance even if it matched the old template.
        data['name'] = local['name']
        for key in ('position', 'rotation', 'scale'):
            if key in local.get('properties', {}):
                data.setdefault('properties', {})[key] = copy.deepcopy(local['properties'][key])
        for component in data.get('components', []):
            if component['type'] == 'Transform':
                component['properties'].update({key: data['properties'][key] for key in ('position', 'rotation', 'scale')})
        data['prefab'] = {'path': link['path'], 'base': copy.deepcopy(remote)}
        return data

    @staticmethod
    def apply(node, data, script_system=None):
        from engine.resources.scene_serializer import SceneSerializer
        fresh = SceneSerializer.node_from_dict(data, script_system)
        for key in fresh.get_property_list():
            if hasattr(fresh, key):
                node.set(key, copy.deepcopy(getattr(fresh, key)))
        node.name = fresh.name
        node.script_path = fresh.script_path
        if hasattr(fresh, '_serialize_data'):
            node._deserialize_data(fresh._serialize_data())
        for component in node.components:
            component.owner = None
        node.components = fresh.components
        for component in node.components:
            component.owner = node
        for child in list(node.get_children()):
            node.remove_child(child)
        for child in list(fresh.get_children()):
            fresh.remove_child(child); node.add_child(child)
        node.prefab_id = getattr(fresh, 'prefab_id', '')
        node.prefab = getattr(fresh, 'prefab', None)
        if hasattr(node, '_component_body'):
            node._component_body = None
