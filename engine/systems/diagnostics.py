"""Structured, navigable errors shared by the editor and script loader."""
from dataclasses import dataclass
from pathlib import Path
import traceback


@dataclass
class Diagnostic:
    message: str
    hint: str
    path: str = ''
    line: int = 1
    column: int = 1
    node: str = ''
    details: str = ''


def explain_exception(error, project_dir='', node=''):
    root=Path(project_dir).resolve() if project_dir else None
    path=getattr(error,'filename','') or ''
    line=getattr(error,'lineno',1) or 1
    column=getattr(error,'offset',1) or 1
    frames=list(traceback.walk_tb(error.__traceback__)) if error.__traceback__ else []
    chosen=None
    for frame,number in frames:
        candidate=Path(frame.f_code.co_filename)
        if candidate.suffix.lower() not in ('.cloud','.py','.cs'): continue
        is_user = 'scripts' in candidate.parts or candidate.suffix.lower()=='.cloud'
        if root and candidate.is_absolute() and candidate.resolve().is_relative_to(root): is_user=True
        if is_user: chosen=(str(candidate),number)
        instance=frame.f_locals.get('self')
        owner=getattr(instance,'owner',None)
        name=getattr(owner or instance,'name',None)
        if isinstance(name,str): node=name
    if not isinstance(error,SyntaxError) and chosen: path,line=chosen
    hints={
        'IndentationError':'Проверьте отступы этого блока. Используйте одинаковые пробелы вместо смеси пробелов и табуляции.',
        'TabError':'Замените табуляцию пробелами и выровняйте строки блока.',
        'SyntaxError':'Проверьте скобки, кавычки, двоеточие и лишние символы в указанной строке.',
        'NameError':'Проверьте имя переменной и создайте её до использования.',
        'AttributeError':'Проверьте наличие объекта, компонента или свойства и правильность его имени.',
        'ZeroDivisionError':'Проверьте делитель: он не должен быть равен нулю.',
        'TypeError':'Проверьте типы значений и количество аргументов вызова.',
        'IndexError':'Проверьте размер списка и границы индекса.',
        'KeyError':'Проверьте наличие ключа в словаре перед обращением.',
        'FileNotFoundError':'Файл не найден. Проверьте путь и наличие ресурса в проекте.',
        'PermissionError':'Не удалось получить доступ к файлу. Проверьте права и не занят ли он другой программой.',
    }
    kind=type(error).__name__
    message=getattr(error,'msg',None) or str(error)
    title={'SyntaxError':'Ошибка синтаксиса','IndentationError':'Неверный отступ',
           'NameError':'Неизвестное имя','AttributeError':'Объект или свойство не найдено',
           'ZeroDivisionError':'Деление на ноль','FileNotFoundError':'Файл не найден',
           'TypeError':'Несовместимые значения','IndexError':'Индекс вне списка',
           'KeyError':'Ключ не найден','PermissionError':'Нет доступа к файлу'}.get(kind,kind)
    return Diagnostic(f'{title}: {message}',hints.get(kind,'Откройте подробности ошибки и проверьте указанное действие.'),
                      str(path),line,column,node,''.join(traceback.format_exception(type(error),error,error.__traceback__)))
