"""SceneTabs — вкладки открытых сцен (аналог Godot Scene tabs)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QWidget, QToolButton, QTabBar
from PyQt6.QtCore import QSize

logger = logging.getLogger("cloudengine.scene_tabs")


class SceneTabs(QTabWidget):
    """Управляет вкладками открытых сцен."""

    current_scene_changed = pyqtSignal(object)   # Scene
    scene_closed = pyqtSignal(object)            # Scene

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self._on_current_changed)
        self.tabBar().tabMoved.connect(self._reindex)
        self._scenes: Dict[int, Any] = {}

    def _reindex(self, *_):
        self._scenes = {i: getattr(self.widget(i), '_cloud_scene', None) for i in range(self.count())}

    def add_scene(self, scene: Any) -> None:
        widget = QWidget()
        widget._cloud_scene = scene
        index = self.addTab(widget, scene.name)
        from editor.icons import get_icon
        close=QToolButton(self.tabBar()); close.setObjectName('SceneTabClose')
        close.setIcon(get_icon('close',14)); close.setIconSize(QSize(14,14)); close.setFixedSize(22,22)
        close.setToolTip('Закрыть сцену'); close.setAccessibleName('Закрыть сцену')
        close.setAutoRaise(True)
        close.clicked.connect(lambda checked=False,page=widget:self.close_tab(self.indexOf(page)) if self.indexOf(page)>=0 else None)
        self.tabBar().setTabButton(index,QTabBar.ButtonPosition.RightSide,close)
        self._reindex()
        self.setCurrentIndex(index)

    def get_scene(self, index: int) -> Optional[Any]:
        widget = self.widget(index)
        return getattr(widget, '_cloud_scene', None) if widget is not None else None

    def get_current_scene(self) -> Optional[Any]:
        return self.get_scene(self.currentIndex())

    def scenes(self) -> list:
        return [self.get_scene(i) for i in range(self.count())]

    def set_scene_name(self, scene: Any, name: str) -> None:
        scene.name = name
        for index in range(self.count()):
            if self.get_scene(index) is scene:
                self.setTabText(index, name)

    def close_tab(self, index: int) -> None:
        if index < 0 or index >= self.count(): return
        scene = self.get_scene(index)
        widget = self.widget(index)
        self.removeTab(index)
        self._reindex()
        if widget is not None:
            widget.deleteLater()
        if scene is not None:
            self.scene_closed.emit(scene)

    def _on_current_changed(self, index: int) -> None:
        scene = self.get_scene(index)
        if scene is not None:
            self.current_scene_changed.emit(scene)
