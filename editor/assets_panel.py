"""AssetsPanel — файловый менеджер проекта.

Умеет:
- показывать дерево файлов проекта с поиском;
- принимать файлы, перетащенные из проводника Windows (копирует их в проект);
- импортировать файлы и создавать папки через контекстное меню;
- перетаскивать ассеты во Viewport (создаётся Sprite2D).
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QUrl, QSize
from PyQt6.QtGui import QDrag, QIcon, QImageReader, QPixmap
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QHeaderView,
                             QTreeWidget, QTreeWidgetItem, QMenu, QInputDialog,
                             QFileDialog, QMessageBox, QLabel, QPushButton, QHBoxLayout)

from editor.icons import get_icon

logger = logging.getLogger("cloudengine.assets")

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga", ".webp")
_AUDIO_EXTS = (".wav", ".ogg", ".caudio")


class AssetTree(QTreeWidget):
    """Дерево файлов: принимает файлы из проводника и отдаёт их наружу."""

    files_dropped = pyqtSignal(list, str)   # (пути, папка назначения)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    # ------------------------------------------------------------------
    # Приём файлов из проводника
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            item = self.itemAt(event.position().toPoint())
            target = self._target_dir(item)
            paths = [url.toLocalFile() for url in event.mimeData().urls()
                     if url.isLocalFile()]
            if paths and target:
                self.files_dropped.emit(paths, target)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _target_dir(self, item: Optional[QTreeWidgetItem]) -> str:
        """Папка, в которую класть перетащенные файлы."""
        if item is None:
            return self.property("project_dir") or ""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        kind = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not path:
            return self.property("project_dir") or ""
        return path if kind == "dir" else os.path.dirname(path)

    # ------------------------------------------------------------------
    # Перетаскивание ассетов в Viewport
    # ------------------------------------------------------------------
    def startDrag(self, supported_actions) -> None:  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path):
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        mime.setText(path)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class AssetsPanel(QWidget):
    """Файловый менеджер проекта."""

    resource_moved = pyqtSignal(str, str)
    open_scene = pyqtSignal(str)
    open_script = pyqtSignal(str)
    attach_script = pyqtSignal(str)
    open_image = pyqtSignal(str)
    open_visual = pyqtSignal(str)
    asset_dropped = pyqtSignal(str)
    new_scene_requested = pyqtSignal(str)
    new_script_requested = pyqtSignal(str)
    new_visual_requested = pyqtSignal(str)
    assets_imported = pyqtSignal(list)      # список скопированных путей

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.project_dir: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск файлов...")
        self.search.textChanged.connect(self._on_search)
        layout.addWidget(self.search)
        self.tree = AssetTree()
        self.tree.setIconSize(QSize(48, 48))
        self.tree.setHeaderLabels(["Имя", "Тип"])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 70)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self.tree)

        hint = QLabel("Перетащите файлы сюда, чтобы добавить их в проект")
        hint.setStyleSheet("color: #9e9e9e; padding: 0 4px 2px 4px;")
        layout.addWidget(hint)

    # ==================================================================
    # Проект
    # ==================================================================
    def set_project_dir(self, path: str) -> None:
        self.project_dir = path
        self.tree.setProperty("project_dir", path)
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        if not self.project_dir:
            return
        root_item = self._build_dir_item(self.project_dir)
        root_item.setText(0, os.path.basename(self.project_dir.rstrip("\\/")) or self.project_dir)
        self.tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)

    def _build_dir_item(self, path: str) -> QTreeWidgetItem:
        name = os.path.basename(path) or path
        item = QTreeWidgetItem([name, ""])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, "dir")
        item.setIcon(0, get_icon("folder"))
        try:
            entries = sorted(os.listdir(path), key=lambda s: (not os.path.isdir(os.path.join(path, s)), s.lower()))
        except Exception:
            return item
        for entry in entries:
            if entry.startswith('.') or entry in ('__pycache__', 'venv', 'venv1', 'venv2', 'node_modules', 'build', 'dist'):
                continue
            full = os.path.join(path, entry)
            if os.path.islink(full):
                continue
            if os.path.isdir(full):
                item.addChild(self._build_dir_item(full))
            else:
                child = QTreeWidgetItem([entry, _file_type(entry)])
                child.setData(0, Qt.ItemDataRole.UserRole, full)
                child.setData(0, Qt.ItemDataRole.UserRole + 1, "file")
                child.setIcon(0, _icon_for_file(entry))
                if entry.lower().endswith(_IMAGE_EXTS):
                    reader = QImageReader(full)
                    reader.setAutoTransform(True)
                    size = reader.size()
                    if size.isValid():
                        size.scale(48, 48, Qt.AspectRatioMode.KeepAspectRatio)
                        reader.setScaledSize(size)
                    image = reader.read()
                    if not image.isNull():
                        child.setIcon(0, QIcon(QPixmap.fromImage(image)))
                item.addChild(child)
        return item

    def stop_audio(self):
        channel = getattr(self, '_preview_channel', None)
        if channel is not None:
            channel.stop()
        self._preview_channel = None

    def preview_audio(self):
        item = self.tree.currentItem()
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else ''
        if not path or not path.lower().endswith(_AUDIO_EXTS):
            return
        try:
            import pygame
            self.stop_audio()
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._preview_sound = pygame.mixer.Sound(path)
            self._preview_channel = self._preview_sound.play()
        except Exception as exc:
            QMessageBox.warning(self, 'Прослушивание', str(exc))

    def find_unused(self):
        from pathlib import Path
        if not self.project_dir:
            return
        root = Path(self.project_dir)
        sources = []
        for path in root.rglob('*'):
            if path.is_file() and path.suffix.lower() in ('.scene', '.json', '.cloud', '.py', '.cs', '.shader', '.material', '.prefab', '.gamedata', '.behavior', '.particles') and not any(p.startswith('.') or p in ('__pycache__', 'build', 'dist') for p in path.relative_to(root).parts):
                try:
                    sources.append(path.read_text(encoding='utf-8-sig').replace('\\\\', '/').replace('\\', '/'))
                except (OSError, UnicodeError):
                    pass
        text = '\n'.join(sources)
        unused = []
        for path in root.rglob('*'):
            if path.is_file() and path.suffix.lower() in (*_IMAGE_EXTS, *_AUDIO_EXTS, '.ttf'):
                relative = path.relative_to(root).as_posix()
                if relative not in text and path.name not in text:
                    unused.append(relative)
        QMessageBox.information(self, 'Ресурсы без найденных ссылок',
            'Динамические пути в скриптах могут не определяться.\n\n' + ('\n'.join(unused) or 'Все ресурсы имеют ссылки.'))

    def import_files(self, paths: List[str], target_dir: str = "") -> List[str]:
        """Копирует файлы в проект и обновляет дерево.

        :return: список путей, куда файлы были скопированы.
        """
        if not paths:
            return []
        target_dir = target_dir or self._selected_dir()
        if not target_dir:
            logger.warning("Не выбрана папка проекта для импорта")
            return []
        os.makedirs(target_dir, exist_ok=True)
        copied: List[str] = []
        for source in paths:
            if not os.path.isfile(source):
                continue
            destination = os.path.join(target_dir, os.path.basename(source))
            destination = _unique_path(destination)
            try:
                shutil.copy2(source, destination)
                copied.append(destination)
            except Exception:
                logger.exception("Не удалось скопировать %s", source)
        if copied:
            self.refresh()
            self.assets_imported.emit(copied)
        return copied

    def _selected_dir(self) -> str:
        """Папка для импорта: выбранная в дереве либо корень проекта."""
        item = self.tree.currentItem()
        if item is not None:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            kind = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if path:
                return path if kind == "dir" else os.path.dirname(path)
        if self.project_dir:
            assets_dir = os.path.join(self.project_dir, "assets")
            return assets_dir if os.path.isdir(assets_dir) else self.project_dir
        return ""

    def _on_files_dropped(self, paths: List[str], target_dir: str) -> None:
        copied=[]
        for source in paths:
            if os.path.splitext(source)[1].lower() in (*_IMAGE_EXTS,*_AUDIO_EXTS):
                self.preview_import(source,target_dir)
            else:
                copied.extend(self.import_files([source],target_dir))
        if copied:
            logger.info("Импортировано файлов: %d", len(copied))

    # ==================================================================
    # События
    # ==================================================================
    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or os.path.isdir(path):
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".scene":
            self.open_scene.emit(path)
        elif ext == ".vgraph":
            self.open_visual.emit(path)
        elif ext in (".py", ".cloud", ".cs", ".shader", ".material", ".prefab", ".gamedata"):
            self.open_script.emit(path)
        elif ext in _IMAGE_EXTS:
            self.open_image.emit(path)

    def _on_search(self, text: str) -> None:
        self._filter_items(self.tree.invisibleRootItem(), text.lower())

    def _filter_items(self, parent: QTreeWidgetItem, text: str) -> None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if not text:
                child.setHidden(False)
            else:
                child.setHidden(text not in child.text(0).lower())
            self._filter_items(child, text)

    def _on_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else self.project_dir
        is_dir = (item is None) or item.data(0, Qt.ItemDataRole.UserRole + 1) == "dir"
        target_dir = path if is_dir else os.path.dirname(path or "")
        menu = QMenu(self)

        import_action = menu.addAction("Импортировать файлы...")
        import_action.setIcon(get_icon("image"))
        import_action.triggered.connect(
            lambda: self._choose_import_files(target_dir))

        new_scene = menu.addAction("Новая сцена (.scene)")
        new_scene.triggered.connect(
            lambda: self._create_new(path, ".scene", self.new_scene_requested))
        new_script = menu.addAction("Новый скрипт (.py)")
        new_script.triggered.connect(
            lambda: self._create_new(path, ".py", self.new_script_requested))
        cloud = menu.addAction("Новый Cloud Script (.cloud)")
        cloud.triggered.connect(lambda: self._create_new(path, ".cloud", self.new_script_requested))
        csharp = menu.addAction("Новый C# скрипт (.cs)")
        csharp.triggered.connect(lambda: self._create_new(path, ".cs", self.new_script_requested))
        shader = menu.addAction("Новый шейдер (.shader)")
        shader.triggered.connect(lambda: self._create_new(path, ".shader", self.new_script_requested))
        new_folder = menu.addAction("Новая папка")
        new_folder.setIcon(get_icon("folder"))
        new_folder.triggered.connect(lambda: self._create_folder(target_dir))

        if item is not None and not is_dir:
            if os.path.splitext(path)[1].lower() in _IMAGE_EXTS:
                menu.addAction('Нарезать спрайт…', lambda: self.open_image.emit(path))
            if os.path.splitext(path)[1].lower() in (*_IMAGE_EXTS,*_AUDIO_EXTS):
                menu.addAction('Предпросмотр и настройки импорта…',lambda:self.preview_import(path,target_dir))
            if os.path.splitext(path)[1].lower() in (".py", ".cloud", ".cs"):
                attach = menu.addAction("Назначить скрипт выбранному объекту")
                attach.triggered.connect(lambda: self.attach_script.emit(path))
            menu.addSeparator()
            rename = menu.addAction("Переименовать")
            rename.triggered.connect(lambda: self._rename(item))
            delete = menu.addAction("Удалить")
            delete.setIcon(get_icon("delete"))
            delete.triggered.connect(lambda: self._delete_file(path))
        if item and is_dir and path and os.path.abspath(path) != os.path.abspath(self.project_dir):
            menu.addAction('Переименовать папку…', lambda: self._rename(item))
        if item and path and os.path.abspath(path) != os.path.abspath(self.project_dir):
            menu.addAction('Переместить…', lambda: self._move_resource(path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _choose_import_files(self, target_dir: str) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Импортировать файлы в проект", "",
            "Все поддерживаемые (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.wav *.ogg *.ttf);;"
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;"
            "Звуки (*.wav *.ogg);;Все файлы (*)")
        if files:
            for source in files:
                if os.path.splitext(source)[1].lower() in (*_IMAGE_EXTS,*_AUDIO_EXTS):
                    self.preview_import(source,target_dir)
                else:
                    self.import_files([source],target_dir)

    def preview_import(self,path,target_dir=None):
        from editor.import_preview import ImportPreview
        dialog=ImportPreview(path,self.project_dir,target_dir,self)
        if dialog.exec()==dialog.DialogCode.Accepted:
            self.refresh()
            self.assets_imported.emit([dialog.result_path])

    def _create_new(self, path: str, ext: str, signal) -> None:
        base_dir = path if os.path.isdir(path) else os.path.dirname(path or "")
        name, ok = QInputDialog.getText(self, "Новый файл", "Имя файла:",
                                        text=f"new{ext}")
        if ok and name.strip():
            full = os.path.join(base_dir, name.strip())
            if not full.endswith(ext):
                full += ext
            signal.emit(full)

    def _create_folder(self, base_dir: str) -> None:
        if not base_dir:
            return
        name, ok = QInputDialog.getText(self, "Новая папка", "Имя папки:")
        if ok and name.strip():
            try:
                os.makedirs(os.path.join(base_dir, name.strip()), exist_ok=True)
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать папку:\n{exc}")

    def _rename(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        old_name = os.path.basename(path)
        name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=old_name)
        if not ok or not name.strip() or name.strip() == old_name:
            return
        try:
            from build_support import validate_name
            destination = os.path.join(os.path.dirname(path), validate_name(name))
            self._relocate(path, destination)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось переименовать:\n{exc}")

    def _relocate(self, path, destination):
        if getattr(getattr(self.window(), 'viewport', None), 'is_playing', False):
            raise ValueError('Остановите Play перед перемещением ресурса')
        from editor.resource_refactor import relocate_resource
        old, new = relocate_resource(self.project_dir, path, destination)
        self.resource_moved.emit(old, new)
        self.refresh()

    def _move_resource(self, path):
        folder = QFileDialog.getExistingDirectory(self, 'Переместить ресурс в папку проекта', self.project_dir)
        if not folder:
            return
        try:
            self._relocate(path, os.path.join(folder, os.path.basename(path)))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Перемещение', str(error))

    def _delete_file(self, path: str) -> None:
        try:
            os.remove(path)
            self.refresh()
        except Exception as exc:
            logger.warning("Не удалось удалить %s: %s", path, exc)


def _unique_path(path: str) -> str:
    """Подбирает свободное имя файла (file.png -> file_1.png)."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    index = 1
    while os.path.exists(f"{base}_{index}{ext}"):
        index += 1
    return f"{base}_{index}{ext}"


def _file_type(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    if ext == ".scene":
        return "Сцена"
    if ext in (".py", ".cloud", ".cs", ".shader"):
        return "Скрипт"
    if ext == ".vgraph":
        return "Визуальный скрипт"
    if ext in _IMAGE_EXTS:
        return "Текстура"
    if ext in _AUDIO_EXTS:
        return "Звук"
    if ext == ".json":
        return "JSON"
    return ext[1:] if ext else "Файл"


def _icon_for_file(name: str) -> Any:
    ext = os.path.splitext(name)[1].lower()
    if ext == ".scene":
        return get_icon("scene")
    if ext in (".py", ".cloud", ".cs", ".shader"):
        return get_icon("script")
    if ext == ".vgraph":
        return get_icon("node")
    if ext in _IMAGE_EXTS:
        return get_icon("image")
    if ext in _AUDIO_EXTS:
        return get_icon("audio")
    return get_icon("file")
