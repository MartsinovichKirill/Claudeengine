"""Build the Windows single-file bootstrap after PyInstaller packaging."""
import hashlib,os,shutil,subprocess
from pathlib import Path
from build_support import build_environment

def wrap_onefile(executable, root):
    executable=Path(executable).resolve();root=Path(root).resolve()
    windows=Path(os.environ.get('SystemRoot','C:/Windows'))
    candidates=[windows/'Microsoft.NET/Framework64/v4.0.30319/csc.exe',windows/'Microsoft.NET/Framework/v4.0.30319/csc.exe']
    compiler=next((path for path in candidates if path.is_file()),None)
    if compiler is None:
        raise RuntimeError('Для сборки загрузчика требуется компилятор .NET Framework csc.exe')
    work=executable.parent/'.bootstrap';work.mkdir(exist_ok=True)
    payload=work/'CloudEnginePayload.exe';shutil.copy2(executable,payload)
    source=(root/'launcher/CloudBootstrap.cs').read_text(encoding='utf-8')
    source=source.replace('PAYLOAD_HASH',hashlib.sha256(payload.read_bytes()).hexdigest())
    generated=work/'CloudBootstrap.cs';generated.write_text(source,encoding='utf-8')
    output=work/'CloudEngineLauncher.exe'
    args=[str(compiler),'/nologo','/target:winexe','/platform:x64','/optimize+','/reference:System.Windows.Forms.dll','/resource:'+str(payload)+',CloudEnginePayload','/out:'+str(output)]
    icon=root/'assets/engine_icon.ico'
    if icon.is_file():args.append('/win32icon:'+str(icon))
    args.append(str(generated))
    env=build_environment()
    temporary=work/'temp';temporary.mkdir(exist_ok=True)
    env['TEMP']=env['TMP']=str(temporary)
    code=subprocess.call(args,env=env,cwd=work)
    if code==0:shutil.copy2(output,executable)
    return code
