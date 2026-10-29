"""Isolate the frozen editor's Qt from other applications installed on Windows."""
import os
import sys
from pathlib import Path

_dll_directories=[]


def configure():
    if not getattr(sys,'frozen',False) or sys.platform!='win32':return None
    bundle=Path(sys._MEIPASS)
    qt=bundle/'PyQt6/Qt6'
    if not qt.is_dir():qt=bundle/'PyQt6/Qt'
    plugins=qt/'plugins'
    headless=any(flag in sys.argv for flag in ('--smoke-test','--runtime-check','--test-scene')) and os.environ.get('QT_QPA_PLATFORM') in ('offscreen','minimal')
    for name in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_PLATFORMTHEME','QT_STYLE_OVERRIDE',
                 'QT_QPA_GENERIC_PLUGINS','QML_IMPORT_PATH','QML2_IMPORT_PATH'):
        os.environ.pop(name,None)
    os.environ['QT_PLUGIN_PATH']=str(plugins)
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH']=str(plugins/'platforms')
    if not headless:os.environ['QT_QPA_PLATFORM']='windows'
    os.environ['QT_OPENGL']='software'
    os.environ['QT_QUICK_BACKEND']='software'
    windows=Path(os.environ.get('SystemRoot',os.environ.get('WINDIR','C:/Windows')))
    paths=[qt/'bin',bundle,windows/'System32',windows]
    os.environ.setdefault('CLOUDENGINE_ORIGINAL_PATH',os.environ.get('PATH',''))
    os.environ['PATH']=os.pathsep.join(str(path) for path in paths)
    if hasattr(os,'add_dll_directory'):
        for path in paths[:2]:
            if path.is_dir():_dll_directories.append(os.add_dll_directory(str(path)))
    return plugins/'platforms/qwindows.dll'


def verify_windows_plugin():
    if not getattr(sys,'frozen',False) or sys.platform!='win32' or os.environ.get('QT_QPA_PLATFORM')!='windows':return
    import ctypes
    plugin=Path(os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'])/'qwindows.dll'
    if not plugin.is_file():raise RuntimeError('Не найден Windows-плагин Qt: '+str(plugin))
    try:ctypes.WinDLL(str(plugin),winmode=0x00000100|0x00001000)
    except OSError as error:raise RuntimeError('Windows не смог загрузить qwindows.dll или его зависимости: '+str(error)+'\nПлагин: '+str(plugin)) from error
