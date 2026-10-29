"""Редактор визуальных скриптов — node-граф (аналог Blueprints/VisualScript).

Позволяет собирать логику игры из узлов: события, ветвления, действия и
вычисления, соединяя их связями. Граф хранится в файле `.vgraph`.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
                         QPolygonF, QWheelEvent)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGraphicsScene,
                             QGraphicsView, QGraphicsItem, QGraphicsPathItem,
                             QGraphicsProxyWidget, QMenu, QPushButton,
                             QToolButton, QLabel, QFileDialog, QMessageBox,
                             QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox,
                             QComboBox, QColorDialog, QGraphicsItemGroup)

from engine.visual.graph import VisualGraph, VisualLink, VisualNode
from engine.visual.nodes import (EXEC, VISUAL_CATEGORIES, get_visual_node_type,
                                 is_event_node)
from editor.icons import get_icon

logger = logging.getLogger("cloudengine.visual.editor")

NODE_WIDTH = 230
HEADER_HEIGHT = 26
PIN_HEIGHT = 20
PROP_HEIGHT = 26
PIN_RADIUS = 5

_PIN_COLORS = {
    EXEC: QColor("#e0e0e0"),
    "float": QColor("#9fd3ff"),
    "int": QColor("#9fd3ff"),
    "bool": QColor("#ff9f9f"),
    "string": QColor("#c9a0ff"),
    "vector2": QColor("#9fffc0"),
    "any": QColor("#bdbdbd"),
}


# ======================================================================
# Узел графа
# ======================================================================
class NodeItem(QGraphicsItem):
    """Графический узел визуального скрипта."""

    def __init__(self, node: VisualNode, editor: "VisualScriptEditor") -> None:
        super().__init__()
        self.node = node
        self.editor = editor
        self.node_type = get_visual_node_type(node.type)
        self.input_pins: List[Tuple[str, str]] = list(
            self.node_type.inputs if self.node_type else [])
        self.output_pins: List[Tuple[str, str]] = list(
            self.node_type.outputs if self.node_type else [])
        self.links: List["LinkItem"] = []
        self._proxies: List[QGraphicsProxyWidget] = []

        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(node.x, node.y)
        self.setZValue(10)
        self._build_property_widgets()

    # ------------------------------------------------------------------
    # Геометрия
    # ------------------------------------------------------------------
    def _rows(self) -> int:
        return max(len(self.input_pins), len(self.output_pins), 1)

    def _properties(self) -> Dict[str, Dict[str, Any]]:
        if self.node_type is None:
            return {}
        return {k: v for k, v in self.node_type.properties.items()
                if k not in ("x", "y")}

    def node_height(self) -> float:
        height = HEADER_HEIGHT + self._rows() * PIN_HEIGHT + 6
        height += len(self._properties()) * PROP_HEIGHT
        return height

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(0, 0, NODE_WIDTH, self.node_height())

    def pin_position(self, name: str, is_input: bool) -> QPointF:
        """Позиция пина в координатах сцены."""
        pins = self.input_pins if is_input else self.output_pins
        index = 0
        for i, (pin_name, _ptype) in enumerate(pins):
            if pin_name == name:
                index = i
                break
        y = HEADER_HEIGHT + index * PIN_HEIGHT + PIN_HEIGHT / 2
        x = 0.0 if is_input else float(NODE_WIDTH)
        return self.mapToScene(QPointF(x, y))

    def pin_at(self, scene_pos: QPointF) -> Optional[Tuple[str, bool]]:
        """Пин под указанной точкой сцены: (имя, является_входом)."""
        for name, _ptype in self.input_pins:
            if (self.pin_position(name, True) - scene_pos).manhattanLength() < 12:
                return (name, True)
        for name, _ptype in self.output_pins:
            if (self.pin_position(name, False) - scene_pos).manhattanLength() < 12:
                return (name, False)
        return None

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, option: Any, widget: Any = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect()
        color = QColor(self.node_type.color if self.node_type else "#3c3c3c")

        # Тело.
        painter.setBrush(QBrush(QColor("#2f2f33")))
        border = QColor("#478cbf") if self.isSelected() else QColor("#1a1a1a")
        painter.setPen(QPen(border, 2 if self.isSelected() else 1))
        painter.drawRoundedRect(rect, 6, 6)

        # Заголовок.
        header = QRectF(rect.left(), rect.top(), rect.width(), HEADER_HEIGHT)
        path = QPainterPath()
        path.addRoundedRect(header, 6, 6)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#ffffff")))
        font = QFont()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        title = self.node_type.title if self.node_type else self.node.type
        painter.drawText(header.adjusted(6, 0, -6, 0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         title)

        # Пины.
        font.setBold(False)
        font.setPointSize(7)
        painter.setFont(font)
        for index, (name, ptype) in enumerate(self.input_pins):
            y = HEADER_HEIGHT + index * PIN_HEIGHT + PIN_HEIGHT / 2
            pin_color = _PIN_COLORS.get(ptype, _PIN_COLORS["any"])
            painter.setBrush(QBrush(pin_color))
            painter.setPen(QPen(QColor("#1a1a1a"), 1))
            painter.drawEllipse(QPointF(0, y), PIN_RADIUS, PIN_RADIUS)
            painter.setPen(QPen(QColor("#d0d0d0")))
            painter.drawText(QRectF(10, y - 8, NODE_WIDTH / 2 - 12, 16),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             name)
        for index, (name, ptype) in enumerate(self.output_pins):
            y = HEADER_HEIGHT + index * PIN_HEIGHT + PIN_HEIGHT / 2
            pin_color = _PIN_COLORS.get(ptype, _PIN_COLORS["any"])
            painter.setBrush(QBrush(pin_color))
            painter.setPen(QPen(QColor("#1a1a1a"), 1))
            painter.drawEllipse(QPointF(NODE_WIDTH, y), PIN_RADIUS, PIN_RADIUS)
            painter.setPen(QPen(QColor("#d0d0d0")))
            painter.drawText(QRectF(NODE_WIDTH / 2, y - 8, NODE_WIDTH / 2 - 12, 16),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             name)

    def itemChange(self, change: Any, value: Any) -> Any:  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node.x = float(self.pos().x())
            self.node.y = float(self.pos().y())
            for link in list(self.links):
                link.update_path()
            if self.editor is not None:
                self.editor.mark_dirty()
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Виджеты свойств внутри узла
    # ------------------------------------------------------------------
    def _build_property_widgets(self) -> None:
        if self.node_type is None:
            return
        properties = self._properties()
        if not properties:
            return
        top = HEADER_HEIGHT + self._rows() * PIN_HEIGHT + 4
        for index, (prop, spec) in enumerate(properties.items()):
            widget = _make_property_widget(prop, spec, self.node, self.editor)
            if widget is None:
                continue
            widget.setFixedWidth(NODE_WIDTH - 70)
            proxy = QGraphicsProxyWidget(self)
            proxy.setWidget(widget)
            proxy.setPos(64, top + index * PROP_HEIGHT + 3)
            proxy.setZValue(11)
            self._proxies.append(proxy)


# ======================================================================
# Связь
# ======================================================================
class LinkItem(QGraphicsPathItem):
    """Связь между пинами двух узлов."""

    def __init__(self, link: VisualLink, source: NodeItem, target: NodeItem,
                 editor: "VisualScriptEditor") -> None:
        super().__init__()
        self.link = link
        self.source = source
        self.target = target
        self.editor = editor
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_path()

    def update_path(self) -> None:
        start = self.source.pin_position(self.link.from_pin, False)
        end = self.target.pin_position(self.link.to_pin, True)
        self.setPath(_bezier(start, end))

    def shape(self) -> QPainterPath:
        stroker_path = QPainterPath(self.path())
        from PyQt6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        return stroker.createStroke(stroker_path)

    def paint(self, painter: QPainter, option: Any, widget: Any = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#ffd479") if self.isSelected() else QColor("#8ab4d8"), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())


def _bezier(start: QPointF, end: QPointF) -> QPainterPath:
    """Плавная кривая между двумя пинами."""
    path = QPainterPath(start)
    dx = max(abs(end.x() - start.x()) * 0.5, 40.0)
    path.cubicTo(QPointF(start.x() + dx, start.y()),
                 QPointF(end.x() - dx, end.y()), end)
    return path


# ======================================================================
# Сцена графа
# ======================================================================
class GraphScene(QGraphicsScene):
    """Сцена, синхронизированная с моделью VisualGraph."""

    def __init__(self, editor: "VisualScriptEditor") -> None:
        super().__init__(editor)
        self.editor = editor
        self.setBackgroundBrush(QBrush(QColor("#232326")))
        self.items_by_id: Dict[str, NodeItem] = {}
        self.link_items: List[LinkItem] = []

    def rebuild(self) -> None:
        """Полностью перестраивает сцену по модели графа."""
        # Снимаем фокус: удаление QGraphicsProxyWidget, который держит фокус,
        # может привести к падению Qt.
        try:
            self.clearFocus()
            focused = self.focusItem()
            if focused is not None:
                focused.clearFocus()
        except Exception:
            pass
        self.clear()
        self.items_by_id.clear()
        self.link_items.clear()
        graph = self.editor.graph
        if graph is None:
            return
        for node in graph.nodes.values():
            item = NodeItem(node, self.editor)
            self.addItem(item)
            self.items_by_id[node.id] = item
        for link in graph.links:
            self._add_link_item(link)

    def _add_link_item(self, link: VisualLink) -> None:
        source = self.items_by_id.get(link.from_node)
        target = self.items_by_id.get(link.to_node)
        if source is None or target is None:
            return
        item = LinkItem(link, source, target, self.editor)
        self.addItem(item)
        source.links.append(item)
        target.links.append(item)
        self.link_items.append(item)

    def add_node_item(self, node: VisualNode) -> NodeItem:
        item = NodeItem(node, self.editor)
        self.addItem(item)
        self.items_by_id[node.id] = item
        return item

    def refresh_links(self) -> None:
        for item in self.link_items:
            item.update_path()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        painter.setPen(QPen(QColor("#2c2c31"), 1))
        step = 24
        left = int(rect.left()) - int(rect.left()) % step
        top = int(rect.top()) - int(rect.top()) % step
        for x in range(left, int(rect.right()), step):
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), step):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)


# ======================================================================
# Вид
# ======================================================================
class GraphView(QGraphicsView):
    """Представление графа с созданием связей и контекстным меню."""

    def __init__(self, editor: "VisualScriptEditor") -> None:
        super().__init__(editor)
        self.editor = editor
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._pending_pin: Optional[Tuple[NodeItem, str]] = None
        self._temp_link: Optional[QGraphicsPathItem] = None

    # ------------------------------------------------------------------
    # Масштаб
    # ------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    # ------------------------------------------------------------------
    # Мышь: создание связей
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            hit = self._pin_at(scene_pos)
            if hit is not None:
                item, pin_name, is_input = hit
                if is_input:
                    # Тянем от входного пина — ищем уже подключённую связь.
                    link = self.editor.graph.link_into(item.node.id, pin_name)
                    if link is not None:
                        source_item = self.editor.scene.items_by_id.get(link.from_node)
                        if source_item is not None:
                            self.editor.remove_link(link)
                            self._pending_pin = (source_item, link.from_pin)
                            self._start_temp_link(event)
                            return
                    self._pending_pin = None
                else:
                    self._pending_pin = (item, pin_name)
                    self._start_temp_link(event)
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._pending_pin is not None and self._temp_link is not None:
            start = self._pending_pin[0].pin_position(self._pending_pin[1], False)
            end = self.mapToScene(event.position().toPoint())
            self._temp_link.setPath(_bezier(start, end))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._pending_pin is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            hit = self._pin_at(scene_pos)
            if hit is not None:
                item, pin_name, is_input = hit
                if is_input:
                    self.editor.create_link(self._pending_pin[0], self._pending_pin[1],
                                            item, pin_name)
            self._cancel_temp_link()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _pin_at(self, scene_pos: QPointF):
        for item in self.editor.scene.items(scene_pos):
            if isinstance(item, NodeItem):
                pin = item.pin_at(scene_pos)
                if pin is not None:
                    return (item, pin[0], pin[1])
        return None

    def _start_temp_link(self, event) -> None:
        self._temp_link = QGraphicsPathItem()
        self._temp_link.setPen(QPen(QColor("#ffd479"), 2, Qt.PenStyle.DashLine))
        self._temp_link.setZValue(5)
        self.editor.scene.addItem(self._temp_link)

    def _cancel_temp_link(self) -> None:
        if self._temp_link is not None:
            self.editor.scene.removeItem(self._temp_link)
            self._temp_link = None
        self._pending_pin = None

    # ------------------------------------------------------------------
    # Контекстное меню
    # ------------------------------------------------------------------
    def _on_context_menu(self, pos) -> None:
        scene_pos = self.mapToScene(pos)
        menu = QMenu(self)
        item = None
        for graphics_item in self.editor.scene.items(scene_pos):
            if isinstance(graphics_item, NodeItem):
                item = graphics_item
                break

        if item is not None:
            remove_node = menu.addAction("Удалить узел")
            remove_node.setIcon(get_icon("delete"))
            remove_node.triggered.connect(lambda: self.editor.delete_node(item))
            if item.node_type is not None and not is_event_node(item.node.type):
                dup = menu.addAction("Дублировать узел")
                dup.triggered.connect(lambda: self.editor.duplicate_node(item))
        else:
            palette = menu.addMenu("＋ Добавить узел")
            for category, types in VISUAL_CATEGORIES.items():
                cat_menu = palette.addMenu(category)
                for type_name in types:
                    action = cat_menu.addAction(
                        get_visual_node_type(type_name).title)
                    action.triggered.connect(
                        lambda checked=False, t=type_name, p=scene_pos:
                        self.editor.add_node(t, p))
        menu.exec(self.mapToGlobal(pos))


# ======================================================================
# Панель редактора
# ======================================================================
class VisualScriptEditor(QWidget):
    """Панель редактирования визуального скрипта.

    Компоненты визуального кода живут только здесь: навешивание графа на
    объект сцены выполняется кнопкой «Навесить на объект».
    """

    graph_saved = pyqtSignal(str)
    attach_requested = pyqtSignal(str)      # путь к .vgraph
    detach_requested = pyqtSignal(str)      # путь к .vgraph

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.graph: Optional[VisualGraph] = None
        self._dirty = False
        self._build_ui()

    # ==================================================================
    # Интерфейс
    # ==================================================================
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        bar = QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)

        self.path_label = QLabel("Граф не открыт")
        self.path_label.setStyleSheet("color: #9e9e9e;")
        bar.addWidget(self.path_label)
        bar.addStretch(1)

        add_btn = QToolButton()
        add_btn.setText("＋ Узел")
        add_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(add_btn)
        for category, types in VISUAL_CATEGORIES.items():
            cat_menu = menu.addMenu(category)
            for type_name in types:
                action = cat_menu.addAction(get_visual_node_type(type_name).title)
                action.triggered.connect(
                    lambda checked=False, t=type_name: self.add_node(t, QPointF(80, 80)))
        add_btn.setMenu(menu)
        bar.addWidget(add_btn)

        for text, slot in (("Сохранить", self.save_graph),
                           ("Сохранить как...", self.save_graph_as),
                           ("Проверить", self.validate_graph),
                           ("Вписать", self.fit_view)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            bar.addWidget(button)
        layout.addLayout(bar)

        # --- Строка привязки графа к объекту сцены ---
        attach_bar = QHBoxLayout()
        attach_bar.setContentsMargins(4, 0, 4, 2)

        self.attach_button = QPushButton("Навесить на объект…")
        self.attach_button.setIcon(get_icon("component"))
        self.attach_button.setToolTip(
            "Компоненты визуального кода навешиваются здесь, а не в общем списке")
        self.attach_button.clicked.connect(self._request_attach)
        attach_bar.addWidget(self.attach_button)

        self.detach_button = QPushButton("Снять с объекта")
        self.detach_button.setIcon(get_icon("delete"))
        self.detach_button.clicked.connect(self._request_detach)
        attach_bar.addWidget(self.detach_button)

        self.usage_label = QLabel("Граф нигде не используется")
        self.usage_label.setStyleSheet("color:#8c8c99;")
        attach_bar.addWidget(self.usage_label, 1)
        layout.addLayout(attach_bar)

        self.scene = GraphScene(self)
        self.view = GraphView(self)
        self.view.setScene(self.scene)
        layout.addWidget(self.view, 1)

    # ------------------------------------------------------------------
    def current_path(self) -> str:
        """Путь к текущему файлу графа."""
        return (self.graph.path if self.graph is not None else "") or ""

    def _request_attach(self) -> None:
        path = self.current_path()
        if not path:
            self.validate_graph()
            path = self.current_path()
        if path:
            self.attach_requested.emit(path)

    def _request_detach(self) -> None:
        path = self.current_path()
        if path:
            self.detach_requested.emit(path)

    def set_usage(self, nodes: list) -> None:
        """Показывает, на какие объекты навешен этот граф."""
        if not nodes:
            self.usage_label.setText("Граф нигде не используется")
            self.usage_label.setStyleSheet("color:#8c8c99;")
            return
        names = ", ".join(getattr(node, "name", "?") for node in nodes[:6])
        extra = "" if len(nodes) <= 6 else f" и ещё {len(nodes) - 6}"
        self.usage_label.setText(f"Навешен на: {names}{extra}")
        self.usage_label.setStyleSheet("color:#6bbf6b;")

    # ==================================================================
    # Работа с графом
    # ==================================================================
    def new_graph(self, name: str = "Graph") -> VisualGraph:
        """Создаёт новый граф с событием «Каждый кадр»."""
        graph = VisualGraph(name)
        graph.add_node("EventProcess", 40.0, 60.0)
        self.set_graph(graph)
        return graph

    def set_graph(self, graph: Optional[VisualGraph]) -> None:
        self.graph = graph
        self.scene.rebuild()
        self._dirty = False
        if graph is None:
            self.path_label.setText("Граф не открыт")
        else:
            self.path_label.setText(graph.path or f"{graph.name} (не сохранён)")
        self.fit_view()

    def load_graph(self, path: str) -> bool:
        """Загружает граф из файла."""
        try:
            graph = VisualGraph.load(path)
        except Exception:
            logger.exception("Не удалось открыть граф %s", path)
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть граф:\n{path}")
            return False
        self.set_graph(graph)
        return True

    def save_graph(self) -> bool:
        """Сохраняет граф (спрашивает путь, если его нет)."""
        if self.graph is None:
            return False
        if not self.graph.path:
            return self.save_graph_as()
        self.graph.save(self.graph.path)
        self._dirty = False
        self.path_label.setText(self.graph.path)
        self.graph_saved.emit(self.graph.path)
        return True

    def save_graph_as(self) -> bool:
        if self.graph is None:
            return False
        start = self.graph.path or ""
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить визуальный скрипт",
                                              start, "Визуальный скрипт (*.vgraph)")
        if not path:
            return False
        if not path.endswith(".vgraph"):
            path += ".vgraph"
        self.graph.save(path)
        self._dirty = False
        self.path_label.setText(path)
        self.graph_saved.emit(path)
        return True

    def mark_dirty(self) -> None:
        self._dirty = True
        if self.graph is not None and self.graph.path:
            self.path_label.setText(f"{self.graph.path} *")

    # ==================================================================
    # Операции с узлами
    # ==================================================================
    def add_node(self, type_name: str, scene_pos: QPointF) -> Optional[VisualNode]:
        """Добавляет узел в указанную точку сцены."""
        if self.graph is None:
            self.new_graph()
        node = self.graph.add_node(type_name, float(scene_pos.x()), float(scene_pos.y()))
        self.scene.add_node_item(node)
        self.mark_dirty()
        return node

    def delete_node(self, item: NodeItem) -> None:
        """Удаляет узел и его связи."""
        if self.graph is None:
            return
        self.graph.remove_node(item.node.id)
        self.scene.rebuild()
        self.mark_dirty()

    def duplicate_node(self, item: NodeItem) -> None:
        """Дублирует узел со сдвигом."""
        if self.graph is None:
            return
        source = item.node
        clone = self.graph.add_node(source.type, source.x + 30.0, source.y + 30.0,
                                    props=dict(source.props))
        self.scene.add_node_item(clone)
        self.mark_dirty()

    def create_link(self, source_item: NodeItem, from_pin: str,
                    target_item: NodeItem, to_pin: str) -> None:
        """Создаёт связь между пинами."""
        if self.graph is None:
            return
        link = self.graph.add_link(source_item.node.id, from_pin,
                                   target_item.node.id, to_pin)
        if link is None:
            return
        # Убираем старые графические связи, ведущие в этот входной пин.
        for existing in list(self.scene.link_items):
            if existing.link.to_node == target_item.node.id and \
                    existing.link.to_pin == to_pin and existing.link is not link:
                self._remove_link_item(existing)
        self.scene._add_link_item(link)
        self.mark_dirty()

    def remove_link(self, link: VisualLink) -> None:
        if self.graph is None:
            return
        self.graph.remove_link(link)
        for item in list(self.scene.link_items):
            if item.link is link:
                self._remove_link_item(item)
        self.mark_dirty()

    def _remove_link_item(self, item: LinkItem) -> None:
        if item in self.scene.link_items:
            self.scene.link_items.remove(item)
        if item in item.source.links:
            item.source.links.remove(item)
        if item in item.target.links:
            item.target.links.remove(item)
        self.scene.removeItem(item)

    def delete_selected(self) -> None:
        """Удаляет выбранные узлы и связи."""
        if self.graph is None:
            return
        changed = False
        for item in list(self.scene.selectedItems()):
            if isinstance(item, LinkItem):
                self.remove_link(item.link)
                changed = True
            elif isinstance(item, NodeItem):
                self.graph.remove_node(item.node.id)
                changed = True
        if changed:
            self.scene.rebuild()
            self.mark_dirty()

    # ==================================================================
    # Проверка графа
    # ==================================================================
    def validate_graph(self) -> List[str]:
        """Проверяет граф и показывает отчёт."""
        if self.graph is None:
            return ["Граф не открыт"]
        problems: List[str] = []
        events = [n for n in self.graph.nodes.values() if is_event_node(n.type)]
        if not events:
            problems.append("Нет ни одного узла-события (логика не запустится)")

        reachable = set()
        stack = [n.id for n in events]
        while stack:
            node_id = stack.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            for link in self.graph.links:
                if link.from_node == node_id:
                    stack.append(link.to_node)

        for node in self.graph.nodes.values():
            if node.id not in reachable:
                title = get_visual_node_type(node.type)
                problems.append(f"Узел «{title.title if title else node.type}» "
                                f"недостижим из событий")
            node_type = get_visual_node_type(node.type)
            if node_type is None:
                problems.append(f"Неизвестный тип узла: {node.type}")
                continue
            for pin, _ptype in node_type.inputs:
                if pin == "exec":
                    continue
                if self.graph.link_into(node.id, pin) is None and \
                        pin not in node_type.properties:
                    problems.append(
                        f"У «{node_type.title}» вход «{pin}» не подключён "
                        f"(будет использовано значение по умолчанию)")

        if problems:
            QMessageBox.information(self, "Проверка графа",
                                    "\n".join(f"• {p}" for p in problems[:25]))
        else:
            QMessageBox.information(self, "Проверка графа", "Граф корректен ✔")
        return problems

    def fit_view(self) -> None:
        """Вписывает граф в окно."""
        rect = self.scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self.view.fitInView(rect.adjusted(-40, -40, 40, 40),
                            Qt.AspectRatioMode.KeepAspectRatio)

    # ==================================================================
    # Клавиатура
    # ==================================================================
    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected()
            return
        if event.key() == Qt.Key.Key_S and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.save_graph()
            return
        super().keyPressEvent(event)


# ======================================================================
# Виджеты свойств
# ======================================================================
def _make_property_widget(prop: str, spec: Dict[str, Any], node: VisualNode,
                          editor: VisualScriptEditor) -> Optional[QWidget]:
    """Создаёт редактор одного свойства узла."""
    ptype = spec.get("type", "string")
    value = node.props.get(prop, spec.get("default"))

    def store(new_value: Any) -> None:
        node.props[prop] = new_value
        editor.mark_dirty()

    if ptype == "bool":
        widget = QCheckBox()
        widget.setChecked(bool(value))
        widget.toggled.connect(store)
        return widget
    if ptype == "int":
        widget = QSpinBox()
        widget.setRange(int(spec.get("min", -10**6)), int(spec.get("max", 10**6)))
        widget.setValue(int(value) if value is not None else 0)
        widget.valueChanged.connect(store)
        return widget
    if ptype == "float":
        widget = QDoubleSpinBox()
        widget.setRange(float(spec.get("min", -1e6)), float(spec.get("max", 1e6)))
        widget.setDecimals(2)
        widget.setSingleStep(float(spec.get("step", 0.1)))
        widget.setValue(float(value) if value is not None else 0.0)
        widget.valueChanged.connect(store)
        return widget
    if ptype == "enum":
        widget = QComboBox()
        options = [str(o) for o in spec.get("options", [])]
        widget.addItems(options)
        index = widget.findText(str(value))
        if index >= 0:
            widget.setCurrentIndex(index)
        widget.currentTextChanged.connect(store)
        return widget
    if ptype == "color":
        widget = QPushButton()
        color = value if isinstance(value, (list, tuple)) else [255, 255, 255, 255]
        _apply_color_style(widget, color)

        def pick() -> None:
            current = QColor(*[int(c) for c in color[:3]])
            chosen = QColorDialog.getColor(current, editor, "Цвет")
            if chosen.isValid():
                rgba = [chosen.red(), chosen.green(), chosen.blue(), 255]
                store(rgba)
                _apply_color_style(widget, rgba)

        widget.clicked.connect(pick)
        return widget

    widget = QLineEdit(str(value if value is not None else ""))
    widget.editingFinished.connect(lambda: store(widget.text()))
    return widget


def _apply_color_style(button: QPushButton, color: Any) -> None:
    r, g, b = [int(c) for c in (list(color) + [255, 255, 255])[:3]]
    button.setStyleSheet(
        f"background-color: rgb({r},{g},{b}); border: 1px solid #1a1a1a; border-radius: 3px;")
