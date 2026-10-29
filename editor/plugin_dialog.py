"""Plugin management shared by the startup hub and editor."""
import json
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QFileDialog, QMessageBox, QInputDialog, QLineEdit)
from editor.icons import get_icon
from editor.plugin_system import PluginStore


class PluginDialog(QDialog):
    def __init__(self, parent=None, host=None):
        super().__init__(parent)
        self.host = host
        self.store = host.store if host else PluginStore()
        self.setWindowTitle('Cloud Plugins — менеджер плагинов')
        self.resize(780, 590)
        layout = QVBoxLayout(self)
        title = QLabel('Плагины Cloud Engine'); title.setStyleSheet('font-size: 22px; font-weight: bold; color: #75b8ed;')
        layout.addWidget(title)
        hint = QLabel('Галочка включает плагин в редакторе. Пользовательские плагины выполняют Python-код с правами приложения; устанавливайте доверенные пакеты.')
        hint.setWordWrap(True); layout.addWidget(hint)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Поиск плагинов…')
        self.search.textChanged.connect(self.filter_plugins)
        layout.addWidget(self.search)
        reload_button = QPushButton('Перезагрузить плагины')
        reload_button.clicked.connect(self.reload_plugins)
        layout.addWidget(reload_button)
        self.list = QListWidget(); self.list.itemChanged.connect(self.changed)
        layout.addWidget(self.list, 1)
        self.details = QLabel(); self.details.setWordWrap(True); layout.addWidget(self.details)
        self.list.currentItemChanged.connect(self.describe)
        row = QHBoxLayout()
        for text, callback in [('Установить ZIP', self.install_zip), ('Добавить свою папку', self.install_folder), ('Создать свой плагин', self.create_plugin)]:
            button = QPushButton(text); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row)
        self.status = QLabel(str(self.store.root)); self.status.setWordWrap(True); layout.addWidget(self.status)
        remove = QPushButton('Удалить выбранный плагин')
        remove.clicked.connect(self.remove_plugin)
        layout.addWidget(remove)
        close = QPushButton('Готово'); close.clicked.connect(self.accept); layout.addWidget(close)
        self.refresh()

    def filter_plugins(self, text):
        for index in range(self.list.count()):
            item = self.list.item(index)
            plugin = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(text.casefold() not in (item.text() + ' ' + plugin.get('description','')).casefold())

    def reload_plugins(self):
        if self.host:
            self.host.reload()
        self.refresh()
        self.filter_plugins(self.search.text())

    def refresh(self):
        self.list.blockSignals(True); self.list.clear()
        for plugin in self.store.discover():
            item = QListWidgetItem(f'{plugin["name"]}  ·  {plugin["version"]}' + ('  ·  встроенный' if plugin['builtin'] else ''))
            item.setIcon(get_icon('component'))
            item.setData(Qt.ItemDataRole.UserRole, plugin)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if plugin['enabled'] else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)

    def describe(self, item, *_):
        if not item:
            return
        plugin = item.data(Qt.ItemDataRole.UserRole)
        error = self.host.errors.get(plugin['id'], '') if self.host else ''
        self.details.setText(str(plugin.get('description', '')) + ('\nОшибка загрузки: ' + error if error else '') + '\n' + str(plugin['path']))

    def changed(self, item):
        plugin = item.data(Qt.ItemDataRole.UserRole)
        try:
            self.store.set_enabled(plugin['id'], item.checkState() == Qt.CheckState.Checked)
            if self.host:
                self.host.reload()
            self.describe(item)
        except Exception as exc:
            QMessageBox.warning(self, 'Плагин', str(exc)); self.refresh()

    def install(self, path):
        if not path:
            return
        try:
            plugin_id = self.store.install(path)
            self.refresh(); self.status.setText(f'Установлен {plugin_id}. Поставьте галочку, чтобы включить.')
        except Exception as exc:
            QMessageBox.warning(self, 'Установка плагина', str(exc))

    def install_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Пакет плагина', '', 'Cloud Plugin (*.zip)')
        self.install(path)

    def remove_plugin(self):
        item = self.list.currentItem()
        if item is None:
            return
        plugin = item.data(Qt.ItemDataRole.UserRole)
        if plugin['builtin']:
            QMessageBox.information(self, 'Плагин', 'Встроенные плагины можно отключить галочкой.')
            return
        if QMessageBox.question(self, 'Удалить плагин', 'Удалить ' + plugin['name'] + '? Пакет останется в локальной папке .trash.') != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.set_enabled(plugin['id'], False)
            if self.host:
                self.host.reload()
            archived = self.store.uninstall(plugin['id'])
            self.refresh()
            self.status.setText('Плагин удалён. Резервная копия: ' + str(archived))
        except Exception as error:
            QMessageBox.warning(self, 'Удаление плагина', str(error))

    def install_folder(self):
        self.install(QFileDialog.getExistingDirectory(self, 'Папка с plugin.json'))

    def create_plugin(self):
        name, ok = QInputDialog.getText(self, 'Свой плагин', 'ID (a-z, цифры, дефис):', text='my-plugin')
        if not ok:
            return
        import re
        if not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}', name):
            QMessageBox.warning(self, 'Плагин', 'Недопустимый ID.'); return
        parent = QFileDialog.getExistingDirectory(self, 'Где создать исходники плагина?')
        if not parent:
            return
        target = Path(parent) / name
        try:
            target.mkdir()
            (target / 'plugin.json').write_text(json.dumps({'id': name, 'name': name, 'version': '1.0.0', 'api_version': 1, 'entry': 'plugin.py', 'description': 'Мой плагин Cloud Engine'}, ensure_ascii=False, indent=2), encoding='utf-8')
            (target / 'plugin.py').write_text('def setup(context):\n    def run():\n        context.log("Мой плагин работает!")\n    context.add_action("Мой инструмент", run)\n', encoding='utf-8')
            self.status.setText('Исходники созданы: ' + str(target) + '. Добавьте эту папку через менеджер.')
        except OSError as exc:
            QMessageBox.warning(self, 'Создать плагин', str(exc))
