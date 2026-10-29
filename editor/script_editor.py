"""ScriptEditor — встроенный редактор кода с подсветкой синтаксиса Python."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from PyQt6.QtCore import Qt, QRegularExpression, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton)

logger = logging.getLogger("cloudengine.script_editor")

# Цвета подсветки (Godot-подобная палитра).
_COLOR_KEYWORD = QColor("#c678dd")
_COLOR_STRING = QColor("#98c379")
_COLOR_COMMENT = QColor("#7f8c8d")
_COLOR_NUMBER = QColor("#d19a66")
_COLOR_BUILTIN = QColor("#e5c07b")
_COLOR_DEF = QColor("#61afef")
_COLOR_SELF = QColor("#e06c75")


class PythonHighlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса Python."""

    def __init__(self, document: Any) -> None:
        super().__init__(document)
        self.rules: list = []
        self._build_rules()

    def _build_rules(self) -> None:
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(_COLOR_KEYWORD)
        keyword_fmt.setFontWeight(QFont.Weight.Bold)
        keywords = ["script", "extends", "on", "let", "const", "func", "export", "signal", "true", "false", "null", "public", "override", "void", "double", "using", "def", "class", "import", "from", "return", "if", "elif",
                    "else", "for", "while", "in", "not", "and", "or", "pass",
                    "break", "continue", "lambda", "global", "with", "as",
                    "try", "except", "finally", "raise", "yield", "None",
                    "True", "False", "is", "del", "assert", "async", "await"]
        for kw in keywords:
            self.rules.append((QRegularExpression(rf"\b{kw}\b"), keyword_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(_COLOR_STRING)
        self.rules.append((QRegularExpression(r"(\"[^\"]*\"|'[^']*')"), string_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(_COLOR_COMMENT)
        comment_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(_COLOR_NUMBER)
        self.rules.append((QRegularExpression(r"\b\d+(\.\d+)?\b"), number_fmt))

        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(_COLOR_BUILTIN)
        builtins = ["print", "len", "range", "int", "float", "str", "bool",
                    "list", "dict", "tuple", "set", "super", "isinstance",
                    "getattr", "setattr", "hasattr", "abs", "min", "max",
                    "round", "sum", "enumerate", "zip"]
        for name in builtins:
            self.rules.append((QRegularExpression(rf"\b{name}\b"), builtin_fmt))

        def_fmt = QTextCharFormat()
        def_fmt.setForeground(_COLOR_DEF)
        self.rules.append((QRegularExpression(r"\bdef\s+(\w+)"), def_fmt))

        self_fmt = QTextCharFormat()
        self_fmt.setForeground(_COLOR_SELF)
        self.rules.append((QRegularExpression(r"\bself\b"), self_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class ScriptEditor(QWidget):
    """Редактор Python-скриптов."""

    saved = pyqtSignal(str)  # путь

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.path: str = ""
        self.project_dir = ''
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)
        self.path_label = QLabel("Нет открытого скрипта")
        self.path_label.setStyleSheet("color: #9e9e9e;")
        toolbar.addWidget(self.path_label)
        toolbar.addStretch(1)
        self.save_btn = QPushButton("Сохранить (Ctrl+S)")
        self.save_btn.clicked.connect(self.save)
        toolbar.addWidget(self.save_btn)
        layout.addLayout(toolbar)

        from editor.cloud_code_edit import CloudCodeEdit
        self.editor = CloudCodeEdit()
        self.editor.definition_requested.connect(self.goto_definition)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(
            4 * self.editor.fontMetrics().horizontalAdvance(" "))
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.editor)

        self.highlighter = PythonHighlighter(self.editor.document())
        self.diagnostics = QLabel('Cloud Scripts · Ctrl+Space: подсказки · F12: определение')
        self.diagnostics.setWordWrap(True)
        layout.addWidget(self.diagnostics)
        self.diagnostics.linkActivated.connect(lambda _: self.goto_line(getattr(self, "_diagnostic_line", 1)))
        self.check_timer = QTimer(self)
        self.check_timer.setSingleShot(True)
        self.check_timer.setInterval(450)
        self.check_timer.timeout.connect(self.check_syntax)
        self.editor.textChanged.connect(lambda: self.check_timer.start())

    def goto_line(self, line):
        block = self.editor.document().findBlockByNumber(max(0, int(line) - 1))
        if block.isValid():
            cursor = self.editor.textCursor()
            cursor.setPosition(block.position())
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()
            self.editor.setFocus()

    def check_syntax(self):
        if not self.path.endswith('.cloud'):
            return
        from engine.systems.cloud_scripts import compile_cloud
        try:
            compile_cloud(self.editor.toPlainText(), self.path)
            self.diagnostics.setText('✓ Синтаксис Cloud Scripts проверен · Ctrl+Space · F12')
            self.diagnostics.setStyleSheet('color: #8fc7a0')
        except (SyntaxError, IndentationError) as exc:
            import html
            self._diagnostic_line = exc.lineno or 1
            self.diagnostics.setText(f'<a href="error">Строка {exc.lineno}, столбец {exc.offset}: {html.escape(str(exc.msg))}</a>')
            self.diagnostics.setStyleSheet('color: #ef9595')
        except Exception as exc:
            self.diagnostics.setText(str(exc))

    # ------------------------------------------------------------------
    # Работа с файлами
    # ------------------------------------------------------------------
    def load_file(self, path: str) -> None:
        if self.path and self.path != path and self.is_modified() and not self.save():
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self.editor.setPlainText(fh.read())
            self.path = path
            self.path_label.setText(path)
            self.editor.document().setModified(False)
        except Exception as exc:
            logger.warning("Не удалось открыть скрипт %s: %s", path, exc)

    def save(self) -> bool:
        if not self.path:
            return False
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(self.editor.toPlainText())
            self.saved.emit(self.path)
            self.editor.document().setModified(False)
            return True
        except Exception as exc:
            logger.error("Не удалось сохранить %s: %s", self.path, exc)
            return False

    def new_file(self, path: str, template: str = "") -> None:
        self.editor.setPlainText(template)
        self.path = path
        self.path_label.setText(path)

    def is_modified(self) -> bool:
        return self.editor.document().isModified()

    def goto_definition(self, name):
        import re
        from pathlib import Path
        from PyQt6.QtGui import QTextCursor
        pattern = re.compile(r'^\s*(?:func|def|class|script|export|let|const)\s+' + re.escape(name) + r'\b', re.M)
        paths = [Path(self.path)] if self.path else []
        if self.project_dir:
            paths += sorted(Path(self.project_dir, 'scripts').rglob('*.cloud'))
        for path in dict.fromkeys(paths):
            try:
                source = self.editor.toPlainText() if str(path) == self.path else path.read_text(encoding='utf-8-sig')
                match = pattern.search(source)
                if not match:
                    continue
                if str(path) != self.path:
                    if self.is_modified() and not self.save():
                        return
                    self.load_file(str(path))
                cursor = self.editor.textCursor()
                cursor.setPosition(match.start())
                self.editor.setTextCursor(cursor)
                self.editor.centerCursor()
                return
            except OSError:
                continue
        from engine.nodes import NODE_CLASSES
        import inspect
        for cls in NODE_CLASSES.values():
            value = getattr(cls, name, None)
            if name == cls.__name__:
                value = cls
            if value is None:
                continue
            try:
                file = inspect.getsourcefile(value)
                _, line = inspect.getsourcelines(value)
                if file and os.path.isfile(file):
                    if self.is_modified() and not self.save():
                        return
                    self.load_file(file)
                    cursor = self.editor.textCursor()
                    cursor.setPosition(self.editor.document().findBlockByNumber(line - 1).position())
                    self.editor.setTextCursor(cursor); self.editor.centerCursor()
                    return
            except (TypeError, OSError):
                continue
