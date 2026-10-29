"""Build-selected UI flavor, overridable for source-based previews."""
import json
import sys
from pathlib import Path


def flavor():
    if '--interface' in sys.argv:
        index=sys.argv.index('--interface')
        if index+1<len(sys.argv) and sys.argv[index+1] in ('modern','classic'): return sys.argv[index+1]
    if getattr(sys,'frozen',False):
        path=Path(getattr(sys,'_MEIPASS',Path(sys.executable).parent))/'ui-profile.json'
        try:
            value=json.loads(path.read_text(encoding='utf-8'))['interface']
            if value in ('modern','classic'): return value
        except (OSError,ValueError,KeyError): pass
    return 'modern'


def defaults():
    classic=flavor()=='classic'
    return {'palette':'midnight','accent':'#88aef5','font_family':'Segoe UI','font_size':13,
            'density':'comfortable','icon_size':20,'radius':6,'group_menus':True,'menu_layout_version':1,
            'toolbar_labels':False,'toolbar_groups':{'history':True,'scene':True,'play':True,'view':True,'project':True}}
