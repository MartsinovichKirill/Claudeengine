"""Implementations shared by the ten bundled plugin packages."""
import json
import math
import zipfile
from pathlib import Path


def activate(context, tool):
    from PyQt6.QtWidgets import (QFileDialog, QMessageBox, QInputDialog, QColorDialog,
        QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox)
    from PyQt6.QtGui import QColor
    from engine.math.vector2 import Vector2
    editor = context.editor
    project = Path(context.project_dir) if context.project_dir else None

    def report(title, text):
        QMessageBox.information(editor, title, str(text))

    if tool == 'screenshot':
        path, _ = QFileDialog.getSaveFileName(editor, 'Снимок сцены', '', 'PNG (*.png)')
        if path:
            import pygame
            if editor.viewport.screen is None:
                raise ValueError('Нет кадра для сохранения.')
            pygame.image.save(editor.viewport.screen, path)
            context.log('Снимок: ' + path)
        return
    if not project:
        raise ValueError('Сначала откройте проект.')
    if tool == 'validator':
        problems = []
        settings = json.loads((project / 'project.json').read_text(encoding='utf-8-sig'))
        if not (project / settings.get('main_scene', '')).is_file():
            problems.append('Не найдена стартовая сцена')
        if context.scene:
            for node in context.scene.get_nodes():
                children = node.get_children()
                if len({child.name for child in children}) != len(children):
                    problems.append(node.name + ': одинаковые имена дочерних объектов')
                for target in [node, *node.components]:
                    for name in ('texture_path', 'normal_map', 'script_path', 'shader_path'):
                        value = getattr(target, name, '')
                        if value and not (project / value).is_file():
                            problems.append(node.name + ': отсутствует ' + value)
        report('Проверка проекта', '\n'.join(problems) or 'Проблем не найдено.')
    elif tool == 'statistics':
        files = [p for p in project.rglob('*') if p.is_file() and not any(part.startswith('.') or part in ('__pycache__', 'build', 'dist') for part in p.relative_to(project).parts)]
        nodes = context.scene.get_nodes() if context.scene else []
        report('Статистика', f'Файлов: {len(files)}\nРазмер: {sum(p.stat().st_size for p in files) / 1048576:.2f} МБ\nОбъектов сцены: {len(nodes)}\nКомпонентов: {sum(len(n.components) for n in nodes)}\nСкриптов: {sum(p.suffix in (".py", ".cloud", ".cs") for p in files)}')
    elif tool == 'backup':
        path, _ = QFileDialog.getSaveFileName(editor, 'Архив проекта', str(project.parent / (project.name + '-backup.zip')), 'ZIP (*.zip)')
        if path:
            target = Path(path).resolve()
            if target.is_relative_to(project.resolve()):
                raise ValueError('Сохраните архив вне папки проекта.')
            with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
                for file in project.rglob('*'):
                    relative = file.relative_to(project)
                    if file.is_file() and not file.is_symlink() and not any(p.startswith('.') or p in ('__pycache__', 'build', 'dist') for p in relative.parts):
                        archive.write(file, relative)
            context.log('Резервная копия: ' + str(target))
    elif tool == 'notes':
        path = project / 'PROJECT_NOTES.md'
        dialog = QDialog(editor); dialog.setWindowTitle('Заметки проекта'); dialog.resize(640, 480)
        layout = QVBoxLayout(dialog); edit = QPlainTextEdit()
        edit.setPlainText(path.read_text(encoding='utf-8') if path.exists() else '# Заметки проекта\n')
        layout.addWidget(edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == dialog.DialogCode.Accepted:
            path.write_text(edit.toPlainText(), encoding='utf-8'); editor.assets.refresh()
    elif tool == 'find':
        name, ok = QInputDialog.getText(editor, 'Найти объект', 'Часть имени или тип компонента:')
        if ok and name.strip() and context.scene:
            needle = name.casefold()
            nodes = [n for n in context.scene.get_nodes() if needle in n.name.casefold() or any(needle in c.get_type_name().casefold() for c in n.components)]
            if nodes:
                editor.hierarchy.select_node(nodes[0]); editor.focus_selected()
                context.log('Найдено: ' + ', '.join(n.name for n in nodes))
            else:
                report('Поиск', 'Объекты не найдены.')
    elif tool == 'grid':
        step, ok = QInputDialog.getDouble(editor, 'Привязать выделенное к сетке', 'Шаг:', editor.viewport.grid_size, 1, 4096, 1)
        if ok:
            for node in context.selected():
                if hasattr(node, 'position'):
                    context.set_property(node, 'position', Vector2(round(node.position.x / step) * step, round(node.position.y / step) * step))
            context.refresh()
    elif tool == 'palette':
        color = QColorDialog.getColor(QColor(255, 255, 255), editor, 'Цвет выделенных объектов', QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            for node in context.selected():
                renderers = [c for c in node.components if c.get_type_name() == 'SpriteRenderer']
                for renderer in renderers:
                    from editor.undo_stack import ComponentPropertyCommand
                    editor.undo_stack.execute(ComponentPropertyCommand(renderer, 'color', renderer.color, color.getRgb()))
                if not renderers and hasattr(node, 'modulate'):
                    context.set_property(node, 'modulate', color.getRgb())
            context.refresh()
    elif tool == 'array':
        from editor.undo_stack import AddNodeCommand
        selected = context.selected()
        if len(selected) != 1 or selected[0].parent is None:
            raise ValueError('Выберите один объект с родителем.')
        count, ok = QInputDialog.getInt(editor, 'Ряд объектов', 'Количество копий:', 5, 1, 200)
        if not ok:
            return
        spacing, ok = QInputDialog.getDouble(editor, 'Ряд объектов', 'Шаг по X:', 64, -10000, 10000, 1)
        if ok:
            node = selected[0]
            from engine.resources.scene_serializer import SceneSerializer
            for index in range(count):
                clone = SceneSerializer.node_from_dict(SceneSerializer.node_to_dict(node), editor.script_system)
                clone.name = editor._unique_name(node.parent, node.name)
                clone.position.x += spacing * (index + 1)
                editor.undo_stack.execute(AddNodeCommand(node.parent, clone)); editor.viewport.bind_node_assets(clone)
            context.refresh()
    elif tool == 'atlas':
        files, _ = QFileDialog.getOpenFileNames(editor, 'Изображения для атласа', str(project / 'assets'), 'Images (*.png *.jpg *.webp *.bmp)')
        if not files:
            return
        target, _ = QFileDialog.getSaveFileName(editor, 'Сохранить атлас', str(project / 'assets/atlas.png'), 'PNG (*.png)')
        if not target:
            return
        import pygame
        images = [pygame.image.load(path) for path in files]
        width = max(image.get_width() for image in images); height = max(image.get_height() for image in images)
        columns = math.ceil(math.sqrt(len(images))); rows = math.ceil(len(images) / columns)
        if width * height * columns * rows > 64 * 1024 * 1024:
            raise ValueError('Атлас слишком большой (больше 64 млн пикселей).')
        atlas = pygame.Surface((width * columns, height * rows), pygame.SRCALPHA)
        metadata = {}
        for index, image in enumerate(images):
            x, y = index % columns * width, index // columns * height
            atlas.blit(image, (x, y)); metadata[str(index)] = {'source': Path(files[index]).name, 'rect': [x, y, image.get_width(), image.get_height()]}
        pygame.image.save(atlas, target)
        Path(target).with_suffix('.atlas.json').write_text(json.dumps({'hframes': columns, 'vframes': rows, 'frames': metadata}, indent=2), encoding='utf-8')
        editor.assets.refresh(); context.log('Атлас: ' + target)
    elif tool == 'unused':
        editor.assets.find_unused()
