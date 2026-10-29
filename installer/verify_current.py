import os,subprocess,json,hashlib,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];q=r/'build/setup-fix-verification';folder=q/'Final check Кириллица/Cloud Engine';folder.mkdir(parents=True,exist_ok=True)
project=folder/'Моя игра.scene';project.write_text('preserve user project',encoding='utf-8')
blocked=q/'blocked-temp';blocked.write_text('not a directory')
env=os.environ.copy();env.update(TEMP=str(blocked),TMP=str(blocked),LOCALAPPDATA=str(q/'Runtime'),QT_QPA_PLATFORM='offscreen',SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
def run(args):
    p=subprocess.run(list(map(str,args)),env=env,timeout=90);print('exit',p.returncode,flush=True);assert p.returncode==0
run([q/'CloudEngine-Installer-Verification.exe','/SP-','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=desktopicon','/DIR='+str(folder),'/LOG='+str(q/'final-install.log')])
engine=folder/'CloudEngine.exe';source=r/'releases/Current/CloudEngine.exe'
result={'invalid_temp_install':True,'integrity':hashlib.sha256(engine.read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest(),'desktop_shortcut':(folder/'Verification Desktop/Cloud Engine 1.2.0-beta.5.lnk').is_file(),'start_shortcut':(folder/'Verification Start Menu/Cloud Engine 1.2.0-beta.5.lnk').is_file()}
run([engine,'--smoke-test',q/'final-engine.json'])
result['engine_checks']=all(json.loads((q/'final-engine.json').read_text(encoding='utf-8')).values())
env['TEMP']=env['TMP']=str(r/'build/creation-temp')
run([folder/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(q/'final-uninstall.log')])
for _ in range(30):
    if not engine.exists():break
    time.sleep(.2)
result['removed_engine']=not engine.exists();result['preserved_project']=project.exists()
(q/'final-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result,flush=True);assert all(result.values())
