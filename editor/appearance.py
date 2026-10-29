"""UI preferences, compact menus and a command palette without replacing actions."""
import copy
from pathlib import Path
from PyQt6.QtCore import Qt,QSize
from PyQt6.QtGui import QColor,QFont,QPalette,QAction,QKeySequence
from PyQt6.QtWidgets import (QApplication,QDialog,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QFormLayout,
    QLabel,QPushButton,QToolButton,QComboBox,QFontComboBox,QSpinBox,QCheckBox,QColorDialog,
    QDialogButtonBox,QListWidget,QLineEdit,QMenu,QSizePolicy,QTabWidget)
from editor.ui_profile import flavor,defaults
from editor.icons import get_icon


def preferences(store=None):
    from editor.editor_settings import EditorSettings
    store=store or EditorSettings()
    result=defaults(); saved=store.get('appearance',{})
    if isinstance(saved,dict):
        result.update({key:value for key,value in saved.items() if key in result})
        result['toolbar_groups']={**defaults()['toolbar_groups'],**(saved.get('toolbar_groups',{}) if isinstance(saved.get('toolbar_groups',{}),dict) else {})}
        if flavor()=='classic' and saved.get('menu_layout_version',0)<1:
            result['group_menus']=True
    return result


def apply_application_theme(app,options=None):
    options=options or preferences()
    app.setStyle('Fusion')
    if flavor()=='classic':
        from editor.classic_theme import apply_theme
        apply_theme(app)
        if options['font_size']!=13 or options['font_family']!='Segoe UI':
            app.setStyleSheet(app.styleSheet()+f'\nQWidget {{ font-family:"{options["font_family"]}"; font-size:{options["font_size"]}px; }}')
        app.setStyleSheet(app.styleSheet()+'\nQToolButton#SceneTabClose { background:transparent; border:0; padding:2px; min-width:12px; min-height:12px; } QToolButton#SceneTabClose:hover { background:#4b3944; border-radius:3px; }')
        close_icon=(Path(__file__).resolve().parents[1]/'assets'/'ui'/'close.svg').as_posix()
        app.setStyleSheet(app.styleSheet()+f'\nQDockWidget {{ titlebar-close-icon:url("{close_icon}"); }} QDockWidget::close-button {{ border:0; background:transparent; padding:3px; }} QDockWidget::close-button:hover {{ background:#3d4e60; border-radius:3px; }}')
    else:
        from editor.modern_theme import stylesheet,PALETTES
        c=PALETTES.get(options.get('palette'),PALETTES['midnight'])
        palette=QPalette()
        for role,color in [(QPalette.ColorRole.Window,c['bg']),(QPalette.ColorRole.Base,c['input']),
            (QPalette.ColorRole.Text,c['text']),(QPalette.ColorRole.WindowText,c['text']),
            (QPalette.ColorRole.Button,c['surface']),(QPalette.ColorRole.ButtonText,c['text']),
            (QPalette.ColorRole.Highlight,options['accent']),(QPalette.ColorRole.HighlightedText,'#ffffff')]:
            palette.setColor(role,QColor(color))
        app.setPalette(palette); app.setStyleSheet(stylesheet(options))
    app.setProperty('cloudAppearance',copy.deepcopy(options))


def group_menus(window,grouped):
    menubar=window.menuBar()
    for parent,action in getattr(window,'_ui_insertions',[]): parent.removeAction(action)
    window._ui_insertions=[]
    originals=window._ui_original_menus
    for menu,title in originals:
        menu.setTitle(title); menubar.removeAction(menu.menuAction())
    if not grouped:
        for menu,title in originals: menubar.addMenu(menu)
        return
    menus={title:menu for menu,title in originals}
    def nest(child,parent,title=None):
        if child in menus and parent in menus:
            menu=menus[child]
            if title: menu.setTitle(title)
            action=menus[parent].addMenu(menu); window._ui_insertions.append((menus[parent],action))
    nest('Выровнять','Правка','Выравнивание объектов')
    nest('Нода','Сцена','Добавить объект')
    nest('Компонент','Сцена','Компоненты объекта')
    nest('Разработка','Проект','Игровые данные и проверки')
    nest('Восстановление','Проект','Резервные копии')
    nest('Рабочее пространство','Вид')
    nest('Язык / Language','Вид')
    nest('Графика','Инструменты','Отрисовка и камера')
    nest('Плагины','Инструменты')
    nest('Шаблоны','Инструменты')
    nest('Отладка','Инструменты')
    for name in ('Файл','Правка','Сцена','Проект','Вид','Инструменты'):
        if name in menus: menubar.addMenu(menus[name])


def tool_button(action,size,labels=False):
    button=QToolButton(); button.setDefaultAction(action); button.setIconSize(QSize(size,size))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if labels else Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setAutoRaise(True)
    return button


def rebuild_toolbar(window,options):
    toolbar=window.toolbar
    if not hasattr(window,'_ui_toolbar_actions'): window._ui_toolbar_actions=list(toolbar.actions())
    # Keep the original QWidgetAction's widget alive when replacing our strip.
    toolbar.align_button.setParent(toolbar); toolbar.align_button.hide()
    old=getattr(window,'_ui_command_strip',None)
    for action in toolbar.actions(): toolbar.removeAction(action)
    if old is not None: old.deleteLater()
    if flavor()=='classic':
        for action in window._ui_toolbar_actions: toolbar.addAction(action)
        toolbar.align_button.show(); return
    container=QWidget(); container.setObjectName('EditorCommandStrip'); container.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
    layout=QHBoxLayout(container); layout.setContentsMargins(0,0,0,0); layout.setSpacing(10)
    window._ui_command_strip=container
    size=max(16,min(28,int(options.get('icon_size',20))))
    for name in ('play','pause','stop','save','undo','redo','grid','gizmo','focus','mode_2d','snap','settings','build'):
        action=getattr(toolbar,name+'_action',None) if name!='mode_2d' else toolbar.mode_2d
        if action:
            icon={'gizmo':'eye','focus':'focus','mode_2d':'scene','settings':'settings','build':'build'}.get(name,name)
            action.setIcon(get_icon(icon,size,'#a7dfb4' if name=='play' else '#bbc9dc'))
    for code,icon in [('select','cursor'),('pan','hand'),('move','move'),('rotate','rotate'),('scale','scale')]: toolbar._tool_actions[code].setIcon(get_icon(icon,size))
    groups={}
    def group(name):
        frame=QFrame(container); frame.setObjectName('ToolGroup'); row=QHBoxLayout(frame); row.setContentsMargins(3,3,3,3); row.setSpacing(2)
        frame.setVisible(options['toolbar_groups'].get(name,True)); groups[name]=frame; layout.addWidget(frame); return row
    row=group('history')
    for action in (toolbar.save_action,toolbar.undo_action,toolbar.redo_action): row.addWidget(tool_button(action,size))
    row=group('scene')
    for code in ('select','pan','move','rotate','scale'): row.addWidget(tool_button(toolbar._tool_actions[code],size))
    layout.addStretch(1)
    row=group('play')
    for action in (toolbar.play_action,toolbar.pause_action,toolbar.stop_action): row.addWidget(tool_button(action,size,options['toolbar_labels']))
    layout.addStretch(1)
    row=group('view'); view=QToolButton(); view.setIcon(get_icon('layers',size)); view.setText('Сцена'); view.setToolTip('Сетка, маркеры, фокус и привязка')
    view.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); view.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu=QMenu(view)
    for action in (toolbar.grid_action,toolbar.gizmo_action,toolbar.focus_action,toolbar.mode_2d,toolbar.snap_action): menu.addAction(action)
    view.setMenu(menu); row.addWidget(view)
    toolbar.align_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly); toolbar.align_button.setIconSize(QSize(size,size)); toolbar.align_button.setToolTip('Выравнивание объектов')
    row.addWidget(toolbar.align_button); toolbar.align_button.show()
    row=group('project'); row.addWidget(tool_button(toolbar.settings_action,size))
    build=tool_button(toolbar.build_action,size,True); build.setText('Сборка'); build.setObjectName('PrimaryBuild'); row.addWidget(build)
    toolbar.addWidget(container)
    window._ui_toolbar_groups=groups


class CommandPalette(QDialog):
    def __init__(self,window):
        super().__init__(window); self.setWindowTitle('Поиск команды'); self.resize(650,520)
        layout=QVBoxLayout(self); self.search=QLineEdit(); self.search.setPlaceholderText('Начните вводить название команды…'); layout.addWidget(self.search)
        self.list=QListWidget(); layout.addWidget(self.list,1); self.commands=[]; seen=set()
        def walk(menu,path):
            for action in menu.actions():
                if action.menu(): walk(action.menu(),path+' / '+action.menu().title())
                elif not action.isSeparator() and action.text() and id(action) not in seen:
                    seen.add(id(action)); self.commands.append((path+' / '+action.text().replace('&',''),action))
        for menu,title in window._ui_original_menus: walk(menu,title)
        self.search.textChanged.connect(self.filter); self.search.returnPressed.connect(self.run_command); self.list.itemActivated.connect(lambda _:self.run_command())
        self.filter(''); self.search.setFocus()

    def filter(self,text):
        self.list.clear(); self.visible=[]
        for title,action in self.commands:
            if all(part in title.casefold() for part in text.casefold().split()) and action.isEnabled():
                self.visible.append(action); self.list.addItem(title)
        if self.list.count(): self.list.setCurrentRow(0)

    def run_command(self):
        row=self.list.currentRow()
        if 0<=row<len(self.visible):
            action=self.visible[row]; self.accept()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0,action.trigger)


class AppearanceDialog(QDialog):
    def __init__(self,window):
        super().__init__(window); self.window_ref=window; self.original=preferences(window.settings_store); self.options=copy.deepcopy(self.original)
        self.setWindowTitle('Настройка интерфейса'); self.resize(740,650)
        root=QVBoxLayout(self); heading=QLabel('Интерфейс редактора'); heading.setObjectName('SectionTitle'); root.addWidget(heading)
        note=QLabel('Изменения можно посмотреть перед сохранением. Настройки Modern и Classic хранятся отдельно.'); note.setWordWrap(True); note.setObjectName('SecondaryText'); root.addWidget(note)
        tabs=QTabWidget(); root.addWidget(tabs,1); look=QWidget(); form=QFormLayout(look); form.setSpacing(14); tabs.addTab(look,'Оформление')
        self.palette=QComboBox()
        for name,label in [('midnight','Midnight — тёмно-синий'),('graphite','Graphite — нейтральный'),('slate','Slate — серо-синий')]: self.palette.addItem(label,name)
        form.addRow('Палитра',self.palette); self.palette.setEnabled(flavor()!='classic')
        self.font=QFontComboBox(); form.addRow('Шрифт интерфейса',self.font)
        self.font_size=QSpinBox(); self.font_size.setRange(10,18); form.addRow('Размер текста, px',self.font_size)
        self.density=QComboBox()
        for value,label in [('compact','Компактно'),('comfortable','Обычно'),('spacious','Свободно')]: self.density.addItem(label,value)
        form.addRow('Плотность',self.density)
        self.icon_size=QSpinBox(); self.icon_size.setRange(16,28); self.icon_size.setSingleStep(2); form.addRow('Размер иконок, px',self.icon_size)
        self.radius=QSpinBox(); self.radius.setRange(0,12); form.addRow('Скругление, px',self.radius)
        self.accent=QPushButton('Выбрать цвет…'); self.accent.clicked.connect(self.choose_accent); form.addRow('Акцент',self.accent)
        for control in (self.density,self.icon_size,self.radius,self.accent): control.setEnabled(flavor()!='classic')
        tools=QWidget(); toolform=QFormLayout(tools); toolform.setSpacing(14); tabs.addTab(tools,'Меню и инструменты')
        self.grouped=QCheckBox('Сгруппировать верхние меню'); toolform.addRow(self.grouped)
        self.labels=QCheckBox('Подписи кнопок запуска'); toolform.addRow(self.labels)
        self.groups={}
        for key,label in [('history','Сохранение и история'),('scene','Инструменты сцены'),('play','Запуск игры'),('view','Отображение и выравнивание'),('project','Настройки и сборка')]:
            check=QCheckBox(label); self.groups[key]=check; check.setEnabled(flavor()!='classic'); toolform.addRow(check)
        self.labels.setEnabled(flavor()!='classic')
        panels=QWidget(); panel_layout=QVBoxLayout(panels); tabs.addTab(panels,'Панели')
        panel_layout.addWidget(QLabel('Панели можно перетаскивать, объединять вкладками и скрывать.'))
        self.panel_checks=[]
        for dock in window.findChildren(__import__('PyQt6.QtWidgets',fromlist=['QDockWidget']).QDockWidget):
            check=QCheckBox(dock.windowTitle()); check.setChecked(dock.isVisible()); self.panel_checks.append((dock,check)); panel_layout.addWidget(check)
        panel_layout.addStretch()
        row=QHBoxLayout(); preview=QPushButton('Предпросмотр'); preview.clicked.connect(self.preview); row.addWidget(preview)
        reset=QPushButton('По умолчанию'); reset.clicked.connect(self.reset_defaults); row.addWidget(reset); root.addLayout(row)
        buttons=QDialogButtonBox(); buttons.addButton('Сохранить',QDialogButtonBox.ButtonRole.AcceptRole); buttons.addButton('Отмена',QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.original_panels={dock:dock.isVisible() for dock,check in self.panel_checks}
        self.finished.connect(self.finish); self.fill()

    def fill(self):
        o=self.options; self.palette.setCurrentIndex(self.palette.findData(o['palette'])); self.font.setCurrentFont(QFont(o['font_family'])); self.font_size.setValue(o['font_size'])
        self.density.setCurrentIndex(self.density.findData(o['density'])); self.icon_size.setValue(o['icon_size']); self.radius.setValue(o['radius'])
        self.grouped.setChecked(o['group_menus']); self.labels.setChecked(o['toolbar_labels']); self.accent.setText(o['accent'])
        for key,check in self.groups.items(): check.setChecked(o['toolbar_groups'].get(key,True))

    def read(self):
        self.options.update(palette=self.palette.currentData(),font_family=self.font.currentFont().family(),font_size=self.font_size.value(),density=self.density.currentData(),icon_size=self.icon_size.value(),radius=self.radius.value(),group_menus=self.grouped.isChecked(),toolbar_labels=self.labels.isChecked(),toolbar_groups={key:check.isChecked() for key,check in self.groups.items()})
        return copy.deepcopy(self.options)

    def choose_accent(self):
        color=QColorDialog.getColor(QColor(self.options['accent']),self,'Акцент интерфейса')
        if color.isValid(): self.options['accent']=color.name(); self.accent.setText(color.name())
    def preview(self):
        apply_preferences(self.window_ref,self.read())
        for dock,check in self.panel_checks: dock.setVisible(check.isChecked())
    def reset_defaults(self): self.options=defaults(); self.fill()
    def save(self):
        self.preview(); self.window_ref.settings_store.set('appearance',self.read()); self.window_ref.save_layout(); self.window_ref.settings_store.save(); self.accept()
    def finish(self,result):
        if result!=QDialog.DialogCode.Accepted:
            apply_preferences(self.window_ref,self.original)
            for dock,visible in self.original_panels.items(): dock.setVisible(visible)


def apply_preferences(window,options):
    apply_application_theme(QApplication.instance(),options)
    group_menus(window,options['group_menus']); rebuild_toolbar(window,options)
    # Relayout native tab buttons after density/font changes.
    window.scene_tabs.setMaximumHeight(max(42,int(options['font_size'])+32))


def install(window):
    originals=[(action.menu(),action.menu().title()) for action in window.menuBar().actions() if action.menu()]
    window._ui_original_menus=originals
    view=next((menu for menu,title in originals if title=='Вид'),None)
    if view:
        view.addSeparator(); action=view.addAction(get_icon('settings'),'Настройка интерфейса…')
        action.triggered.connect(lambda:AppearanceDialog(window).exec())
    action=QAction('Поиск команды…',window); action.setShortcut(QKeySequence('Ctrl+K')); action.triggered.connect(lambda:CommandPalette(window).exec()); window.addAction(action)
    window.command_palette_action=action
    if flavor()=='modern':
        search=QToolButton(); search.setObjectName('CommandSearch'); search.setText('Поиск  Ctrl K'); search.setIcon(get_icon('search',16)); search.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        search.clicked.connect(action.trigger); window.menuBar().setCornerWidget(search,Qt.Corner.TopRightCorner)
    apply_preferences(window,preferences(window.settings_store))
