"""Table editor for typed, reusable gameplay records."""
import json
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,
    QTableWidget,QTableWidgetItem,QPushButton,QDialogButtonBox,QMessageBox,QFileDialog)
from engine.resources.game_data import FIELD_TYPES,TEMPLATES,template,save_document,validate_document,project_path

TYPE_LABELS={'int':'Целое число','float':'Число','bool':'Флаг','string':'Текст','vector2':'Вектор XY','color':'Цвет RGBA','resource':'Ресурс'}


class GameDataEditor(QDialog):
    def __init__(self,project_dir,path='',parent=None):
        super().__init__(parent); self.setWindowTitle('Игровые данные'); self.resize(860,600)
        self.project_dir=Path(project_dir).resolve(); self.path=str(path) if path else ''; self.saved_path=''
        layout=QVBoxLayout(self)
        title=QLabel('Игровые данные'); title.setObjectName('SectionTitle'); layout.addWidget(title)
        hint=QLabel('Один файл используется разными объектами. Изменения сохраняются только после нажатия «Сохранить».'); hint.setWordWrap(True); hint.setObjectName('SecondaryText'); layout.addWidget(hint)
        row=QHBoxLayout(); self.name=QLineEdit(); self.name.setPlaceholderText('Название записи')
        self.kind=QComboBox()
        for name,label in [('weapon','Оружие'),('enemy','Враг'),('item','Предмет'),('custom','Свои данные')]: self.kind.addItem(label,name)
        row.addWidget(self.name,1); row.addWidget(self.kind); layout.addLayout(row)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Имя поля','Тип','Значение'])
        self.table.horizontalHeader().setStretchLastSection(True); self.table.setColumnWidth(0,220); self.table.setColumnWidth(1,170)
        self.table.verticalHeader().setDefaultSectionSize(39)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); layout.addWidget(self.table,1)
        row=QHBoxLayout()
        for label,action in [('Добавить поле',self.add_field),('Удалить поле',self.remove_field),('Взять поля шаблона',self.use_template)]:
            button=QPushButton(label); button.clicked.connect(action); row.addWidget(button)
        layout.addLayout(row)
        hint=QLabel('Числа: 12 или 0.5 • Флаг: true / false • Вектор: [0, 10] • Цвет: [255, 120, 0, 255]'); hint.setWordWrap(True); layout.addWidget(hint)
        self.path_label=QLabel(self.path or 'Новый файл .gamedata'); self.path_label.setObjectName('SecondaryText'); layout.addWidget(self.path_label)
        buttons=QDialogButtonBox(); buttons.addButton('Сохранить',QDialogButtonBox.ButtonRole.AcceptRole); buttons.addButton('Отмена',QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        if path:
            data=json.loads(project_path(self.project_dir,path).read_text(encoding='utf-8-sig')); validate_document(data,self.project_dir); self.fill(data)
        else: self.fill(template('weapon','Новое оружие'))

    def fill(self,data):
        self.name.setText(data['name']); self.kind.setCurrentIndex(self.kind.findData(data['kind'])); self.table.setRowCount(0)
        for name,field in data['fields'].items(): self.add_field(False,name,field['type'],field['value'])

    def add_field(self,checked=False,name='',kind='float',value=0.0):
        row=self.table.rowCount(); self.table.insertRow(row)
        self.table.setItem(row,0,QTableWidgetItem(name)); combo=QComboBox()
        for key in FIELD_TYPES: combo.addItem(TYPE_LABELS[key],key)
        combo.setCurrentIndex(combo.findData(kind)); self.table.setCellWidget(row,1,combo)
        self.table.setItem(row,2,QTableWidgetItem(value if kind in ('string','resource') else json.dumps(value,ensure_ascii=False)))

    def remove_field(self):
        if self.table.currentRow()>=0: self.table.removeRow(self.table.currentRow())

    def use_template(self):
        if self.table.rowCount() and QMessageBox.question(self,'Шаблон','Заменить текущие поля выбранным шаблоном?')!=QMessageBox.StandardButton.Yes: return
        self.fill(template(self.kind.currentData(),self.name.text().strip() or 'Новая запись'))

    def document(self):
        fields={}
        for row in range(self.table.rowCount()):
            name=self.table.item(row,0).text().strip() if self.table.item(row,0) else ''
            if name in fields: raise ValueError('Повторяется имя поля: '+name)
            kind=self.table.cellWidget(row,1).currentData(); value=self.table.item(row,2).text() if self.table.item(row,2) else ''
            if kind not in ('string','resource'):
                try: value=json.loads(value)
                except ValueError: raise ValueError(f'Поле {name}: неверное значение. Число записывается через точку; флаг — true / false.')
            fields[name]={'type':kind,'value':value}
        data={'version':1,'kind':self.kind.currentData(),'name':self.name.text().strip(),'fields':fields}
        validate_document(data,self.project_dir); return data

    def save(self):
        try:
            data=self.document(); path=self.path
            if not path:
                path,_=QFileDialog.getSaveFileName(self,'Сохранить игровые данные',str(self.project_dir/'data'/'new.gamedata'),'Cloud Game Data (*.gamedata)')
                if not path: return
                if not path.endswith('.gamedata'): path+='.gamedata'
            save_document(path,data,self.project_dir); self.saved_path=path; self.accept()
        except (OSError,ValueError,TypeError) as error: QMessageBox.warning(self,'Игровые данные',str(error))
