"""One-time preparation: exact supplied sheets, shared crop and unchanged pixels."""
import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent/'player_controller'
assets = ROOT/'assets'
assets.mkdir(parents=True, exist_ok=True)
clips = {}
for name, count, fps, loop in [('idle',10,7,True),('walk',10,10,True),('run',10,16,True),('jump',6,10,False)]:
    source = Path(r'C:\Users\Matvey\AppData\Local\Temp')/f'male_hero_template-{name}.png'
    target = assets/'originals'; target.mkdir(exist_ok=True)
    shutil.copy2(source, target/source.name)
    sheet = Image.open(source).convert('RGBA')
    assert sheet.size == (count*128,128)
    folder = assets/name; folder.mkdir(exist_ok=True)
    frames = []
    for index in range(count):
        # All animations share a fixed pivot and baseline. Never trim each frame independently.
        frame = sheet.crop((index*128+40,24,index*128+88,88))
        assert frame.getbbox()
        filename = f'{name}_{index:02}.png'; frame.save(folder/filename)
        frames.append(f'assets/templates/@TEMPLATE@/{name}/{filename}')
    clips[name.title()] = {'frames':frames,'fps':fps,'loop':loop}

im = Image.new('RGBA',(64,64),(37,49,62,255)); d=ImageDraw.Draw(im)
d.rectangle((0,0,63,5),fill=(103,160,163,255));d.line((0,7,63,7),fill=(64,100,110,255),width=2)
im.save(assets/'ground.png')
for filename,color,peaks in [('far.png',(29,43,69,255),[220,100,190,40,210,130,240]),('near.png',(38,66,87,255),[300,200,340,160,270,210,320])]:
    im=Image.new('RGBA',(1024,720));d=ImageDraw.Draw(im)
    points=[(0,720)]+[(i*171,y) for i,y in enumerate(peaks)]+[(1024,720)]
    d.polygon(points,fill=color);im.save(assets/filename)

def node(kind,name,props=None,children=None,**extras):
    return dict(type=kind,name=name,properties=props or {},children=children or [],**extras)
base='assets/templates/@TEMPLATE@/'
visual=node('AnimatedSprite2D','Visual',{'position':[0,-27],'scale':[3,3], 'animation':'Idle', 'playing':True},data={'animations':clips})
player=node('CharacterBody2D','Player',{'position':[180,435]},[
    node('CollisionShape2D','Collider',{'size':[42,90]}),visual],script='scripts/templates/@TEMPLATE@.cloud')
def platform(name,x,y,w,h):
    return node('StaticBody2D',name,{'position':[x,y]},[
        node('CollisionShape2D','Collider',{'size':[w,h]}),
        node('Sprite2D','Surface',{'texture_path':base+'ground.png','scale':[w/64,h/64]})])
root=node('Node2D','PlayerDemo',children=[
    node('Parallax2D','FarBackground',{'scroll_scale':[.15,.08], 'repeat_size':[1024,0], 'z_index':-20},[
        node('Sprite2D','Mountains',{'texture_path':base+'far.png', 'position':[512,180]})]),
    node('Parallax2D','NearBackground',{'scroll_scale':[.4,.15], 'repeat_size':[1024,0], 'z_index':-10},[
        node('Sprite2D','Hills',{'texture_path':base+'near.png','position':[512,260]})]),
    platform('Ground',1500,550,4200,140),
    platform('Step1',650,410,180,36),platform('Step2',1000,335,180,36),platform('Step3',1350,260,220,36),
    platform('Landing',1780,390,300,36), player,
    node('Camera2D','Camera',{'position':[180,335],'target_path':'Player','position_smoothing':6, 'look_ahead':65,'offset':[0,-100]}),
    node('CanvasLayer','HUD',{'layer':5,'offset':[24,20]},[
        node('Label','Title',{'text':'Контроллер игрока 2D','font_size':24,'position':[0,0]}),
        node('Label','Controls',{'text':'A / D — ходьба   Shift — бег   Пробел — прыжок   R — на старт','font_size':18,'position':[0,38]})])])
(ROOT/'scene.json').write_text(json.dumps({'scene':{'name':'Player Controller','root':root}},ensure_ascii=False,indent=2),encoding='utf-8')
print('Prepared 36 frames, four clips and demo scene')
