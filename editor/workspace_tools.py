"""Workspace profiles, shortcut configuration and project symbol tools."""
import io,json,tokenize,keyword
from pathlib import Path
from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QAction,QKeySequence
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QDialogButtonBox,QKeySequenceEdit,QInputDialog,QMessageBox,QListWidget

def configure_shortcuts(window):
    dialog=QDialog(window);dialog.setWindowTitle('Горячие клавиши');dialog.resize(580,650)
    from PyQt6.QtWidgets import QScrollArea,QWidget
    layout=QVBoxLayout(dialog);scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();form=QFormLayout(content);scroll.setWidget(content);layout.addWidget(scroll)
    fields=[]
    seen=set()
    for action in window.findChildren(QAction):
        name=action.objectName() or action.text()
        if not name or name in seen:continue
        seen.add(name)
        field=QKeySequenceEdit(action.shortcut());form.addRow(name,field);fields.append((name,action,field))
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
    if dialog.exec():
        keys={};conflicts=[]
        for name,action,field in fields:
            key=field.keySequence().toString()
            if key and key in keys:conflicts.append(key)
            if key:keys[key]=name
        if conflicts:QMessageBox.warning(window,'Конфликт клавиш',', '.join(conflicts));return
        saved={}
        for name,action,field in fields:action.setShortcut(field.keySequence());saved[name]=field.keySequence().toString()
        window.settings_store.set('shortcuts',saved);window.settings_store.save()

def symbol_hits(root,symbol):
    hits=[]
    for path in Path(root).rglob('*'):
        if path.suffix not in ('.cloud','.py') or '__pycache__' in path.parts:continue
        source=path.read_text(encoding='utf-8-sig')
        try:
            tokens=list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (tokenize.TokenError,IndentationError):continue
        for token in tokens:
            if token.type==tokenize.NAME and token.string==symbol:hits.append((path,token.start,token.end))
    return hits

def symbol_tool(window,rename=False):
    symbol,ok=QInputDialog.getText(window,'Символ проекта','Имя функции или свойства:')
    if not ok or not symbol.isidentifier():return
    if window.script_editor.is_modified() and not window.script_editor.save():return
    root=Path(window.project_dir)/'scripts';hits=symbol_hits(root,symbol)
    if rename:
        replacement,ok=QInputDialog.getText(window,'Переименовать','Новое имя:')
        if not ok or not replacement.isidentifier() or keyword.iskeyword(replacement):return
        if QMessageBox.question(window,'Переименование',f'Заменить {len(hits)} вхождений {symbol} на {replacement}? Это замена токенов во всём проекте; одноимённые независимые символы тоже попадут в список. Резервные копии будут сохранены.')!=QMessageBox.StandardButton.Yes:return
        grouped={}
        for path,start,end in hits:grouped.setdefault(path,[]).append((start,end))
        from datetime import datetime
        backup=Path(window.project_dir)/'.cloud-backups'/datetime.now().strftime('%Y%m%d-%H%M%S')
        for path,positions in grouped.items():
            source=path.read_text(encoding='utf-8-sig');lines=source.splitlines(True)
            for start,end in sorted(positions,reverse=True):
                row=start[0]-1;lines[row]=lines[row][:start[1]]+replacement+lines[row][end[1]:]
            target=backup/path.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source,encoding='utf-8')
            path.write_text(''.join(lines),encoding='utf-8')
        if window.script_editor.path:window.script_editor.load_file(window.script_editor.path)
        return
    dialog=QDialog(window);dialog.setWindowTitle('Использования: '+symbol);dialog.resize(760,500);layout=QVBoxLayout(dialog);listing=QListWidget();layout.addWidget(listing)
    listing.addItems([f'{path.relative_to(root)}:{start[0]}' for path,start,end in hits])
    def open_hit(item):
        index=listing.row(item);window.open_script(str(hits[index][0]));dialog.accept()
    listing.itemDoubleClicked.connect(open_hit);dialog.exec()

def install(window):
    menu=window.menuBar().addMenu('Рабочее пространство')
    def save_profile():
        name,ok=QInputDialog.getText(window,'Раскладка','Название:')
        if not ok or not name.strip():return
        profiles=window.settings_store.get('workspace_profiles',{})
        profiles[name.strip()]={'state':bytes(window.saveState().toBase64()).decode(),'geometry':bytes(window.saveGeometry().toBase64()).decode()}
        window.settings_store.set('workspace_profiles',profiles);window.settings_store.save()
    def load_profile():
        profiles=window.settings_store.get('workspace_profiles',{})
        if not profiles:return
        name,ok=QInputDialog.getItem(window,'Раскладки','Выбрать:',list(profiles),0,False)
        if ok:
            window.restoreState(QByteArray.fromBase64(profiles[name]['state'].encode()));window.restoreGeometry(QByteArray.fromBase64(profiles[name]['geometry'].encode()))
    menu.addAction('Сохранить раскладку как…',save_profile);menu.addAction('Выбрать раскладку…',load_profile)
    menu.addAction('Горячие клавиши…',lambda:configure_shortcuts(window))
    menu.addAction('Найти использования символа…',lambda:symbol_tool(window))
    menu.addAction('Переименовать символ…',lambda:symbol_tool(window,True))
    seen_keys=set()
    for action in window.findChildren(QAction):
        key=action.shortcut().toString()
        if key:
            if key in seen_keys:action.setShortcut(QKeySequence())
            else:seen_keys.add(key)
    saved=window.settings_store.get('shortcuts',{})
    for action in window.findChildren(QAction):
        name=action.objectName() or action.text()
        if name in saved:action.setShortcut(QKeySequence(saved[name]))
