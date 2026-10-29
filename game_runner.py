"""Standalone player. Deliberately has no editor or Qt imports."""
import argparse
import json
import logging
import sys
from pathlib import Path


def run(project, frames=0):
    import pygame
    from engine.core.scene import Scene
    from engine.core.scene_tree import SceneTree
    from engine.core.game_loop import GameLoop
    from engine.resources.asset_manager import AssetManager
    from engine.systems.script_system import ScriptSystem
    from engine.systems.render_system import RenderSystem
    from engine.systems.physics_system import PhysicsSystem
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.animation_system import AnimationSystem
    from engine.systems.audio_system import AudioSystem
    from engine.systems.particle_system import ParticleSystem
    from engine.systems.ui_system import UISystem
    from engine.systems.light_system import LightSystem
    from engine.systems.post_process import PostProcessSystem
    project = Path(project).resolve()
    settings = json.loads((project / 'project.json').read_text(encoding='utf-8-sig'))
    scene_path = (project / settings['main_scene']).resolve()
    if not scene_path.is_relative_to(project) or not scene_path.is_file():
        raise ValueError('Стартовая сцена отсутствует или находится вне проекта')
    pygame.init()
    window = settings.get('window', {})
    flags = pygame.RESIZABLE if window.get('resizable', True) else 0
    if window.get('fullscreen', False):
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((int(window.get('width', 1280)), int(window.get('height', 720))), flags)
    pygame.display.set_caption(window.get('title', settings.get('name', 'Cloud Game')))
    icon = window.get('icon', '')
    if icon and (project / icon).is_file():
        pygame.display.set_icon(pygame.image.load(str(project / icon)))
    scripts = ScriptSystem(str(project)); scripts.reload()
    if scripts.errors:
        raise RuntimeError('Ошибки скриптов: ' + repr(scripts.errors))
    assets = AssetManager(str(project))
    tree = SceneTree(settings)
    render = RenderSystem(tree, assets)
    audio = AudioSystem(tree); audio.init_mixer()
    loop = GameLoop(tree, settings, screen)
    loop.attach_systems(physics=PhysicsSystem(tree), collision=CollisionSystem(tree),
        render=render, animation=AnimationSystem(tree), audio=audio,
        particle=ParticleSystem(tree), ui=UISystem(tree), script=scripts,
        light=LightSystem(tree), post_process=PostProcessSystem(tree))
    scene = Scene.load(str(scene_path), scripts)
    render.prepare_scene(scene); tree.change_scene(scene); render.bind_assets()
    loop.start()
    clock = pygame.time.Clock()
    count = 0
    try:
        while loop.running:
            # Preserve keyboard/mouse events for InputManager's polling.
            if pygame.event.get(pygame.QUIT):
                break
            loop.step()
            pygame.display.flip()
            clock.tick(int(settings.get('max_fps', 60)))
            count += 1
            if frames and count >= frames:
                break
    finally:
        loop.stop(); tree.cutscenes.stop(True); tree._exit_scene(tree.current_scene); pygame.quit()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default=str(Path(__file__).resolve().parent / 'game_data'))
    parser.add_argument('--frames', type=int, default=0)
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.project, args.frames))
    except Exception:
        log = Path(sys.executable).parent / 'game-error.log' if getattr(sys, 'frozen', False) else Path('game-error.log')
        logging.basicConfig(filename=str(log), level=logging.ERROR)
        logging.exception('Game startup failed')
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'Ошибка запуска игры. Подробности: ' + str(log), 'Cloud Game', 16)
        raise SystemExit(1)
