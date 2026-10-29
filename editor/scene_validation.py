"""Editor navigation for shared read-only validation."""
from engine.testing.scene_validation import SceneIssue, validate_scene

def show_scene_issues(editor, issues):
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton
    dialog = QDialog(editor)
    dialog.setWindowTitle('Проверка сцены')
    dialog.resize(720, 380)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('Исправьте ошибки перед запуском. Выберите строку для выделения объекта; двойной щелчок открывает скрипт.'))
    items = QListWidget()
    for issue in issues:
        items.addItem((getattr(issue.node, 'name', 'Сцена')) + ' — ' + issue.message)
    def focus(row):
        if 0 <= row < len(issues) and issues[row].node is not None:
            editor.hierarchy.select_node(issues[row].node)
    items.currentRowChanged.connect(focus)
    def open_issue(item):
        issue = issues[items.row(item)]
        if issue.path:
            editor.open_script_location(issue.path, issue.line)
            dialog.accept()
    items.itemDoubleClicked.connect(open_issue)
    layout.addWidget(items)
    close = QPushButton('Закрыть')
    close.clicked.connect(dialog.accept)
    layout.addWidget(close)
    dialog.exec()
