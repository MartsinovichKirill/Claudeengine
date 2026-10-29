"""Completion, documentation and definition lookup without executing user code."""
import inspect
import re
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QStringListModel
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit, QCompleter, QToolTip


class CloudCodeEdit(QPlainTextEdit):
    definition_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.api = {}
        from engine.nodes import NODE_CLASSES
        from engine.math.vector2 import Vector2
        from engine.components.behaviour import Behaviour
        from engine.components.registry import COMPONENT_CLASSES
        for cls in [*NODE_CLASSES.values(), *COMPONENT_CLASSES.values(), Behaviour, Vector2]:
            self.api.setdefault(cls.__name__, inspect.getdoc(cls) or cls.__name__)
            props = getattr(cls, 'get_exported_properties', lambda: {})()
            for name, spec in props.items():
                self.api.setdefault(name, f'{cls.__name__}.{name}: {spec.get("type", "value")}\n{spec.get("hint", "")}')
            for name in dir(cls):
                if name.startswith('__'):
                    continue
                value = getattr(cls, name, None)
                if callable(value):
                    try:
                        signature = str(inspect.signature(value))
                    except (ValueError, TypeError):
                        signature = '(…)'
                    self.api.setdefault(name, cls.__name__ + '.' + name + signature + '\n' + (inspect.getdoc(value) or ''))
        self.completer = QCompleter(self)
        self.completion_model = QStringListModel(self.completer)
        self.completer.setModel(self.completion_model)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.activated.connect(self.insert_completion)

    def word(self, position=None):
        cursor = self.cursorForPosition(position) if position is not None else self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def symbols(self):
        source = self.toPlainText()
        before = source[:self.textCursor().position()]
        receiver = re.search(r'([\w.]+)\.\w*$', before)
        if receiver:
            from engine.nodes import NODE_CLASSES
            from engine.math.vector2 import Vector2
            value = receiver[1]
            cls = None
            if value == 'self':
                base = re.search(r'script\s+\w+\s+extends\s+(\w+)', source)
                from engine.components.behaviour import Behaviour
                cls = ({**NODE_CLASSES, 'Behaviour': Behaviour}).get(base[1]) if base else None
            elif value == 'self.transform':
                from engine.components.transform import Transform
                cls = Transform
            elif value == 'self.game_object':
                cls = NODE_CLASSES.get('GameObject')
            elif value in ('self.position', 'self.scale', 'self.velocity', 'self.transform.position', 'self.transform.scale'):
                cls = Vector2
            else:
                from engine.components.registry import COMPONENT_CLASSES
                component_match=re.search(r'\b'+re.escape(value)+r'\s*=\s*self\.get_component\([\"\'](\w+)[\"\']\)',source)
                if component_match:cls=COMPONENT_CLASSES.get(component_match[1])
                declaration = re.search(r'\b' + re.escape(value) + r'\s*(?::\s*(\w+))?\s*=\s*(\w+)\(', source)
                if declaration:
                    cls = NODE_CLASSES.get(declaration[1] or declaration[2])
                    if (declaration[1] or declaration[2]) == 'Vector2':
                        cls = Vector2
            if cls:
                properties = set(getattr(cls, 'get_exported_properties', lambda: {})())
                properties.update(name for name in dir(cls) if not name.startswith('__'))
                if value == 'self':
                    properties.update(re.findall(r'\b(?:func|def|export|let|const|signal)\s+(\w+)', source))
                return sorted(properties)
        return sorted(set(self.api) | set(re.findall(r'\b(?:func|def|class|script|let|const|export|signal)\s+(\w+)', source)) | {'self', 'true', 'false', 'null', 'range', 'len', 'print', 'int', 'float', 'str', 'list', 'dict'})

    def insert_completion(self, value):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(self.completer.completionPrefix()))
        cursor.insertText(value)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event):
        if self.completer.popup().isVisible() and event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab, Qt.Key.Key_Escape):
            event.ignore()
            return
        if event.key() == Qt.Key.Key_F12:
            self.definition_requested.emit(self.word())
            return
        explicit = event.key() == Qt.Key.Key_Space and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if not explicit:
            super().keyPressEvent(event)
        cursor = self.textCursor()
        prefix = self.toPlainText()[:cursor.position()]
        match = re.search(r'(\w*)$', prefix)
        word = match[1] if match else ''
        if explicit or (event.text() and (len(word) >= 2 or event.text() == '.')):
            self.completion_model.setStringList(self.symbols())
            self.completer.setCompletionPrefix(word)
            rect = self.cursorRect()
            rect.setWidth(330)
            self.completer.complete(rect)
        else:
            self.completer.popup().hide()

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            name = self.word(event.pos())
            text = self.api.get(name)
            if not text:
                match = re.search(r'^\s*(?:func|def|class|script|export|let|const)\s+' + re.escape(name) + r'\b.*', self.toPlainText(), re.M)
                text = match[0].strip() if match else None
            if text:
                QToolTip.showText(event.globalPos(), text[:1500], self)
            return True
        return super().viewportEvent(event)

    def mousePressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.definition_requested.emit(self.word(event.position().toPoint()))
            return
        super().mousePressEvent(event)
