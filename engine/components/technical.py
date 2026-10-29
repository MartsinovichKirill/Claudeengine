"""Small, executable technical components. No character or game-rule presets."""
import copy
import json
import math
from engine.components.component import Component
from engine.math.vector2 import Vector2


class DataProcessor(Component):
    """Reusable calculation with exported inputs, a result and a changed signal."""
    signals = ['changed']
    operation = None
    arguments = ()
    exported_properties = {}
    def __init__(self):
        super().__init__()
        for name, spec in self.get_exported_properties().items():
            value = copy.deepcopy(spec['default'])
            self.set(name, Vector2(value) if spec['type'] == 'vector2' else value)
        self.last_error = ''
    def evaluate(self):
        result = self.operation(*(getattr(self, name) for name in self.arguments))
        if isinstance(result, float) and not math.isfinite(result):
            raise ValueError('Результат должен быть конечным числом')
        previous = self.result
        self.result = result
        if previous != result:
            self.emit_signal('changed', result)
        self.last_error = ''
        return result
    def _process(self, delta):
        if self.auto_update:
            try:
                self.evaluate()
            except (ValueError, TypeError, ZeroDivisionError, OverflowError, KeyError) as exc:
                self.last_error = str(exc)


TECHNICAL_COMPONENTS = []


def processor(name, description, category, function, inputs, output='float', default=0.0):
    specs = {key: {'type': kind, 'default': value} for key, kind, value in inputs}
    specs.update(result={'type': output, 'default': default}, auto_update={'type': 'bool', 'default': True})
    cls = type(name, (DataProcessor,), {'__module__': __name__, 'type_name': name,
        'description': description, 'operation': staticmethod(function),
        'arguments': tuple(key for key, _, _ in inputs), 'exported_properties': specs})
    globals()[name] = cls
    TECHNICAL_COMPONENTS.append((cls, category))


def numeric(name, description, function, args, output='float'):
    processor(name, description, 'Математика', function,
        [(arg, 'float', 1.0 if arg in ('b', 'maximum', 'length', 'power', 'base', 'to_max') else 0.0) for arg in args],
        output, False if output == 'bool' else 0.0)


_NUMERIC = [
    ('Add', 'Сумма двух чисел', lambda a,b:a+b, ('a','b')),
    ('Subtract', 'Разность двух чисел', lambda a,b:a-b, ('a','b')),
    ('Multiply', 'Произведение двух чисел', lambda a,b:a*b, ('a','b')),
    ('Divide', 'Деление с диагностикой нулевого знаменателя', lambda a,b:a/b, ('a','b')),
    ('Modulo', 'Остаток от деления', lambda a,b:a%b, ('a','b')),
    ('Power', 'Возведение в степень', lambda a,power:a**power, ('a','power')),
    ('SquareRoot', 'Квадратный корень', math.sqrt, ('a',)),
    ('CubeRoot', 'Кубический корень с сохранением знака', lambda a:math.copysign(abs(a)**(1/3),a), ('a',)),
    ('Absolute', 'Абсолютная величина', abs, ('a',)),
    ('Minimum', 'Минимум двух чисел', min, ('a','b')),
    ('Maximum', 'Максимум двух чисел', max, ('a','b')),
    ('Clamp', 'Ограничение числа диапазоном', lambda a,minimum,maximum:max(minimum,min(maximum,a)), ('a','minimum','maximum')),
    ('Saturate', 'Ограничение диапазоном 0…1', lambda a:max(0,min(1,a)), ('a',)),
    ('Floor', 'Округление вниз', lambda a:float(math.floor(a)), ('a',)),
    ('Ceiling', 'Округление вверх', lambda a:float(math.ceil(a)), ('a',)),
    ('Round', 'Округление до ближайшего целого', lambda a:float(round(a)), ('a',)),
    ('Truncate', 'Отбрасывание дробной части', lambda a:float(math.trunc(a)), ('a',)),
    ('Fraction', 'Дробная часть', lambda a:a-math.floor(a), ('a',)),
    ('Sign', 'Знак числа: -1, 0 или 1', lambda a:float((a>0)-(a<0)), ('a',)),
    ('Lerp', 'Линейная интерполяция', lambda a,b,t:a+(b-a)*t, ('a','b','t')),
    ('InverseLerp', 'Положение числа внутри диапазона', lambda a,b,value:(value-a)/(b-a), ('a','b','value')),
    ('Remap', 'Перевод значения между диапазонами', lambda value,a,b,to_min,to_max:to_min+(value-a)/(b-a)*(to_max-to_min), ('value','a','b','to_min','to_max')),
    ('SmoothStep', 'Гладкая интерполяция кубической кривой', lambda a:(lambda t:t*t*(3-2*t))(max(0,min(1,a))), ('a',)),
    ('SmootherStep', 'Гладкая интерполяция пятой степени', lambda a:(lambda t:t*t*t*(t*(t*6-15)+10))(max(0,min(1,a))), ('a',)),
    ('Sine', 'Синус угла в радианах', math.sin, ('a',)),
    ('Cosine', 'Косинус угла в радианах', math.cos, ('a',)),
    ('Tangent', 'Тангенс угла в радианах', math.tan, ('a',)),
    ('ArcSine', 'Обратный синус', math.asin, ('a',)),
    ('ArcCosine', 'Обратный косинус', math.acos, ('a',)),
    ('ArcTangent', 'Обратный тангенс', math.atan, ('a',)),
    ('ArcTangent2', 'Угол направления по двум координатам', math.atan2, ('a','b')),
    ('ToRadians', 'Градусы в радианы', math.radians, ('a',)),
    ('ToDegrees', 'Радианы в градусы', math.degrees, ('a',)),
    ('Exponential', 'Экспонента', math.exp, ('a',)),
    ('Logarithm', 'Логарифм числа по основанию', lambda a,base:math.log(max(a,1e-12),base if base>0 and base!=1 else math.e), ('a','base')),
    ('Logarithm10', 'Десятичный логарифм', lambda a:math.log10(max(a,1e-12)), ('a',)),
    ('Repeat', 'Циклическое ограничение числа', lambda a,length:a%length, ('a','length')),
    ('PingPong', 'Треугольное отражение числа в диапазоне', lambda a,length:length-abs(a%(2*length)-length), ('a','length')),
    ('Step', 'Пороговая функция', lambda a,b:float(a>=b), ('a','b')),
    ('DeltaAngle', 'Кратчайшая разница углов в градусах', lambda a,b:(b-a+180)%360-180, ('a','b')),
    ('MoveTowards', 'Ограниченное приближение значения', lambda a,b,maximum:a+max(-abs(maximum),min(abs(maximum),b-a)), ('a','b','maximum')),
    ('Hypotenuse', 'Гипотенуза по двум катетам', math.hypot, ('a','b')),
    ('SmoothMinimum', 'Плавный минимум двух значений', lambda a,b,length:-math.log(math.exp(-a/max(length,1e-6))+math.exp(-b/max(length,1e-6)))*max(length,1e-6), ('a','b','length')),
    ('Quantize', 'Округление числа по шагу', lambda a,length:round(a/length)*length, ('a','length')),
    ('Reciprocal', 'Обратное число', lambda a:1/a if a else 0.0, ('a',)),
    ('Negate', 'Смена знака', lambda a:-a, ('a',)),
]
for _name, _description, _operation, _args in _NUMERIC:
    numeric(_name, _description, _operation, _args)
for _name, _description, _operation in (
    ('GreaterThan','Проверка больше',lambda a,b:a>b),
    ('LessThan','Проверка меньше',lambda a,b:a<b),
    ('Equal','Проверка равенства',lambda a,b:a==b),
    ('Approximately','Приблизительное равенство',lambda a,b:math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-6))):
    numeric(_name, _description, _operation, ('a','b'), 'bool')

_VECTORS = [
    ('VectorAdd','Сумма векторов',lambda a,b:a+b,'vector2'),
    ('VectorSubtract','Разность векторов',lambda a,b:a-b,'vector2'),
    ('VectorMultiply','Покомпонентное произведение',lambda a,b:Vector2(a.x*b.x,a.y*b.y),'vector2'),
    ('VectorDivide','Покомпонентное деление',lambda a,b:Vector2(a.x/b.x if b.x else 0,a.y/b.y if b.y else 0),'vector2'),
    ('VectorDot','Скалярное произведение',lambda a,b:a.x*b.x+a.y*b.y,'float'),
    ('VectorCross','Векторное произведение 2D',lambda a,b:a.x*b.y-a.y*b.x,'float'),
    ('VectorDistance','Расстояние между точками',lambda a,b:math.hypot(a.x-b.x,a.y-b.y),'float'),
    ('VectorDistanceSquared','Квадрат расстояния',lambda a,b:(a.x-b.x)**2+(a.y-b.y)**2,'float'),
    ('VectorMinimum','Покомпонентный минимум',lambda a,b:Vector2(min(a.x,b.x),min(a.y,b.y)),'vector2'),
    ('VectorMaximum','Покомпонентный максимум',lambda a,b:Vector2(max(a.x,b.x),max(a.y,b.y)),'vector2'),
    ('VectorMidpoint','Середина между точками',lambda a,b:(a+b)*0.5,'vector2'),
    ('VectorReflect','Отражение вектора относительно нормали',lambda a,b:a-b.normalized()*(2*(a.x*b.normalized().x+a.y*b.normalized().y)),'vector2'),
    ('VectorProject','Проекция вектора',lambda a,b:b*((a.x*b.x+a.y*b.y)/(b.x*b.x+b.y*b.y)) if b.x or b.y else Vector2(),'vector2'),
    ('VectorDirection','Единичное направление между точками',lambda a,b:(b-a).normalized(),'vector2'),
    ('VectorAngleBetween','Угол между векторами в радианах',lambda a,b:math.atan2(a.x*b.y-a.y*b.x,a.x*b.x+a.y*b.y),'float'),
]
for _name, _description, _operation, _output in _VECTORS:
    processor(_name,_description,'Векторы',_operation,[('a','vector2',[0,0]),('b','vector2',[1,1])],_output,[0,0] if _output=='vector2' else 0.0)
for _name, _description, _operation, _output in (
    ('VectorNormalize','Нормализация вектора',lambda a:a.normalized(),'vector2'),
    ('VectorLength','Длина вектора',lambda a:math.hypot(a.x,a.y),'float'),
    ('VectorLengthSquared','Квадрат длины',lambda a:a.x*a.x+a.y*a.y,'float'),
    ('VectorPerpendicular','Перпендикулярный вектор',lambda a:Vector2(-a.y,a.x),'vector2'),
    ('VectorAngle','Угол вектора в радианах',lambda a:math.atan2(a.y,a.x),'float'),
    ('VectorAbsolute','Абсолютные координаты',lambda a:Vector2(abs(a.x),abs(a.y)),'vector2'),
    ('VectorFloor','Округление координат вниз',lambda a:Vector2(math.floor(a.x),math.floor(a.y)),'vector2'),
    ('VectorCeiling','Округление координат вверх',lambda a:Vector2(math.ceil(a.x),math.ceil(a.y)),'vector2'),
    ('VectorRound','Округление координат',lambda a:Vector2(round(a.x),round(a.y)),'vector2'),
    ('VectorNegate','Смена направления вектора',lambda a:-a,'vector2')):
    processor(_name,_description,'Векторы',_operation,[('a','vector2',[0,0])],_output,[0,0] if _output=='vector2' else 0.0)

for _name, _description, _operation in (
    ('TextUpper','Перевести текст в верхний регистр',str.upper),
    ('TextLower','Перевести текст в нижний регистр',str.lower),
    ('TextTitle','Заглавные буквы слов',str.title),
    ('TextCapitalize','Заглавная первая буква',str.capitalize),
    ('TextTrim','Удалить пробелы по краям',str.strip),
    ('TextTrimStart','Удалить начальные пробелы',str.lstrip),
    ('TextTrimEnd','Удалить конечные пробелы',str.rstrip),
    ('TextReverse','Обратный порядок символов',lambda text:text[::-1]),
    ('TextCaseFold','Нормализация регистра для сравнения',str.casefold),
    ('TextSwapCase','Смена регистра символов',str.swapcase),
    ('TextEscapeJSON','Экранирование текста как JSON-строки',lambda text:json.dumps(text,ensure_ascii=False)),
    ('TextNormalizeWhitespace','Нормализация пробелов',lambda text:' '.join(text.split())),
    ('TextNormalizePath','Нормализация разделителей пути',lambda text:text.replace('\\','/')),
    ('TextEncodeUTF8Hex','UTF-8 текст в HEX',lambda text:text.encode('utf-8').hex())):
    processor(_name,_description,'Текст и данные',_operation,[('text','string','')],'string','')
for _name, _description, _operation, _output, _default in (
    ('TextConcat','Объединение строк',lambda text,value:text+value,'string',''),
    ('TextContains','Поиск подстроки',lambda text,value:value in text,'bool',False),
    ('TextStartsWith','Проверка начала строки',lambda text,value:text.startswith(value),'bool',False),
    ('TextEndsWith','Проверка окончания строки',lambda text,value:text.endswith(value),'bool',False),
    ('TextFind','Индекс подстроки',lambda text,value:text.find(value),'int',0),
    ('TextCount','Количество вхождений подстроки',lambda text,value:text.count(value),'int',0)):
    processor(_name,_description,'Текст и данные',_operation,[('text','string',''),('value','string','')],_output,_default)
processor('TextLength','Число символов','Текст и данные',len,[('text','string','')],'int',0)
processor('TextReplace','Замена подстроки','Текст и данные',lambda text,old,new:text.replace(old,new),[('text','string',''),('old','string',''),('new','string','')],'string','')


class ShapeRenderer(Component):
    requires_game_object = True
    exported_properties = {
        'size': {'type':'vector2','default':[64,64]},
        'offset': {'type':'vector2','default':[0,0]},
        'color': {'type':'color','default':[110,180,235,255]},
        'width': {'type':'int','default':2,'min':1,'max':128},
        'points': {'type':'string','default':'[[0,-32],[32,32],[-32,32]]'},
        'start_angle': {'type':'float','default':0.0},
        'end_angle': {'type':'float','default':180.0},
    }
    shape = 'rectangle'
    def __init__(self):
        super().__init__()
        for name,spec in self.exported_properties.items():
            self.set(name,Vector2(spec['default']) if spec['type']=='vector2' else copy.deepcopy(spec['default']))
    def draw(self,surface,center,camera):
        import pygame
        transform = self.owner.get_global_transform()
        def point(x,y):
            p = self.owner.world_to_screen(transform.xform(Vector2(x,y)+self.offset),camera)
            return (round(p.x),round(p.y))
        w,h = abs(self.size.x),abs(self.size.y)
        left,top = point(-w/2,-h/2); right,bottom = point(w/2,h/2)
        rect = pygame.Rect(min(left,right),min(top,bottom),max(1,abs(right-left)),max(1,abs(bottom-top)))
        color = tuple(self.color); width = max(1,int(self.width))
        layer = pygame.Surface(surface.get_size(),pygame.SRCALPHA)
        if self.shape in ('rectangle','rectangle_outline'):
            pygame.draw.polygon(layer,color,[point(-w/2,-h/2),point(w/2,-h/2),point(w/2,h/2),point(-w/2,h/2)],width if self.shape.endswith('outline') else 0)
        elif self.shape in ('circle','ring'):
            pygame.draw.circle(layer,color,point(0,0),max(1,int(min(rect.size)/2)),width if self.shape=='ring' else 0)
        elif self.shape in ('ellipse','ellipse_outline'):
            pygame.draw.ellipse(layer,color,rect,width if self.shape.endswith('outline') else 0)
        elif self.shape=='rounded_rectangle':
            pygame.draw.rect(layer,color,rect,border_radius=max(1,int(min(rect.size)/5)))
        elif self.shape=='line':
            pygame.draw.line(layer,color,point(-w/2,-h/2),point(w/2,h/2),width)
        elif self.shape=='cross':
            pygame.draw.line(layer,color,point(-w/2,0),point(w/2,0),width)
            pygame.draw.line(layer,color,point(0,-h/2),point(0,h/2),width)
        elif self.shape=='grid':
            for i in range(9):
                pygame.draw.line(layer,color,point(-w/2+w*i/8,-h/2),point(-w/2+w*i/8,h/2),width)
                pygame.draw.line(layer,color,point(-w/2,-h/2+h*i/8),point(w/2,-h/2+h*i/8),width)
        elif self.shape=='arc':
            pygame.draw.arc(layer,color,rect,math.radians(self.start_angle),math.radians(self.end_angle),width)
        else:
            points = [point(float(p[0]),float(p[1])) for p in json.loads(self.points)]
            if self.shape=='polyline' and len(points)>=2:
                pygame.draw.lines(layer,color,False,points,width)
            elif len(points)>=3:
                pygame.draw.polygon(layer,color,points,width if self.shape=='polygon_outline' else 0)
        surface.blit(layer,(0,0))

for _name,_shape,_description in (
    ('RectangleRenderer','rectangle','Заливка прямоугольника'),
    ('RectangleOutlineRenderer','rectangle_outline','Контур прямоугольника'),
    ('CircleRenderer','circle','Заливка круга'),('RingRenderer','ring','Кольцо'),
    ('EllipseRenderer','ellipse','Заливка эллипса'),('EllipseOutlineRenderer','ellipse_outline','Контур эллипса'),
    ('RoundedRectangleRenderer','rounded_rectangle','Скруглённый прямоугольник'),
    ('LineRenderer','line','Отрезок'),('PolylineRenderer','polyline','Ломаная по точкам'),
    ('PolygonRenderer','polygon','Заливка полигона'),('PolygonOutlineRenderer','polygon_outline','Контур полигона'),
    ('ArcRenderer','arc','Дуга'),('GridRenderer','grid','Сетка 8×8'),('CrossRenderer','cross','Перекрестие')):
    _cls = type(_name,(ShapeRenderer,),{'__module__':__name__,'type_name':_name,'shape':_shape,'description':_description})
    globals()[_name]=_cls; TECHNICAL_COMPONENTS.append((_cls,'Геометрия и отрисовка'))


class TransformConstraint(Component):
    requires_game_object = True
    allow_multiple = False
    exported_properties = {'minimum':{'type':'vector2','default':[-100,-100]},
        'maximum':{'type':'vector2','default':[100,100]},'step':{'type':'float','default':16.0,'min':0.001}}
    operation = None
    def __init__(self):
        super().__init__()
        self.minimum=Vector2(-100,-100); self.maximum=Vector2(100,100); self.step=16.0
    def _process(self,delta):
        self.operation(self)

def clamp_position(c):
    c.owner.position=Vector2(max(c.minimum.x,min(c.maximum.x,c.owner.position.x)),max(c.minimum.y,min(c.maximum.y,c.owner.position.y)))
def snap_position(c):
    step=max(abs(c.step),0.001); c.owner.position=Vector2(round(c.owner.position.x/step)*step,round(c.owner.position.y/step)*step)
def clamp_scale(c):
    c.owner.scale=Vector2(max(c.minimum.x,min(c.maximum.x,c.owner.scale.x)),max(c.minimum.y,min(c.maximum.y,c.owner.scale.y)))
for _name,_description,_operation in (
    ('PositionBounds','Ограничить локальную позицию диапазоном',clamp_position),
    ('PositionGrid','Квантовать локальную позицию по сетке',snap_position),
    ('ScaleBounds','Ограничить масштаб диапазоном',clamp_scale),
    ('UniformScale','Сделать масштаб одинаковым по осям',lambda c:setattr(c.owner,'scale',Vector2(c.owner.scale.x,c.owner.scale.x))),
    ('RotationNormalize','Нормализовать угол до -180…180',lambda c:setattr(c.owner,'rotation',(c.owner.rotation+180)%360-180)),
    ('RotationQuantize','Округлить угол по шагу',lambda c:setattr(c.owner,'rotation',round(c.owner.rotation/max(abs(c.step),.001))*max(abs(c.step),.001))),
    ('RotationBounds','Ограничить угол диапазоном',lambda c:setattr(c.owner,'rotation',max(c.minimum.x,min(c.maximum.x,c.owner.rotation))))):
    _cls=type(_name,(TransformConstraint,),{'__module__':__name__,'type_name':_name,'description':_description,'operation':staticmethod(_operation)})
    globals()[_name]=_cls; TECHNICAL_COMPONENTS.append((_cls,'Ограничения Transform'))


class PhysicsUtility(Component):
    requires_game_object=True
    exported_properties={'value':{'type':'vector2','default':[0,0]},'amount':{'type':'float','default':1.0},'limit':{'type':'float','default':100.0,'min':0.0}}
    operation=None
    def __init__(self):
        super().__init__(); self.value=Vector2(); self.amount=1.0; self.limit=100.0
    def _physics_process(self,delta):
        rigid=self.get_component('Rigidbody2D')
        if rigid and rigid.enabled:
            body=rigid.sync()
            self.operation(self,body,delta)

for _name,_description,_operation in (
    ('ConstantForce2D','Постоянная сила на Rigidbody2D',lambda c,b,dt:b.apply_force(c.value)),
    ('LinearDamping2D','Дополнительное затухание скорости',lambda c,b,dt:setattr(b,'velocity',b.velocity*max(0,1-c.amount*dt))),
    ('AngularDamping2D','Затухание угловой скорости',lambda c,b,dt:setattr(b,'angular_velocity',b.angular_velocity*max(0,1-c.amount*dt))),
    ('VelocityLimit2D','Ограничение линейной скорости',lambda c,b,dt:setattr(b,'velocity',b.velocity.normalized()*min(math.hypot(b.velocity.x,b.velocity.y),max(0,c.limit)))),
    ('AngularVelocityLimit2D','Ограничение угловой скорости',lambda c,b,dt:setattr(b,'angular_velocity',max(-abs(c.limit),min(abs(c.limit),b.angular_velocity)))),
    ('FreezePositionX2D','Блокировка скорости по оси X',lambda c,b,dt:setattr(b,'velocity',Vector2(0,b.velocity.y))),
    ('FreezePositionY2D','Блокировка скорости по оси Y',lambda c,b,dt:setattr(b,'velocity',Vector2(b.velocity.x,0))),
    ('FreezeRotation2D','Блокировка угловой скорости',lambda c,b,dt:setattr(b,'angular_velocity',0.0)),
    ('Acceleration2D','Добавочная постоянная акселерация',lambda c,b,dt:setattr(b,'velocity',b.velocity+c.value*dt)),
    ('ConstantTorque2D','Добавочный угловой момент',lambda c,b,dt:setattr(b,'angular_velocity',b.angular_velocity+c.amount/max(b.mass,.001)*dt))):
    _cls=type(_name,(PhysicsUtility,),{'__module__':__name__,'type_name':_name,'description':_description,'operation':staticmethod(_operation)})
    globals()[_name]=_cls; TECHNICAL_COMPONENTS.append((_cls,'Физические инструменты'))
