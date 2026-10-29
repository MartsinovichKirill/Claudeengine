"""Cloud Engine — точка входа.

Запуск:
    python main.py                     # открыть редактор
    python main.py --build             # собрать CloudEngine.exe (PyInstaller)
    python main.py --project <папка>   # открыть конкретный проект
    python main.py --version           # версия движка
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

logger = logging.getLogger("cloudengine")
_startup_log = None


def configure_startup_logging():
    global _startup_log
    portable = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    locations = [] if getattr(sys, 'frozen', False) else [portable / 'logs']
    if os.environ.get('CLOUDENGINE_LOG_DIR'):locations.insert(0,Path(os.environ['CLOUDENGINE_LOG_DIR']))
    if os.environ.get('LOCALAPPDATA'):
        locations.append(Path(os.environ['LOCALAPPDATA']) / 'CloudEngine' / 'logs')
    if getattr(sys, 'frozen', False):
        import tempfile
        locations.append(Path(tempfile.gettempdir()) / 'CloudEngine-logs')
    for directory in locations:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            _startup_log = directory / "startup.log"
            handler = logging.FileHandler(_startup_log, encoding="utf-8")
            logging.basicConfig(level=logging.INFO, handlers=[handler],
                                format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True)
            # Windowed PyInstaller builds have no stdout/stderr. Libraries
            # should still be able to print diagnostics without crashing.
            if sys.stdout is None:
                sys.stdout = open(_startup_log, "a", encoding="utf-8", buffering=1)
            if sys.stderr is None:
                sys.stderr = sys.stdout
            logger.info("Starting Cloud Engine; frozen=%s", getattr(sys, "frozen", False))
            return
        except OSError:
            continue


def install_exception_guard() -> None:
    """Не даёт необработанным исключениям в обработчиках Qt ронять редактор.

    PyQt по умолчанию вызывает abort() при исключении внутри слота, из-за чего
    любая мелкая ошибка (например, отсутствующий атрибут) мгновенно закрывает
    всё приложение. Свой sys.excepthook отменяет это поведение: ошибка
    попадает в лог и в консоль редактора, а работа продолжается.
    """
    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            logger.error("Необработанная ошибка:\n%s", text)
        except Exception:
            pass
        try:
            sys.__stderr__.write(text)
            sys.__stderr__.flush()
        except Exception:
            pass
        # Показываем последнюю ошибку в консоли редактора, если она уже открыта.
        try:
            from editor.console_panel import report_unhandled
            report_unhandled(text)
        except Exception:
            pass

    sys.excepthook = hook

    # Ошибки в потоках Qt тоже не должны убивать процесс.
    try:
        from PyQt6.QtCore import qInstallMessageHandler

        def qt_handler(mode, context, message):
            if message and "Point size" not in message and "libpng" not in message:
                from PyQt6.QtCore import QtMsgType
                level=logging.CRITICAL if mode==QtMsgType.QtFatalMsg else logging.WARNING if mode in (QtMsgType.QtWarningMsg,QtMsgType.QtCriticalMsg) else logging.DEBUG
                logger.log(level,"Qt: %s",message)

        qInstallMessageHandler(qt_handler)
    except Exception:
        pass


def _prepare_root() -> str:
    """Добавляет корень движка в sys.path и возвращает его."""
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def _parse_args(argv):
    """Простой разбор аргументов командной строки."""
    args = {"build": False, "onefile": False, "console": False,
            "project": "", "version": False, "clean": False, "smoke_test": "", "runtime_check": "", "window_check": ""}
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--build":
            args["build"] = True
        elif arg == "--onefile":
            args["onefile"] = True
        elif arg == "--console":
            args["console"] = True
        elif arg == "--clean":
            args["clean"] = True
        elif arg == "--version":
            args["version"] = True
        elif arg == "--project" and i + 1 < len(argv):
            i += 1
            args["project"] = argv[i]
        elif arg == "--window-check" and i + 1 < len(argv):
            i += 1
            args["window_check"] = argv[i]
        elif arg == "--runtime-check" and i + 1 < len(argv):
            i += 1
            args["runtime_check"] = argv[i]
        elif arg == "--smoke-test" and i + 1 < len(argv):
            i += 1
            args["smoke_test"] = argv[i]
        elif not arg.startswith("-") and os.path.isdir(arg):
            args["project"] = arg
        i += 1
    return args


def _set_icon(app, root: str) -> None:
    """Устанавливает иконку приложения (ico на Windows, иначе png)."""
    try:
        from editor.icons import ensure_default_icon, get_app_icon
        from PyQt6.QtGui import QIcon

        ensure_default_icon(os.path.join(root, "assets", "default_icon.png"))
        icon = QIcon()
        for name in ("app_icon.ico", "engine_icon.ico", "app_icon.png",
                     "engine_icon.png"):
            path = os.path.join(root, "assets", name)
            if os.path.isfile(path):
                candidate = QIcon(path)
                if not candidate.isNull():
                    icon = candidate
                    break
        if icon.isNull():
            icon = get_app_icon()
        app.setWindowIcon(icon)
    except Exception as exc:
        print(f"[Cloud Engine] Иконка недоступна: {exc}")


def run_editor(args) -> int:
    """Запускает редактор Cloud Engine."""
    root = _prepare_root()

    from qt_runtime import configure, verify_windows_plugin
    configure()

    # Ставим защиту ДО создания QApplication.
    install_exception_guard()

    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError(f"Не удалось загрузить Qt редактора: {exc}") from exc

    # Окружение SDL готовим до инициализации pygame (встраивание в Qt).
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    verify_windows_plugin()
    app = QApplication(sys.argv[:1])
    logger.info("Qt initialized: platform=%s plugins=%s",app.platformName(),os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH","default"))
    app.setApplicationName("Cloud Engine")
    app.setOrganizationName("CloudEngine")

    try:
        from editor.theme import apply_theme
        apply_theme(app)
    except Exception as exc:
        print(f"[Cloud Engine] Не удалось применить тему: {exc}")

    from editor.localization import install
    install(app)
    _set_icon(app, root)

    from editor.main_window import MainWindow

    if args.get('window_check'):
        import json
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QFontDatabase
        from editor.project_hub import ProjectHub
        report=Path(args['window_check']);report.parent.mkdir(parents=True,exist_ok=True)
        hub=ProjectHub();hub.show()
        def capture():
            hub.grab().save(str(report.with_suffix('.png')))
            report.write_text(json.dumps({'platform':app.platformName(),'window_visible':hub.isVisible(),'fonts_available':bool(QFontDatabase.families()),'plugin_path':os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH',''),'version':__import__('engine').__version__},ensure_ascii=False,indent=2),encoding='utf-8')
            hub.close();app.quit()
        QTimer.singleShot(700,capture)
        app.exec()
        return 0

    if args.get("runtime_check"):
        from portable_diagnostics import run
        return run(app, args["runtime_check"])
    if args.get("smoke_test"):
        return smoke_editor(app, args["smoke_test"])

    project = args.get("project", "")
    if not project:
        from editor.project_hub import ProjectHub
        hub = ProjectHub()
        if not hub.exec():
            return 0
        project = hub.project_path

    window = MainWindow()
    window.show()

    if project:
        window.open_project(project)

    return app.exec()


def smoke_editor(app, report_path):
    """Exercise actual frozen GUI initialization, hub, projects and rendering."""
    import json
    import tempfile
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen' and os.name == 'nt':
        # The offscreen font database does not enumerate Windows system fonts.
        from PyQt6.QtGui import QFontDatabase, QFont
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf'
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path)); app.setFont(QFont('Segoe UI',10))
    from PyQt6.QtCore import QTimer
    from editor.project_hub import ProjectHub, create_project
    from editor.main_window import MainWindow
    report = Path(report_path).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    results = {"frozen": bool(getattr(sys, "frozen", False))}
    with tempfile.TemporaryDirectory(prefix="cloud-smoke-", dir=report.parent) as temporary:
        hub = ProjectHub()
        hub.show()
        app.processEvents()
        results["hub"] = hub.isVisible()
        results['hub_templates'] = hasattr(hub, 'template') and hub.template.findText('Контроллер игрока 2D') >= 0
        hub.hide()
        window = MainWindow()
        window.save_layout = lambda: None
        window.show()
        for template in ("Пустой 2D", "Платформер"):
            project = create_project(temporary, template, template)
            window.open_project(project)
            app.processEvents()
            if window.current_scene is None:
                raise RuntimeError(f"Не загрузилась сцена шаблона {template}")
            results[template] = True
        window.viewport._tick_editor()
        results['plugins'] = len(window.plugin_host.loaded) == 10 and not window.plugin_host.errors
        from engine.nodes.game_object import GameObject
        from engine.resources.scene_serializer import SceneSerializer
        obj = GameObject('ComponentSmoke')
        for component in ('SpriteRenderer', 'Rigidbody2D', 'BoxCollider2D', 'Animator'):
            obj.add_component(component)
        restored = SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(obj))
        results['components'] = len(restored.components) == 5
        from engine.systems.cloud_scripts import compile_cloud
        scope = {'GameObject': GameObject}
        exec(compile_cloud('script Check extends GameObject:\n    export speed: float = 3.0\n    func answer():\n        return sum(i for i in range(4))\n'), scope)
        results['cloud_scripts'] = scope['Check']().answer() == 6
        from engine.nodes.tilemap import TileMap
        from engine.core.scene_tree import SceneTree
        from engine.core.scene import Scene
        from engine.systems.physics_system import PhysicsSystem
        from engine.systems.collision_system import CollisionSystem
        from engine.math.vector2 import Vector2
        physics_root = GameObject('PhysicsCheck')
        tiles = TileMap(); tiles.position = Vector2(-16,100); tiles.set_cell(0,0,0,True)
        falling = GameObject('Falling'); falling.add_component('BoxCollider2D')
        rigid = falling.add_component('Rigidbody2D'); rigid.velocity = Vector2(0,20000)
        physics_root.add_child(tiles); physics_root.add_child(falling)
        tree = SceneTree(); tree.current_scene = Scene('PhysicsCheck',physics_root)
        tree.collision_system = CollisionSystem(tree)
        PhysicsSystem(tree).integrate(1/60)
        results['fast_box_tile_collision'] = abs(falling.position.y-84)<0.001
        results['bundled_runtime'] = bool(getattr(sys,'frozen',False))
        results["viewport"] = window.viewport.screen is not None
        window.play_game()
        window.viewport._tick_game()
        results["play"] = window.viewport.is_playing
        window.stop_game()
        from editor.creation_smoke import run as check_creation
        results.update(check_creation(app,window,report))
        from editor.production_smoke import run as check_production
        results.update(check_production(app,window,report))
        from editor.interface_smoke import run as check_interface
        results.update(check_interface(app,window,report))
        from editor.cinema_smoke import run as check_cinema
        results.update(check_cinema(app,window,report))
        from editor.template_smoke import run as check_templates
        results.update(check_templates(app,window,report))
        from editor.studio_smoke import run as check_studio
        results.update(check_studio(app,window,report))
        QTimer.singleShot(250, app.quit)
        app.exec()
        window.close()
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def _main() -> int:
    """Главная функция: редактор или сборка EXE."""
    if '--test-scene' in sys.argv:
        from engine.testing.project_checks import worker
        return worker(sys.argv[sys.argv.index('--test-scene')+1])
    if '--portable-export' in sys.argv:
        import argparse
        parser=argparse.ArgumentParser()
        parser.add_argument('--portable-export',action='store_true')
        parser.add_argument('--project',required=True)
        parser.add_argument('--output',required=True)
        parser.add_argument('--name',required=True)
        parser.add_argument('--target',default='windows')
        options=parser.parse_args()
        from build_game import native_target,prepare_source
        if options.target != native_target():
            return prepare_source(options.project, options.output, options.name, options.target)
        from portable_export import export_portable
        template=Path(__file__).resolve().parent/'player-template'
        export_portable(options.project,options.output,options.name,template)
        return 0
    args = _parse_args(sys.argv)

    if args["version"]:
        _prepare_root()
        try:
            from engine import __version__
        except Exception:
            __version__ = "1.0.0"
        print(f"Cloud Engine {__version__}")
        return 0

    if args["build"]:
        root = _prepare_root()
        try:
            from build_exe import build
        except Exception as exc:
            print(f"[Cloud Engine] Не удалось загрузить сборщик: {exc}")
            return 1
        return build(onefile=args["onefile"], console=args["console"],
                     clean=args["clean"], root=root)

    return run_editor(args)


def main() -> int:
    configure_startup_logging()
    try:
        return _main()
    except Exception:
        logger.exception("Ошибка запуска Cloud Engine")
        message = "Cloud Engine не удалось запустить.\n\n" + traceback.format_exc()
        if _startup_log:
            message += f"\nЖурнал: {_startup_log}"
        if os.name == "nt" and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "Ошибка запуска Cloud Engine", 0x10)
        else:
            print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
