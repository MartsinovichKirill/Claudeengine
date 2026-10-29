import json,os,shutil,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[1];q=r/'build/qt-fix3-final-windows-test';q.mkdir(exist_ok=True)
exe=r/'build/qt-fix3-final-editor/CloudEngine.exe';foreign=q/'foreign-qt';foreign.mkdir(exist_ok=True)
for name in ('Qt6Core.dll','Qt6Gui.dll','qwindows.dll'):(foreign/name).write_bytes(b'not a compatible Qt DLL')
reports=[]
for case in ('normal','foreign-environment','unicode-path'):
    env=os.environ.copy()
    for key in list(env):
        if key.startswith(('QT_','QML')):env.pop(key,None)
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',LOCALAPPDATA=str(q/'Settings'),TEMP=str(r/'build/creation-temp'),TMP=str(r/'build/creation-temp'))
    program=exe;cwd=q
    if case!='normal':
        env.update(QT_QPA_PLATFORM='broken-external-backend',QT_PLUGIN_PATH=str(foreign),QT_QPA_PLATFORM_PLUGIN_PATH=str(foreign),QT_STYLE_OVERRIDE='missing-style',QML2_IMPORT_PATH=str(foreign),PATH=str(foreign)+';'+env.get('PATH',''))
        cwd=foreign
    if case=='unicode-path':
        folder=q/'Проверка запуска с пробелами';folder.mkdir(exist_ok=True);program=folder/'CloudEngine.exe';shutil.copy2(exe,program)
    report=q/(case+'.json')
    p=subprocess.run([str(program),'--window-check',str(report)],env=env,cwd=cwd,timeout=90)
    print(case,'exit',p.returncode,flush=True);assert p.returncode==0 and report.is_file()
    data=json.loads(report.read_text(encoding='utf-8'));print(data,flush=True)
    assert data['platform']=='windows' and data['window_visible'] and data['fonts_available']
    reports.append({'case':case,**data})
(q/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS: native Windows Qt in all three environments',flush=True)
