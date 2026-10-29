"""Windows C# script bridge, compiled with the installed Framework compiler."""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from engine.nodes.node2d import Node2D


def load_csharp(path):
    source = Path(path)
    host = Path(__file__).resolve().parents[1] / 'scripting' / 'ScriptHost.cs'
    compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not compiler.is_file():
        raise RuntimeError('C# requires the Windows .NET Framework C# compiler')
    digest = hashlib.sha256(source.read_bytes() + host.read_bytes()).hexdigest()[:20]
    cache = source.parent / '.cloud_cache'
    cache.mkdir(exist_ok=True)
    executable = cache / (digest + '.exe')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if not executable.exists():
        result = subprocess.run([str(compiler), '/nologo', '/target:exe',
            '/r:System.Web.Extensions.dll', '/out:' + str(executable), str(host), str(source)],
            capture_output=True, text=True, creationflags=flags, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    class CSharpNode(Node2D):
        def __init__(self, name='CSharpNode'):
            super().__init__(name)
            self._worker = None
            self._responses = queue.Queue()

        def _start(self):
            self._worker = subprocess.Popen([str(executable)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                encoding='utf-8', creationflags=flags)
            output = self._worker.stdout
            responses = self._responses
            def read():
                for line in output: responses.put(line)
                responses.put(None)
            threading.Thread(target=read, daemon=True).start()

        def _invoke(self, event, delta=0):
            if self._worker is None: self._start()
            velocity = getattr(self, 'velocity', None)
            state = dict(event=event, delta=delta, X=self.position.x,Y=self.position.y,
                Rotation=self.rotation,ScaleX=self.scale.x,ScaleY=self.scale.y,Name=self.name,
                VelocityX=getattr(velocity,'x',0),VelocityY=getattr(velocity,'y',0),
                OnFloor=bool(getattr(self,'is_on_floor',lambda:False)()))
            try:
                self._worker.stdin.write(json.dumps(state)+'\n');self._worker.stdin.flush()
                line = self._responses.get(timeout=2)
                if line is None: raise RuntimeError('C# worker exited')
                result = json.loads(line)
                if 'error' in result: raise RuntimeError(result['error'])
                self.position.x,self.position.y=result['X'],result['Y']
                self.rotation=result['Rotation'];self.scale.x,self.scale.y=result['ScaleX'],result['ScaleY']
                if velocity is not None: velocity.x,velocity.y=result['VelocityX'],result['VelocityY']
            except Exception:
                self._close()
                self.process_enabled=False;self.physics_process_enabled=False
                raise

        def _close(self):
            if self._worker is not None:
                self._worker.kill();self._worker.wait(timeout=2)
                self._worker.stdin.close();self._worker.stdout.close();self._worker=None

        def _ready(self): self._invoke('ready')
        def _process(self,delta): self._invoke('process',delta)
        def _physics_process(self,delta): self._invoke('physics',delta)
        def _exit_tree(self): self._close()

    CSharpNode.__name__ = source.stem
    return CSharpNode
