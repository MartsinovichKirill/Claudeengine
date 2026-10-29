import os,subprocess,json,hashlib,time
from pathlib import Path
r=Path(__file__).resolve().parents[1];q=r/'build/installer-fix2-test';q.mkdir(exist_ok=True)
blocked=q/'blocked-temp';blocked.write_text('not a temporary directory')
env=os.environ.copy();env.update(TEMP=str(blocked),TMP=str(blocked),LOCALAPPDATA=str(q/'Runtime'),QT_QPA_PLATFORM='offscreen',SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
source=r/'releases/Current/CloudEngine.exe';reports=[]
for case in ('normal','blocked-shell','shortcut-collision','no-shortcuts'):
    target=q/('Install '+case);target.mkdir(exist_ok=True)
    userfile=target/'User project.scene';userfile.write_text('keep user data')
    if case=='blocked-shell':(target/'BlockedShell').write_text('folder is denied')
    if case=='shortcut-collision':
        collision=target/'Verification Start Menu/Cloud Engine 1.2.0-beta.6.lnk';collision.mkdir(parents=True,exist_ok=True)
    tasks='/TASKS=' if case=='no-shortcuts' else '/TASKS=desktopicon,startmenuicon'
    args=[str(q/'CloudEngine-Installer-Verification.exe'),'/SP-','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',tasks,'/DIR='+str(target),'/LOG='+str(q/(case+'.log'))]
    if case=='blocked-shell':args.append('/CloudTestBlockedShell=1')
    result=subprocess.run(args,env=env,timeout=90);print(case,'setup exit',result.returncode,flush=True);assert result.returncode==0
    exe=target/'CloudEngine.exe';assert hashlib.sha256(exe.read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest()
    summary=(target/'InstallationReport.txt').read_text(encoding='utf-8-sig')
    assert (target/'Cloud Engine 1.2.0-beta.6.lnk').is_file()
    if case=='blocked-shell':assert 'Desktop shortcut: 0' in summary and 'Start Menu shortcut: 0' in summary
    if case=='shortcut-collision':assert 'Start Menu shortcut: 0' in summary
    if case=='no-shortcuts':
        assert not (target/'Verification Desktop/Cloud Engine 1.2.0-beta.6.lnk').exists()
        assert not (target/'Verification Start Menu/Cloud Engine 1.2.0-beta.6.lnk').exists()
    if case=='normal':
        assert (target/'Verification Desktop/Cloud Engine 1.2.0-beta.6.lnk').is_file()
        assert (target/'Verification Start Menu/Cloud Engine 1.2.0-beta.6.lnk').is_file()
        result=subprocess.run([str(exe),'--smoke-test',str(q/'engine-report.json')],env=env,timeout=90);assert result.returncode==0
        checks=json.loads((q/'engine-report.json').read_text(encoding='utf-8'));assert all(checks.values())
    uninstall_env=env.copy();uninstall_env['TEMP']=uninstall_env['TMP']=str(r/'build/creation-temp')
    result=subprocess.run([str(target/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(q/(case+'-uninstall.log'))],env=uninstall_env,timeout=90);assert result.returncode==0
    for _ in range(30):
        if not exe.exists():break
        time.sleep(.2)
    assert not exe.exists() and userfile.exists()
    reports.append({'case':case,'install':True,'local_shortcut':True,'uninstall':True,'user_project_preserved':True,'summary':summary})
(q/'matrix-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS: all four installation scenarios and editor checks',flush=True)
