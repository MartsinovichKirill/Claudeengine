"""Breakpoint controls, live stack and scoped variable inspection."""
from PyQt6.QtCore import QEventLoop
from PyQt6.QtGui import QColor, QTextCursor, QTextCharFormat
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QTextEdit
from engine.systems.script_debugger import ScriptDebugger


def display(value):
    if type(value) in (str, int, float, bool, type(None)):
        return repr(value)[:300]
    if type(value) in (list, tuple, dict, set):
        return f'{type(value).__name__} ({len(value)})'
    return '<' + type(value).__name__ + '>'


class DebuggerPanel(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.loop = None
        self.debugger = ScriptDebugger(on_pause=self.pause)
        layout = QVBoxLayout(self)
        self.status = QLabel('F9 — точка остановки на строке курсора. Отладчик действует при Play.')
        self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout()
        for label, callback in [('Точка (F9)', self.toggle), ('Продолжить (F6)', lambda: self.resume('continue')),
                                ('Войти (F11)', lambda: self.resume('into')), ('Шаг (F10)', lambda: self.resume('over')),
                                ('Выйти (Shift+F11)', lambda: self.resume('out'))]:
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row)
        self.stack = QTreeWidget(); self.stack.setHeaderLabels(['Стек', 'Файл / строка'])
        self.stack.itemClicked.connect(self.select_frame); layout.addWidget(self.stack)
        self.variables = QTreeWidget(); self.variables.setHeaderLabels(['Переменная', 'Значение'])
        layout.addWidget(self.variables, 1)
        self.breakpoint_list = QLabel(); self.breakpoint_list.setWordWrap(True); layout.addWidget(self.breakpoint_list)
        self.frames = []

    def toggle(self):
        editor = self.window.script_editor
        if not editor.path:
            return
        line = editor.editor.textCursor().blockNumber() + 1
        self.debugger.toggle(editor.path, line)
        self.refresh_marks()

    def refresh_marks(self):
        from pathlib import Path
        editor = self.window.script_editor
        key = str(Path(editor.path).resolve()).casefold() if editor.path else ''
        selections = []
        for line in self.debugger.breakpoints.get(key, set()):
            block = editor.editor.document().findBlockByNumber(line - 1)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(block)
                selection.format.setBackground(QColor('#653844'))
                selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
                selections.append(selection)
        editor.editor.setExtraSelections(selections)
        self.breakpoint_list.setText('Точки: ' + '; '.join(Path(path).name + ':' + ','.join(map(str, sorted(lines))) for path, lines in self.debugger.breakpoints.items() if lines))

    def pause(self, frame):
        self.show(); self.window.debugger_dock.show(); self.window.debugger_dock.raise_()
        self.status.setText(f'Остановка: {frame.f_code.co_filename}:{frame.f_lineno}')
        self.frames = []; self.stack.clear()
        current = frame
        while current:
            if self.debugger.contains(current.f_code.co_filename):
                self.frames.append(current)
                QTreeWidgetItem(self.stack, [current.f_code.co_name, f'{current.f_code.co_filename}:{current.f_lineno}'])
            current = current.f_back
        self.show_frame(frame)
        self.loop = QEventLoop(self)
        self.loop.exec()
        self.loop = None; self.frames = []
        self.variables.clear(); self.stack.clear()
        import time
        if self.window.viewport.game_loop:
            self.window.viewport.game_loop._last_time=time.perf_counter()
        self.status.setText('Выполнение продолжается')

    def show_frame(self, frame):
        self.window.script_editor.load_file(frame.f_code.co_filename)
        editor = self.window.script_editor.editor
        block = editor.document().findBlockByNumber(frame.f_lineno - 1)
        editor.setTextCursor(QTextCursor(block)); editor.centerCursor()
        self.variables.clear()
        for name, value in sorted(frame.f_locals.items()):
            item = QTreeWidgetItem(self.variables, [name, display(value)])
            # Inspect stored attributes only; never execute property getters or eval.
            values = value if type(value) is dict else getattr(value, '__dict__', {})
            if isinstance(values, dict):
                for key, child in list(values.items())[:100]:
                    QTreeWidgetItem(item, [str(key), display(child)])
        self.refresh_marks()

    def select_frame(self, item):
        index = self.stack.indexOfTopLevelItem(item)
        if 0 <= index < len(self.frames):
            self.show_frame(self.frames[index])

    def resume(self, mode):
        if self.loop:
            self.debugger.command(mode)
            self.loop.quit()

    def abort(self):
        self.debugger.abort_requested = True
        if self.loop:
            self.loop.quit()
