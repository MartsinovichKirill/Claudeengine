import os,subprocess,json,time,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[1];q=r/'build/qt-fix3-installed-test';q.mkdir(exist_ok=True);target=q/'Cloud Engine'
blocked=q/'blocked-temp';blocked.write_text('not a temp directory')
env=os.environ.copy();env.update(TEMP=str(blocked),TMP=str(blocked),LOCALAPPDATA=str(q/'Settings'),QT_QPA_PLATFORM='external-broken-platform',QT_PLUGIN_PATH='C:/missing-qt',QT_QPA_PLATFORM_PLUGIN_PATH='C:/missing-platforms',SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
setup=r/'build/qt-fix3-final-package/CloudEngine-1.2.0-beta.6-Setup-Fix3.exe'
def run(args,timeout=120):
    result=subprocess.run(list(map(str,args)),env=env,timeout=timeout);print('exit',result.returncode,flush=True);assert result.returncode==0
run([setup,'/SP-','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=startmenuicon','/DIR='+str(target),'/LOG='+str(q/'install.log')])
engine=target/'CloudEngine.exe';source=r/'build/qt-fix3-final-editor/CloudEngine.exe';assert hashlib.sha256(engine.read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest()
run([engine,'--window-check',q/'window.json'])
window=json.loads((q/'window.json').read_text(encoding='utf-8'));assert window['platform']=='windows' and window['window_visible'] and window['fonts_available']
run([engine,'--smoke-test',q/'engine.json'],180)
checks=json.loads((q/'engine.json').read_text(encoding='utf-8'));assert all(checks.values()),checks
project=target/'My project.scene';project.write_text('preserve user project')
env['TEMP']=env['TMP']=str(r/'build/creation-temp')
run([target/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'])
for _ in range(30):
    if not engine.exists():break
    time.sleep(.2)
report={'installation':True,'actual_windows_platform':window['platform'],'visible_window':window['window_visible'],'foreign_environment_ignored':True,'engine_checks':len(checks),'engine_passed':all(checks.values()),'uninstall':not engine.exists(),'project_preserved':project.exists()}
(q/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report,flush=True);assert report['uninstall'] and report['project_preserved']
