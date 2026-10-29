"""Cloud Scripts compiler and project-local module runtime.

The language uses Python expressions and indentation, with script, on, func,
let, const, export and signal declarations. Generated code retains line numbers.
"""
from __future__ import annotations

import ast
import builtins
import copy
import io
import linecache
import re
import tokenize
import types
from pathlib import Path


def _cloud_class(cls):
    """Give each instance independent fields and expose exported fields."""
    fields = cls.__dict__.get('__cloud_fields__', ())
    merged = {}
    for base in reversed(cls.__mro__[1:]):
        merged.update(copy.deepcopy(getattr(base, 'exported_properties', {})))
    merged.update(copy.deepcopy(cls.__dict__.get('exported_properties', {})))
    cls.exported_properties = merged
    for name, spec in cls.__dict__.get('exported_properties', {}).items():
        spec.setdefault('default', copy.deepcopy(getattr(cls, name, None)))
    original = cls.__init__
    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        for name in fields:
            setattr(self, name, copy.deepcopy(getattr(cls, name)))
    cls.__init__ = initialize
    return cls


def transpile_cloud(source: str, filename='<cloud>') -> str:
    lines = []
    string_lines = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.STRING:
                string_lines.update(range(token.start[0] + 1, token.end[0] + 1))
    except (tokenize.TokenError, IndentationError):
        pass  # The translated tokenizer/parser below reports the diagnostic.
    for index, line in enumerate(source.splitlines(), 1):
        if index in string_lines:
            lines.append(line)
            continue
        line = re.sub(r'^(\s*)script\s+(\w+)\s+extends\s+([\w.]+)\s*:', r'\1class \2(\3):', line)
        line = re.sub(r'^(\s*)on\s+(\w+)\((.*?)\)(\s*(?:->\s*[^:]+)?\s*):',
                      lambda m: m[1] + 'def _' + m[2] + '(self' + (', ' + m[3] if m[3].strip() else '') + ')' + m[4] + ':', line)
        line = re.sub(r'^(\s*)(async\s+)?func\s+', lambda m: m[1] + (m[2] or '') + 'def ', line)
        line = re.sub(r'^(\s*)(?:let|const)\s+', r'\1', line)
        # Export markers are legal Python annotations until the AST pass.
        line = re.sub(r'^(\s*)export\s+(\w+)\s*:\s*(\w+)\s*=', r'\1\2: __cloud_export_\3 =', line)
        line = re.sub(r'^(\s*)signal\s+(\w+)\s*$', r'\1__cloud_signal_\2 = None', line)
        lines.append(line)
    translated = '\n'.join(lines) + '\n'
    # Token-aware aliases never modify strings or comments.
    aliases = {'true': 'True', 'false': 'False', 'null': 'None'}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(translated).readline))
    except tokenize.TokenError as exc:
        message, (line, column) = exc.args
        raise SyntaxError(message, (filename, line, column + 1, source.splitlines()[line - 1] if line <= len(source.splitlines()) else '')) from exc
    return tokenize.untokenize([t._replace(string=aliases.get(t.string, t.string))
                               if t.type == tokenize.NAME else t for t in tokens])


def compile_cloud(source, filename='<cloud>'):
    translated = transpile_cloud(source, filename)
    try:
        tree = ast.parse(translated, filename)
    except SyntaxError as error:
        lines = source.splitlines()
        if error.lineno and error.lineno <= len(lines):
            error.text = lines[error.lineno - 1] + '\n'
        raise
    constant_lines = {i: match[1] for i, text in enumerate(source.splitlines(), 1)
                      if (match := re.match(r'\s*const\s+(\w+)', text))}
    def validate_constants(scope):
        declarations = {}
        def walk(node):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                yield child
                yield from walk(child)
        nodes = list(walk(scope))
        for node in nodes:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and constant_lines.get(node.lineno) == node.id:
                declarations.setdefault(node.id, node.lineno)
        for node in nodes:
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in declarations and node.lineno != declarations[node.id]:
                raise SyntaxError(f'Cannot reassign constant {node.id}', (filename, node.lineno, node.col_offset + 1, source.splitlines()[node.lineno - 1]))
    for scope in [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]:
        validate_constants(scope)
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        fields, exports, signals = [], {}, []
        for statement in cls.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not statement.args.args or statement.args.args[0].arg not in ('self', 'cls'):
                    decorators = {d.id for d in statement.decorator_list if isinstance(d, ast.Name)}
                    if 'staticmethod' not in decorators:
                        statement.args.args.insert(0, ast.arg(arg='cls' if 'classmethod' in decorators else 'self'))
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                fields.append(statement.target.id)
                annotation = statement.annotation
                if isinstance(annotation, ast.Name) and annotation.id.startswith('__cloud_export_'):
                    kind = annotation.id.removeprefix('__cloud_export_')
                    if kind not in ('int', 'float', 'bool', 'str', 'string', 'Vector2', 'color', 'resource'):
                        raise SyntaxError(f'Unsupported exported type: {kind}', (filename, statement.lineno, statement.col_offset + 1, source.splitlines()[statement.lineno - 1]))
                    exports[statement.target.id] = {'type': {'str': 'string', 'Vector2': 'vector2'}.get(kind, kind)}
                    statement.annotation = ast.Constant(value=kind)
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        if target.id.startswith('__cloud_signal_'):
                            signals.append(target.id.removeprefix('__cloud_signal_'))
                        elif not target.id.startswith('__'):
                            fields.append(target.id)
        extra = ast.parse('__cloud_fields__ = ' + repr(fields)).body
        if exports:
            extra += ast.parse('exported_properties = ' + repr(exports)).body
        if signals:
            extra += ast.parse('signals = ' + repr(signals)).body
        for statement in extra:
            ast.copy_location(statement, cls)
        cls.body.extend(extra)
        cls.decorator_list.append(ast.parse("__import__('engine.systems.cloud_scripts', fromlist=['_cloud_class'])._cloud_class", mode='eval').body)
    ast.fix_missing_locations(tree)
    linecache.cache[str(filename)] = (len(source), None, source.splitlines(True), str(filename))
    return compile(tree, filename, 'exec')


class CloudRuntime:
    """Isolated module cache per project; no process-wide import hooks."""
    def __init__(self, scripts_dir):
        self.root = Path(scripts_dir).resolve()
        self.modules = {}

    def load(self, name):
        requested_suffix = Path(name).suffix
        name = name.replace('\\', '/').removesuffix('.cloud').removesuffix('.py').replace('/', '.')
        if not all(part.isidentifier() for part in name.split('.')):
            raise ImportError(f'Invalid Cloud module: {name}')
        if name in self.modules:
            return self.modules[name]
        path = self.root.joinpath(*name.split('.')).with_suffix('.py' if requested_suffix == '.py' else '.cloud')
        if not path.is_file():
            path = path.with_suffix('.py')
        if not path.is_relative_to(self.root):
            raise ImportError(name)
        module = types.ModuleType('cloudengine_user_' + name)
        module.__file__ = str(path)
        self.modules[name] = module
        from engine.nodes import NODE_CLASSES
        from engine.math.vector2 import Vector2
        from engine.core.signal import Signal
        namespace = dict(vars(builtins))
        namespace['__import__'] = self._import
        module.__dict__.update(NODE_CLASSES)
        from engine.components.behaviour import Behaviour
        module.__dict__["Behaviour"] = Behaviour
        from engine.resources.game_data import load_data
        module.__dict__['load_data'] = lambda path: load_data(path,self.root.parent)
        module.__dict__.update(__builtins__=namespace, __cloud_class__=_cloud_class,
                               Vector2=Vector2, Signal=Signal)
        try:
            source = path.read_text(encoding='utf-8-sig')
            code = compile_cloud(source, str(path)) if path.suffix == '.cloud' else compile(source, str(path), 'exec')
            exec(code, module.__dict__)
        except BaseException:
            self.modules.pop(name, None)
            raise
        return module

    def _import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if level:
            current = (globals or {}).get('__name__', '').removeprefix('cloudengine_user_').split('.')[:-1]
            if level > len(current) + 1:
                raise ImportError('Relative import outside scripts directory')
            name = '.'.join(current[:len(current) - level + 1] + ([name] if name else []))
        path = self.root.joinpath(*name.split('.')).with_suffix('.cloud')
        if path.is_file() or path.with_suffix('.py').is_file():
            if '.' in name and not fromlist:
                raise ImportError('Use "from package.module import name" for nested Cloud modules')
            return self.load(name)
        return builtins.__import__(name, globals, locals, fromlist, level)
