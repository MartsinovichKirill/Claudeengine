"""Attach a shared data file without copying its fields into the scene."""
from engine.components.component import Component


class DataSource(Component):
    type_name='DataSource'
    description='Общие игровые данные из файла .gamedata без копирования настроек'
    allow_multiple=False
    exported_properties={'data_path':{'type':'resource','default':''}}

    def __init__(self):
        super().__init__(); self.data_path=''; self._data=None; self._loaded_path=''

    def read(self,key,default=None):
        if not self.data_path: return default
        tree=self.get_tree()
        manager=getattr(self.owner,'_asset_manager',None)
        root=getattr(manager,'project_dir','') or getattr(getattr(tree,'script_system',None),'project_dir','')
        if not root: raise ValueError('DataSource: проект не определён')
        if self._data is None or self._loaded_path!=(root,self.data_path):
            from engine.resources.game_data import GameData
            self._data=GameData(self.data_path,root); self._loaded_path=(root,self.data_path)
        return self._data.get(key,default)
