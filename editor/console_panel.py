"""ConsolePanel — лог-консоль редактора с фильтром по уровню.

Вывод буферизуется и объединяет повторяющиеся сообщения, чтобы шторм
ошибок из игрового цикла не подвешивал интерфейс.
"""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                             QPushButton, QComboBox, QLabel)
from PyQt6.QtWidgets import QTabWidget

from editor.icons import get_icon

_LEVEL_COLORS = {
    "INFO": QColor("#d0d0d0"),
    "WARNING": QColor("#e0a800"),
    "ERROR": QColor("#e05c5c"),
    "DEBUG": QColor("#7f8c8d"),
}

_LEVELS = ["info", "warning", "error", "debug"]

#: Максимум строк, накапливаемых до сброса (защита от шторма логов).
_MAX_PENDING = 1500


class TracebackText(QPlainTextEdit):
    location_requested = pyqtSignal(str, int)
    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        import re
        text = self.cursorForPosition(event.position().toPoint()).block().text()
        match = re.search(r'File "([^"]+)", line (\d+)', text)
        if match:
            self.location_requested.emit(match[1], int(match[2]))

class ConsolePanel(QWidget):
    """Панель консоли с фильтрацией, буферизацией и очисткой."""

    location_requested = pyqtSignal(str, int)
    node_requested = pyqtSignal(str)
    diagnostic_requested = pyqtSignal(object)
    log_requested = pyqtSignal(str, str)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.current_filter = "info"
        self._pending: List[List[Any]] = []   # [level, message, count]
        self._dropped = 0
        self.project_dir = ''
        self._build_ui()
        self.log_requested.connect(self._append_log)
        self.diagnostic_requested.connect(self._add_diagnostic)

        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(120)
        self._flush_timer.timeout.connect(self._flush)

    # ==================================================================
    # Интерфейс
    # ==================================================================
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 4, 4, 0)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(_LEVELS)
        self.filter_combo.currentTextChanged.connect(self._on_filter)
        toolbar.addWidget(QLabel("Уровень:"))
        toolbar.addWidget(self.filter_combo)
        toolbar.addStretch(1)

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.setIcon(get_icon("clear"))
        self.clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_btn)
        layout.addLayout(toolbar)

        self.text = TracebackText()
        self.text.location_requested.connect(self.location_requested.emit)
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(3000)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(font)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.text, 'Журнал')
        from editor.problems_panel import ProblemsPanel
        self.problems = ProblemsPanel()
        self.problems.location_requested.connect(self.location_requested.emit)
        self.problems.node_requested.connect(self.node_requested.emit)
        self.tabs.addTab(self.problems, 'Проблемы')
        layout.addWidget(self.tabs)

    def _add_diagnostic(self, diagnostic):
        self.problems.add(diagnostic)
        self.tabs.setTabText(1, f'Проблемы ({len(self.problems.entries)})')
        self.tabs.setCurrentIndex(1)

    def _on_filter(self, text: str) -> None:
        self.current_filter = text

    def _level_visible(self, level: str) -> bool:
        order = {"debug": 0, "info": 1, "warning": 2, "error": 3}
        return order.get(level.lower(), 1) >= order.get(self.current_filter, 0)

    # ==================================================================
    # Запись
    # ==================================================================
    def log(self, message: str, level: str = "INFO") -> None:
        self.log_requested.emit(str(message),level)

    def _append_log(self, message: str, level: str = "INFO") -> None:
        """Добавляет сообщение в буфер (на экран попадёт пачкой)."""
        if not self._level_visible(level):
            return
        text = str(message)
        if self._pending and self._pending[-1][1] == text and self._pending[-1][0] == level:
            self._pending[-1][2] += 1
        else:
            self._pending.append([level, text, 1])
        if len(self._pending) > _MAX_PENDING:
            self._dropped += len(self._pending) - _MAX_PENDING // 2
            del self._pending[:_MAX_PENDING // 2]
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush(self) -> None:
        """Переносит буфер в текстовое поле."""
        if not self._pending:
            return
        lines = self._pending
        self._pending = []
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for level, message, count in lines:
            fmt = QTextCharFormat()
            fmt.setForeground(_LEVEL_COLORS.get(level.upper(), _LEVEL_COLORS["INFO"]))
            suffix = f"   (повтор ×{count})" if count > 1 else ""
            cursor.insertText(f"[{level.upper()}] {message}{suffix}\n", fmt)
        if self._dropped:
            cursor.insertText(f"[WARNING] пропущено сообщений: {self._dropped}\n")
            self._dropped = 0
        self.text.setTextCursor(cursor)
        self.text.ensureCursorVisible()
        # Не даём буферу копить лишнее при очень частых записях.
        if self._pending:
            self._flush_timer.start()

    def clear(self) -> None:
        self._pending.clear()
        self._dropped = 0
        self.text.clear()
        self.problems.clear()
        self.tabs.setTabText(1, 'Проблемы')

    def shutdown(self) -> None:
        """Останавливает таймер вывода (вызывается при закрытии редактора)."""
        try:
            self._flush_timer.stop()
        except Exception:
            pass
        self._pending.clear()


class ConsoleLogHandler(logging.Handler):
    """Перенаправляет записи Python logging в ConsolePanel."""

    def __init__(self, panel: ConsolePanel) -> None:
        super().__init__()
        self.panel = panel

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.panel.log(self.format(record), record.levelname)
            diagnostic = getattr(record, 'diagnostic', None)
            if diagnostic is None and record.exc_info and record.exc_info[1] is not None:
                from engine.systems.diagnostics import explain_exception
                diagnostic = explain_exception(record.exc_info[1], self.panel.project_dir)
            if diagnostic is not None:
                self.panel.diagnostic_requested.emit(diagnostic)
        except Exception:
            pass


def install_console_handler(panel: ConsolePanel) -> ConsoleLogHandler:
    """Устанавливает глобальный обработчик логов для Cloud Engine."""
    global _ACTIVE_PANEL
    _ACTIVE_PANEL = panel
    handler = ConsoleLogHandler(panel)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return handler


#: Последняя созданная консоль — в неё пишутся необработанные ошибки.
_ACTIVE_PANEL: "ConsolePanel | None" = None


def report_unhandled(text: str) -> None:
    """Показывает необработанную ошибку в консоли редактора (если она есть)."""
    if _ACTIVE_PANEL is not None:
        _ACTIVE_PANEL.log(text.strip(), "ERROR")
