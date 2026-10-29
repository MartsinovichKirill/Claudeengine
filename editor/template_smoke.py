"""Exercise the real template and frame editor in source and frozen builds."""
import json
from pathlib import Path
from editor.project_hub import create_project
from editor.template_library import install_player_template
from editor.sprite_frames_editor import SpriteFramesEditor
from editor.template_dialog import TemplateDialog
from engine.nodes.animated_sprite import AnimatedSprite2D


def run(app, window, report):
    parent = Path(report).parent
    name = 'TemplateSmoke'
    index = 1
    while (parent/name).exists():
        name = f'TemplateSmoke{index}';index += 1
    project = create_project(parent,name,'Контроллер игрока 2D')
    window.open_project(project)
    visual = window.current_scene.find_node('Visual')
    assert isinstance(visual, AnimatedSprite2D)
    assert len(visual.animations)==4 and len(visual.frames)==10
    window.inspector.set_node(visual)
    frames = SpriteFramesEditor(visual,project,window)
    frames.show();app.processEvents()
    frames.names.setCurrentText('Run');frames.tick();app.processEvents()
    assert frames.frames.count()==10 and not frames.preview.pixmap().isNull()
    frames.save();frames.timer.stop()
    window.save_scene()
    window.play_game();app.processEvents()
    for _ in range(10):
        window.viewport.game_loop._frame(1/60) if hasattr(window.viewport,'game_loop') else None
    window.stop_game()
    dialog=TemplateDialog(window,project);dialog.show();app.processEvents()
    dialog.grab().save(str(Path(report).with_name('templates-dialog.png')));dialog.close()
    second=install_player_template(project);assert second.name=='player_controller_2.scene'
    assert json.loads(Path(project,'project.json').read_text())['main_scene'].endswith('player_controller.scene')
    return {'player_template':True,'named_sprite_editor':True,'template_reimport_safe':True,'template_project':project}
