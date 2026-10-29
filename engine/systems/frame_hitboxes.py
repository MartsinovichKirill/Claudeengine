"""Frame-based attack/hurt polygons. No automatic HP policy or physics bodies."""
import math
from engine.math.vector2 import Vector2


def validate_boxes(boxes):
    if not isinstance(boxes, dict): raise ValueError('hitboxes должен быть словарём кадров')
    for frame, items in boxes.items():
        if not str(frame).isdigit() or not isinstance(items, list): raise ValueError('Некорректный кадр хитбоксов')
        ids = set()
        for box in items:
            if box.get('kind') not in ('hit', 'hurt'): raise ValueError('Тип области: hit или hurt')
            ident = box.get('id', '')
            if not ident or ident in ids: raise ValueError('ID областей должны быть уникальны в кадре')
            ids.add(ident)
            rect = box.get('rect', [])
            if len(rect) != 4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in rect) or min(rect[2:]) <= 0:
                raise ValueError('Область должна иметь конечные координаты и положительный размер')
            for key in ('layer','mask'):
                value=box.get(key,1)
                if not isinstance(value,int) or value < 0: raise ValueError('Слой и маска должны быть неотрицательными целыми')
    return boxes


def active_boxes(sprite):
    spec = sprite.animations.get(sprite.animation, {})
    if not sprite.frames: return []
    width,height=sprite.frames[max(0,min(sprite.frame,len(sprite.frames)-1))].get_size()
    transform = sprite.get_global_transform()
    result=[]
    for box in spec.get('hitboxes',{}).get(str(sprite.frame),[]):
        if not box.get('enabled',True):continue
        x,y,w,h=box['rect'];points=[]
        for px,py in ((x,y),(x+w,y),(x+w,y+h),(x,y+h)):
            if sprite.flip_h:px=width-px
            if sprite.flip_v:py=height-py
            point=Vector2(px-width/2 if sprite.centered else px,py-height/2 if sprite.centered else py)+sprite.offset
            points.append(transform.xform(point))
        result.append(dict(box,points=points))
    return result


def overlaps(a,b):
    # SAT, so rotation and negative scale do not create oversized AABB hits.
    for polygon in (a,b):
        for index,p in enumerate(polygon):
            edge=polygon[(index+1)%len(polygon)]-p
            axis=Vector2(-edge.y,edge.x)
            aa=[q.dot(axis) for q in a];bb=[q.dot(axis) for q in b]
            if max(aa)<=min(bb) or max(bb)<=min(aa):return False
    return True


def actor(sprite):
    from engine.nodes.rigidbody2d import PhysicsBody2D
    node=sprite
    while node is not None:
        if isinstance(node,PhysicsBody2D) or (hasattr(node,'get_component') and node.get_component('Rigidbody2D') is not None):return node
        node=node.get_parent()
    return sprite


class FrameHitboxSystem:
    def __init__(self, tree):
        self.tree=tree;self.contacts={};self.scene=None

    def update(self):
        from engine.nodes.animated_sprite import AnimatedSprite2D
        scene=self.tree.current_scene
        if scene is not self.scene:self.contacts.clear();self.scene=scene
        if scene is None:return
        sprites=[n for n in scene.get_nodes() if isinstance(n,AnimatedSprite2D) and not n._pending_free and self.visible(n)]
        boxes={n:active_boxes(n) for n in sprites}
        active=set()
        for source in sprites:
            for hit in boxes[source]:
                if hit['kind']!='hit':continue
                token=(source,source.animation,source._hitbox_cycle,hit['id'])
                active.add(token);seen=self.contacts.setdefault(token,set())
                for target in sprites:
                    if actor(source) is actor(target):continue
                    if actor(target) in seen:continue
                    for hurt in boxes[target]:
                        if hurt['kind']!='hurt' or not(hit.get('mask',1)&hurt.get('layer',1)):continue
                        if overlaps(hit['points'],hurt['points']):
                            seen.add(actor(target))
                            source.emit_signal('hitbox_entered',target,hit['id'],hurt['id'])
                            target.emit_signal('hurtbox_entered',source,hit['id'],hurt['id'])
                            break
        self.contacts={key:value for key,value in self.contacts.items() if key in active}

    @staticmethod
    def visible(node):
        while node is not None:
            if not getattr(node,'visible',True):return False
            node=node.get_parent()
        return True
