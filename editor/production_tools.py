"""Entry points for gameplay data, AI authoring and project checks."""
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox,QFileDialog


def open_data(window,path=''):
    if not window.project_dir:
        QMessageBox.information(window,'Игровые данные','Сначала откройте проект.'); return
    try:
        from editor.game_data_editor import GameDataEditor
        dialog=GameDataEditor(window.project_dir,path,window)
        if dialog.exec():
            window.assets.refresh()
            window.console.log('Игровые данные сохранены: '+dialog.saved_path,'INFO')
    except (OSError,ValueError,TypeError) as error: QMessageBox.warning(window,'Игровые данные',str(error))


def install(window):
    menu=window.menuBar().addMenu('Разработка')
    menu.addAction('Новые игровые данные…',lambda:open_data(window))
    def choose():
        path,_=QFileDialog.getOpenFileName(window,'Игровые данные',window.project_dir,'Cloud Game Data (*.gamedata)')
        if path: open_data(window,path)
    menu.addAction('Открыть игровые данные…',choose)
    menu.addSeparator()
    def check():
        if not window.project_dir:
            QMessageBox.information(window,'Проверка проекта','Сначала откройте проект.'); return
        if window.viewport.is_playing:
            QMessageBox.information(window,'Проверка проекта','Остановите Play перед проверкой.'); return
        from editor.project_tests_dialog import ProjectTestsDialog
        dialog=ProjectTestsDialog(window.project_dir,window); dialog.exec()
    menu.addAction('Автоматическая проверка проекта…',check)
    menu.addAction('Открыть последний отчёт',lambda:open_report(window))


def open_report(window):
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtCore import QUrl
    reports=sorted((Path(window.project_dir)/'.cloud-test-reports').glob('*.md')) if window.project_dir else []
    if reports: QDesktopServices.openUrl(QUrl.fromLocalFile(str(reports[-1])))
    else: QMessageBox.information(window,'Отчёт','Сначала выполните проверку проекта.')
