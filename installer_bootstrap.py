"""Wrap Inno Setup before it touches the user's TEMP directory."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess


def wrap_setup(executable,root):
    root=Path(root); executable=Path(executable)
    work=root/'build'/'setup-bootstrap'/executable.stem
    work.mkdir(parents=True,exist_ok=True)
    payload=work/'SetupPayload.exe'; shutil.copy2(executable,payload)
    source=(root/'installer/SetupBootstrap.cs').read_text(encoding='utf-8')
    source=source.replace('PAYLOAD_HASH',hashlib.sha256(payload.read_bytes()).hexdigest())
    generated=work/'SetupBootstrap.cs'; generated.write_text(source,encoding='utf-8')
    compiler=Path(os.environ.get('SystemRoot','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    output=work/'Setup.exe'
    env=os.environ.copy(); env['TEMP']=env['TMP']=str(work)
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64','/optimize+',
                    '/reference:System.Windows.Forms.dll','/win32icon:'+str(root/'assets/engine_icon.ico'),
                    '/resource:'+str(payload)+',CloudEnginePayload','/out:'+str(output),str(generated)],check=True,env=env)
    shutil.copy2(output,executable)
