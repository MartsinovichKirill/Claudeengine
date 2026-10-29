"""Scoped Python tracing for Cloud Scripts; no tracing in exported games by default."""
import contextlib
import sys
from pathlib import Path


class DebugStop(BaseException):
    pass


class ScriptDebugger:
    def __init__(self, project_dir='', on_pause=None):
        self.project_dir = project_dir
        self.on_pause = on_pause
        self.breakpoints = {}
        self.paused = False
        self.enabled = True
        self.mode = 'continue'
        self.frame = None
        self.depth = 0
        self.abort_requested = False
        self._path_cache = {}

    def toggle(self, path, line):
        key = str(Path(path).resolve()).casefold()
        lines = self.breakpoints.setdefault(key, set())
        if line in lines:
            lines.remove(line)
        else:
            lines.add(line)
        return line in lines

    def contains(self, path):
        if not self.project_dir:
            return False
        if path not in self._path_cache:
            resolved=Path(path).resolve()
            self._path_cache[path]=resolved.suffix.lower() in ('.cloud','.py') and resolved.is_relative_to(Path(self.project_dir).resolve() / 'scripts')
        return self._path_cache[path]

    def script_depth(self, frame):
        depth = 0
        while frame:
            depth += self.contains(frame.f_code.co_filename)
            frame = frame.f_back
        return depth

    def command(self, mode):
        self.mode = mode
        if self.frame:
            self.depth = self.script_depth(self.frame)

    def trace(self, frame, event, arg):
        if self.abort_requested:
            raise DebugStop()
        if not self.enabled or not self.contains(frame.f_code.co_filename):
            return None
        if event != 'line':
            return self.trace
        key = str(Path(frame.f_code.co_filename).resolve()).casefold()
        depth = self.script_depth(frame)
        stop = frame.f_lineno in self.breakpoints.get(key, set())
        stop |= self.mode == 'into' or self.mode == 'over' and depth <= self.depth or self.mode == 'out' and depth < self.depth
        if stop:
            self.paused = True
            self.frame = frame
            self.mode = 'continue'
            try:
                if self.on_pause:
                    self.on_pause(frame)
            finally:
                self.paused = False
                self.frame = None
            if self.abort_requested:
                raise DebugStop()
        return self.trace

    @contextlib.contextmanager
    def tracing(self):
        previous = sys.gettrace()
        sys.settrace(self.trace if self.enabled else previous)
        try:
            yield
        finally:
            sys.settrace(previous)

    def reset(self):
        self.mode = 'continue'
        self.abort_requested = False
        self._path_cache = {}
        self.frame = None
        self.paused = False
