import os,subprocess,json,hashlib,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];q=r/'build/beta6-final-install-test';q.mkdir(exist_ok=True)
blocked_temp=q/'blocked-temp';blocked_temp.write_text('not a directory')
blocked_target=q/'unwritable-target';blocked_target.write_text('not a directory')
folder=q/'Fallback Installation';folder.mkdir(exist_ok=True)
project=folder/'Мой проект.scene';project.write_text('preserve user project',encoding='utf-8')
env=os.environ.copy();env.update(TEMP=str(blocked_temp),TMP=str(blocked_temp),LOCALAPPDATA=str(q/'Runtime'),QT_QPA_PLATFORM='offscreen',SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
def run(args):
    p=subprocess.run(list(map(str,args)),env=env,timeout=90);print('exit',p.returncode,flush=True);assert p.returncode==0
run([q/'CloudEngine-Installer-Verification.exe','/SP-','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=desktopicon','/DIR='+str(blocked_target),'/LOG='+str(q/'installation.log')])
engine=folder/'CloudEngine.exe';source=r/'build/beta6-final-release/CloudEngine.exe'
result={'invalid_temp_install':True,'invalid_target_fallback':engine.is_file(),'integrity':hashlib.sha256(engine.read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest(),'desktop_shortcut':(folder/'Verification Desktop/Cloud Engine 1.2.0-beta.6.lnk').is_file(),'start_shortcut':(folder/'Verification Start Menu/Cloud Engine 1.2.0-beta.6.lnk').is_file()}
run([engine,'--smoke-test',q/'engine-report.json'])
checks=json.loads((q/'engine-report.json').read_text(encoding='utf-8'));result['engine_checks']=all(checks.values());result['engine_check_count']=len(checks)
env['TEMP']=env['TMP']=str(r/'build/creation-temp')
run([folder/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(q/'uninstall.log')])
for _ in range(30):
    if not engine.exists():break
    time.sleep(.2)
result['removed_engine']=not engine.exists();result['preserved_project']=project.exists()
(q/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result,flush=True);assert all(result.values())
