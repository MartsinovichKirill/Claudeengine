"""Collision geometry inspection in editor and Play, without changing physics."""
from engine.math.vector2 import Vector2


def draw_collisions(surface, scene, camera):
    if surface is None or scene is None:
        return
    import pygame
    if not pygame.font.get_init():
        pygame.font.init()
    font=pygame.font.Font(None,18)
    def screen(point):
        return camera.world_to_screen(point) if camera else Vector2(point)
    for node in scene.get_nodes():
        getter=getattr(node,'get_collision_shapes',None)
        if not callable(getter):
            continue
        shapes=getter()
        rigid=node.get_component('Rigidbody2D')
        layer=getattr(rigid or node,'collision_layer',1)
        mask=getattr(rigid or node,'collision_mask',1)
        color=(100,220,165) if rigid and rigid.enabled else (100,185,245)
        for shape in shapes:
            transform=shape.get_global_transform()
            if shape.shape_type=='circle':
                center=screen(shape.get_global_position())
                zoom=getattr(camera,'zoom',1.0)
                radius=shape.radius*max(abs(transform.scale.x),abs(transform.scale.y))*abs(zoom)
                pygame.draw.circle(surface,color,center.as_ints(),max(1,round(radius)),2)
            else:
                points=[screen(p).as_ints() for p in shape.get_world_vertices()]
                if len(points)>=3:
                    pygame.draw.polygon(surface,color,points,2)
            center=screen(shape.get_global_position())
            pygame.draw.line(surface,color,(center.x-4,center.y),(center.x+4,center.y),1)
            pygame.draw.line(surface,color,(center.x,center.y-4),(center.x,center.y+4),1)
        if shapes:
            position=screen(node.get_global_position())
            label=font.render(f'{node.name}  layer:{layer} mask:{mask}',True,color)
            surface.blit(label,(position.x+8,position.y+8))
