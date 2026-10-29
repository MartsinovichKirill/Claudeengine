import os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path('CloudEngine').resolve()))
os.environ['SDL_VIDEODRIVER']='dummy'
import pygame
pygame.init();pygame.display.set_mode((1,1))
from engine.systems.csharp_system import load_csharp
with tempfile.TemporaryDirectory(dir='C:/Cloud') as d:
    source=Path(d,'Spinner.cs')
    source.write_text('using CloudEngine; public class Spinner : CloudBehaviour { public override void Ready() { X=12; } public override void Process(double delta) { Rotation += 90*delta; } }')
    node=load_csharp(source)();node._ready();node._process(.5)
    assert node.position.x==12 and node.rotation==45
    node._exit_tree()
    from engine.systems.shader_system import apply_shader
    shader=Path(d,'test.shader');shader.write_text('def fragment(rgb,uv,time):\n    return rgb * [0,1,0]\n')
    surface=pygame.Surface((8,8));surface.fill('white');apply_shader(surface,shader)
    assert tuple(surface.get_at((0,0)))[:3]==(0,255,0)
    from editor.project_hub import create_project
    project=create_project(d,'Platform','Платформер')
    assert Path(project,'assets/player.png').is_file()
    from engine.systems.script_system import ScriptSystem
    scripts=ScriptSystem(project);assert scripts.reload()>=1
    from engine.resources.scene_serializer import SceneSerializer
    scene=SceneSerializer.load_scene(str(Path(project,'scenes/main.scene')),scripts)
    from engine.systems.render_system import RenderSystem
    class Tree: current_scene=scene
    from engine.resources.asset_manager import AssetManager
    renderer=RenderSystem(Tree(),AssetManager(project));renderer.prepare_scene(scene)
    renderer.render(pygame.Surface((1024,600)))
    class Counter(__import__('engine.nodes.node2d',fromlist=['Node2D']).Node2D):
        def __init__(self,name):super().__init__(name);self.count=0
        def _draw_local(self,surface,center,camera):self.count+=1
    from engine.core.scene import Scene
    root=Counter('root');child=Counter('child');root.add_child(child);Tree.current_scene=Scene('Test',root)
    renderer=RenderSystem(Tree());renderer.render(pygame.Surface((32,32)))
    assert root.count==child.count==1
    root.visible=False;renderer.render(pygame.Surface((32,32)));assert child.count==1
print('PASS: C# compilation and callbacks, shader, platformer assets/scene, single draw, hidden parent')
