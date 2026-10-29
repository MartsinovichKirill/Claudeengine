"""Editable animation state graph with validated transitions."""
import json
from editor.authoring_style import COLORS
from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtGui import QColor, QPen, QBrush, QPainterPath, QPolygonF
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGraphicsScene,
    QGraphicsView, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QDialogButtonBox, QMessageBox, QLineEdit,QWidget,QSplitter,QTabWidget,QGraphicsRectItem)


class GraphView(QGraphicsView):
    def wheelEvent(self,event):
        factor=1.15 if event.angleDelta().y()>0 else 1/1.15
        if .2<self.transform().m11()*factor<4:self.scale(factor,factor)


class StateItem(QGraphicsRectItem):
    def __init__(self,editor,name,row,x,y,color):
        super().__init__(0,0,172,64);self.editor=editor;self.name=name;self.row=row
        self.setPos(x,y);self.setBrush(QBrush(QColor(color)));self.setPen(QPen(QColor(COLORS['border'])))
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable|QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
    def mousePressEvent(self,event):
        self.editor.states.selectRow(self.row);super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        self.editor.editor_positions[self.name]=[self.pos().x(),self.pos().y()]
        super().mouseReleaseEvent(event);QTimer.singleShot(0,self.editor.draw_graph)


class AnimatorEditor(QDialog):
    def __init__(self, component, parent=None):
        super().__init__(parent)
        from editor.authoring_style import apply,COLORS
        apply(self);self.setWindowTitle('Animator — состояния и переходы');self.resize(1420,800)
        self.component=component;self.result_data=None
        self.editor_positions=dict(getattr(component,'editor_positions',{}));self.first_graph=True
        layout=QVBoxLayout(self);layout.addWidget(QLabel('ANIMATOR · Base Layer'))
        split=QSplitter();layout.addWidget(split,1)
        left=QWidget();leftbox=QVBoxLayout(left);leftbox.addWidget(QLabel('Состояния'))
        self.states=self.table(leftbox,['Состояние','Клип'],list(component.states.items()))
        leftbox.addWidget(QLabel('Начальное состояние'));self.entry=QLineEdit(component.entry_state);leftbox.addWidget(self.entry)
        leftbox.addWidget(QLabel('Параметры'))
        self.parameter_table=self.table(leftbox,['Имя','Значение JSON'],[(k,json.dumps(v,ensure_ascii=False)) for k,v in component.parameters.items()])
        self.parameters=QLineEdit(json.dumps(component.parameters,ensure_ascii=False));self.parameters.hide();leftbox.addWidget(self.parameters)
        split.addWidget(left)
        center=QWidget();centerbox=QVBoxLayout(center);bar=QHBoxLayout();bar.addWidget(QLabel('BASE LAYER'));bar.addStretch()
        self.graph=QGraphicsScene(self);self.graph.setBackgroundBrush(QBrush(QColor(COLORS['bg_dark'])))
        self.view=GraphView(self.graph);self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        fit=QPushButton('Показать весь граф');fit.clicked.connect(lambda:self.view.fitInView(self.graph.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio));bar.addWidget(fit)
        centerbox.addLayout(bar);centerbox.addWidget(self.view,1)
        centerbox.addWidget(QLabel('Тяните состояния · колесо — масштаб · фон — панорама'));split.addWidget(center)
        right=QWidget();rightbox=QVBoxLayout(right);rightbox.addWidget(QLabel('Переходы · сверху вниз'))
        self.transitions=self.table(rightbox,['Из','В','Параметр','Условие','Значение'],
            [[t.get('from','*'),t.get('to',''),t.get('parameter',''),t.get('operator','=='),json.dumps(t.get('value'),ensure_ascii=False)] for t in component.transitions])
        hint=QLabel('* — любое состояние. Значение: число, true, false или строка в кавычках. Оранжевый блок — начальное состояние.');hint.setWordWrap(True);rightbox.addWidget(hint)
        split.addWidget(right);split.setSizes([260,680,460])
        for col,width in enumerate([65,65,90,70,95]):self.transitions.setColumnWidth(col,width)
        self.states.itemChanged.connect(self.draw_graph);self.transitions.itemChanged.connect(self.draw_graph)
        self.entry.textChanged.connect(self.draw_graph);self.parameter_table.itemChanged.connect(self.sync_parameters)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept_data);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.draw_graph()

    def sync_parameters(self):
        try:self.parameters.setText(json.dumps({k:json.loads(v) for k,v in self.rows(self.parameter_table) if k},ensure_ascii=False))
        except ValueError:pass

    def table(self, layout, headers, rows):
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        for values in rows:
            row = table.rowCount(); table.insertRow(row)
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(str(value)))
        layout.addWidget(table)
        controls = QHBoxLayout()
        add = QPushButton('＋ Добавить'); remove = QPushButton('− Удалить выбранное')
        add.clicked.connect(lambda: table.insertRow(table.rowCount()))
        remove.clicked.connect(lambda: (table.removeRow(table.currentRow()), self.draw_graph()))
        controls.addWidget(add); controls.addWidget(remove); layout.addLayout(controls)
        return table

    @staticmethod
    def rows(table):
        return [[table.item(row, col).text().strip() if table.item(row, col) else '' for col in range(table.columnCount())] for row in range(table.rowCount())]

    def draw_graph(self, *_):
        self.graph.clear()
        positions = {}
        self.graph.addRect(0, 0, 150, 44, QPen(QColor('#81bb94')), QBrush(QColor('#3c614a')))
        any_text = self.graph.addText('Any State (*)'); any_text.setDefaultTextColor(QColor('#dbe9f5')); any_text.setPos(12, 8)
        positions['*'] = (75, 22)
        for i, (name, clip) in enumerate(self.rows(self.states)):
            x, y = (i % 4) * 205, 120 + (i // 4) * 150
            x,y=self.editor_positions.get(name,[x,y])
            positions[name] = (x + 80, y + 32)
            color='#9a693e' if name==self.entry.text() else COLORS['selection'] if name==self.component.state else COLORS['bg_light']
            item=StateItem(self,name,i,x,y,color);self.graph.addItem(item)
            text = self.graph.addText(name + '\n' + clip);text.setTextWidth(150);text.setDefaultTextColor(QColor(COLORS['text']));text.setParentItem(item);text.setPos(10,5);text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        for index, (start, end, parameter, operation, value) in enumerate(self.rows(self.transitions)):
            if start == end or start not in positions or end not in positions:
                continue
            x1, y1 = positions[start]; x2, y2 = positions[end]
            y1 += 24 if start == '*' else 32
            y2 -= 32
            lane = 64 + index * 12 if start == '*' else max(y1, y2) + 35 + index * 15
            path = QPainterPath(QPointF(x1, y1)); path.lineTo(x1, lane); path.lineTo(x2, lane); path.lineTo(x2, y2)
            line = self.graph.addPath(path, QPen(QColor(COLORS['accent']))); line.setZValue(-1)
            line.setToolTip(f'{start} → {end}: {parameter} {operation} {value}')
            self.graph.addPolygon(QPolygonF([QPointF(x2, y2), QPointF(x2-5, y2-8), QPointF(x2+5, y2-8)]), QPen(QColor(COLORS['accent'])), QBrush(QColor(COLORS['accent'])))
            label = self.graph.addText(parameter + ' ' + operation + ' ' + value)
            label.setDefaultTextColor(QColor(COLORS['text_dim'])); label.setPos(x2-75, y2-25 if start == '*' else lane)
        self.graph.setSceneRect(self.graph.itemsBoundingRect().adjusted(-15, -15, 15, 15))
        if self.first_graph:
            self.view.fitInView(self.graph.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio);self.first_graph=False

    def accept_data(self):
        try:
            pairs = self.rows(self.states)
            states = dict(pairs)
            if any(not name or not clip for name, clip in pairs) or len(states) != len(pairs):
                raise ValueError('Названия состояний должны быть уникальны; укажите клипы.')
            if (states and self.entry.text().strip() not in states) or (not states and self.entry.text().strip()):
                raise ValueError('Начальное состояние отсутствует.')
            transitions = []
            for start, end, parameter, operation, value in self.rows(self.transitions):
                if start not in ('*', *states) or end not in states or not parameter or operation not in ('==', '!=', '>', '<', '>=', '<='):
                    raise ValueError('Проверьте состояния, параметр и условие перехода.')
                transitions.append(dict(zip(('from', 'to', 'parameter', 'operator', 'value'), (start, end, parameter, operation, json.loads(value)))))
            if hasattr(self,'parameter_table'):
                pairs=self.rows(self.parameter_table)
                if any(not k for k,v in pairs) or len({k for k,v in pairs})!=len(pairs):raise ValueError('Имена параметров должны быть уникальны')
                parameters={k:json.loads(v) for k,v in pairs}
            else:parameters = json.loads(self.parameters.text())
            if not isinstance(parameters, dict):
                raise ValueError('Параметры должны быть JSON-объектом.')
            self.result_data = {'states': states, 'transitions': transitions, 'parameters': parameters,'editor_positions':self.editor_positions}
            self.accept()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Animator', str(exc))
