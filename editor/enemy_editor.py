"""Editable, draggable state graph for EnemyAI; no scene mutation until Apply."""
import copy
import json
from pathlib import Path
from PyQt6.QtCore import Qt,QPointF,QRectF,QTimer
from PyQt6.QtGui import QPainter,QColor,QPen,QPainterPath,QBrush,QPolygonF
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QGraphicsObject,QGraphicsScene,QGraphicsView,
    QGraphicsItem,QLabel,QPushButton,QListWidget,QFormLayout,QWidget,QComboBox,QDoubleSpinBox,
    QInputDialog,QTableWidget,QTableWidgetItem,QDialogButtonBox,QMessageBox,QFileDialog,QSplitter)
from engine.components.enemy_ai import ACTIONS,CONDITIONS,OPERATORS,default_graph,validate_graph

ACTION_LABELS={'wait':'Ожидание','patrol':'Патруль','chase':'Погоня','attack':'Атака','custom':'Свой скрипт'}
CONDITION_LABELS={'target_visible':'Цель в радиусе обнаружения','target_lost':'Цель потеряна','in_attack_range':'Цель в радиусе атаки','out_attack_range':'Цель вне радиуса атаки','timeout':'Прошло время состояния','parameter':'Значение параметра'}


class StateCard(QGraphicsObject):
    def __init__(self,name,action,entry,moved):
        super().__init__(); self.name=name; self.action=action; self.entry=entry; self.moved=moved
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemIsSelectable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

    def boundingRect(self): return QRectF(0,0,180,76)
    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#80b5dd' if self.isSelected() else '#425566'),2 if self.isSelected() else 1))
        painter.setBrush(QColor('#263b4c' if self.isSelected() else '#202a34')); painter.drawRoundedRect(self.boundingRect(),8,8)
        painter.setPen(QColor('#edf3f9')); painter.drawText(QRectF(12,10,156,24),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,self.name)
        painter.setPen(QColor('#8cb8d3')); painter.drawText(QRectF(12,40,156,22),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,('● ' if self.entry else '')+ACTION_LABELS[self.action])
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged: self.moved(self)
        return super().itemChange(change,value)


class EnemyEditor(QDialog):
    def __init__(self,component,parent=None):
        super().__init__(parent); self.setWindowTitle('Поведение врага — EnemyAI'); self.resize(1100,760)
        self.data=copy.deepcopy(component.graph); self.result_data=None; self.cards={}; self.edges=[]; self._building=False
        root=QVBoxLayout(self)
        title=QLabel('Поведение врага'); title.setObjectName('SectionTitle'); root.addWidget(title)
        hint=QLabel('Перетаскивайте состояния на графе. Переходы проверяются сверху вниз, один за физический шаг. Атака вызывает сигнал или ваш метод.'); hint.setWordWrap(True); root.addWidget(hint)
        toolbar=QHBoxLayout()
        for text,callback in [('Добавить состояние',self.add_state),('Переименовать',self.rename_state),('Удалить',self.remove_state),('Связать состояния',self.add_transition),('Загрузить граф…',self.load_graph),('Сохранить граф…',self.save_graph)]:
            button=QPushButton(text); button.clicked.connect(callback); toolbar.addWidget(button)
        root.addLayout(toolbar)
        splitter=QSplitter(); panel=QWidget(); form=QFormLayout(panel)
        self.states=QListWidget(); self.states.currentTextChanged.connect(self.select_state); form.addRow(self.states)
        self.entry=QComboBox(); self.entry.currentTextChanged.connect(self.change_entry); form.addRow('Старт',self.entry)
        self.action=QComboBox()
        for key in ACTIONS: self.action.addItem(ACTION_LABELS[key],key)
        self.action.currentIndexChanged.connect(self.change_state); form.addRow('Действие',self.action)
        self.duration=QDoubleSpinBox(); self.duration.setRange(0,3600); self.duration.setValue(1); self.duration.valueChanged.connect(self.change_state)
        form.addRow('Время, с',self.duration)
        self.graph=QGraphicsScene(self); self.graph.setBackgroundBrush(QColor('#151d25'))
        self.view=QGraphicsView(self.graph); self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.graph.selectionChanged.connect(self.select_card)
        splitter.addWidget(panel); splitter.addWidget(self.view); splitter.setSizes([240,820]); root.addWidget(splitter,1)
        self.transitions=QTableWidget(0,6); self.transitions.setHorizontalHeaderLabels(['Из','В','Условие','Параметр','Оператор','Значение JSON'])
        self.transitions.verticalHeader().setDefaultSectionSize(39)
        self.transitions.horizontalHeader().setStretchLastSection(True); self.transitions.setMaximumHeight(190); self.transitions.setColumnWidth(2,230)
        root.addWidget(self.transitions)
        row=QHBoxLayout(); remove=QPushButton('Удалить переход'); remove.clicked.connect(self.remove_transition); row.addWidget(remove)
        up=QPushButton('Выше приоритет'); up.clicked.connect(lambda:self.move_transition(-1)); row.addWidget(up)
        down=QPushButton('Ниже приоритет'); down.clicked.connect(lambda:self.move_transition(1)); row.addWidget(down)
        parameters=QPushButton('Параметры…'); parameters.clicked.connect(self.edit_parameters); row.addWidget(parameters); root.addLayout(row)
        buttons=QDialogButtonBox(); buttons.addButton('Применить',QDialogButtonBox.ButtonRole.AcceptRole); buttons.addButton('Отмена',QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.apply); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.rebuild()

    def sync_transitions(self):
        if self._building: return
        transitions=[]
        for row in range(self.transitions.rowCount()):
            read=lambda col:self.transitions.item(row,col).text().strip() if self.transitions.item(row,col) else ''
            condition=self.transitions.cellWidget(row,2).currentData()
            entry={'from':self.transitions.cellWidget(row,0).currentText(),'to':self.transitions.cellWidget(row,1).currentText(),'condition':condition}
            if condition=='parameter': entry.update(parameter=read(3),operator=self.transitions.cellWidget(row,4).currentText(),value=json.loads(read(5)))
            transitions.append(entry)
        self.data['transitions']=transitions

    def rebuild(self):
        current=self.states.currentItem().text() if self.states.currentItem() else ''
        self._building=True; self.states.clear(); self.entry.clear(); self.graph.clear(); self.cards={}; self.edges=[]
        self.states.addItems(self.data['states']); self.entry.addItems(self.data['states']); self.entry.setCurrentText(self.data['entry'])
        for i,(name,state) in enumerate(self.data['states'].items()):
            card=StateCard(name,state['action'],name==self.data['entry'],self.card_moved)
            self.graph.addItem(card); self.cards[name]=card
            card.setPos(*self.data.get('positions',{}).get(name,[(i%3)*260,(i//3)*150]))
        self.transitions.setRowCount(0)
        for transition in self.data['transitions']:
            row=self.transitions.rowCount(); self.transitions.insertRow(row)
            for col,key,values in [(0,'from',['*',*self.data['states']]),(1,'to',list(self.data['states'])),(2,'condition',list(CONDITIONS)),(4,'operator',list(OPERATORS))]:
                combo=QComboBox()
                for value in values: combo.addItem(CONDITION_LABELS.get(value,value),value)
                combo.setCurrentIndex(max(0,combo.findData(transition.get(key,'==')))); self.transitions.setCellWidget(row,col,combo)
                combo.currentIndexChanged.connect(self.transition_changed)
            self.transitions.setItem(row,3,QTableWidgetItem(transition.get('parameter','')))
            self.transitions.setItem(row,5,QTableWidgetItem(json.dumps(transition.get('value',True),ensure_ascii=False)))
        try: self.transitions.itemChanged.disconnect(self.transition_changed)
        except TypeError: pass
        self.transitions.itemChanged.connect(self.transition_changed)
        self._building=False; self.redraw_edges()
        for index in range(self.states.count()):
            if self.states.item(index).text()==current: self.states.setCurrentRow(index); break
        if self.states.currentRow()<0 and self.states.count(): self.states.setCurrentRow(0)
        QTimer.singleShot(0,self.fit_graph)

    def fit_graph(self):
        self.view.fitInView(self.graph.itemsBoundingRect().adjusted(-35,-50,35,50),Qt.AspectRatioMode.KeepAspectRatio)
        if self.view.transform().m11()>1.2:
            self.view.resetTransform(); self.view.scale(1.2,1.2)

    def showEvent(self,event):
        super().showEvent(event); QTimer.singleShot(0,self.fit_graph)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'view'): QTimer.singleShot(0,self.fit_graph)

    def card_moved(self,card):
        if self._building: return
        self.data.setdefault('positions',{})[card.name]=[card.pos().x(),card.pos().y()]; self.redraw_edges()

    def redraw_edges(self):
        for item in self.edges: self.graph.removeItem(item)
        self.edges=[]
        for i,transition in enumerate(self.data['transitions']):
            first=self.cards.get(transition['from']); second=self.cards.get(transition['to'])
            if not second: continue
            end=second.pos()+QPointF(0,38); start=first.pos()+QPointF(180,38) if first else end+QPointF(-140,-70)
            bend=-85-i*12 if start.x()>end.x() else 75+i*10
            path=QPainterPath(start); path.cubicTo(start+QPointF(70,bend),end+QPointF(-70,bend),end)
            line=self.graph.addPath(path,QPen(QColor('#688ca8'),2)); line.setZValue(-1); self.edges.append(line)
            arrow=self.graph.addPolygon(QPolygonF([end,end+QPointF(-10,-5),end+QPointF(-10,5)]),QPen(Qt.PenStyle.NoPen),QBrush(QColor('#688ca8'))); self.edges.append(arrow)
            short={'target_visible':'Цель рядом','target_lost':'Цель потеряна','in_attack_range':'Дистанция атаки','out_attack_range':'Цель отошла','timeout':'Таймер','parameter':'Параметр'}
            label=self.graph.addText(str(i+1)+' · '+short[transition['condition']]); label.setDefaultTextColor(QColor('#a2b2c1')); label.setToolTip(CONDITION_LABELS[transition['condition']])
            label.setPos(path.pointAtPercent(.5)+QPointF(-50,-22)); self.edges.append(label)

    def select_state(self,name):
        if self._building or name not in self.data['states']: return
        state=self.data['states'][name]; self.action.blockSignals(True); self.duration.blockSignals(True)
        self.action.setCurrentIndex(self.action.findData(state['action'])); self.duration.setValue(state.get('duration',1))
        self.action.blockSignals(False); self.duration.blockSignals(False)
        for key,card in self.cards.items(): card.setSelected(key==name)

    def select_card(self):
        selected=self.graph.selectedItems()
        if selected and isinstance(selected[0],StateCard):
            matches=self.states.findItems(selected[0].name,Qt.MatchFlag.MatchExactly)
            if matches: self.states.setCurrentItem(matches[0])

    def change_state(self,*_):
        item=self.states.currentItem()
        if self._building or not item: return
        state=self.data['states'][item.text()]; state['action']=self.action.currentData(); state['duration']=self.duration.value()
        self.cards[item.text()].action=state['action']; self.cards[item.text()].update()

    def change_entry(self,name):
        if self._building: return
        self.data['entry']=name
        for key,card in self.cards.items(): card.entry=key==name; card.update()

    def transition_changed(self,*_):
        if self._building: return
        try: self.sync_transitions(); self.redraw_edges()
        except ValueError: pass  # The user may still be typing a JSON value.

    def add_state(self):
        name,ok=QInputDialog.getText(self,'Состояние','Уникальное имя:')
        if ok and name.strip() and name.strip() not in self.data['states']:
            self.data['states'][name.strip()]={'action':'wait','duration':1}; self.rebuild()

    def rename_state(self):
        item=self.states.currentItem()
        if not item: return
        old=item.text(); name,ok=QInputDialog.getText(self,'Состояние','Новое имя:',text=old); name=name.strip()
        if not ok or not name or name in self.data['states']: return
        self.data['states'][name]=self.data['states'].pop(old)
        if self.data['entry']==old: self.data['entry']=name
        if old in self.data.get('positions',{}): self.data['positions'][name]=self.data['positions'].pop(old)
        for transition in self.data['transitions']:
            for key in ('from','to'):
                if transition[key]==old: transition[key]=name
        self.rebuild()

    def remove_state(self):
        item=self.states.currentItem()
        if not item or len(self.data['states'])<=1: return
        name=item.text(); self.data['states'].pop(name); self.data.get('positions',{}).pop(name,None)
        self.data['transitions']=[t for t in self.data['transitions'] if name not in (t['from'],t['to'])]
        if self.data['entry']==name: self.data['entry']=next(iter(self.data['states']))
        self.rebuild()

    def add_transition(self):
        names=list(self.data['states']); start,ok=QInputDialog.getItem(self,'Переход','Из состояния:',['*',*names],0,False)
        if not ok: return
        end,ok=QInputDialog.getItem(self,'Переход','В состояние:',names,0,False)
        if ok: self.data['transitions'].append({'from':start,'to':end,'condition':'target_visible'}); self.rebuild()

    def remove_transition(self):
        row=self.transitions.currentRow()
        if row>=0: self.data['transitions'].pop(row); self.rebuild()

    def move_transition(self,offset):
        row=self.transitions.currentRow(); destination=row+offset
        if row>=0 and 0<=destination<len(self.data['transitions']):
            self.data['transitions'][row],self.data['transitions'][destination]=self.data['transitions'][destination],self.data['transitions'][row]
            self.rebuild(); self.transitions.selectRow(destination)

    def edit_parameters(self):
        text,ok=QInputDialog.getMultiLineText(self,'Параметры','JSON-объект, например {"health": 3}:',json.dumps(self.data.get('parameters',{}),ensure_ascii=False,indent=2))
        if ok:
            try:
                value=json.loads(text)
                if not isinstance(value,dict): raise ValueError('Нужен JSON-объект')
                self.data['parameters']=value
            except ValueError as error: QMessageBox.warning(self,'Параметры',str(error))

    def validated(self): self.sync_transitions(); return validate_graph(self.data)
    def apply(self):
        try: self.result_data={'graph':self.validated()}; self.accept()
        except (ValueError,TypeError) as error: QMessageBox.warning(self,'Граф',str(error))

    def save_graph(self):
        try: data=self.validated()
        except (ValueError,TypeError) as error: QMessageBox.warning(self,'Граф',str(error)); return
        path,_=QFileDialog.getSaveFileName(self,'Граф поведения','','Cloud Behavior (*.behavior)')
        if path:
            if not path.endswith('.behavior'): path+='.behavior'
            try: Path(path).write_text(json.dumps({'version':1,'graph':data},ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error: QMessageBox.warning(self,'Граф',str(error))

    def load_graph(self):
        path,_=QFileDialog.getOpenFileName(self,'Граф поведения','','Cloud Behavior (*.behavior)')
        if path:
            try: self.data=validate_graph(json.loads(Path(path).read_text(encoding='utf-8'))['graph']); self.rebuild()
            except (OSError,ValueError,KeyError,TypeError) as error: QMessageBox.warning(self,'Граф',str(error))
