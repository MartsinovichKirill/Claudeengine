"""Persisted RU/EN UI translation, without changing project data or enum values."""
from PyQt6.QtCore import QObject, QEvent, QSettings, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QLabel, QAbstractButton, QGroupBox, QDockWidget, QMenu

EN = dict(line.split('|', 1) for line in '''Файл|File
Правка|Edit
Проект|Project
Сцена|Scene
Нода|Node
Компонент|Component
Вид|View
Окно|Window
Справка|Help
Отладка|Debug
Инструменты|Tools
Плагины|Plugins
Шаблоны|Templates
Сохранить шаблон ZIP…|Save template ZIP…
Контроллер игрока 2D|2D Player Controller
Контроллер игрока 2D…|2D Player Controller…
Анимации AnimatedSprite2D…|AnimatedSprite2D animations…
Добавить в проект…|Add to project…
Кадров/с|Frames/sec
Зациклить|Loop
Предпросмотр|Preview
Новая|New
Убрать кадры|Remove frames
Добавить PNG…|Add PNG…
Выровнять|Align
Язык / Language|Language / Язык
Открыть|Open
Сохранить|Save
Отменить|Undo
Повторить|Redo
Копировать|Copy
Вставить|Paste
Удалить|Delete
Закрыть|Close
Применить|Apply
Добавить|Add
Создать|Create
Выбрать|Select
Обновить|Refresh
Играть|Play
Пауза|Pause
Остановить|Stop
Настройки|Settings
Настройки проекта|Project settings
Запустить проект|Run project
Новая сцена|New scene
Открыть сцену...|Open scene...
Сохранить сцену|Save scene
Сохранить сцену как...|Save scene as...
Выход|Exit
Новый проект|New project
Открыть проект|Open project
Открыть проект...|Open project...
Создать проект|Create project
Последние проекты|Recent projects
Двойной щелчок — продолжить работу|Double-click to continue
Рабочее пространство для ваших идей|A workspace for your ideas
Cloud Hub — проекты|Cloud Hub — projects
Cloud Engine — редактор|Cloud Engine — editor
Название проекта|Project name
Папка проектов|Projects folder
Расположение|Location
Ширина|Width
Высота|Height
Разрешение|Resolution
Пиксельная графика|Pixel art
Обзор…|Browse…
Выбрать папку…|Choose folder…
Сцена (Hierarchy)|Scene (Hierarchy)
Инспектор|Inspector
Ресурсы|Assets
Ресурсы (FileSystem)|Assets (FileSystem)
Консоль|Console
Скрипт|Script
Профилировщик|Profiler
Плитки (TileMap)|Tiles (TileMap)
Панель инструментов|Toolbar
Выбор (Q)|Select (Q)
Рука / панорама (W)|Hand / Pan (W)
Перемещение (E)|Move (E)
Вращение (R)|Rotate (R)
Масштаб (T)|Scale (T)
Играть (F5)|Play (F5)
Пауза (F6)|Pause (F6)
Остановить (F7)|Stop (F7)
Сохранить сцену (Ctrl+S)|Save scene (Ctrl+S)
Отменить (Ctrl+Z)|Undo (Ctrl+Z)
Повторить (Ctrl+Y)|Redo (Ctrl+Y)
Показывать сетку|Show grid
Показывать маркеры нод|Show node markers
Фокус на выбранной ноде (F)|Focus selected (F)
2D режим|2D mode
Прилипание к сетке (Ctrl+G)|Snap to grid (Ctrl+G)
Настройки проекта (Ctrl+,)|Project settings (Ctrl+,)
Собрать EXE...|Build EXE...
Дублировать ноду|Duplicate node
Удалить ноду|Delete node
Фокус на ноде|Focus node
Добавить компонент|Add component
Трансформация|Transform
Позиция|Position
Вращение|Rotation
Масштаб|Scale
Имя|Name
Тип|Type
Цвет|Color
Размер|Size
Смещение|Offset
Сбросить|Reset
Включён|Enabled
Объект не выбран|No object selected
Нет открытой сцены.|No scene is open.
Инструмент|Tool
Параметры кисти|Brush settings
Коллизия (твёрдый тайл)|Collision (solid tile)
Закрашенные тайлы станут препятствием для физики|Painted tiles block physics bodies
Размер ячейки|Cell size
Показывать сетку тайлов|Show tile grid
Тайлы набора|Tileset
Добавить спрайты…|Add sprites…
Очистить карту|Clear map
Выключено|Off
Кисть|Brush
Ластик|Eraser
Заливка|Fill
Прямоугольник|Rectangle
TileMap не выбран|No TileMap selected
Нарезать спрайт…|Slice sprite…
Sprite Studio — нарезка спрайтов|Sprite Studio — sprite slicing
Пропускать полностью прозрачные части|Skip fully transparent regions
Префикс файлов|File prefix
Сохранить части и JSON…|Save regions and JSON…
Удалить часть|Delete region
Отступ X|Offset X
Зазор X|Spacing X
Импортировать файлы...|Import files...
Предпросмотр и настройки импорта…|Import preview and settings…
Новая папка|New folder
Переименовать|Rename
Новая сцена (.scene)|New scene (.scene)
Новый скрипт (.py)|New script (.py)
Новый Cloud Script (.cloud)|New Cloud Script (.cloud)
Новый C# скрипт (.cs)|New C# script (.cs)
Новый шейдер (.shader)|New shader (.shader)
Назначить скрипт выбранному объекту|Attach script to selected object
Документация|Documentation
Перезагрузить скрипты|Reload scripts
Проверить|Validate
Очистить|Clear
О движке|About
Восстановить расположение панелей|Reset panel layout
Продолжить|Continue
Шаг с заходом|Step into
Шаг с обходом|Step over
Шаг с выходом|Step out
Точки остановки|Breakpoints
Переменные|Variables
Стек вызовов|Call stack
Редактор материалов|Material editor
Редактор интерфейсов|UI editor
Текстура|Texture
Материал|Material
Сохранить материал|Save material
Ошибка|Error
Готово|Done
Отмена|Cancel
Да|Yes
Нет|No'''.splitlines())

EN.update({'Поиск: имя файла или ID тайла':'Search: filename or tile ID', '★ Избранный тайл':'★ Favourite tile', 'Все тайлы':'All tiles', 'С коллизией':'Solid tiles', 'Без коллизии':'Non-solid tiles', 'Избранное':'Favourites', 'Проверка сцены':'Scene validation', '■ Зелёная рамка — коллизия · ★ — избранное':'■ Green outline: collision · ★: favourite'})

class Localization(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.language = QSettings('CloudEngine', 'Language').value('language', 'ru')
        self.pending = False
        app.installEventFilter(self)
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Show, QEvent.Type.Polish, QEvent.Type.LayoutRequest) and not self.pending:
            self.pending = True
            QTimer.singleShot(0, self.refresh)
        return False
    def translate_property(self, obj, getter, setter):
        value = getattr(obj, getter)()
        key = '_cloud_i18n_' + getter
        previous = obj.property(key)
        source = previous[0] if previous and value == previous[1] else value
        translated = EN.get(source, source) if self.language == 'en' else source
        obj.setProperty(key, [source, translated])
        if translated != value:
            getattr(obj, setter)(translated)
    def refresh(self):
        # Editable content and resource/project names never pass through translation.
        app = QApplication.instance()
        for widget in app.allWidgets():
            for getter, setter in [('toolTip','setToolTip'), ('windowTitle','setWindowTitle'), ('placeholderText','setPlaceholderText')]:
                if not hasattr(widget, getter):
                    continue
                self.translate_property(widget, getter, setter)
            if isinstance(widget,QAbstractButton) and widget.icon().isNull():
                from editor.icons import get_icon
                source=widget.text().casefold()
                names={'сохран':'save','save':'save','отмен':'undo','undo':'undo','удал':'delete','delete':'delete','откры':'folder','open':'folder','добав':'add','add':'add','нов':'file','new':'file','экспорт':'build','export':'build','поиск':'search','search':'search','настрой':'settings','settings':'settings'}
                for word,icon in names.items():
                    if word in source:widget.setIcon(get_icon(icon));break
            if isinstance(widget, (QLabel, QAbstractButton)):
                self.translate_property(widget, 'text', 'setText')
            if isinstance(widget, (QGroupBox, QMenu)):
                self.translate_property(widget, 'title', 'setTitle')
            for action in widget.actions():
                self.translate_property(action, 'text', 'setText')
                self.translate_property(action, 'toolTip', 'setToolTip')
        self.pending = False
    def set_language(self, language):
        self.language = language
        QSettings('CloudEngine', 'Language').setValue('language', language)
        self.refresh()

def install(app):
    if not hasattr(app, '_cloud_localization'):
        app._cloud_localization = Localization(app)
    return app._cloud_localization

def language_menu(menu):
    for label, language in [('Русский', 'ru'), ('English', 'en')]:
        action = menu.addAction(label)
        action.triggered.connect(lambda checked=False, code=language: install(QApplication.instance()).set_language(code))
