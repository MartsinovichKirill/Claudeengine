"""Saved-project checks with bounded child-process runs and JSON reports."""
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback


def project_files(root,suffix):
    return sorted(path for path in root.rglob('*'+suffix) if path.is_file() and not path.is_symlink()
                  and not any(part.startswith('.') or part in ('build','builds','dist','venv','node_modules','__pycache__') for part in path.relative_to(root).parts))


def validate_project(project_dir,scenes=None):
    """Read saved files; scripts are compiled but never executed at this stage."""
    from engine.resources.game_data import validate_document,project_path
    from engine.components.enemy_ai import validate_graph
    from engine.resources.scene_serializer import SceneSerializer
    from engine.systems.cloud_scripts import compile_cloud
    root=Path(project_dir).resolve(); results=[]
    def issue(path,error):
        results.append({'stage':'validation','status':'failed','path':str(path),'line':getattr(error,'lineno',1) or 1,'message':str(error)})
    try:
        settings=json.loads((root/'project.json').read_text(encoding='utf-8-sig'))
        start=project_path(root,settings.get('main_scene',''))
        if not start.is_file() or start.suffix!='.scene': raise ValueError('Не выбрана существующая стартовая сцена')
    except (OSError,ValueError,TypeError) as error: issue(root/'project.json',error)
    for path in [*project_files(root,'.gamedata'),*project_files(root,'.behavior')]:
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if path.suffix=='.gamedata': validate_document(data,root,True)
            else: validate_graph(data['graph'])
        except (OSError,ValueError,TypeError,KeyError) as error: issue(path,error)
    for path in [*project_files(root/'.'/'scripts','.cloud'),*project_files(root/'scripts','.py')]:
        try:
            source=path.read_text(encoding='utf-8-sig')
            compile_cloud(source,str(path)) if path.suffix=='.cloud' else compile(source,str(path),'exec')
        except (OSError,ValueError,SyntaxError) as error: issue(path,error)
    selected=[project_path(root,path) for path in scenes] if scenes is not None else project_files(root,'.scene')
    for path in selected:
        try:
            raw=json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(raw.get('scene',{}).get('root'),dict): raise ValueError('В сцене нет корневого объекта')
            # Validate serialized component data before permissive legacy loading.
            def check(node):
                for component in node.get('components',[]):
                    if component.get('type')=='EnemyAI': validate_graph(component.get('data',{}).get('graph',{}))
                for child in node.get('children',[]): check(child)
            check(raw['scene']['root'])
            scene=SceneSerializer.load_scene(str(path))
            # Shared read-only rules are in the engine; importing does not load Qt.
            from engine.testing.scene_validation import validate_scene
            for problem in validate_scene(scene,str(root)):
                results.append({'stage':'validation','status':'failed','path':str(path),'resource':problem.path,'line':problem.line,'node':getattr(problem.node,'name',''),'message':problem.message})
        except (OSError,ValueError,TypeError,KeyError) as error: issue(path,error)
    return results


class ErrorCapture(logging.Handler):
    def __init__(self): super().__init__(logging.ERROR); self.errors=[]
    def emit(self,record):
        if len(self.errors)<30:
            self.errors.append(self.format(record))


def run_scene(project,scene_path,frames=120):
    """Run a private copy using the actual game systems and fixed simulation time."""
    os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from engine.core.scene import Scene
    from engine.core.scene_tree import SceneTree
    from engine.core.game_loop import GameLoop
    from engine.core.time import Time
    from engine.resources.asset_manager import AssetManager
    from engine.systems.script_system import ScriptSystem
    from engine.systems.render_system import RenderSystem
    from engine.systems.physics_system import PhysicsSystem
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.animation_system import AnimationSystem
    from engine.systems.audio_system import AudioSystem
    from engine.systems.particle_system import ParticleSystem
    from engine.systems.ui_system import UISystem
    from engine.systems.light_system import LightSystem
    from engine.systems.post_process import PostProcessSystem
    root=Path(project).resolve(); settings=json.loads((root/'project.json').read_text(encoding='utf-8-sig'))
    capture=ErrorCapture(); logger=logging.getLogger(); logger.addHandler(capture)
    tree=None; entered=False; audio=None; executed=0; started=time.monotonic()
    try:
        pygame.init(); screen=pygame.display.set_mode((640,360))
        scripts=ScriptSystem(str(root)); scripts.reload()
        if scripts.errors: raise ValueError('Ошибки загрузки скриптов: '+repr(scripts.errors))
        assets=AssetManager(str(root)); tree=SceneTree(settings); render=RenderSystem(tree,assets)
        audio=AudioSystem(tree); audio.init_mixer(); loop=GameLoop(tree,settings,screen)
        loop.attach_systems(physics=PhysicsSystem(tree),collision=CollisionSystem(tree),render=render,
            animation=AnimationSystem(tree),audio=audio,particle=ParticleSystem(tree),ui=UISystem(tree),script=scripts,
            light=LightSystem(tree),post_process=PostProcessSystem(tree))
        scene=Scene.load(str(root/scene_path),scripts)
        render.prepare_scene(scene); entered=True; tree.change_scene(scene); render.bind_assets(); loop.start()
        for _ in range(max(1,min(3600,int(frames)))):
            Time.delta=1/60; Time.time+=1/60; Time.frame_count+=1
            loop._frame(1/60); executed+=1
            if capture.errors: break
        loop.stop()
    except Exception as error:
        capture.errors.append(''.join(traceback.format_exception(type(error),error,error.__traceback__)))
    finally:
        try:
            if tree and entered and tree.current_scene: tree._exit_scene(tree.current_scene)
        except Exception: capture.errors.append(traceback.format_exc())
        pygame.quit(); logger.removeHandler(capture)
    return {'stage':'runtime','path':str(scene_path),'status':'failed' if capture.errors else 'passed',
            'frames':executed,'seconds':round(time.monotonic()-started,3),'errors':capture.errors,
            'message':capture.errors[0] if capture.errors else 'Запуск и завершение сцены без зарегистрированных ошибок'}


def worker(config_path):
    config=json.loads(Path(config_path).read_text(encoding='utf-8'))
    result=run_scene(config['project'],config['scene'],config.get('frames',120))
    Path(config['result']).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['status']=='passed' else 1


class ProjectCheckRunner:
    def __init__(self,project_dir,report_path,scenes=None,frames=120,timeout=15):
        self.root=Path(project_dir).resolve(); self.report_path=Path(report_path).resolve()
        self.scenes=scenes; self.frames=max(1,min(3600,int(frames))); self.timeout=max(1,min(120,float(timeout)))
        self.cancelled=threading.Event(); self.process=None

    def cancel(self):
        self.cancelled.set()
        process=self.process
        if process and process.poll() is None:
            try: process.terminate()
            except OSError: pass

    def run(self,progress=None):
        self.report_path.parent.mkdir(parents=True,exist_ok=True)
        records=validate_project(self.root,self.scenes)
        scenes=self.scenes if self.scenes is not None else [path.relative_to(self.root).as_posix() for path in project_files(self.root,'.scene')]
        for record in records:
            if progress: progress(record)
        if not scenes:
            record={'stage':'validation','path':'','status':'failed','message':'Нет выбранных сцен для проверки'}; records.append(record)
            if progress: progress(record)
        if not records:
            # Copies are disposable: normal save calls from game scripts cannot alter source scenes.
            with tempfile.TemporaryDirectory(prefix='.cloud-check-',dir=self.report_path.parent) as temporary:
                workspace=Path(temporary)
                for index,scene in enumerate(scenes):
                    if self.cancelled.is_set(): break
                    if progress: progress({'stage':'running','status':'running','path':scene,'message':'Запуск сцены…'})
                    copy_root=workspace/str(index)
                    def ignore(folder,names): return [name for name in names if name.startswith('.') or name in ('build','builds','dist','venv','node_modules','__pycache__') or Path(folder,name).is_symlink()]
                    shutil.copytree(self.root,copy_root,ignore=ignore)
                    result_path=workspace/f'result-{index}.json'; config_path=workspace/f'config-{index}.json'
                    config_path.write_text(json.dumps({'project':str(copy_root),'scene':str(scene),'frames':self.frames,'result':str(result_path)},ensure_ascii=False),encoding='utf-8')
                    command=[sys.executable]
                    if not getattr(sys,'frozen',False): command.append(str(Path(__file__).resolve().parents[2]/'main.py'))
                    command+=['--test-scene',str(config_path)]
                    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',PYTHONIOENCODING='utf-8')
                    kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
                    self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,**kwargs)
                    try:
                        output,_=self.process.communicate(timeout=self.timeout)
                        if self.cancelled.is_set(): break
                        if result_path.is_file():
                            record=json.loads(result_path.read_text(encoding='utf-8'))
                            for key in ('message',): record[key]=record.get(key,'').replace(str(copy_root),str(self.root))
                            record['errors']=[text.replace(str(copy_root),str(self.root)) for text in record.get('errors',[])]
                        else: record={'stage':'runtime','status':'failed','path':scene,'message':'Проверочный процесс завершился без отчёта','errors':[output.decode('utf-8',errors='replace')[-6000:]]}
                    except subprocess.TimeoutExpired:
                        self.process.kill(); self.process.communicate()
                        record={'stage':'runtime','status':'timeout','path':scene,'message':f'Сцена не завершила проверку за {self.timeout:g} с'}
                    finally: self.process=None
                    record['path']=str(scene)
                    records.append(record)
                    if progress: progress(record)
        report={'version':1,'project':str(self.root),'created':time.strftime('%Y-%m-%d %H:%M:%S'),
                'frames_per_scene':self.frames,'cancelled':self.cancelled.is_set(),'results':records,
                'passed':bool(records) and not self.cancelled.is_set() and all(record['status']=='passed' for record in records)}
        self.report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        lines=['# Проверка проекта',f'Проект: {self.root}',f'Результат: {"ПРОЙДЕНО" if report["passed"] else "НЕ ПРОЙДЕНО"}',
               'Проверяются сохранённые сцены, ресурсы и короткий запуск без ввода игрока. Проходимость и баланс не оцениваются.','']
        lines += [f'- {record["status"]} · {record.get("path", "")} · {record["message"]}' for record in records]
        self.report_path.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')
        return report
