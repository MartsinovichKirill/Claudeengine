import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import unittest
import tempfile
from pathlib import Path
from engine.nodes.game_object import GameObject
from engine.components.registry import all_visible_components, create_component
from engine.components.component import Component
from engine.systems.cloud_scripts import CloudRuntime

class CatalogAudit(unittest.TestCase):
    def test_all_components_roundtrip_and_default_processing(self):
        import pygame
        pygame.init();pygame.display.set_mode((1,1))
        surface=pygame.Surface((256,256),pygame.SRCALPHA)
        for name in all_visible_components():
            with self.subTest(component=name):
                owner=GameObject();component=create_component(name)
                if getattr(component, 'requires_tilemap', False):
                    from engine.nodes.tilemap import TileMap
                    owner=TileMap()
                if name=='Transform':component=owner.transform
                else:owner.add_component(component)
                restored=Component.from_dict(component.to_dict())
                self.assertIsNotNone(restored)
                self.assertEqual(restored.get_type_name(),name)
                component._process(1/60);component._physics_process(1/60)
                if callable(getattr(component,'draw',None)):
                    component.draw(surface,owner.position,None)
        pygame.quit()
    def test_cloud_inheritance_and_resource_export(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build') as folder:
            Path(folder,'base.cloud').write_text('script Base extends Behaviour:\n    export strength: float = 2.0\n    let items = []\n',encoding='utf-8')
            Path(folder,'child.cloud').write_text('from base import Base\nscript Child extends Base:\n    export texture: resource = "assets/a.png"\n    async func task():\n        return 42\n',encoding='utf-8')
            cls=CloudRuntime(folder).load('child').Child
            a,b=cls(),cls();a.items.append(1)
            self.assertEqual(b.items,[])
            self.assertIn('strength',cls.get_exported_properties())
            self.assertEqual(cls.get_exported_properties()['texture']['type'],'resource')
            coroutine=a.task()
            with self.assertRaises(StopIteration) as done:
                coroutine.send(None)
            self.assertEqual(done.exception.value,42)
if __name__=='__main__':unittest.main()

