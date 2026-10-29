"""Responsive project checks in bounded child processes, with persisted reports."""
from pathlib import Path
import time
from PyQt6.QtCore import QThread,pyqtSignal,QTimer,Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,
    QSpinBox,QTableWidget,QTableWidgetItem,QPlainTextEdit,QPushButton,QMessageBox)
from engine.testing.project_checks import ProjectCheckRunner,project_files


class CheckThread(QThread):
    progress=pyqtSignal(object); completed=pyqtSignal(object); failed=pyqtSignal(str)
    def __init__(self,runner,parent=None): super().__init__(parent); self.runner=runner
    def run(self):
        try: self.completed.emit(self.runner.run(self.progress.emit))
        except Exception as error:
            import traceback
            self.failed.emit(str(error)+'\n'+traceback.format_exc())


class ProjectTestsDialog(QDialog):
    def __init__(self,project_dir,parent=None,run_immediately=False):
        super().__init__(parent); self.setWindowTitle('Проверка проекта'); self.resize(960,740)
        self.project_dir=Path(project_dir).resolve(); self.thread=None; self.report=None
        self.run_immediately=run_immediately
        root=QVBoxLayout(self); title=QLabel('Проверка проекта'); title.setObjectName('SectionTitle'); root.addWidget(title)
        hint=QLabel('Проверяются сохранённые файлы. Сцены запускаются в отдельных процессах на копии проекта. Это проверка ошибок запуска, а не проходимости игры.'); hint.setWordWrap(True); root.addWidget(hint)
        row=QHBoxLayout(); self.scenes=QListWidget(); self.scenes.setMaximumHeight(150)
        for path in project_files(self.project_dir,'.scene'):
            item=QListWidgetItem(path.relative_to(self.project_dir).as_posix()); item.setCheckState(Qt.CheckState.Checked); self.scenes.addItem(item)
        root.addWidget(self.scenes)
        self.frames=QSpinBox(); self.frames.setRange(1,3600); self.frames.setValue(120)
        self.timeout=QSpinBox(); self.timeout.setRange(1,120); self.timeout.setValue(15)
        row.addWidget(QLabel('Кадров на сцену')); row.addWidget(self.frames); row.addWidget(QLabel('Лимит процесса, с')); row.addWidget(self.timeout); row.addStretch(); root.addLayout(row)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Сцена / файл','Результат','Сообщение']); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0,240); self.table.setColumnWidth(1,130); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.itemSelectionChanged.connect(self.details_changed)
        root.addWidget(self.table,1); self.details=QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(130); root.addWidget(self.details)
        self.status=QLabel('Готово к проверке'); self.status.setWordWrap(True); root.addWidget(self.status)
        row=QHBoxLayout(); self.start=QPushButton('Запустить проверку'); self.start.setProperty('primary',True); self.start.clicked.connect(self.start_checks); row.addWidget(self.start)
        self.cancel=QPushButton('Остановить'); self.cancel.setEnabled(False); self.cancel.clicked.connect(self.cancel_checks); row.addWidget(self.cancel)
        self.continue_button=QPushButton('Продолжить сборку' if run_immediately else 'Готово'); self.continue_button.setEnabled(False); self.continue_button.clicked.connect(self.accept); row.addWidget(self.continue_button)
        self.close_button=QPushButton('Закрыть'); self.close_button.clicked.connect(self.reject); row.addWidget(self.close_button); root.addLayout(row)
        self.records=[]
        if run_immediately: QTimer.singleShot(0,self.start_checks)

    def start_checks(self):
        if self.thread and self.thread.isRunning(): return
        scenes=[self.scenes.item(i).text() for i in range(self.scenes.count()) if self.scenes.item(i).checkState()==Qt.CheckState.Checked]
        if not scenes: QMessageBox.information(self,'Сцены','Выберите хотя бы одну сцену.'); return
        self.records=[]; self.table.setRowCount(0); self.report=None; self.continue_button.setEnabled(False)
        self.report_path=self.project_dir/'.cloud-test-reports'/('check-'+str(time.time_ns())+'.json')
        runner=ProjectCheckRunner(self.project_dir,self.report_path,scenes,self.frames.value(),self.timeout.value())
        self.thread=CheckThread(runner,self); self.thread.progress.connect(self.add_record); self.thread.completed.connect(self.completed); self.thread.failed.connect(self.failed)
        self.thread.finished.connect(self.finished_checks)
        self.start.setEnabled(False); self.cancel.setEnabled(True); self.scenes.setEnabled(False); self.status.setText('Проверка проекта…'); self.thread.start()

    def add_record(self,record):
        if record['status']=='running': self.status.setText('Запуск: '+record['path']); return
        self.records.append(record); row=self.table.rowCount(); self.table.insertRow(row)
        labels={'passed':'Пройдено','failed':'Ошибка','timeout':'Превышен лимит'}
        for column,value in enumerate([record.get('path',''),labels.get(record['status'],record['status']),record['message'].splitlines()[0]]):
            item=QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(row,column,item)
        self.table.selectRow(row)

    def details_changed(self):
        row=self.table.currentRow()
        if 0<=row<len(self.records):
            record=self.records[row]; self.details.setPlainText(record['message']+'\n'+'\n'.join(record.get('errors',[])))

    def completed(self,report):
        self.report=report
        self.status.setText(('Проверка пройдена.' if report['passed'] else 'Проверка не пройдена.' )+' Отчёты: '+str(self.report_path)+' и .md')
        if self.thread is None or not self.thread.isRunning():
            self.continue_button.setEnabled(report['passed'] or not self.run_immediately)

    def failed(self,error): self.status.setText('Не удалось закончить проверку'); self.details.setPlainText(error)
    def finished_checks(self):
        self.start.setEnabled(True); self.cancel.setEnabled(False); self.scenes.setEnabled(True)
        if self.report: self.continue_button.setEnabled(self.report['passed'] or not self.run_immediately)
    def cancel_checks(self):
        if self.thread and self.thread.isRunning(): self.thread.runner.cancel(); self.status.setText('Остановка проверочного процесса…')
    def reject(self):
        if self.thread and self.thread.isRunning(): self.cancel_checks(); return
        super().reject()
    def closeEvent(self,event):
        if self.thread and self.thread.isRunning(): self.cancel_checks(); event.ignore()
        else: event.accept()
