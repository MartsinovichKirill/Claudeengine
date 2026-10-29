"""Диалог сборки CloudEngine.exe (запускает PyInstaller в отдельном процессе)."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any
from pathlib import Path
from build_support import build_environment, external_dll_search, find_build_python, validate_name, validate_build_destination

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QRadioButton, QCheckBox, QPushButton,
                             QPlainTextEdit, QProgressBar, QButtonGroup,
                             QMessageBox, QLineEdit, QFileDialog, QComboBox)

logger = logging.getLogger("cloudengine.build")


class BuildDialog(QDialog):
    """Собирает игру/редактор в EXE и показывает вывод сборщика."""

    def __init__(self, parent: Any = None, project_dir='') -> None:
        super().__init__(parent)
        self.project_dir = project_dir
        self.setWindowTitle('Экспорт игры' if project_dir else 'Сборка CloudEngine.exe')
        self.resize(760, 520)
        self.process: QProcess | None = None
        self.result_path: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Сборка выполняется PyInstaller. Если он не установлен, он будет "
            "поставлен автоматически. Для сборки из EXE нужен установленный Python "
            "с зависимостями движка. Папку результата можно выбрать ниже."
        )
        if self.project_dir:
            info.setText('Windows: готовый EXE на Windows. macOS: приложение на Mac. При выборе другой ОС создаётся ZIP с исходниками и инструкцией сборки; это не готовая игра.')
        if self.project_dir and getattr(sys, 'frozen', False):
            info.setText('Автономный экспорт использует встроенный player. Установка Python и PyInstaller не требуется. Для другой ОС создаётся пакет исходников. Формат — папка; иконка окна задаётся в проекте, EXE использует иконку player.')
        info.setWordWrap(True)
        info.setStyleSheet("color: #9e9e9e;")
        layout.addWidget(info)

        self.target_combo = QComboBox()
        self.target_combo.addItem('Windows (.exe)', 'windows')
        self.target_combo.addItem('macOS (.app) — сборка на Mac', 'macos')
        self.target_combo.setCurrentIndex(1 if sys.platform == 'darwin' else 0)
        if self.project_dir:
            layout.addWidget(self.target_combo)
        mode_row = QHBoxLayout()
        self.radio_onedir = QRadioButton("Папка (быстрее запуск)")
        self.radio_onedir.setChecked(True)
        self.radio_onefile = QRadioButton("Один .exe (удобнее переносить)")
        group = QButtonGroup(self)
        group.addButton(self.radio_onedir)
        group.addButton(self.radio_onefile)
        mode_row.addWidget(self.radio_onedir)
        mode_row.addWidget(self.radio_onefile)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        opts_row = QHBoxLayout()
        self.console_check = QCheckBox("Показывать консоль (для отладки)")
        self.clean_check = QCheckBox("Очистить кэш сборки")
        opts_row.addWidget(self.console_check)
        opts_row.addWidget(self.clean_check)
        opts_row.addStretch(1)
        layout.addLayout(opts_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Имя файла:"))
        self.name_edit = QLineEdit('CloudGame' if self.project_dir else 'CloudEngine')
        name_row.addWidget(self.name_edit, 1)
        layout.addLayout(name_row)
        self.icon_edit = QLineEdit()
        if self.project_dir and getattr(sys, 'frozen', False):
            self.radio_onefile.setChecked(False)
            self.radio_onefile.setEnabled(False)
            self.radio_onedir.setChecked(True)
            self.radio_onefile.setToolTip('Автономный экспорт использует папочную сборку player.')
        if self.project_dir:
            icon_row = QHBoxLayout()
            icon_row.addWidget(QLabel('Иконка (.ico / .icns):'))
            icon_row.addWidget(self.icon_edit)
            choose_icon = QPushButton('Обзор…')
            choose_icon.clicked.connect(self._choose_icon)
            icon_row.addWidget(choose_icon)
            layout.addLayout(icon_row)
            layout.addWidget(QLabel('Окно, стартовая сцена и ресурсы берутся из настроек проекта.'))

        python_row = QHBoxLayout()
        python_row.addWidget(QLabel("Python для сборки:"))
        self.python_edit = QLineEdit("" if getattr(sys, 'frozen', False) else sys.executable)
        self.python_edit.setPlaceholderText("Автоматический поиск python.exe")
        python_row.addWidget(self.python_edit, 1)
        choose_python = QPushButton("Обзор…")
        choose_python.clicked.connect(self._choose_python)
        python_row.addWidget(choose_python)
        layout.addLayout(python_row)
        if self.project_dir and getattr(sys, "frozen", False):
            self.python_edit.setEnabled(False)
            self.python_edit.setPlaceholderText("Встроенный player — Python не требуется")
            choose_python.setEnabled(False)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Папка результата:"))
        root = Path(__file__).resolve().parents[1]
        portable = Path(os.environ.get('CLOUDENGINE_LAUNCHER_PATH') or sys.executable).resolve().parent
        base = portable.parent if (portable / '_internal').is_dir() else portable
        destination = base / 'builds' if getattr(sys, 'frozen', False) else root / 'dist'
        self.output_edit = QLineEdit(str(destination))
        output_row.addWidget(self.output_edit, 1)
        choose_output = QPushButton("Обзор…")
        choose_output.clicked.connect(self._choose_output)
        output_row.addWidget(choose_output)
        layout.addLayout(output_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.output.setFont(font)
        layout.addWidget(self.output, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.build_btn = QPushButton("Собрать")
        self.build_btn.clicked.connect(self.start_build)
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close)
        buttons.addWidget(self.build_btn)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)
        self.check_project=QCheckBox('Проверять сохранённые сцены перед сборкой')
        self.check_project.setChecked(True)
        if self.project_dir: layout.insertWidget(1,self.check_project)

    # ==================================================================
    # Запуск сборки
    # ==================================================================
    def _choose_python(self):
        path, _ = QFileDialog.getOpenFileName(self, "Python для сборки", "", "Python (python.exe python3 python)")
        if path:
            self.python_edit.setText(path)

    def _choose_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Иконка игры', self.project_dir, 'Icon (*.ico *.icns)')
        if path:
            self.icon_edit.setText(path)

    def _choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Папка результата", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def start_build(self) -> None:
        """Запускает PyInstaller отдельным процессом."""
        if self.process is not None:
            return
        if self.project_dir and self.check_project.isChecked():
            from editor.project_tests_dialog import ProjectTestsDialog
            verification=ProjectTestsDialog(self.project_dir,self,run_immediately=True)
            if verification.exec()!=verification.DialogCode.Accepted or not verification.report or not verification.report['passed']:
                return
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(root, 'build_game.py' if self.project_dir else 'build_exe.py')
        if not os.path.isfile(script):
            QMessageBox.warning(self, "Сборка", "build_exe.py не найден.")
            return

        try:
            if self.project_dir:
                from build_game import native_target
                self.source_package = self.target_combo.currentData() != native_target()
            name = validate_name(self.name_edit.text())
            if not self.output_edit.text().strip():
                raise ValueError("Выберите папку результата.")
            destination = Path(self.output_edit.text()).expanduser().resolve()
            validate_build_destination(destination, name, self.radio_onefile.isChecked())
            destination.mkdir(parents=True, exist_ok=True)
            interpreter = sys.executable if self.project_dir and getattr(sys, "frozen", False) else find_build_python(root, self.python_edit.text().strip())
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Сборка", str(exc))
            return
        self.result_path = destination / (f"{name}.exe" if self.radio_onefile.isChecked() else f"{name}/{name}.exe")
        if self.project_dir:
            from build_game import game_output
            self.result_path = (destination / (name + '-' + self.target_combo.currentData() + '-source.zip') if self.source_package else game_output(destination, name, self.target_combo.currentData(), self.radio_onefile.isChecked(), self.console_check.isChecked()))
        if getattr(sys, 'frozen', False) and self.result_path.resolve() == Path(sys.executable).resolve():
            QMessageBox.warning(self, "Сборка", "Выберите другую папку: запущенный EXE нельзя перезаписать.")
            return
        args = [script, '--name', name, '--output', str(destination)]
        if self.project_dir:
            args += ['--project', self.project_dir, '--target', self.target_combo.currentData()]
            if self.source_package:
                args += ['--prepare-source']
            if self.icon_edit.text().strip():
                args += ['--icon', self.icon_edit.text().strip()]
        if self.radio_onefile.isChecked():
            args.append("--onefile")
        if self.console_check.isChecked():
            args.append("--console")
        if self.clean_check.isChecked():
            args.append("--clean")

        if self.project_dir and getattr(sys, 'frozen', False):
            args = ['--portable-export', '--project', self.project_dir, '--output', str(destination), '--name', name, '--target', self.target_combo.currentData()]
        self.output.clear()
        self._append(f"[build] Запуск: {interpreter} {' '.join(args)}\n")
        self.progress.setVisible(True)
        self.build_btn.setEnabled(False)
        for control in (self.target_combo, self.name_edit, self.python_edit, self.output_edit, self.radio_onefile, self.radio_onedir, self.console_check, self.clean_check):
            control.setEnabled(False)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(root)
        environment = QProcessEnvironment()
        for key, value in build_environment().items():
            environment.insert(key, value)
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        process = self.process
        with external_dll_search():
            process.start(interpreter, args)
            process.waitForStarted(3000)

    def _read_stdout(self) -> None:
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        self._append(data)

    def _read_stderr(self) -> None:
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardError()).decode("utf-8", "replace")
        self._append(data)

    def _append(self, text: str) -> None:
        if not text:
            return
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _on_finished(self, code: int, status: Any) -> None:
        self._read_stdout()
        self._read_stderr()
        self.progress.setVisible(False)
        self.build_btn.setEnabled(True)
        for control in (self.target_combo, self.name_edit, self.python_edit, self.output_edit, self.radio_onefile, self.radio_onedir, self.console_check, self.clean_check):
            control.setEnabled(True)
        if self.project_dir and getattr(sys, 'frozen', False):
            self.radio_onefile.setChecked(False)
            self.radio_onefile.setEnabled(False)
            self.radio_onedir.setChecked(True)
            self.python_edit.setEnabled(False)
        self._append(f"\n[build] Процесс завершён с кодом {code}\n")
        if code == 0 and status == QProcess.ExitStatus.NormalExit and self.result_path and self.result_path.exists():
            self._append(f"[build] Готово: {self.result_path}\n")
            if getattr(self, "source_package", False):
                self._append("[build] Это пакет исходников. Распакуйте его на целевой ОС и следуйте BUILD.txt.\n")
            elif not self.radio_onefile.isChecked():
                self._append("[build] Переносите всю папку рядом с EXE, включая _internal.\n")
        else:
            self._append("[build] Сборка не завершена. Причина указана в журнале выше.\n")
        self.process = None

    def _on_error(self, error):
        if self.process is not None:
            self._append(f"[build] Ошибка процесса: {self.process.errorString()}\n")
        if error == QProcess.ProcessError.FailedToStart:
            self._on_finished(-1, QProcess.ExitStatus.CrashExit)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.process is not None:
            self.process.kill()
            self.process = None
        super().closeEvent(event)
