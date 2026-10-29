"""Compact error list with complete details and source navigation."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,
                            QPlainTextEdit,QPushButton,QApplication,QLabel)


class ProblemsPanel(QWidget):
    location_requested=pyqtSignal(str,int)
    node_requested=pyqtSignal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.entries=[]; self.signatures={}
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['Объект','Причина','Место','Повторы'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(1,420); self.table.setColumnWidth(2,220)
        self.table.itemSelectionChanged.connect(self.select); self.table.itemDoubleClicked.connect(lambda _:self.open_source())
        layout.addWidget(self.table,1)
        self.details=QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(170); layout.addWidget(self.details)
        toolbar=QHBoxLayout(); self.count=QLabel('Ошибок нет'); toolbar.addWidget(self.count); toolbar.addStretch()
        for title,callback in [('К месту ошибки',self.open_source),('Выбрать объект',self.select_node),('Копировать отчёт',self.copy),('Очистить',self.clear)]:
            button=QPushButton(title); button.clicked.connect(callback); toolbar.addWidget(button)
        layout.addLayout(toolbar)

    def add(self,diagnostic):
        signature=(diagnostic.path,diagnostic.line,diagnostic.node,diagnostic.message)
        if signature in self.signatures:
            row=self.signatures[signature]; count=int(self.table.item(row,3).text())+1; self.table.item(row,3).setText(str(count)); return
        if len(self.entries)>=250: return
        row=len(self.entries); self.entries.append(diagnostic); self.signatures[signature]=row
        self.table.insertRow(row)
        place=f'{diagnostic.path}:{diagnostic.line}' if diagnostic.path else 'Подробности ниже'
        for column,value in enumerate([diagnostic.node or '—',diagnostic.message,place,'1']):
            item=QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(row,column,item)
        self.count.setText(f'Проблем: {len(self.entries)}'); self.table.selectRow(row)

    def current(self):
        row=self.table.currentRow()
        return self.entries[row] if 0<=row<len(self.entries) else None

    def select(self):
        entry=self.current()
        if entry: self.details.setPlainText(entry.message+'\n\nЧто проверить: '+entry.hint+'\n\n'+entry.details)

    def open_source(self):
        entry=self.current()
        if entry and entry.path: self.location_requested.emit(entry.path,entry.line)

    def select_node(self):
        entry=self.current()
        if entry and entry.node: self.node_requested.emit(entry.node)

    def copy(self):
        entry=self.current()
        if entry: QApplication.clipboard().setText(f'{entry.node}\n{entry.path}:{entry.line}:{entry.column}\n'+self.details.toPlainText())

    def clear(self):
        self.entries.clear(); self.signatures.clear(); self.table.setRowCount(0); self.details.clear(); self.count.setText('Ошибок нет')
