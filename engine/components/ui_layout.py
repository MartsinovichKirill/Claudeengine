"""Resolution-independent screen rectangles for UI elements."""
from engine.components.component import Component
from engine.math.vector2 import Vector2


class RectTransform(Component):
    type_name = 'RectTransform'
    description = 'UI-прямоугольник: привязки, отступы, размер и опорная точка'
    allow_multiple = False
    exported_properties = {
        'anchor_min': {'type':'vector2','default':[0,0]},
        'anchor_max': {'type':'vector2','default':[0,0]},
        'offset': {'type':'vector2','default':[0,0]},
        'size_delta': {'type':'vector2','default':[160,48]},
        'pivot': {'type':'vector2','default':[0,0]},
    }
    def __init__(self):
        super().__init__()
        self.anchor_min=Vector2(); self.anchor_max=Vector2(); self.offset=Vector2()
        self.size_delta=Vector2(160,48); self.pivot=Vector2()
    def resolve(self, screen_size):
        parent_position=Vector2(); parent_size=Vector2(screen_size)
        parent=getattr(self.owner,'parent',None)
        parent_rect=parent.get_component('RectTransform') if parent else None
        if parent_rect and parent_rect.enabled:
            parent_position,parent_size=parent_rect.resolve(screen_size)
        size=Vector2(max(0,parent_size.x*(self.anchor_max.x-self.anchor_min.x)+self.size_delta.x),
                     max(0,parent_size.y*(self.anchor_max.y-self.anchor_min.y)+self.size_delta.y))
        position=parent_position+Vector2(parent_size.x*self.anchor_min.x,parent_size.y*self.anchor_min.y)+self.offset-Vector2(size.x*self.pivot.x,size.y*self.pivot.y)
        return position,size


class HorizontalLayout(Component):
    type_name='HorizontalLayout'
    allow_multiple=False
    exported_properties={'spacing':{'type':'float','default':8.0,'min':0.0},'padding':{'type':'vector2','default':[12,12]},'auto_size':{'type':'bool','default':True}}
    vertical=False
    def __init__(self):
        super().__init__();self.spacing=8.0;self.padding=Vector2(12,12);self.auto_size=True
    def arrange(self,screen_size):
        owner=self.owner
        transform=owner.get_component('RectTransform')
        if transform is None:
            transform=owner.add_component('RectTransform');transform.size_delta=Vector2(screen_size)
        position,size=transform.resolve(screen_size)
        cursor=self.padding.y if self.vertical else self.padding.x
        cross=0
        for child in owner.get_children():
            if not getattr(child,'visible',True):continue
            rect=child.get_component('RectTransform')
            if rect is None:rect=child.add_component('RectTransform');rect.size_delta=Vector2(getattr(child,'size',Vector2(160,48)))
            rect.anchor_min=Vector2();rect.anchor_max=Vector2();rect.pivot=Vector2()
            rect.offset=Vector2(self.padding.x,cursor) if self.vertical else Vector2(cursor,self.padding.y)
            cursor+=(rect.size_delta.y if self.vertical else rect.size_delta.x)+self.spacing
            cross=max(cross,rect.size_delta.x if self.vertical else rect.size_delta.y)
        if self.auto_size:
            length=max(0,cursor-self.spacing)
            transform.size_delta=Vector2(cross+self.padding.x*2,length+self.padding.y) if self.vertical else Vector2(length+self.padding.x,cross+self.padding.y*2)

class VerticalLayout(HorizontalLayout):
    type_name='VerticalLayout'
    vertical=True

def arrange_tree(root,screen_size):
    for component in root.components:
        if isinstance(component,HorizontalLayout) and component.enabled:component.arrange(screen_size)
    for child in root.get_children():arrange_tree(child,screen_size)
